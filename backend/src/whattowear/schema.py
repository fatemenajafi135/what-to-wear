"""Shared data contracts for the styling engine.

These types are the stable seams between phases: `WardrobeItem` is the contract
the (future) wardrobe-capture flow must produce; `Context` is what the pipeline
consumes; `OutfitResult` is `pipeline.cite.build_result`'s internal return
shape (its only remaining consumer since /recommend's retirement — Feature
002 Phase 3 T037a); `SuggestResult` is what `POST /suggest` actually returns
to callers.
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
    pattern: Optional[str] = None  # free-text, matches fabric's shape (Feature 003)
    fit: Optional[str] = None  # free-text, matches fabric's shape (Feature 003)
    photo_path: Optional[str] = None  # Storage object path, set once at creation (Feature 006)

    @field_validator("colors")
    @classmethod
    def _colors_must_be_hex(cls, v: list[str]) -> list[str]:
        return [normalize_hex(c) for c in v]


class WardrobeItemPatch(BaseModel):
    """A partial correction to an owned WardrobeItem (US3). Every field is
    optional -- only fields present in the request are applied, matching
    PATCH semantics. Reuses the same field-level validation as WardrobeItem
    so an invalid value is rejected with a 422 before it ever reaches the DB
    (FR-007), while `category` stays open-ended (its slot/bucket is derived
    on read via categories.group_of(), never itself validated here)."""

    category: Optional[str] = None
    colors: Optional[list[str]] = None
    formality: Optional[Formality] = None
    warmth: Optional[int] = Field(default=None, ge=0, le=5)
    season: Optional[list[Season]] = None
    fabric: Optional[str] = None
    pattern: Optional[str] = None  # free-text, matches fabric's shape (Feature 003)
    fit: Optional[str] = None  # free-text, matches fabric's shape (Feature 003)
    photo_path: Optional[str] = None  # Storage object path; None clears it (Feature 008 US4)

    @field_validator("colors")
    @classmethod
    def _colors_must_be_hex(cls, v: Optional[list[str]]) -> Optional[list[str]]:
        return v if v is None else [normalize_hex(c) for c in v]


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


# --- photo-based item ingestion (Feature 003: mvp-app) -----------------------


class ExtractedAttributes(BaseModel):
    """Draft output of one VLM extraction call over a single item photo.
    Every field optional — extraction failing on any/all of them must not
    block adding the item (FR-006); the user fills in whatever's missing."""

    category: Optional[str] = None
    colors: Optional[list[str]] = None
    fabric: Optional[str] = None
    warmth: Optional[int] = Field(default=None, ge=0, le=5)
    formality: Optional[Formality] = None
    season: Optional[list[Season]] = None
    pattern: Optional[str] = None
    fit: Optional[str] = None

    @field_validator("colors")
    @classmethod
    def _colors_must_be_hex(cls, v: Optional[list[str]]) -> Optional[list[str]]:
        return v if v is None else [normalize_hex(c) for c in v]


class PhotoExtractionResponse(BaseModel):
    """What POST /wardrobe/items/extract returns — an unsaved draft."""

    photo_path: str
    extracted: ExtractedAttributes
    extraction_ok: bool


class CreateWardrobeItemFromUploadRequest(BaseModel):
    """Body of POST /wardrobe/items/upload — the user-confirmed (possibly
    corrected) attributes. fabric/pattern/fit are required HERE ONLY: SC-003
    requires 100% of items saved through the photo flow to have every
    attribute populated, none blank. WardrobeItem/WardrobeItemPatch (the
    correction path) keep all three optional, unchanged."""

    photo_path: str
    category: str
    colors: list[str] = Field(min_length=1)
    formality: Formality
    warmth: int = Field(ge=0, le=5)
    season: list[Season] = Field(min_length=1)
    fabric: str
    pattern: str
    fit: str

    @field_validator("colors")
    @classmethod
    def _colors_must_be_hex(cls, v: list[str]) -> list[str]:
        return [normalize_hex(c) for c in v]


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
    """`pipeline.cite.build_result`'s return shape — its only remaining
    consumer is `pipeline.graph.explain`, which uses just `.sources` from
    it (the graph's own `ScoredOutfit` list is the real outfits, see
    `SuggestResult`). Kept only because `cite.py` stays unchanged
    (constitution Principle I); not a public response type."""

    outfits: list[Outfit]
    sources: list[CitedSource] = Field(default_factory=list)
    context: Optional[Context] = None


