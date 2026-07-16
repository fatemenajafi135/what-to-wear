"""Thin FastAPI test surface over the styling graph — for exercising the
engine over HTTP. No UI/frontend (that's a parallel track). Run:

    uv run uvicorn whattowear.api:app --reload
"""

from __future__ import annotations

import json
import os
import uuid

from fastapi import Depends, FastAPI, File, HTTPException, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from . import crud, storage, vision
from .auth import get_bearer_token, get_current_user_id
from .colors import nearest_name
from .db import engine, get_session
from .ingest.build_kb import COLLECTION, QDRANT_API_KEY, QDRANT_URL
from .memory.preferences import DerivedSignal, derive_signals
from .pipeline import cache as suggest_cache
from .pipeline import context_assembler
from .pipeline.context_assembler import load_wardrobe
from .pipeline.graph import get_compiled_graph
from .schema import (
    CreateWardrobeItemFromUploadRequest,
    ExtractedAttributes,
    PhotoExtractionResponse,
    PreferenceProfile,
    PreferenceSignal,
    SubmitFeedbackRequest,
    SuggestionFeedback,
    SuggestRequest,
    SuggestResult,
    WardrobeItem,
    WardrobeItemPatch,
)

app = FastAPI(title="What to Wear — RAG styling engine (test API)")

_cors_origins = [o.strip() for o in os.environ.get("WTW_CORS_ORIGINS", "*").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _db_reachable() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except SQLAlchemyError:
        return False


def _vector_store_reachable() -> bool:
    """Only meaningful when a real Qdrant server is configured — the
    in-memory fallback (`WTW_QDRANT_URL=""`, dev/CI only) has no external
    dependency to fail. A short-timeout `collection_exists` call, not
    `kb.get_kb()` (a memoized singleton that would trigger a full,
    potentially expensive KB (re)build on the first health check rather
    than a live reachability probe)."""
    if not QDRANT_URL:
        return True
    try:
        from qdrant_client import QdrantClient

        QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY, timeout=5).collection_exists(COLLECTION)
        return True
    except Exception:
        return False


@app.get("/health")
def health(response: Response) -> dict:
    """FR-012 (Feature 005, a `/speckit.analyze` finding against the spec's
    own Edge Case): reports failure when the database or vector store is
    unreachable, not merely when the process itself is running."""
    failed = [
        name for name, ok in [("database", _db_reachable()), ("vector_store", _vector_store_reachable())] if not ok
    ]
    if failed:
        response.status_code = 503
        return {"status": "unhealthy", "failed_dependencies": failed}
    return {"status": "ok"}


@app.post("/suggest", response_model=SuggestResult)
def suggest_endpoint(
    req: SuggestRequest,
    user_id: str = Depends(get_current_user_id),
) -> StreamingResponse:
    """Supersedes /recommend (contracts/suggest.md). Same auth model — the
    requester's identity always comes from the verified JWT `sub`, never the
    body. SSE: an `outfit` event per ranked outfit, then a `done` event
    carrying the full response shape (a client that only reads `done` gets
    the exact non-streaming payload). `response_model` is for OpenAPI docs
    only — returning a Response subclass directly makes FastAPI skip
    response_model serialization, but it's still what generates the
    SuggestResult/ScoredOutfit/DimensionScore schemas the frontend needs
    (T036b) since a raw StreamingResponse alone wouldn't.

    Feature 005 US3/FR-006/007: a fresh (non-continuing) request — no
    incoming `thread_id` — is eligible for the per-user Redis cache
    (`pipeline/cache.py`). A refinement turn (`thread_id` supplied,
    continuing a conversation the checkpointer already has state for)
    always runs the graph — refinements are inherently stateful and aren't
    idempotent the way a first turn is (research.md §2). The wardrobe is
    loaded once here and passed through to the graph either way (`wardrobe=`
    override on `GraphState`), so caching doesn't cost a second DB fetch.

    A cache hit still seeds the checkpointer (`graph.update_state`) with the
    turn's `ctx`/`original_context`/`last_result` before returning — found
    necessary during implementation: a hit's `thread_id` is otherwise never
    passed to `graph.invoke`, so the checkpointer would have no state for it,
    and a later refinement turn continuing that `thread_id` would wrongly be
    treated as a brand-new conversation (`parse_request` only detects a
    continuation via `original_context` already being checkpointed)."""
    is_fresh_request = req.thread_id is None
    thread_id = req.thread_id or str(uuid.uuid4())
    wardrobe = load_wardrobe(user_id)

    cache_key = None
    if is_fresh_request:
        cache_key = suggest_cache.compute_cache_key(
            user_id,
            occasion=req.occasion,
            mood=req.mood,
            formality=req.formality,
            location=req.location,
            temp_c=req.temp_c,
            wardrobe=wardrobe,
        )
        cached = suggest_cache.get_cached_result(cache_key)
        if cached is not None:
            cached_result, cached_note = cached
            graph = get_compiled_graph()
            config = {"configurable": {"thread_id": thread_id}}
            ctx = context_assembler.assemble_context(
                req.occasion,
                mood=req.mood,
                formality=req.formality,
                location=req.location,
                temp_c=req.temp_c,
                wardrobe=wardrobe,
                user_id=user_id,
            )
            graph.update_state(
                config,
                {
                    "thread_id": thread_id,
                    "user_id": user_id,
                    "wardrobe": wardrobe,
                    "ctx": ctx,
                    "original_context": ctx,
                    "last_result": cached_result,
                    "refinement_deltas": [],
                },
            )
            return StreamingResponse(
                _event_stream(thread_id, cached_result, cached_note), media_type="text/event-stream"
            )

    graph = get_compiled_graph()
    config = {"configurable": {"thread_id": thread_id}}
    final_state = graph.invoke(
        {
            "occasion": req.occasion,
            "mood": req.mood,
            "formality": req.formality,
            "location": req.location,
            "temp_c": req.temp_c,
            "strategy": req.strategy,
            "thread_id": thread_id,
            "user_id": user_id,
            "wardrobe": wardrobe,
        },
        config=config,
    )

    if cache_key is not None:
        suggest_cache.set_cached_result(cache_key, final_state["result"], final_state.get("note"))

    return StreamingResponse(
        _event_stream(final_state["thread_id"], final_state["result"], final_state.get("note")),
        media_type="text/event-stream",
    )


