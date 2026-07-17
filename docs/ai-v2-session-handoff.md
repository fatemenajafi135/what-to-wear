# AI v2 — Session Handoff (start here)

**Role of this file:** the "next session, start here" pointer for the AI-improvement
epic. It does **not** replace the task spec — it records the plan, the verified
findings, the branch sequence, and the carry-forward gotchas a fresh session must
know before touching scoring/retrieval.

## Source of truth (read in this order)
1. `.specify/memory/constitution.md` — binding rules. This work is **additive**
   (Principle I): extend retrieval/ingest/KB/eval; never rewrite them.
2. `docs/claude-code-implementation-spec.md` — the WP-by-WP *what & where*. The
   detailed task breakdown lives there; this handoff points into it, doesn't copy it.
3. `docs/development-plan-v2.md` — the *why* (if present).
4. `CLAUDE.md` — operational gotchas (eval flakiness, tests hit the live DB, Supabase
   pooler, etc.).

## Current state of `main`
- Merge `3f81fec` landed six reliability fixes (branch `fix/category-group-mapping`).
  `/suggest` is reliable: category mapping fixed, checkpointer pooled, coherent
  outfits, formality inference, clean Qdrant rebuild. **This epic builds on that.**
- The `/suggest` cache is **OFF** by default (`WTW_SUGGEST_CACHE_ENABLED`, default
  false). Don't be surprised; don't re-enable without the owner's OK.

## Status: `feature/009-scoring-fixes` merged; `feature/010-engine` implemented, not yet merged (owner directive: commit only, no merge this session)
T0.1-T0.4 are done — full spec-kit cycle (`specs/009-scoring-fixes/`),
color-harmony rewrite + ranking default + sort-before-cap + palette
additions, all four independently unit-tested, eval no-regression gate
green (`docs/eval-baselines/pre-009/COMPARISON.md`). **Two real
inconsistencies in this doc's own T0.1 algorithm were found and fixed
during implementation** — see `specs/009-scoring-fixes/research.md`
Decision 1's addenda: the required "tomato red + emerald green <0.45" test
case didn't actually pass at the originally-proposed 0.4 midband score
(revised to 0.3), and the "navy + mustard" complementary-pair example is
structurally impossible here (navy is a named neutral in this project's own
palette, not a chromatic — substituted cobalt). Full narrative: `CLAUDE.md`
Current State and `docs/SDD-HANDOFF.md` Step 10.

