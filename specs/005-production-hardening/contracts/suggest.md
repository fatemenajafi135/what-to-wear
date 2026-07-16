# Contract addendum: `POST /suggest` (Production Hardening)

Extends `specs/002-styling-agent/contracts/suggest.md` (still the source of
truth for request/response *shape* — unchanged by this feature, per FR-011).
This addendum documents the two internal behavior changes visible to a
client, both non-breaking:

## 1. A cache hit answers without new provider calls (FR-006/007, US3)

When `thread_id` is omitted (or is a fresh id the checkpointer has no prior
state for) and a matching cached result exists (research.md §2), the
response is the SSE `outfit`/`done` event sequence built directly from the
cached `SuggestResult` — byte-identical shape to a freshly generated
response, just assembled without invoking the graph. A client cannot
distinguish a cache hit from a very fast fresh computation by response shape
— only by latency (SC-003: well under a second) and, on the server side, by
the absence of new LangSmith-traced provider calls (US4's independent test).

Refinement turns (`thread_id` continuing an existing conversation) always
run the graph — never served from this cache (research.md §2).

## 2. An outfit can be silently dropped for failing grounding (FR-003/004/005, US2)

`result.outfits` may now be shorter than what `generate_outfits`/
`score_and_rank` produced if one or more outfits fail the grounding check
(research.md §3) — indistinguishable, from the response shape alone, from
the existing "fewer than 3 outfits available from this closet" case; both
surface through the same existing `note` field. No new error shape, no new
HTTP status code. If every outfit fails verification, the existing
zero-outfits-plus-`note` response is returned — never a 5xx.

## Unaffected

Request shape, auth model (`get_current_user_id`, `401` on missing/invalid
JWT), `ScoredOutfit`/`DimensionScore`/`Context` shapes, and the SSE event
framing are all exactly as documented in `specs/002-styling-agent/contracts/
suggest.md` — nothing in this feature changes what a suggestion contains or
how it's chosen (FR-011).
