# Tasks: Profile and Settings

**Input**: Design documents from `/specs/013-profile-settings/`
**Prerequisites**: plan.md, research.md, data-model.md, contracts/profile-settings-api.md, quickstart.md

**Tests**: Included — this codebase has an established pytest/Vitest convention (459 backend
tests green today) and the handoff's Definition of Done explicitly requires a proven RLS test,
so test tasks are in scope, not optional here.

**Organization**: Tasks are grouped by user story from spec.md (US1-US5, priority order) so
each phase is an independently testable increment, per each story's own "Independent Test" in
spec.md.

---

## Phase 1: Setup

- [ ] T001 [P] Add `openapi-typescript` devDependency and a `generate:api` script (reads
      `http://localhost:8000/openapi.json`, writes `frontend/lib/api/schema.d.ts`) to
      `frontend/package.json`, per research.md §2.
- [ ] T002 [P] Add `frontend/lib/api/schema.d.ts` to `.gitignore` (generated, not committed).

---

## Phase 2: Foundational (blocking prerequisites for all user stories)

**These tasks must complete before any user-story phase below**, since every story reads
and/or writes `user_profile` through the same table, backend routes, and typed frontend client.

- [ ] T003 Write `infra/supabase/migrations/0003_user_profile.sql`: create `user_profile`
      table exactly per data-model.md (columns, defaults, `unique(user_id)`, FK to
      `auth.users(id) on delete cascade`), attach `public.set_updated_at()` (from
      `0001_init.sql` — do not write a second trigger function), enable RLS, and add the two
      policies (`user_profile_select_own`, `user_profile_modify_own`) from data-model.md.
- [ ] T004 Run `cd infra && npx supabase db reset` and confirm `0003` applies cleanly after
      `0001_init.sql` from an empty database (quickstart.md §1). Depends on: T003.
- [ ] T005 [P] Create `backend/src/whattowear/models/user_profile.py` — SQLAlchemy model
      matching data-model.md's `user_profile` columns exactly.
- [ ] T006 [P] Create `backend/src/whattowear/schemas/profile.py` — Pydantic models
      `ProfileResponse`, `StylePreferencesUpdate`, `BodySizeUpdate`, `NotificationsUpdate` per
      contracts/profile-settings-api.md, with validators for: `style_tags`/`colour_tags`
      fixed-vocabulary membership, `body_shape`/`gender` fixed-vocabulary-or-null,
      `top_size`/`bottom_size` fixed-option-list-or-null, `birth_date` not in the future,
      `brands_to_avoid` trimmed/de-duplicated/non-empty-string.
- [ ] T007 Create `backend/src/whattowear/repositories/profile_repository.py` — all DB access
      for this table: `get_or_default(session, user_id)` (returns defaults if no row),
      `upsert_style_preferences(...)`, `upsert_body_size(...)`, `upsert_notifications(...)`
      (each an `insert ... on conflict (user_id) do update`, scoped by the caller's
      JWT-verified `user_id` — the enforcement that actually protects data per research.md
      §1). Depends on: T005.
- [ ] T008 Create `backend/src/whattowear/api/v1/routes/profile.py` — `GET /profile`,
      `PATCH /profile/style-preferences`, `PATCH /profile/body-size`,
      `PATCH /profile/notifications`, each behind `Depends(get_current_user_id)` exactly like
      `whoami.py`. Depends on: T006, T007.
- [ ] T009 Wire the profile router into `backend/src/whattowear/main.py`
      (`app.include_router(profile_router, prefix="/api/v1")`). Depends on: T008.
- [ ] T010 [P] Write `backend/tests/unit/test_profile_schemas.py` — vocabulary validation,
      future-birth-date rejection, brands-to-avoid trim/dedupe/empty-string rejection. Depends
      on: T006.
- [ ] T011 [P] Write `backend/tests/integration/test_user_profile_rls.py` — opens its own
      Postgres connection as the `authenticated` role with `SET LOCAL request.jwt.claims` set
      to two distinct user ids in turn, inserts a row per user directly, and asserts user A's
      session cannot `SELECT` user B's row. This connection is separate from the app's
      SQLAlchemy session — it must not go through `core/db.py`'s pooled engine, per research.md
      §1's "false-positive proof" warning. Depends on: T004.
