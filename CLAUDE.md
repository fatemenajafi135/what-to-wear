# CLAUDE.md

Guidance for Claude Code (and any fresh session) working in this repo.

## What this is

**What to Wear** — an AI personal styling agent. Grounded-assembly RAG: given a
user's wardrobe + a context (occasion, mood, weather), it assembles an outfit
**from items they already own**, obeying rules retrieved from a fashion
knowledge base, and cites those rules. Solo project; course capstone that may
become a product. Backend in `backend/`; `frontend/` has a working Next.js app
(Feature 003) covering sign-in, add-by-photo, closet view, and get-a-suggestion
(now against `/suggest`, Feature 002 Phase 3) — not yet deployed publicly.

## Read these first (in this order)

1. **`docs/SDD-HANDOFF.md`** — the authoritative plan: current state, the
   5-feature roadmap, known debt, and what's next. Start here every session.
2. **`.specify/memory/constitution.md`** — the non-negotiable rules. Treat as
   binding. Changing it requires an explicit amendment (see its Governance
   section), not a quiet edit.
3. **`specs/<feature>/`** — the full spec/plan/research/tasks for each shipped
   or in-progress feature (e.g. `specs/001-closet-persistence/`).

`docs/what_to_wear_build_plan.md` is **superseded** (pre-constitution
brainstorm, wrong taxonomy/paths/auth) — do not follow it; it's kept for
historical reference only.

## This is a spec-driven project (Spec Kit)

Features run through the Spec Kit workflow: `/speckit.specify` →
`/speckit.clarify` → `/speckit.plan` → `/speckit.tasks` → `/speckit.analyze` →
`/speckit.implement`. (Tasks before analyze, not after: the `speckit-analyze`
skill hard-requires `tasks.md` to exist — `check-prerequisites.sh
--require-tasks` errors out otherwise, since analyze cross-checks spec + plan +
tasks together. Confirmed directly in the 002 session; if you see the reverse
order elsewhere, this is the corrected one.) Don't skip `/speckit.analyze`, and
read it like a critic — the planner over-builds; hold it to the constitution's
simplicity rule.

## Session workflow (planner / worker split)

This project is run as **one planning conversation + a fresh session per feature
(or per Feature-002 phase)**. The durable source of truth is the **repo**
(`docs/SDD-HANDOFF.md`, `specs/`, git, the memory files) — not any single chat.
So:

- **A worker session** picks up the next item from SDD-HANDOFF, runs it through
  the spec-kit workflow, and **on completion MUST write state back** — this is
  the handoff contract, not optional:
  1. Update `docs/SDD-HANDOFF.md`: the feature table + "current state" (and
     "Known debt" if you closed or added any).
  2. Update the **"Current state" section in this file (CLAUDE.md)**.
  3. Mark the feature's `specs/<feature>/tasks.md` items `[X]`.
  4. Add a memory if a real decision was made (see the memory index).
  Skip this and the next session starts from stale state and creates conflicts.
- **A planner session** (e.g. deciding the next feature) must **re-read
  SDD-HANDOFF + `git log` first** — don't plan from stale in-context memory, a
  worker session may have moved things since.

## Current state (keep this in sync as features land)

- **Feature 001 (closet-persistence): DONE, merged to `main`.** Per-user closet
  + shared catalog in Postgres (Supabase), JWT auth (ES256/JWKS), full CRUD.
  `context_assembler.load_wardrobe()` reads Postgres now, not the JSON fixture.
- **Feature 002 (styling-agent), broadened + phased — ALL PHASES DONE,
  merged to `main` (2026-07-16).** Phase 1 (auth-gate `/recommend`,
  unit-test backfill) merged earlier. Phases 2–4, built in a parallel
  worktree alongside Feature 004 and merged back after both finished:
  - **Phase 2 — `scoring/` package**: four deterministic dimension scorers
    (color harmony, formality coherence, weather fitness, silhouette
    balance) + a swappable combination strategy (FR-009a), imported
    unchanged into both the graph and `eval/harness.py` via one shared
    `scoring.score_outfits()` call (Principle V — never forked).
  - **Phase 3 — `pipeline/graph.py` + `POST /suggest`**: the linear pipeline
    became an 8-node LangGraph `StateGraph`; `wardrobe_retrieval` prunes on
    hard constraints before generation ever sees the closet (k=8/slot);
    `score_and_rank` is the only ranking step. `/recommend` and
    `pipeline/run.py` are **deleted** — `/suggest` (SSE) is the sole
    suggestion entrypoint, and the frontend (`app/suggest/page.tsx`,
    `components/SuggestionResult.tsx`) is cut over to it (a hand-rolled SSE
    parser in `lib/api-client.ts`, since `EventSource` doesn't support
    POST). `eval/harness.py` now runs the golden set through the compiled
    graph, not the retired `run_pipeline`.
  - **Phase 4 — refinement**: `memory/store.py`'s checkpointer is now
    Postgres-backed (see Gotchas below for a real prepared-statement issue
    hit here). "Warmer"/"less formal"/"alternatives" are deterministic
    keyword-parsed deltas that shift `wardrobe_retrieval`'s pruning bounds
    or exclude prior item-sets — never touching `ctx` itself, so unstated
    constraints survive a refinement turn (FR-013). An optional
    reported-only LLM judge score (`eval/judge.py`, FR-010) is opt-in via
    `harness.py --judge`, off by default.
  - Full eval no-regression gate green after every phase touching
    retrieval/generation (per-case `retrieval_recall` byte-identical to the
    archived baseline throughout). Full narrative, including two real bugs
    found via live end-to-end testing (not just unit tests) and fixed:
    SDD-HANDOFF Step 3.
