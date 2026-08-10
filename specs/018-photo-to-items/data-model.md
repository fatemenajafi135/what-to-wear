# Data model: Photo to items

One migration (a nullable column), no new table. This feature's schema surface is: (1) the
migration; (2) `schema.py` additions/changes; (3) new `core/config.py` settings; (4) the
`ports.py` Protocol addition.

## 1. Migration `0013_isolated_photo.sql`

```sql
-- Feature 018: each detection's isolated (background-removed) image is its
-- own Storage object under the same {user_id}/ prefix photo_path already
-- uses — infra/supabase/migrations/0006_wardrobe_photos.sql's RLS policy
-- matches on that prefix alone, so no policy change is needed here, only
-- the pointer column. Additive, not a taxonomy change (Constitution VI is
-- not implicated — spec.md says so explicitly).
--
-- Nullable with no default: isolation is best-effort (FR-013) and every
-- item saved before this migration has none. Both ClosetGrid and the item
-- detail hero already fall back to the original photo when this is null
-- (ItemPhoto's existing behavior, unchanged).

alter table wardrobe_items
  add column isolated_photo_path text;

comment on column wardrobe_items.isolated_photo_path is
  'Storage object path of the background-removed image, when isolation succeeded. NULL falls back to photo_path.';
```

No `check` constraint on shape (unlike `photo_background_color`'s hex-format check) — this is a
Storage object path, same shape as `photo_path`, which itself has no format check either.

## 2. `schema.py` changes

### `BoundingBox` — new

```python
class BoundingBox(BaseModel):
    """A detection's region within the original photo, as fractions of its
    width/height (0-1) — resolution-independent, so the frontend applies it
    against the browser's own naturalWidth/naturalHeight (research.md §4).
    {0,0,1,1} means "the whole photo" — the fallback region for the
    single-draft cases (research.md §2)."""

    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    width: float = Field(gt=0, le=1)
    height: float = Field(gt=0, le=1)
```

### `ExtractedAttributes` — unchanged

No field added, removed, or renamed (FR-005). Reused as-is, one instance per detection.

### `DetectedGarment` — new

```python
class DetectedGarment(BaseModel):
    """One detection from vision.detect_garments_from_image — a region plus
    the same attribute set a single-item photo has always produced."""

    region: BoundingBox
    attributes: ExtractedAttributes
```

### `PhotoExtractionResponse` — extended

```python
class PhotoExtractionResponse(BaseModel):
    """What one detection's draft looks like — unchanged shape from before
    this feature (photo_path, extracted, extraction_ok), so a caller
    inspecting a single element of the new list sees exactly what it saw
    from the old single-object response (FR-004)."""

    photo_path: str
    extracted: ExtractedAttributes
    extraction_ok: bool
    region: BoundingBox
    isolated_photo_path: str | None = None
```

`PhotoExtractionView` (route-local, `closet.py`) is unchanged in kind — still
`PhotoExtractionResponse` plus `color_names`, now also carrying a route-computed
`isolated_photo_url: str | None` (signed, same TTL as `photo_url`, never stored) alongside it.

### `PhotoExtractionListResponse` — new

```python
class PhotoExtractionListResponse(BaseModel):
    """POST /closet/items/extract's actual response shape from this feature
    on: always a list, even when it holds exactly one draft (FR-001)."""

    drafts: list[PhotoExtractionView]
    truncated: bool  # FR-002 — more garments were detected than the 8-item cap kept
```

### `CreateWardrobeItemFromUploadRequest` — one field added

```python
class CreateWardrobeItemFromUploadRequest(BaseModel):
    photo_path: str
    isolated_photo_path: str | None = None   # NEW
    category: str
    colors: list[str] = Field(min_length=1)
    formality: Formality
    warmth: int = Field(ge=0, le=5)
    season: list[Season]
    fabric: str | None = None
    pattern: str | None = None
    fit: str | None = None
    name: str | None = None
    notes: str | None = None
    photo_background_color: str | None = None
```

(`formality`/`warmth`/`season` shown required per the existing 2026-08 revision recorded in the
field's own docstring — this feature does not reopen that decision.)

### `WardrobeItem` — one field added

```python
class WardrobeItem(BaseModel):
    ...
    photo_path: str | None = None
    isolated_photo_path: str | None = None   # NEW — mirrors photo_path exactly
    photo_background_color: str | None = None
    ...
```

### `ClosetItemView` (route-local, `closet.py`) — one computed field added

```python
class ClosetItemView(WardrobeItem):
    category_group: CategoryGroup
    color_names: list[str]
    photo_url: str | None = None
    isolated_photo_url: str | None = None   # NEW — signed at read time, same pattern as photo_url
```

## 3. `core/config.py` — new settings

```python
# --- Photo to items (feature 018) --------------------------------------------
wtw_max_detections_per_photo: int = 8            # FR-002
wtw_isolation_strategy: str = "segmentation"      # "segmentation" | "generative" | "hybrid" (FR-016)
wtw_isolation_timeout_seconds: float = 8.0        # per-detection, research.md §5
wtw_isolation_hybrid_min_area: float = 0.03       # research.md §6 — provisional, tuned from real data
wtw_isolation_hybrid_max_area: float = 0.92       # research.md §6 — provisional, tuned from real data
wtw_segmentation_api_url: str | None = None       # unset until a provider is chosen (research.md §5)
wtw_segmentation_api_key: str | None = None
wtw_generative_isolation_model: str | None = None # defaults to wtw_chat_model if unset, vision.py-style
```

All new AI-adjacent settings stay optional-until-used, matching `cohere_api_key`/`tavily_api_key`'s
existing pattern — `get_settings()` must not fail for a caller that never touches isolation.

## 4. `ports.py` — new Protocol

```python
@runtime_checkable
class IsolationClient(Protocol):
    """Structurally satisfied by each of adapters/isolation_segmentation.py,
    isolation_generative.py, isolation_hybrid.py — chosen by
    adapters.isolation.get_isolation_client() reading wtw_isolation_strategy,
    the same shape kb.py's wtw_kb_mode selection already establishes for a
    different Protocol."""

    def isolate(self, image_bytes: bytes, mime_type: str, region: BoundingBox) -> IsolationOutcome: ...


class IsolationOutcome(BaseModel):
    """Not part of ports.py itself (a plain return value, not a Protocol) —
    defined in schema.py beside the other AI-layer contracts."""

    image_bytes: bytes | None   # None on failure — caller falls back (FR-013)
    mime_type: str | None
    mask_area_fraction: float | None  # segmentation only; drives research.md §6's hybrid trigger
    cost_usd: float | None            # for eval/vision_harness.py's isolation_report() (research.md §9)
    latency_seconds: float
```

## 5. State / flow summary

```
upload → detect_garments_from_image() → 1..8 DetectedGarment
  ├─ call fails                  → 1 draft, extraction_ok=False, region={0,0,1,1}
  ├─ call succeeds, 0 detections → 1 draft, extraction_ok=True (all-null), region={0,0,1,1}
  └─ call succeeds, N detections → N drafts (N = min(len(raw), 8)), truncated = len(raw) > 8
       for each draft (concurrent):
         isolate(original_bytes, mime_type, region)
           ├─ succeeds → upload isolated image → draft.isolated_photo_path/_url set
           └─ fails/times out → draft.isolated_photo_path stays None (card still saveable, FR-013)
→ PhotoExtractionListResponse{ drafts, truncated }
```

Saving a draft (`POST /closet/items/from-upload`) is unchanged in shape — it already takes
`photo_path` plus corrected attributes; it now also accepts and persists
`isolated_photo_path` unmodified, exactly as it does `photo_background_color` today.
