"""Before/after evidence capture for the "warmer" refinement's warmth-floor
fix (Feature 007 Task C, spec.md FR-013/SC-005, research.md D9).

Drives the eval baseline user's real closet through the real compiled graph
(same fixture eval/harness.py and tests/integration/test_suggest_refinement.py
already use) — one request per OCCASION_FORMALITY entry, followed by a
"warmer" refinement turn on the same thread — and records how often the
refinement turn falls back to the previous result (FR-015) because the
tightened bounds left nothing.

This is a one-time diagnostic script, not a permanent module or a pytest
test (see research.md D9 for why): run once against the pre-fix code, once
against the post-fix code, and compare the two printed tables.

Needs the real gateway/DB/KB, like eval/harness.py — same documented
flakiness under transient network drops applies here.

Usage:
    uv run python scripts/warmth_floor_evidence.py --out artifacts/warmth_floor_before.json
    # ... apply the pipeline/graph.py fix ...
    uv run python scripts/warmth_floor_evidence.py --out artifacts/warmth_floor_after.json
"""

from __future__ import annotations

import argparse
import json
import uuid

from whattowear.crud import EVAL_BASELINE_USER_ID
from whattowear.pipeline.context_assembler import OCCASION_FORMALITY
from whattowear.pipeline.graph import get_compiled_graph

_FALLBACK_MARKER = "previous suggestions"


def _invoke(graph, occasion: str, thread_id: str, **kwargs) -> dict:
    return graph.invoke(
        {"occasion": occasion, "thread_id": thread_id, "user_id": str(EVAL_BASELINE_USER_ID), **kwargs},
        config={"configurable": {"thread_id": thread_id}},
    )


def run(strategy: str = "advanced") -> list[dict]:
    graph = get_compiled_graph()
    rows: list[dict] = []
    for occasion, formality in OCCASION_FORMALITY.items():
        thread_id = str(uuid.uuid4())
        try:
            _invoke(graph, occasion, thread_id, formality=formality, strategy=strategy)
            second = _invoke(graph, "warmer", thread_id, strategy=strategy)
        except Exception as exc:  # noqa: BLE001 - record and continue, same as harness.run_strategy
            rows.append({"occasion": occasion, "error": str(exc)})
            continue
        note = second.get("note") or ""
        rows.append({"occasion": occasion, "fell_back": _FALLBACK_MARKER in note, "note": note})
    return rows


def summarize(rows: list[dict], strategy: str) -> None:
    scored = [r for r in rows if "fell_back" in r]
    errored = len(rows) - len(scored)
    rate = sum(1 for r in scored if r["fell_back"]) / len(scored) if scored else float("nan")
    print("\nstrategy      | fallback_rate | cases | errors")
    print(f"{strategy:<13} | {rate:>13.2f} | {len(scored):>5} | {errored:>6}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--strategy", default="advanced", choices=["baseline", "hybrid", "advanced"])
    ap.add_argument("--out", required=True, help="path to write the raw per-case JSON results")
    args = ap.parse_args()

    rows = run(strategy=args.strategy)
    summarize(rows, args.strategy)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(rows, fh, indent=2)
    print(f"\nwrote {len(rows)} rows -> {args.out}")


if __name__ == "__main__":
    main()
