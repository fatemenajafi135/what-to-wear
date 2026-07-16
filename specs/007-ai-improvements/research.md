# Phase 0 Research: L1/L3 Retrieval Restructure + Refinement Warmth-Floor Fix

No `[NEEDS CLARIFICATION]` markers carried over from spec.md. This document resolves the handoff's
explicitly-flagged "open decisions" plus a few implementation-shape questions found while reading the
existing code (`retrieval/hybrid.py`, `retrieval/advanced.py`, `pipeline/graph.py`,
`external/trends.py`, `data/kb/manifest.yaml`, `data/golden_set.yaml`).

## D1: L1 semantic search — which query text, how many results

**Decision**: Reuse `query_builder.l3_query(ctx)` as the query text for the new L1 similarity_search
branch (not a new, separately-tuned query string), with `k=5` (matching the existing `k_l3` default
used elsewhere in the file, so the two semantic branches — L1's new one and L3 — are consistent rather
than introducing a third differently-tuned constant).

**Rationale**: `l3_query()` already synthesizes occasion + formality + mood + season + temp band into
one NL string — exactly the shape a color-theory/proportion passage search wants too (it's the same
underlying "what is this request about" question L3 already answers). Building a second, L1-specific
query function would duplicate that logic for no measured benefit; the constitution's simplicity
clause disfavors that. `retrieve_l1()`'s signature already reuses `ctx` for its optional
`color_filter` narrowing — reusing an existing query-builder function keeps that same pattern of "one
query construction owner per shape of need."

**Alternatives considered**:
- A dedicated `l1_semantic_query(ctx)` in query_builder.py, phrased around color/proportion vocabulary
  specifically. Rejected for now — no evidence yet that `l3_query`'s phrasing under-serves L1 passage
  retrieval; if the eval harness shows otherwise after this lands, that's a cheap follow-up, not a
  blocker to ship this feature.
