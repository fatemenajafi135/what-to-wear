# Grounded vs Engine approach — eval comparison (Feature 010, WP2)

Full golden set (24 cases), `--strategies advanced` (retrieval strategy held
constant), run back-to-back on `feature/010-engine` via the harness
extension this feature adds (`eval/harness.py --approach {grounded,engine}`).
Artifacts: `advanced-grounded.jsonl` / `advanced-engine.jsonl` in this
directory (copies of `backend/artifacts/eval_runs/{advanced,advanced-engine}.jsonl`,
gitignored at the source). Unlike the pre-009/post-009 comparison, this is
**not** a before/after of the same code path — `grounded` is the existing,
unmodified default path; `engine` is the new opt-in path. Both were measured
at the same point in time, same closet, same golden set.

## Headline numbers

| metric | grounded | engine | delta |
|---|---:|---:|---|
| retrieval_recall | 0.94 | 0.94 | identical (retrieval is upstream of the approach split — expected, confirms no interference) |
| owned_only | 1.00 | 1.00 | identical — grounding guarantee holds on both paths |
| cites_grounded | 1.00 | 1.00 | identical — zero hallucinated citations reach the caller on either path |
| every_choice_cites | 1.00 | 0.79 | **see "Not a citation-quality regression" below** |
| weather_appropriate | 0.83 | 0.92 | **engine better** |
| occasion_fit | 1.00 | 1.00 | identical |
| respects_exclusions | 1.00 | 0.96 | engine slightly lower (1/24 case) |
| outfit_count_in_range | 0.92 | 0.79 | **see "Not a citation-quality regression" below** — same root cause |
| all_have_four_scores | 1.00 | 1.00 | identical |
| ranked_descending | 1.00 | 0.92 | **see "A real, spec'd design tension" below** |
| top_rank_score (mean) | 782.74 | 798.65 | **engine higher** — engine's picks score better on the same deterministic scorer it optimizes over |

## Not a citation-quality regression — it's the fallback, working correctly

`every_choice_cites` and `outfit_count_in_range` both "fail" on the exact
same 5/24 cases (`g01`, `g10`, `g11`, `g17`, `g24`), every one of which
returned fewer than 3 outfits (1 or 2). Traced to source: in every one of
these 5 cases, the enumerator's shortlist had fewer than 3 valid combos to
offer (a sparse-candidate scenario for that golden case's context), so
`engine_write`'s validation correctly rejects any LLM attempt at picking 3
and falls back to the deterministic top-N-by-`rank_score` path — whose
rationale is deliberately `cites=[]` (confirmed directly in the artifact,
e.g. `g01`: `"Selected by deterministic ranking (top dimension:
neutral-anchored (L1-color-neutral-anchor))."  [cites: ]`). This is FR-006/
FR-007 working exactly as designed: the fallback never fabricates a
citation to satisfy a check. `every_choice_cites`/`outfit_count_in_range`
as harness metrics don't have a way to distinguish "no citation because
nothing was retrieved to honestly cite" from "no citation because the model
was lazy" — both read as a bare failure. Net: **not a hallucination problem,
not a hidden bug** — it's a metric blind spot the harness inherited by
being written before this feature's fallback mode existed. Worth a
follow-up: teach `every_choice_cites`/`outfit_count_in_range` (or a new
harness field) to recognize a fallback-produced outfit as a distinct,
intentional case rather than a bare failure.

## A real, spec'd design tension — worth the owner's input for the constitution amendment

`ranked_descending` fails on 2/24 cases (`g15`, `g20`), both on the happy
path (3 outfits returned, no fallback). Traced to source: `engine_write`
lets the LLM choose the **order** of its 3 picks from the shortlist
(`docs/claude-code-implementation-spec.md` WP2: "output = ordered pick of 3
combo indices"; this feature's own FR-005: "choosing an ordered subset...
and writing a rationale") — and the LLM's presentation order doesn't always
match strict descending `rank_score` order among those 3 already-vetted
outfits. This is a genuine, measured consequence of a deliberate design
choice, not a bug: Principle II's literal text is about *selection*
("item selection is the output of deterministic pruning, combination, and
scoring code"), and every item in every returned outfit here is still 100%
deterministically selected — but `pipeline/graph.py`'s own module docstring
separately claims "the LLM never ranks (constitution Principle II)," which
this data shows isn't strictly true for the engine path's final 3-item
ordering. Flagging this explicitly rather than quietly resolving it either
way: the planned constitution amendment (recording the engine approach's
Principle II compliance, still open per `docs/ai-v2-session-handoff.md`)
should either (a) note that ordering-among-an-already-safe-shortlist is
outside Principle II's scope, or (b) if a stricter reading is wanted, change
`engine_write` to always sort the LLM's picks back into `rank_score` order
before returning — a small, well-contained fix if the answer is "no, it
should never diverge." Not resolved unilaterally here since the source spec
explicitly asked for LLM-ordered output.

## Genuine positive signals

- **weather_appropriate 0.92 vs 0.83**: deterministic weather-fitness
  scoring directly shapes which combos even reach the shortlist, rather
  than relying on the LLM to reason about warmth while also inventing the
  combination — a real, measurable benefit of the deterministic-selection
  design, not just a compliance nicety.
- **top_rank_score 798.65 vs 782.74**: engine's final picks score higher on
  average on the exact same deterministic scorer both paths share —
  expected, since engine explicitly ranks and selects from the top of that
  scorer's output, while grounded's LLM-assembled combos are scored only
  after the fact.

## What's unaffected (the core safety guarantees)

`retrieval_recall`, `owned_only`, and `cites_grounded` are identical or
perfect on both paths — the three metrics that most directly matter for
constitution Principles III (style KB gates retrieval) and IV (grounded
output only) show zero difference introduced by this feature, on either the
existing path (untouched, as expected) or the new one (verified, not just
asserted).
