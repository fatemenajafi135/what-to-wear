"""Eval harness (core, needs the gateway).

Runs the pipeline over the golden set for each strategy, computes:
- **verifiable checks** (owned-only, cites-grounded, every-choice-cites, and the
  outfit-property checks), and
- **retrieval recall** (relevant rule_ids ∩ retrieved) — the crisp retrieval
  metric that shows baseline < hybrid < advanced.

It writes per-strategy JSONL run artifacts (user_input / reference /
reference_contexts / response / retrieved_contexts + checks) that the isolated
`evals/` project scores with RAGAS + LLM-judge, and prints the comparison table.
"""

from __future__ import annotations

import json
from collections import defaultdict

from ..crud import EVAL_BASELINE_USER_ID
from ..ingest.loaders import REPO_ROOT
from ..kb import get_kb
from ..pipeline import cite
from ..pipeline.run import run_pipeline
from .golden_set import GoldenCase, load_cases
from .properties import check_outfit

ARTIFACTS_DIR = REPO_ROOT / "artifacts" / "eval_runs"
STRATEGIES = ["baseline", "hybrid", "advanced"]


def _user_input(case: GoldenCase) -> str:
    wx = f" when it is {case.temp_c}C" if case.temp_c is not None else ""
    mood = f"{case.mood} " if case.mood else ""
    return f"What should I wear for a {mood}{case.occasion}{wx}?"


def _rule_text_map() -> dict[str, str]:
    return {c.metadata["rule_id"]: c.page_content for c in get_kb().chunks}


def run_case(case: GoldenCase, strategy: str, rule_text: dict[str, str]) -> dict:
    run = run_pipeline(
        case.occasion,
        mood=case.mood,
        formality=case.formality,
        temp_c=case.temp_c,
        strategy=strategy,
        user_id=str(EVAL_BASELINE_USER_ID),
    )
    wardrobe = {it.id: it for it in run.ctx.wardrobe}
    retrieved_ids = run.retrieval.rule_ids()
    gen = run.generation

    # retrieval recall (crisp)
    relevant = set(case.relevant_rule_ids)
    hit = len(relevant & set(retrieved_ids)) / len(relevant) if relevant else 1.0

    # verifiable grounding checks (from cite)
    owned_ok, hallucinated = cite.owned_only(gen, set(wardrobe))
    cites_ok, bad_cites = cite.all_cites_grounded(gen, set(retrieved_ids))
    every_cites = cite.every_choice_cites(gen)

    # outfit-property checks on the first outfit
    first = gen.outfits[0].items if gen.outfits else []
    props = check_outfit(first, wardrobe, case.expected)

    return {
        "case_id": case.id,
        "strategy": strategy,
        "user_input": _user_input(case),
        "reference": case.reference,
        "reference_contexts": [rule_text[r] for r in case.relevant_rule_ids if r in rule_text],
        "response": cite.render_text(run.result),
        "retrieved_contexts": [d.page_content for d in run.retrieval.all()],
        "retrieval_recall": hit,
        "checks": {
            "owned_only": owned_ok,
            "cites_grounded": cites_ok,
            "every_choice_cites": every_cites,
            **props,
        },
        "hallucinated_items": hallucinated,
        "ungrounded_cites": bad_cites,
    }


def run_strategy(cases: list[GoldenCase], strategy: str, rule_text: dict[str, str]) -> list[dict]:
    rows = []
    for case in cases:
        try:
            rows.append(run_case(case, strategy, rule_text))
        except Exception as exc:  # noqa: BLE001
            print(f"  [error] {case.id}/{strategy}: {exc}")
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    out = ARTIFACTS_DIR / f"{strategy}.jsonl"
    with open(out, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")
    print(f"  wrote {len(rows)} rows -> {out}")
    return rows


def summarize(rows_by_strategy: dict[str, list[dict]]) -> None:
    check_keys = [
        "retrieval_recall",
        "owned_only",
        "cites_grounded",
        "every_choice_cites",
        "weather_appropriate",
        "occasion_fit",
        "respects_exclusions",
    ]
    print("\n=== Baseline vs advanced (verifiable metrics, mean over golden set) ===")
    header = f"{'metric':<22}" + "".join(f"{s:>12}" for s in rows_by_strategy)
    print(header)
    print("-" * len(header))
    for key in check_keys:
        line = f"{key:<22}"
        for strat, rows in rows_by_strategy.items():
            if not rows:
                line += f"{'-':>12}"
                continue
            if key == "retrieval_recall":
                val = sum(r["retrieval_recall"] for r in rows) / len(rows)
            else:
                val = sum(1 for r in rows if r["checks"].get(key)) / len(rows)
            line += f"{val:>12.2f}"
        print(line)


def main(strategies: list[str] | None = None, limit: int | None = None) -> None:
    strategies = strategies or STRATEGIES
    cases = load_cases()
    if limit:
        cases = cases[:limit]
    rule_text = _rule_text_map()
    rows_by_strategy: dict[str, list[dict]] = defaultdict(list)
    for strat in strategies:
        print(f"\nRunning strategy: {strat} ({len(cases)} cases)")
        rows_by_strategy[strat] = run_strategy(cases, strat, rule_text)
    summarize(rows_by_strategy)


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--strategies", nargs="*", default=STRATEGIES)
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()
    main(strategies=args.strategies, limit=args.limit)
