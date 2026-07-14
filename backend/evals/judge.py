"""End-to-end LLM-as-judge rubric on the run artifacts (openevals).

The crisp, verifiable checks (owned-only, cites-grounded, weather, occasion floor)
are already computed by the main harness and stored in each row's `checks`. This
adds the FUZZY rubric scores an LLM is better at:
- groundedness   (openevals RAG_GROUNDEDNESS_PROMPT)
- answer quality (openevals CORRECTNESS_PROMPT vs the reference)
- stylistic coherence + occasion nuance (custom rubric)

Run (in the evals venv):  uv run python judge.py
"""

from __future__ import annotations

import pandas as pd

from common import discover_strategies, load_runs, openevals_judge_llm

COHERENCE_PROMPT = """You are a fashion-styling judge. Given a styling REQUEST and a
recommended OUTFIT with rationale, rate how stylistically coherent and appropriate
the outfit is for the occasion, mood, and weather described.

Score 0.0 to 1.0 where:
- 1.0 = coherent, occasion-appropriate, well-reasoned, colors/proportions sensible
- 0.5 = acceptable but with a notable weakness
- 0.0 = incoherent or inappropriate for the stated context

<request>{inputs}</request>
<outfit>{outputs}</outfit>

Return only the score and a one-sentence justification."""


def _build_judges():
    from openevals.llm import create_llm_as_judge
    from openevals.prompts import CORRECTNESS_PROMPT, RAG_GROUNDEDNESS_PROMPT

    judge = openevals_judge_llm()
    return {
        "groundedness": create_llm_as_judge(
            prompt=RAG_GROUNDEDNESS_PROMPT, judge=judge,
            feedback_key="groundedness", continuous=True,
        ),
        "correctness": create_llm_as_judge(
            prompt=CORRECTNESS_PROMPT, judge=judge,
            feedback_key="correctness", continuous=True,
        ),
        "coherence": create_llm_as_judge(
            prompt=COHERENCE_PROMPT, judge=judge,
            feedback_key="coherence", continuous=True,
        ),
    }


def _score_row(judges: dict, r: dict) -> dict:
    context = "\n".join(r["retrieved_contexts"])
    rec = {"case_id": r["case_id"]}
    for name, judge in judges.items():
        try:
            if name == "groundedness":
                res = judge(inputs=r["user_input"], outputs=r["response"], context=context)
            elif name == "correctness":
                res = judge(inputs=r["user_input"], outputs=r["response"], reference_outputs=r["reference"])
            else:  # coherence
                res = judge(inputs=r["user_input"], outputs=r["response"])
            rec[name] = res["score"]
        except Exception as exc:  # noqa: BLE001
            print(f"  [warn] {name} judge failed for {r['case_id']}: {exc}")
            rec[name] = None
    return rec


def main() -> None:
    strategies = discover_strategies()
    if not strategies:
        print("No run artifacts. Run the main harness first.")
        return
    judges = _build_judges()
    summary = {}
    for strat in strategies:
        print(f"\nJudging strategy: {strat}")
        rows = load_runs(strat)
        scored = [_score_row(judges, r) for r in rows]
        df = pd.DataFrame(scored)
        df.to_csv(f"judge_scores_{strat}.csv", index=False)
        # combine with the crisp checks already in the artifacts
        checks = pd.DataFrame([{**{"case_id": r["case_id"]}, **r["checks"]} for r in rows])
        summary[strat] = {
            **df.drop(columns=["case_id"]).mean(numeric_only=True).to_dict(),
            **checks.drop(columns=["case_id"]).mean(numeric_only=True).to_dict(),
        }

    table = pd.DataFrame(summary)
    print("\n=== End-to-end rubric + verifiable checks (mean over golden set) ===")
    print(table.round(3).to_string())
    table.to_csv("judge_summary.csv")


if __name__ == "__main__":
    main()
