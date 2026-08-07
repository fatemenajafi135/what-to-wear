# Handoff — Feature 003: Auth

**From:** tech lead · **Status:** ready to start · **Branch:** `feat/003-auth`, cut from
`rebuild`

This slice gates every authenticated screen in the product. Features 004 onward assume a
signed-in user exists and that the backend can prove who they are.

**This handoff assumes you are starting on a fresh machine and have not worked on this
repository before.** Section 2 gets you from nothing to a running stack.

---

## 1. Mission

Ship the four auth screens, real Supabase authentication, session persistence, route
protection, and the backend's ability to verify a caller's identity — so feature 004 can
simply ask "who is this?" and get an answer.

---

## 2. Setting up from scratch

### Prerequisites

| Tool | Version | Check |
|---|---|---|
| Docker | running daemon | `docker info` |
| `uv` | 0.11+ | `uv --version` |
| Node.js | 20+ | `node --version` |
| Git | 2.27+ | `git --version` |

### Clone and branch

```bash
git clone <repo-url> what-to-wear
cd what-to-wear
git checkout rebuild
git checkout -b feat/003-auth
```

⚠️ **`rebuild` is the trunk for this project, not `main`.** `main` is the old live
prototype and shares no history with `rebuild`. Never branch from `main`, never merge into
it, never push it.

### Start the local database

```bash
cd infra
npm install                 # installs the pinned Supabase CLI
npx supabase start          # Postgres + Auth + Storage in Docker
```

First run pulls several images and takes a few minutes. Leave it running.

### Backend

```bash
cd ../backend
uv sync
cp .env.example .env        # needs NO editing — the local values are already correct
uv run pytest               # expect 6 passed
uv run uvicorn whattowear.main:app --reload
```

In another terminal:

```bash
curl -s localhost:8000/health     # {"status":"ok"}
```

If that returns `503` with `failed_dependencies: ["database"]`, Supabase is not running.

### Frontend

```bash
cd ../frontend
npm ci
npm run dev                 # http://localhost:3000
```

You should see the app shell with a bottom tab bar. Resize past 768px and 1024px — the
chrome becomes a rail, then a sidebar. Visit `/dev/components` to see every existing
component in every state; **that catalogue is your component reference and everything you
need for the forms already exists there.**

### Credentials

**Email + password needs nothing.** Local Supabase provides auth out of the box, and
`.env.example` is already correct.

**Google OAuth needs a Google Cloud OAuth client ID and secret**, configured in
`infra/supabase/config.toml`. If you do not have one, build the OAuth path anyway — wire it,
type it, and leave it untestable locally. Say so in your report. Do **not** stub it out or
delete the button.

### Verify your setup before writing code

```bash
cd backend  && uv run pytest && uv run ruff check . && uv run mypy src && uv run lint-imports
cd ../frontend && npm run lint && npm run typecheck && npm run build && npm test
```

All green means the baseline is sound and anything that breaks later is yours.

---

## 3. How to run this

```
/speckit-specify → /speckit-clarify → /speckit-plan → /speckit-tasks
                 → /speckit-analyze → /speckit-implement
```

Spec Kit cuts `003-auth`. **Rename it immediately** — the repo also holds the old
prototype's branches and `003-mvp-app` is one of them:

```bash
git branch -m feat/003-auth
```

`plan-template.md` carries ten Constitution Check gates. Fill each one in; mark N/A with a
one-line reason where a principle genuinely does not apply. Merge back into `rebuild` by PR.

---

## 4. Read first

| # | Source | What to take |
|---|---|---|
| 1 | `.specify/memory/constitution.md` | Binding. **VII** (contracts), **VIII** (visual truth), **IX** (one codebase) apply. |
| 2 | `docs/design-decisions.md` **§12** | **The auth flow decision. Read this before designing anything.** |
| 3 | `docs/design-decisions.md` §1 | The form-control spec — `Input`, `Select`, validation copy. Already built; this is the contract. |
| 4 | `design/design-system.md` §4 (Auth stack), §5, §6 (Auth copy), §8 | Routes, states, verbatim copy, accessibility. |
| 5 | `docs/ios-verification-backlog.md` | What you must record rather than test. |
| 6 | `../app-legacy/backend/src/whattowear/auth.py` | Read-only reference for JWT verification. 70 lines. |

`design/prototype/` is reference only — read it to understand intent, **never copy code from
it**. Nothing under `_scaffolding/` may appear in the product.

---

## 5. In scope

### 5.1 Screens — four routes

Per `design-system.md` §4's auth stack. All copy is specified verbatim in §6; ship it
exactly.

| Route | Notes |
|---|---|
| `/signin` | Email + password, plus the Google button. Default when signed out. |
| `/signup` | Same shape. |
| `/forgot-password` | Has a **confirmation state, not a separate route**. |
| `/reset-password/:token` | Three states — **form**, **error** (expired link), **success**. Reachable only from the emailed link, never from in-app nav. |

Layout per §5: full-bleed `max-width: 360px` on mobile, same centred at tablet, and at
desktop it gains a `--color-surface` panel at `max-width: 400px`.

Accessibility per §8: the auth shell is `role="main"`, and **the wordmark is promoted to
`<h1>`** on Sign in and Sign up — those screens have no `TopHeader` to carry it.

