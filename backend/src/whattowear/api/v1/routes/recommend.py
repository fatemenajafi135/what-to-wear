"""GET/POST /api/v1/recommend/* — the styling chat (feature 008, specs/008-
styling-chat/contracts/recommend.md).

`GET /recommend/readiness` gates the whole screen — pure wardrobe-shape
arithmetic (`readiness.py`), no pipeline call. `POST /recommend/messages` is
the one real caller of `pipeline.graph.get_compiled_graph` anywhere in this
codebase outside the eval harness (constitution Principle I: the graph is
invoked exactly as `eval/harness.py` already does, never a second/altered
call path). The readiness gate is re-checked here too, independent of
whatever the client already showed — a client-only gate is a spec violation
(handoff §5.2) — and the pipeline is never invoked for a blocked request.
"""

from __future__ import annotations

import logging
import uuid
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from whattowear.adapters import storage
from whattowear.auth import get_current_access_token, get_current_user_id
from whattowear.categories import CategoryGroup, group_of
from whattowear.colors import nearest_names
from whattowear.core.config import get_settings
from whattowear.pipeline.graph import get_compiled_graph
from whattowear.readiness import ReadinessResult, evaluate_wardrobe_readiness
from whattowear.repositories.supabase_closet import SupabaseClosetRepository
from whattowear.schema import ScoredOutfit, WardrobeItem

logger = logging.getLogger(__name__)

router = APIRouter()

# One request in flight at a time is enough — this backstop exists to bound
# a stuck request, not to run several concurrently (research.md §3).
_EXECUTOR = ThreadPoolExecutor(max_workers=4)


def _get_repository() -> SupabaseClosetRepository:
    return SupabaseClosetRepository()


class ReadinessResponse(BaseModel):
    ready: bool
    sparse: bool
    missing: list[str]

    @classmethod
    def from_result(cls, result: ReadinessResult) -> ReadinessResponse:
        return cls(ready=result.ready, sparse=result.sparse, missing=result.missing)


class SendMessageRequest(BaseModel):
    message: str
    thread_id: str | None = None


class RecommendItemView(BaseModel):
    """A route-local view of `WardrobeItem`, deliberately not imported from
    `closet.py` — every route in this codebase defines its own response
    model beside itself (`closet.py`'s own `ClosetItemView` docstring notes
    it does the same relative to `whoami.py`), so this mirrors that shape
    rather than coupling two route modules together."""

    id: str
    name: str | None
    category: str
    category_group: CategoryGroup
    colors: list[str]
    color_names: list[str]
    photo_url: str | None

    @classmethod
    def from_wardrobe_item(cls, item: WardrobeItem, photo_url: str | None) -> RecommendItemView:
        return cls(
            id=item.id,
            name=item.name,
            category=item.category,
            category_group=group_of(item.category),
            colors=item.colors,
            color_names=nearest_names(item.colors),
            photo_url=photo_url,
        )


class CitedRule(BaseModel):
    number: int
    text: str


class StylingOutfit(BaseModel):
    rationale_text: str
    items: list[RecommendItemView]
    match_label: str | None


class SendMessageResponse(BaseModel):
    thread_id: str
    reply_text: str | None
    outfit: StylingOutfit | None
    citations: list[CitedRule]


def match_label(rank_score: float) -> str | None:
    """design-system.md § Scores: labels only, never the float. Below 0.4 an
    outfit is never surfaced at all (`None`), not shown with a discouraging
    label — the caller must treat `None` as "don't render this outfit"."""
    if rank_score >= 0.8:
        return "great"
    if rank_score >= 0.6:
        return "good"
    if rank_score >= 0.4:
        return "might_work"
    return None


