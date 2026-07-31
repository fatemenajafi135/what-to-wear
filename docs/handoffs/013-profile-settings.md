# Handoff — Feature 013: Profile and Settings

**From:** tech lead · **Status:** ready to start · **Branch:** `feat/013-profile-settings`,
cut from `rebuild` · **Migration number: `0003`**

Mostly frontend: two screens, five settings sections, built from form controls that already
exist. One straightforward new table behind them.

**This handoff assumes you are starting on a different machine and have never worked on this
repository.** Section 2 gets you from nothing to a running stack.

---

## 1. Mission

A user can see their profile and set their style preferences, body and size details, account
email, and notification preference — and those choices persist.

---

## 2. Setting up from scratch

### Prerequisites

| Tool | Check |
|---|---|
| Docker (daemon running) | `docker info` |
| `uv` | `uv --version` |
| Node.js 20+ | `node --version` |
| Git 2.27+ | `git --version` |

### Clone and branch

```bash
git clone <repo-url> what-to-wear
cd what-to-wear
git checkout rebuild
```

⚠️ **`rebuild` is the trunk, not `main`.** `main` is the old live prototype and shares no
history with `rebuild`. Never branch from it, merge into it, or push it.

### Database

```bash
cd infra
npm install                 # pinned Supabase CLI
npx supabase start          # Postgres + Auth + Storage in Docker
```

First run pulls several images — a few minutes. Leave it running.

### Backend

```bash
cd ../backend
uv sync
cp .env.example .env        # needs NO editing for this feature
uv run uvicorn whattowear.main:app --reload
```

Check: `curl -s localhost:8000/health` → `{"status":"ok"}`. A `503` with
`failed_dependencies: ["database"]` means Supabase isn't running.

> **Note:** `.env.example` lists AI-layer keys (`AI_GATEWAY_API_KEY`, `COHERE_API_KEY`, …).
> **You do not need them.** They belong to the styling pipeline and nothing in this feature
> touches it. Leave them blank.

### Frontend

```bash
cd ../frontend
npm ci
```

Create `frontend/.env.local`:

```
NEXT_PUBLIC_SUPABASE_URL=http://127.0.0.1:54321
NEXT_PUBLIC_SUPABASE_ANON_KEY=<from `npx supabase status` in infra/>
```

```bash
npm run dev                 # http://localhost:3000
```

### Two URLs you will want

- **`localhost:3000/dev/components`** — every existing component in every state, both
  themes. **This is your parts catalogue; everything you need is already there.**
- **`localhost:54323`** — Supabase Studio, to see the database.

### Verify before writing code

```bash
cd backend  && uv run pytest && uv run ruff check . && uv run mypy src && uv run lint-imports
cd ../frontend && npm run lint && npm run typecheck && npm run build && npm test
```

Expect **459 backend tests** green. All green means the baseline is sound and anything that
breaks later is yours.

---

## 3. How to run this

```
/speckit-specify → /speckit-clarify → /speckit-plan → /speckit-tasks
                 → /speckit-analyze → /speckit-implement
```

Spec Kit cuts `013-profile-settings`. **Rename it immediately:**

```bash
git branch -m feat/013-profile-settings
```

`plan-template.md` carries ten Constitution Check gates — fill each in, marking N/A with a
one-line reason where a principle genuinely doesn't apply. Merge into `rebuild` by PR using
**"Create a merge commit"**.

---

## 4. Read first

| # | Source | What to take |
|---|---|---|
| 1 | `.specify/memory/constitution.md` | Binding. **VII**, **VIII**, **IX** apply. |
| 2 | `design/design-system.md` §4 (Settings section contents), §5, §6, §8 | The five sections, their exact fields, layout per tier, copy, accessibility. |
| 3 | `docs/design-decisions.md` §1 | **The form-control spec.** `Input`, `Select`, `DatePicker`, `TagInput` — all already built. This is the contract. |
| 4 | `docs/design-decisions.md` §6 | The rebuilt type scale. Supersedes design-system §2. |
| 5 | `docs/ios-verification-backlog.md` | What to record rather than test. |

