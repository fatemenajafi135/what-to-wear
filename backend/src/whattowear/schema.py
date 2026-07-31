"""Shared data contracts for the styling engine.

These types are the stable seams between the AI layer and everything that
will call it: `WardrobeItem` is the contract wardrobe capture must produce;
`Context` is what the pipeline consumes; `OutfitResult` is
`pipeline.cite.build_result`'s internal return shape; `SuggestResult` is
what a suggest endpoint returns to callers. Constitution Principle VII:
these Pydantic models ARE the API contract — no hand-maintained duplicate
type definition is permitted elsewhere.

Ported whole, not trimmed to only what this feature's own modules import:
this file is the single source of truth for every AI-adjacent contract
future features (wardrobe capture, preference memory, the suggest route)
will need, and fragmenting it now would just mean re-adding the same types
later, against the file that owns them. No logic changes from the legacy
version — only `Optional[X]` -> `X | None` (this project's convention
elsewhere, e.g. core/config.py, ports.py) and updated cross-references.
"""

from __future__ import annotations

from typing import Literal

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
    """Metadata attached to every KB chunk. Citations depend on these
    existing from chunk one — never bolted on later."""

    source: str  # human-readable source name
    url: str  # provenance link (for the cited-output "sources" line)
    layer: Layer
    rule_id: str  # stable, unique — what the generator cites
    license: str | None = None  # e.g. "PD", "CC-BY-SA", "own"
    # optional structured fields used by the L4 metadata filter
    occasion: str | None = None
    formality: Formality | None = None
    temp_band: TempBand | None = None
    season: Season | None = None


# --- inputs ------------------------------------------------------------------


class WardrobeItem(BaseModel):
    """A single owned garment.

    `colors` are hex — the source of truth (see colors.py). Human-readable
    names are derived on demand via colors.nearest_names(), never stored, so
    name and hex can never drift out of sync."""

    id: str
    category: str  # e.g. "top", "trousers", "outerwear", "shoes"
    colors: list[str] = Field(default_factory=list)  # hex, e.g. "#1b2a4a"
    formality: Formality
    warmth: int = Field(ge=0, le=5)  # 0 = airy, 5 = heaviest
    season: list[Season] = Field(default_factory=list)
    fabric: str | None = None
    source: Literal["catalog", "upload"] | None = None
    pattern: str | None = None  # free-text, matches fabric's shape
    fit: str | None = None  # free-text, matches fabric's shape
    photo_path: str | None = None  # Storage object path, set once at creation

    @field_validator("colors")
    @classmethod
    def _colors_must_be_hex(cls, v: list[str]) -> list[str]:
        return [normalize_hex(c) for c in v]


class WardrobeItemPatch(BaseModel):
    """A partial correction to an owned WardrobeItem. Every field is
    optional — only fields present in the request are applied, matching
    PATCH semantics. Reuses the same field-level validation as WardrobeItem
    so an invalid value is rejected before it ever reaches the DB, while
    `category` stays open-ended (its slot/bucket is derived on read via
    categories.group_of(), never itself validated here)."""

    category: str | None = None
    colors: list[str] | None = None
    formality: Formality | None = None
    warmth: int | None = Field(default=None, ge=0, le=5)
    season: list[Season] | None = None
    fabric: str | None = None
    pattern: str | None = None
    fit: str | None = None
    photo_path: str | None = None  # None clears it

    @field_validator("colors")
    @classmethod
    def _colors_must_be_hex(cls, v: list[str] | None) -> list[str] | None:
        return v if v is None else [normalize_hex(c) for c in v]


class Context(BaseModel):
    """Normalized request context (pipeline stage 1 output)."""

    occasion: str
    formality: Formality
    mood: str | None = None
    temp_c: float | None = None
    condition: str | None = None  # e.g. "rain", "clear"
    temp_band: TempBand | None = None
    season: Season | None = None
    wardrobe: list[WardrobeItem] = Field(default_factory=list)
    user_id: str | None = None


# --- photo-based item ingestion ------------------------------------------


class ExtractedAttributes(BaseModel):
    """Draft output of one VLM extraction call over a single item photo
    (vision.py). Every field optional — extraction failing on any/all of
    them must not block adding the item; the user fills in whatever's
    missing."""

    category: str | None = None
    colors: list[str] | None = None
    fabric: str | None = None
    warmth: int | None = Field(default=None, ge=0, le=5)
    formality: Formality | None = None
    season: list[Season] | None = None
    pattern: str | None = None
    fit: str | None = None

    @field_validator("colors")
    @classmethod
    def _colors_must_be_hex(cls, v: list[str] | None) -> list[str] | None:
        return v if v is None else [normalize_hex(c) for c in v]


