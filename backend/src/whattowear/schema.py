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

from .colors import is_hex, name_to_hex, normalize_hex

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
    # Feature 018: the background-removed image, when isolation succeeded at
    # save time. Storage object path, same shape as photo_path — mirrors it
    # exactly rather than introducing a second kind of reference. NULL is a
    # normal, saveable outcome (isolation is best-effort), never an error
    # state (spec.md FR-013).
    isolated_photo_path: str | None = None
    # Presentation-only: pads a non-square photo to 1:1. NOT a garment colour
    # — keeping it out of `colors` keeps the backdrop out of the colour-harmony
    # scorer (docs/design-decisions.md §31).
    photo_background_color: str | None = None
    # Added for feature 004 (closet read) — resolved in /speckit-clarify
    # 2026-07-31: the design system requires both fields on Item detail and
    # the Add-item review card, but neither existed on this contract or in
    # the legacy schema. Additive-only: not part of constitution VI's frozen
    # taxonomy, so no eval regression — every fixture item simply has both
    # as None, which is valid since both are optional.
    name: str | None = None
    notes: str | None = None
    # Added for feature 005 (closet write). Never read back by this
    # feature's own UI (design-system §2.3 excludes a favourite indicator
    # from Item detail) — consumed by future features (Outfits, favourites
    # views). Additive-only, defaults False, no eval regression.
    favorite: bool = False

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
    name: str | None = None
    notes: str | None = None

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
    # The photo BACKGROUND's dominant colour, not the garment's. Never shown
    # as an attribute of the item — it exists so a non-square photo can be
    # padded to 1:1 with a colour that continues its own backdrop instead of
    # a grey letterbox (docs/design-decisions.md §31).
    background_color: str | None = None

    @field_validator("colors")
    @classmethod
    def _colors_must_be_hex(cls, v: list[str] | None) -> list[str] | None:
        return v if v is None else [normalize_hex(c) for c in v]

    @field_validator("background_color")
    @classmethod
    def _background_color_must_be_hex(cls, v: str | None) -> str | None:
        """Tolerant, unlike `colors`: a malformed background colour costs a
        cosmetic fallback, never a failed extraction, so it is dropped
        rather than raised on."""
        if v is None:
            return None
        try:
            return normalize_hex(v)
        except ValueError:
            return None


class BoundingBox(BaseModel):
    """A detection's region within the original photo, as fractions of its
    width/height (0-1) — resolution-independent, so the frontend applies it
    against the browser's own naturalWidth/naturalHeight rather than the
    backend needing to know the display size (specs/018-photo-to-items/
    research.md §4). `{0,0,1,1}` means "the whole photo" — the fallback
    region for the single-draft cases vision.detect_garments_from_image
    never itself constructs (that's the route's job, see closet.py)."""

    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    width: float = Field(gt=0, le=1)
    height: float = Field(gt=0, le=1)


class DetectedGarment(BaseModel):
    """One detection from vision.detect_garments_from_image — a region plus
    the same attribute set a single-item photo has always produced. Feature
    018 (photo-to-items): one VLM call now returns a list of these instead
    of one ExtractedAttributes for the whole photo (research.md §1)."""

    region: BoundingBox
    attributes: ExtractedAttributes


class PhotoExtractionResponse(BaseModel):
    """What one detection's draft looks like — an unsaved draft. Unchanged
    shape from before feature 018 (photo_path, extracted, extraction_ok), so
    a caller inspecting a single element of the now-list response
    (PhotoExtractionListResponse) sees exactly what the old single-object
    response returned (spec.md FR-004)."""

    photo_path: str
    extracted: ExtractedAttributes
    extraction_ok: bool
    region: BoundingBox
    # Storage object path of the isolated image, when isolation succeeded
    # for this detection. Always present, possibly null — never omitted, so
    # clients don't need an `in` check (contracts/closet-items-extract.md).
    isolated_photo_path: str | None = None


class PhotoExtractionListResponse(BaseModel):
    """POST /closet/items/extract's actual response shape from feature 018
    on: always a list, even when it holds exactly one draft (spec.md
    FR-001) — an extension of the existing contract, not a new route."""

    drafts: list[PhotoExtractionResponse]
    # True when more garments were detected than wtw_max_detections_per_photo
    # kept (spec.md FR-002) — the 8 kept are the most confidently/prominently
    # detected, never a silent drop.
    truncated: bool


