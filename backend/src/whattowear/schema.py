"""Shared data contracts for the styling engine.

These types are the stable seams between phases: `WardrobeItem` is the contract
the (future) wardrobe-capture flow must produce; `Context` is what the pipeline
consumes; `OutfitResult` is what `recommend()` returns to any caller (test API,
Demo Day UI, MCP tool).
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

from .colors import normalize_hex

# --- controlled vocabularies -------------------------------------------------

Layer = Literal["L1", "L2", "L3", "L4"]
# Ordered formality scale; the L4 filter compares against these.
Formality = Literal["casual", "smart_casual", "business_casual", "semi_formal", "formal", "black_tie"]
FORMALITY_ORDER: dict[str, int] = {
    "casual": 0,
    "smart_casual": 1,
    "business_casual": 2,
    "semi_formal": 3,
    "formal": 4,
    "black_tie": 5,
}
TempBand = Literal["freezing", "cold", "cool", "mild", "warm", "hot"]
Season = Literal["spring", "summer", "autumn", "winter"]


# --- knowledge-base chunk metadata (stamped AT INGEST) -----------------------


class ChunkMeta(BaseModel):
    """Metadata attached to every KB chunk. Citations depend on these existing
    from chunk one (handoff §7) — never bolted on later."""

    source: str  # human-readable source name
    url: str  # provenance link (for the cited-output "sources" line)
    layer: Layer
    rule_id: str  # stable, unique — what the generator cites
    license: Optional[str] = None  # e.g. "PD", "CC-BY-SA", "own"
    # optional structured fields used by the L4 metadata filter
    occasion: Optional[str] = None
    formality: Optional[Formality] = None
    temp_band: Optional[TempBand] = None
    season: Optional[Season] = None


# --- inputs ------------------------------------------------------------------


class WardrobeItem(BaseModel):
    """A single owned garment. Wardrobe capture is out of scope this phase;
    this is the shape the capture flow must eventually emit.

    `colors` are hex — the source of truth (see colors.py). Human-readable
    names are derived on demand via colors.nearest_names(), never stored, so
    name and hex can never drift out of sync."""

    id: str
    category: str  # e.g. "top", "trousers", "outerwear", "shoes"
    colors: list[str] = Field(default_factory=list)  # hex, e.g. "#1b2a4a"
    formality: Formality
    warmth: int = Field(ge=0, le=5)  # 0 = airy, 5 = heaviest
    season: list[Season] = Field(default_factory=list)
    fabric: Optional[str] = None
    source: Optional[Literal["catalog", "upload"]] = None

    @field_validator("colors")
    @classmethod
    def _colors_must_be_hex(cls, v: list[str]) -> list[str]:
        return [normalize_hex(c) for c in v]


class Context(BaseModel):
    """Normalized request context (pipeline stage 1 output)."""

    occasion: str
    formality: Formality
    mood: Optional[str] = None
    temp_c: Optional[float] = None
    condition: Optional[str] = None  # e.g. "rain", "clear"
    temp_band: Optional[TempBand] = None
    season: Optional[Season] = None
    wardrobe: list[WardrobeItem] = Field(default_factory=list)
    user_id: Optional[str] = None


# --- outputs -----------------------------------------------------------------


class Rationale(BaseModel):
    text: str
    cites: list[str] = Field(default_factory=list)  # rule_ids — grounding proof


class CitedSource(BaseModel):
    rule_id: str
    source: str
    url: str
    layer: Layer


class Outfit(BaseModel):
    items: list[str]  # wardrobe item ids ONLY
    rationale: list[Rationale]


class OutfitResult(BaseModel):
    """What `recommend()` returns. 1-3 outfits + resolved sources."""

    outfits: list[Outfit]
    sources: list[CitedSource] = Field(default_factory=list)
    context: Optional[Context] = None
