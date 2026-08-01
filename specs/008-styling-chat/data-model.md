# Data model — Feature 008: Styling chat

No new database tables. This feature adds route-local Pydantic models (backend) and a client-side
conversation shape (frontend); the pipeline's own contracts (`schema.SuggestRequest`/
`SuggestResult`/`ScoredOutfit`) are consumed unmodified per Principle I/VII.

## Backend — route-local models (`api/v1/routes/recommend.py`)

### `ReadinessResponse` (GET `/recommend/readiness`)

| Field | Type | Notes |
|---|---|---|
| `ready` | `bool` | `false` blocks the composer entirely. |
| `sparse` | `bool` | `true` shows the dismissible sparse-closet banner; only meaningful when `ready` is `true`. |
| `missing` | `list[str]` | Natural-language item-type phrases (e.g. `["a top", "a pair of shoes"]`) the client joins into `recommend.insufficient_closet.body`'s `{missing}`. Empty when `ready` is `true`, or when blocked purely by the item-count floor with coverage otherwise satisfied (see below). |

Computed from `repository.list_wardrobe_items(user_id)` — no pipeline call, no LLM call.

**Readiness algorithm** (design-decisions.md §11's three-band rule, implemented here):

```
has_top, has_bottom, has_footwear, has_full_body = presence per CategoryGroup (categories.group_of)
skeleton_a_ok = has_top and has_bottom and has_footwear
skeleton_b_ok = has_full_body and has_footwear
coverage_ok = skeleton_a_ok or skeleton_b_ok
count_ok = len(items) >= wtw_wardrobe_min_items   # 5

ready = coverage_ok and count_ok
sparse = ready and len(items) < wtw_wardrobe_sparse_threshold   # 15

missing:
  if coverage_ok: []                          # blocked purely on count, if at all
  else:
    gaps_a = [phrase for (phrase, ok) in [("a top", has_top), ("a bottom", has_bottom),
                                            ("a pair of shoes", has_footwear)] if not ok]
    gaps_b = [phrase for (phrase, ok) in [("a full-body piece like a dress or jumpsuit", has_full_body),
                                            ("a pair of shoes", has_footwear)] if not ok]
    missing = gaps_a if len(gaps_a) <= len(gaps_b) else gaps_b   # fewer gaps = closer skeleton; ties favor A
```

When `ready` is `false` purely because of the count floor (coverage satisfied, `missing == []`),
the frontend falls back to the generic phrase "a few more items" rather than an empty list —
implemented client-side, since it is a copy-only fallback with nothing to compute.

### `SendMessageRequest` (POST `/recommend/messages`)

| Field | Type | Notes |
|---|---|---|
| `message` | `str`, min length 1 | The composer's free text. Maps 1:1 onto `SuggestRequest.occasion` — the pipeline already treats this field as free text and as a refinement utterance on a continuing thread (research.md §5). |
| `thread_id` | `str \| None` | Omitted on the first message of a conversation; echoed back from the previous response on every refinement (research.md §2). |

### `StylingReplyItem` (nested in the response)

`ClosetItemView`-shaped (reused, not duplicated — same model `closet.py` already defines and
exports): `id`, `name`, `category`, `category_group`, `colors`, `color_names`, `photo_url`, etc.

### `SendMessageResponse` (POST `/recommend/messages`)

| Field | Type | Notes |
|---|---|---|
| `thread_id` | `str` | Always present in the response, even if absent in the request — the id to echo on the next send (research.md §2). |
| `reply_text` | `str \| None` | The pipeline's `note`, when present (empty-outfit / refinement-fallback honesty copy, research.md §6). `None` when a normal outfit reply needs no extra note. |
| `outfit` | `StylingOutfit \| None` | The single top-ranked suggestion (`SuggestResult.outfits[0]` when non-empty), or `None` when the pipeline produced nothing viable. |
| `citations` | `list[CitedRule]` | Flattened, de-duplicated across the rendered outfit's `rationale[].cites`, resolved against `SuggestResult.sources` (rule_id → source/url/layer) — only rules actually rendered inline get a citation entry, never the full retrieved set. |

### `StylingOutfit` (nested)

| Field | Type | Notes |
|---|---|---|
| `rationale_text` | `str` | Joined `rationale[].text` from `ScoredOutfit.rationale`, with inline citation markers left as `[n]`-style tokens the frontend renders as `Badge`s against `citations`. |
| `items` | `list[StylingReplyItem]` | Resolved per research.md §1 — never bare ids. |
| `match_label` | `Literal["great", "good", "might_work"]` | Derived from `rank_score` via the existing thresholds (design-system.md § Scores: ≥0.8 / 0.6–0.79 / 0.4–0.59). An outfit scoring below 0.4 is never returned as `outfit` at all — same "not surfaced" rule the design system states — it falls through to the empty-reply case instead. **No numeric field anywhere on this model** (FR-016). |

### `CitedRule`

| Field | Type | Notes |
|---|---|---|
| `number` | `int` | 1-based, stable within one reply — what the inline badge and the rule-list row both display. |
| `text` | `str` | The explanation shown in the dashed rule list. Sourced from `CitedSource.source`/rule text already carried by the pipeline's retrieval — no new copy invented. |

## Backend — config additions (`core/config.py`, `Settings`)

| Field | Default | Notes |
|---|---|---|
| `wtw_wardrobe_min_items` | `5` | The hard floor (design-decisions.md §11). |
| `wtw_wardrobe_sparse_threshold` | `15` | The sparse-banner threshold (design-decisions.md §11). |
| `wtw_styling_request_timeout_seconds` | `120` | The backstop timeout around the graph invocation (research.md §3/§24.3). |

## Frontend — conversation state (client-side only, not persisted)

| Field | Type | Notes |
|---|---|---|
| `threadId` | `string \| null` | `null` until the first reply arrives; held in the Recommend page's component state only (research.md §2). Cleared by "New chat." |
| `messages` | `ChatMessage[]` | In-memory transcript for the mounted session — user/assistant turns, each assistant turn optionally carrying a resolved `StylingOutfit` and citations. Not persisted across reload (011's concern). |
| `status` | `"idle" \| "sending" \| "error"` | Drives the composer's disabled state, the "Thinking…" row, and the error card with retry. No `"styling"` sub-state is needed beyond `"sending"` — this feature has no separate multi-outfit generation phase (that's 009's pager). |
| `readiness` | `{ ready: boolean; sparse: boolean; missing: string[] } \| null` | Fetched once on mount from `GET /recommend/readiness`; re-fetched after any action that could change wardrobe size is out of scope here (no such action exists on this screen). |
