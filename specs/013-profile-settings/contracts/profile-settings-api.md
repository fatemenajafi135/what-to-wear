# Contract: Profile & Settings API

All routes are under `api/v1/routes/profile.py`, mounted at `/api/v1/profile`, and require the
existing `get_current_user_id` bearer-token dependency (feature 003) — a missing/invalid token
yields `401` exactly as `whoami` already does. The frontend never hand-writes these shapes; it
imports the types this contract describes from `frontend/lib/api/schema.d.ts`, generated from
the backend's live `/openapi.json` (research.md §2). This document is the human-readable
mirror of that generated contract, not a second source of truth for it.

## `GET /api/v1/profile`

Returns the caller's full profile — the saved row if one exists, or all-default values if it
doesn't (FR-015; no 404 for "no profile yet").

**Response 200** (`ProfileResponse`):

```json
{
  "style_tags": [],
  "colour_tags": [],
  "brands_to_avoid": [],
  "body_shape": null,
  "gender": null,
  "birth_date": null,
  "height": null,
  "top_size": null,
  "bottom_size": null,
  "shoe_size": null,
  "notifications_enabled": true
}
```

Used by both `/profile` (three summary cards) and `/profile/settings` (all five sections'
initial/saved state) — one shared fetch, no per-section GET.

## `PATCH /api/v1/profile/style-preferences`

Whole-section replace (Edit/Done semantics — the request always carries all three fields).

**Request** (`StylePreferencesUpdate`):

```json
{
  "style_tags": ["Classic", "Minimal"],
  "colour_tags": ["Neutral tones"],
  "brands_to_avoid": ["Brand X"]
}
```

**Response 200**: the updated `ProfileResponse` (full profile, so the frontend can trust the
server's normalized values — e.g. de-duplicated `brands_to_avoid` — without a second GET).

**422**: any `style_tags`/`colour_tags` value outside its fixed vocabulary.

## `PATCH /api/v1/profile/body-size`

**Request** (`BodySizeUpdate`):

```json
{
  "body_shape": "hourglass",
  "gender": "woman",
  "birth_date": "1990-05-12",
  "height": "5 ft 6 in",
  "top_size": "M",
  "bottom_size": "8",
  "shoe_size": "8"
}
```

Any field may be `null` (not yet set). **Response 200**: updated `ProfileResponse`.

**422**: `body_shape`/`gender` outside their fixed vocabularies, `top_size`/`bottom_size`
outside their option lists, or `birth_date` in the future (spec.md User Story 3, Acceptance
Scenario 3).

## `PATCH /api/v1/profile/notifications`

No Edit/Done — commits immediately on toggle.

**Request** (`NotificationsUpdate`): `{ "notifications_enabled": false }`

**Response 200**: updated `ProfileResponse`.

## Not a backend route: Account (email)

Per research.md §3, editing the Account email calls Supabase Auth's `updateUser({ email })`
directly from the frontend — no `/api/v1/profile/account` route exists. `GET /api/v1/profile`
does not return an email field; the frontend reads the current email from the Supabase Auth
session it already holds.

## Not a backend route: Connected accounts

Static render — Google Calendar always shown disconnected/inert (feature 012's scope), Weather
services always shown "Coming soon". No field, no endpoint.

## Error shape (shared with the rest of the backend)

`422` uses FastAPI's default validation-error body (Pydantic's `detail` array) — no custom
error envelope introduced. `401` matches `whoami`'s existing behavior exactly (same response
for missing token, malformed token, and invalid signature). A `5xx` or a network failure is
what the frontend maps to the shared `settings.error.body`/`.cta` state (design-system §6);
`offline` is detected client-side via `navigator.onLine`, independent of any response.
