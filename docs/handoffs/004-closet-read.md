# Handoff — Feature 004: Closet (read)

**From:** tech lead · **Status:** ready to start · **Branch:** `feat/004-closet-read`, cut
from `rebuild` · **Migration number: `0002`**

This slice adds the first **product table** to the project, and with it the RLS convention
every later table copies. Features 005, 006, 008, 009 and 010 all need items to exist, so
this is the critical path.

Runs on the project owner's machine — the local Supabase stack is part of the deliverable's
verification, not an afterthought.

---

## 1. Mission

Users can see their closet. Items exist in the database, are private per user, and render in
the grid and detail screens with every specified state.

**Read only.** Adding, editing and deleting items is feature 005. Photo upload is 006.

---

## 2. How to run this

```bash
git checkout rebuild && git pull
```

```
/speckit-specify → /speckit-clarify → /speckit-plan → /speckit-tasks
                 → /speckit-analyze → /speckit-implement
```

Spec Kit cuts `004-closet-read`. **Rename it immediately** — the repo also holds the old
prototype's branches under the same numbers (`004-preference-memory` is legacy):

```bash
git branch -m feat/004-closet-read
```

Merge back into `rebuild` by PR, using **"Create a merge commit"**.

---

## 3. Read first

| # | Source | What to take |
|---|---|---|
| 1 | `.specify/memory/constitution.md` | Binding. **VI (schema stability)**, **VII (contracts)**, **VIII (visual truth)**, **IX (one codebase)** all apply. |
| 2 | `backend/src/whattowear/ports.py` | **`ClosetRepository` already exists.** You implement it — see §4.2. |
| 3 | `design/design-system.md` §4, §5, §6 (Closet, Item detail), Screen anatomy | Routes, grid columns per tier, states, verbatim copy. |
| 4 | `docs/design-decisions.md` §1, §6 | Form controls (Item detail's read view), the rebuilt type scale. |
| 5 | `../app-legacy/backend/alembic/versions/0001_initial_wardrobe_schema.py` | **A checklist, not a script to replay.** Read-only. |
| 6 | `notes/run-locally.md` | Ports, Studio, the pooler URL gotcha. |

---

## 4. In scope

### 4.1 Migration `0002` — the items table, and the RLS convention

`infra/supabase/migrations/0002_*.sql`. Hand-written from the design's data model, using the
legacy Alembic file as a **checklist of what existed** — not a replay. Replaying the dump
reintroduces the old structure through the back door.

The legacy columns, for reference: `id`, `user_id`, `category`, `colors`, `fabric`,
`warmth`, `formality`, `season`, `source`, `catalog_item_id`, `created_at`, `updated_at`,
plus `pattern`, `fit` and `photo_path` added later.

**Principle VI is binding and the taxonomy is frozen.** Feature 002's `0001_init.sql`
already created `category_group` and `formality_level` as Postgres enums — **use them**. Do
not create a parallel scale, do not rename a group, do not widen an enum.

**⚠ This is the first table in the project with RLS, so you are setting the pattern.**
Every closet item is private to its owner. Get this right and later features copy it; get it
wrong and they copy that instead. Enable RLS, write per-user policies, and **prove isolation
with a test** — two users, each sees only their own rows. A policy that is written but never
exercised is a policy that does not work.

Catalog items are shared and read-only, so their access rule differs from wardrobe items.
Decide it explicitly and say why.

### 4.2 The repository — a contract that already exists

**Do not invent an interface.** Feature 007 defined it, and the whole AI pipeline consumes it:

```python
# backend/src/whattowear/ports.py
class ClosetRepository(Protocol):
    def list_wardrobe_items(self, user_id: str) -> list[WardrobeItem]: ...
    def list_catalog_items(self) -> list[WardrobeItem]: ...
    def get_derivation_inputs(self, user_id: str) -> tuple[list[FeedbackRecord], dict[str, datetime]]: ...
```

Implement a real, database-backed version under `repositories/`.

**Keep `adapters/closet_fixture.py::FixtureClosetRepository`.** It is what lets the eval
harness run without a database, and 459 tests depend on that. You are *adding* an
implementation, not replacing one. When you are done, two things satisfy the Protocol and
`ports.py` finally has the two concrete implementations the constitution's Quality Bar asks
for before an abstraction is justified.

`get_derivation_inputs` reaches into feedback data that does not exist yet (feature 010's
territory). Returning empty is fine — say so explicitly rather than leaving it unclear.

### 4.3 Read routes

Under `api/v1/routes/`. Authenticated — feature 003 built the dependency that names the
caller; use it. A user can only ever read their own closet, enforced at **both** the RLS and
the query level. Belt and braces, deliberately: RLS is the guarantee, the query is the
intent.

Response models are Pydantic; the frontend consumes generated OpenAPI types (Principle VII).
No hand-written duplicate types.

### 4.4 Screens

**`/closet`** — sticky header (`TopHeader`, title "Closet", subtitle = item count), then the
category `Chip` row: All, Tops, Bottoms, Outerwear, Shoes, Accessories (single-select, no
sort). Grid: **2 columns mobile / 3 tablet / 4 desktop**.

**`/closet/:itemId`** — `TopHeader` with back arrow and a `dots` right slot (the overflow
sheet it opens is **005's**; wire the trigger, leave the sheet for them or render it empty —
say which you chose). Photo block, then one `--color-surface` card listing Name, Category,
Group, Fabric, Colour, Notes as label/value pairs.

**Desktop two-pane** at 1024px+: the closet grid becomes the wide list pane beside an
item-detail pane, with the design system's placeholder copy when nothing is selected.

**Every state**, per §6 and the per-screen skeleton spec:

| State | Copy |
|---|---|
| loading | the Closet skeleton — 2×2 grid of 120px blocks at 14px radius |
| empty (first run) | `closet.empty.first_run.body` + `.cta` |
| **empty-filtered** | `closet.empty.filtered.body` + `.cta` — **a distinct state**, different copy, different recovery |
| error | `closet.error.body` + `.cta` |
| offline | global banner; suppress the screen-level error (§6's precedence rule) |

"Load more" is a **manual text button**, not infinite scroll.

**No real photos exist.** Use the diagonal-stripe placeholder from § Image treatment. Do not
invent an image pipeline — that is 006.

---

## 5. Explicitly out of scope

Adding, editing, deleting items · the item overflow sheet's actions · photo upload, storage,
vision (**006**) · outfits (010) · the styling screen (008) · feedback and preference
derivation (010) · any cloud Supabase project — **local only**.

---

## 6. Decisions already made — do not relitigate

| Topic | Decision | Source |
|---|---|---|
| Taxonomy | Frozen. Use `0001_init.sql`'s enums. No parallel formality scale, no renamed groups. | constitution VI |
| Repository interface | `ports.ClosetRepository` — already defined, already consumed. | 007 |
| Migrations | Supabase only. **Alembic is not used.** | constitution |
| Type scale | `docs/design-decisions.md` §6, **not** design-system §2 (superseded). Minimum text 11px. | §6 |
| Empty vs empty-filtered | Genuinely distinct states with different copy and recovery. | design-system §6 |
| Grid vs list | Closet is a **real grid** (2/3/4). Outfits is the one that's a list. | design-decisions §2 |

---

## 7. Traps

1. **Do not replay the legacy migration.** It is a checklist. Replaying it reintroduces the
   prototype's structure, which is the entire thing this rebuild exists to avoid.
2. **Do not replace `FixtureClosetRepository`.** The eval harness runs without a database
   because of it. Breaking that breaks 007's gate.
3. **Prove RLS isolates, don't assume it.** Two users, a test, real rows.
4. **`empty` and `empty-filtered` are different screens.** "No items match this filter" with
   a *Clear filter* action is not "your closet is empty" with an *Add your first item*
   action. Conflating them is the most common way this screen ships wrong.
5. **Offline suppresses the screen-level error.** §6's precedence rule — do not
   double-message the same root cause.
6. **`../app-legacy` is read-only.** Read it, copy out of it, never modify it.
7. **`design/prototype/` is reference only — never copy code from it.**

---

## 8. Definition of done

- [ ] `npx supabase db reset` from empty reproduces the schema, `0002` included.
- [ ] **RLS proven**: a test shows user A cannot read user B's items.
- [ ] A real `ClosetRepository` implementation satisfies the Protocol; the fixture still works.
- [ ] Eval harness still runs — **459 tests still pass**.
- [ ] `/closet` and `/closet/:itemId` render every state in both themes at 320 / 768 / 1024 / 1440.
- [ ] Desktop two-pane works; placeholder copy shows when nothing is selected.
- [ ] Frontend consumes generated OpenAPI types. No hand-written duplicates.
- [ ] `ruff`, `ruff format --check`, `mypy`, `pytest`, `lint-imports`, `eslint`,
      `tsc --noEmit`, `next build` all clean.
- [ ] No secret in the diff. `.env.example` updated with placeholders if anything was added.

---

## 9. If you hit a gap

`docs/design-decisions.md` has no open items. If you find one it does not cover, **do not
invent a value** — that is a Principle VIII violation. Add it there with your reasoning and
flag it.

When you write `research.md`, the failure mode to guard against is not weak reasoning — it
is an **incomplete option list**. Feature 001 shipped a defect whose decision record was
well-argued but never considered the option that turned out correct. Ask what you have not
listed.

## 10. Report back with

What you built · the RLS policy you wrote and how you proved it · which Constitution Check
gates you could not satisfy · the §8 checklist results · anything recorded in
`design-decisions.md`.

**Name what you skipped.** A report admitting two gaps is worth more than one claiming a
clean sweep.
