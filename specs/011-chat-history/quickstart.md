# Quickstart — Feature 011: Chat history

Validates the feature end-to-end against a real local stack. See `contracts/recommend.md` for
exact request/response shapes and `data-model.md` for the schema.

## Prerequisites

```bash
cd infra && npx supabase start && npx supabase db reset   # applies 0001–0011
docker compose up -d                                        # Qdrant, if not already running
cd ../backend && uv sync && uv run uvicorn whattowear.main:app --reload
cd ../frontend && npm ci && npm run generate:api-types && npm run dev
```

Needs a populated `whattowear_kb` Qdrant collection and a live LLM gateway key in
`backend/.env` — an empty KB produces citation-less replies, which would make Story 2's
citation-badge assertion untestable (though not wrong: it should legitimately show none for a
reply with nothing to cite).

## Scenario 1 — a conversation survives a reload (Story 1)

1. Sign in, go to `/recommend`, send a message that will produce at least one outfit.
2. Reload the page. Confirm Recommend shows the fresh greeting (§25 — client state was never
   persisted) with `thread_id` gone from memory.
3. Open Chat history (`/history`) from the Recommend header. Confirm the conversation you just
   had appears as a row — no "New chat" tap was needed first.
4. In `psql`/Supabase Studio: `select id, user_id, created_at, updated_at from sessions order by
   updated_at desc limit 1;` — confirm the row exists and `id` matches the `thread_id` the
   `POST /recommend/messages` response echoed in step 1 (check network tab, not just the UI).

## Scenario 2 — browse, reopen, citations (Story 2)

1. With at least one past session that produced an outfit, open `/history`.
2. Confirm the row shows: preview text + date on the top line, message count on the second,
   and — only for this session — an outfit-count line in the primary accent color.
3. Tap the row. Confirm `/history/:sessionId` renders the full transcript in order: your
   message(s) as user bubbles, the assistant's reply as an assistant bubble.
4. For the turn that produced an outfit: confirm the assistant bubble shows citation badges
   (numbered pills) inline in the text, and confirm there is **no** item-thumbnail row and **no**
   numbered rule list anywhere on that screen (§46) — this is a deliberate asymmetry with Outfit
   detail, not a bug to "fix."
5. Confirm empty (`chat_history.empty.body`) and error (`chat_history.error.body` /
   `.error.cta`) states use the exact copy from design-system.md § Chat history — force the
   error state by stopping the backend mid-request.

## Scenario 3 — continue a conversation (Story 3)

1. From Session detail, open the browser's network tab.
2. Tap "Continue conversation." Confirm you land on `/recommend` with the prior transcript
   visible (not the fresh greeting).
3. Send a new message. In the network tab, inspect the outgoing `POST /recommend/messages`
   request body — confirm `thread_id` equals the session's own `id`, **not** a new value.
   (Do not infer this from the reply reading "continuous" — the handoff is explicit that this
   must be checked at the request level.)
4. Reload `/history`, reopen the same session, confirm the new turn is appended to the same
   transcript rather than appearing as a second session.

## Scenario 4 — "New chat" still guards correctly (Story 4)

1. On a fresh greeting (no messages sent), confirm "New chat" renders visibly but disabled.
2. Send a message, then tap "New chat." Confirm Recommend resets to the greeting.
3. Open `/history` — confirm the conversation from step 2 is present, exactly as it would have
   been even without the "New chat" tap (§44 — nothing about tapping it changed what got saved).

## Scenario 5 — outfit linking and pre-existing rows (Story 5, FR-009)

1. Pick a session that produced outfits; confirm Session detail's "{count} → View in Outfits"
   button count matches `select count(*) from outfits where thread_id = '<session id>';`.
2. Tap it, confirm it lands on `/outfits` and the outfits are visible there too.
3. In `psql`, find (or create, pre-migration-style) an outfit row with `thread_id is null`.
   Confirm it appears normally in the Outfits gallery but is not attributed to any session
   anywhere in `/history` — no session claims it, no count includes it.

## Scenario 6 — RLS (SC-005)

Run `backend/tests/integration/test_sessions_rls.py` (same two-user, direct-port,
`SET ROLE authenticated` shape as `test_outfits_rls.py`) — must pass with the app's own
BYPASSRLS connection never involved, proving the policy + GRANT in isolation.

## Scenario 7 — both widths, both themes

1. At a viewport under 1024px: `/history` shows a single-column list; tapping a row navigates to
   `/history/:sessionId` as its own screen (back arrow returns to the list).
2. At 1024px+: `/history` shows the two-pane layout — list on the left, either "Select a
   conversation to view it." or the selected session's detail on the right, matching Outfits'
   own `page.module.css` breakpoint mechanism (design-system.md §5).
3. Repeat both at `localhost:3000` and `127.0.0.1:3000`, and in both light/dark theme.

## Definition of done

Handoff §7's checklist — verified by the scenarios above plus:

```bash
cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy src \
  && uv run pytest && uv run lint-imports
cd frontend && npm run lint && npm run typecheck && npm run build && npm test
```

Backend test count must not drop below 692; frontend below 291 (handoff §7). Eval baselines
(`docs/eval-baselines/`) must be unchanged — nothing in `pipeline/`, `scoring/`, or `retrieval/`
is touched by this feature, so no eval re-run is expected to show any movement; run
`uv run pytest tests/evals -k baseline` (or the project's existing eval-check invocation) once
to confirm rather than assume.
