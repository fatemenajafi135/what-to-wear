# Research: Photo upload + vision

Every section below either resolves a technical unknown or records one of the handoff's named
gaps with its full alternative list (handoff §10: "the failure mode to guard against is not
weak reasoning — it is an incomplete option list"). Condensed versions of §§2–8 are mirrored
into `docs/design-decisions.md` starting at its own §23, each pointing back here for the full
argument — the same split feature 012 used for calendar token storage (design-decisions §16).

---

## 1. Raw bearer token access for Storage calls

**Problem**: `auth.py`'s only dependency, `get_current_user_id`, verifies the JWT and returns
just the `sub` claim. Storage uploads and signed-URL generation both need the *raw* token
(handoff trap 1: "never a service-role key for uploads — the caller's own bearer token,
always").

**Decision**: add a second, independent dependency, `get_current_access_token`, beside
`get_current_user_id` in `auth.py` — same verification, returns the raw token string instead
of the `sub` claim. Routes that need both (the two new photo routes; the closet read routes,
now that they mint signed URLs) declare both dependencies.

**Alternatives considered**:
- *Change `get_current_user_id`'s return type to a tuple/dataclass of `(user_id, token)`.*
  Rejected — every existing caller across 004/005/012/013 destructures a bare string; changing
  the shape is a breaking edit to four features' worth of call sites for a need only this
  feature has.
- *One combined `get_current_identity()` dependency returning both, used everywhere.* Considered
  — avoids the ~6 lines of duplicated JWT verification `get_current_access_token` otherwise
  repeats. Rejected because FastAPI's dependency cache means routes that only ever call
  `get_current_user_id` today would still pay the (harmless but pointless) cost of computing a
  token they never use, and it's a wider refactor than this feature needs to touch; the
  constitution's Quality Bar prefers this small, explicit duplication over a premature shared
  abstraction.

---

## 2. Storage bucket: private, with signed URLs — §23.1

**Problem** (handoff §5.1): decide and record private-bucket-plus-signed-URLs vs. a public
bucket, and what signed-URL expiry does to a cached closet grid.

**Decision**: **private bucket** (`wardrobe-photos`), declared in `infra/supabase/config.toml`
as `[storage.buckets.wardrobe-photos]` with `public = false`. The backend mints a **1-hour
signed URL** (`WTW_PHOTO_URL_TTL_SECONDS = 3600`, a new setting) at read time — inside
`GET /closet/items` and `GET /closet/items/{item_id}` — and returns it as a new `photo_url`
field on `ClosetItemView`, alongside the unsigned `photo_path` already on `WardrobeItem`.
Nothing signed is ever persisted; a stale cached URL just means the next closet fetch (already
the app's own re-fetch-on-navigate pattern, see `ClosetGrid.tsx`) hands back a fresh one. The
browser's own HTTP image cache holds the *image bytes* for as long as the response's cache
headers allow, independent of the URL's signature expiry, so a already-rendered tile does not
need to re-fetch merely because the signing token backing its URL has since expired.

**Why private wins**: these are photos of a specific person's clothes in their home — the same
category of private, per-user data `wardrobe_items` itself already is, protected by RLS and an
explicit `user_id` filter (004/005's established pattern). A public bucket would mean anyone who
learns or guesses an object path (`{user_id}/{uuid4}-{filename}` — a UUID makes *guessing* hard,
but a path can still leak via a referrer header, a screenshot, browser history, or a shared
link) can view that photo forever, with no way to revoke access short of deleting the object.
That directly undermines the same per-user isolation `storage.objects` RLS is about to enforce
on write; making it public on read would be inconsistent — protect the object on upload and
overwrite, but not on read.

**Storage RLS is the real enforcement here, not just the convention.** Unlike
`wardrobe_items`, where this backend's own pooler connection has `BYPASSRLS` and the actual
isolation is the repository's `WHERE user_id = ...` filter (RLS shipping only as
defense-in-depth for other access paths), photo uploads and signed-URL requests never go
through that pooled Postgres connection at all — they go through Supabase Storage's own HTTP
API, authenticated with the caller's JWT, which evaluates `storage.objects` RLS for real on
every call. This is why trap 1 ("never a service-role key") matters concretely here: a
service-role key would bypass the one RLS check in this feature that isn't just documentation.

**Alternatives considered**:
- *Public bucket.* Rejected for the reason above — private data with no revocation story.
- *Private bucket, no signed URLs — proxy every photo byte through the backend instead.* Would
  work and sidesteps signed-URL expiry entirely, but adds a new streaming-response code path to
  every route that renders a photo, for a problem signed URLs already solve natively in
  Supabase Storage; more code for no isolation benefit over signing.
- *Longer-lived signed URLs (e.g. 24h) to reduce re-signing frequency.* Rejected — the closet
  grid already re-fetches on every navigation to `/closet` (no client-side cache layer exists
  yet, per `known-gaps.md`'s offline section), so a longer TTL buys nothing except a wider
  window an intercepted URL stays valid; 1 hour is short enough to bound that exposure and long
  enough that a single page session never sees a URL expire mid-view.

**Addendum — batch signing, not one call per item (found in `/speckit-analyze`).** Minting a
signed URL per item on every `GET /closet/items` page (up to `wtw_closet_page_size`, 20 items)
via 20 sequential HTTP calls to Supabase Storage would add real, avoidable latency to the
screen the user sees most often. **Decision: use Supabase Storage's bulk-sign endpoint**
(`POST /storage/v1/object/sign/{bucket}`, accepting `{"paths": [...]}`, returning a
path→signed-URL map in one round trip) for `list_closet_items`; the single-item
`GET /closet/items/{id}` route keeps the single-path sign call, where batching has no benefit.
**Alternative considered**: parallelize N sequential calls with `asyncio`/a thread pool instead
of using the bulk endpoint. Rejected — Supabase Storage already exposes the batch operation
natively; reimplementing client-side concurrency to fan out N HTTP calls is strictly more code
for a worse result (still N round trips over the wire, just concurrent) than one request that
already returns all N URLs.

---

## 3. Maximum upload file size — §23.2

**Problem** (handoff §5.2): nothing in the design or schema states a limit; an unbounded
multipart body reaching a VLM is both a cost and a memory problem.

**Decision**: **10 MiB** (`WTW_MAX_UPLOAD_BYTES = 10_485_760`, a new setting), enforced in the
extract route before the file is read into memory or forwarded to Storage/the VLM, rejected
with `422`. `infra/supabase/config.toml`'s bucket also sets `file_size_limit = "10MiB"` as a
second, independent backstop at the Storage layer itself.

**Rationale**: a modern phone camera JPEG typically runs 2–8 MB; 10 MiB gives headroom above
that without inviting a pathological upload. It's also comfortably under `[storage]`'s existing
project-wide `file_size_limit = "50MiB"` in `config.toml`, so the bucket-level limit is the
binding one, not the reverse.

**Alternatives considered**:
- *5 MiB.* Rejected — tight enough to clip a legitimate high-resolution phone photo,
  particularly a portrait-orientation full-length garment shot.
- *No app-level limit, rely on the project-wide 50 MiB Storage default alone.* Rejected — 50 MiB
  is sized for the project in general, not this specific multipart-to-VLM path; letting a
  50 MiB file reach `vision.py`'s base64-encode-and-inline-in-a-chat-message step is a real
  memory and gateway-cost concern the handoff explicitly flags.

---

## 4. Review-card / required-attribute mismatch — §23.3

**Problem** (handoff §3.2): the design's six-field review card (Name, Category, Group, Fabric,
Color, Notes) doesn't cover the five attributes `CreateWardrobeItemFromUploadRequest` currently
requires non-null (Formality, Warmth, Season, Pattern, Fit) — a user cannot see or correct them,
and a total extraction failure would leave all five `null` against a schema that demands values.

**Investigated first**: what does the database actually require? `0002_wardrobe_and_catalog_
items.sql` has `formality`, `warmth`, `season` as `NOT NULL`; `fabric`, `pattern`, `fit` are
already nullable. `WardrobeItemPatch` (005's edit path) already treats all six as fully
optional. So the *database* only forces three of the five to have some value, not all five.

**Decision**: **relax the request contract**, matching `WardrobeItemPatch`'s existing
optionality. `CreateWardrobeItemFromUploadRequest` makes `formality`, `warmth`, `season`,
`fabric`, `pattern`, `fit` all optional. On save:
- `fabric`, `pattern`, `fit` — DB-nullable, so a missing value is simply stored `NULL`. `fabric`
  stays on the review card (still user-correctable); `pattern`/`fit` are saved as scanned (or
  `NULL`) and remain editable afterward through 005's existing edit form — never blocking save.
- `formality`, `warmth`, `season` — DB-`NOT NULL`, so a value the scan didn't find (or the user
  didn't provide) falls back to one documented, conservative default rather than blocking the
  save: `formality → "casual"` (the least assumption-laden point on the ordered scale),
  `warmth → 3` (the scale's midpoint, 0–5), `season → all four seasons` (the least-wrong
  assumption when season is genuinely unknown — "wearable year-round" rather than arbitrarily
  picking one). All three remain correctable via the existing edit form exactly like every other
  field.

Name/Category/Group/Fabric/Color/Notes are the six review-card fields; the five extra
attributes ride along unreviewed but never block a save, matching FR-005.

**Alternatives considered** (the three the handoff itself named, plus the one it didn't):
- *(a) Extend the review card beyond the design's six fields.* Rejected — a straight Principle
  VIII violation ("nothing visual is invented in code"); the design system enumerates exactly
  six fields for this card and doesn't leave room to add five more silently.
- *(b) Accept unreviewed attributes, but block save entirely when extraction fails completely
  (all eleven null).* Rejected — this is exactly the failure mode §3.2 warns about: it would
  make "extraction failure is a 200, never blocking" (§5.2, FR-002/FR-005) false in practice,
  forcing a full restart for a photo that uploaded successfully but scanned poorly.
- *(c, chosen) Relax the contract with documented conservative defaults for the three DB-bound
  fields, leave the DB-nullable three genuinely null.* Chosen because it's the only option that
  satisfies FR-005 without inventing UI and without violating `0002`'s existing `NOT NULL`
  constraints (which are Principle VI-adjacent — not part of the frozen taxonomy itself, but
  changing them would still be an unrelated, unjustified schema edit this feature has no reason
  to make).
- *(d, not named in the handoff, worth stating explicitly per its own instruction to look for
  the missing option) Migrate `formality`/`warmth`/`season` to nullable in `0006` instead of
  defaulting them.* Considered — would let a truly-unknown value stay honestly `NULL` instead of
  a guessed default. Rejected: every consumer of `WardrobeItem` downstream (the scoring
  functions in particular — `scoring/weather_fitness.py`, `scoring/formality_coherence.py`) is
  written against `formality: Formality` and `warmth: int` as non-optional Python types; making
  them `| None` ripples into every scorer's signature for a case (total extraction failure) the
  chosen defaults already handle acceptably, and does so without touching code outside this
  feature's own scope.

---

## 5. Color text field vs. stored hex — §23.4

**Problem** (handoff §3.3): the review card's Color field is free text; `wardrobe_items.colors`
is `text[]` of hex. `colors.py`'s own docstring argues hex is truth, names are derived only.

**Decision**: the Color field is **pre-filled with the derived name** of the scanned hex
(`colors.nearest_names`, already used elsewhere — e.g. `ItemEditForm.tsx`'s Colour field follows
the identical pattern today for the edit flow). On save, the (possibly user-edited) text is
matched **case-insensitively, trimmed, against `FASHION_COLOR_PALETTE`'s exact keys** — reusing
`colors.name_to_hex` unchanged. An unmatched value is rejected with `422` and new copy naming
the problem (`field.color.notRecognized` — data-model.md §"Validation copy"), not silently
approximated.

**Alternatives considered** (the three the handoff named):
- *(a, chosen) Exact match against the curated palette, reject what doesn't match.* Chosen: it's
  the one option that can't silently store the wrong color. `colors.py`'s own docstring already
  prescribes the remedy for a genuinely new color name — "extend `FASHION_COLOR_PALETTE`" — so
  routing an unrecognized name to a clear, correctable error is consistent with how the rest of
  the codebase already treats this exact situation (`name_to_hex` raises `KeyError` today; the
  route surfaces that as a 422 rather than swallowing it).
- *(b) Swatch-pick instead of a text field.* Rejected outright per the handoff — the design
  system states "Color (text)" explicitly; building a swatch picker would be inventing a
  different control than what's specified (Principle VIII).
- *(c) Accept text and match nearest (fuzzy string match, not color-space nearest — there's no
  "nearest" for a name typed against another name).* Rejected: a fuzzy string match that always
  succeeds can pick a *plausible-looking but wrong* palette entry with nothing telling the user
  a substitution happened — e.g. a typo or a genuinely absent color silently lands on whatever
  string is closest in edit distance, which could be visually unrelated. That risks storing a
  materially incorrect color as ground truth, which is a worse outcome than a clear, correctable
  rejection. `colors.nearest_names` (hex → name) already exists for the *display* direction and
  is reused for the pre-fill; there is no equivalent "nearest" operation defined for the reverse
  (name → hex) that doesn't have this failure mode.

---

## 6. Partial bulk-save failure — §23.5

**Problem** (handoff §5.4): what happens when one card in a queue of several fails to save.

**Decision**: **per-card isolation.** A failed save (a genuine request failure, not a client-side
validation problem, which is caught before the request is even sent) leaves that card's own
"Save & next" button in `Button`'s already-specified **Error** treatment (transparent
background, `--color-error` border+text, "Try again" label — design-system §3, no new component
needed). Cards saved before the failure are unaffected and stay saved. The queue does not
silently skip the failed card or auto-advance past it; the user retries in place (same button,
same handler) or abandons the whole overlay, in which case only the already-saved cards persist
(spec.md User Story 2, Acceptance Scenario 5).

**Alternatives considered**:
- *Abort/roll back the whole batch on any single failure.* Rejected — each card's save is
  already an independent `POST`, not a transaction spanning the queue; rolling back items that
  already succeeded would delete data the user correctly saved, to "fix" a problem with a
  different item entirely.
- *Skip the failed card silently and continue to the next.* Rejected — this is the literal
  failure mode FR-008 exists to prevent: the user would believe all N photos were processed and
  discover the gap only later, with no record of which item was lost.
- *A dedicated "Skip this item" affordance distinct from retry.* Considered — would let a user
  deliberately abandon one problem photo without abandoning the whole queue. Rejected for this
  slice: no such affordance is named anywhere in the design system or the handoff, and adding
  one is new UI Principle VIII doesn't currently license; closing the overlay already gives an
  equivalent (if coarser) escape hatch. Worth revisiting if bulk upload sees real use and this
  friction shows up in practice.

**Addendum — bulk photo count ceiling (found in `/speckit-analyze`).** spec.md's Assumptions
promise "a reasonable practical ceiling is assumed and enforced" for how many photos one bulk
session can queue, but no concrete number was ever picked. **Decision: 20 photos per bulk
session**, enforced client-side on the picker's selection (a selection beyond it is truncated to
the first 20 with a brief inline notice, not a hard rejection of the whole action). Chosen to
match `wtw_closet_page_size`'s existing 20 — already the project's precedent for "one screenful"
— and because a queue much longer than that turns a bounded review task into an open-ended one
with no save-progress mechanism beyond what's already saved. **Alternatives considered**: no
limit — rejected, an unbounded queue of full-resolution photos held in browser memory
simultaneously (each up to `wtw_max_upload_bytes`, 10 MiB) risks a real memory problem on a
phone, the primary capture device for this flow; a much smaller cap (e.g. 5) — rejected as overly
restrictive for someone cataloging a whole wardrobe in one sitting, the exact scenario bulk
upload exists for.

---

## 7. Camera permission primer — copy — §23.6

**Problem** (handoff §5.5): `known-gaps.md` requires a primer gated behind a persisted
`wtw_camera_primed` flag and names its own required action ("gated behind the primer's
**Continue** action") but no title/body copy exists anywhere, and `design/prototype/` has no
working primer to read intent from (confirmed — no camera-primer markup exists there, matching
what design-decisions §18 already found true for the calendar primer).

**Decision**: follow §18's established shape exactly (own bespoke `<dialog>`-based card, not
`BottomSheet`, per the same escape hatch), first-person stylist voice:

| Element | Copy |
|---|---|
| Title | Before you scan |
| Body | I'll use your camera to scan the garment so I can fill in its details automatically. Nothing is saved until you review and confirm. |
| Primary action | Continue |
| Secondary action | Not now |

"Continue" (not a more specific label) because `known-gaps.md` itself names the action
generically ("the primer's Continue action") rather than naming a specific destination the way
the calendar primer's "Continue to Google" names its OAuth handoff — there's no equivalent
named external destination for a native file/camera input to reference. "Nothing is saved until
you review and confirm" directly reassures against the one real anxiety a camera permission
prompt raises (what happens to the photo), mirroring the calendar primer's own reassurance
pattern ("You can disconnect anytime from Settings").

**Alternatives considered**:
- *Reuse "Continue to Google"'s exact structure with a swapped noun ("Continue to Camera").*
  Rejected — there's no separate consent screen being navigated to the way Google's OAuth
  screen is; the primer gates a same-page `<input type="file" capture="environment">`, not an
  external redirect, so implying a hop to another destination would misdescribe what happens
  next.
- *Neutral/system voice ("This app would like to access your camera").* Rejected on the same
  grounds §18 rejected it for calendar — breaks voice consistency with every other first-person
  string in the Add-item flow the user is mid-way through (`add_item.upload.placeholder`,
  `add_item.empty.body`), for no stated exception in §9's copy conventions (system voice is
  reserved for connection/sync *status*, not a user-initiated action's own explanation).

**Addendum — what "Not now" actually does (found in `/speckit-analyze`, closes spec.md
SC-006).** Unlike the calendar primer (where declining just returns to a screen with nothing
lost — there's always a "Connect" action to try again), declining the camera primer must not
strand the user mid-upload with no way to pick a photo at all. **Decision: accepting sets
`wtw_camera_primed` and opens the file input *with* `capture="environment"` (jumps straight to
the camera app on a device that supports it); declining closes the primer *without* setting the
flag and opens the identical file input *without* the `capture` attribute** — the browser's
normal file/photo picker, which on most platforms still offers "take photo" as one option among
several, just not as the forced default. The primer therefore only gates the camera-jump
shortcut, never file access itself, and reappears on the next upload attempt since declining
doesn't persist a "primed" state — consistent with the flag's own name (*camera*-primed, not
*upload*-primed). **Alternative considered**: declining disables the whole Dropzone for that
session. Rejected outright — it directly contradicts SC-006's explicit requirement and would
make declining the primer indistinguishable from being offline.

---

## 8. Review progress bar animation, and "Enter manually" — §23.7/§23.8

Both are `design-system.md`'s own **Open Questions** list, not the handoff's six, but the
handoff explicitly folds them into this feature's scope (§10).

**§23.7 — animates.** The bar transitions with `--motion-duration-base` /
`--motion-easing-standard` (the same pairing `BottomSheet`'s recommended open/close motion
already establishes, § BottomSheet & toast motion), gated by `prefers-reduced-motion` per §8's
accessibility requirement (falls back to an instant jump when reduced motion is requested).
**Alternative rejected**: an unconditional instant jump — no stated reason favors it, and it
would need its own reduced-motion carve-out anyway since there'd be nothing to gate.

**§23.8 — same review form, blank.** "Enter manually" (offered from the "no garment found"
empty state) advances to the identical six-field review card component already built for the
scanned case, with every field starting empty and the same uploaded photo still attached (the
photo genuinely uploaded even though nothing was detected in it — §5.2). **Alternatives
considered**: a second, purpose-built manual-entry form — rejected, directly contradicts
"every form control already exists... do not build new ones" (handoff §5.3) for no benefit the
existing card doesn't already provide blank.

---

## 9. Vision harness fixture images — §5.6

**Problem**: `evals/golden_set.yaml`'s two `vision_cases` reference
`fixtures/vision_samples/navy_top_placeholder.png` and `beige_trousers_placeholder.png`, neither
of which exists, in either codebase.

**Decision, with an honest limitation**: this sandbox has no camera and no vetted way to source
rights-cleared real garment photographs from the internet. Two small PNG fixtures are generated
programmatically (simple flat-color silhouettes — a navy top shape, a beige trousers shape) and
committed at exactly the two paths the golden set already names, so
`uv run python -m whattowear.eval.vision_harness` has real files to load and stops failing on a
missing-file error. **This closes the "file doesn't exist" gap, not the "is this a
representative garment photo" gap** — a synthetic silhouette is not a real photograph, and a
VLM's extraction quality against it is not evidence of extraction quality against a real photo.
The harness itself also cannot be run to completion in this environment regardless of the fixture
images existing, since no live VLM gateway key is configured here (§12 below) — reported
explicitly rather than left silently unverified.

**Alternatives considered**:
- *Leave the fixture files absent, matching 007's status quo.* Rejected — the handoff assigns
  sourcing them to this slice specifically ("you are the slice that produces real garment
  photos... it is yours"), and leaving the golden set unrunnable a second time is exactly the
  outcome the handoff calls out as the thing to not repeat.
- *Source real photos from the web via a fetch tool.* Rejected — no image-sourcing tool with
  clear licensing/rights information is available in this environment, and guessing at usage
  rights for an internet image is the wrong failure mode to risk in a committed fixture.

---

## 10. Multipart request bodies and `openapi-typescript`

**Problem** (handoff §5.2 warning): "Multipart request bodies do not round-trip usefully through
`openapi-typescript`."

**Finding**: `openapi-typescript` renders a `multipart/form-data` request body as
`{ [key: string]: unknown }` or an unhelpfully loose type rather than a typed shape mirroring
the FastAPI `File(...)`/`Form(...)` parameters — because OpenAPI's own multipart schema
representation is itself loose, this is a real upstream limitation, not a generator bug.

**Decision**: the extract route's frontend call site builds a raw `FormData` and calls
`apiClient.POST("/api/v1/closet/items/extract", { body: formData })` — `openapi-fetch` accepts
`FormData` directly and skips its usual JSON-stringify step when the body is already a
`FormData` instance (checked in `openapi-fetch`'s source: it special-cases `FormData`/`Blob`/
`ArrayBuffer` bodies). The response side (`PhotoExtractionResponse`) is a normal JSON shape and
types correctly with no special handling. No hand-maintained duplicate request type is
introduced — the *response* type still comes from the generated schema (Principle VII); only
the opaque multipart *request* body sidesteps typing, which is the documented, upstream-caused
exception, not a hand-rolled contract.

---

## 11. No-photo treatment for pre-existing items

**Problem** (handoff §5.5, spec.md Edge Cases): an item seeded before this feature shipped has
`photo_path IS NULL`. The removed diagonal-stripe placeholder must not be repurposed as its
stand-in.

**Decision**: a plain, static `--color-surface-sunken` fill (no pattern, no debug label, no
animation) with a centered Lucide icon appropriate to the surface (a generic "image" glyph),
`aria-hidden="true"` exactly like the current placeholder block already is (it conveys no
information a screen reader needs beyond the item's own name, already announced by the
surrounding link/heading). This reads as "no photo" rather than "loading" or "photo failed to
load" (which the design system's real loading skeleton and a distinct future error state would
otherwise need to be distinguished from), and needs no new token — it's the same
`--color-surface-sunken` fill already used for input/skeleton wells.

**Alternatives considered**:
- *Keep the diagonal-stripe pattern specifically for the true-no-photo case (not as a loading
  state, just as the empty-photo state).* Rejected — `design-system.md`'s Image treatment
  section is explicit and unconditional: "once real photos replace the placeholder, this
  striped pattern... should be deleted outright, not preserved as a loading state" — it doesn't
  carve out a no-photo exception, and repurposing removed scaffolding for a new meaning invites
  exactly the confusion the instruction is trying to avoid.
- *Render nothing (collapse the photo area entirely) when there's no photo.* Rejected — it
  would change the tile/hero's layout dimensions conditionally, which both the grid (fixed
  120px tiles) and the item-detail hero (fixed 220px block, 40%-width at tablet+) depend on
  staying constant regardless of content.

---

## 12. Environment limitations encountered while building this slice

Recorded here rather than silently worked around, per the handoff's "if you cannot complete
something" instruction:

- **No live VLM gateway key.** The repo owner was asked and explicitly chose to proceed without
  one for this session. Every extraction call site is built and unit-tested against the mocked
  seam (`vision._image_content_block`, matching `test_vision.py`'s existing pattern) — no test
  anywhere makes a live call (constitution Quality Bar, trap 3). The one live-call check §9 of
  the handoff's definition of done asks for is reported as explicitly skipped, not faked.
- **No local Supabase in this sandbox.** `npx supabase start` requires pulling several Docker
  images; every pull in this environment fails with `403 Forbidden` from the registry CDN
  (CloudFront/GHCR), which the agent-proxy documentation for this environment identifies as an
  egress-policy denial not to be retried or routed around. This means `npx supabase db reset`,
  the live two-user Storage-isolation test, and any integration test that needs a running
  database (`test_closet_routes.py`'s own docstring already documents this class of test as
  requiring a live local stack) cannot be executed here. Migration `0006` and every new
  integration test are written to the same standard the existing ones already meet and are
  ready to run wherever Docker egress is available (a normal dev machine or CI); they are not
  fabricated as passing.
