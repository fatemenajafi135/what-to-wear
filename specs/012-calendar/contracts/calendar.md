# Contract: Calendar routes

All routes require `Authorization: Bearer <supabase-access-token>` (feature 003's
`get_current_user_id` dependency) and are prefixed `/api/v1/calendar`. **401** on a
missing/invalid/expired token, same shape as `whoami.md`'s contract, on every route below —
not repeated per-route.

## `GET /connection`

Used by both `/calendar` and Settings → Connected accounts — the one shared read of
connection state (spec FR-012).

**200**
```json
{ "connected": true, "connected_at": "2026-07-20T10:00:00Z" }
```
`connected_at` is `null` when `connected` is `false`. Never includes a token in any form.

## `POST /connect/start`

Begins the PKCE flow (research.md §1/§3). No request body.

**200**
```json
{ "authorize_url": "https://accounts.google.com/o/oauth2/v2/auth?..." }
```
The frontend performs `window.location.assign(authorize_url)` — never fetches it as JSON and
renders a redirect itself (design-decisions §12's "never a provider-hosted page" is about the
*return* leg; the *outbound* leg to the provider's own consent screen is expected and is not
what that rule forbids).

## `POST /connect/finish`

Called by `/calendar/callback` (the app route Google redirects back to) after extracting
`code`/`state` from the query string.

**Request**
```json
{ "code": "4/0Ab...", "state": "3fa85f64-5717-4562-b3fc-2c963f66afa6" }
```

**200**
```json
{ "connected": true, "connected_at": "2026-07-31T09:00:00Z" }
```

**400** — `state` doesn't match a pending attempt for the calling user (expired, already used,
or forged), or the token exchange with Google failed. `{"detail": "Could not complete calendar connection"}`
— deliberately generic; never echoes Google's own error body, which can contain the
`code`/`code_verifier` context (never log or return the raw code/verifier either, per spec
FR-005).

## `POST /disconnect`

No request body. Deletes the connection and (per FR-013) any picked event.

**200**
```json
{ "connected": false }
```
Idempotent — disconnecting an already-disconnected user still returns `200`, not `404`.

## `GET /events`

Only meaningful when connected; returns the next 7 days, capped at 20, from the primary
calendar (research.md §4), ordered by start time.

**200**
```json
{
  "events": [
    { "google_event_id": "abc123", "title": "Dinner with Sam",
      "start": "2026-08-01T19:30:00Z", "location": "Tanto" }
  ]
}
```
Empty `events: []` is a valid 200 (the connected-empty state) — not a 404.

**409** — not connected. `{"detail": "Calendar not connected"}`. The frontend never calls this
route without first checking `GET /connection`, but the backend enforces it anyway rather than
trusting the client's own state.

**502** — the live Google Calendar API call itself failed (rate limit, Google outage, or a
refresh-token failure distinct from "was never connected" — research.md §6 folds an *expired*
refresh into "disconnected" via `GET /connection`, so a `502` here specifically means "was
connected moments ago, but this particular request to Google failed"). Maps to the design
system's `calendar.error` state; the frontend's offline-precedence rule (design-system §6)
suppresses this in favor of the global offline banner when `navigator.onLine` is `false`.

## `GET /picked-event`

Used by `/recommend`'s context line.

**200**
```json
{ "picked": true, "event": { "google_event_id": "abc123", "title": "Dinner with Sam",
  "start": "2026-08-01T19:30:00Z", "location": "Tanto" } }
```
`event` is `null` when `picked` is `false`.

## `PUT /picked-event`

Upserts the snapshot (spec: "exactly zero or one per user").

**Request**
```json
{ "google_event_id": "abc123", "title": "Dinner with Sam",
  "start": "2026-08-01T19:30:00Z", "location": "Tanto" }
```

**200** — same shape as `GET /picked-event`'s `200`.

## Behavioral guarantees

- Every route's `user_id` comes from `get_current_user_id` (feature 003) — never a request
  body or query parameter, matching `closet.md`'s existing convention.
- Ownership is enforced twice: the repository's `WHERE user_id = :caller_id` (the real
  guarantee for this backend's own bypass-privileged connection) and RLS on all three tables
  (the convention, proven independent of that connection — `research.md` §9,
  `test_calendar_rls.py`).
- No route response, and no error `detail` string on any route, ever contains
  `access_token`/`refresh_token`/`code`/`code_verifier` in any form (spec FR-005).
- Response models are Pydantic; the frontend consumes only `openapi-typescript`-generated
  types (Constitution VII) — no hand-written duplicate of any shape above.
