# Pre-009 vs post-009 comparison

Eval no-regression gate for `feature/009-scoring-fixes` (T019-T020). Baseline
snapshot: `docs/eval-baselines/pre-009/`. Post-implementation snapshot:
`docs/eval-baselines/post-009/`. Both are copies of
`backend/artifacts/eval_runs/*.jsonl` (gitignored at the source, tracked here
for the record — see `docs/eval-baselines/pre-009/NOTES.md`).

## Deterministic metrics (constitution-required no-regression bar)

- **`retrieval_recall`**: byte-identical on every one of the 23 golden cases
  shared between both runs, across all three strategies (baseline, hybrid,
  advanced). The one new case in the post-009 `advanced` run (`g17`) simply
  wasn't present in the pre-009 run — a known harness-flakiness gap, not a
  behavior change; retrieval itself is untouched by this feature.
- **`owned_only`**: 1.00 in both runs, all strategies, zero diffs per case —
  the grounding guarantee is unaffected.
- **`hallucinated_items`**: 0 rows in both runs, all strategies.

This satisfies spec.md SC-005 and the constitution's Principle I no-regression
requirement — this feature touches scoring/ranking/pre-generation-narrowing
only, never retrieval itself, and the numbers confirm it.

## Generation-dependent metrics (expected to drift run-to-run — not a
regression signal per `CLAUDE.md`'s documented eval-harness gotcha)

| metric | baseline (pre→post) | hybrid (pre→post) | advanced (pre→post) |
|---|---|---|---|
| cites_grounded | 1.00→1.00 | 0.917→0.96 | 1.00→0.92 |
| weather_appropriate | 0.875→0.92 | 0.833→0.88 | 0.870→0.88 |
| outfit_count_in_range | 0.708→0.83 | 0.917→0.88 | 0.957→0.88 |
| respects_exclusions | 0.958→1.00 | 0.958→1.00 | 0.957→1.00 |

Mixed movement in both directions across a single run each, consistent with
LLM-sampling noise on generation-dependent checks — none of this feature's
changes touch citation logic, the generation prompt, or grounding
verification. `weather_appropriate`'s across-the-board improvement is
directionally consistent with T012 (best-fitting items no longer dropped
before generation sees them) but isn't claimed as proven by a single run.

## Color-harmony fix, concrete before/after (Task 5 deliverable evidence)

Old algorithm (mean pairwise WCAG contrast, inverted):
- navy `#1b2a4a` + charcoal `#36454f` (tonal, elegant): **low** score
  (low contrast ratio between two dark, similar-lightness colors)
- tomato red `#ff6347` + emerald green `#046307` (clashing): **high** score
  (high contrast ratio between a light warm hue and a dark cool hue)

New algorithm (`scoring/color_harmony.py`, this feature), run directly:

```
navy+charcoal (tonal):   value=0.9  reason="neutral-anchored (L1-color-neutral-anchor)"
tomato+emerald (clash):  value=0.4  reason="a hue pairing that is neither analogous nor
                                              genuinely complementary — no organizing
                                              relationship with some (not extreme) value contrast"
```

The ranking is now correct: the tonal, elegant pairing scores more than
double the clashing one, with a human-readable reason citing the fired
color-theory rule — this is the "found by code review → fixed → re-measured"
story for the deliverable's Task 5.
