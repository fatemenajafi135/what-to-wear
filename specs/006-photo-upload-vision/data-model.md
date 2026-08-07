# Data model: Photo upload + vision

No new database table. This feature's schema surface is: (1) a Storage bucket + its RLS
policies, declared in migration `0006`; (2) two Pydantic contract changes in `schema.py`; (3)
two new backend settings; (4) one route-local response field addition.

## 1. Storage: `wardrobe-photos` bucket

Declared in `infra/supabase/config.toml` (research.md §2):

```toml
[storage.buckets.wardrobe-photos]
public = false
file_size_limit = "10MiB"
allowed_mime_types = ["image/jpeg", "image/png", "image/webp"]
```

Object path convention (unchanged from the legacy adapter, research.md's storage adapter port):
`{user_id}/{uuid4}-{filename}`. The `user_id` prefix is what the RLS policy below matches on via
`storage.foldername(name)`.

## 2. Migration `0006` — Storage RLS

```sql
-- storage.objects RLS for the wardrobe-photos bucket (research.md §2). Unlike
-- wardrobe_items, this backend's own pooler connection never touches
-- storage.objects directly — every upload/sign call goes through Supabase
-- Storage's own HTTP API, authenticated with the caller's JWT, so this
-- policy is the real (not just documented-convention) isolation guarantee.
create policy "wardrobe_photos_owner_rw" on storage.objects
  for all
  using (
    bucket_id = 'wardrobe-photos'
    and (storage.foldername(name))[1] = auth.uid()::text
  )
  with check (
    bucket_id = 'wardrobe-photos'
    and (storage.foldername(name))[1] = auth.uid()::text
  );

-- Table-level GRANT, matching 0002's own precedent — required or the policy
-- above is unreachable ("permission denied for table objects") regardless of
-- what it says (handoff §5.1, trap 4).
grant select, insert, update, delete on storage.objects to authenticated;
```

Proven by `backend/tests/integration/test_storage_rls.py` (new): user A uploads an object under
their own prefix; user B's client, scoped to user B's own JWT, attempts to read and to overwrite
that exact object path and is refused both times — mirroring `test_wardrobe_rls.py`'s existing
two-user pattern for the `wardrobe_items` table.

## 3. `schema.py` changes

### `CreateWardrobeItemFromUploadRequest` — relaxed (research.md §4)

```python
class CreateWardrobeItemFromUploadRequest(BaseModel):
    photo_path: str
    category: str
    colors: list[str] = Field(min_length=1)
    formality: Formality | None = None
    warmth: int | None = Field(default=None, ge=0, le=5)
    season: list[Season] | None = None
    fabric: str | None = None
    pattern: str | None = None
    fit: str | None = None

    @field_validator("colors")
    @classmethod
    def _colors_must_be_hex(cls, v: list[str]) -> list[str]:
        return [normalize_hex(c) for c in v]
```

`photo_path`, `category`, `colors` stay required — they're the review-card fields with no safe
default (an item with no color or no category isn't meaningfully saveable). `formality`,
`warmth`, `season`, `fabric`, `pattern`, `fit` become optional; the route (not this model)
applies the three documented defaults from research.md §4 for `formality`/`warmth`/`season`
only, immediately before constructing the `WardrobeItem` to persist — `fabric`/`pattern`/`fit`
pass through as `None` when absent, matching the database's own nullability.

### Extract-route response — unchanged shape, existing types

`PhotoExtractionResponse`/`ExtractedAttributes` (both already exist, both already fully
optional per field) need no change — this feature is their first caller.

## 4. New settings (`core/config.py`)

```python
wtw_max_upload_bytes: int = 10_485_760          # research.md §3
wtw_photo_signed_url_ttl_seconds: int = 3600     # research.md §2
```

Both optional-with-default, consistent with every other numeric setting in this file
(`wtw_closet_page_size` precedent) — no `.env.example` entry is strictly required, but both are
added there (documented, blank-default-shown) for discoverability.

## 5. `ClosetItemView` gains `photo_url`

```python
class ClosetItemView(WardrobeItem):
    category_group: CategoryGroup
    color_names: list[str]
    photo_url: str | None = None   # NEW — signed URL, minted at read time, never stored
```

`None` when `photo_path` is `None` (no photo). Populated by the route (not the repository —
signing needs the caller's raw access token, which the repository layer has no access to and
shouldn't; matches `ports.ClosetRepository`'s unchanged signature) by calling the new
`adapters/storage.py:create_signed_url(access_token, photo_path)` once per item in the response.

## 6. New adapter: `adapters/storage.py`

Ported (not copied — see handoff §3.1) from `../app-legacy/backend/src/whattowear/storage.py`:

```python
def upload_photo(access_token: str, user_id: str, file_bytes: bytes, filename: str, content_type: str) -> str: ...
def create_signed_url(access_token: str, photo_path: str, expires_in: int | None = None) -> str: ...
```

Both read configuration via `get_settings()` inside the function body (never `os.environ` or
`load_dotenv()` at module scope — handoff §3.1, trap 2, `test_import_safety.py`), and both use
the caller's own bearer token, never a service-role key (trap 1).

## 7. Validation copy additions (frontend, `lib/`)

New field-level error key, alongside the existing `field.*` set (design-decisions §1.7):

| Key | Copy |
|---|---|
| `field.color.notRecognized` | I don't recognize that color. Try a name like navy, charcoal or olive. |

## 8. Key entities (from spec.md, grounded in the concrete shapes above)

- **Wardrobe item photo** = one `storage.objects` row in `wardrobe-photos`, path-scoped to its
  owner. Exists independently of any `wardrobe_items` row (the extract route uploads before any
  item is created).
- **Extracted attributes (draft)** = `PhotoExtractionResponse` (existing, unchanged) — never
  persisted directly; the review card's edits + this draft become a
  `CreateWardrobeItemFromUploadRequest` only on explicit save.
- **Review queue item** (frontend-only, no backend shape) = `{ file, photoPath, extracted,
  fields, status: 'pending' | 'saving' | 'saved' | 'error' }`, one per queued photo in
  `AddItemFlow`'s bulk branch.
