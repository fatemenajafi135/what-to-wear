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

## Status: `feature/009-scoring-fixes` implemented, not yet merged
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

**This branch's changes are uncommitted in the working tree** — confirm
with the owner before committing/merging. Next: `feature/010-approach-plumbing`
(T0.5) per the sequence below, once 009 is committed.

## Branch convention (owner's decision)
- **`feature/NNN-name`**, 3-digit, continuing from 008. One branch per WP; each ends
  with `cd backend && uv run pytest` green and its own acceptance criteria met.
- Do **not** rename already-merged branches (their names are baked into `main`'s
  merge commits — leave history alone). Convention applies going forward only.

## Planned sequence
| Order | Branch | Scope | Spec ref |
|-------|--------|-------|----------|
| 1 | `feature/009-scoring-fixes` | **Urgent debug**: color-harmony rewrite, combine default, sort-before-cap, palette | T0.1–T0.4 |
| 2 | `feature/010-approach-plumbing` | `approach` scaffolding (no behavior change) | T0.5 |
| 3 | `feature/011-engine` | Engine approach — Principle II compliance | WP2 |
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
- **009 scoring-fixes: ✅ DONE (implemented, not yet merged).** T0.1 new color
  tests pass (deleted `test_high_contrast_pair_scores_higher_than_low_contrast_pair`,
  as planned); `test_combine.py`, `test_eval_properties.py` green; T0.3 unit test
  (9th-item-only-exact survives the cap) passes; T0.4 `nearest_names` test
  (`#0d9488`→"teal") passes. Eval baseline snapshotted first, per the Step 0
  instruction above. See `docs/SDD-HANDOFF.md` Step 10 for full detail
  including two real spec-inconsistency fixes found during implementation.
- **010 approach-plumbing:** `approach` field on `SuggestRequest` (default `engine`,
  keep `strategy`); appears in graph state; integration test posts `approach:"engine"`
  → 200; no behavior change.
- **011 engine:** enumeration counts on a 3×2×2 closet; full-body + outerwear crossing;
  safety valve; engine returns 3 outfits, every cite resolves; a seeded "perfect"
  combo ranks #1; golden g01 passes all property checks. **Flag:** verify latency of
  `score_outfits` over all combos; the 20,000-combo valve is generous — consider
  top-6/slot (safe post-T0.3).

## Planner's open flags for the owner (decide as you reach them)
- WP2 combinatorics/perf — load-test before trusting the 20k valve.
- WP3 adds a 5th scorer → eval baseline must be re-run (SC-005 4→5).
- WP6 compare = 4× LLM cost + the most concurrency-bug-prone code; keep below the
  cut-line unless there's real time.
- WP4 weather is under-prioritized in the spec: weather is currently **dead** (the
  frontend sends only `occasion`, so `temp_band` is always None). Cheap, credible fix
  — pull it up if the rubric rewards context-awareness.
