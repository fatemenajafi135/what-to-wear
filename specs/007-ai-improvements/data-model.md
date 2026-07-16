# Phase 1 Data Model: L1/L3 Retrieval Restructure + Refinement Warmth-Floor Fix

No new persisted entities, no schema.py changes, no Alembic migration — every "entity" below is a
runtime shape that already exists (`Document`, `WardrobeItem`) or a small new pure-Python value
introduced by this feature, never persisted.

## Semantic passage (L1 semantic chunk)

Not a new type — a `langchain_core.documents.Document` (the same type every KB chunk already is),
distinguished from an atomic rule card only by its metadata's `granularity` value.

| Field | Type | Source | Notes |
|---|---|---|---|
| `page_content` | `str` | `chunk_section()` (existing, `ingest/chunkers.py`) | A ~900-char (default `WTW_CHUNK_SIZE`) slice of the long-form source, unchanged by this feature |
| `metadata.source` | `str` | inherited from the parent `Document` the loader produced | e.g. `"Wikipedia: Color theory"` |
| `metadata.url` | `str` | inherited | e.g. `https://en.wikipedia.org/wiki/Color_theory` |
| `metadata.layer` | `str` | inherited | Always `"L1"` for this pool |
| `metadata.rule_id` | `str` | `chunk_section()` | e.g. `"L1-wikipedia-color--sec-004"` — stable across rebuilds of the same corpus (deterministic from source + chunk index) |
| `metadata.granularity` | `str` | `chunk_section()` | Always `"section"` — this is the new filter key `retrieve_l1()` queries on |

**Already exists, unchanged by this feature**: the loader/chunker/embedding pipeline that produces
these. This feature only adds a query path (`retrieve_l1`'s new `similarity_search` branch) that reads
what's already been written to the `whattowear_kb` Qdrant collection.

## Live trend result

A `Document`, constructed fresh on every request inside `retrieve_l3()` — never persisted, never
re-read across requests.

| Field | Type | Source | Notes |
|---|---|---|---|
| `page_content` | `str` | Tavily result's `content` (fallback: `title`) | Raw search-result text, not distilled — distinct from `l3_trend_cards.jsonl`'s hand-distilled cards, which paraphrase in the project's own words |
| `metadata.source` | `str` | `f"Live trend search: {title}"` | Distinguishes a live result from a KB-sourced one at a glance in rendered citations |
| `metadata.url` | `str` | Tavily result's `url` | |
| `metadata.layer` | `str` | constant `"L3"` | Same layer tag as the (now-baseline-only) static trend cards, so `RetrievalResult.l3` / `rule_ids()` / `cite.py` need no changes |
| `metadata.rule_id` | `str` | `f"L3-live-{sha1(url)[:10]}"` | Deterministic per-URL within a run; not guaranteed stable across days (Tavily's top result for a query can change) — acceptable per FR-007 (only needs to resolve to *this request's* retrieval) |
| `metadata.granularity` | `str` | constant `"live"` | Distinguishes from `"atomic"`/`"section"` if ever needed downstream; not consumed by any existing code path |

**Validity/lifetime**: request-scoped only. Never written to `data/kb/*.jsonl`, never embedded, never
appears in a subsequent request unless Tavily happens to return the same URL again.

## Category warmth ceiling

A plain `dict[str, int]`, computed fresh per graph invocation inside `wardrobe_retrieval()` — not a
class, not persisted.

| Key | Value | Computed as |
|---|---|---|
| category group (`"top"`, `"bottom"`, `"full_body"`, `"outerwear"`, `"footwear"`, `"accessory"` — the existing frozen taxonomy) | `int`, 0-5 | `max(item.warmth for item in ctx.wardrobe if categories.group_of(item.category) == group)`, or absent (falls back to `_WARMTH_SCALE_REFERENCE = 5`) if the group has no items in the closet |

**Lifetime**: one graph invocation. Recomputed every request (and every refinement turn, since
`wardrobe_retrieval` runs again each turn) from the current `ctx.wardrobe` — always reflects the
closet as it exists right now, not a cached/stale view (relevant if a user edits their closet mid-
conversation, though that's an existing, unrelated behavior this feature doesn't change).

## Existing entities referenced, unchanged

- `WardrobeItem` (`schema.py`) — read-only input to the new ceiling computation; no field added.
- `RetrievalResult` (`retrieval/base.py`) — `l1`/`l3` fields now may contain a mix of `granularity`
  values; the dataclass shape itself (`l1: list[Document]`, `l3: list[Document]`, `.all()`,
  `.rule_ids()`) is unchanged.
- `CitedSource` (`schema.py`) — unchanged; both new `Document` shapes already carry the four fields
  `cite.build_result` reads (`rule_id`, `source`, `url`, `layer`).
