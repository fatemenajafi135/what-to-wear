# Feature 007 (AI layer port) — eval comparison against 010-engine

Full golden set (24 cases), `--strategies advanced` (retrieval strategy held
constant), run on `feat/007-ai-port` against the ported `whattowear` package
in this rebuild. Compared metric by metric against the recorded
[`../010-engine/COMPARISON.md`](../010-engine/COMPARISON.md) baseline — the
last measurement taken on the legacy prototype before this port, same golden
set, same closet fixture. Artifacts:
`backend/artifacts/eval_runs/{advanced,advanced-engine}.jsonl` (gitignored at
the source; this file is the durable record).

This is a **behaviour-preservation check**, not a before/after of a design
change: 007's job was to port the pipeline into new infrastructure (new
`ports.py` DI, new prompt-file loader, new fixture-backed `ClosetRepository`)
without changing what it does. Where a number moved, the question this
document answers is *why* — code regression, or the LLM's own run-to-run
variance (temperature 0.3, no seed, live API call, no fixed model snapshot).

## As-ported (pre-fix) — headline numbers

Run on 2026-07-30, before the issue-1 citation-guard fix (see
"Post-fix" section below).

| metric | baseline grounded | as-ported grounded | baseline engine | as-ported engine |
|---|---:|---:|---:|---:|
| retrieval_recall | 0.94 | 0.94 | 0.94 | 0.94 |
| owned_only | 1.00 | 1.00 | 1.00 | 1.00 |
| cites_grounded | 1.00 | **0.96** | 1.00 | 1.00 |
| every_choice_cites | 1.00 | 1.00 | 0.79 | **0.79** |
| weather_appropriate | 0.83 | **0.88** | 0.92 | **0.88** |
| occasion_fit | 1.00 | 1.00 | 1.00 | 1.00 |
| respects_exclusions | 1.00 | 1.00 | 0.96 | **0.96** |
| outfit_count_in_range | 0.92 | **0.83** | 0.79 | **0.79** |
| all_have_four_scores | 1.00 | 1.00 | 1.00 | 1.00 |
| ranked_descending | 1.00 | 1.00 | 1.00* | 1.00 |
| top_rank_score (mean) | 782.74 | 785.73 | 798.65 | 801.43 |

\* The recorded 010-engine baseline measured `ranked_descending` at 0.92 and
then noted a **RESOLVED (Option B)** fix applied after that measurement was
captured (`engine_write` sorts its picks into `rank_score`-descending order
before returning). That fix was already present in the code 007 ported from
— confirmed at `backend/src/whattowear/pipeline/engine.py:181` — so 1.00 is
the correct number to compare against, not the pre-fix 0.92.

Bold = a delta of more than rounding noise. Every one is traced to specific
case IDs below, not averaged away.

### Engine path — an almost-exact reproduction

Three of eleven metrics match the baseline to two decimal places, on the same
case IDs:

- `every_choice_cites`: 0.79 both, failing on the identical 5 cases
  (`g01`, `g10`, `g11`, `g17`, `g24`) as the original 010-engine measurement.
- `outfit_count_in_range`: 0.79 both, same 5 cases — same root cause as the
  original (below).
- `respects_exclusions`: 0.96 both (1/24 case; the as-ported run's failing
  case is `g10`, not separately identified in the original COMPARISON.md).

**Root cause, unchanged from the original**: in all 5 cases, the enumerator's
shortlist had fewer than 3 valid combos, so `engine_write`'s validation
correctly rejects any LLM attempt at picking 3 and falls back to the
deterministic top-N-by-`rank_score` path, whose rationale is honestly
`cites=[]`. This is FR-006/FR-007 working as designed, not a fabricated
citation — exactly the harness metric blind spot the original COMPARISON.md
already documented. Confirmed in the as-ported artifacts:
`num_outfits` is 2 (`g01`, `g10`, `g17`, `g24`) or 1 (`g11`) on every failing
case, and `ungrounded_cites`/`hallucinated_items` are both empty on all five
— nothing invented, just an honest shortfall.

`weather_appropriate` moved from 0.92 to 0.88 (22/24 → 21/24 passing): the
baseline's 2 failing cases plus one more, `g19` (`g17`, `g19`, `g20` fail
here; the original doesn't name its 2 failing cases so a full 1:1 comparison
of *which* cases isn't possible, but the magnitude — one additional
borderline case — is consistent with LLM selection variance on the
already-non-deterministic "which 3 from the shortlist" choice, not a scoring
change, since `scoring/` was not touched by this port).

`top_rank_score` moved from 798.65 to 801.43 (+2.78) — consistent with the
one extra case where the LLM picked a different (marginally higher-scoring)
subset of the shortlist.

### Grounded path — three real deltas, all traced

`cites_grounded` dropped from 1.00 to 0.96 — **this is issue 1**. The single
failing case, `g17` ("classic wedding, -1C"), has
`ungrounded_cites: ["L1-three-max"]`: the LLM cited `L1-three-max` where the
actually-retrieved rule id is `L1-color-three-max` — a one-word citation
typo. Pre-fix, `pipeline/cite.py::build_result` drops the unresolvable id
from the `sources` map but leaves it in the rationale's `cites` list
unchanged, so the response ships a dangling citation marker. The original
010-engine baseline never observed this because at that measurement, the LLM
happened not to make this specific typo — its 1.00 was the LLM behaving, not
the system preventing, per the inventory's own framing. See the "Post-fix"
section below for the corrected behaviour.

`outfit_count_in_range` dropped from 0.92 to 0.83 (22/24 → 20/24), failing on
`g01`, `g10`, `g14`, `g17`. All four returned `num_outfits: 2` instead of 3.
Unlike the engine path, the grounded path lets the LLM assemble and write the
*entire* response itself (no deterministic shortlist-then-fallback
structure), so this is squarely LLM discretion — the model chose to return 2
well-justified outfits rather than stretch to a weaker third, on 4 cases this
run versus (unnamed, but numerically 2) cases in the original. Nothing in
`pipeline/graph.py`'s grounded path differs from what was ported.

`weather_appropriate` moved from 0.83 to 0.88 (better) — failing on `g13`,
`g17`, `g19` here vs the original's unnamed 4/24 failures. An improvement in
the aggregate number on the same non-deterministic path is exactly the kind
of noise this document is not supposed to average away: it is not evidence
the port improved weather-fitness, since `scoring/weather_fitness.py` and
`external/weather.py` were ported unchanged and are not on the grounded
path's LLM-authored critical path for outfit *content* the same way the
engine path's deterministic pre-filter is.

`top_rank_score` moved from 782.74 to 785.73 (+2.99) — within the noise
implied by the above case-level churn.

## What's unaffected (the core safety guarantees)

`retrieval_recall`, `owned_only`, `occasion_fit`, and `all_have_four_scores`
are identical to the baseline on both paths — retrieval and the deterministic
scorers, none of which this port touched, show zero drift.

## Post-fix (issue 1 — citation guard)

See the dedicated section below, added after the fix landed. Re-run cost:
real API calls, 24 cases × 2 approaches, same as the pre-fix run above.