def _event_stream(thread_id: str, result: SuggestResult, note: str | None):
    for i, outfit in enumerate(result.outfits):
        payload = {"index": i, "outfit": outfit.model_dump(mode="json")}
        yield f"event: outfit\ndata: {json.dumps(payload)}\n\n"

    done_payload = {
        "thread_id": thread_id,
        "result": result.model_dump(mode="json"),
        "note": note,
    }
    yield f"event: done\ndata: {json.dumps(done_payload)}\n\n"


@app.get("/wardrobe/items", response_model=list[WardrobeItem])
def list_wardrobe_items(
    session: Session = Depends(get_session),
    user_id: str = Depends(get_current_user_id),
) -> list[WardrobeItem]:
    return crud.list_wardrobe_items(session, user_id)


@app.get("/catalog/items", response_model=list[WardrobeItem])
def list_catalog_items(
    session: Session = Depends(get_session),
    user_id: str = Depends(get_current_user_id),  # any authenticated user; catalog isn't user-scoped
) -> list[WardrobeItem]:
    return crud.list_catalog_items(session)


class AddWardrobeItemRequest(BaseModel):
    catalog_item_id: uuid.UUID


class AddWardrobeItemsBulkRequest(BaseModel):
    catalog_item_ids: list[uuid.UUID]


@app.post("/wardrobe/items", response_model=WardrobeItem, status_code=201)
def add_wardrobe_item(
    req: AddWardrobeItemRequest,
    session: Session = Depends(get_session),
    user_id: str = Depends(get_current_user_id),
) -> WardrobeItem:
    item = crud.add_wardrobe_item_from_catalog(session, user_id, req.catalog_item_id)
    if item is None:
        raise HTTPException(404, f"unknown catalog_item_id: {req.catalog_item_id}")
    return item


@app.post("/wardrobe/items/bulk", response_model=list[WardrobeItem], status_code=201)
def add_wardrobe_items_bulk(
    req: AddWardrobeItemsBulkRequest,
    session: Session = Depends(get_session),
    user_id: str = Depends(get_current_user_id),
) -> list[WardrobeItem]:
    try:
        return crud.add_wardrobe_items_from_catalog(session, user_id, req.catalog_item_ids)
    except crud.UnknownCatalogItemIds as e:
        raise HTTPException(404, f"unknown catalog_item_id(s): {[str(i) for i in e.missing_ids]}") from e


@app.patch("/wardrobe/items/{item_id}", response_model=WardrobeItem)
def update_wardrobe_item(
    item_id: uuid.UUID,
    patch: WardrobeItemPatch,
    session: Session = Depends(get_session),
    user_id: str = Depends(get_current_user_id),
) -> WardrobeItem:
    item = crud.update_wardrobe_item(session, user_id, item_id, patch)
    if item is None:
        raise HTTPException(404, f"wardrobe item not found: {item_id}")
    return item


@app.delete("/wardrobe/items/{item_id}", status_code=204)
def delete_wardrobe_item(
    item_id: uuid.UUID,
    session: Session = Depends(get_session),
    user_id: str = Depends(get_current_user_id),
) -> None:
    deleted = crud.delete_wardrobe_item(session, user_id, item_id)
    if not deleted:
        raise HTTPException(404, f"wardrobe item not found: {item_id}")


