# Research: Closet (read)

## 1. RLS enforcement — the backend's own connection bypasses it

**Finding.** The local Supabase stack's pooler tenant `pooler-dev` (the one `DATABASE_URL`
in `backend/.env` connects through, per `notes/run-locally.md`) authenticates as Postgres
role `postgres`. Querying the running stack directly confirms:

```
 rolname  | rolsuper | rolbypassrls
----------+----------+--------------
 postgres | f        | t
```

`postgres` has `BYPASSRLS`. **Row-level security is a no-op for any query issued over the
backend's own connection**, regardless of what policies exist or whether `auth.uid()`
resolves correctly — Postgres skips RLS evaluation entirely for a bypass-privileged role.
`0001_init.sql`'s RLS-convention comment ("a backend that queries Postgres directly must
establish that [JWT] context itself... for these policies to evaluate correctly") is
technically incomplete: establishing the JWT context is necessary but not sufficient, because
the role itself bypasses the check before the context would ever be consulted.

**Decision — layered enforcement, not a single mechanism:**

1. **Query level is the live guarantee for this feature's actual traffic.** Every repository
   read filters `WHERE user_id = :caller_id` explicitly. This is what actually protects data
   returned by the FastAPI backend today.
2. **RLS ships anyway, correctly, as the convention every later table copies** — and as
   defense-in-depth for any access path that does NOT go through the bypass-privileged
   pooler role (Supabase Studio using the anon/authenticated key, PostgREST's Data API, a
   future serverless function, or a future migration of the backend off the bypass role).
   Writing it now, even though the app's own connection doesn't exercise it, is cheaper than
   retrofitting it once other tables assume it works.
3. **The isolation test proves the policy itself, independent of the app's bypass-privileged
   connection** — see §2. Testing through the app's own session would give a false pass: the
   query-level filter alone would make the test succeed even if the RLS policy were missing
   or wrong, since the same bypass role that skips RLS is also the role every other repository
   test runs under.

**Alternatives considered:**
- *Reconfigure the pooler tenant to authenticate as a non-bypass role for the app itself.*
  Rejected for this feature: changes `infra/supabase/config.toml`'s pooler tenant and the
  backend's `DATABASE_URL` shape project-wide, well beyond a single feature's blast radius,
  for a local-only single-developer stack where the query-level filter already provides the
  real guarantee. Worth revisiting before a multi-tenant production deployment, but that is a
  cross-cutting infra decision, not this feature's to make unilaterally.
- *Skip RLS entirely since the backend bypasses it anyway.* Rejected — directly contradicts
  the handoff's explicit instruction to establish the RLS convention, and would leave every
  non-backend access path (Studio, PostgREST, a future edge function) completely unprotected.
- *Trust RLS alone and drop the query-level filter.* Rejected — given finding #1, this would
  ship a closet with **no working per-user isolation at all** over the app's real traffic.
  "Belt and braces" in the handoff is doing real work here, not being cautious for its own
  sake.

## 2. Proving RLS isolation without the bypass role

**Decision.** The isolation test connects directly to the local Postgres instance (port
`54322`, not the pooler) as the `authenticator` role — the one Postgres role in the local
stack that can log in, does **not** bypass RLS, and is a member of `authenticated`/`anon`/
`service_role` (confirmed via `pg_auth_members`) — then issues `SET ROLE authenticated` and
`SELECT set_config('request.jwt.claim.sub', :user_id, true)` before running a raw,
unfiltered `SELECT * FROM wardrobe_items` for each of two seeded users. This is the same
mechanism PostgREST uses per-request; using it directly from a test proves the policy itself,
with no query-level filter in the way to produce a false pass.

`auth.uid()`'s actual local definition (read from `pg_proc`) checks
`current_setting('request.jwt.claim.sub', true)` first, falling back to the `sub` key of
`request.jwt.claims` JSON — so setting the scalar `request.jwt.claim.sub` GUC is sufficient
and is the simpler of the two paths it supports.

**Alternatives considered:**
- *Prove isolation by calling the FastAPI routes as two different users and asserting each
  only sees their own items.* Valuable and included as an integration test, but insufficient
  alone per §1 — it would pass identically whether or not the RLS policy exists, since the
  query-level filter is what it's actually exercising. Kept as a complementary test of the
  route's query-level intent, not a substitute for the RLS-specific test.
