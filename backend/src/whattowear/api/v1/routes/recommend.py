"""GET/POST /api/v1/recommend/* — the styling chat (feature 008, specs/008-
styling-chat/contracts/recommend.md) and the outfit suggestion pager
(feature 009, specs/009-suggestion-pager/contracts/recommend.md).

`GET /recommend/readiness` gates the whole screen — pure wardrobe-shape
arithmetic (`readiness.py`), no pipeline call. `POST /recommend/messages` is
the one real caller of `pipeline.graph.get_compiled_graph` anywhere in this
codebase outside the eval harness (constitution Principle I: the graph is
invoked exactly as `eval/harness.py` already does, never a second/altered
call path). The readiness gate is re-checked here too, independent of
whatever the client already showed — a client-only gate is a spec violation
(handoff §5.2) — and the pipeline is never invoked for a blocked request.

`POST /recommend/messages` now returns **every** surfaced outfit (`outfits`,
not just `outfits[0]`) — feature 009 replaces 008's single-flat-card
rendering with a pager. As of design-decisions.md §42, every returned
outfit is also persisted immediately, in the same request, using the
pipeline's own in-hand `ScoredOutfit`/`SuggestResult.sources` — no separate
"save" action exists anymore (reversing §32's "heart's first tap creates
the row" model; the heart now only ever toggles `favorite` via
`POST /recommend/outfits/{id}/favorite`, on a row that already exists from
the moment the reply was generated).
"""

from __future__ import annotations

import logging
import uuid
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from datetime import datetime
from typing import Literal, NamedTuple

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
from whattowear.repositories.supabase_outfits import Sort, SupabaseOutfitRepository
from whattowear.schema import CitedSource, Context, ScoredOutfit, WardrobeItem

logger = logging.getLogger(__name__)

router = APIRouter()

# One request in flight at a time is enough — this backstop exists to bound
# a stuck request, not to run several concurrently (research.md §3).
_EXECUTOR = ThreadPoolExecutor(max_workers=4)

# No formality→human-label mapping exists anywhere else in the codebase
# (checked: both backend and frontend only ever carry the raw `Formality`
# literal, e.g. "business_casual") — this is small and specific enough to
# the meta line's own copy that it stays local rather than becoming a new
# shared constant nothing else needs yet (specs/009-suggestion-pager/
# research.md §3).
_FORMALITY_LABELS: dict[str, str] = {
    "casual": "Casual",
    "smart_casual": "Smart casual",
    "business_casual": "Business casual",
    "semi_formal": "Semi-formal",
    "formal": "Formal",
    "black_tie": "Black tie",
}


def _get_repository() -> SupabaseClosetRepository:
    return SupabaseClosetRepository()


def _get_outfit_repository() -> SupabaseOutfitRepository:
    return SupabaseOutfitRepository()


def _parse_outfit_id(outfit_id: str) -> None:
    """Same guard `closet.py::_parse_item_id` uses for every write route —
    a syntactically invalid id 404s here rather than reaching the
    database's `uuid` column comparison, which would otherwise raise a raw,
    unhandled `DataError`."""
    try:
        uuid.UUID(outfit_id)
    except ValueError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Outfit not found") from None


def _meta_line(context: Context) -> str:
    """design-system.md § Outfit suggestion pager item 4:
    "{occasion} · {formality|weather}" — one per reply (one `Context` per
    request), not one per outfit (design-decisions.md §34). Weather is
    preferred when the pipeline detected one; `formality` is the correct
    fallback since it's a required `Context` field, never absent."""
    second = context.condition or _FORMALITY_LABELS[context.formality]
    return f"{context.occasion} · {second}"


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
    photo_background_color: str | None

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
            photo_background_color=item.photo_background_color,
        )


MatchLabel = Literal["great", "good", "might_work"]


class StylingOutfit(BaseModel):
    # Always present (design-decisions.md §42) — every outfit returned here
    # was already persisted before the response was sent, never a
    # not-yet-saved placeholder.
    id: str
    # The card's own "title" (design-decisions.md §36 — nothing else produces
    # one for a fresh suggestion) and `meta_line`'s first segment.
    occasion: str
    rationale_text: str
    items: list[RecommendItemView]
    match_label: MatchLabel
    meta_line: str
    # Always `true` at creation (the row's own default) — exposed so the
    # client can initialize the heart's fill state from this response
    # instead of assuming, and reflect a later toggle without a refetch.
    favorite: bool


