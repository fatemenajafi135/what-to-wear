# Handoff — Feature 012: Calendar

**From:** tech lead · **Status:** ready to start · **Branch:** `feat/012-calendar`, cut from
`rebuild` · **Migration number: `0004`**

The third Wave A slice. Independent of the closet, so it runs alongside 004 and 013 — but it
has a **credential dependency** the other two don't. Read §2 before scheduling it.

**This handoff assumes you may be starting on a machine that has never worked on this
repository.** Section 3 gets you from nothing to a running stack.

---

## 1. Mission

A user connects Google Calendar, sees their upcoming events, and picks one to style for —
with that choice surfacing back on the Recommend screen.

---

## 2. ⚠ Read this before you start — the credential situation

This slice needs a **Google Cloud OAuth client** (client ID + secret) with Calendar scopes.
**One does not exist for this project yet.**

That same missing credential is why feature 003's Google sign-in button ships disabled —
`infra/.env` doesn't exist, so `config.toml`'s `env(SUPABASE_AUTH_EXTERNAL_GOOGLE_CLIENT_ID)`
resolves empty. **Creating one Google Cloud project with both sign-in and Calendar scopes
unblocks 003's button and this entire feature at once.** Worth doing before this slice starts,
if it can be.

**If you do not have one:** build everything anyway, exactly as feature 003 did. The
disconnected state, the permission primer, the event list, the empty state, the error state,
the picked-event context line and all the persistence are testable with fixture data. Only
the live OAuth round-trip is not.

**Wire it, leave it untestable, and say so plainly in your report. Do not stub the flow out,
delete the button, or fake a success path.** A fake success is worse than an honest gap,
because it looks finished.

Record every untestable item in `docs/ios-verification-backlog.md`'s spirit — but for this,
just be explicit in the report.

---

## 3. Setting up from scratch

### Prerequisites

| Tool | Check |
|---|---|
| Docker (daemon running) | `docker info` |
| `uv` | `uv --version` |
| Node.js 20+ | `node --version` |

### Clone, branch, run

```bash
git clone <repo-url> what-to-wear && cd what-to-wear
git checkout rebuild
```

⚠️ **`rebuild` is the trunk, not `main`.** `main` is the old live prototype and shares no
history with `rebuild`. Never branch from it, merge into it, or push it.

```bash
cd infra     && npm install && npx supabase start
cd ../backend && uv sync && cp .env.example .env && uv run uvicorn whattowear.main:app --reload
cd ../frontend && npm ci && npm run dev
```

Create `frontend/.env.local`:

```
NEXT_PUBLIC_SUPABASE_URL=http://127.0.0.1:54321
NEXT_PUBLIC_SUPABASE_ANON_KEY=<from `npx supabase status` in infra/>
```

> The AI-layer keys in `backend/.env.example` (`AI_GATEWAY_API_KEY`, `COHERE_API_KEY`, …)
> belong to the styling pipeline. **This feature does not need them.** Leave them blank.

**Two URLs worth having open:** `localhost:3000/dev/components` (every existing component in
every state) and `localhost:54323` (Supabase Studio).

### Verify before writing code

```bash
cd backend  && uv run pytest && uv run ruff check . && uv run mypy src && uv run lint-imports
cd ../frontend && npm run lint && npm run typecheck && npm run build && npm test
```

All green means the baseline is sound and anything that breaks later is yours.

---

## 4. How to run this

```
/speckit-specify → /speckit-clarify → /speckit-plan → /speckit-tasks
                 → /speckit-analyze → /speckit-implement
```

Spec Kit cuts `012-calendar`. **Rename it immediately:**

```bash
git branch -m feat/012-calendar
```

Merge into `rebuild` by PR using **"Create a merge commit"**.

---

## 5. Read first

| # | Source | What to take |
|---|---|---|
| 1 | `.specify/memory/constitution.md` | Binding. **VII**, **VIII**, **IX** apply. |
| 2 | `design/design-system.md` §4, §6 (Calendar), Screen anatomy → Calendar, "Date & time formats" | Route, all four states, verbatim copy, row composition, the date-format spec. |
| 3 | `design/known-gaps.md` §-2 | The permission primer and the `wtw_calendar_primed` persisted flag. |
| 4 | `docs/design-decisions.md` §12 | The auth flow decision — PKCE, redirect rules, why no magic link. Same OAuth constraints apply here. |
| 5 | `docs/handoffs/013-profile-settings.md` §7 | What 013 deliberately left inert for you. |

`design/prototype/` is reference only — read it for intent, **never copy code from it**.

---

## 6. In scope

### 6.1 Migration `0004`

`infra/supabase/migrations/0004_*.sql`. Stores the calendar connection state and the
user's picked event context.

**Follow the RLS pattern feature 004 establishes in `0002`.** Read that migration first.
A calendar connection is private to its owner — enable RLS, write per-user policies, and
**prove isolation with a test**.

OAuth tokens are credentials. Decide explicitly how they are stored and say why in your
report — this is the first feature in the project to hold a third-party token.

### 6.2 `/calendar` — four states

Sticky `TopHeader`, title "Calendar events", back arrow, no right slot.

| State | What renders |
|---|---|
| **Disconnected** | One centred `--color-surface` card: 44px calendar-glyph icon tile, `calendar.disconnected.title`, `calendar.disconnected.body`, full-width primary `calendar.disconnected.cta` |
| **Connected, has events** | `calendar.list.hint` caption, then stacked event rows — title on its own line, then a `{time} · {location}` meta line |
| **Connected, no events** | `calendar.empty.body` + `calendar.empty.cta` ("Style something", which bypasses the calendar and goes to Recommend) |
| **Error** | `calendar.error.body` + `calendar.error.cta` |

