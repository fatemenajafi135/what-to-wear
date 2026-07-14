"""Tavily trend search (external API #2 / agentic search).

Two uses:
1. `search_trends()` — live web search for current styling trends, callable at
   request time to augment the L3 layer with fresh signal.
2. `refresh_trend_cards()` — distills search results into L3 trend cards (our
   words + link, full article text never stored — legal policy §4) and appends
   to the L3 card file so the next build indexes them.
"""

from __future__ import annotations

import json
from pathlib import Path

from langsmith import traceable

from ..config import get_chat_model
from ..ingest.loaders import REPO_ROOT

L3_CARDS_PATH = REPO_ROOT / "data" / "kb" / "l3_trend_cards.jsonl"

_DISTILL_PROMPT = (
    "You distill fashion-trend web results into ONE factual trend card. "
    "Output strict JSON: {{\"claim\": short factual trend statement in your own "
    "words, \"season\": one of spring|summer|autumn|winter, \"formality\": one of "
    "casual|smart_casual|business_casual|semi_formal|formal|black_tie}}. "
    "Do NOT copy sentences from the source; summarize the fact only.\n\n"
    "Query: {query}\nResults:\n{results}"
)


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
    import json as _json

    joined = "\n".join(
        f"- {r.get('title','')}: {r.get('content','')[:400]}" for r in results
    )
    msg = _DISTILL_PROMPT.format(query=query, results=joined)
    raw = get_chat_model(temperature=0.0).invoke(msg).content
    try:
        start, end = raw.find("{"), raw.rfind("}")
        card = _json.loads(raw[start : end + 1])
    except Exception:  # noqa: BLE001
        return None
    return card


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
        new_cards.append({
            "rule_id": f"L3-live-{next_n:03d}",
            "text": card["claim"],
            "season": card.get("season"),
            "formality": card.get("formality"),
            "source": "Distilled trend card (Tavily live search)",
            "url": top_url,
        })
        next_n += 1
    if append and new_cards:
        with open(L3_CARDS_PATH, "a", encoding="utf-8") as fh:
            for c in new_cards:
                fh.write(json.dumps(c) + "\n")
    return new_cards


def _load_existing() -> list[dict]:
    if not L3_CARDS_PATH.exists():
        return []
    with open(L3_CARDS_PATH, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]
