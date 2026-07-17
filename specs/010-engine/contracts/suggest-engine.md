# Contract Delta: `POST /suggest` — `approach` field

This documents only the **delta** against the existing, shipped
`POST /suggest` contract (see `specs/002-styling-agent/contracts/suggest.md`
for the full existing contract, unchanged by this feature except as noted).

## Request

```jsonc
POST /suggest
Authorization: Bearer <jwt>
Content-Type: application/json

{
  "occasion": "wedding",
  "formality": "formal",      // optional, unchanged
  "mood": "elegant",          // optional, unchanged
  "location": "Boston",       // optional, unchanged
  "temp_c": 5,                 // optional, unchanged
  "strategy": "advanced",     // optional, unchanged, back-compat kept
  "thread_id": null,          // optional, unchanged

  "approach": "engine"        // NEW, optional. One of:
                               //   "direct" | "grounded" | "engine" | "agentic" | "compare"
                               // Default: "grounded" (today's existing behavior).
                               // Only "engine" changes behavior in this feature;
                               // every other value (including omission) is
                               // identical to pre-feature behavior.
}
```

## Response

**No change to the response schema.** `SuggestResult` (outfits, sources,
context) is identical whether `approach` was `"grounded"` or `"engine"` — the
engine path maps its output into the exact same `ScoredOutfit`/`Rationale`
types before the response is built. A caller cannot distinguish which
approach produced a given response by its shape, only by the `approach`
value it originally sent.

## Behavioral contract (engine-specific)

1. **Determinism of selection**: every item in every returned outfit was
   present in an enumerated, deterministically-scored combination *before*
   any LLM call in this request's processing. (Testable indirectly: seed a
   closet where the enumerator can only ever produce a known, fixed set of
   valid combinations, and confirm every returned outfit's item set is a
   member of that fixed set.)
2. **Never fewer than the grounded path's own degradation behavior**: if the
   closet can't complete any valid combination, the response looks exactly
   like today's "not enough items" case (empty/short `outfits` + `note`) —
   `explain` is unchanged and handles both paths identically.
3. **Refinement stickiness**: a request with `thread_id` set, continuing a
   conversation whose first turn used `approach: "engine"`, stays on the
   engine path for that turn regardless of what `approach` value (if any)
   the refinement request itself carries.
4. **Fallback never surfaces as an error**: a malformed/out-of-range engine
   LLM selection never produces a non-2xx response or an empty result where
   valid combinations existed — it silently substitutes the deterministic
   top-3-by-score with template rationale.

## Non-goals of this contract delta

- No new endpoint.
- No change to the SSE event framing (`outfit`/`done` events unchanged).
- No new error response shape — invalid `approach` values are rejected the
  same way any other Pydantic `Literal` validation failure is (422), no
  bespoke handling.
