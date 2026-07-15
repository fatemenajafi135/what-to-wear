"""Thin FastAPI test surface over `recommend()` — for exercising the engine over
HTTP. No UI/frontend (that's a parallel track). Run:

    uv run uvicorn whattowear.api:app --reload
"""

from __future__ import annotations

from typing import Optional

from fastapi import Depends, FastAPI
from pydantic import BaseModel
from sqlalchemy.orm import Session

from . import crud
from .auth import get_current_user_id
from .db import get_session
from .pipeline import cite
from .pipeline.run import run_pipeline
from .schema import Formality, OutfitResult, WardrobeItem

app = FastAPI(title="What to Wear — RAG styling engine (test API)")


class RecommendRequest(BaseModel):
    occasion: str
    mood: Optional[str] = None
    formality: Optional[Formality] = None
    location: Optional[str] = None  # geocoded via Open-Meteo
    temp_c: Optional[float] = None  # fallback if no location / offline
    user_id: Optional[str] = None
    strategy: str = "advanced"  # baseline | hybrid | advanced


class RecommendResponse(BaseModel):
    result: OutfitResult
    rendered: str  # human-readable "why + sources"


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/recommend", response_model=RecommendResponse)
def recommend_endpoint(req: RecommendRequest) -> RecommendResponse:
    run = run_pipeline(
        req.occasion,
        mood=req.mood,
        formality=req.formality,
        location=req.location,
        temp_c=req.temp_c,
        user_id=req.user_id,
        strategy=req.strategy,
    )
    return RecommendResponse(result=run.result, rendered=cite.render_text(run.result))


@app.get("/wardrobe/items", response_model=list[WardrobeItem])
def list_wardrobe_items(
    session: Session = Depends(get_session),
    user_id: str = Depends(get_current_user_id),
) -> list[WardrobeItem]:
    return crud.list_wardrobe_items(session, user_id)
