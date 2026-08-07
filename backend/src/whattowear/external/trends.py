"""Tavily trend search (external API #2 / agentic search).

Two uses:
1. `search_trends()` — live web search for current styling trends, callable
   at request time to augment the L3 layer with fresh signal
   (`retrieval/hybrid.py::retrieve_l3`).
2. `refresh_trend_cards()` — a maintenance CLI helper (not on the live
   pipeline path) that distills search results into L3 trend cards (our
   words + link, full article text never stored) and appends to the L3
   card file so the next ingestion run indexes them.
"""

from __future__ import annotations

import json
from pathlib import Path

from langsmith import traceable

from ..adapters.llm_gateway import get_chat_model
from ..core.config import get_settings
from ..prompts import load_prompt


@traceable(name="external.tavily_search", run_type="tool")
def search_trends(query: str, max_results: int = 5) -> list[dict]:
    """Live Tavily search. Returns raw results (title, url, content)."""
    from langchain_tavily import TavilySearch

    tool = TavilySearch(max_results=max_results, topic="general")
    resp = tool.invoke({"query": query})
    # langchain_tavily returns {"results": [...]} or a list depending on version
    if isinstance(resp, dict):
        return resp.get("results", [])
    return resp or []


def distill_card(query: str, results: list[dict]) -> dict | None:
    """LLM-distill search results into one trend card (via the gateway)."""
    prompt_text, _version = load_prompt("trends_distill")
    joined = "\n".join(f"- {r.get('title', '')}: {r.get('content', '')[:400]}" for r in results)
    msg = prompt_text.format(query=query, results=joined)
    raw = get_chat_model(temperature=0.0).invoke(msg).content
    try:
        if not isinstance(raw, str):
            # BaseMessage.content is str | list[str | dict] (multimodal
            # responses); a plain-text distillation call never returns the
            # list form in practice, but the type is real — treat it the
            # same as any other malformed response, not a crash.
            raise TypeError("expected a plain-text response")
        start, end = raw.find("{"), raw.rfind("}")
        card = json.loads(raw[start : end + 1])
    except Exception:  # noqa: BLE001
        return None
    return card


def _l3_cards_path() -> Path:
    """`$CORPUS_LOCAL_DIR/kb/l3_trend_cards.jsonl` — constitution Principle
    X: no document path lives inside the repo. Replaces the legacy
    `REPO_ROOT`-relative constant, which pointed at a path this rebuild's
    corpus model retired (specs/007-ai-port/research.md §10)."""
    corpus_dir = get_settings().corpus_local_dir
    if not corpus_dir:
        raise RuntimeError("CORPUS_LOCAL_DIR is required to refresh trend cards. Set it in .env (see .env.example).")
    return Path(corpus_dir) / "kb" / "l3_trend_cards.jsonl"


def refresh_trend_cards(queries: list[str], append: bool = True) -> list[dict]:
    """Search + distill + (optionally) append new L3 cards to the card file."""
    new_cards: list[dict] = []
    existing = _load_existing()
    next_n = len(existing) + 1
    for q in queries:
        results = search_trends(q)
        if not results:
            continue
        card = distill_card(q, results)
        if not card or not card.get("claim"):
            continue
        top_url = results[0].get("url", "https://www.tavily.com/")
        new_cards.append(
            {
                "rule_id": f"L3-live-{next_n:03d}",
                "text": card["claim"],
                "season": card.get("season"),
                "formality": card.get("formality"),
                "source": "Distilled trend card (Tavily live search)",
                "url": top_url,
            }
        )
        next_n += 1
    if append and new_cards:
        with open(_l3_cards_path(), "a", encoding="utf-8") as fh:
            for c in new_cards:
                fh.write(json.dumps(c) + "\n")
    return new_cards


def _load_existing() -> list[dict]:
    path = _l3_cards_path()
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]
