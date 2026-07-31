# Research: Profile and Settings

## 1. RLS on `user_profile`: the backend's own connection bypasses it

**Finding**: `0001_init.sql` documents the RLS convention (`auth.uid() = user_id` policies)
and explicitly defers "the mechanism that populates `auth.uid()` for a request made through
the backend's own connection" to feature 003. Feature 003's `auth.py` verifies the JWT and
returns the `sub` claim, but never establishes that claim as Postgres session state, and
`core/db.py`'s `DATABASE_URL` connects as `postgres.pooler-dev` — the Postgres **superuser**
role via Supavisor, which bypasses RLS unconditionally regardless of any policy. The frontend
never queries Supabase tables directly (`grep` across `frontend/` found no `.from(...)` calls
outside the Supabase Auth client) — the only path to `user_profile` is through this backend.
So today, an RLS policy on any per-user table is real-but-inert from the app's own connection;
it only matters against a hypothetical future direct-PostgREST or leaked-anon-key path.

**Decision**: Write the RLS policy per the documented convention (defense-in-depth, and
required by the constitution regardless of whether the app's own connection currently
exercises it). Enforce the actual, working isolation guarantee at the **repository layer** —
every query scoped by `user_id = :current_user_id` from the JWT-verified caller, which is the
same pattern every other authenticated route in this codebase already relies on implicitly.
Prove the RLS policy itself (not the repository's `WHERE` clause) with a dedicated test that
opens its own Postgres connection as the `authenticated` role with `request.jwt.claims` set
via `SET LOCAL`, independent of the app's SQLAlchemy session — the only way to exercise the
policy honestly rather than produce a false-positive "proof" that passes even if the policy
were wrong (a failure mode the feature 013 handoff explicitly names: "a policy written but
never exercised is a policy that does not work"). Record the auth.uid()-wiring gap here and
in the completion report as a flagged, out-of-scope cross-cutting issue for a future
infra-scoped feature — not something to fix inside a Settings slice, and not something to
silently skip either.

**Rationale**: This matches the standard "service-role backend + RLS as defense-in-depth"
shape Supabase itself documents for apps with a trusted custom backend. It also avoids
touching `core/db.py`/`auth.py` — shared plumbing feature 004 depends on and is developing
against in parallel elsewhere; a collision there is a worse outcome than documenting a gap.

**Alternatives considered**:
- *Wire real per-request `auth.uid()` now (switch role, `SET LOCAL request.jwt.claims` per
  request in `get_session()`).* Rejected for this feature — correct long-term fix, but
  cross-cutting shared-plumbing surgery that belongs in its own infra-scoped change, reviewed
  and tested on its own, not bundled into a Settings PR.
- *Skip the RLS policy entirely since it's inert from the app's connection today.* Rejected —
  the constitution and handoff both require it as the per-user-table convention; "inert from
  one path today" isn't "worthless" once the future direct-access path exists, and it's the
  gate every table since `0001_init.sql` must satisfy.
- *"Prove" isolation using the app's own session (superuser) hitting two users' rows.*
  Rejected — this is exactly the false-positive the handoff warns against: it would pass even
  with a missing or wrong policy, since the superuser role never evaluates RLS at all.

## 2. Frontend consuming backend data — no existing contract-generation path

**Finding**: No prior feature needed the frontend to call a FastAPI product endpoint (003's
Supabase Auth calls go straight to Supabase, not through this backend). There is no
OpenAPI-type-generation tooling in `frontend/package.json` yet, so Principle VII's "frontend
consumes generated OpenAPI types, no hand-written duplicates" has no established path.

**Decision**: Add `openapi-typescript` as a frontend devDependency with a `generate:api`
script that reads the backend's `/openapi.json` (backend must be running locally) and writes
`frontend/lib/api/schema.d.ts` (gitignored, regenerated on demand — same "generated, not
committed" posture as any codegen output). A small hand-written `lib/api/client.ts` wraps
`fetch`, attaches the Supabase session's bearer token, and types its return value against the
generated schema; `lib/api/profile.ts` holds the four profile-specific calls. Only the
generated file is exempt from "no hand-written duplicate" — `client.ts` is plumbing, not a
type duplicate.

**Rationale**: `openapi-typescript` is a types-only generator (no runtime client, no extra
runtime dependency) — the lightest tool that satisfies the constitution's actual requirement
(shared types, not a specific client library).

**Alternatives considered**:
- *A heavier generated-client library (`openapi-fetch`, `orval`).* Rejected as more than this
  feature's four endpoints need; types-only plus the existing thin `fetch` convention is
  proportionate.
- *Hand-write matching TypeScript interfaces.* Rejected — this is precisely the "hand-written
  duplicate" Principle VII prohibits, and it drifts the moment a Pydantic field changes.

## 3. Account email — Supabase Auth, not a new column

**Finding**: FR-013 requires the Account email to "survive... a new sign-in session," which
only holds if editing it changes the actual Supabase Auth identity (the value a new session's
JWT would carry), not a redundant copy. Feature 003 already wired Supabase Auth end to end
(sign-in, sign-out, password reset) and the frontend already holds a Supabase client
(`lib/supabase/client.ts`) capable of `auth.updateUser({ email })`.

**Decision**: Account's Edit/Done calls `supabase.auth.updateUser({ email })` directly from
the frontend — no new backend endpoint, no new `user_profile` column. This keeps `user_profile`
scoped exactly to declared taste + notification preference, matching the handoff's framing
("013 owns a new `user_profile` table" for *declared* data) and mirrors "sign-out already
exists from feature 003 — don't rebuild it."

**Rationale**: Consistent with feature 003 owning all identity/auth state; avoids a second,
inevitably-drifting source of truth for the account email.

**Alternatives considered**:
- *Store email in `user_profile` too, synced on save.* Rejected — two sources of truth for
  the same fact, and the "survives a new sign-in session" requirement is only trivially true
  if the session's own JWT is what changed, not a side table.

**Note on scope**: Supabase's email-change flow may require confirmation depending on project
config; this feature calls `updateUser` and displays the request as accepted (matching
acceptance scenario 2's "the new address is saved and shown as the current value") without
building a custom "pending confirmation" banner — that UX is Supabase Auth's existing
behavior, unchanged by this feature, and out of scope to redesign here.

## 4. Profile's "three cards" — contents not named anywhere

**Finding**: `design-system.md` says "three cards" three times (§2 type-scale note, §5
responsive table's "3rd card wraps", §8 "Profile's three cards get `<h2>` each") but never
names what the three are. `design/prototype/` (reference only) shows a materially different,
superseded split — Style preferences and Body & size as *editable* cards directly on its
"Profile" screen, with Account/Connected accounts/Notifications only reachable via its
separate "Settings" screen — which contradicts the current spec's "Settings has all five
sections, Profile has none of the controls" model and is therefore not load-bearing here.

**Decision**: Profile's three read-only summary cards are **Account** (email), **Style
preferences** (style tags + colour tags only — "Brands to avoid" omitted from the summary as
a third-level nested list would fit poorly in a compact card; the full picker lives in
Settings), and **Body & size** (body shape, gender, birth date, height, sizes — whichever of
these the user has set; unset fields simply don't render a row). Connected accounts and
Notifications are Settings-only, consistent with User Story 5 being explicitly the lowest
priority / thinnest-value section pair in spec.md.

**Rationale**: Account is the one thing Profile can show with zero new data modeling (it's
already available from the authenticated session) and gives the screen an identity anchor in
the absence of any specified header/avatar row in the current design-system text (the
prototype's avatar+name+email header is not mentioned anywhere in `design-system.md`'s current
Profile description, so it is not assumed here). Style preferences and Body & size are the
two sections spec.md itself calls "core declared-taste data this feature exists to capture"
(User Stories 2-3, both P1) — promoting them to Profile's summary is the natural complement to
that stated priority.

**Alternatives considered**:
- *Third card = Connected accounts or Notifications.* Rejected — both are explicitly the
  lowest-priority, thinnest sections (User Story 5); summarizing an inert calendar toggle or a
  single switch on the entry-point screen undersells the two sections spec.md prioritizes.
- *Mirror the prototype's Style + Body & size (only 2 cards, directly editable).* Rejected —
  contradicts the current design-system's "three cards" (stated three times) and its "Profile
  has no edit affordance, that's Settings' job" framing (gear icon → Settings, not inline
  edit).

## 5. Two design-system "Open questions" resolved here

Both are on `design-system.md`'s own admitted "Open questions" list (not spec ambiguities —
visual-detail gaps the doc says to "decide during build and move on").

**Body-shape illustrations** (stroke weight/size): five filled (not stroked) geometric
silhouettes — head as a circle, torso/hip shape as 1-2 polygons per option — at a 32×44
viewBox, rendered at 26×36px in the read-only summary and inside a 64×84px option box in the
edit-mode picker (`BodyShapePicker`), matching the proportions implied by the prototype's own
placeholder art (reference only, not copied — no `<svg>`/markup is reused, only the size
ratios). Recorded so a future pass doesn't have to re-derive it from scratch.

**Settings Edit/Done toggle visual treatment**: label-only swap ("Edit" ↔ "Done"); the
button's color/border/background stay identical in both states — no separate "editing" style.
Consistent with the design system's general minimalism (§5 of design-decisions.md: no
extra states invented beyond what a token already covers) and avoids inventing a new visual
state with no token backing it.
