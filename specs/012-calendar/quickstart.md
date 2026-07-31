# Quickstart: Calendar

Environment setup is covered by `docs/handoffs/012-calendar.md` §3. This file only adds the
calendar-specific validation once that baseline is running.

## Prerequisites

```bash
cd infra && npx supabase start   # leave running
cd infra && npx supabase db reset   # replays every migration from empty, 0004 included
```

A Google Cloud OAuth client with the Calendar API enabled and
`calendar.events.readonly` added to the consent screen's scopes (see the feature report for
the exact steps taken). `infra/.env` needs `GOOGLE_OAUTH_CLIENT_ID` /
`GOOGLE_OAUTH_CLIENT_SECRET`; `backend/.env` needs `WTW_TOKEN_ENCRYPTION_KEY` (generate with
`python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`).
Without a real client, everything except the live OAuth round-trip is still fully testable —
see the feature report for exactly what was verified in this session.

## Backend — fast checks, no database

```bash
cd backend
uv run pytest tests/unit -v
uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run lint-imports
```

Expected: 459+ passing — this feature adds new unit tests; it must not remove or break any of
the existing ones.

## Backend — RLS isolation proof (needs a running local Postgres)

```bash
uv run pytest tests/integration/test_calendar_rls.py -v
```

Connects directly to Postgres (port 54322) as the `authenticator` role — not through the app's
own bypass-privileged pooler connection — `SET ROLE authenticated`, sets
`request.jwt.claim.sub` to each of two seeded users in turn, and asserts a raw, unfiltered
`SELECT * FROM calendar_connections` / `picked_events` returns only that user's row. See
`research.md` §9 for why this has to run outside the app's own connection to mean anything.

## Backend — routes (needs a running local Postgres; Google client optional)

```bash
uv run pytest tests/integration/test_calendar_routes.py -v
uv run uvicorn whattowear.main:app --reload
```

```bash
# 401 — no token
curl -s -o /dev/null -w "%{http_code}\n" localhost:8000/api/v1/calendar/connection   # expect 401

# 200 — real token (see specs/003-auth/quickstart.md for how to obtain one)
curl -s -H "Authorization: Bearer $TOKEN" localhost:8000/api/v1/calendar/connection | jq .
# expect {"connected": false, "connected_at": null} for a fresh user
```

## Frontend — states without a live Google client

```bash
cd frontend
npm run lint && npm run typecheck && npm run build && npm test
npm run dev
```

Visit `/calendar` signed in as a fresh user: disconnected card renders. Fixture data (not a
live Google account) exercises connected-with-events, connected-empty, and error states —
see the feature report for exactly how each was driven without a real OAuth round-trip.

## Full manual pass (needs a real Google Cloud OAuth client)

1. `/calendar` → "Connect Google Calendar" → permission primer appears once
   (`wtw_calendar_primed` unset) → "Continue to Google" → Google consent screen → redirected
   back through `/calendar/callback` → `/calendar` now shows the connected state.
2. Reconnect from a second session/incognito window as the same user: primer does not
   reappear.
3. Pick an event → all rows disable → `/recommend` shows "Styling for {event} · Change".
4. Disconnect from Settings → Connected accounts (the only disconnect affordance — `/calendar`
   only ever shows a connect action, in its disconnected state; see `docs/design-decisions.md`
   §16) → `/calendar` and Settings both reflect disconnected on next view, and `/recommend`'s
   context line reverts to the unpicked prompt. Since feature 013 is not yet merged into
   `rebuild`, this step is verified against this feature's own local harness for the shared
   connect/disconnect logic, not against 013's actual Settings page — see the feature report.
