# Implementation Plan: Photo to items

**Branch**: `feat/018-photo-to-items` | **Date**: 2026-08-10 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/018-photo-to-items/spec.md`

## Summary

`POST /closet/items/extract` moves from one VLM call describing the whole photo to one VLM call
that detects *and* describes every garment in it (up to 8), in a single structured-output
response — not a detection call followed by N extraction calls, which would multiply cost and
latency by the same factor this feature is trying to bound. The route then runs isolation
(configurable strategy: segmentation, generative reconstruction, or a hybrid of the two) against
each detection synchronously, before the response is returned, so every review card the frontend
renders already carries its clean image. `wardrobe_items` gains one nullable column
(`isolated_photo_path`) via an additive migration; the existing per-`{user_id}` Storage RLS policy
already covers the new object without a policy change (it matches on path prefix, not filename).
`prompts/vision_system.md` is rewritten (v2 → v3) for multi-garment detection and the accuracy
failures issue #46 names; every claim about it is settled by `eval/vision_harness.py` against an
expanded, real fixture corpus, which also produces the per-strategy isolation comparison research.md
§9 commits to measuring rather than assuming.

## Technical Context

**Language/Version**: Python 3.12 (backend, `uv`), TypeScript / Next.js App Router (frontend) —
unchanged, no new language.

**Primary Dependencies**: `langchain_litellm`/`adapters.llm_gateway` (existing, reused for both the
detection+extraction call and the generative-reconstruction isolation strategy — no new LLM
client); `requests` (existing, reused for the segmentation strategy's hosted HTTP call, same
pattern `adapters/storage.py` already uses — no new HTTP client library, no SDK).

**Storage**: Postgres via Supabase (`wardrobe_items` gains one nullable column,
`isolated_photo_path`, by migration) + Supabase Storage, same `wardrobe-photos` bucket feature 006
already provisioned — the isolated image is a second object under the same `{user_id}/` prefix,
which `wardrobe_photos_owner_rw`'s existing RLS policy (`infra/supabase/migrations/0006_wardrobe_
photos.sql`) already matches on path prefix alone. No new bucket, no new Storage policy.

**Testing**: `pytest` (backend, unit + integration — every VLM/isolation call mocked, matching
`test_vision.py`'s existing pattern; CI makes no live calls per the Quality Bar) + the existing,
now-extended `eval/vision_harness.py` (loose checks, live-gateway only, excluded from CI, same as
today) + frontend component tests (existing `*.test.tsx` convention, `BulkQueue`/`AddItemFlow`/
`ReviewCard`/`OrientationAwarePhoto`/`ItemPhoto` all get updated cases).

**Target Platform**: unchanged — Railway (backend), Vercel (frontend). Isolation strategies are
explicitly **hosted calls, not in-process models** (FR-015) specifically so this feature adds zero
new heavyweight runtime dependencies to the backend image — §56/§57's already-recorded image-size
and cold-start findings are the reason, not a new concern this plan discovers.

**Project Type**: web application (existing `frontend/` + `backend/` split, unchanged).

**Performance Goals**: SC-007 — a photo with the maximum 8 detections completes detection,
extraction and isolation for all of them within 30s at p50. Isolation calls for the detections in
one photo run concurrently (research.md §6), not sequentially, to hold this budget with margin to
spare even when the hybrid strategy occasionally escalates one or two detections to the slower
generative path.

**Constraints**: SC-008's $0.05-per-photo cost ceiling at the default configuration; FR-002's
8-detection cap; FR-014's per-detection isolation timeout (research.md §5: 8s); no pipeline/
scoring/retrieval change (Principle I — this feature touches `vision.py` and its prompt, both
already outside `pipeline/`); no inline prompt strings (Technology Constraints); every eval row
records prompt version and model (FR-009).

**Scale/Scope**: one route's response shape extended (not a new route), one prompt rewritten
(v2 → v3), one new port (`IsolationClient`) with three adapters, one migration, one eval-harness
extension, frontend changes confined to the existing Add-item surface (`AddItemFlow`, `BulkQueue`,
`ReviewCard`, `OrientationAwarePhoto`) plus the two read surfaces that render a saved item's photo
(`ClosetGrid`, `ItemDetailCard` — both already share one component, `ItemPhoto`, which needs no
change beyond what each call site passes it, per research.md §8).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [x] **I — Salvaged AI code is authoritative.** No `pipeline/`, `retrieval/`, `scoring/`,
      `memory/`, `ingest/`, or `eval/harness.py` file is touched. `vision.py` (already outside
      the salvaged pipeline, feature 006's own module) is extended, not regenerated, and its one
      existing eval file (`eval/vision_harness.py`) is extended in place, per the brief's own
      instruction that it stay structurally separate from `harness.py`'s no-regression gate.
- [x] **II — Deterministic scoring.** Unaffected — no outfit scoring code touched. Detection,
      extraction, and isolation are all metadata/image-derivation steps over a photo the user is
      actively adding, not outfit item selection; nothing here is on the suggest/recommend path
      Principle II governs.
- [x] **III — Style gates wardrobe.** N/A — this feature has no retrieval call of any kind.
- [x] **IV — Grounded output.** N/A in the sense this principle means it (outfit citations) — but
      the feature's own analogous guarantee holds: every surfaced item photo, isolated or not, is
      still provably the user's own upload (FR-017/FR-019), and a failed isolation is never
      disguised as a success (FR-013).
- [x] **V — Scorers are eval metrics.** N/A — no new outfit-quality judgment is introduced.
      Extraction accuracy and isolation quality are judged by `eval/vision_harness.py`'s loose
      checks, which is the eval file this principle would point at if this *were* a scorer — but
      it isn't one; extraction correctness is a data-quality measure, not a styling judgment.
- [x] **VI — Schema stability.** FR-005 and spec.md's Assumptions state this explicitly: no
      attribute is added, removed, or changed. `isolated_photo_path` is a new column pointing at
      an image, not a taxonomy field — same class of change as `photo_path`/`photo_background_
      color` before it (features 006 and its follow-up), neither of which triggered VI either.
- [x] **VII — Contracts.** `frontend/lib/api/schema.d.ts` is regenerated from the backend's
      OpenAPI output after the extract route's response shape and the two new fields on
      `ClosetItemView`/`CreateWardrobeItemFromUploadRequest` land; no hand-maintained duplicate
      type (data-model.md).
- [x] **VIII — Visual truth.** Every value this feature's frontend work touches already exists in
      `design-system.md`/`docs/design-decisions.md`: `ItemPhoto`'s neutral-surface fallback
      (`--color-surface-sunken`) is the exact token FR-021 reuses for a removed background, no new
      value invented. The one genuinely new UI surface — the item-detail original/isolated toggle
      (FR-020) — has no design-system entry yet; handled the same way feature 016 handled missing
      copy (Principle VIII's own instruction): built with the app's existing toggle/segmented-
      control primitive if one exists, status reported explicitly rather than a value invented,
      not shipped as though it were signed off (research.md §8). Loading/empty/error/offline:
      the review card's scanning/ready/upload-error states are unchanged in kind, only in count
      (N cards instead of 1); the new "some garments weren't captured" notice and the detail-page
      toggle both need states of their own, scoped in tasks.md.
- [x] **IX — One codebase.** No new route, no new screen, no platform branching — this extends
      the existing Add-item surface and the existing Closet/Item-detail surfaces, identical at
      every form factor already.
- [x] **X — Documents are data.** The fixture corpus growing from 2 to 10+ images stays under the
      already-tracked `evals/fixtures/vision_samples/` carve-out (constitution's explicit list of
      exceptions already names it) — no `infra/corpus.yaml` entry needed, this isn't the RAG
      corpus.

No unresolved gate. Complexity Tracking is not needed — the three isolation adapters satisfy the
Quality Bar's own two-implementations-or-a-measured-problem test for introducing a port (`ports.py`
already sets this precedent for exactly this reason), so `IsolationClient` is not a speculative
abstraction.

## Project Structure

### Documentation (this feature)

```text
specs/018-photo-to-items/
├── plan.md              # this file
├── research.md          # Phase 0 — done
├── data-model.md         # Phase 1 — done
├── quickstart.md        # Phase 1 — done
├── contracts/
│   ├── closet-items-extract.md          # supersedes 006's version (response shape only)
│   └── closet-items-from-upload.md      # supersedes 006's version (two new fields)
└── tasks.md             # Phase 2 (/speckit-tasks) — not yet generated
```

### Source Code (repository root)

```text
backend/
├── infra/supabase/migrations/
│   └── 0013_isolated_photo.sql                # NEW — wardrobe_items.isolated_photo_path
├── src/whattowear/
│   ├── ports.py                                # CHANGED — add IsolationClient Protocol
│   ├── adapters/
│   │   ├── isolation_segmentation.py           # NEW — hosted background-removal call
│   │   ├── isolation_generative.py             # NEW — hosted generative-reconstruction call
│   │   ├── isolation_hybrid.py                 # NEW — composes the two above (FR-011/FR-012)
│   │   ├── isolation.py                        # NEW — get_isolation_client() factory, config-selected
│   │   └── llm_gateway.py                      # CHANGED — get_image_model() factory, mirrors
│   │                                             #   get_chat_model(), for the generative strategy
│   │                                             #   (found missing here in /speckit-analyze)
│   ├── vision.py                                # CHANGED — detect_garments_from_image() replaces
│   │                                             #   extract_attributes_from_image(); returns
│   │                                             #   list[DetectedGarment]; one VLM call, not N+1
│   ├── schema.py                                # CHANGED — BoundingBox, DetectedGarment,
│   │                                             #   PhotoExtractionListResponse; WardrobeItem +
│   │                                             #   CreateWardrobeItemFromUploadRequest gain
│   │                                             #   isolated_photo_path
│   ├── core/config.py                           # CHANGED — wtw_isolation_strategy,
│   │                                             #   wtw_isolation_timeout_seconds,
│   │                                             #   wtw_max_detections_per_photo,
│   │                                             #   hybrid threshold + segmentation/generative
│   │                                             #   endpoint settings
│   ├── prompts/
│   │   └── vision_system.md                     # CHANGED — v2 → v3, multi-garment (#46)
│   ├── api/v1/routes/closet.py                  # CHANGED — extract route returns
│   │                                             #   PhotoExtractionListResponse; from-upload
│   │                                             #   accepts + persists isolated_photo_path;
│   │                                             #   ClosetItemView signs isolated_photo_url
│   ├── repositories/supabase_closet.py          # CHANGED — create_wardrobe_item_from_upload
│   │                                             #   inserts isolated_photo_path
│   └── eval/
│       └── vision_harness.py                    # CHANGED — multi-detection checks (FR-009),
│                                                 #   + per-strategy isolation cost/latency report
├── evals/
│   ├── golden_set.yaml                          # CHANGED — vision_cases gain expected_count,
│                                                 #   multi-garment/occluded/worn fixtures
│   └── fixtures/vision_samples/                 # CHANGED — 2 placeholders → 10+ real photos
└── tests/
    ├── unit/
    │   ├── test_vision.py                       # CHANGED — multi-detection, cap, fallback cases
    │   ├── test_isolation.py                    # NEW — each adapter + hybrid trigger, mocked
    │   └── eval/test_vision_harness.py           # CHANGED (if exists) or NEW — harness shape
    └── integration/
        └── test_closet_routes.py                # CHANGED — new + updated extract/from-upload cases

