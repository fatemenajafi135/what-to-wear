# Quickstart: validating Conversational styling turns end-to-end

## Prerequisites

- `backend/.env` populated (copy `backend/.env.example`; needs `AI_GATEWAY_API_KEY` — a live LLM
  gateway is required, this slice adds a real call path).
- `npx supabase start` (applies `infra/supabase/migrations/`, including this slice's `0012`), then
  `docker compose up -d` from `infra/` for Qdrant, populated — an empty Qdrant makes "Start styling"
  look broken (no citations) even though this slice never touches retrieval.
- `cd backend && uv sync && uv run uvicorn whattowear.main:app --reload`
- `cd frontend && npm ci && npm run generate:api-types && npm run dev`

## Scenario 1 — the stylist replies (User Story 1)

1. Open `http://localhost:3000/recommend` (closet must already meet `wtw_wardrobe_min_items`, or the
   screen shows the insufficient-closet gate instead).
2. Type "something for a wedding" and send.
3. **Expect**: an assistant bubble appears with a reply before "Start styling" is tapped — the
   composer disables and shows a "Thinking…" state between send and reply.
4. Send a reply to whatever it asked (e.g. "pretty formal, outdoors").
5. **Expect**: the next reply does not ask about anything already covered by turns 1–2.

## Scenario 2 — the conversation reaches the pipeline (User Story 2, the load-bearing check)

1. Continue the Scenario 1 thread. Tap "Start styling."
2. **Expect**: a wrap-up assistant bubble ("Styling for wedding, formal." or whatever the final
   copy says) appears, then the outfit pager loads beneath it.
3. **Verify the actual invoke input, not the outfits**: with `LANGSMITH_TRACING` on (the default),
   open the trace for this request in LangSmith and inspect the `graph.invoke(...)` call's input —
   confirm `formality` (stated in turn 2, not turn 1) is present in that literal input dict. A
   passing UI result with a wrong/missing invoke input is exactly the failure mode this check
   exists to catch (handoff §8).
   - Alternative without LangSmith access: add a temporary `print(invoke_input)` in
     `send_message` before the `_invoke()` closure runs, tail the `uvicorn` server log, remove it
     before committing.

## Scenario 3 — turn cap and failure resilience (User Story 4)

1. Start a fresh thread. Send 7 messages in a row (one more than the default
   `wtw_conversation_turn_cap = 6`).
2. **Expect**: by message 7, the reply is the fixed "turn cap reached" copy, not a freshly generated
   one — and no further LLM call happens for any message after that on this thread (confirm via
   LangSmith trace count, or via a breakpoint/log in `conversation.reply`).
3. Tap "Start styling." **Expect**: it still works.
4. Separately: temporarily set `AI_GATEWAY_API_KEY` to an invalid value, restart the backend, send
   one message. **Expect**: a reply still renders (the fixed "call failed" copy), the composer
   re-enables, and "Start styling" still produces outfits from whatever was gathered before the
   failure. Restore the real key afterward.

## Scenario 4 — offline

1. In DevTools, throttle to "Offline."
2. **Expect**: the composer is disabled; no message appears to send or queue.

## Automated coverage this quickstart does not replace

- `backend/tests/unit/test_conversation.py` — extraction/merge logic, LLM call mocked.
- `backend/tests/unit/eval/test_conversational_golden_set.py` — golden-set fixture shape.
- `backend/tests/integration/test_recommend_routes.py` — new `/recommend/turns` cases, the
  updated `/recommend/messages` cases (no more `user_message` double-insert, `wrap_up_text`
  present, slot composition on a first invoke, raw-text refinement unchanged on a second).
- `frontend/components/recommend/*.test.tsx` — Composer/ChatMessageList/RecommendChat behavior
  (disabled states, bubble rendering, wrap-up ordering).

Run `eval/conversational_harness.py` manually (live gateway, not part of `pytest`/CI) to score the
golden set's two halves before considering the copy/extraction quality itself done.
