# 010-engine eval baseline

Snapshot of `backend/artifacts/eval_runs/{advanced,advanced-engine}.jsonl`
taken on `feature/010-engine`, both runs on the same commit, same closet
(`EVAL_BASELINE_USER_ID`), same golden set (24 cases), `--strategies advanced`
(retrieval strategy held constant so the comparison isolates the selection
approach). Gitignored at the source (`backend/artifacts/eval_runs/`), so
this copy is the durable record — needed because `approach=engine` is a new
capability the eval harness didn't support running before this feature
(`eval/harness.py`'s `--approach` flag, added this feature).

Unlike `pre-009`/`post-009` (a before/after of the *same* code path after a
bug fix), this is a same-time comparison of *two different* selection
approaches — see `COMPARISON.md` for the full breakdown, including two
findings traced to their exact root cause (a harness-metric blind spot
around the deterministic fallback's intentionally-empty citations, and a
genuine, spec'd design tension around LLM-ordered final presentation) rather
than left as unexplained numbers.

`hallucinated_items` was 0 across both files. `owned_only` was 1.00 on both.