def _resolve_outfit(
    outfit: ScoredOutfit,
    sources: dict[str, str],
    wardrobe_by_id: dict[str, WardrobeItem],
    access_token: str,
) -> tuple[StylingOutfit, list[CitedRule]] | None:
    """`None` when the top-ranked outfit scores below the "not surfaced at
    all" floor (design-system.md § Scores, < 0.4) — the caller falls back to
    the empty-reply path exactly as it would for zero outfits."""
    label = match_label(outfit.rank_score)
    if label is None:
        return None

    photo_paths: list[str] = [
        item.photo_path
        for item_id in outfit.items
        if (item := wardrobe_by_id.get(item_id)) is not None and item.photo_path is not None
    ]
    signed_urls = storage.create_signed_urls(access_token, photo_paths)

    items = [
        RecommendItemView.from_wardrobe_item(
            wardrobe_by_id[item_id],
            photo_url=signed_urls.get(wardrobe_by_id[item_id].photo_path or ""),
        )
        for item_id in outfit.items
        if item_id in wardrobe_by_id
    ]

    seen: dict[str, int] = {}
    citations: list[CitedRule] = []
    text_parts: list[str] = []
    for rationale in outfit.rationale:
        text_parts.append(rationale.text)
        for rule_id in rationale.cites:
            if rule_id not in sources:
                continue  # ungrounded cites are already filtered upstream; defensive only
            if rule_id not in seen:
                seen[rule_id] = len(citations) + 1
                citations.append(CitedRule(number=seen[rule_id], text=sources[rule_id]))

    styling_outfit = StylingOutfit(
        rationale_text=" ".join(text_parts),
        items=items,
        match_label=label,
    )
    return styling_outfit, citations


@router.get("/recommend/readiness")
def get_readiness(
    user_id: str = Depends(get_current_user_id),  # noqa: B008
    repository: SupabaseClosetRepository = Depends(_get_repository),  # noqa: B008
) -> ReadinessResponse:
    settings = get_settings()
    items = repository.list_wardrobe_items(user_id)
    result = evaluate_wardrobe_readiness(
        items,
        min_items=settings.wtw_wardrobe_min_items,
        sparse_threshold=settings.wtw_wardrobe_sparse_threshold,
    )
    return ReadinessResponse.from_result(result)


@router.post("/recommend/messages")
def send_message(
    body: SendMessageRequest,
    user_id: str = Depends(get_current_user_id),  # noqa: B008
    access_token: str = Depends(get_current_access_token),  # noqa: B008
    repository: SupabaseClosetRepository = Depends(_get_repository),  # noqa: B008
) -> SendMessageResponse:
    settings = get_settings()
    items = repository.list_wardrobe_items(user_id)

    readiness = evaluate_wardrobe_readiness(
        items,
        min_items=settings.wtw_wardrobe_min_items,
        sparse_threshold=settings.wtw_wardrobe_sparse_threshold,
    )
    if not readiness.ready:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Your closet isn't ready for a styling request yet.")

    if not body.message.strip():
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "message must not be empty")

    thread_id = body.thread_id or str(uuid.uuid4())
    graph = get_compiled_graph(repository)

    def _invoke() -> dict:
        return graph.invoke(
            {
                "occasion": body.message,
                "thread_id": thread_id,
                "user_id": user_id,
                "approach": "grounded",
            },
            config={"configurable": {"thread_id": thread_id}},
        )

    future = _EXECUTOR.submit(_invoke)
    try:
        final_state = future.result(timeout=settings.wtw_styling_request_timeout_seconds)
    except FutureTimeoutError:
        raise HTTPException(status.HTTP_504_GATEWAY_TIMEOUT, "That took too long. Try again.") from None

    result = final_state["result"]
    note = final_state["note"]

    wardrobe_by_id = {item.id: item for item in items}
    sources_by_rule_id = {source.rule_id: source.source for source in result.sources}

    outfit: StylingOutfit | None = None
    citations: list[CitedRule] = []
    if result.outfits:
        resolved = _resolve_outfit(result.outfits[0], sources_by_rule_id, wardrobe_by_id, access_token)
        if resolved is not None:
            outfit, citations = resolved

    # `note` covers the pipeline's own "zero outfits" honesty copy
    # (research.md §6); the generic fallback covers the one case the
    # pipeline can't name itself — a top-ranked outfit this route filtered
    # out for scoring below the "not surfaced" floor (§ Scores) while
    # `result.outfits` was non-empty, so `explain()` had no reason to set
    # `note`.
    if outfit is not None:
        reply_text = None
    elif note:
        reply_text = note
    else:
        reply_text = (
            "I couldn't put together a confident outfit from that — "
            "try loosening a constraint or adding a few more pieces."
        )

    return SendMessageResponse(
        thread_id=thread_id,
        reply_text=reply_text,
        outfit=outfit,
        citations=citations,
    )