- [ ] T012 [P] Write `backend/tests/integration/test_profile_routes.py` — `GET` returns
      all-defaults for a brand-new user (no 404), a `PATCH` persists and is reflected on the
      next `GET`, missing/invalid bearer token yields `401`, out-of-vocabulary values yield
      `422`, and — proving SC-004 at the route level, not just the DB level (T011 is the DB
      proof) — two different valid tokens each see and persist only their own independent
      profile, never each other's. Depends on: T009.
- [ ] T013 Create `frontend/lib/api/client.ts` (thin typed `fetch` wrapper: attaches the
      current Supabase session's access token as `Authorization: Bearer`, throws on non-2xx,
      types its return against `frontend/lib/api/schema.d.ts`) and `frontend/lib/api/profile.ts`
      (`getProfile`, `updateStylePreferences`, `updateBodySize`, `updateNotifications`).
      Depends on: T001, T009 (needs a running backend to generate against once, per
      quickstart.md §4).

---

## Phase 3: User Story 1 - View profile (Priority: P1) 🎯 MVP

**Goal**: A signed-in user opens `/profile` and sees three cards (Account, Style preferences,
Body & size) plus a gear icon to Settings and working sign-out.

**Independent Test** (spec.md): Sign in, navigate to `/profile`, confirm the three cards (or
their loading/error/empty state), the gear icon, and sign-out all work.