- *Stand up a second Postgres role dedicated to tests only.* Unnecessary — `authenticator`
  already exists in the stock local Supabase stack for exactly this purpose (it's what
  PostgREST itself authenticates as) and needs no new infra.

## 3. Catalog vs wardrobe — one table or two

**Decision.** Two tables: `wardrobe_items` (owned, one row per item per user) and
`catalog_items` (shared, no owner). `wardrobe_items.catalog_item_id` is a nullable FK to
`catalog_items.id` (`on delete set null`) — matching the legacy checklist's
`catalog_item_id` column, which only makes sense if catalog items are their own addressable
rows rather than a `user_id IS NULL` special case in the same table.

**RLS, decided explicitly per the handoff's instruction:**
- `wardrobe_items`: RLS enabled; a single `for all using (auth.uid() = user_id) with check
  (auth.uid() = user_id)` policy, following `0001_init.sql`'s own documented convention
  exactly (`<table>_modify_own`), scoped down to the `select` this feature needs — write
  policies are harmless to include now (`for all`) since no route in this feature performs a
  write, and it saves feature 005 from having to add the policy later.
- `catalog_items`: RLS enabled; a single `for select using (true)` policy restricted to the
  `authenticated` role (`to authenticated`) — every signed-in user reads the whole catalog,
  nobody owns a row, and no insert/update/delete policy exists at all in this feature (catalog
  population is out of scope; only a bypass-privileged role — a seed script or migration —
  can write to it until a feature explicitly owns catalog management).

**Alternatives considered:**
- *Single `items` table with nullable `user_id`.* Rejected — makes the RLS policy itself more
  complex (`user_id IS NULL OR auth.uid() = user_id`, which is a materially different and
  easier-to-get-wrong guarantee than two simple policies), and contradicts the legacy
  checklist's separate `catalog_item_id` FK column, which implies catalog rows have their own
  identity.
- *No catalog table in this migration; stub `list_catalog_items()` some other way.* Rejected
  — the Protocol requires a real `list_catalog_items()` method, and the RLS access-rule
  difference the handoff asks for can't be "decided explicitly" without a table whose policy
  differs.

## 4. `name` / `notes` — resolved in `/speckit-clarify`

Both added as new optional fields (`str | None = None`) on `WardrobeItem` (`schema.py`),
additive-only. No eval-harness regression: neither field is read by any existing scoring,
retrieval, or pipeline code, and the fixture-backed repository's 40-item corpus simply leaves
both `None`, which is valid per the field's optionality. Mirrored onto `WardrobeItemPatch`
for consistency (feature 005's edit path), since the two models already mirror each other
field-for-field and leaving one silently behind its sibling would be a foreseeable near-term
inconsistency this feature can prevent for free.

## 5. Pagination — protocol stays untouched, the route paginates

**Finding.** `ports.ClosetRepository.list_wardrobe_items(user_id) -> list[WardrobeItem]` takes
no page/limit parameters, and the handoff is explicit: do not invent an interface. The AI
pipeline's own callers (`context_assembler.load_wardrobe`, `graph.verify_grounding`) need the
**full** wardrobe every time — a paginated repository method would silently break them if
ever reused there.

**Decision.** The repository method is unpaginated, exactly matching the Protocol. The new
HTTP route applies category filtering and page-size-20 slicing itself, in Python, over the
list the repository returns. At this project's real scale (a personal closet, tens to low
hundreds of items) this is not a performance concern; at a scale where it became one, the fix
is a second, route-specific repository method — not a Protocol change — since the Protocol is
governed by what the AI pipeline needs, not by what one HTTP route needs.

**Page size: 20**, resolved in `/speckit-clarify`, defined as `WTW_CLOSET_PAGE_SIZE` (a
config constant, not a literal, matching `docs/design-decisions.md` §11's `wardrobeMinItems`
precedent for how this project treats UI-visible numeric thresholds).

## 6. Item detail — an extra repository method outside the Protocol

**Decision.** The concrete database-backed repository class gets one method beyond what
`ports.ClosetRepository` requires: `get_wardrobe_item(user_id, item_id) -> WardrobeItem |
None`, a single-row, indexed `WHERE user_id = :user_id AND id = :item_id` query. Python
`Protocol`s are structural — a concrete class satisfying a Protocol is free to expose
additional methods the Protocol doesn't require, and nothing forbids the item-detail route
from calling one. The alternative (fetching the full wardrobe list and filtering in Python
for one item) works but does a full-table-for-this-user scan for a single-row lookup and
still has to re-derive "not found vs not mine" by hand; a dedicated indexed query is both
simpler and correctly O(1) instead of O(n).