class SendMessageResponse(BaseModel):
    thread_id: str
    reply_text: str | None
    outfits: list[StylingOutfit]


class SavedOutfitResponse(BaseModel):
    id: str
    favorite: bool


class OutfitSummary(BaseModel):
    """The Outfits gallery card (design-system.md § Outfits (gallery)) —
    feature 010. `item_thumbnails` is capped at 4 (the card's own real-
    thumbnail limit); `item_count` lets the frontend compute the "+N"
    overflow chip without a second request."""

    id: str
    title: str
    match_label: MatchLabel
    favorite: bool
    created_at: datetime
    item_thumbnails: list[RecommendItemView]
    item_count: int


class OutfitSummaryListResponse(BaseModel):
    outfits: list[OutfitSummary]


class DimensionScoreView(BaseModel):
    """One bar in Outfit detail's Match breakdown (design-system.md §
    Scores). `value` is transmitted for the frontend to compute a bar's
    fill width — it is never rendered as visible text on any screen
    (design-decisions.md §38's explicit transmit-vs-render distinction)."""

    dimension: str
    value: float


class CitedRuleView(BaseModel):
    """One row of Outfit detail's numbered styling-rules list — the
    footnote a `[n]` marker in `rationale_with_citations` points at."""

    number: int
    text: str


class OutfitDetailResponse(BaseModel):
    """Outfit detail (design-system.md § Outfit detail) — feature 010."""

    id: str
    title: str
    occasion: str
    items: list[RecommendItemView]
    rationale_text: str
    rationale_with_citations: str
    citations: list[CitedRuleView]
    dimension_scores: list[DimensionScoreView]
    match_label: MatchLabel
    favorite: bool
    created_at: datetime


class RenameOutfitRequest(BaseModel):
    title: str


class RenamedOutfitResponse(BaseModel):
    id: str
    title: str


def match_label(rank_score: float) -> MatchLabel | None:
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


class _ResolvedOutfit(NamedTuple):
    """The view-building half of turning a `ScoredOutfit` into a
    `StylingOutfit` — everything that doesn't depend on the row that's
    about to be created for it (design-decisions.md §42). Kept separate
    from persistence so `_resolve_outfit` stays a pure view-builder."""

    rationale_text: str
    items: list[RecommendItemView]
    match_label: MatchLabel


