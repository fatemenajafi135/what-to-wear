# Handoff — Feature 005: Closet (write)

**From:** tech lead · **Status:** ready to start · **Branch:** `feat/005-closet-write`, cut
from `rebuild` · **Migration number: `0005`**

Follows feature 004 directly and touches the same files. **Run this alone** — Wave A's three
parallel slices produced five separate collisions, and every one cost more to untangle than
the parallelism saved.

---

## 1. Mission

A user can manage their closet: edit an item's details, mark it as worn, favourite it, and
delete it. Reading the closet already works — this adds everything that changes it.

---

## 2. Scope corrections — read before planning

Three things differ from what you might assume. I checked each against the design system and
the live schema.

### 2.1 There is no "add from catalog" flow. Do not build one.

The word **"catalog" appears zero times in `design/design-system.md`.** The rebuild's only
way to add an item is **photo upload, which is feature 006**. The legacy prototype had
catalog-based adding; the new design dropped it.

The `catalog_items` table exists because the salvaged AI pipeline's `ClosetRepository`
Protocol needs `list_catalog_items()` for outfit substitution. **That is its only consumer.**
Do not build a catalog browse or catalog-add screen — it is not in the design, and inventing
one is a Principle VIII violation.

**So this slice adds no new items.** Edit, favourite, wear, delete — nothing that creates.

### 2.2 The schema has no `favorite` or `worn` columns yet

`wardrobe_items` today: `id user_id category colors formality warmth season fabric pattern
fit name notes source catalog_item_id photo_path created_at updated_at`.

Two of this slice's four actions have nowhere to write. Your migration adds that — see §5.1.

### 2.3 "Log as worn today" records data the UI never shows

Design-system Screen anatomy, Item detail, is explicit: *"No image gallery, no
size/worn-count/favorite display on the page itself."*

So the action exists, the data persists, and **nothing in this slice displays either.**
That is correct, not an oversight — wear history feeds later features and the styling
pipeline. Do not add a worn-count badge or a favourite indicator to justify the action; the
design deliberately keeps that page free of them.

**Decide and record**: what "worn today" means when tapped twice in one day. One row per
tap, or one per day? Neither is specified. Pick one, justify it, and put it in
`docs/design-decisions.md`.

---

## 3. How to run this

```bash
git checkout rebuild && git pull
cd backend && uv sync
cd ../frontend && npm ci && npm run generate:api-types   # backend must be running
```

⚠️ **`lib/api/schema.d.ts` is generated, not committed.** Regenerate it after every pull that
changes backend routes, and again after you add yours, or the frontend types the old API.

```
/speckit-specify → /speckit-clarify → /speckit-plan → /speckit-tasks
                 → /speckit-analyze → /speckit-implement
```

Rename the branch Spec Kit cuts: `git branch -m feat/005-closet-write`.

---

## 4. Read first

| # | Source | What to take |
|---|---|---|
| 1 | `.specify/memory/constitution.md` | Binding. **VI** (schema), **VII** (contracts), **VIII** (visual truth) apply. |
| 2 | `design/design-system.md` §3 BottomSheet, §4, Screen anatomy → Item detail | The overflow menu, the edit form, and what must *not* appear on the page. |
| 3 | `infra/supabase/migrations/0002_wardrobe_and_catalog_items.sql` | The RLS **and GRANT** pattern you follow. Read it before writing `0005`. |
| 4 | `backend/src/whattowear/repositories/supabase_closet.py` | Extend this. Do not write a second repository. |
| 5 | `docs/design-decisions.md` §1 | The form-control spec for the edit form. All controls already exist. |

---

## 5. In scope

### 5.1 Migration `0005`

Adds the storage the four actions need: a favourite flag on the item, and wear history.

**Wear history is a modelling decision, not a column choice.** A `worn_count` integer cannot
answer "most worn this month" or be undone; a `item_wears` table can, at the cost of a join.
Nothing in the current design needs the richer shape — but the Outfits screen already
specifies a **"Most worn"** sort, so something will. Decide deliberately and record why.

**Follow `0002`'s RLS pattern exactly**, including the table-level `GRANT`. Feature 013 hit
this: RLS restricts *rows*, but without a `GRANT` the `authenticated` role cannot touch the
table at all, and their test fixture's blanket grant masked it until it was caught late.
**Prove isolation with a two-user test.**

### 5.2 Write routes

Extend `api/v1/routes/closet.py` and `repositories/supabase_closet.py`:

| Action | Shape |
|---|---|
| Edit an item | `PATCH` — partial update, per the field list in §5.3 |
| Favourite / unfavourite | Toggle |
| Log as worn today | Record a wear |
| Delete | Hard delete |

Authenticated via feature 003's dependency. Ownership enforced at **both** the RLS and query
level, as `004` does. Pydantic in, generated OpenAPI types out (Principle VII).

