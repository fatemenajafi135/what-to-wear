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

`fix/007-citation-guard` adds `pipeline/grounding.py::filter_ungrounded_cites()`
— dropping any rule_id an LLM cites that wasn't actually retrieved, at the
two points a `GenOutput` is produced (`graph.py::generate_outfits` for the
grounded path; `engine.py::engine_write`, which already did this inline
pre-fix, refactored onto the same shared helper). Re-ran the full 24-case
golden set on both approaches after the fix, same day, same model
(`gpt-5.4-mini` via the gateway). Re-run cost: 2 × 24 live LLM calls (real
API spend, no mocking — this is the actual acceptance gate).

| metric | baseline (010-engine) | as-ported pre-fix | as-ported post-fix |
|---|---:|---:|---:|
| | grounded / engine | grounded / engine | grounded / engine |
| retrieval_recall | 0.94 / 0.94 | 0.94 / 0.94 | 0.94 / 0.94 |
| owned_only | 1.00 / 1.00 | 1.00 / 1.00 | 1.00 / 1.00 |
| cites_grounded | 1.00 / 1.00 | 0.96 / 1.00 | **1.00 / 1.00** |
| every_choice_cites | 1.00 / 0.79 | 1.00 / 0.79 | 1.00 / 0.79 |
| weather_appropriate | 0.83 / 0.92 | 0.88 / 0.88 | 0.88 / 0.88 |
| occasion_fit | 1.00 / 1.00 | 1.00 / 1.00 | 1.00 / 1.00 |
| respects_exclusions | 1.00 / 0.96 | 1.00 / 0.96 | 1.00 / 0.96 |
| outfit_count_in_range | 0.92 / 0.79 | 0.83 / 0.79 | 0.83 / 0.79 |
| all_have_four_scores | 1.00 / 1.00 | 1.00 / 1.00 | 1.00 / 1.00 |
| ranked_descending | 1.00 / 1.00 | 1.00 / 1.00 | 1.00 / 1.00 |
| top_rank_score (mean) | 782.74 / 798.65 | 785.73 / 801.43 | 790.59 / 801.43 |

### Which metric absorbed the signal, and why that's honest

`cites_grounded` is now **1.00 by construction** on the grounded path, not by
luck: `filter_ungrounded_cites` runs before `state["generated"]` is ever set,
and the harness's `cites_grounded` check
(`eval/harness.py` → `cite.all_cites_grounded(gen, ...)`) reads exactly that
object. It is now structurally impossible for an unresolvable rule_id to
reach that check — the same way `owned_only` has been 1.00 on both paths
throughout this whole document, for the same structural reason (a
deterministic guard runs before the object the check inspects is built).

The predicted destination for the signal was `every_choice_cites`: dropping
a citation from a rationale line that had only that one (bad) citation
leaves the line with an honestly empty `cites` list — which is exactly what
`every_choice_cites` (`all(r.cites for ... in rationale)`) is designed to
catch. That is the *correct* place for this signal to live: an empty-cites
line is a real, visible fact about the response (the caller can render "no
specific rule cited" instead of a dangling badge), where `cites_grounded`
pre-fix conflated "the LLM cited something bogus" with "everything's fine"
whenever the id-resolution silently succeeded downstream.

**What this specific re-run actually shows**: `every_choice_cites` stayed at
1.00/0.79 (grounded/engine) — identical to the pre-fix run, on the engine
path because it was already filtering (no behavior change there, confirmed:
same 5 failing case IDs — `g01`, `g10`, `g11`, `g17`, `g24` — as both the
pre-fix run and the original baseline), and on the grounded path because
*this specific post-fix run's LLM output didn't happen to reproduce a
citation hallucination* — a fresh, unseeded call to a temperature-0.3 model
is not guaranteed to repeat the exact mistake `g17` made in the pre-fix run.
Grepping the full post-fix run log (`grep "Dropping ungrounded"`) for both
approaches found **zero matches** — the guard's drop path did not execute in
this particular re-run, on either path. This is a legitimate, expected
outcome (the original 010-engine baseline's own grounded-path 1.00 was the
LLM behaving on that occasion too, per the inventory's framing this document
already cites) — but it does mean this re-run cannot *empirically*
demonstrate the every_choice_cites destination firing live. What it can and
does demonstrate: (1) `cites_grounded`'s 1.00 is now a structural guarantee,
independent of whether the LLM misbehaves on any given call, confirmed by
code inspection — `filter_ungrounded_cites` runs unconditionally before
`state["generated"]` is set on every path, verifiable at
`pipeline/graph.py::generate_outfits` and `pipeline/engine.py::engine_write`;
(2) a follow-up artifact-level check (every cited rule_id in every rendered
response resolves to an entry in that response's own `Sources:` list — the
literal "dangling badge" the issue described) found **zero dangling
citations** across all 24 post-fix grounded-path cases; (3) the drop path
and its logging are covered by a dedicated unit test
(`tests/unit/pipeline/test_grounding.py::TestFilterUngroundedCites`,
7 cases, including `test_dropped_citation_is_logged` and
`test_all_cites_ungrounded_leaves_honestly_empty_list`), which is the actual
proof the mechanism works — this eval re-run confirms it doesn't regress
anything, not that it fires on demand.

`outfit_count_in_range` (grounded) stayed at 0.83 but the *specific* failing
cases shifted from `g01`/`g10`/`g14`/`g17` (pre-fix) to `g01`/`g11`/`g17`/`g24`
(post-fix) — consistent with ordinary run-to-run LLM variance on which cases
get a 2- vs 3-outfit response, not a citation-guard side effect (the guard
only ever removes bad cites, never changes item selection or outfit count).
`top_rank_score` (grounded) moved from 785.73 to 790.59, again within the
noise implied by that case-level churn. Every other metric is unchanged
between pre-fix and post-fix runs, on both paths, exactly as expected: the
fix touches only citation lists, nothing that any other check inspects.