frontend/
├── lib/api/schema.d.ts                          # REGENERATED (generated, gitignored)
├── components/ui/ItemPhoto/
│   └── ItemPhoto.tsx                            # UNCHANGED (research.md §8 — no code change,
│                                                 #   only what call sites pass it)
└── app/(app)/
    ├── add/
    │   ├── AddItemFlow.tsx                      # CHANGED — one photo -> N drafts -> N review cards
    │   ├── BulkQueue.tsx                        # CHANGED — queue keyed to drafts, not files
    │   ├── ReviewCard.tsx                       # CHANGED — renders isolated image or region-
    │   │                                         #   cropped original fallback
    │   ├── OrientationAwarePhoto.tsx             # CHANGED (or a sibling) — region-cropped /
    │   │                                         #   isolated source support (research.md §7)
    │   ├── fromUploadBody.ts                     # CHANGED — thread isolated_photo_path
    │   ├── AddItemFlow.test.tsx                  # CHANGED
    │   ├── BulkQueue.test.tsx                    # CHANGED
    │   ├── ReviewCard.test.tsx                   # CHANGED
    │   └── OrientationAwarePhoto.test.tsx        # CHANGED
    └── closet/[itemId]/
        ├── page.tsx                              # CHANGED — original/isolated toggle (FR-020)
        └── ItemDetailToggle.tsx                  # NEW — the toggle control itself
```

**Structure Decision**: every file above sits inside the fixed layout (`frontend/`, `backend/`,
`infra/`). No new top-level directory. `IsolationClient`'s three adapters sit beside the existing
`adapters/storage.py`/`adapters/llm_gateway.py`, matching `ports.py`'s own stated pattern exactly —
a Protocol in `ports.py`, structurally-satisfying adapters underneath it, chosen by one factory
function reading configuration (mirrors how `kb.py`'s `wtw_kb_mode` already selects between
`corpus`/`reconnect` — same shape, applied to a different Protocol).

## Complexity Tracking

*No entries — no Constitution Check gate required a justified exception.*
