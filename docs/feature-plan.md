# Feature plan

The slice breakdown for the rebuild. **This file is the plan of record.** Any earlier
eight-feature list is superseded.

---

## Why this replaced the original eight

The first breakdown was written before any code existed. Feature 001 gave us a calibration
point — **68 tasks, 103 files, 5,582 lines** — and reviewing the remaining seven slices
against it surfaced three problems:

1. **The list was frontend-shaped.** Every backend concern was hidden inside a UI feature:
   the backend scaffold, `ports.py`, the import-linter contract and CI had no home at all;
   the local database and `0001_init.sql` were "before feature 003"; the AI layer extraction
   was "under feature 005". None were slices, so none had a spec, a gate, or a definition of
   done.
2. **Two slices were epics.** "Closet / items CRUD + upload" meant backend scaffold +
   database + migrations + items API + closet grid + item detail + edit forms + photo
   storage + VLM vision + review queue + bulk upload — four to five times the size of 001.
   "Styling recommendations" meant the entire AI port *plus* the richest screen in the app
   *plus* the suggestion pager.
3. **`/calendar` had no feature.** The design system specifies twelve routes. Eleven mapped
   to a slice. The Calendar screen — four states, Google Calendar OAuth, a permission primer,
   event rows, and a context line that surfaces back on Recommend — mapped to nothing, and
   would have been discovered mid-build.

## The two principles

**Backend foundations get their own slices.** They have no UI and are verified differently —
a reproducible `supabase db reset`, a passing eval run. Buried inside a UI feature, they get
rushed to make a screen work.

**Every slice is independently demoable.** One sentence a person can watch happen. This is
what the Spec Kit spec template asks for, and it is the test for whether a slice is really
one thing.

---

## The slices

| # | Slice | Demoable outcome |
|---|---|---|
| 001 | ✅ App shell, tokens, component library, PWA basics | Chrome adapts across three tiers; every component renders every state in both themes |
| 002 | Backend + database foundation | `supabase db reset` succeeds from empty; CI green on both stacks |
| 003 | Auth | I sign up, sign in, reset my password, and stay signed in inside the installed PWA |
| 004 | Closet — read | I can see my closet |
| 005 | Closet — write | I can add, edit and remove items |
| 006 | Photo upload + vision | I add an item by photographing it |
| 007 | AI layer port | Eval run matches the recorded baselines |
| 008 | Styling chat | I ask for an outfit in plain English and get one, with cited reasoning |
| 009 | Outfit suggestion pager | I get several suggestions and can page between them |
| 010 | Outfits gallery + detail | I browse, filter and open saved outfits |
| 011 | Chat history | I reopen a past conversation and continue it |
| 012 | Calendar | I connect my calendar and style for a real event |
| 013 | Profile / settings | I set my style preferences, sizes and account details |
| 014 | Offline + caching + update prompt | The app works offline and tells me when a new version is ready |
| 015 | Install prompts + primers + splash | I install it to my home screen on iOS and Android |
| 016 | Conversational styling turns | The stylist actually replies as I talk, then styles from what we discussed |

**016 was added after 008 and 009 shipped**, not planned up front. 008 implemented
design-decisions.md §28: the composer's send is local-only and "Start styling" is the only
backend call — so the chat looked conversational while only the user talked. §37 amends that
decision (§28's option list was incomplete; it never considered a lightweight non-pipeline
turn). 016 is that slice. **It sequences after 009**, which rewrites the same response shape and
components, **and before 011**, which persists a transcript whose shape this changes.

## Scope boundaries worth stating up front

**002 — Backend + database foundation.** `backend/src/whattowear/` per the constitution's
layout, `pyproject.toml` with `uv`, `core/config` and `core/logging`, `ports.py` Protocols,
the import-linter contract wired into CI, the CI workflow covering both stacks, local
Supabase, `infra/supabase/migrations/0001_init.sql` hand-written from the new data models,
and one health route. **No product endpoints, no UI, no salvaged AI code.**

**004 / 005 / 006 — the closet, split three ways.** 004 is the items schema, repository,
read routes and the read-only screens. 005 adds mutations and the overflow sheets. 006 is
the riskiest third on its own — Supabase Storage buckets and policies, the upload flow, the
VLM extraction wired to the salvaged vision module, the review queue, the bulk branch, and
the camera permission primer.

**007 — AI layer port.** The Phase 5 extraction as its own slice: `ports.py`
implementations, module-by-module port out of the legacy checkout, prompts moved to files,
the corpus manifest and ingestion CLI, and evals green against `docs/eval-baselines/`.
**This is the highest-risk work in the project.** It carries three iterations of evaluated
quality work, and its gate is an eval run, not a screen.

**008 / 009 — styling, split two ways.** 008 is the chat surface with a single-outfit reply.
009 is the multi-outfit pager with its four group states, feedback footer and favourite
toggle — genuinely separable, and complex enough to deserve its own spec.

**014 / 015 — PWA completion, split two ways.** 014 is Serwist, per-screen cache strategies
and the update prompt. 015 is `beforeinstallprompt`, the iOS manual card across five
browsers with different copy each, the permission primers and Apple splash screens.

## Ordering and dependencies

```
001 ✅
 └─ 002 backend + database
     ├─ 003 auth ─────────────────┐
     │                            │
     ├─ 004 closet read ─ 005 closet write ─ 006 photo + vision
     │                            │
     └─ 007 AI port ─ 008 styling chat ─ 009 suggestion pager
                                  │
                       010 outfits ─ 011 chat history ─ 012 calendar ─ 013 profile
                                  │
                       014 offline + update ─ 015 install + splash
```

Hard constraints:

- **002 precedes everything data-driven.** Nothing else can be built against a database that
  does not exist.
- **007 precedes 008 and 009.** The styling UI consumes the ported pipeline. Building the
  screen first guarantees a parallel implementation, which Principle I prohibits.
- **014 and 015 come last**, after real screens exist. Cache strategies written against stub
  routes are fiction.
- **003 can run in parallel** with the 004–006 chain once 002 lands, if there are two agents.

## Deliberate merges, if fewer slices are wanted

Two are defensible: **014 + 015** back into one PWA feature, and **004 + 005** back into one
closet feature. That gives thirteen. **006 and 007 stay separate regardless** — they are the
two highest-risk slices and both are verified by something other than a screen working.