`design/prototype/` is reference only — read it to understand intent, **never copy code from
it**. Nothing under `_scaffolding/` may appear in the product.

---

## 5. In scope

### 5.1 Migration `0003` — a new `user_profile` table

`infra/supabase/migrations/0003_*.sql`, hand-written.

**Follow the RLS pattern established by feature 004's `0002` migration.** Read it first.
A profile is private to its owner — enable RLS, write per-user policies, and **prove
isolation with a test**. A policy written but never exercised is a policy that does not work.

Feature 002's `0001_init.sql` created the `updated_at` trigger function — use it rather than
writing another.

### 5.2 `/profile`

Per design-system §8: Profile has **no `TopHeader`**, so it needs a **visually-hidden
`<h1>Profile</h1>`**, and its three cards each get an `<h2>`. A gear icon navigates to
`/profile/settings`. Sign-out already exists from feature 003 — don't rebuild it.

At tablet the three cards become a 2-column grid (third wraps); at desktop, all three in a
row at ~340px each.

### 5.3 `/profile/settings` — five sections

**An in-page section switcher, not sub-routes.** One route, five panes.

| Section | Controls |
|---|---|
| **Style preferences** | Style tags (multi-select `Chip`): Classic, Minimal, Bold, Casual, Edgy · Colour tags (multi-select `Chip`): Neutral tones, Jewel tones, Pastels, Monochrome, Earth tones · "Brands to avoid" — `TagInput` |
| **Body & size** | Body shape (single-select, 5 illustrated options): Hourglass, Pear, Rectangle, Apple, Inverted triangle · Gender (single-select `Chip`): Woman, Man, Non-binary, Prefer not to say · Birth date (`DatePicker`) · Height, Top size (XXS–XXXL), Bottom size (00–20), Shoe size (`Select`) |
| **Account** | Email address (editable `Input`) |
| **Connected accounts** | Google Calendar row · Weather services with a "Coming soon" muted `Badge`, not interactive — **see §7, feature 012 owns the calendar toggle** |
| **Notifications** | Push notifications: one `Switch`, default **on** |

**Every section except Notifications has an Edit/Done toggle**: "Edit" reveals the editable
controls, "Done" commits the draft back to the saved value. Notifications has no edit state —
the switch commits immediately.