- **Feature 003 (mvp-app), redefined from "closet-ingestion" — code complete,
  not yet deployed.** Full spec-kit cycle run on branch `003-mvp-app`.
  Backend: additive `pattern`/`fit` migration, CORS middleware, `vision.py`
  (VLM photo→attribute extraction) + `storage.py` (Supabase Storage upload,
  caller's own bearer token, no service key), two new endpoints
  (`POST /wardrobe/items/extract`, `POST /wardrobe/items/upload`) — parallel
  to, not replacing, the existing catalog-add path. `/recommend`,
  `/wardrobe/items` CRUD, and JWT auth all reused unchanged. 149 existing +
  11 new backend tests pass, ruff clean. Frontend: first code in
  `frontend/` — Next.js app (App Router, TypeScript) covering all 4 required
  user stories (sign-in/up, add-by-photo, view closet, get a suggestion),
  consuming the backend's OpenAPI schema for types (constitution Principle
  VII — generated and verified, not hand-maintained). typecheck/lint/build
  clean; smoke-tested against a locally running backend. **The 3 manual,
  owner-only steps this feature left outstanding** — create the Supabase
  Storage `wardrobe-photos` bucket + RLS policy, deploy backend to Railway,
  deploy frontend to Vercel (`specs/003-mvp-app/tasks.md`
  T010/T037/T038/T039) — **are now done**, confirmed by the project owner
  during Feature 005 (which absorbed completing them into its own scope,
  per that feature's plan). The live backend is currently running
  pre-Feature-005 code; see Feature 005's entry below for what needs a
  redeploy. **Also remaining, deliberately paused:
  visual polish** — three styling passes (ad hoc CSS, then the Nocturne
  design system's own component classes, then tracing exact colors out of
  `design/What to Wear.dc.html`'s render logic) still didn't match
  expectations; stopped rather than keep iterating without a way to
  actually see it rendered. Full narrative:
  `docs/003-mvp-app-implementation-report.md` (local, untracked). See
  SDD-HANDOFF Step 4.
- **Feature 004 (preference-memory) — DONE, merged to `main`.** Full
  spec-kit cycle run. Closed the gap `set_preference()`/`get_profile()` were
  defined but never called/backed by anything durable: reactions (`POST
  /preferences/feedback`) now persist to Postgres (`suggestion_feedback` +
  `preference_signal_dismissal`, migration `0003`), a pure `derive_signals()`
  function (`memory/preferences.py`) computes rejected colors/avoided
  categories/formality drift with a net-count threshold, and
  `memory/store.py`'s `get_profile()` derives from that instead of an
  `InMemoryStore` — `profile_note(user_id)`'s signature/behavior are
  unchanged, so the generation path needed **zero** changes, exactly as
  planned. Three more endpoints (`GET /preferences`, `DELETE
  /preferences/signals/{signal_key}`, `DELETE /preferences`) plus a
  frontend reaction affordance and a `/preferences` view. **One thing the
  plan didn't anticipate**: `set_preference()`'s free-form key/value API had
  no equivalent under the new derive-only model, so it was removed outright
  (its one caller, `eval/test_users.py`'s manual debug tool, was updated to
  match). 181 backend tests pass (162 pre-existing + 19 new), ruff clean,
  eval no-regression gate passed (this feature touches no retrieval/
  generation code). Full detail: SDD-HANDOFF Step 5.
- **Features 002 (Phases 2–4) and 004 were developed in parallel, in
  separate git worktrees (2026-07-16), then merged back to `main` in a
  dedicated merge session** (`/home/fateme/Projects/w2w/what-to-wear-002`,
  `/home/fateme/Projects/w2w/what-to-wear-004` — both worktrees can be
  removed now that their branches are merged). 004 merged first; by the
  time 002 was ready, `main` had moved and the merge produced 10 real
  conflicts (not the 9 estimated ahead of time — `schema.py` and
  `eval/test_users.py` also conflicted). Two files needed real
  reconciliation, not just picking a side: `memory/store.py` (002's
  Postgres-backed checkpointer + 004's Postgres-derived profile — both
  kept, they touch disjoint functions in the same file) and `api.py` (002's
  `/suggest` replacing `/recommend` + 004's four new `/preferences/*`
  endpoints — both kept, only the import block actually overlapped).
  `eval/test_users.py` needed a real fix, not just a merge: 002's `__main__`
  block still called `seed_test_user_memory()` → `memory.set_preference()`,
  which 004 had deleted outright — resolved by keeping 002's graph-based
  invocation but dropping the now-nonexistent seeding call, matching 004's
  approach. Full test suite + eval no-regression gate re-run after
  resolving, before the merge commit (see Gotchas below for what that
  surfaced). `.specify/feature.json`, `frontend/lib/api-types.ts`, and
  `frontend/openapi.json` were regenerated/repointed rather than
  hand-merged.
- **Feature 005 (production-hardening) — DONE, merged to `main`, and
  deployed live.** Full spec-kit cycle on branch
  `005-production-hardening` (own worktree,
  `/home/fateme/Projects/w2w/what-to-wear-005` — can be removed now, the
  branch is merged). `/speckit.clarify` resolved
  4 ambiguities (per-user-only cache scope; LangSmith tracing satisfies
  FR-010's operator-visibility requirement — no new dashboard built;
  same-provider-only retry, no cross-provider fallback; a concrete
  sub-second cache-hit target for SC-003). `/speckit.analyze` found and
  fixed 2 gaps before implementing: the spec's own Edge Case about
  DB/vector-store health checks had no FR or task (added FR-012 + a task),
  and the grounding guardrail's original closet-only design was a
  literal-compliance gap against constitution Principle IV — widened to
  check both the closet and the shared catalog at negligible cost.
  - **Output grounding guardrail (US2)**: new `pipeline/grounding.py` +
    a `verify_grounding` graph node between `score_and_rank` and `explain`,
    dropping any outfit whose items aren't in the requester's wardrobe or
    the shared catalog — a safety net on top of, not instead of, the
    existing deterministic-selection guarantee. Eval harness confirms
    `retrieval_recall` byte-identical to the archived baseline and
    `owned_only` unaffected — no legitimately-grounded outfit is ever
    dropped.
  - **Per-user `/suggest` cache (US3)**: new `pipeline/cache.py` — an
    explicit, exact-key Redis cache around the whole graph invocation, not
    LiteLLM's own per-call semantic cache (which can't reach retrieval and
    risks fuzzy false-positive matches across different users' closets — a
    real correctness risk, not just a staleness one). Keyed by the
    verified user id + normalized context + a full-content wardrobe
    fingerprint, so any closet edit naturally busts a stale entry. Two real
    bugs found via testing: an occasion-normalization bug in the cache-key
    derivation, and a cache hit's `thread_id` never reaching the
    checkpointer (breaking a refinement that continued a cached first
    turn) — fixed by seeding the checkpointer on every hit via
    `graph.update_state(...)`.
  - **LiteLLM routing (US4)**: `config.py`'s `get_chat_model`/
    `get_judge_model` now build `langchain-litellm`'s `ChatLiteLLM` instead
    of `langchain_openai`'s `ChatOpenAI` (same gateway) — automatic retry +
    LangSmith-visible cost/usage for free. Three of four call sites needed
    zero changes; `vision.py`'s all-`Optional`-fields extraction schema hit
    a real gateway incompatibility with `ChatLiteLLM`'s structured-output
    handling (two guessed fallbacks were tried and rejected by the gateway
    before finding the real fix — a hand-written nullable-required JSON
    schema). See Gotchas below.
  - **Deploy (US1)**: Feature 003's three manual steps (Supabase Storage
    bucket, Railway, Vercel) are now all confirmed working by the project
    owner. Railway had a real "builds fine, container stops a few seconds
    later, no traceback" issue during this feature's own pre-merge testing,
    resolved on the dashboard side (health-check/service-type config) —
    not a code issue. A **second, different** Railway issue surfaced
    during the post-merge redeploy: the public domain's Networking target
    port didn't match the port the app actually bound to, producing
    "Application failed to respond" from a perfectly healthy container —
    fixed by aligning the target port and pinning `PORT=8080` explicitly.
    `/health`/`/docs` confirmed reachable live afterward — this feature's
    actual changes (cache, guardrail, LiteLLM, the new `/health`) are
    validated in production, not just merged.
  - Also shipped, beyond the original task list: `GET /health` now checks
    Postgres + Qdrant reachability (`503` naming the failed dependency)
    instead of always returning a static `200 ok` (FR-012, a
    `/speckit.analyze` finding against the spec's own Edge Case).
  - The "intermittent" test failure originally flagged here was
    root-caused during the merge — it wasn't flaky, see Gotchas below.
  - Full narrative: `docs/SDD-HANDOFF.md` Step 6,
    `docs/005-production-hardening-merge-report.md`.
- **Feature 006 (wardrobe-item-photos) — DONE, merged to `main`, deployed
  live (confirmed on Vercel).** Direct user request, not part of the
  original 5-feature plan: closet cards didn't show the item's actual photo
  even though one already existed in Storage for every photo-uploaded item.
  Kept deliberately minimal — one user story, no new API endpoint (the
  frontend's existing authenticated Supabase client generates signed URLs
  against the already-secured private bucket directly). Backend: additive
  migration `0004` adds nullable `photo_path` on `wardrobe_items`;
  `create_wardrobe_item_from_upload` now sets it (previously received but
  silently discarded) and `_to_wardrobe_item` returns it on every read
  path including `GET /wardrobe/items`. Frontend: `ClosetItemCard.tsx`
  resolves `photo_path` to a signed URL client-side and renders it above
  the swatch row, with any failure (absent path, expired object, network
  error) falling back to today's swatch-only card. Live browser
  verification (real photo + swatch fallback) confirmed by the owner.
  Full detail: `docs/SDD-HANDOFF.md` Step 7, `specs/006-wardrobe-item-photos/`.
- **Feature 007 (ai-improvements) — built in a separate, credential-less
  sandbox (three build tasks from a cert-challenge handoff, not
  planner-originated), then independently reviewed, verified, and merged
  from this session.** Closes two cert-rubric gaps plus a real bug, all
  independent, backend-only:
  - **L1 semantic sub-layer**: `retrieval/hybrid.py`'s `retrieve_l1()` now
    unions the existing hand-written atomic rule cards with a
    `similarity_search` over long-form section chunks (Wikipedia color
    theory/harmony/complementary-colors, Chevreul, Munsell) that
    `build_kb.py` already embedded into the same L1 layer but retrieval never
    queried — a genuinely new capability over data that was already there.
  - **Live Tavily L3**: `retrieve_l3()` now calls the project's existing
    `external/trends.search_trends()` live at request time instead of
    querying a static pre-ingested trend collection, mapping results into
    citable `Document`s with a synthetic per-result `rule_id`; degrades to
    `[]` on failure (weather-fallback pattern). The static
    `l3_trend_cards.jsonl` stays ingested for `baseline`'s sake (it queries
    the whole corpus directly and never calls `retrieve_l3`) — only the
    hybrid/advanced code path is retired, not the underlying data. 3 golden
    cases' `relevant_rule_ids` trimmed of a now-unreproducible static L3 pin.
  - **Warmth-floor fix**: the "warmer" refinement's prior fix (a blanket
    `_WARMTH_FLOOR_EXEMPT_GROUPS` exemption for footwear/accessory, Feature
    002 Phase 4) is replaced with a per-category-relative floor
    (`_category_warmth_ceiling()`) scaled to each category's own achievable
    warmth in the actual closet, capped at that ceiling — a low-ceiling
    category now gets a real, small push instead of either an impossible
    flat bar or a full pass-through.
  - **A real operational gap found during this session's review, not in the
    original sandbox**: the new L1 semantic filter is a compound Qdrant
    filter (`layer` + `granularity`), and the live collection only had an
    index on `layer` — filtering on an unindexed field 400s in server mode.
    Fixed by adding the missing `metadata.granularity` payload index
    directly (cheap — the underlying chunk data already carried this field,
    no re-embed needed).
  - Verified this session: eval no-regression gate + integration tests
    against real credentials (this session's sandbox had none). Full
    narrative and exact outcome: `docs/SDD-HANDOFF.md` Step 8.
- **Feature 008 (bulk-upload-outfit-photos) — continued forward on the
  `006-wardrobe-item-photos` branch after 006 already merged (per explicit
  user instruction, not a fresh branch); numbered 008 since 007 was already
  taken by the unrelated ai-improvements branch.** Four more photo
  capabilities, direct user request, all building on Feature 006: **US1/P1
  bulk photo upload** (new `/closet/add-bulk` page — select up to 30
  photos, sequential extraction with per-item progress, per-item review
  reusing `ExtractedItemForm`, per-item save with independent
  retry-on-failure so one bad photo/save never costs the rest of the
  batch — no new backend logic, reuses the existing single-item
  extract/upload endpoints in a loop); **US2/P2 outfit-suggestion photo
  display** (`SuggestionResult.tsx` now renders each outfit's items as a
  horizontal row of real photos via a new `OutfitItemPhoto` component,
  replacing the old text-only list — the underlying data, `closetById`'s
  `WardrobeItem` objects, already carried `photo_path`, this was purely a
  rendering change); **US3/P3 photo preview during single-item review**
  (`ExtractedItemForm` now shows the captured photo); **US4/P4 edit/remove
  photo on a saved item** (`WardrobeItemPatch` gains `photo_path` — enables
  removal via the existing generic `PATCH` endpoint, zero `crud.py` change
  needed — plus one new endpoint, `POST /wardrobe/items/{id}/photo`,
  composing `storage.upload_wardrobe_photo` + `crud.update_wardrobe_item`;
  deliberately never calls `vision.extract_attributes_from_image` — a photo
  swap isn't a re-classification, FR-014). Shared infra: `ClosetItemCard`'s
  Feature-006 signed-URL logic extracted into a reusable
  `useSignedPhotoUrl` hook, reused by US2/US3/US4 rather than duplicated
  three times. Full detail: `docs/SDD-HANDOFF.md` Step 9,
  `specs/008-bulk-upload-outfit-photos/`.
- **AI v2 epic (WP0-WP8) started, `feature/009-scoring-fixes` merged to
  `main`.** New multi-branch epic on top of 006/007/008, driven by a
  certification-challenge resubmission (`docs/deliverable.md`,
  `docs/claude-code-implementation-spec.md`, `docs/ai-v2-session-handoff.md`
  — the last is the authoritative "start here" pointer for this epic,
  analogous to this file's own role for the rest of the project). Owner's
  directive: urgent debug first (T0.1-T0.4, this branch), then WP0's
  `approach` plumbing (010), then WP2 Engine (011), then the planner's
  recommendation for what follows. **009 ran the full spec-kit cycle**
  (`specs/009-scoring-fixes/`) and fixed four verified-real bugs, all
  independent (four user stories):
  - **Color-harmony scorer was inverted** (Task 5's headline deliverable
    story) — `scoring/color_harmony.py` scored mean pairwise WCAG contrast
    directly, rewarding clashing complementary pairs over tonal/neutral
    ones. Rewritten around real color theory (neutral-anchored/analogous
    favored, unbalanced-complementary and 3+-hue clashes penalized) — new
    `colors.hex_to_hsl()`. **A real inconsistency in the source technical
    spec was found and fixed during implementation, not assumed upfront**:
    the spec's own required test case (tomato red + emerald green, `<0.45`)
    failed arithmetic against its own proposed algorithm once run against
    the real palette hexes (0.4 base + 0.1 bonus = 0.5) — resolved by
    revising that hue-band's base score 0.4→0.3, re-verified against all 6
    of the spec's required cases before committing. A second such issue:
    the spec's own illustrative "navy + mustard" complementary-pair example
    doesn't work at all, because navy is one of this project's own *named
    neutrals* (pre-existing, intentional — "navy is the new black") and so
    can never be a chromatic partner; substituted `cobalt`. Full narrative:
    `specs/009-scoring-fixes/research.md` Decision 1's addenda.
  - **Default ranking strategy** changed from equal-weighted average to the
    existing, already-tested `fit_first_lexicographic` (weather/formality
    fit decide before color/silhouette cosmetic tiebreaks) — a one-line
    default-parameter change in `scoring/combine.py`.
  - **Per-slot candidate cap wasn't sorted before truncating** — the actual
    best-fitting item in a slot could be silently dropped from
    `pipeline/graph.py`'s `wardrobe_retrieval` purely for not being early in
    closet order. Fixed by sorting on formality/warmth fitness immediately
    before the existing `_CANDIDATES_PER_SLOT` slice. **`/speckit.analyze`
    caught a real plan error before this was implemented**: the draft
    algorithm assumed a formality-inference fallback was needed
    (`ctx.formality or infer_formality(...)`), but `ctx.formality` is
    already unconditionally resolved by `context_assembler.assemble_context`
    before `Context` is ever built — the fallback would have been dead
    code, simplified out before implementing.
  - **Color-name lookup was missing common names** (e.g. teal resolved to
    "sage") — 8 names added to `colors.FASHION_COLOR_PALETTE`.
  - Eval no-regression gate: `retrieval_recall` byte-identical on every
    shared golden case across all three strategies (baseline/hybrid/
    advanced), `owned_only` unaffected, zero hallucinated items — full
    comparison against a snapshotted pre-009 baseline (gitignored source,
    tracked at `docs/eval-baselines/pre-009/` and `.../post-009/` since
    `backend/artifacts/eval_runs/` isn't) in
    `docs/eval-baselines/pre-009/COMPARISON.md`. 350/351 backend tests pass
    (1 failure reproduced as a pass twice in isolation — confirmed
    LLM-sampling flakiness per the gotcha below, not a regression). ruff
    clean on every file this feature touches.
  - Since committed and merged to `main`.
- **Feature 010 (engine) — implemented on `feature/010-engine`, all tasks
  complete, NOT YET MERGED (owner directive this session: do not merge —
  commit only).** WP2 Engine, with WP0's T0.5 `approach` plumbing folded in
  (one branch, per `docs/ai-v2-session-handoff.md`'s scoping decision — the
  spec's separate 010/011 split is consolidated). Full spec-kit cycle
  (`specs/010-engine/`); `/speckit.analyze` found and fixed two real
  coverage gaps before implementing: FR-007 (citation resolution) had no
  deterministic runtime enforcement, only a prompt instruction — closed
  with a citation filter in `engine_write` mirroring `verify_grounding`'s
  role, applied to citations instead of items; FR-011 (refinement
  approach-stickiness) was only covered by a mocked invoke-dict check —
  added a real-checkpointer two-turn test.
  - **`approach` opt-in on `POST /suggest`** (`SuggestRequest.approach`,
    default `"grounded"` = today's unchanged behavior; `"engine"` is the
    only new value actually routed anywhere). Sticky across a refinement
    conversation via the same mechanism `original_context` already uses —
    `api.py` only includes `approach` in the graph-invoke input on a fresh
    request, so LangGraph's checkpoint-merge leaves a continuing thread's
    turn-1 value untouched regardless of what a later turn's body carries.
  - **New `pipeline/engine.py`**: `enumerate_outfits()` deterministically
    builds top×bottom×footwear and full_body×footwear skeletons (outerwear-
    crossed, additively, when cold/freezing), reusing the existing
    `_is_valid_combination`/`_is_slot_complete` guards — moved verbatim
    into a new `pipeline/validity.py` first, since `graph.py` importing
    `engine.py`'s node functions while `engine.py` imported those guards
    from `graph.py` would have been circular (pre-authorized by the source
    spec as a "pure move, no edits" if this happened). A >20,000-projected-
    combo safety valve slices the already-fitness-sorted candidate lists
    `wardrobe_retrieval` hands it — no second sort. `engine_write()` is the
    path's one LLM call: selection-and-writing only, never proposing a
    combination — a structurally/semantically invalid response (wrong
    count, out-of-range/duplicate index, call failure) discards entirely
    and falls back to the deterministic top-3-by-`rank_score` with
    template rationale, so a bad model response degrades the result at
    worst, never breaks the request.
  - **Graph wiring**: one new conditional edge after `wardrobe_retrieval`
    (`approach=="engine"` → `engine_enumerate_and_score` → `engine_write`;
    everything else → the existing `generate_outfits` → `score_and_rank`,
    byte-for-byte unchanged), both branches converging on the existing
    `verify_grounding` → `explain` tail. `engine_write`'s node wrapper
    mirrors its result into both `scored_outfits` and a synthetic
    `generated` (`GenOutput`) so neither downstream node needs an
    engine-specific branch.
  - Opt-in only (per `docs/ai-v2-session-handoff.md`'s scoping decision) —
    the default path is provably unaffected, so the full eval no-regression
    gate was not required for this feature; the comparison lives in the
    spec/task artifacts instead.
  - 371/371 backend tests pass (351 pre-feature baseline + 20 new — 17
    unit, 4 integration, one pre-existing test file gained a class), zero
    regressions. Two integration tests ran against the live stack for
    real (KB/Qdrant/DB, one including a genuine `engine_write` LLM call,
    not mocked) rather than only mocked. ruff clean on every file this
    feature touches. `frontend/lib/api-types.ts` regenerated — diff shows
    only the new `approach` field, nothing else.
  - **Constitution note**: the new `engine` path itself complies with
    Principle II (deterministic selection); the pre-existing default
    (`grounded`) path's `generate_outfits` still doesn't (the LLM assembles
    combinations directly) — untouched by design, per the source spec's own
    instruction not to "fix" `direct`/`grounded`. The constitution amendment
    recording their explicit exemption is still a separate follow-up, not
    done in this feature (doesn't require any code change).
  - Full detail: `specs/010-engine/` (spec/plan/research/data-model/
    contracts/quickstart/tasks, all current), 9 commits on
    `feature/010-engine`, one per logical task group.
- **Next**: get the owner's go-ahead to merge `feature/010-engine`, then
  continue the AI v2 epic per the planner's call (WP3 HITL, WP1 Direct, WP8
  eval, WP4 weather as time allows — see
  `docs/ai-v2-session-handoff.md`'s open flags). Separately, all 5
  originally-planned features plus 006, 007, and 008 are done and merged.
- **Environment gotcha found while finishing Feature 004**: a fresh `git
  worktree add` only copies tracked files — `backend/data/` (gitignored:
  golden set, KB corpus, wardrobe fixture) was entirely absent from this
  worktree, breaking `test_seed.py` and the eval harness with
  `FileNotFoundError` until copied over from a sibling checkout that has
  it. If a fresh worktree session hits that error, this is why.

## The rules that bite hardest (full text in the constitution)

- **The LLM never selects clothing items.** Item selection is deterministic
  pruning/combination/scoring (Principle 2). Scoring for outfit quality is pure
  Python, reused unchanged in the eval harness (Principle 5). An LLM *judge*
  score may be reported as an edge signal but never drives selection.
- **Style KB gates wardrobe retrieval** — KB queried first, returns structured
  directives, never parallel (Principle 3).
- **Grounded output only** — every item in a suggestion exists in the closet or
  catalog; every rationale cites a retrieved rule_id or scorer output.
- **No-regression gate** — after any change touching retrieval/generation,
  re-run the eval harness and compare against `backend/artifacts/eval_runs/`.
- **Schema is frozen** (Principle 6): category groups
  `top/bottom/full_body/outerwear/footwear/accessory`, six-value formality enum
  (`casual`…`black_tie`), warmth **0–5**, seasons, hex colors. Don't introduce a
  parallel numeric formality scale or rename groups.
- **Simplicity over abstraction** — no repository patterns / service layers /
  ABCs unless two concrete implementations exist today.

## Commands (run from `backend/`)

```bash
uv sync --group dev                      # install incl. pytest/ruff
uv run alembic upgrade head              # apply migrations (needs DATABASE_URL)
uv run python -m whattowear.crud seed-catalog        # one-time catalog seed
uv run python -m whattowear.crud seed-eval-baseline  # eval baseline user's closet
uv run uvicorn whattowear.api:app --reload           # API + Swagger at /docs
uv run pytest tests/ -q                  # unit + integration tests
uv run ruff check . && uv run ruff format .          # lint + format
uv run python -m whattowear.eval.harness # no-regression eval gate
```

Env: `cp backend/.env.example backend/.env` and fill it — needs the gateway
keys (`AI_GATEWAY_API_KEY`, `TAVILY_API_KEY`, `COHERE_API_KEY`), the Qdrant
cloud URL/key, **and** `DATABASE_URL` + `SUPABASE_URL` (the app raises without
the DB vars). Full run/architecture detail: `backend/README.md`.

## Gotchas a fresh session will hit

- **Tests run against the real Supabase database**, isolated per-test by a
  rolled-back transaction fixture (`backend/tests/conftest.py`) — there is no
  separate test DB. They're slower than mocks and need network + real DB creds.
- **The eval harness makes many external calls and is flaky under transient
  network drops** (Qdrant/Cohere/gateway resets). `retrieval_recall` is the
  deterministic metric to compare across runs; the generation-dependent checks
  drift run-to-run from LLM sampling — that's not a regression. Don't declare a
  regression from a single failed or partial run.
- **`/recommend` no longer exists** (Feature 002 Phase 3, T037a) — deleted along
  with `pipeline/run.py` once `/suggest` was verified equivalent and the
  frontend confirmed cut over. `POST /suggest` (SSE, auth-gated the same way
  `/recommend` used to be — `get_current_user_id`, `user_id` from the verified
  JWT `sub`, never the body) is the sole suggestion entrypoint now.
- **Supabase pooler (port 6543)** doesn't support server-side prepared
  statements — the engine disables them; migrations prefer the direct 5432 URL
  when reachable. See `specs/001-closet-persistence/research.md`. **This bit a
  second component in Feature 002 Phase 4**: `langgraph-checkpoint-postgres`'s
  `PostgresSaver.from_conn_string` hardcodes `prepare_threshold=0` (prepare on
  first use) and reproduced the same "prepared statement does not exist"
  failure — even against `DATABASE_URL_DIRECT`, not just the pooler. Fixed in
  `memory/store.py` by connecting manually with `prepare_threshold=None`
  instead of using `from_conn_string`.
- **A fresh `git worktree add` does NOT carry over gitignored files** —
  `backend/data/` (KB source + `golden_set.yaml`) and `backend/artifacts/
  eval_runs/` are both gitignored, so a new worktree starts with neither and
  the eval harness can't run at all until they exist. Copy them from an
  existing checkout (`rsync -a` from the main worktree's `backend/data/` and
  `backend/artifacts/eval_runs/`) — confirmed necessary setting up this
  worktree for Feature 002 Phases 2-4.
- **The same gitignored-files gap hits a fresh remote-sandbox clone too, not
  just `git worktree add`** (confirmed in the Feature 007 session). A plain
  fresh clone (no prior checkout to copy from, no `.env` either) is missing
  `data/wikipedia/*.md`, `data/books/*.epub`, and `data/fixtures/wardrobe.json`
  — only `golden_set.yaml`, `data/kb/manifest.yaml`, and the 3 `data/kb/*.jsonl`
  card files are actually tracked in git. `get_kb()` fails on the missing
  `.epub` before ever making a network call, so this bites even a KB read that
  doesn't need real credentials. Combined with no `.env` (no DB/gateway/Tavily/
  Qdrant/LangSmith credentials at all in a fresh sandbox), a session in this
  situation can implement and unit-test any pure-Python change but cannot run
  the eval harness, any integration test hitting `/suggest`, or anything else
  touching the real KB/DB/gateway — there is no local workaround, only
  documenting exactly what couldn't be verified and flagging the eval gate as
  the mandatory next step for a session that does have real credentials.
- **LangGraph checkpoint deserialization warns on the project's own Pydantic/
  dataclass types** (`Context`, `ScoredOutfit`, `SuggestResult`, `GenOutput`,
  `RetrievalResult`, `WardrobeItem`) — `Deserializing unregistered type ...
  This will be blocked in a future version`. Still works today (Feature 002
  Phase 4's refinement checkpointing); a future `langgraph-checkpoint-postgres`
  upgrade may require registering these via `allowed_msgpack_modules`. Not
  done — flagged for whoever upgrades that dependency next.
- **Node.js isn't preinstalled in a fresh sandbox** (confirmed in the Feature
  003 session). No passwordless sudo either. Install via nvm (user-level, no
  root): `curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh
  | bash && nvm install --lts`. If the coding tool runs each command through a
  single long-lived shell process (rather than a fresh login shell per
  command), edits to `~/.zshenv`/`~/.zshrc` made *after* that process started
  won't take effect for the rest of the session — prefix Node/npm commands
  with `export PATH="$HOME/.nvm/versions/node/<version>/bin:$PATH"` instead of
  relying on shell-startup-file sourcing.
- **`frontend/lib/api-types.ts` needs a reachable backend to (re)generate** —
  `npm run fetch:openapi` curls `/openapi.json` from a *running* instance
  (local `uvicorn` or the deployed Railway URL). There's no way to generate
  it from static source alone; start the backend first.
- **The Supabase Storage `wardrobe-photos` bucket + its per-user RLS policy
  is a manual, one-time dashboard step** (Feature 003), not something any
  migration or seed script creates — see `specs/003-mvp-app/quickstart.md`
  Prerequisites. `storage.py` will fail every upload until this exists.
- **`ChatLiteLLM`'s default structured-output handling rejects an
  all-`Optional`-fields Pydantic schema against this project's gateway**
  (Feature 005) — `"'required' is required to be supplied and to be an
  array including every key in properties"`. Pydantic omits fields with
  defaults from the generated JSON schema's `required` array;
  `langchain_openai.ChatOpenAI` used to paper over this, `ChatLiteLLM`
  doesn't. Two plausible-looking fallbacks do **not** work against this
  gateway either — confirmed by reproducing the real `BadRequestError` for
  each: `method="json_mode"` (gateway rejects `response_format={"type":
  "json_object"}` outright, even text-only) and `method="json_schema",
  strict=False` (the `strict` flag doesn't suppress the requirement
  server-side). The actual fix: pass a hand-written JSON schema dict with
  every property typed nullable (`["string", "null"]`) and *all* listed in
  `required` directly to `with_structured_output(schema_dict,
  method="json_schema")` — see `vision.py`'s `_EXTRACTION_SCHEMA` for the
  working example. Any future all-optional-fields extraction schema will
  hit this same wall.
- **Any integration test hitting `/suggest` for a seeded user is now
  implicitly subject to the per-user Redis cache** (Feature 005) — a
  cross-test-file cache hit caused a real, reproducible failure
  (`test_suggest_refinement.py` reading a stale result cached by an
  unrelated earlier test). Fixed with a global autouse fixture in
  `tests/conftest.py` (`_flush_suggest_cache`, mirrors `db_session`'s
  rollback isolation but for Redis) — any new integration test file hitting
  `/suggest` gets this for free, no per-file fixture needed.
- **`test_suggest_cache.py::test_closet_edit_invalidates_the_cache` looked
  flaky, wasn't** — resolved during the 005 merge, worth knowing about for
  any test that mutates data via a `client` fixture: this file's fixture
  only overrides `get_current_user_id`, not `get_session` (unlike
  `db_session`-isolated tests elsewhere), so its `PATCH` commits for real,
  permanently, against the live `EVAL_BASELINE_USER_ID` wardrobe. The
  original test patched a **hardcoded** literal string and never reset
  it — so any run after the first was a no-op edit (confirmed by reading
  the row directly: it already held that exact value from a prior run),
  making the resulting "cache hit" correct behavior on unchanged data, not
  a bug. Fixed with a `uuid.uuid4()`-suffixed value per invocation. General
  lesson: a test that writes real data through a non-isolated session
  needs either unique-per-run values or the `db_session` rollback fixture
  — a fixed literal will eventually collide with its own prior run. Full
  narrative: `docs/005-production-hardening-merge-report.md`.

## Git

Commit per logical unit with clear messages. Don't push or merge unless asked.
Keep history clean (no noise merges). `gh` is not installed in some
environments — offer the web PR flow when that's the case.