class PhotoExtractionResponse(BaseModel):
    """What a photo-extraction endpoint returns — an unsaved draft."""

    photo_path: str
    extracted: ExtractedAttributes
    extraction_ok: bool


class CreateWardrobeItemFromUploadRequest(BaseModel):
    """Body of a wardrobe-item-from-upload request — the user-confirmed
    (possibly corrected) attributes. fabric/pattern/fit are required HERE
    ONLY: every item saved through the photo flow must have every attribute
    populated, none blank. WardrobeItem/WardrobeItemPatch (the correction
    path) keep all three optional, unchanged."""

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
    """`pipeline.cite.build_result`'s return shape — consumed by
    `pipeline.graph.explain`, which uses just `.sources` from it (the
    graph's own `ScoredOutfit` list is the real outfits, see
    `SuggestResult`). Kept only because `cite.py` stays unchanged
    (constitution Principle I); not a public response type."""

    outfits: list[Outfit]
    sources: list[CitedSource] = Field(default_factory=list)
    context: Context | None = None


# --- preference memory --------------------------------------------------

Verdict = Literal["liked", "rejected"]


class SubmitFeedbackRequest(BaseModel):
    """Body of a suggestion-feedback request. item_ids identify the
    reacted-to outfit — resolved server-side against the caller's own
    wardrobe_items, never trusted as-is."""

    verdict: Verdict
    reason: str | None = None  # only meaningful when verdict == "rejected"
    item_ids: list[str] = Field(min_length=1)


class SuggestionFeedback(BaseModel):
    """What a suggestion-feedback endpoint returns."""

    id: str
    verdict: Verdict
    reason: str | None = None
    item_ids: list[str]
    created_at: str


class PreferenceSignal(BaseModel):
    key: str  # "color:#1b2a4a" / "category:blazer" / "formality_drift"
    summary: str  # plain-language, e.g. "You tend to reject navy items."


class PreferenceProfile(BaseModel):
    """What a preferences endpoint returns. `has_feedback` distinguishes "no
    feedback at all" from "feedback exists but no signal has crossed
    threshold yet" (also `signals=[]`, but `has_feedback` is True)."""

    has_feedback: bool
    signals: list[PreferenceSignal] = Field(default_factory=list)


Approach = Literal["direct", "grounded", "engine", "agentic", "compare"]


class SuggestRequest(BaseModel):
    """Body of a suggest request. No `user_id` field — identity always
    comes from the verified JWT `sub`.

    `approach`: which selection strategy to run. `"grounded"` names the
    default pipeline (LLM assembles outfits, `generate_outfits`/
    `score_and_rank`) so its meaning is explicit rather than
    implicit-via-absence. Only `"grounded"` (the default) and `"engine"`
    are routed anywhere by this feature; the other values are accepted
    (matching the full roadmap) but fall through to the `grounded` branch
    unchanged, same as omitting the field."""

    occasion: str
    mood: str | None = None
    formality: Formality | None = None
    location: str | None = None
    temp_c: float | None = None
    strategy: str = "advanced"
    thread_id: str | None = None
    approach: Approach = "grounded"


# --- deterministic scoring -----------------------------------------------

ScoreDimension = Literal["color_harmony", "formality_coherence", "weather_fitness", "silhouette_balance"]
SCORE_DIMENSIONS: tuple[ScoreDimension, ...] = (
    "color_harmony",
    "formality_coherence",
    "weather_fitness",
    "silhouette_balance",
)


class DimensionScore(BaseModel):
    """One deterministic scorer's output for one outfit."""

    dimension: ScoreDimension
    value: float = Field(ge=0.0, le=1.0)
    reason: str


class ScoredOutfit(BaseModel):
    """An `Outfit` extended with per-dimension scores and a combined rank
    score. `scores` always carries exactly one entry per `SCORE_DIMENSIONS`
    value."""

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
    """What a suggest endpoint's `result` field carries — `OutfitResult`'s
    shape, but with `ScoredOutfit` entries. A separate type from
    `OutfitResult` (not a field-type change on it) since `OutfitResult` is
    kept as `pipeline.cite.build_result`'s internal return shape."""

    outfits: list[ScoredOutfit]
    sources: list[CitedSource] = Field(default_factory=list)
    context: Context | None = None