**009 is now committed and merged to `main`.** `feature/010-engine` (WP2
Engine, folding in WP0's T0.5 plumbing per the scoping decision below) is
now also fully implemented — all 23 tasks in `specs/010-engine/tasks.md`
done, 371/371 backend tests green, 9 commits on the branch. **Not merged
this session** — the owner asked for commit-only, no merge. Next: get the
owner's go-ahead to merge, then continue per the planner's call (see the
Planner's open flags below).

## Branch convention (owner's decision)
- **`feature/NNN-name`**, 3-digit, continuing from 008. One branch per WP; each ends
  with `cd backend && uv run pytest` green and its own acceptance criteria met.
- Do **not** rename already-merged branches (their names are baked into `main`'s
  merge commits — leave history alone). Convention applies going forward only.

## Planned sequence
| Order | Branch | Scope | Spec ref |
|-------|--------|-------|----------|
| 1 | `feature/009-scoring-fixes` (merged) | **Urgent debug**: color-harmony rewrite, combine default, sort-before-cap, palette | T0.1–T0.4 |
| 2 | `feature/010-engine` (implemented, not merged) | `approach` plumbing (T0.5) folded into the Engine approach itself — Principle II compliance | T0.5 + WP2 |
| 4+ | (planner rec) | WP1 Direct → WP3 HITL → WP8 eval; WP4 weather = best "if time" | — |

Owner's directive: **urgent debug first, then WP0 → WP2**, then the above.

## The three problems are VERIFIED real (not hypothetical)
- **Color-harmony scorer is inverted.** `scoring/color_harmony.py:37` scores
  `avg_ratio / 10.0` — higher WCAG contrast = higher score. So navy+charcoal (elegant)
  scores low, tomato-red+emerald-green (clashing) scores high. T0.1 rewrites it. This
  is also the deliverable's Task-5 "found by eval → fixed → re-measured" story.
- **Per-slot cap keeps arbitrary items.** `pipeline/graph.py::wardrobe_retrieval` does
  `items[:_CANDIDATES_PER_SLOT]` with **no sort** → best-fitting items can be dropped
  before generation. T0.3 sorts first.
- **Principle II is violated.** The generator LLM picks item IDs
  (`pipeline/generator.py`). WP2 Engine brings the default path into compliance
  (deterministic enumerate + score; LLM only writes/ranks a pre-scored top-K).

## ⚠️ DO THIS FIRST on the scoring branch — snapshot the eval baseline
**DONE for 009** — `docs/eval-baselines/pre-009/` (pre) and `.../post-009/`
(post), compared in `docs/eval-baselines/pre-009/COMPARISON.md`.
T0.1/T0.3 (and later WP3) change scores. **The eval harness OVERWRITES
`backend/artifacts/eval_runs/*.jsonl`, and those files are gitignored** — so the
"before" numbers vanish the moment you re-run it. The whole "color-harmony improved,
re-measured" narrative needs a preserved before-snapshot.
- **Step 0:** copy the current `backend/artifacts/eval_runs/` to a tracked location
  (e.g. `docs/eval-baselines/pre-009/`) and record the current harness numbers
  (advanced `retrieval_recall ≈ 0.94`, `owned_only 1.00` — captured this session).
  Only then start changing scorers. **For any future branch in this epic (010+),
  repeat this same pattern with the next prefix.**

## Reuse these primitives — do NOT re-implement (they're already merged)
- `pipeline/context_assembler.infer_formality(occasion)` — free-text → formality.
  T0.3's "ctx.formality **or inferred**" means this function.
- `pipeline/graph._is_valid_combination` / `_is_slot_complete` — the coherence guards.
  Keep exact semantics everywhere; the spec says move to `pipeline/validity.py` only
  if imports go circular (pure move, no edits).
- `categories.group_of` (now round-trips group names) / `is_core`.
- `scoring/score_outfits` and the `DIMENSION_SCORERS` registry (WP3 adds a 5th).
- `memory/store.get_checkpointer` (pooled) — don't revert to a single connection.

## Carry-forward gotchas (cost real time last session)
- **Qdrant:** `get_kb()` reconnects when `count == len(chunks)` (391); otherwise it
  re-embeds. Rebuild is now `force_recreate=True` + longer timeout/smaller batches
  (`WTW_QDRANT_TIMEOUT`, `WTW_QDRANT_BATCH_SIZE`). The free-tier cluster is slow/cold —
  a rebuild may need a retry. Normal startups just reconnect.
- **Eval harness is flaky** (network: Qdrant/Cohere/gateway) and makes ~24 LLM calls.
  `retrieval_recall` is the deterministic metric to compare; generation-side numbers
  drift run-to-run — don't call a regression from one run.
- **Tests hit the real Supabase DB** (rolled-back transaction fixture). Running the
  **entire** suite in one process hits DB connection contention → spurious ERRORs in
  later integration tests; they pass in isolation. Prefer running affected subsets.
- **Refinement integration tests are LLM-sampling flaky** — a different one fails each
  run. Not a regression signal.

## Constitution
- Additive only. **Amendment required** (WP8/global instructions): state that the
  default `engine` approach complies with Principle II, and `direct`/`grounded` are
  retained as evaluated comparison baselines, explicitly exempt. Do this via the
  speckit constitution flow — don't quietly violate.
- Run `/speckit.analyze` on each WP's spec/plan/tasks and hold the planner to the
  simplicity rule (it over-builds).

## Per-branch acceptance (condensed — full detail in the spec)
- **009 scoring-fixes: ✅ DONE, merged to `main`.** T0.1 new color
  tests pass (deleted `test_high_contrast_pair_scores_higher_than_low_contrast_pair`,
  as planned); `test_combine.py`, `test_eval_properties.py` green; T0.3 unit test
  (9th-item-only-exact survives the cap) passes; T0.4 `nearest_names` test
  (`#0d9488`→"teal") passes. Eval baseline snapshotted first, per the Step 0
  instruction above. See `docs/SDD-HANDOFF.md` Step 10 for full detail
  including two real spec-inconsistency fixes found during implementation.
- **010 engine (folds in 010 approach-plumbing + 011 engine, one branch per
  the scoping decision below): ✅ DONE (implemented, NOT merged — owner
  directive this session).** `approach` field on `SuggestRequest` (default
  `"grounded"` = today's behavior, not `"engine"` — the spec said default
  `engine`, but this session kept the opt-in scoping decision below, which
  supersedes that default for now; keeps `strategy`); appears in graph
  state, sticky across refinement turns; integration test posts
  `approach:"engine"` → 200, value in state; default path behavior
  unchanged (byte-for-byte, confirmed via the full 371-test suite).
  Enumeration counts verified on synthetic closets; full-body + outerwear
  crossing (additive, not replacing the bare skeleton); safety valve
  (slices already-sorted candidates, no re-sort — cheaper than the
  originally-planned re-sort); engine returns 3 outfits, every cite
  resolves (a deterministic filter added during `/speckit.analyze`, not
  just a prompt instruction); a seeded "perfect" combo ranks #1 (confirmed
  live against the real scorer). **Flag partially addressed, not fully
  closed**: a dedicated unit test confirms the >20,000-combo safety valve
  correctly narrows each slot to top-6 (functional correctness) — but this
  session did NOT load-test real wall-clock `score_outfits` latency at that
  scale against the live gateway; the live integration tests used a small
  (6-item) synthetic wardrobe, nowhere near the valve's ~1,500-combo
  narrowed ceiling. Still an open flag for whoever load-tests this for
  real. Full detail: `specs/010-engine/`, `CLAUDE.md` Current State.

## Planner's open flags for the owner (decide as you reach them)
- WP2 combinatorics/perf — the valve's narrowing logic is unit-tested
  (correctly slices to top-6/slot above 20k projected combos), but real
  wall-clock latency at that scale against the live gateway is still
  untested — load-test before fully trusting the 20k threshold in
  production.
- WP3 adds a 5th scorer → eval baseline must be re-run (SC-005 4→5).
- WP6 compare = 4× LLM cost + the most concurrency-bug-prone code; keep below the
  cut-line unless there's real time.
- WP4 weather is under-prioritized in the spec: weather is currently **dead** (the
  frontend sends only `occasion`, so `temp_band` is always None). Cheap, credible fix
  — pull it up if the rubric rewards context-awareness.

---

## Next up: WP2 Engine — focused execution plan

**Goal:** land the **Engine approach (WP2)** — the Principle-II-compliance milestone
and the highest-value item — as a self-contained, low-risk increment on top of the
merged 009 work.

### Two scoping decisions (already made — don't re-litigate)
1. **One branch `feature/010-engine`** that folds WP0's T0.5 plumbing into WP2
   (plumbing alone has no user value; engine needs it — merging them cuts
   branch/merge overhead). The spec's separate `010`/`011` split is consolidated here.
2. **Keep the current path as the DEFAULT; make `engine` OPT-IN** (`approach:"engine"`).
   The spec says default `engine`, but flipping the default changes the default
   suggestion path and triggers the full (flaky) eval no-regression gate. Opt-in keeps
   engine purely additive → **the eval gate isn't required for this merge**; the
   comparison lives in the writeup. Flip the default later, once it's proven.

### Steps (in order; rough effort in parens)
1. **(~20m) Plumbing.** Branch `feature/010-engine`. `SuggestRequest.approach` (Literal,
   **default = current behavior**, keep `strategy`), `GraphState.approach` persisted
   alongside `original_context`, conditional-edge skeleton, regen
   `frontend/lib/api-types.ts`. *Gate:* post `approach:"engine"` → 200, value in state.
2. **(~30m) Enumerator.** `pipeline/engine.py::enumerate_outfits` — skeletons
   top×bottom×footwear + full_body×footwear; outerwear crossing when
   `ctx.temp_band in {"freezing","cold"}`; >20k-combo safety valve → top-6/slot.
   **Reuse** `_is_valid_combination` + `_is_slot_complete` (import; move to
   `pipeline/validity.py` only if circular). *Gate:* unit — 3×2×2 counts, full-body,
   outerwear cases.
3. **(~30m) Graph path.** `gather_context → style_retrieval → wardrobe_retrieval →
   engine_enumerate_and_score → engine_write → verify_grounding → explain`.
   `engine_enumerate_and_score`: enumerate → `score_outfits` (existing) on all →
   top-K=6. `engine_write`: ONE LLM call, selection+writing only (ordered pick of 3
   indices + rationale citing rule_ids, structured output); **reject any out-of-range
   index → deterministic fallback to top-3 by rank_score**.
4. **(~20m) Verify.** Integration test: engine returns 3 outfits, all items owned,
   every cite resolves (`eval/properties`); a seeded "perfect" combo ranks #1.
   *Gate:* tests green.
5. **(~15m) Land.** Affected unit + integration green, `ruff`, commit per logical unit,
   `--no-ff` merge to main.

### Fallback (risk management)
If the engine path proves harder than expected — graph routing or `engine_write`
structured-output not cooperating — **fall back to WP1 Direct** rather than leaving a
half-finished branch: new `pipeline/direct.py`, one LLM call, prompt = context + **full
closet** via `_format_items` (import from `generator.py`) + "3 complete outfits, ids
only"; apply `_is_slot_complete` + `_is_valid_combination`; wrap as `ScoredOutfit` with
a single `DimensionScore(dimension="direct", value=0.5, ...)`. That still ships a clean,
distinct second approach. Either way, don't merge a branch that isn't green.

### Writeup follow-through
- Engine (or Direct) as a distinct, evaluated approach vs. the current grounded path.
- The 009 color-harmony closed-loop story (numbers in
  `docs/eval-baselines/pre-009/COMPARISON.md`).
- Principle-II: engine complies (deterministic selection); document the design even if
  only Direct shipped. Constitution amendment noted as follow-up.