**`ports.ClosetRepository` must not change.** The AI pipeline consumes it, and `ports.py` is
covered by the import-linter contract. Add methods to the concrete repository, not the
Protocol, unless you can argue the pipeline needs them.

### 5.3 Item detail — edit mode

Per Screen anatomy: choosing **Edit** *"swaps the read-only card for an editable form (same
field order, `Chip`s for Category, text inputs for the rest) ending in a full-width 'Save
changes' button."*

Same field order as the read view: Name, Category, Group, Fabric, Colour, Notes. Category is
`Chip`s; the rest are text inputs. **Every control already exists** — see
`/dev/components`. Do not build new ones.

### 5.4 The item overflow `BottomSheet`

Opened by the `dots` trigger 004 already wired. Four rows, in the design's order:

**Edit · Log as worn today · Favorite · Delete**

`BottomSheet` ships with a `danger` row tone — **Delete uses it.**

⚠️ **The design specifies no delete confirmation.** A single tap on a `danger` row hard-
deleting a garment the user photographed is a harsh, unrecoverable outcome. This is a real
gap: decide whether to add a confirmation step, record the decision and its alternatives in
`docs/design-decisions.md`, and flag it. Do not silently pick either way.

Also close the gap 004 left: it wired the trigger and left the sheet — **say in your report
what state you found it in and what you did with it.**

### 5.5 Offline

Design-system §6: while offline, **"Log as worn"** and submit actions disable via
`navigator.onLine`. Nothing is queued — and the copy must not promise otherwise, because no
retry mechanism exists.

---

## 6. Explicitly out of scope

Adding items by any means — **006 owns photo upload, and no catalog flow exists** · photo
display or storage (006) · outfits (010) · any worn-count or favourite indicator on Item
detail (§2.3) · pagination beyond 004's existing "Load more".

---

## 7. Decisions already made — do not relitigate

| Topic | Decision | Source |
|---|---|---|
| Taxonomy | Frozen. Use `0001_init.sql`'s enums. | constitution VI |
| Repository | Extend `supabase_closet.py`. `ports.ClosetRepository` unchanged. | 007 / 004 |
| RLS | Policies **plus** table-level `GRANT`, proven by a two-user test. | 004 / 013 |
| Migrations | Supabase only. Alembic is not used. | constitution |
| Form controls | Already built. Do not create new ones. | design-decisions §1 |
| Type scale | design-decisions §6, not design-system §2. | §6 |
| Generated schema | Not committed. Regenerate via `npm run generate:api-types`. | §20 |

---

## 8. Traps

1. **Do not build a catalog-add flow.** §2.1. It is not in the design.
2. **Do not display worn count or favourite state on Item detail.** §2.3. The design
   explicitly excludes them.
3. **Do not change `ports.ClosetRepository`.** The AI pipeline depends on its shape.
4. **`GRANT` as well as RLS.** Policies alone leave the table unreachable.
5. **Regenerate `schema.d.ts`** after adding routes, or the frontend types the old API.
6. **Both CORS origins already work** — `localhost` and `127.0.0.1`. Don't narrow that list.
7. **`design/prototype/` is reference only.** Never copy code from it.

---

## 9. Definition of done

- [ ] `npx supabase db reset` from empty applies `0001`–`0005`.
- [ ] **RLS proven**: a test shows user A cannot modify or delete user B's items.
- [ ] Edit, favourite, log-as-worn and delete all work and persist across a reload.
- [ ] The overflow sheet matches the design's four rows and order; Delete uses `danger` tone.
- [ ] Item detail shows **no** worn count and **no** favourite indicator.
- [ ] Offline disables the write actions; no copy promises a retry.
- [ ] Backend test count has not dropped (**549** on `rebuild` today).
- [ ] Frontend test count has not dropped (**127** today).
- [ ] `ruff`, `ruff format --check`, `mypy`, `pytest`, `lint-imports`, `eslint`,
      `tsc --noEmit`, `next build` all clean.
- [ ] **Checked in a browser**, not just in tests — at `localhost:3000` *and* `127.0.0.1:3000`.
- [ ] No secret in the diff.

---

## 10. If you hit a gap

`docs/design-decisions.md` §21 has two **deferred** items; everything else is decided. This
slice has at least three genuine gaps already named — delete confirmation (§5.4), the wear
model (§5.1), and double-tap-in-one-day semantics (§2.3). **Record each with its
alternatives; do not invent a value and move on.**

When you write `research.md`, the failure mode to guard against is not weak reasoning — it is
an **incomplete option list**. Feature 001 shipped a defect whose decision record was
well-argued but never considered the option that turned out correct. Ask what you have not
listed.

## 11. Report back with

What you built · the wear model and why · what you decided about delete confirmation · the
RLS policy and how you proved it · what you found and did with 004's unfinished overflow
sheet · which Constitution Check gates you could not satisfy · the §9 results · what you
saw in the browser.

**Name what you skipped.** A report admitting two gaps is worth more than one claiming a
clean sweep.
