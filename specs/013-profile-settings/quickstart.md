# Quickstart: Profile and Settings

Assumes the stack from `docs/handoffs/013-profile-settings.md` §2 is already running
(`supabase start`, backend `uvicorn`, frontend `next dev`). This guide validates the feature
end to end; it is not an implementation walkthrough — see `tasks.md` for that.

## 1. Schema reproduces from empty

```bash
cd infra && npx supabase db reset
```

Expect `0003_user_profile.sql` to apply cleanly after `0001_init.sql`, with no manual fixup.

## 2. RLS is real (not just written)

```bash
cd backend && uv run pytest tests/integration/test_user_profile_rls.py -v
```

Expect the test to open its own restricted-role connection (`SET LOCAL role authenticated;
SET LOCAL request.jwt.claims = ...`), insert rows for two distinct user ids, and prove user A's
session cannot `SELECT` user B's row. This is a different assertion from "the repository only
returns the caller's row" — it exercises the Postgres policy directly, per research.md §1.

## 3. Backend contract

```bash
uv run uvicorn whattowear.main:app --reload
curl -s localhost:8000/openapi.json | jq '.paths | keys' | grep profile
```

Expect `/api/v1/profile`, `/api/v1/profile/style-preferences`, `/api/v1/profile/body-size`,
`/api/v1/profile/notifications`. With a valid bearer token:

```bash
curl -s -H "Authorization: Bearer $TOKEN" localhost:8000/api/v1/profile
# → all-default ProfileResponse for a brand-new user (FR-015)

curl -s -X PATCH -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"style_tags":["Classic"],"colour_tags":[],"brands_to_avoid":[]}' \
  localhost:8000/api/v1/profile/style-preferences
# → ProfileResponse reflecting the change

curl -s -H "Authorization: Bearer $TOKEN" localhost:8000/api/v1/profile
# → the same change, persisted (FR-013)
```

## 4. Frontend types are generated, not hand-written

```bash
cd frontend && npm run generate:api-types   # backend must be running; renamed post-merge
                                             # with feature 004 (docs/design-decisions.md §17)
git diff --stat lib/api/schema.d.ts   # gitignored — this just confirms the script runs
npm run typecheck                     # profile.ts must compile against the generated schema
```

## 5. Manual pass — both screens, both themes, four widths (320/768/1024/1440)

- `/profile`: three cards (Account, Style preferences, Body & size) render with real or
  default values; gear icon reaches `/profile/settings`; sign-out still works.
- `/profile/settings`: all five sections switch in-page (URL doesn't change); at 1024px+ the
  section list becomes a 320px pane beside the detail pane (design-system §5).
- Per section except Notifications: Edit → change a value → Done → value persists across a
  reload. Edit → change a value → navigate to `/profile` without Done → return to
  `/profile/settings` → previous saved value is shown (FR-011).
- Notifications: toggling commits immediately, no Edit/Done, persists across reload.
- Connected accounts: Google Calendar renders disconnected and inert; Weather services shows
  "Coming soon" and is not interactive.
- Trigger loading (throttle network), error (stop the backend mid-session), and offline
  (devtools offline mode) on both routes; confirm the shared `settings.error.body`/`.cta` copy
  and the global offline banner, and that offline suppresses the screen-level error per
  design-system §6's "offline wins for messaging" rule.
- Keyboard-only pass: focus moves to each screen's `<h1>` on navigation; visible
  `:focus-visible` ring on Tab, none on mouse click; body-shape picker and gender chips are
  operable via keyboard.

## 6. Full verification suite

```bash
cd backend  && uv run pytest && uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run lint-imports
cd ../frontend && npm run lint && npm run typecheck && npm run build && npm test
```

Expect the pre-existing 459 backend tests still green, plus this feature's new tests.
