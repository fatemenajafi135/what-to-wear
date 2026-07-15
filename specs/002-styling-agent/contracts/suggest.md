# Contract: `POST /suggest`

Supersedes `/recommend` (kept alive through Phase 1–2, retired at the end of
Phase 3 — tasks.md T037a — once this endpoint is verified equivalent). The two
cannot coexist past Phase 3: `OutfitResult.outfits` becomes `list[ScoredOutfit]`
in Phase 2 (data-model.md), and `/recommend`'s old linear-pipeline code path
never runs `score_and_rank`, so it can't populate the required 4 scores. Same
auth model as `/recommend` post-Phase-1 and as `/wardrobe/items`: bearer JWT
required, `user_id` is always the verified `sub` claim, never a request field
(FR-001).

## Request

`POST /suggest`, `Authorization: Bearer <jwt>` required.

```jsonc
{
  "occasion": "string, required",
  "mood": "string, optional",
  "formality": "casual|smart_casual|business_casual|semi_formal|formal|black_tie, optional",
  "location": "string, optional — geocoded via Open-Meteo",
  "temp_c": "number, optional — fallback if no location / offline",
  "strategy": "baseline|hybrid|advanced, default advanced",
  "thread_id": "string, optional — continue a refinement conversation (US4); omit to start a new one"
}
```

A plain-English refinement ("warmer", "less formal", "give me alternatives") is
submitted as `occasion`-shaped free text is NOT how refinement works — refinement
reuses `occasion` as the new user utterance when `thread_id` is present; the graph's
`parse_request` node distinguishes "new request" from "refinement of thread
`thread_id`" by intent-parsing that utterance against `original_context` (see
data-model.md `RefinementTurn`). No separate refinement endpoint.

Rejected with `401` if the bearer token is missing or invalid — no closet data is
returned in that response body (SC-001).

## Response — non-streaming shape (the SSE `done` event's payload)

```jsonc
{
  "thread_id": "string — echoed/assigned, use it to continue refining",
  "result": {
    "outfits": [
      {
        "items": ["wardrobe-item-id", "..."],
        "rationale": [
          {"text": "string", "cites": ["rule_id", "..."]}
        ],
        "scores": [
          {"dimension": "color_harmony", "value": 0.0, "reason": "string"},
          {"dimension": "formality_coherence", "value": 0.0, "reason": "string"},
          {"dimension": "weather_fitness", "value": 0.0, "reason": "string"},
          {"dimension": "silhouette_balance", "value": 0.0, "reason": "string"}
        ],
        "rank_score": 0.0
      }
    ],
    "sources": [
      {"rule_id": "string", "source": "string", "url": "string", "layer": "L1|L2|L3|L4"}
    ],
    "context": { "...": "Context, unchanged shape" }
  },
  "note": "string, optional — present when a refinement could not be fully satisfied (FR-015) or when the closet yielded fewer than 3 outfits (FR-002)"
}
```

`result.outfits` has length 3–5 when the closet supports it, fewer (down to 0) with
`note` explaining why otherwise (FR-002). Every `items` entry is a `WardrobeItem.id`
the requester owns — never a catalog id (FR-003, no catalog substitution this
feature).

## Response — streaming transport (SSE, `Content-Type: text/event-stream`)

Per research.md §6, plain `StreamingResponse`, no new dependency:

```text
event: outfit
data: {"index": 0, "outfit": { ... one ScoredOutfit as above ... }}

event: outfit
data: {"index": 1, "outfit": { ... }}

event: done
data: { ... the full response shape above ... }
```

Outfits stream in final rank order as `score_and_rank` completes each one; `done`
carries the complete, authoritative payload (including `sources` and `context`,
which aren't meaningful per-outfit). A client that ignores streaming and just reads
the `done` event gets the exact non-streaming shape above.

## Error cases

| Condition | Response |
|---|---|
| Missing/invalid bearer token | `401`, no body content beyond the error detail |
| Closet has zero core items | `200` with `result.outfits: []` and a `note` explaining why (not an error — FR-002 edge case) |
| `thread_id` refers to a thread that doesn't exist | `404` |
| Refinement can't be satisfied from available items | `200` with the best-available `result` and a `note` (FR-015) |
