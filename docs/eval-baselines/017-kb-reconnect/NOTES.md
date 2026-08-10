Run 2026-08-11, on `main` at `843f0d0`.

Both directories are the same 24-case golden set, same three strategies
(baseline/hybrid/advanced), same `--approach grounded`, same Qdrant collection
(`whattowear_kb`, cloud cluster), same closet fixture, run back-to-back within
the same session — only `WTW_KB_MODE` differs between them.

```
WTW_KB_MODE=corpus    uv run python -m whattowear.eval.harness \
    --strategies baseline hybrid advanced --approach grounded

WTW_KB_MODE=reconnect uv run python -m whattowear.eval.harness \
    --strategies baseline hybrid advanced --approach grounded
```

`--judge` not used (off by default) — this run is about `retrieval_recall`, which
the judge score doesn't inform, and skipping it keeps the run cheap.

`corpus/` is the control: the original, unmodified `get_kb()` path (reads
`CORPUS_LOCAL_DIR`, builds or reconnects with the pre-017 freshness check).
`reconnect/` exercises the new path added in feature 017 (§55/§59): never reads
the corpus, rebuilds the chunk list from the Qdrant collection's own stored
payloads.

See `COMPARISON.md` for the analysis. Short version: `retrieval_recall` is
byte-identical between the two, which is the whole point — it's the one
metric that depends purely on KB content, and it says the two paths surface
the same content.