@app.post("/wardrobe/items/extract", response_model=PhotoExtractionResponse)
def extract_wardrobe_item(
    photo: UploadFile = File(...),
    user_id: str = Depends(get_current_user_id),
    access_token: str = Depends(get_bearer_token),
) -> PhotoExtractionResponse:
    """Draft extraction only — nothing is persisted to wardrobe_items here
    (US2). A photo that can't be confidently interpreted is still a 200 with
    extraction_ok=False, never a 5xx (FR-006)."""
    file_bytes = photo.file.read()
    content_type = photo.content_type or "image/jpeg"
    photo_path = storage.upload_wardrobe_photo(
        user_id, file_bytes, photo.filename or "photo", content_type, access_token
    )

    try:
        extracted = vision.extract_attributes_from_image(file_bytes, content_type)
    except Exception:
        extracted = ExtractedAttributes()

    return PhotoExtractionResponse(
        photo_path=photo_path,
        extracted=extracted,
        extraction_ok=extracted.category is not None,
    )


@app.post("/wardrobe/items/upload", response_model=WardrobeItem, status_code=201)
def upload_wardrobe_item(
    req: CreateWardrobeItemFromUploadRequest,
    session: Session = Depends(get_session),
    user_id: str = Depends(get_current_user_id),
) -> WardrobeItem:
    """Persists a wardrobe item from user-confirmed (possibly corrected)
    attributes -- source='upload', parallel to, not replacing, the
    catalog-based POST /wardrobe/items (US2)."""
    return crud.create_wardrobe_item_from_upload(session, user_id, req)


def _signal_summary(signal: DerivedSignal) -> str:
    """Plain-language projection of a DerivedSignal (FR-007 -- no raw
    hex/internal ids in what the user sees)."""
    if signal.kind == "color":
        return f"You tend to reject {nearest_name(signal.detail)} items."
    if signal.kind == "category":
        return f"You tend to avoid {signal.detail} items."
    if signal.detail == "less_formal":
        return "You usually want suggestions less formal than what's given."
    return "You usually want suggestions more formal than what's given."


def _current_profile(session: Session, user_id: str) -> tuple[bool, list[DerivedSignal]]:
    feedback, dismissals = crud.get_derivation_inputs(session, user_id)
    has_feedback = crud.has_any_feedback(session, user_id)
    return has_feedback, derive_signals(feedback, dismissals)


@app.post("/preferences/feedback", response_model=SuggestionFeedback, status_code=201)
def submit_feedback(
    req: SubmitFeedbackRequest,
    session: Session = Depends(get_session),
    user_id: str = Depends(get_current_user_id),
) -> SuggestionFeedback:
    """Records or replaces a reaction to a specific outfit (US1). item_ids
    are resolved against the caller's own wardrobe -- an id that doesn't
    exist or belongs to someone else is a 404, never silently accepted."""
    try:
        return crud.record_feedback(session, user_id, req)
    except crud.UnknownWardrobeItemIds as e:
        raise HTTPException(404, f"unknown wardrobe item_id(s): {[str(i) for i in e.missing_ids]}") from e


@app.get("/preferences", response_model=PreferenceProfile)
def get_preferences(
    session: Session = Depends(get_session),
    user_id: str = Depends(get_current_user_id),
) -> PreferenceProfile:
    """A plain-language summary of what's been learned (US3). has_feedback
    distinguishes "no feedback at all" from "feedback exists, no signal has
    crossed threshold yet" -- both have signals=[], only the former is False."""
    has_feedback, signals = _current_profile(session, user_id)
    return PreferenceProfile(
        has_feedback=has_feedback,
        signals=[PreferenceSignal(key=s.key, summary=_signal_summary(s)) for s in signals],
    )


@app.delete("/preferences/signals/{signal_key}", status_code=204)
def remove_preference_signal(
    signal_key: str,
    session: Session = Depends(get_session),
    user_id: str = Depends(get_current_user_id),
) -> None:
    """Removes one derived signal without affecting the rest of the profile
    (US4). Idempotent -- dismissing an already-absent signal is a no-op,
    not a 404 (contracts/preferences.md)."""
    crud.dismiss_signal(session, user_id, signal_key)


@app.delete("/preferences", status_code=204)
def clear_preferences(
    session: Session = Depends(get_session),
    user_id: str = Depends(get_current_user_id),
) -> None:
    """Clears the entire derived profile in one action (US4) -- dismisses
    every signal currently present, reusing the exact same per-signal
    mechanism as remove_preference_signal rather than a separate code path
    (research.md #3)."""
    _, signals = _current_profile(session, user_id)
    for signal in signals:
        crud.dismiss_signal(session, user_id, signal.key)