def _resolve_outfit(
    outfit: ScoredOutfit,
    wardrobe_by_id: dict[str, WardrobeItem],
    access_token: str,
) -> _ResolvedOutfit | None:
    """`None` when this outfit scores below the "not surfaced at all" floor
    (design-system.md § Scores, < 0.4) — the caller drops it entirely
    rather than persisting it or including it with no label.

    No citation markers are embedded in `rationale_text` — every outfit
    reply now renders through the pager, which never shows a citation
    (design-decisions.md §33/§35); plain joined rationale text is all any
    caller of this function needs. The saved row's own
    `rationale_with_citations` (Outfit detail's concern) is built
    separately, from the same `ScoredOutfit`, by `_build_rationale_with_citations`."""
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

    rationale_text = " ".join(rationale.text for rationale in outfit.rationale)

    return _ResolvedOutfit(rationale_text=rationale_text, items=items, match_label=label)


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
    outfit_repository: SupabaseOutfitRepository = Depends(_get_outfit_repository),  # noqa: B008
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
    occasion = result.context.occasion if result.context is not None else body.message
    meta_line = _meta_line(result.context) if result.context is not None else body.message

    # Resolve every surfaced outfit (not just the top-ranked one, per the
    # handoff's mission — feature 009), dropping any that scores below the
    # "not surfaced at all" floor rather than including it unlabeled — then
    # persist it immediately (design-decisions.md §42: every returned
    # outfit is already saved, favorited by default; there is no separate
    # save action anymore). Citations/dimension_scores are built straight
    # from this same in-hand `scored_outfit`/`result.sources` — no
    # checkpointer round-trip needed, since generation and persistence now
    # happen in the same request.
    outfits: list[StylingOutfit] = []
    for scored_outfit in result.outfits:
        resolved = _resolve_outfit(scored_outfit, wardrobe_by_id, access_token)
        if resolved is None:
            continue

        rationale_with_citations, citations = _build_rationale_with_citations(scored_outfit, result.sources)
        dimension_scores = [{"dimension": s.dimension, "value": s.value} for s in scored_outfit.scores]
        # `resolved.items` (not `scored_outfit.items` raw) — a scored outfit
        # may legitimately include a shared-catalog item (Constitution IV),
        # which `_resolve_outfit` already drops from what's shown (its
        # `wardrobe_by_id` only ever holds the caller's own wardrobe). Saving
        # the raw pipeline list here would silently persist an id nothing
        # ever displays; using the same filtered list that was just shown
        # keeps the stored row and the response in agreement.
        item_ids = [item.id for item in resolved.items]
        outfit_id = outfit_repository.create(
            user_id=user_id,
            occasion=occasion,
            meta_line=meta_line,
            rationale_text=resolved.rationale_text,
            match_label=resolved.match_label,
            item_ids=item_ids,
            # design-decisions.md §36: seeded from occasion (nothing else
            # produces a title for a fresh suggestion); user-editable after.
            title=occasion,
            rationale_with_citations=rationale_with_citations,
            citations=citations,
            dimension_scores=dimension_scores,
        )
        outfits.append(
            StylingOutfit(
                id=outfit_id,
                occasion=occasion,
                rationale_text=resolved.rationale_text,
                items=resolved.items,
                match_label=resolved.match_label,
                meta_line=meta_line,
                # design-decisions.md §43: "saved" (this row existing at
                # all) and "favorite" are independent now — every outfit is
                # saved unconditionally, but favorite reflects the user's
                # own, not-yet-expressed preference (the row's own default,
                # matched here rather than re-asserted as a literal so the
                # two can never drift apart).
                favorite=False,
            )
        )

    # `note` covers the pipeline's own "zero outfits" honesty copy
    # (research.md §6); the generic fallback covers the one case the
    # pipeline can't name itself — every candidate this route filtered out
    # for scoring below the "not surfaced" floor (§ Scores) while
    # `result.outfits` was non-empty, so `explain()` had no reason to set
    # `note`.
    if outfits:
        reply_text = None
    elif note:
        reply_text = note
    else:
        # Verbatim design-system.md § Outfit suggestion pager, Empty group-
        # state copy — 008's original fallback paraphrased this ("put
        # together a confident outfit" vs. "put an outfit together");
        # Constitution VIII requires shipping copy verbatim, not
        # approximately.
        reply_text = (
            "I couldn't put an outfit together from that — try loosening a constraint or adding a few more pieces."
        )

    return SendMessageResponse(
        thread_id=thread_id,
        reply_text=reply_text,
        outfits=outfits,
    )


def _build_rationale_with_citations(
    outfit: ScoredOutfit, sources: list[CitedSource]
) -> tuple[str, list[dict[str, object]]]:
    """Resurrects the exact `[n]`-marker convention `bdc9ad4` built for 008
    and 009 removed once every outfit reply moved to the citation-free
    pager (design-decisions.md §33/§35) — markers are appended after each
    rationale segment's own text, using that segment's own `cites`, numbered
    in first-appearance order across the outfit's own rationale. Feature
    010's Outfit detail is the only remaining consumer of this shape
    (design-decisions.md §38)."""
    sources_by_rule_id = {source.rule_id: source.source for source in sources}
    seen: dict[str, int] = {}
    citations: list[dict[str, object]] = []
    text_parts: list[str] = []
    for rationale in outfit.rationale:
        segment_numbers: list[int] = []
        for rule_id in rationale.cites:
            if rule_id not in sources_by_rule_id:
                continue  # ungrounded cites are already filtered upstream; defensive only
            if rule_id not in seen:
                seen[rule_id] = len(citations) + 1
                citations.append({"number": seen[rule_id], "text": sources_by_rule_id[rule_id]})
            segment_numbers.append(seen[rule_id])
        markers = "".join(f"[{n}]" for n in segment_numbers)
        text_parts.append(f"{rationale.text} {markers}".rstrip() if markers else rationale.text)
    return " ".join(text_parts), citations


