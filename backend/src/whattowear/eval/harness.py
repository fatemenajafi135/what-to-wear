"""Eval harness (core, needs the gateway).

Runs the compiled graph (pipeline/graph.py) over the golden set for each
strategy — not the retired linear `pipeline.run.run_pipeline` (Feature 002
Phase 3, T032a: one entrypoint, not two to keep in sync). Computes:
- **verifiable checks** (owned-only, cites-grounded, every-choice-cites, and the
  outfit-property checks),
- **retrieval recall** (relevant rule_ids ∩ retrieved) — the crisp retrieval
  metric that shows baseline < hybrid < advanced, and
- **scoring/ranking checks** (SC-003 outfit count, SC-005 all-four-dimensions) —
  what actually measures the graph's `/suggest`-shaped output, not just
  asserts it.

It writes per-strategy JSONL run artifacts (user_input / reference /
reference_contexts / response / retrieved_contexts + checks) that the isolated
`evals/` project scores with RAGAS + LLM-judge, and prints the comparison table.
"""

from __future__ import annotations

import json
import uuid
from collections import defaultdict

from ..crud import EVAL_BASELINE_USER_ID
from ..ingest.loaders import REPO_ROOT
from ..kb import get_kb
from ..pipeline import cite
from ..pipeline.generator import GenOutput
from ..pipeline.graph import get_compiled_graph
from .golden_set import GoldenCase, load_cases
from .judge import format_outfit_for_judge, judge_outfit
from .properties import check_outfit

ARTIFACTS_DIR = REPO_ROOT / "artifacts" / "eval_runs"
STRATEGIES = ["baseline", "hybrid", "advanced"]

# SC-003: 3-5 complete outfits when the closet can support them.
_MIN_EXPECTED_OUTFITS = 3
_MAX_EXPECTED_OUTFITS = 5


def _user_input(case: GoldenCase) -> str:
    wx = f" when it is {case.temp_c}C" if case.temp_c is not None else ""
    mood = f"{case.mood} " if case.mood else ""
    return f"What should I wear for a {mood}{case.occasion}{wx}?"


def _rule_text_map() -> dict[str, str]:
    return {c.metadata["rule_id"]: c.page_content for c in get_kb().chunks}


def run_case(case: GoldenCase, strategy: str, rule_text: dict[str, str], judge: bool = False) -> dict:
    graph = get_compiled_graph()
    thread_id = str(uuid.uuid4())
    final_state = graph.invoke(
        {
            "occasion": case.occasion,
            "mood": case.mood,
            "formality": case.formality,
            "temp_c": case.temp_c,
            "strategy": strategy,
            "thread_id": thread_id,
            "user_id": str(EVAL_BASELINE_USER_ID),
        },
        config={"configurable": {"thread_id": thread_id}},
    )

    ctx = final_state["ctx"]
    retrieval = final_state["retrieval"]
    gen: GenOutput = final_state["generated"]
    scored = final_state["scored_outfits"]
    result = final_state["result"]

    wardrobe = {it.id: it for it in ctx.wardrobe}
    retrieved_ids = retrieval.rule_ids()

    # retrieval recall (crisp)
    relevant = set(case.relevant_rule_ids)
    hit = len(relevant & set(retrieved_ids)) / len(relevant) if relevant else 1.0

    # verifiable grounding checks (from cite)
    owned_ok, hallucinated = cite.owned_only(gen, set(wardrobe))
    cites_ok, bad_cites = cite.all_cites_grounded(gen, set(retrieved_ids))
    every_cites = cite.every_choice_cites(gen)

    # outfit-property checks on the top-ranked outfit
    top = scored[0].items if scored else []
    props = check_outfit(top, wardrobe, case.expected)

    # scoring/ranking checks (Phase 3) — SC-003, SC-005
    outfit_count_in_range = _MIN_EXPECTED_OUTFITS <= len(scored) <= _MAX_EXPECTED_OUTFITS
    all_have_four_scores = all(len(o.scores) == 4 for o in scored) if scored else True
    ranked_descending = [o.rank_score for o in scored] == sorted((o.rank_score for o in scored), reverse=True)

    # optional reported-only LLM judge score (Phase 4, T046, FR-010) — never
    # computed by default (an extra LLM call per case would slow/flake the
    # mandatory no-regression gate); opt in with --judge. Attached to the row
    # for reporting only, never fed back into rank_score/ordering above.
    judge_score = judge_outfit(_user_input(case), format_outfit_for_judge(scored[0])) if judge and scored else None

    return {
        "case_id": case.id,
        "strategy": strategy,
        "user_input": _user_input(case),
        "reference": case.reference,
        "reference_contexts": [rule_text[r] for r in case.relevant_rule_ids if r in rule_text],
        "response": cite.render_text(result),
        "retrieved_contexts": [d.page_content for d in retrieval.all()],
        "retrieval_recall": hit,
        "checks": {
            "owned_only": owned_ok,
            "cites_grounded": cites_ok,
            "every_choice_cites": every_cites,
            "outfit_count_in_range": outfit_count_in_range,
            "all_have_four_scores": all_have_four_scores,
            "ranked_descending": ranked_descending,
            **props,
        },
        "hallucinated_items": hallucinated,
        "ungrounded_cites": bad_cites,
        "num_outfits": len(scored),
        "top_rank_score": scored[0].rank_score if scored else None,
        "judge_score": judge_score,
    }


def run_strategy(cases: list[GoldenCase], strategy: str, rule_text: dict[str, str], judge: bool = False) -> list[dict]:
    rows = []
    for case in cases:
        try:
            rows.append(run_case(case, strategy, rule_text, judge=judge))
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
        "outfit_count_in_range",
        "all_have_four_scores",
        "ranked_descending",
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

    line = f"{'top_rank_score':<22}"
    for rows in rows_by_strategy.values():
        scored = [r["top_rank_score"] for r in rows if r["top_rank_score"] is not None]
        line += f"{sum(scored) / len(scored):>12.2f}" if scored else f"{'-':>12}"
    print(line)

    if any(r.get("judge_score") is not None for rows in rows_by_strategy.values() for r in rows):
        line = f"{'judge_score':<22}"
        for rows in rows_by_strategy.values():
            judged = [r["judge_score"] for r in rows if r["judge_score"] is not None]
            line += f"{sum(judged) / len(judged):>12.2f}" if judged else f"{'-':>12}"
        print(line)


def main(strategies: list[str] | None = None, limit: int | None = None, judge: bool = False) -> None:
    strategies = strategies or STRATEGIES
    cases = load_cases()
    if limit:
        cases = cases[:limit]
    rule_text = _rule_text_map()
    rows_by_strategy: dict[str, list[dict]] = defaultdict(list)
    for strat in strategies:
        print(f"\nRunning strategy: {strat} ({len(cases)} cases)")
        rows_by_strategy[strat] = run_strategy(cases, strat, rule_text, judge=judge)
    summarize(rows_by_strategy)


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--strategies", nargs="*", default=STRATEGIES)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument(
        "--judge",
        action="store_true",
        help="also compute the optional reported-only LLM judge score (FR-010) — one extra "
        "LLM call per case, off by default so it doesn't slow/flake the no-regression gate",
    )
    args = ap.parse_args()
    main(strategies=args.strategies, limit=args.limit, judge=args.judge)