# --- preference memory (Feature 004: preference-memory) ----------------------

Verdict = Literal["liked", "rejected"]


class SubmitFeedbackRequest(BaseModel):
    """Body of POST /preferences/feedback. item_ids identify the reacted-to
    outfit -- resolved server-side against the caller's own wardrobe_items,
    never trusted as-is (see crud.record_feedback)."""

    verdict: Verdict
    reason: Optional[str] = None  # only meaningful when verdict == "rejected"
    item_ids: list[str] = Field(min_length=1)


class SuggestionFeedback(BaseModel):
    """What POST /preferences/feedback returns."""

    id: str
    verdict: Verdict
    reason: Optional[str] = None
    item_ids: list[str]
    created_at: str


class PreferenceSignal(BaseModel):
    key: str  # "color:#1b2a4a" / "category:blazer" / "formality_drift"
    summary: str  # plain-language, e.g. "You tend to reject navy items."


class PreferenceProfile(BaseModel):
    """What GET /preferences returns. has_feedback distinguishes "no
    feedback at all" (FR-008's empty state) from "feedback exists but no
    signal has crossed threshold yet" (also signals=[], but has_feedback is
    True)."""

    has_feedback: bool
    signals: list[PreferenceSignal] = Field(default_factory=list)


Approach = Literal["direct", "grounded", "engine", "agentic", "compare"]


class SuggestRequest(BaseModel):
    """Body of POST /suggest (contracts/suggest.md). No `user_id` field —
    same fix as RecommendRequest post-Phase-1: identity always comes from
    the verified JWT `sub` (FR-001).

    `approach` (Feature 010, WP2): which selection strategy to run.
    `"grounded"` names today's existing default pipeline (LLM assembles
    outfits, `generate_outfits`/`score_and_rank`) so its meaning is
    explicit rather than implicit-via-absence. Only `"grounded"` (the
    default) and `"engine"` are routed anywhere by this feature; the other
    values are accepted (matching the full roadmap) but fall through to
    the `grounded` branch unchanged, same as omitting the field."""

    occasion: str
    mood: Optional[str] = None
    formality: Optional[Formality] = None
    location: Optional[str] = None
    temp_c: Optional[float] = None
    strategy: str = "advanced"
    thread_id: Optional[str] = None
    approach: Approach = "grounded"


# --- deterministic scoring (Feature 002 Phase 2+) -----------------------------

ScoreDimension = Literal["color_harmony", "formality_coherence", "weather_fitness", "silhouette_balance"]
SCORE_DIMENSIONS: tuple[ScoreDimension, ...] = (
    "color_harmony",
    "formality_coherence",
    "weather_fitness",
    "silhouette_balance",
)


class DimensionScore(BaseModel):
    """One deterministic scorer's output for one outfit (data-model.md)."""

    dimension: ScoreDimension
    value: float = Field(ge=0.0, le=1.0)
    reason: str


class ScoredOutfit(BaseModel):
    """An `Outfit` extended with per-dimension scores and a combined rank
    score (data-model.md). `scores` always carries exactly one entry per
    `SCORE_DIMENSIONS` value (FR-008)."""

    items: list[str]
    rationale: list[Rationale]
    scores: list[DimensionScore]
    rank_score: float

    @field_validator("scores")
    @classmethod
    def _scores_cover_all_dimensions(cls, v: list[DimensionScore]) -> list[DimensionScore]:
        dims = [s.dimension for s in v]
        if sorted(dims) != sorted(SCORE_DIMENSIONS) or len(dims) != len(set(dims)):
            raise ValueError(
                f"ScoredOutfit.scores must have exactly one entry per dimension in {SCORE_DIMENSIONS}, got {dims!r}"
            )
        return v


class SuggestResult(BaseModel):
    """What POST /suggest's `result` field carries (contracts/suggest.md) —
    OutfitResult's shape, but with ScoredOutfit entries. A separate type
    from OutfitResult (not a field-type change on it) since OutfitResult is
    kept as `pipeline.cite.build_result`'s internal return shape (see its
    docstring above) rather than merged away."""

    outfits: list[ScoredOutfit]
    sources: list[CitedSource] = Field(default_factory=list)
    context: Optional[Context] = None