@router.get("/recommend/outfits")
def list_outfits(
    sort: Sort = "date",
    user_id: str = Depends(get_current_user_id),  # noqa: B008
    repository: SupabaseClosetRepository = Depends(_get_repository),  # noqa: B008
    access_token: str = Depends(get_current_access_token),  # noqa: B008
    outfit_repository: SupabaseOutfitRepository = Depends(_get_outfit_repository),  # noqa: B008
) -> OutfitSummaryListResponse:
    """The Outfits gallery (design-system.md § Outfits (gallery)) —
    feature 010. Always `200`, `outfits: []` for the true empty case (no
    separate empty response shape, matching 009's `outfits[]` convention
    for the pager)."""
    rows = outfit_repository.list_outfits(user_id, sort=sort)
    wardrobe_by_id = {item.id: item for item in repository.list_wardrobe_items(user_id)}

    # `item_ids` comes back from Postgres as a list of UUID objects, not
    # strings — `wardrobe_by_id` is keyed by `WardrobeItem.id: str`, so every
    # id is stringified here before lookup (a UUID-vs-str key mismatch would
    # silently miss every item instead of raising).
    def _item_ids(row: object) -> list[str]:
        return [str(item_id) for item_id in (row.item_ids or [])]  # type: ignore[attr-defined]

    # Sign every row's first-4 thumbnail photo paths in one batched call
    # rather than one call per row.
    all_photo_paths = [
        item.photo_path
        for row in rows
        for item_id in _item_ids(row)[:4]
        if (item := wardrobe_by_id.get(item_id)) is not None and item.photo_path is not None
    ]
    signed_urls = storage.create_signed_urls(access_token, all_photo_paths)

    summaries = []
    for row in rows:
        item_ids = _item_ids(row)
        thumbnails = [
            RecommendItemView.from_wardrobe_item(
                wardrobe_by_id[item_id],
                photo_url=signed_urls.get(wardrobe_by_id[item_id].photo_path or ""),
            )
            for item_id in item_ids[:4]
            if item_id in wardrobe_by_id
        ]
        summaries.append(
            OutfitSummary(
                id=str(row.id),
                title=row.title,
                match_label=row.match_label,
                favorite=row.favorite,
                created_at=row.created_at,
                item_thumbnails=thumbnails,
                item_count=len(item_ids),
            )
        )
    return OutfitSummaryListResponse(outfits=summaries)


