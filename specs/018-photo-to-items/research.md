# Phase 0 Research: Photo to items

The spec already resolved the constraints the brief called out as spec-level (detection cap,
isolation blocking-vs-after-save, hosted-vs-in-process). This file resolves the *technical*
unknowns those decisions leave open — how detection and extraction are actually called, how
isolation is actually wired, and what the migration/contract changes concretely look like.

## 1. One VLM call does detection AND extraction, not two

**Decision**: `vision.py`'s single VLM call is extended to return an array of detections in one
structured-output response, each carrying a normalized bounding region plus the same nine
attribute fields `ExtractedAttributes` already has. There is no separate "detection" call
followed by up to 8 "extraction" calls.

**Rationale**: a detect-then-extract split would multiply VLM calls by up to 9× per photo (1
detection + up to 8 extraction), blowing both the $0.05 cost ceiling (SC-008) and the 30s p50
latency budget (SC-007) for no accuracy benefit — a vision model asked to enumerate and describe
several garments in one pass is doing exactly the task #46's rewritten prompt targets. This also
matches the brief's own framing: "one prompt file" drives detection and extraction together,
not two prompts.

**Alternatives considered**: (a) chosen. (b) Detect via one call, extract each region via a
second cropped-image call per detection — rejected on cost/latency above. (c) Client-side
detection (a lightweight object-detection model in the browser) — rejected: adds a frontend ML
dependency for a task the vision model already has to do anyway to produce good attributes, and
duplicates the "confidence ranking for the cap" logic in two places.

**Schema shape**: `_EXTRACTION_SCHEMA` (vision.py) becomes the item schema inside a `detections`
array, each entry gaining `region: {x, y, width, height}` (floats, 0–1, fraction of the original
photo — resolution-independent, so the frontend can apply it to the browser's own `naturalWidth`/
`naturalHeight` without the backend needing to know the display size). The model is prompted to
order detections by confidence/prominence; Python enforces the cap by truncating to the first 8
rather than trusting the model to self-limit (`len(raw) > 8` sets `truncated: true`).

## 2. Two failure/empty paths collapse onto one existing pattern, not a new one

**Decision**: the route's existing `try/except Exception` around the VLM call is unchanged in
shape. A genuine call failure still produces the existing `extraction_ok=False`, all-null
result — now wrapped as the single element of a one-item `drafts` list, `region` set to the full
frame (`{0,0,1,1}`). A call that *succeeds* but returns zero detections (the model found nothing
confidently) also produces a single-element list, but with `extraction_ok=True` and null
attributes — matching today's existing "call succeeded, nothing found" semantics exactly (the
prompt already tolerates this per-field; it now needs to tolerate it at the list level too: an
empty `detections` array is a valid, successful response, not a schema violation).

**Rationale**: FR-003 asks for "today's single-draft behavior" on both paths, and today's route
already draws exactly this line (exception vs. successful-but-empty) — reusing it rather than
inventing a third state keeps the failure taxonomy the same size it already is.

## 3. Detection cap enforced in Python, not the schema

**Decision**: the JSON schema sent to the gateway does not set `maxItems` on the `detections`
array (research.md §1's `_EXTRACTION_SCHEMA`-derived schema shape is hand-written already, per
`vision.py`'s existing docstring on why — an all-nullable-required object shape — and gateway
support for array-level `maxItems` alongside that shape is unverified). `WTW_MAX_DETECTIONS_PER_
PHOTO` (default 8, `core/config.py`) is applied in Python after the call returns.

**Rationale**: enforcing the cap in code, not the schema, means a gateway or prompt change that
returns 9 detections degrades to "keep the top 8, flag `truncated`" rather than a schema-validation
exception that would turn an over-detected photo into a hard failure — exactly the graceful
degradation FR-002 asks for.

## 4. Region-cropped preview needs no extra Storage write

**Decision**: before isolation completes (or if it fails), a review card's "that garment's own
region of the original photo" (FR-013/FR-019) is rendered **client-side**, by cropping the
browser's own local blob URL of the uploaded file against the `region` fraction the backend
returned — not a second server-side crop uploaded as its own Storage object.

