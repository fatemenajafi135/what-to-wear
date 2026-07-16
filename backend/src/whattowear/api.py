"""Thin FastAPI test surface over the styling graph — for exercising the
engine over HTTP. No UI/frontend (that's a parallel track). Run:

    uv run uvicorn whattowear.api:app --reload
"""

from __future__ import annotations

import json
import os
import uuid

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from . import crud, storage, vision
from .auth import get_bearer_token, get_current_user_id
from .db import get_session
from .pipeline.graph import get_compiled_graph
from .schema import (
    CreateWardrobeItemFromUploadRequest,
    ExtractedAttributes,
    PhotoExtractionResponse,
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


@app.get("/health")
def health() -> dict:
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
    (T036b) since a raw StreamingResponse alone wouldn't."""
    graph = get_compiled_graph()
    thread_id = req.thread_id or str(uuid.uuid4())
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
        },
        config=config,
    )

    def event_stream():
        for i, outfit in enumerate(final_state["scored_outfits"]):
            payload = {"index": i, "outfit": outfit.model_dump(mode="json")}
            yield f"event: outfit\ndata: {json.dumps(payload)}\n\n"

        done_payload = {
            "thread_id": final_state["thread_id"],
            "result": final_state["result"].model_dump(mode="json"),
            "note": final_state.get("note"),
        }
        yield f"event: done\ndata: {json.dumps(done_payload)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


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