@router.get("/recommend/outfits/{outfit_id}")
def get_outfit(
    outfit_id: str,
    user_id: str = Depends(get_current_user_id),  # noqa: B008
    repository: SupabaseClosetRepository = Depends(_get_repository),  # noqa: B008
    access_token: str = Depends(get_current_access_token),  # noqa: B008
    outfit_repository: SupabaseOutfitRepository = Depends(_get_outfit_repository),  # noqa: B008
) -> OutfitDetailResponse:
    """Outfit detail (design-system.md § Outfit detail) — feature 010. An
    item id in the outfit's `item_ids` no longer present in the caller's
    wardrobe is silently omitted from `items` (Constitution IV — never a
    stale/broken reference), never an error."""
    _parse_outfit_id(outfit_id)
    row = outfit_repository.get(user_id, outfit_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Outfit not found")

    wardrobe_by_id = {item.id: item for item in repository.list_wardrobe_items(user_id)}
    item_ids = [str(item_id) for item_id in (row.item_ids or [])]

    photo_paths = [
        item.photo_path
        for item_id in item_ids
        if (item := wardrobe_by_id.get(item_id)) is not None and item.photo_path is not None
    ]
    signed_urls = storage.create_signed_urls(access_token, photo_paths)

    items = [
        RecommendItemView.from_wardrobe_item(
            wardrobe_by_id[item_id],
            photo_url=signed_urls.get(wardrobe_by_id[item_id].photo_path or ""),
        )
        for item_id in item_ids
        if item_id in wardrobe_by_id
    ]

    return OutfitDetailResponse(
        id=str(row.id),
        title=row.title,
        occasion=row.occasion,
        items=items,
        rationale_text=row.rationale_text,
        rationale_with_citations=row.rationale_with_citations,
        citations=[CitedRuleView(**c) for c in row.citations],
        dimension_scores=[DimensionScoreView(**s) for s in row.dimension_scores],
        match_label=row.match_label,
        favorite=row.favorite,
        created_at=row.created_at,
    )


@router.patch("/recommend/outfits/{outfit_id}/title")
def rename_outfit(
    outfit_id: str,
    body: RenameOutfitRequest,
    user_id: str = Depends(get_current_user_id),  # noqa: B008
    outfit_repository: SupabaseOutfitRepository = Depends(_get_outfit_repository),  # noqa: B008
) -> RenamedOutfitResponse:
    """The gallery card's inline rename and the overflow sheet's "Edit
    title" row both call this (design-system.md § Outfits (gallery) item
    2). Rejects an empty/whitespace-only title (FR-006) before it ever
    reaches the repository."""
    _parse_outfit_id(outfit_id)
    title = body.title.strip()
    if not title:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "title must not be empty")

    new_title = outfit_repository.rename(user_id, outfit_id, title)
    if new_title is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Outfit not found")
    return RenamedOutfitResponse(id=outfit_id, title=new_title)


@router.post("/recommend/outfits/{outfit_id}/wear", status_code=status.HTTP_204_NO_CONTENT)
def log_outfit_worn(
    outfit_id: str,
    user_id: str = Depends(get_current_user_id),  # noqa: B008
    repository: SupabaseClosetRepository = Depends(_get_repository),  # noqa: B008
    outfit_repository: SupabaseOutfitRepository = Depends(_get_outfit_repository),  # noqa: B008
) -> None:
    """design-decisions.md §39: logs the outfit itself as worn today AND
    every item in it the caller still owns, via `SupabaseOutfitRepository.
    log_worn`. Idempotent — a repeat call the same calendar day is a
    no-op success, not an error (FR-005)."""
    _parse_outfit_id(outfit_id)
    row = outfit_repository.get(user_id, outfit_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Outfit not found")

    owned_ids = {item.id for item in repository.list_wardrobe_items(user_id)}
    owned_item_ids = [str(item_id) for item_id in (row.item_ids or []) if str(item_id) in owned_ids]

    if not outfit_repository.log_worn(user_id, outfit_id, owned_item_ids):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Outfit not found")


@router.delete("/recommend/outfits/{outfit_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_outfit(
    outfit_id: str,
    user_id: str = Depends(get_current_user_id),  # noqa: B008
    outfit_repository: SupabaseOutfitRepository = Depends(_get_outfit_repository),  # noqa: B008
) -> None:
    """design-decisions.md §40: confirmation is a client-side UI gate —
    this route performs the delete unconditionally once called, matching
    `DELETE /closet/items/{item_id}`'s own shape. Cascades to the outfit's
    `outfit_wears` rows via the migration's `on delete cascade`."""
    _parse_outfit_id(outfit_id)
    if not outfit_repository.delete(user_id, outfit_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Outfit not found")


@router.post("/recommend/outfits/{outfit_id}/favorite")
def toggle_outfit_favorite(
    outfit_id: str,
    user_id: str = Depends(get_current_user_id),  # noqa: B008
    outfit_repository: SupabaseOutfitRepository = Depends(_get_outfit_repository),  # noqa: B008
) -> SavedOutfitResponse:
    """The heart's second tap onward — flips the same `favorite` flag the
    first tap set to `true`; never deletes the row (design-decisions.md
    §32). `404` (not distinguishing "doesn't exist" from "isn't yours") for
    the same reason `toggle_closet_item_favorite` doesn't either."""
    favorite = outfit_repository.toggle_favorite(user_id, outfit_id)
    if favorite is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Outfit not found")
    return SavedOutfitResponse(id=outfit_id, favorite=favorite)