Form buttons use `Button`'s **`stretch`** mode — 100% width, matching the input fields, at
every breakpoint (§5's button-width rule).

### 5.2 Session and routing

- Supabase client with **`flowType: 'pkce'`**.
- Session persists across reloads and app restarts.
- **Route protection**: unauthenticated visits to any authenticated route redirect to
  `/signin`; authenticated visits to an auth route redirect to `/recommend`.
- `/` redirects: signed-out → `/signin`, signed-in → `/recommend`. Feature 001 wired `/` to
  `/recommend` unconditionally — **you are replacing that** with the real rule.
- `/auth/callback` — the OAuth return route. An **app route**, never a Supabase-hosted page.
- Sign out, reachable from Profile.

### 5.3 Backend identity

Port and adapt `../app-legacy/backend/src/whattowear/auth.py`: verify the Supabase JWT's
signature locally and expose a FastAPI dependency returning the current user id.

Feature 004 depends on this existing. Add a protected example route so it is genuinely
exercised — not a route the product needs, just proof the dependency works end to end, with
tests for a valid token, a missing token and an invalid one.

The JWT secret comes from `npx supabase status`. Add it to `.env.example` as a placeholder,
**never a real value**.

---

## 6. Explicitly out of scope

Any closet, outfit, styling or calendar screen · Profile and Settings content beyond a sign-out
control (013) · password change, account deletion, data export — all deferred in
`known-gaps.md` §0.6 · email OTP and magic links (see §7) · service worker and offline (014) ·
any cloud Supabase project. **Local only.**

---

## 7. Decisions already made — do not relitigate

| Topic | Decision | Source |
|---|---|---|
| **Never send a magic link for sign-in** | On installed iOS the session lands in Safari's storage container and the app never sees it. Unfixable by configuration. | design-decisions §12 |
| Primary flow | Email + password. Google OAuth secondary. | §12 |
| Password minimum | **8 characters**, and raise Supabase's `password_min_length` to match so the server enforces what the client claims. | §1.7 |
| After password reset | Route to `/signin`. **Do not auto-sign-in** — that creates the cross-container handoff §12 exists to avoid, and it fails only on installed iOS. | §12 |
| Field validation | Fires on blur, never on keystroke; re-validates on change once a field has errored. Copy in §1.7. | §1.7 |
| Input font size | 16px at every breakpoint. Below that iOS Safari auto-zooms on focus. | §1.2 |
| Type scale | From design-decisions §6, **not** design-system §2, which is superseded. | §6 |

---

## 8. Traps

1. **Do not build new form components.** `Input`, `Textarea`, `Select`, `Button`, `Banner`
   and the rest already exist with full state matrices. See `/dev/components`. Building a
   second password field is the most likely waste in this slice.
2. **Form-level errors go in a `Banner`** with `variant="error"` above the first field —
   `auth.signin.error.body` and friends. Field-level errors go beneath their own field.
   They are different mechanisms; do not merge them.
3. **`/reset-password/:token` is not reachable from in-app navigation.** Do not add a link to
   it. It exists only as an email destination, and its three states are fully specified.
4. **The Google "G" button** is in the design but its exact treatment is an open question in
   `design-system.md`. Use the standard four-colour mark; if you deviate, record why in
   `docs/design-decisions.md`.
5. **`role="main"` on the auth shell and `<h1>` on the wordmark.** Easy to miss because
   there is no `TopHeader` on these screens to carry the heading.
6. **Do not weaken the redirect allow-list** to make OAuth work locally. If it will not work
   without a Google client ID, leave it and say so.
7. **`main` is the old prototype.** Never branch from it, merge into it, or push it.

---

## 9. Add to the iOS backlog

`docs/ios-verification-backlog.md` already lists four anticipated auth items (5–8). **Confirm
or correct them** once you know what you actually built, and add anything new.

You cannot test installed-iOS behaviour. Build to the spec, record it, move on — do not
block, and do not silently drop an iOS requirement because it is unverifiable.

---

## 10. Definition of done

- [ ] All four routes render every specified state, in both themes, at 320 / 768 / 1024 / 1440.
- [ ] Sign up → sign in → sign out → sign in again works against local Supabase.
- [ ] Session survives a full page reload.
- [ ] Route protection holds in both directions.
- [ ] Password reset completes end to end and lands on `/signin`, **not** inside the app.
- [ ] Backend rejects a missing token, an invalid token, and an expired one, with tests.
- [ ] Google OAuth is wired and PKCE-correct. Tested if you have a client ID; **clearly
      reported as untested if you do not.**
- [ ] Keyboard-only pass: every control reachable, focus ring on keyboard nav and absent on
      mouse click, focus moves to `<h1>` on navigation.
- [ ] `eslint`, `tsc --noEmit`, `next build`, Vitest, Playwright, `ruff`, `ruff format --check`,
      `mypy`, `pytest`, `lint-imports` — all clean.
- [ ] No secret anywhere in the diff. `.env.example` updated with placeholders only.
- [ ] iOS backlog updated.

---

## 11. If you hit a gap

`docs/design-decisions.md` has no open items. If you find something genuinely uncovered, **do
not invent a value and continue** — that is a Principle VIII violation. Add it to that file
with your reasoning and flag it in your report.

When you write `research.md`, the failure mode to guard against is not weak reasoning — it is
an **incomplete option list**. Feature 001 shipped a defect whose decision record was
well-argued but had never considered the option that turned out to be correct. When you write
"alternatives considered", ask what you have not listed.

## 12. Report back with

What you built · which Constitution Check gates you could not satisfy and why · the §10
checklist results · whether OAuth was actually tested or only wired · what you added to the
iOS backlog · anything you recorded in `design-decisions.md`.

**Do not mark an item done that you have not verified.** Say plainly what you skipped — a
report that admits two gaps is worth more than one that claims a clean sweep.
