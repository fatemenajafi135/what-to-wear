# Pre-009 eval baseline

Snapshot of `backend/artifacts/eval_runs/*.jsonl` taken on `main` at commit
`3f81fec`, before any `feature/009-scoring-fixes` changes (T0.1 color-harmony
rewrite, T0.2 default combine strategy, T0.3 sort-before-cap, T0.4 palette
additions). Gitignored in `backend/artifacts/`, so this copy is the only
durable "before" record — needed for the deliverable's "found by eval → fixed
→ re-measured" narrative (Task 5).

## Summary (24 golden cases, `advanced` missing g17 — flaky harness run, not a
regression; see CLAUDE.md eval-harness gotcha)

| strategy | n | avg retrieval_recall | owned_only | weather_appropriate | outfit_count_in_range | respects_exclusions | cites_grounded |
|---|---|---|---|---|---|---|---|
| baseline | 24 | 0.792 | 1.00 | 0.875 | 0.708 | 0.958 | 1.00 |
| hybrid   | 24 | 0.944 | 1.00 | 0.833 | 0.917 | 0.958 | 0.917 |
| advanced | 23 | 0.942 | 1.00 | 0.870 | 0.957 | 0.957 | 1.00 |

`retrieval_recall` is the deterministic metric (per CLAUDE.md); the rest
drift run-to-run from LLM sampling. `hallucinated_items` was 0 across all
three files.

These numbers, plus a fresh post-009 run, are the two data points for the
color-harmony bug story: `scoring/color_harmony.py` currently scores mean
pairwise WCAG contrast directly (higher contrast = higher score), which
rewards clashing complementary pairs and punishes tonal/analogous ones — a
correctness bug the golden-set checks above don't directly surface (none of
them assert on `color_harmony` score value), which is itself worth noting in
the deliverable: this bug was found by code review of the scorer logic
against real palette examples, not by an eval regression.