- [ ] T014 [P] [US1] Replace the stub `frontend/app/(app)/profile/page.tsx`: visually-hidden
      `<h1>Profile</h1>` (`tabIndex={-1}`, focused on navigation per design-system §8), gear
      `IconButton` to `/profile/settings` (existing, keep), "Sign out" `Button` (existing, keep
      unchanged per handoff — don't rebuild it), and three `<h2>`-headed cards: **Account**
      (email, from the Supabase Auth session), **Style preferences** (style tags + colour tags
      only, per research.md §4), **Body & size** (whichever of body shape / gender / birth date
      / height / sizes are set; omit unset fields' rows). Fetches via
      `frontend/lib/api/profile.ts`'s `getProfile`. Update
      `frontend/app/(app)/profile/page.module.css` for the layout (stacked mobile, 2-col
      tablet with 3rd card wrapping, 3-in-a-row ~340px desktop, per design-system §5). Depends
      on: T013.
- [ ] T015 [US1] Add loading (skeleton), error (`profile.error.body`/`.cta` + retry), and
      offline (suppress the screen error per §6's "offline wins for messaging", disable no
      actions since Profile has none to disable) states to the same file. Depends on: T014.
- [ ] T016 [P] [US1] Write a frontend test (`frontend/app/(app)/profile/page.test.tsx` or
      colocated per this repo's existing convention — check `SignInForm.test.tsx` for the
      pattern) covering: three cards render with data, with defaults (no profile yet), the
      error state + retry, and the gear icon's link target.

**Checkpoint**: `/profile` is fully usable standalone (reads only — Settings not required to
exist yet for this phase's own test to pass, though the gear icon will 404 until Phase 4).

---

## Phase 4: User Story 2 - Declare style preferences (Priority: P1)

**Goal**: Style tags, colour tags, and brands-to-avoid are editable via Edit/Done and persist.

**Independent Test** (spec.md): Open Settings, select Style preferences, Edit, change values,
Done, reload, confirm persistence.

- [ ] T017 [US2] Replace the stub `frontend/app/(app)/profile/settings/page.tsx` with the
      shared Settings shell: `TopHeader title="Settings" backHref="/profile"`, an in-page
      section switcher over the five section keys (not sub-routes, per FR-003), a
      `useState`-held `activeSection`, loading/error/offline states shared across sections
      (fetches the whole profile once via `getProfile`), and the responsive layout: stacked on
      mobile/tablet (pushed section-detail-only view), a 320px fixed narrow list pane beside
      the detail pane at 1024px+ (design-system §5's two-pane rule). Update
      `frontend/app/(app)/profile/settings/page.module.css` accordingly. Renders only the
      Style preferences section's content for now (others added in later phases). Depends on:
      T013.
- [ ] T018 [US2] Create
      `frontend/app/(app)/profile/settings/sections/StylePreferencesSection.tsx`: style tags as
      multi-select `Chip`s (Classic, Minimal, Bold, Casual, Edgy), colour tags as multi-select
      `Chip`s (Neutral tones, Jewel tones, Pastels, Monochrome, Earth tones), brands-to-avoid as
      `TagInput` — all pre-filled from the saved `ProfileResponse`. Edit/Done: "Edit" copies
      saved values into local draft state and reveals the controls; "Done" calls
      `updateStylePreferences` and replaces the saved state with the response; navigating away
      (unmount) without Done discards the draft (FR-011) — no local-storage persistence of an
      abandoned draft. Depends on: T017.
- [ ] T019 [P] [US2] Write `StylePreferencesSection.test.tsx`: pre-fill on Edit, Done persists
      and returns to read state, abandoning edit (simulate navigating away) discards the draft,
      empty brands-to-avoid list is a valid saved state (spec.md edge case).

**Checkpoint**: Settings shell exists and one full section (Style preferences) works
end-to-end, independent of US3-US5.

---

## Phase 5: User Story 3 - Declare body & size details (Priority: P1)

**Goal**: Body shape, gender, birth date, and sizes are editable via Edit/Done and persist
together.

**Independent Test** (spec.md): Open Body & size, edit every field, save, reload, confirm all
persist, including the illustrated body-shape selection.

- [ ] T020 [P] [US3] Create `frontend/components/ui/BodyShapePicker/BodyShapePicker.tsx` — the
      one net-new form control (design-decisions.md has no existing illustrated single-select).
      Five options (Hourglass, Pear, Rectangle, Apple, Inverted triangle), each a filled
      geometric silhouette per the stroke/size spec recorded in design-decisions.md (32×44
      viewBox; 26×36px read-only display; 64×84px option box in the picker), single-select,
      horizontally scrollable option row, keyboard-operable (arrow keys or Tab+Enter — match
      the existing `Chip`/`Switch` keyboard convention), 44px+ hit area per option.
- [ ] T021 [US3] Create
      `frontend/app/(app)/profile/settings/sections/BodySizeSection.tsx`: `BodyShapePicker` for
      body shape; gender as single-select `Chip`s (Woman, Man, Non-binary, Prefer not to say);
      `DatePicker` for birth date with blur-triggered future-date validation
      (`field.required`-style copy per design-decisions §1.7's pattern, e.g. a new
      `field.birthDate.future` message: "Enter a date in the past."); `Select` for Height,
      Top size (XXS-XXXL), Bottom size (00-20), Shoe size. **Height's and Shoe size's exact
      option arrays are not specified anywhere in spec/plan/data-model** (only Top/Bottom size
      are pinned) — define a concrete, reasonable list for each directly in this file with a
      one-line comment noting it's this task's own choice, not sourced from the design system.
      Same Edit/Done draft-commit pattern as Style preferences; "Done" calls `updateBodySize`.
      Register this section in the Settings shell's switcher (T017). Depends on: T017, T020.
- [ ] T022 [P] [US3] Write `BodyShapePicker.test.tsx` (renders 5 options, single-select
      behavior, keyboard operability) and `BodySizeSection.test.tsx` (all fields persist
      together, empty birth date shows an empty state not an invalid date, future birth date
      blocks save with a validation error — spec.md's three acceptance scenarios for this
      story).

**Checkpoint**: Both P1 stories (US1, US2, US3) complete — this is the feature's MVP scope per
the handoff's stated priorities.

---

## Phase 6: User Story 4 - Update account email (Priority: P2)

**Goal**: A user can view and edit their account email; it persists across reload as the real
sign-in identity.

**Independent Test** (spec.md): Edit email to invalid format → validation error, no commit.
Edit to valid address → Done → persists across reload.

- [ ] T023 [US4] Create
      `frontend/app/(app)/profile/settings/sections/AccountSection.tsx`: `Input` (type="email")
      showing the current Supabase Auth session email; Edit/Done pattern where "Done" validates
      format on blur (`field.email.invalid` per design-decisions §1.7) then calls
      `supabase.auth.updateUser({ email })` directly (research.md §3 — no backend call, no new
      `user_profile` field) and shows the newly-requested address as current on success.
      Register this section in the Settings shell's switcher (T017). Depends on: T017.
- [ ] T024 [P] [US4] Write `AccountSection.test.tsx`: invalid format blocks Done with a
      validation error and no `updateUser` call; valid format calls `updateUser` and the
      section returns to read state showing the new value.

---

## Phase 7: User Story 5 - Connected accounts and notifications (Priority: P3)

**Goal**: Connected accounts renders Google Calendar disconnected/inert and Weather services
"Coming soon"; Notifications toggles and persists immediately, no Edit/Done.

**Independent Test** (spec.md): Connected accounts shows the specified disconnected/inert
appearance; Notifications toggle persists without a save step.

- [ ] T025 [P] [US5] Create
      `frontend/app/(app)/profile/settings/sections/ConnectedAccountsSection.tsx`: a static
      Google Calendar row in its disconnected appearance with an inert action (no `onClick`
      handler, or a handler that no-ops — feature 012 owns the real toggle, per handoff §7),
      and a Weather services row with a muted `Badge` "Coming soon", not interactive. No
      Edit/Done (nothing here is editable in this feature). Register in the Settings shell's
      switcher. Depends on: T017.
- [ ] T026 [US5] Create
      `frontend/app/(app)/profile/settings/sections/NotificationsSection.tsx`: a single
      `Switch` (`checked={notifications_enabled}`, default from the saved profile — `true` for
      a brand-new user per FR-009) that calls `updateNotifications` immediately on toggle, with
      no Edit/Done affordance at all (design-system §4's stated exception). Register in the
      Settings shell's switcher. Depends on: T017.
- [ ] T027 [P] [US5] Write `ConnectedAccountsSection.test.tsx` (Calendar row renders
      disconnected, its action is inert, Weather row shows "Coming soon" and isn't interactive)
      and `NotificationsSection.test.tsx` (toggle calls the update immediately, no Edit/Done
      controls rendered).

---

## Phase 8: Polish & Cross-Cutting Concerns

- [ ] T028 Add two new entries to `docs/design-decisions.md` resolving the design-system
      "Open questions" this feature touched: the body-shape illustration stroke/size spec, and
      the Settings Edit/Done toggle's label-only (no color/style change) visual treatment —
      content per research.md §5.
- [ ] T029 Add a short entry to `docs/design-decisions.md` recording the Profile "three cards"
      content decision (Account, Style preferences, Body & size) since design-system.md never
      names them — content per research.md §4.
- [ ] T030 Update `docs/ios-verification-backlog.md` with anything built blind for iOS in this
      feature (e.g. `BodyShapePicker`'s touch/scroll behavior on a real iOS device, the native
      `<input type="date">` and `<select>` picker UIs at this feature's specific field set)
      per the handoff §10.
- [ ] T031 Full keyboard-only and reduced-motion manual pass on both routes at 320/768/1024/1440
      in both themes, per quickstart.md §5 — fix any focus-order, `:focus-visible`, or
      focus-on-navigate defects found.
- [ ] T032 Run the full verification suite (quickstart.md §6: `pytest`, `ruff check`,
      `ruff format --check`, `mypy`, `lint-imports`, `eslint`, `tsc --noEmit`, `next build`,
      Vitest) and fix any regressions. Confirm the pre-existing 459 backend tests are still
      green.
- [ ] T033 Confirm no file under `backend/src/whattowear/memory/` was touched (handoff §6/§11)
      and no secret is present in the diff.

---

## Dependencies & Execution Order

- **Setup (Phase 1)** → **Foundational (Phase 2)**: no dependencies within Setup; Foundational
  tasks mostly chain (T003→T004; T005,T006 parallel →T007→T008→T009→T013).
- **User stories (Phases 3-7)** all depend on Foundational completing first (T001-T013).
- **US1 (Phase 3)** has no dependency on any other user story — it only reads.
- **US2 (Phase 4)** builds the Settings shell (T017) that **US3, US4, US5 (Phases 5-7) each
  depend on** — those three phases cannot start until T017 lands, but are independent of each
  other once it has (US3/US4/US5 could proceed in parallel after T017).
- **Polish (Phase 8)** depends on all prior phases.

## Parallel Execution Examples

- Within Foundational: T005 and T006 (different files, no shared dependency) can run together;
  once both land, T007 proceeds.
- Within Foundational: T010, T011, T012 (three independent test files) can be written in
  parallel once their respective implementation tasks land.
- Across stories, once T017 (Settings shell) is done: T020+T021 (US3), T023 (US4), and
  T025+T026 (US5) touch entirely separate section files and can proceed in parallel.

## Implementation Strategy

**MVP = Phases 1-3 (Setup, Foundational, US1)** gets `/profile` fully working standalone.
**Phases 1-5 (through US3)** deliver every P1 story — the handoff's stated core value
("declared taste is the data this feature exists to capture"). **Phases 6-7 (US4, US5)** round
out Settings per spec.md's own P2/P3 ordering and can ship in a follow-up slice if time runs
short — each is independently testable and does not block the others.