class ConversationalTurnResult(BaseModel):
    """One conversational-turn LLM call's output (feature 016, conversation.py) —
    `reply_text` plus whatever slots it newly extracted, matching `GraphState`'s
    own field names exactly (docs/design-decisions.md §47). `reply_text` is
    always present; a call that produces nothing else is still a valid result
    (most turns after the first extract nothing new)."""

    reply_text: str
    occasion: str | None = None
    mood: str | None = None
    formality: Formality | None = None
    location: str | None = None
    temp_c: float | None = None

    @field_validator("formality", mode="before")
    @classmethod
    def _formality_must_be_known(cls, v: str | None) -> str | None:
        """An unrecognized value from the model is dropped, never passed
        through as a parallel formality scale (constitution Principle VI) —
        tolerant the same way `_background_color_must_be_hex` above is,
        because one bad field must not fail the whole turn (`reply_text`
        and every other slot are still worth keeping)."""
        if v is None or v in FORMALITY_ORDER:
            return v
        return None


class CreateWardrobeItemFromUploadRequest(BaseModel):
    """Body of a wardrobe-item-from-upload request — the user-confirmed
    (possibly corrected) attributes.

    `formality`/`warmth`/`season` are REQUIRED, reversing design-decisions
    §23.3. They were briefly optional, on the reasoning that the design's
    six-field review card must not be blocked by anything outside it — but
    the frontend then simply never sent them, and this route substituted
    defaults. Every item added by photo landed as
    `formality='casual', warmth=3, season=[all four]` regardless of what
    the VLM had actually detected, which is worse than either a blocked
    save or an honest null: it is fabricated data, indistinguishable from
    a real reading, feeding a styling pipeline that reasons over exactly
    these fields. The review card now carries all eight extracted
    attributes (design-decisions.md §30), so requiring them here is what
    makes "the scan's findings are what gets stored" enforceable rather
    than merely intended — the legacy app's own SC-003 guarantee.

    `fabric`/`pattern`/`fit` stay optional: the database allows NULL for
    them, so an honest "not detected, not supplied" is representable and
    no default has to be invented.

    `name`/`notes` are on the review card too but are never scan-filled —
    `vision.py`'s `_EXTRACTION_SCHEMA` has no such fields (the VLM prompt
    only asks for garment attributes, not a user-facing label), so these
    two start blank on every review card and are purely user-typed,
    matching `WardrobeItem`'s own existing optionality for both."""

    photo_path: str
    # Feature 018: passed straight through from the extract response's
    # matching draft, unmodified — this route does not re-attempt isolation
    # or otherwise touch it beyond persisting it and the ownership-prefix
    # check below (spec.md FR-013 — isolation failure is never retried at
    # save time). None when the draft never got a usable isolated image.
    isolated_photo_path: str | None = None
    category: str
    colors: list[str] = Field(min_length=1)
    formality: Formality
    warmth: int = Field(ge=0, le=5)
    season: list[Season] = Field(min_length=1)
    fabric: str | None = None
    pattern: str | None = None
    fit: str | None = None
    name: str | None = None
    notes: str | None = None
    photo_background_color: str | None = None

    @field_validator("colors")
    @classmethod
    def _colors_resolve_name_or_hex(cls, v: list[str]) -> list[str]:
        """Unlike `WardrobeItem`/`WardrobeItemPatch` (hex-only — the review
        card never reaches those directly), the review card's Color field
        is free text pre-filled with a *name* (`colors.nearest_names`), so
        this is the one write path that must resolve a name back to hex
        itself (design-decisions.md §23.4, research.md §5) — the frontend
        only gates *whether* to submit (`isRecognizedColorName`); this is
        the authoritative resolution. Raises naming the unresolved value,
        never silently drops or guesses one."""
        resolved: list[str] = []
        for value in v:
            if is_hex(value):
                resolved.append(normalize_hex(value))
                continue
            try:
                resolved.append(name_to_hex(value))
            except KeyError:
                raise ValueError(f"{value!r} isn't a recognized color name or hex code") from None
        return resolved


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
