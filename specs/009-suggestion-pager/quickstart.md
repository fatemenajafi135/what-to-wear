# Quickstart — Feature 009: Outfit suggestion pager

## Prerequisites

Same three-service stack as 008: Postgres (Supabase local) + Qdrant populated (`whattowear_kb`)
+ backend with a live `AI_GATEWAY_API_KEY` for a real end-to-end run (not required for the test
suite, which mocks the gateway). A signed-in test user whose closet clears the readiness bar and
is varied enough to plausibly produce more than one viable outfit for at least one request (a
closet of ~15-20 items across categories is a reasonable bar to aim a manual test at, though the
pipeline's own ranking decides the actual count — this is not something a manual tester can force
exactly).

## Run

```bash
cd infra && npx supabase start && npx supabase db reset   # applies 0001-0009
cd backend && uv sync && uv run uvicorn whattowear.main:app --reload
cd frontend && npm ci && npm run generate:api-types && npm run dev
```

## Validate — several suggestions, paging (User Story 1)

1. Send a styling request likely to produce multiple viable outfits (a broad ask against a
   varied closet, e.g. "smart casual for the office").
2. Confirm the assistant bubble contains a pager (not a single flat card): a header pill + heart
   per card, plain-text description with no citation markers, wrapping thumbnail grid, meta
   line, feedback footer.
3. Confirm the position indicator reads "1 of N" and prev/next controls are present and
   operable; confirm "prev" is disabled at card 1 and "next" at card N.
4. Confirm every outfit shown scores at/above the match floor (cross-check: request the same
   scenario enough times, or via a backend unit test, to confirm a below-floor candidate is
   never included).

## Validate — save a suggestion, persistence survives (User Story 2)

1. Tap a card's heart. Confirm it fills solid immediately.
2. **Read the row back directly** (not just the 2xx): `psql` into the local Supabase DB and
   `select * from outfits where user_id = '<test user id>'` — confirm `item_ids`, `rationale_
   text`, `match_label`, `meta_line`, `favorite = true` are all populated and match what the card
   showed, not defaulted or dropped (the project's own recorded failure mode, docs/handoffs/
   009-suggestion-pager.md §10).
3. Tap the heart again. Confirm it un-fills, and confirm (via the same direct `psql` read) that
   the row still exists with `favorite = false` — not deleted.
4. As a second test user, attempt `GET`/direct query against the first user's saved outfit id.
   Confirm it is unreachable (RLS+GRANT isolation test — automated as
   `test_outfits_isolation.py`, spot-check manually here too).
5. Tap a card's body (not the heart, not a thumbnail, not a feedback control). Confirm navigation
   toward `/outfits/:id` and confirm a 404 there is the expected result (010 hasn't built that
   screen) — record this as an intentionally-skipped verification, not a bug.

## Validate — feedback is not persisted (User Story 3)

1. Tap thumbs-up on a card. Confirm thumbs-down is not simultaneously active.
2. Tap thumbs-down. Confirm it replaces thumbs-up as the active one.
3. Tap the active thumb again. Confirm it deselects.
4. Reload the page (or send a new request). Confirm no thumbs state persists anywhere — inspect
   the network tab across all of the above taps and confirm none of them produced a request to
   any backend route.

## Validate — mobile vs. desktop pager mechanics (User Story 4)

At a mobile viewport (< 768px, e.g. browser devtools device emulation or a real phone):

1. Attempt to swipe the card track directly with a touch/trackpad gesture. Confirm the visible
   card does not change.
2. Confirm only the arrow buttons change the visible card, via the CSS-transform slide.

At a tablet/desktop viewport (≥ 768px):

3. Confirm the card track is natively scrollable/draggable and snaps to one card at a time, with
   neighboring cards peeking at both edges.
4. Confirm the arrow buttons still work, and confirm dragging the track directly also updates the
   position indicator and arrow disabled-states (the `scroll` listener staying in sync).
5. With `prefers-reduced-motion: reduce` set (OS or devtools emulation), confirm card changes are
   not animated as a sliding/smooth-scroll motion at either viewport.

**Both widths must actually be checked in a browser** — this is explicitly called out as
insufficiently verifiable by unit tests alone (handoff §11).

## Validate — Empty and Error group states (User Story 5)

1. Force a reply where the pipeline returns zero outfits, or every candidate scores below 0.4
   (a narrow/contradictory request against a sparse or mismatched closet is one way to attempt
   this; a backend unit test with a mocked pipeline result is the reliable way). Confirm the
   Empty message renders — not an empty-looking pager track.
2. Force a request failure (e.g. stop the backend mid-request, or a backend test asserting the
   504/500 path). Confirm the distinct Error card with "Try again" appears, and that retry
   re-sends the same request.

## Validate — quality gates

```bash
cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy src && \
  uv run pytest -q && uv run lint-imports
cd frontend && npm run lint && npx tsc --noEmit && npm run build
```

Backend test count must not drop below 644; frontend below 247 (handoff §9).

## Validate — eval baselines

Only required if `pipeline/`, `scoring/`, or `retrieval/` were touched (they should not be — this
feature only changes how many already-produced outfits reach the response). If a diff review
shows no changes under those directories, state that explicitly in the final report rather than
silently skipping the check.