At desktop (1024px+) the section list becomes a **320px narrow list pane** beside the section
detail (§5's two-pane rule).

**States** per §6: loading (Settings skeleton — two 100px blocks then one 60px), error
(`settings.error.body` / `.cta`), offline (global banner, per-action disabling).

### 5.4 Persistence

Authenticated routes under `api/v1/routes/`, using feature 003's dependency to name the
caller. Pydantic response models; the frontend consumes generated OpenAPI types (Principle
VII) — no hand-written duplicates.

---

## 6. ⚠ The trap: two different things are called "preferences"

| | What it is | Who owns it |
|---|---|---|
| `backend/src/whattowear/memory/preferences.py` | **Derived** — learned implicitly from outfit thumbs-up/down. `derive_signals()` feeds `profile_note()`, which softly shapes generation. | Feature 007 (ported, evaluated) |
| Settings → "Style preferences" | **Declared** — what the user explicitly states about their taste. | **This feature** |

They share a word and nothing else.

**013 owns a new `user_profile` table and touches nothing under `memory/`.** Writing declared
taste into the derived-signal model would corrupt a pipeline that was ported and measured
against recorded eval baselines — and the eval harness would not catch it, because it never
exercises Settings.

If you believe declared preferences *should* eventually influence generation, that is a real
product question and possibly a good idea. **Raise it; do not implement it here.**

---

## 7. Explicitly out of scope

**The Google Calendar connect/disconnect toggle** — feature 012 owns it, because the OAuth
and the adapter are its work. Render the Connected accounts row with the disconnected
appearance the design specifies and leave the action inert. Say so in your report.

Also out: password change, account deletion, data export — all deferred in
`known-gaps.md` §0.6, and **adding them would be inventing UI the design system does not
contain** · the closet, outfits, styling, calendar screens · any cloud Supabase project.

---

## 8. Decisions already made — do not relitigate

| Topic | Decision | Source |
|---|---|---|
| Form controls | Already built. `Input`, `Select`, `DatePicker`, `TagInput`, `Chip`, `Switch` — see `/dev/components`. **Do not build new ones.** | design-decisions §1 |
| Input font size | 16px at every breakpoint. Below that iOS Safari auto-zooms on focus. | §1.2 |
| Validation | Fires on blur, never on keystroke; re-validates on change once errored. | §1.7 |
| Type scale | design-decisions §6, not design-system §2. Minimum text 11px. | §6 |
| Native `<select>` | Stays native. **Do not build a custom listbox** — you lose mobile pickers, keyboard behaviour and AT semantics. | §1.4 |
| Settings sections | In-page switcher, **not** sub-routes. | design-system §4 |

---

## 9. Traps

1. **Do not build form components.** They exist with full state matrices. Building a second
   `Select` is the most likely waste in this slice.
2. **Profile needs a visually-hidden `<h1>`.** It has no `TopHeader` to carry one, and §8
   requires exactly one `<h1>` per screen. Easy to miss.
3. **Body shape is 5 illustrated options** and the design system admits it never specified
   stroke weight or size for the silhouettes ("Open questions"). That is a genuine gap —
   record your choice in `docs/design-decisions.md` rather than inventing silently.
4. **`Chip` multi-select vs single-select.** Style and colour tags are multi; gender is
   single. The component supports both — read the spec, don't guess.
5. **Edit/Done is a draft commit**, not live-saving. "Done" writes; navigating away without
   it should not persist. Decide what happens on abandon and say so.
6. **`design/prototype/` is reference only.** Never copy code from it.

---

## 10. Add to the iOS backlog

`docs/ios-verification-backlog.md` — add anything here you build blind for iOS. You cannot
test installed-iOS behaviour; build to spec, record it, move on. Do not silently drop an iOS
requirement because it is unverifiable.

---

## 11. Definition of done

- [ ] `npx supabase db reset` from empty reproduces the schema, `0003` included.
- [ ] **RLS proven**: a test shows user A cannot read user B's profile.
- [ ] `/profile` and `/profile/settings` render every state in both themes at 320 / 768 / 1024 / 1440.
- [ ] All five sections work; Edit/Done commits and persists across a reload.
- [ ] Desktop two-pane: 320px section list beside the detail pane.
- [ ] Exactly one `<h1>` per screen; keyboard-only pass; focus ring on keyboard nav and
      absent on mouse click.
- [ ] Nothing under `backend/src/whattowear/memory/` was modified.
- [ ] **459 backend tests still pass.**
- [ ] `ruff`, `ruff format --check`, `mypy`, `pytest`, `lint-imports`, `eslint`,
      `tsc --noEmit`, `next build`, Vitest all clean.
- [ ] No secret in the diff.
- [ ] iOS backlog updated.

---

## 12. If you hit a gap

`docs/design-decisions.md` has no open items. If you find one it does not cover — the
body-shape illustrations are a likely candidate — **do not invent a value and continue**.
That is a Principle VIII violation. Add it to that file with your reasoning and flag it.

When you write `research.md`, the failure mode to guard against is not weak reasoning — it is
an **incomplete option list**. Feature 001 shipped a defect whose decision record was
well-argued but never considered the option that turned out to be correct. Ask what you have
not listed.

## 13. Report back with

What you built · which Constitution Check gates you could not satisfy and why · the §11
checklist results · confirmation you did not touch `memory/` · what you left inert for
feature 012 · anything recorded in `design-decisions.md` · what you added to the iOS backlog.

**Name what you skipped.** A report admitting two gaps is worth more than one claiming a
clean sweep.