**Alternatives considered:**
- *Add `get_wardrobe_item` to the Protocol itself.* Rejected — the AI pipeline has no
  single-item lookup need today (Quality Bar: no speculative interface surface), and widening
  a Protocol feature 007 already shipped and the whole pipeline consumes is out of this
  feature's remit without a measured need driving it.

## 7. No ORM layer — SQLAlchemy Core `text()`, matching existing precedent

**Decision.** The repository issues parameterized `sqlalchemy.text()` SQL directly over the
`Session` `core/db.py` already provides, mapping rows to `WardrobeItem` by keyword. No
declarative ORM base or `Table` metadata layer is introduced.

**Rationale.** Nothing in this codebase uses SQLAlchemy's ORM today — `main.py`'s health
check already uses raw `text("SELECT 1")` — so a full declarative layer for one table would
be new, unjustified structure (Quality Bar: introduced only when there's a measured problem).
Two straightforward tables with simple filters don't have one. If a third table's repository
later needs query composition an ORM would meaningfully simplify, that's the point to
introduce it — not preemptively here.

## 8. `frontend/lib/api/` — first consumer of generated OpenAPI types

**Finding.** No frontend code calls the FastAPI backend yet (`003-auth`'s `whoami` route is
proof-of-concept only, never called from the UI) and no OpenAPI type-generation tooling
exists in the repo. `specs/002-backend-foundation/plan.md` explicitly deferred this: "Full
OpenAPI-generated frontend types become relevant once a frontend consumes a backend route,
starting at feature 004." This is that feature.

**Decision.** `openapi-typescript` (dev dependency) generates `frontend/lib/api/schema.d.ts`
from the backend's `/openapi.json`, committed to the repo like a migration file — regenerated
by a `generate:api-types` npm script whenever backend routes change, not at CI/build time
(CI has no live backend to query, matching how `infra/supabase/migrations/` are committed,
generated-once artifacts rather than built fresh every run). `openapi-fetch` (its companion,
minimal-runtime typed-client library) wraps `fetch` against the generated `paths` type in a
thin `frontend/lib/api/client.ts`, attaching the current Supabase session's access token as
the `Authorization` bearer header. No hand-written duplicate response type is added anywhere
on the frontend (Principle VII).

**Alternatives considered:**
- *Hand-write a `ClosetItem` TypeScript interface mirroring the Pydantic response model.*
  Rejected outright — the exact hand-maintained duplicate Principle VII prohibits.
  Constitution VII names this as its reason for the OpenAPI-generation requirement.
- *A heavier generated client (`orval`, full `openapi-generator` codegen with request
  functions per operation).* Rejected as more machinery than one feature with two GET routes
  needs; `openapi-typescript` + `openapi-fetch` is the minimal pairing that still satisfies
  Principle VII, and is easy to grow into if later features add more routes.

## 9. The global offline banner doesn't exist yet

**Finding.** `design/design-system.md` §6's offline precedence rule ("suppress the
screen-level error state and rely on the global banner") presumes a persistent, app-shell-level
offline banner already exists. It doesn't — `app/(app)/layout.tsx` mounts only `TabBar` and
`FocusOnNavigate`; nothing renders `Banner` anywhere, and no `navigator.onLine` tracking
exists in the frontend at all yet.

**Decision.** Add the minimal global piece this feature's own requirement depends on: a small
`useOnlineStatus()` hook (window `online`/`offline` events + `navigator.onLine`) and a
`Banner variant="offline"` mounted once in `app/(app)/layout.tsx`, shared app-shell chrome
already common to every authenticated route. This is not new screen-specific work — it is the
one piece of infrastructure that has to exist for FR-008 (suppress screen-level error while
offline) to be meaningfully implementable or testable at all, and it costs one hook plus one
existing component mounted in one already-shared file.

**Alternatives considered:**
- *Build the offline banner scoped to `/closet` only.* Rejected — contradicts design-system
  §6, which specifies the banner as global/persistent across screens, and would mean the very
  next screen to need it (any of 005-013) reimplements the same hook independently.
  Placing it in the shared authenticated-app layout is the smallest change that is still
  correct per spec, not scope creep into unrelated screens' content.
