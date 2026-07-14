"""RAGAS retrieval-quality scoring on the run artifacts.

Metrics (vibrantlabs fork collections API, async .ascore().value):
- ContextRecall      — did retrieval surface the reference context?
- Faithfulness       — is the answer grounded in the retrieved context?
- ContextEntityRecall— entity coverage of retrieval vs reference
- NoiseSensitivity   — sensitivity to irrelevant retrieved chunks

Run (in the evals venv):  uv run python score_ragas.py
Prints a per-strategy table so baseline vs advanced retrieval quality is visible.
"""

from __future__ import annotations

import asyncio

import pandas as pd

from common import discover_strategies, load_runs, ragas_judge_llm


async def _score_rows(rows: list[dict], judge) -> list[dict]:
    from ragas.metrics.collections import (
        ContextEntityRecall,
        ContextRecall,
        Faithfulness,
        NoiseSensitivity,
    )

    cr = ContextRecall(llm=judge)
    fa = Faithfulness(llm=judge)
    ce = ContextEntityRecall(llm=judge)
    ns = NoiseSensitivity(llm=judge, mode="relevant")

    out = []
    for r in rows:
        rec = {"case_id": r["case_id"]}
        ui, rc, ref, resp = (
            r["user_input"], r["retrieved_contexts"], r["reference"], r["response"],
        )
        async def _safe(coro):
            try:
                return (await coro).value
            except Exception as exc:  # noqa: BLE001
                print(f"  [warn] metric failed for {r['case_id']}: {exc}")
                return None

        rec["context_recall"] = await _safe(cr.ascore(user_input=ui, retrieved_contexts=rc, reference=ref))
        rec["faithfulness"] = await _safe(fa.ascore(user_input=ui, response=resp, retrieved_contexts=rc))
        rec["context_entity_recall"] = await _safe(ce.ascore(reference=ref, retrieved_contexts=rc))
        rec["noise_sensitivity"] = await _safe(
            ns.ascore(user_input=ui, response=resp, reference=ref, retrieved_contexts=rc)
        )
        out.append(rec)
    return out


def main() -> None:
    strategies = discover_strategies()
    if not strategies:
        print("No run artifacts. Run `python -m whattowear.eval.harness` in the main project first.")
        return
    judge = ragas_judge_llm()
    summary = {}
    for strat in strategies:
        print(f"\nScoring strategy: {strat}")
        rows = load_runs(strat)
        scored = asyncio.run(_score_rows(rows, judge))
        df = pd.DataFrame(scored)
        df.to_csv(f"ragas_scores_{strat}.csv", index=False)
        summary[strat] = df.drop(columns=["case_id"]).mean(numeric_only=True)

    table = pd.DataFrame(summary)
    print("\n=== RAGAS retrieval metrics (mean, higher is better except noise_sensitivity) ===")
    print(table.round(3).to_string())
    table.to_csv("ragas_summary.csv")


if __name__ == "__main__":
    main()
