"""Per-user suggestion cache (Feature 005 US3/FR-006/FR-007).

An explicit, application-level Redis cache around the whole `/suggest` graph
invocation — not LiteLLM's own per-call semantic cache, which can't reach
retrieval and risks fuzzy false-positive matches (research.md §2). The key
is an exact hash over normalized, already-well-defined fields plus a
fingerprint of the requesting user's current wardrobe, so a closet edit
naturally invalidates a stale entry (FR-007) without an explicit
invalidation-on-write hook.

Implementation note (found during implementation, not in the original
design docs): the wardrobe fingerprint hashes each item's full serialized
content, not an `(id, updated_at)` pair — the shared `WardrobeItem` Pydantic
schema (unlike the SQLAlchemy row it's built from) doesn't carry
`updated_at`, and adding it there would ripple into the OpenAPI-generated
frontend types for a cache-only concern. Hashing full content is simpler,
needs no schema change, and catches an in-place edit (not just add/remove)
exactly as well.

Every public function here degrades to "no cache" on any Redis error —
per spec.md's own Edge Cases, an unavailable cache store must never fail
the request, only make it process fresh.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from typing import Optional

import redis

from ..external.weather import month_to_season, temp_to_band
from ..schema import Formality, SuggestResult, WardrobeItem
from .context_assembler import infer_formality

_KEY_PREFIX = "suggest:v1:"
_DEFAULT_TTL_SECONDS = 3600

_client: Optional["redis.Redis"] = None


def _get_client() -> "redis.Redis":
    """Lazy singleton (mirrors kb.get_kb()/memory.store.get_checkpointer()).
    `from_url` doesn't connect eagerly, so this is cheap to build even when
    Redis is unreachable — the actual connection attempt (and failure)
    happens per-command, caught by the callers below."""
    global _client
    if _client is None:
        url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
        _client = redis.Redis.from_url(url, socket_connect_timeout=1, socket_timeout=1)
    return _client


def _wardrobe_fingerprint(wardrobe: list[WardrobeItem]) -> str:
    items_repr = sorted(item.model_dump_json() for item in wardrobe)
    return hashlib.sha256("|".join(items_repr).encode()).hexdigest()


def compute_cache_key(
    user_id: str,
    *,
    occasion: str,
    mood: Optional[str],
    formality: Optional[Formality],
    location: Optional[str],
    temp_c: Optional[float],
    wardrobe: list[WardrobeItem],
    approach: str,
) -> str:
    """Per-user only by construction (this session's clarification) — the
    verified `user_id` is always part of the material, never derived from
    anything client-suppliable independent of auth. `occasion`/`mood` are
    normalized so equivalent-but-differently-cased requests collapse to the
    same key; `formality` resolves through the same `infer_formality()`
    `context_assembler.assemble_context` itself uses, so a request that omits
    it still matches one that states the resolved value explicitly.

    `approach` (Feature 010) is required, not optional-with-a-default: an
    `engine` request and a `grounded` request with otherwise-identical
    context must never collide on the same key, or one approach's cached
    result would silently be served for the other once caching is enabled."""
    occasion_norm = occasion.strip().lower()
    mood_norm = (mood or "").strip().lower()
    resolved_formality = formality or infer_formality(occasion_norm)

    if temp_c is not None:
        temp_band = temp_to_band(temp_c)
        season = month_to_season(datetime.now(timezone.utc).month)
        location_component = ""
    else:
        # No temp_c to derive a band from. When `location` is given,
        # assemble_context resolves temp/season via a live weather call —
        # replicating that here would mean paying for a network call before
        # every cache check, defeating the point. Keying on the normalized
        # location string itself is a reasonable proxy: two requests for the
        # same place still collapse to one entry, bounded by the safety-net
        # TTL for any weather drift in between.
        temp_band = None
        season = None
        location_component = (location or "").strip().lower()

    wardrobe_fp = _wardrobe_fingerprint(wardrobe)
    material = "|".join(
        [
            user_id,
            occasion_norm,
            mood_norm,
            resolved_formality,
            str(temp_band),
            str(season),
            location_component,
            wardrobe_fp,
            approach,
        ]
    )
    return _KEY_PREFIX + hashlib.sha256(material.encode()).hexdigest()


def get_cached_result(key: str) -> Optional[tuple[SuggestResult, Optional[str]]]:
    """`(result, note)` on a hit — `note` is the same optional "fewer than
    expected outfits" message the original response carried, not part of
    `SuggestResult` itself (matches the `/suggest` SSE `done` event's own
    two separate fields). `None` on a miss or any Redis/parse error — a
    cache failure degrades to "process fresh," never an error."""
    try:
        raw = _get_client().get(key)
    except redis.RedisError:
        return None
    if raw is None:
        return None
    try:
        payload = json.loads(raw)
        return SuggestResult.model_validate(payload["result"]), payload.get("note")
    except (json.JSONDecodeError, KeyError, ValueError):
        return None


def set_cached_result(
    key: str,
    result: SuggestResult,
    note: Optional[str] = None,
    ttl_seconds: int = _DEFAULT_TTL_SECONDS,
) -> None:
    payload = {
        "result": result.model_dump(mode="json"),
        "note": note,
        "cached_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        _get_client().set(key, json.dumps(payload), ex=ttl_seconds)
    except redis.RedisError:
        pass
