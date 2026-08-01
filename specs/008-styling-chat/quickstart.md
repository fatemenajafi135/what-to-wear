# Quickstart — Feature 008: Styling chat

## Prerequisites

- Postgres (Supabase local stack) and Qdrant both running, per `docs/handoffs/008-styling-chat.md`
  §4 — `npx supabase start && docker compose up -d` from `infra/`.
- Qdrant's `whattowear_kb` collection populated (391 points expected locally — verify with
  `curl -s http://localhost:6333/collections/whattowear_kb`; an empty collection returns a real
  reply with zero citations, which looks like a bug and isn't one).
- `backend/.env` has `AI_GATEWAY_API_KEY` set (a live LLM gateway is required for a real end-to-end
  run; not for the test suite, which mocks the gateway).
- A signed-in test user whose closet clears the readiness bar (`≥5` items, with at least one top +
  bottom + footwear, or one full-body item + footwear).

## Run

```bash
cd backend && uv sync && uv run uvicorn whattowear.main:app --reload
cd frontend && npm ci && npm run generate:api-types && npm run dev
```

## Validate — happy path (User Story 1)

1. Sign in, open `/recommend`. Confirm the hero state: brand mark, wordmark, time-of-day-correct
   greeting, welcome bubble, three suggestion chips.
2. Type "business casual for a rainy commute", send.
3. Confirm: a transient "Thinking…" row appears immediately; the composer and send button are
   disabled for the whole wait (no premature timeout — this can take several seconds, by design,
   research.md §3); the eventual assistant reply contains inline numbered citation badges, a
   dashed rule list explaining each, and a thumbnail row.
4. Tap a thumbnail — lands on that item's `/closet/:itemId`.
5. Confirm every item shown belongs to the signed-in test user's own closet (cross-check against
   `GET /api/v1/closet/items`).

## Validate — refinement (User Story 2)

1. After the first reply, send "something warmer" in the same conversation.
2. Confirm the second reply reads as a refinement (different/adjusted outfit reflecting "warmer"),
   not an unrelated fresh suggestion — and confirm the request included the `thread_id` echoed
   back from the first response (inspect the network request body).

## Validate — insufficient closet (User Story 3)

1. As a test user with `<5` items, or one missing a whole skeleton (e.g. only tops, no bottoms/
   footwear), open `/recommend`.
2. Confirm the composer is replaced by the insufficient-closet message naming what's missing, and
   confirm no `POST /recommend/messages` call happens.
3. Call `POST /api/v1/recommend/messages` directly (e.g. via `curl`) as that same user, bypassing
   the UI gate entirely. Confirm a `403` and confirm (via logs/tracing) the pipeline was never
   invoked.

## Validate — New chat (User Story 4)

1. On a fresh hero state (or immediately after a reset), confirm "New chat" renders visibly but
   disabled.
2. Send one message, then trigger "New chat." Confirm the screen returns to the hero state with a
   fresh `thread_id` on the next send (inspect the network request — no `thread_id` in the body).

## Validate — calendar context (User Story 5)

1. With no picked calendar event: confirm the context line reads "Style for an event from
   calendar."
2. Pick an event on `/calendar`, return to `/recommend`: confirm the line reads "Styling for
   {event} · Change."

## Validate — quality gates

```bash
cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy src && \
  uv run pytest -q && uv run lint-imports
cd frontend && npm run lint && npx tsc --noEmit && npm run build
```

Backend test count must not drop below 617; frontend below 182 (handoff §9).

## Validate — eval baselines

Only required if `pipeline/`, `scoring/`, or `retrieval/` were touched (they should not be — this
feature only adds callers). If a diff review shows no changes under those directories, this step
is a no-op and should be stated as such in the final report, not silently skipped.
