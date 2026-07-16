# Data Model: Production Hardening

No new Postgres tables or SQLAlchemy models. This feature's only new
"entity" is a Redis-backed cache entry; everything else (the grounding
check, the LLM routing swap) is behavior over data that already exists
(`WardrobeItem`, `CatalogItem`, `SuggestResult`) with no schema change.

## Cached suggestion entry (Redis, not Postgres)

Not a table — a Redis string key holding a JSON blob, with a TTL.

**Key** (per research.md §2):

```
suggest:v1:{sha256(user_id | occasion_norm | mood_norm | formality | temp_band | season | wardrobe_fp)}
```

- `v1` namespaces the key shape so a future change to what's hashed (e.g. if
  a new context field becomes cache-relevant) can't collide with old
  entries left over from before a deploy.
- `user_id`: the verified JWT `sub` — never client-supplied, same as every
  other per-user scoping in this codebase. Guarantees the per-user-only
  cache scope from this session's clarification structurally (a different
  user's request hashes to a different key, always).
- `occasion_norm`/`mood_norm`: `.strip().lower()` of the request fields.
- `formality`: the resolved `Formality` enum value (already computed by
  `context_assembler.assemble_context` from the request or
  `OCCASION_FORMALITY`'s default) — not the raw optional request field, so
  two requests that resolve to the same effective formality match.
- `temp_band`/`season`: `context_assembler`'s existing derived bands, not
  the raw `temp_c` float — this is what makes "near-identical" requests
  collapse to the same entry per the spec's Assumptions.
- `wardrobe_fp`: `sha256` over that user's wardrobe items' full serialized
  content (each item's `model_dump_json()`, sorted before joining so load
  order never matters). Changes on any add/edit/remove — this is the
  mechanism that satisfies FR-007 (no explicit invalidation call needed; a
  stale fingerprint just never matches a fresh lookup again). Hashing full
  content rather than an `(id, updated_at)` pair (research.md §2's
  implementation-time correction) needs no schema change to the shared
  `WardrobeItem` model, which doesn't carry `updated_at`.

**Value** (JSON):

```json
{
  "result": { /* SuggestResult.model_dump(mode="json") — unchanged shape */ },
  "cached_at": "2026-07-16T12:00:00Z"
}
```

`result` is exactly what `/suggest`'s `done` SSE event already sends today —
no new response shape. `cached_at` is informational only (not used for any
logic beyond the Redis-native TTL, which is the actual expiry mechanism).

**TTL**: a fixed safety-net duration (e.g. 3600s) set on write via the
client's own `EX` option — not read/compared in application code. Belt only;
the fingerprint-in-the-key is the belt-and-suspenders correctness mechanism
that actually matters for FR-007.

**Lifecycle**:
1. Miss (key absent, or Redis unreachable) → graph runs in full → on success,
   value written with the TTL.
2. Hit → value returned as-is, graph never invoked.
3. Never explicitly deleted — a stale entry (old wardrobe fingerprint) is
   simply never looked up again once the wardrobe changes; it expires via
   TTL on its own.

## Grounding verification (no new entity)

A pure predicate over data already in `GraphState`
(`ctx.wardrobe`, `scored_outfits`) plus the shared catalog
(`crud.list_catalog_items`, fetched fresh in the `verify_grounding` node —
no new table, the catalog already exists) — see research.md §3 and
`contracts/suggest.md` (updated) for the node's place in the graph. No
request/response shape changes: a dropped outfit is simply absent from the
`scored_outfits` list and the `outfit` SSE events derived from it; `explain`'s
existing `note` field (already part of `SuggestResult`) covers the "fewer
than expected / none at all" cases with its current logic, unchanged.

## LLM routing (no new entity)

`config.py`'s factory functions keep their existing signatures and return
types (`ChatOpenAI`-compatible `BaseChatModel`, satisfied by `ChatLiteLLM`).
No Pydantic model changes.
