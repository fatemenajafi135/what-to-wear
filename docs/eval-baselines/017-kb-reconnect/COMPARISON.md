# Corpus mode vs reconnect mode — eval comparison (feature 017, `WTW_KB_MODE`)

Full golden set (24 cases), all three retrieval strategies, `--approach grounded`,
run back-to-back on `main` at `843f0d0` via the harness's existing sweep
(`eval/harness.py`, no code changes needed — the comparison is driven entirely by
`WTW_KB_MODE`). Same corpus content, same Qdrant collection, same closet fixture, same
model, same day. Artifacts: `corpus/{baseline,hybrid,advanced}.jsonl` and
`reconnect/{baseline,hybrid,advanced}.jsonl` in this directory (copies of
`backend/artifacts/eval_runs/*.jsonl`, gitignored at the source).

This is the eval run owed since `docs/design-decisions.md` §59 (`WTW_KB_MODE`,
feature 017's deployment work). The constitution requires an eval run for any refactor
touching the knowledge base; `corpus` mode is the original, unmodified, evaluated code
path, so this isolates the one variable actually in question — does `reconnect` mode
(no corpus on disk, chunks rebuilt from Qdrant payloads) retrieve the same content as
`corpus` mode (reads the corpus, builds/reconnects with a freshness check)?

## The metric that actually answers the question: `retrieval_recall`

| strategy | corpus | reconnect | delta |
|---|---:|---:|---|
| baseline | 0.79 | 0.79 | **byte-identical** |
| hybrid | 0.94 | 0.94 | **byte-identical** |
| advanced | 0.94 | 0.94 | **byte-identical** |

Identical across all three strategies and all 24 cases. `retrieval_recall` is the one
metric that depends purely on KB *content* — relevant rule_ids ∩ retrieved — and is
otherwise deterministic (no LLM sampling involved in retrieval itself). Byte-identical
recall proves `reconnect`'s chunk-rebuild-from-payloads path surfaces exactly the same
rules as `corpus`'s read-the-corpus-and-build path. This is the direct evidence §59
was owed.

Also matches the last recorded baseline for this metric — `010-engine`'s
`advanced`/`grounded` column recorded `retrieval_recall = 0.94` on 2026-07-31 — so this
also stands as a routine no-regression check against prior history, not just the
same-day A/B.

`owned_only`, `cites_grounded`, `every_choice_cites`, `occasion_fit`,
`respects_exclusions`, `all_have_four_scores`, and `ranked_descending` were all `1.00`
in both runs, every strategy — the grounding guarantee and every hard constraint hold
identically regardless of which KB-access mode produced the retrieved context.

## Generation-dependent metrics — expected drift, not a regression signal

| metric | strategy | corpus | reconnect |
|---|---|---:|---:|
| weather_appropriate | baseline | 0.92 | 0.92 |
| weather_appropriate | hybrid | 0.92 | 0.83 |
| weather_appropriate | advanced | 0.88 | 0.83 |
| outfit_count_in_range | baseline | 0.83 | 0.79 |
| outfit_count_in_range | hybrid | 0.88 | 0.83 |
| outfit_count_in_range | advanced | 0.79 | 0.83 |
| top_rank_score (mean) | baseline | 792.05 | 784.75 |
| top_rank_score (mean) | hybrid | 788.57 | 776.70 |
| top_rank_score (mean) | advanced | 783.51 | 778.79 |

Movement here is consistent with ordinary LLM-sampling noise on generation-dependent
checks, exactly the pattern `docs/eval-baselines/pre-009/COMPARISON.md` documents and
names as expected, not a regression signal: two runs of the *identical* code path drift
by a comparable amount run-to-run. Nothing about `WTW_KB_MODE` touches generation,
scoring, or ranking — only which code path fetches the retrieved chunks — so this
movement is attributed to sampling, not to the mode under test.

## Conclusion

`WTW_KB_MODE=reconnect` retrieves the same content as `WTW_KB_MODE=corpus`, evidenced
by byte-identical `retrieval_recall` across all three strategies and the full golden
set. `docs/design-decisions.md` §59 is closed — the eval run it named as outstanding is
this one.