- Reusing `naive_query(ctx)` (the baseline retriever's query). Rejected: `naive_query` is deliberately
  generic ("what to wear for X, Y, Z") — `l3_query` already carries more of the signal (mood tone,
  weather framing) that a color/proportion passage search benefits from.

## D2: L1 semantic branch filter shape

**Decision**: Filter on `metadata.layer == "L1"` AND `metadata.granularity == "section"` (the tag
`chunk_section` already stamps on every long-form chunk), using a Qdrant `models.Filter` with two
`FieldCondition`s — the same construction pattern `hybrid._l3_filter()` already uses for L3, just with
an added `granularity` condition so atomic cards (already returned by the existing load-all) aren't
duplicated into the semantic result set.

**Rationale**: `metadata.granularity` already exists on every chunk (`chunk_atomic` stamps
`"atomic"`, `chunk_section` stamps `"section"`) — no new metadata field needed. Filtering on it avoids
returning the same atomic card twice (once from load-all, once from the semantic branch matching its
own short text) and keeps the union clean: load-all always contributes every atomic card; the new
branch only ever contributes section chunks.

**Alternatives considered**: Filter on `layer=="L1"` alone and de-duplicate by `rule_id` in Python
after the fact. Rejected — strictly more code for the same outcome; the metadata field to do this at
the query level already exists.

**One infra note**: `kb.py`'s `get_kb()` server-mode path already creates a payload index on
`metadata.layer` (`build_kb.build_vectorstore`, "server mode... requires an explicit payload index to
filter on a field"). A compound filter (`layer` + `granularity`) against a Qdrant collection needs an
index on *each* field used in the filter, not just the first — `granularity` doesn't have one yet.
`build_vectorstore` needs one more `client.create_payload_index(..., field_name="metadata.granularity",
...)` call alongside the existing `metadata.layer` one, or the first live query against the server
collection will 400 with "Index required but not found for metadata.granularity" (the exact failure
mode already documented in `build_kb.py`'s comment for the `layer` index, one field over). This is a
one-line addition next to the existing index creation, not a new pattern.

## D3: Tavily query template and result count

**Decision**: Reuse `query_builder.l3_query(ctx)` for the live Tavily query too (not the handoff's
literal example template `f"{season} fashion trends for {occasion}"`), with `max_results=5` for the
`hybrid` strategy and `max_results=8` (i.e. reuse `advanced.FIRST_STAGE_K`) for `advanced`, reranked
down to 5 the same way the static implementation was.

**Rationale**: `l3_query()` is already the tuned, existing query for "what should the trend layer be
about" — it already includes season/occasion/mood/formality/temp band, a strict superset of the
handoff's example template. Reusing it means one query-construction path stays the single source of
truth for "what is L3 about" regardless of whether L3 is served by a vector store or a live search —
consistent with D1's reasoning for L1. Result counts match the existing `k_l3`/`FIRST_STAGE_K`
constants already in `hybrid.py`/`advanced.py` so this change doesn't quietly alter how much L3 content
downstream generation sees.

**Alternatives considered**: The handoff's literal example template. Rejected as a *second* place that
builds a trend-relevant query string when one already exists and already covers a superset of that
example's fields — not because the example was wrong, but because it's redundant with code already in
the file being modified.

## D4: Live Tavily result → citable Document shape

**Decision**: Each Tavily result dict (`{title, url, content, ...}`, per `search_trends()`'s existing
return shape) becomes one `Document`:

```python
Document(
    page_content=result.get("content", result.get("title", "")),
    metadata={
        "source": f"Live trend search: {result.get('title', 'web result')}",
        "url": result.get("url", ""),
        "layer": "L3",
        "rule_id": f"L3-live-{hashlib.sha1(result['url'].encode()).hexdigest()[:10]}",
        "granularity": "live",
    },
)
```

**Rationale**: The four keys (`source`, `url`, `layer`, `rule_id`) are exactly what `cite.build_result`
and `cite.all_cites_grounded` already read off every `Document`'s metadata — no changes needed
downstream to cite a live result the same way a KB chunk is cited. `rule_id` is derived from the
result's own URL (sha1, truncated) rather than a counter, so it's the same for the same URL within one
process — not globally stable across processes/days (Tavily's top result for the same query can change
day to day), which is fine: FR-007 only requires a citation resolve to *this request's own* retrieval,
never that IDs be stable over time. `granularity: "live"` mirrors the `"atomic"`/`"section"` tags
already in use, in case future retrieval logic wants to distinguish live from KB-backed L3 (not needed
by this feature, but free and consistent to add — matches the existing pattern rather than inventing a
new one, since `chunk_atomic`/`chunk_section` already establish that every chunk carries this key).

**Alternatives considered**: A distinct citation *type* for live results (the handoff's third open
question) — e.g. a separate `CitedSource` variant. Rejected: `CitedSource` (schema.py) already has
exactly the fields a live result naturally has (`rule_id`, `source`, `url`, `layer`) — inventing a
parallel shape would violate Principle VI's spirit (no parallel taxonomy) for no behavioral gain, since
nothing downstream needs to tell live and KB citations apart to render or verify them.

## D5: Tavily failure handling

**Decision**: Wrap the `search_trends()` call in `retrieve_l3()` in a bare `try/except Exception`,
matching `context_assembler.assemble_context`'s existing weather-lookup fallback (`except Exception as
exc: # noqa: BLE001 - offline/bad location: fall back` then `print(f"[warn] ...")`), logging via the
project's existing `logging_utils.get_logger` instead of `print` (matching `hybrid.py`'s neighbors —
`build_kb.py` already uses the logger, `context_assembler.py`'s `print` predates it and isn't the
pattern to copy verbatim) and returning `[]`.

**Rationale**: FR-008 requires a suggestion to still be produced when Tavily fails — the rest of the
pipeline (`wardrobe_retrieval` onward) already tolerates an empty `retrieval.l3` (that's exactly what
happens today for any request with `ctx.season is None`, which skips L3 entirely). No new fallback
logic needed anywhere downstream; the fix is entirely contained to catching the exception at the point
of the call.

**Alternatives considered**: A retry-with-backoff wrapper. Rejected — `search_trends()` already has no
timeout configured explicitly (`langchain_tavily.TavilySearch` has its own internal default); adding
retry logic here is exactly the kind of scope creep the constitution's simplicity clause warns against
for a solo project, and Feature 005 already established "same-provider-only retry, no cross-provider
fallback" as this project's general retry posture for LLM calls, not tool calls like Tavily search —
extending that posture to Tavily is a separate, future decision, not required by this feature's
acceptance criteria (FR-008 only requires graceful degradation, not resilience-maximizing retry).

## D6: What "remove the now-unused static L3 path" means, precisely

**Decision**: `retrieve_l3()`'s *function body* is replaced (old static-vector-search implementation
deleted, since after this change nothing calls it — `hybrid.retrieve()` and `advanced.retrieve()` are
its only two callers and both switch to the live version). `data/kb/manifest.yaml`'s
`l3_trend_cards.jsonl` entry and the `data/kb/l3_trend_cards.jsonl` file itself are **not** removed —
`baseline.retrieve()` queries the whole Qdrant collection directly (`kb.vectorstore.similarity_search`)
and never calls `retrieve_l3` at all, so those static cards remain part of the corpus baseline is scored
against. Removing them from the manifest would shrink baseline's corpus and change its numbers — which
the spec (FR-009/SC-006) and the handoff's own out-of-scope note both explicitly forbid.

**Rationale**: This resolves an apparent tension in the handoff (Task B step 6, "remove or archive the
now-unused static... ingestion path" vs. the out-of-scope note "keep baseline... working as-is"). The
"unused... path" is retrieval *code* (the function body that queried the static collection for
hybrid/advanced), not the underlying *data* (the corpus baseline still needs). Keeping the jsonl file
ingested but retiring only the code path that used to query it for hybrid/advanced satisfies both
constraints simultaneously without a special-case flag or a second retrieval function.

**Alternatives considered**: Drop `ingest: true` on the `l3_trend_cards.jsonl` manifest entry.
Rejected outright per the reasoning above — directly violates the explicit "don't silently change what
baseline returns" constraint.

## D7: golden_set.yaml's 3 L3-pinned cases

**Decision**: For the 3 cases whose `relevant_rule_ids` include a static L3 id
(`L3-2025-metallic-evening`, `L3-2025-tailored-trousers`, `L3-2025-quiet-luxury`), drop only that one
id from each list, keeping the L4/L1 ids already present. No new "expected live trend claim" assertion
is added — a live web result can't be pinned to a fixed expected id by construction (that's the whole
point of making it live), so `retrieval_recall` for `hybrid`/`advanced` on these 3 cases now measures
recall over L4+L1 only, same as it already does for the other 22 cases that never had an L3 pin.

**Rationale**: This is the smallest change that keeps `retrieval_recall` a meaningful, comparable
number across the whole golden set post-change, and is explicitly anticipated by FR-009/SC-006 ("the
plain approach's own measured numbers unaffected... structured/enhanced approaches are where the new
behavior shows up") — the *new* behavior (a live citable trend result) is separately verified by
SC-003 (a rationale traceable to a live result), not by `retrieval_recall`.

**Alternatives considered**: Add a semantic/fuzzy recall check for L3 (e.g. "some L3-layer chunk was
retrieved, regardless of exact id"). Rejected for this feature — a real metric-design change to the
eval harness, out of scope for a request that's about retrieval sourcing, not eval methodology; flagged
as a reasonable future improvement in the final report, not built here.

## D8: Warmth-floor scaling formula

**Decision**:

```python
_WARMTH_SCALE_REFERENCE = 5  # schema.py's fixed warmth ceiling (0-5) -- the range the
                              # original flat _REFINEMENT_WARMTH_STEP was implicitly tuned against

def _category_warmth_ceiling(wardrobe: list[WardrobeItem]) -> dict[str, int]:
    ceilings: dict[str, int] = {}
    for item in wardrobe:
        group = categories.group_of(item.category)
        ceilings[group] = max(ceilings.get(group, 0), item.warmth)
    return ceilings

# inside _item_fits_hard_constraints, replacing the exemption branch:
if warmer_count:
    group = categories.group_of(item.category)
    ceilings = category_ceilings if category_ceilings is not None else _category_warmth_ceiling(ctx.wardrobe)
    ceiling = ceilings.get(group, _WARMTH_SCALE_REFERENCE)
    floor = min(ceiling, round(warmer_count * _REFINEMENT_WARMTH_STEP * ceiling / _WARMTH_SCALE_REFERENCE))
    if item.warmth < floor:
        return False
```

`wardrobe_retrieval()` precomputes `category_ceilings` once (it already loops over the full
`ctx.wardrobe`) and passes it to every `_item_fits_hard_constraints` call; the parameter defaults to
`None` (computed lazily from `ctx.wardrobe` inside the function) so existing direct unit-test call
sites that don't pass it keep working unchanged.

**Rationale**: This is the literal reading of spec FR-010/FR-011: the floor scales to what a category
can *actually* provide (its own max warmth in the current closet, `ceiling`) rather than either a flat
absolute number (the original bug) or a full pass-through (the current exemption, which is really "the
category's floor is always 0" — a degenerate special case of exactly this same formula, since a
category with `ceiling < _WARMTH_SCALE_REFERENCE` will always compute *some* nonzero floor once
`warmer_count` is large enough — capped at `ceiling`, so the warmest item(s) in that category always
survive). Capping at `ceiling` directly satisfies FR-011 ("MUST NOT exceed what the warmest item
actually available... can satisfy"). Using the fixed schema range (5) as the scaling reference — not,
say, the *overall* wardrobe's max warmth across all categories — keeps the formula stable and
independent of what else happens to be in the closet; it's calibrated against the one number that's
actually fixed by the schema (Principle VI), not a moving target.

**Worked example** (footwear ceiling=3, one "warmer": floor = min(3, round(1*2*3/5)) = min(3, round(1.2))
= min(3, 1) = 1 — a real, useful step up from nothing, not a full exemption. Two "warmer"s: floor =
min(3, round(2*2*3/5)) = min(3, round(2.4)) = min(3, 2) = 2. Three "warmer"s: floor = min(3, round(3*2*3/5))
= min(3, round(3.6)) = min(3, 4) = 3 — capped at the category's own ceiling, satisfying FR-011.
Accessory ceiling=0 (a closet with no-warmth accessories, the exact case the original bug hit): floor =
min(0, anything) = 0 always — every accessory keeps passing, which is correct: a category that
genuinely has zero warmth range shouldn't gate anything, satisfying FR-011's "never fully excluded" the
same way, just because its own ceiling already *is* zero.

**Alternatives considered**:
- A fixed per-category ceiling table (hardcoded domain knowledge, e.g. `{"footwear": 3, "accessory": 2,
  ...}`) instead of computing it from `ctx.wardrobe`. Rejected: brittle across different users' closets
  (a closet with genuinely warm boots would be wrongly capped at a hardcoded 3), and the
  actually-owned-items definition of "achievable" is both more correct per spec wording ("what that
  category can actually provide") and self-updating with no maintenance burden.
- Keep the existing blanket exemption for footwear/accessory specifically, and only add proportional
  scaling for other categories. Rejected: this is exactly the special-casing the bug fix is meant to
  remove — the new formula already produces the *correct* near-zero-effective-floor behavior for
  genuinely low-ceiling categories (see accessory example above) without a hardcoded group list, so the
  special case is redundant, not complementary.

## D9: Before/after evidence capture for the warmth-floor fix

**Decision**: A standalone script under `backend/scripts/warmth_floor_evidence.py` (not a permanent
module, not wired into the eval harness or CI) that:
1. Loads the eval baseline user's real closet (`crud.EVAL_BASELINE_USER_ID`, same fixture `harness.py`
   already uses).
2. Drives a fixed small set of occasion/formality requests through the real compiled graph
   (`get_compiled_graph()`), each followed by a `"warmer"` refinement turn on the same thread — same
   two-call pattern `test_suggest_refinement.py`'s `TestWarmerRefinement` already exercises, just
   looped over more occasions for a meaningful sample size (all `OCCASION_FORMALITY` entries, 9 cases).
3. Records whether the refinement turn's response carries the FR-015 fallback note ("couldn't fully
   satisfy... showing your previous suggestions instead").
4. Prints a `strategy | fallback_rate` table and writes the raw per-case results to a JSON file passed
   as an argument (so it can be run once before the code change with one output path, and once after
   with another, then diffed).

**Rationale**: This needs the real gateway/DB/KB (same constraints `eval/harness.py` and
`test_suggest_refinement.py` already document) — reusing the compiled graph directly, not a mock, is
the only way to observe FR-015's actual fallback behavior. A script (not a pytest test) because this is
a one-time diagnostic capture (per spec Assumptions: "not a permanently running metric"), matching how
the handoff frames it ("Save this as before.jsonl or equivalent — this is your only chance to get a
real baseline number").

**Alternatives considered**: A pytest test asserting the fallback rate improved. Rejected — this would
be a flaky, LLM-sampling-dependent assertion in the permanent test suite (the same reason
`test_suggest_refinement.py`'s existing tests use `pytest.skip` on a fallback rather than asserting
against one), and the spec's own Assumptions section says this is a one-time capture, not an ongoing
gate.