**Rationale**: the original file is already in the browser's memory the instant it's selected
(`AddItemFlow`/`BulkQueue` already do `URL.createObjectURL(file)` today); a region is four
floats, cheap to ship in the JSON response already being returned. A server-side per-detection
crop object would mean up to 8 extra Storage writes per photo for an image nobody may ever save
— pure waste against the same cost/latency budget research.md §1 already protects. This also
means `wardrobe_items` needs exactly one new image-pointer column (FR-018's "one column"), not
one per pipeline stage.

**Mechanism**: `OrientationAwarePhoto` gains an optional `region` prop; when present (and no
`isolatedSrc` is available yet), it renders the full blob at a scale/position computed from
`region`'s fractions inside an `overflow: hidden` frame — the same orientation-driven
letterbox-vs-natural choice it already makes governs the *frame*, cropping is a transform on top
of it, not a replacement for it (FR-022 — no separate treatment for cut-outs, and none is
introduced for the pre-isolation crop either).

## 5. Isolation is a hosted HTTP call per strategy, timeout-bounded, run concurrently across detections

**Decision**: `IsolationClient` (new `ports.py` Protocol) is satisfied by three adapters, each a
plain `requests`-based HTTP call (same idiom as `adapters/storage.py`, no SDK):

- `adapters/isolation_segmentation.py` — calls a hosted background-removal endpoint
  (`WTW_SEGMENTATION_API_URL`/`WTW_SEGMENTATION_API_KEY`, unset-until-configured, mirroring
  `cohere_api_key`/`tavily_api_key`'s existing optional-until-used pattern in `core/config.py`).
  Returns the cutout image bytes plus the mask's area as a fraction of the frame (needed by §6).
- `adapters/isolation_generative.py` — routes through the **existing** `adapters/llm_gateway.py`
  factory (no new client), calling an image-generation-capable model
  (`WTW_GENERATIVE_ISOLATION_MODEL`, defaulting alongside `wtw_vision_model`'s existing pattern)
  with the detection's region as an inpaint/reference input, producing a clean product-style
  image of just that garment.
- `adapters/isolation_hybrid.py` — calls the segmentation adapter first; escalates to the
  generative adapter only when §6's trigger fires. Composes the other two adapters directly
  (plain function composition — no third HTTP call of its own).

Each call is wrapped in `WTW_ISOLATION_TIMEOUT_SECONDS` (default 8.0) — a timeout is treated
identically to any other isolation failure (FR-013's fallback), not surfaced differently.
Isolation calls for the detections in one photo are dispatched concurrently (`concurrent.futures.
ThreadPoolExecutor`, matching the route's existing synchronous style — `extract_closet_item` is a
plain `def`, already run in FastAPI's threadpool, so this is in keeping with the file's own
idiom rather than introducing `async def` for one route) so 8 detections' isolation calls cost
roughly one call's wall-clock time, not eight, protecting SC-007's 30s p50 budget.

**Rationale**: FR-015 (hosted, not in-process) plus SC-008's cost ceiling rule out anything that
installs `rembg`/`onnxruntime`/model weights into the backend image (§56/§57). Reusing the
existing gateway for the generative strategy avoids a second LLM client entirely; the
segmentation strategy needs its own hosted endpoint because background removal isn't a
chat-completion shape the gateway's existing factory produces.

**Open item, not blocking implementation**: `WTW_SEGMENTATION_API_URL`/`_API_KEY` need a real
hosted background-removal provider selected and an account provisioned before this reaches a
live environment — the adapter is written against a generic "send an image, get a cutout"
contract so any provider fits, matching how `cohere_api_key`/`tavily_api_key` are already unset
in every environment until someone configures them. CI never calls it live (Quality Bar); unit
tests mock the HTTP call.

## 6. Hybrid trigger: a measurable property, not a vibe (FR-012)

**Decision**: the hybrid adapter escalates to generative reconstruction when the segmentation
call's own reported mask-area fraction is below `WTW_ISOLATION_HYBRID_MIN_AREA` (default `0.03`
— essentially nothing was isolated) or above `WTW_ISOLATION_HYBRID_MAX_AREA` (default `0.92` —
essentially the whole frame was kept, meaning nothing was actually removed), or when the
segmentation call itself fails or times out.

**Rationale**: both bounds describe segmentation degenerating into "found nothing" or "found
everything," the two shapes a failed cutout actually takes, without requiring any perceptual
image-quality judgment. **These two numbers are explicitly provisional** — spec.md's Assumptions
already flag this: the real values are set from `eval/vision_harness.py`'s per-strategy report
(§9) against the expanded fixture corpus during implementation, not asserted here. The trigger's
*shape* (a measurable property of the segmentation output) is what FR-012 fixes permanently; the
thresholds are a config default, changeable without a code change.

## 7. Storage: same bucket, same RLS, one new column

**Decision**: the isolated image uploads to the existing `wardrobe-photos` bucket at
`{user_id}/{uuid4}-isolated-{filename}` via `adapters/storage.py::upload_photo` (already
generic — no change needed to that function). `infra/supabase/migrations/0006_wardrobe_photos.
sql`'s RLS policy matches on `(storage.foldername(name))[1] = auth.uid()::text` — the *first*
path segment — so it already covers this object with zero policy change. One migration
(`0013_isolated_photo.sql`) adds `wardrobe_items.isolated_photo_path text`, nullable, no check
constraint beyond format (same shape as `0006`/`0008`'s precedent). Not a Constitution VI change
(spec.md says so explicitly; this plan doesn't re-litigate it).

## 8. Frontend: `ItemPhoto` needs no code change; call sites decide what to pass it

**Decision**: `components/ui/ItemPhoto/ItemPhoto.tsx` already does exactly what FR-021 wants —
`object-fit: contain` at 1:1, letterboxed in a passed `backgroundColor`, falling back to
`--color-surface-sunken` when none is given. For an isolated image, `ClosetGrid` and
`ItemDetailCard` pass `src={item.isolated_photo_url ?? item.photo_url}` and
`backgroundColor={item.isolated_photo_url ? null : item.photo_background_color}` — no
`backgroundColor` for an isolated image means the existing neutral-surface fallback applies,
which is precisely "the app's standard neutral surface treatment" FR-021 asks for. Zero lines of
`ItemPhoto.tsx` itself change.

The item-detail original/isolated toggle (FR-020) is new: `ItemDetailToggle.tsx`, rendered only
when `item.isolated_photo_url` is present, flips which `src`/`backgroundColor` pair
`ItemDetailCard` passes to `ItemPhoto`. No design-system token exists yet for a toggle of this
specific kind — built from the app's existing segmented-control/tab primitive if one exists in
`components/ui/`, else a minimal two-button group using existing `Button` states, clearly scoped
as a UI gap in tasks.md rather than inventing a new visual language for it (Principle VIII).

**Rationale**: keeping the decision entirely in what each call site passes — rather than
teaching `ItemPhoto` a new "isolated" concept — means the one shared component both surfaces
already use stays exactly as simple as it is today, and the two surfaces stay free to diverge
(only the detail page gets a toggle) without forking the component.

## 9. Measurement: one harness, two report modes

**Decision**: `eval/vision_harness.py` gains:
- Extended `_check()`: loads `expected_count` (new, optional, per `vision_cases:` entry) and
  compares `len(detections)`, plus the existing per-field loose checks now applied per detection
  rather than to a single result — still LOOSE, still structurally separate from `harness.py`.
- A new `isolation_report()` function: for each configured strategy, runs every fixture-corpus
  image through `get_isolation_client(strategy)`, records wall-clock latency, success/failure,
  and reported cost (each adapter returns its own call's cost, matching how `LangSmith` already
  tracks token cost elsewhere — constitution Technology Constraints), and prints a per-strategy
  summary table. This is what produces the real numbers research.md §6's provisional thresholds
  and the plan's "segmentation is fastest/cheapest" assumption (FR-016) get checked against.

**Rationale**: "one corpus, three claims" (the brief's own phrase) — accuracy (#46),
per-strategy isolation comparison (#48), and the detection-count check (#45) all read the same
`evals/fixtures/vision_samples/` directory and the same `vision_cases:` entries, so there is one
place the corpus can go stale rather than three.

## 10. Frontend queue: drafts, not files

**Decision**: `BulkQueue`'s `QueueEntry` becomes one-per-draft, not one-per-file. Scanning photo
*i* still happens once (one `POST /closet/items/extract` call), but its response's `drafts` array
is flattened into N queue entries sharing the same underlying `photoUrl` blob and `photoPath`, each
carrying its own `region`/`isolatedPhotoUrl`/`extracted`/`extraction_ok`. `AddItemFlow`'s
single-photo path does the same flattening for its one photo, so a single-photo upload that
happens to detect several garments reviews exactly like a small bulk batch (FR-025) rather than
needing a second review UI.

**Rationale**: this is what makes "keyed to detections, not files" (FR-023) and "X of Y counts
detections" (FR-024) true without duplicating BulkQueue's state machine for a second axis (photo
index *and* detection index) — flattening to one axis before the state machine sees it keeps
`currentIndex`/`advance()`/`handleSave()` exactly as simple as they are today.
