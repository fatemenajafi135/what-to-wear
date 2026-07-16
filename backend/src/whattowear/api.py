"""Thin FastAPI test surface over `recommend()` — for exercising the engine over
HTTP. No UI/frontend (that's a parallel track). Run:

    uv run uvicorn whattowear.api:app --reload
"""

from __future__ import annotations

import os
import uuid
from typing import Optional

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session

from . import crud, storage, vision
from .auth import get_bearer_token, get_current_user_id
from .colors import nearest_name
from .db import get_session
from .memory.preferences import DerivedSignal, derive_signals
from .pipeline import cite
from .pipeline.run import run_pipeline
from .schema import (
    CreateWardrobeItemFromUploadRequest,
    ExtractedAttributes,
    Formality,
    OutfitResult,
    PhotoExtractionResponse,
    PreferenceProfile,
    PreferenceSignal,
    SubmitFeedbackRequest,
    SuggestionFeedback,
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


class RecommendRequest(BaseModel):
    occasion: str
    mood: Optional[str] = None
    formality: Optional[Formality] = None
    location: Optional[str] = None  # geocoded via Open-Meteo
    temp_c: Optional[float] = None  # fallback if no location / offline
    strategy: str = "advanced"  # baseline | hybrid | advanced
    # user_id is NOT accepted from the body — it comes from the verified JWT
    # `sub` claim (see get_current_user_id). A client-supplied id here would let
    # any caller read any user's closet through the pipeline (the pre-002 leak).


class RecommendResponse(BaseModel):
    result: OutfitResult
    rendered: str  # human-readable "why + sources"


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/recommend", response_model=RecommendResponse)
def recommend_endpoint(
    req: RecommendRequest,
    user_id: str = Depends(get_current_user_id),
) -> RecommendResponse:
    run = run_pipeline(
        req.occasion,
        mood=req.mood,
        formality=req.formality,
        location=req.location,
        temp_c=req.temp_c,
        user_id=user_id,
        strategy=req.strategy,
    )
    return RecommendResponse(result=run.result, rendered=cite.render_text(run.result))


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