Plus loading (the Calendar skeleton: two 56px blocks at 14px radius) and offline (global
banner; suppress the screen-level error per §6's precedence rule).

**Once an event is picked, all rows go disabled** (`opacity: 0.5`, `cursor: not-allowed`).
The picked context surfaces on Recommend — **not** as a highlighted row here.

### 6.3 Dates are computed, not hardcoded

The design system is explicit that the prototype hardcoded `"Today, 7:30 PM"` into mock data
and that this is a gap to close. **Compute it**: the relative-day label from the event's real
timestamp — Today / Tomorrow / weekday name for the next ~6 days / short date beyond — plus a
locale-aware time. See "Date & time formats".

### 6.4 The two connect entry points must stay in sync

There are **two** places a user connects or disconnects:

1. The `/calendar` disconnected state's "Connect Google Calendar" button.
2. **Settings → Connected accounts**, which feature 013 deliberately left inert for you.

They read and write the same state. A "Connected" status `Badge` shows in Settings when
linked, a "Connect" text action when not. Wire both; do not let them drift.

### 6.5 The permission primer

`known-gaps.md` §-2: a primer card must appear **before** the real Google consent screen,
gated behind a persisted `wtw_calendar_primed` flag so it shows once, not every time.

### 6.6 The Recommend context line

Below Recommend's message list: either a "Style for an event from calendar" link (nothing
picked) or "Styling for {event} · Change" with a small calendar glyph (picked).

⚠ **This touches `/recommend`, which is feature 008's screen.** It exists today only as a
stub from 001. Add the context line to the stub, keep the change small and self-contained,
and **say in your report exactly what you touched there** — 008 will build on top of it and
needs to know.

---

## 7. Explicitly out of scope

The styling chat itself (008) · the suggestion pager (009) · weather services in Connected
accounts — the design specifies a "Coming soon" muted `Badge`, **not interactive**, so leave
it that way · closet, outfits, profile screens · any cloud Supabase project — local only.

---

## 8. Decisions already made — do not relitigate

| Topic | Decision | Source |
|---|---|---|
| OAuth flow | PKCE. Redirect to an **app route**, never a provider-hosted page. Every redirect URL on the allow-list. | design-decisions §12 |
| Manifest `scope` | Already `/`, so any app route qualifies as a redirect target. Does nothing on Android; it is what makes the flow work on installed iOS. | §12 |
| Type scale | design-decisions §6, **not** design-system §2 (superseded). Minimum text 11px. | §6 |
| Input font size | 16px at every breakpoint — below that iOS Safari auto-zooms on focus. | §1.2 |
| Form controls | Already built. See `/dev/components`. **Do not build new ones.** | §1 |
| Migrations | Supabase only. **Alembic is not used.** | constitution |

---

## 9. Traps

1. **Do not fake a connected state.** If you have no Google credential, the honest outcome is
   a wired flow that cannot complete, clearly reported. A hardcoded "Connected" badge is the
   worst possible result, because it looks done.
2. **Do not hardcode dates.** The design system names this as the specific thing the
   prototype got wrong. Compute from real timestamps.
3. **Two entry points, one state.** Settings and `/calendar` must agree. Testing only one is
   how they drift.
4. **Weather services stays inert.** It is specified as a "Coming soon" muted `Badge`. Making
   it interactive is inventing UI the design system does not contain — a Principle VIII
   violation in the opposite direction.
5. **OAuth tokens are credentials.** They never go in a tracked file, never in a log line,
   never in an error message returned to the client.
6. **Keep your `/recommend` change minimal.** It is 008's screen; you are a guest there.
7. **`design/prototype/` is reference only. Never copy code from it.**

---

## 10. Definition of done

- [ ] `npx supabase db reset` from empty reproduces the schema, `0004` included.
- [ ] **RLS proven**: a test shows user A cannot read user B's calendar connection.
- [ ] `/calendar` renders all four states plus loading and offline, in both themes, at
      320 / 768 / 1024 / 1440.
- [ ] Event rows show computed relative dates, not fixed strings.
- [ ] Picking an event disables the rows and surfaces the context on Recommend.
- [ ] Settings → Connected accounts reflects and controls the same state as `/calendar`.
- [ ] The permission primer appears once, gated by `wtw_calendar_primed`.
- [ ] OAuth is wired and PKCE-correct. **Tested if a Google client exists; clearly reported
      as untested if not.**
- [ ] No OAuth token in any tracked file, log, or client-facing error.
- [ ] Exactly one `<h1>`; keyboard-only pass; focus ring on keyboard nav, absent on mouse.
- [ ] Backend test count has not dropped.
- [ ] `ruff`, `ruff format --check`, `mypy`, `pytest`, `lint-imports`, `eslint`,
      `tsc --noEmit`, `next build`, Vitest all clean.

---

## 11. If you hit a gap

`docs/design-decisions.md` has no open items. If you find one it does not cover — token
storage strategy is a likely candidate — **do not invent a value and continue**. That is a
Principle VIII violation for visual matters and a plain architectural gap otherwise. Record it
with your reasoning and flag it.

When you write `research.md`, the failure mode to guard against is not weak reasoning — it is
an **incomplete option list**. Feature 001 shipped a defect whose decision record was
well-argued but had never considered the option that turned out correct. Ask what you have not
listed.

## 12. Report back with

What you built · **whether OAuth was actually tested or only wired** · how you stored the
tokens and why · exactly what you changed in `/recommend` · which Constitution Check gates you
could not satisfy · the §10 checklist results · anything recorded in `design-decisions.md`.

**Name what you skipped.** A report admitting two gaps is worth more than one claiming a clean
sweep.
