# Handoff — Feature 010: Outfits gallery + detail

**From:** tech lead · **Status:** ready to start · **Branch:** `feat/010-outfits`, cut from
`rebuild` · **Migration number: `0010`** ·
**`design-decisions.md` sections start at `## 38`**

**Run this alone.** It extends the table and routes 009 just landed.

---

## 1. Mission

**I browse the outfits I've saved, filter them, open one, and see the full reasoning behind
it.**

---

## 2. What 009 gave you

| | |
|---|---|
| `outfits` table | `id, user_id, occasion, meta_line, rationale_text, match_label, item_ids, favorite, created_at, updated_at` (migration `0009`) |
| Save a suggestion | `POST /api/v1/recommend/outfits` |
| Toggle favourite | `POST /api/v1/recommend/outfits/{id}/favorite` |
| Its reasoning | `docs/design-decisions.md` §32–36 |

`favorite` is existence + flag: un-saving flips it, never deletes. 009's schema comment is
explicit that **Delete is yours.**

---

## 3. ⚠️ Outfit detail's two defining features are not in the database

Read this before planning. It is the same shape as 009's persistence gap, and it will derail
the slice if you meet it mid-implementation.

Design-system § Outfit detail specifies the page carries, in one card:

- *"the styling description as plain text … **with inline numbered citation Badges (this is now
  citations' only home)**"*, then *"the full numbered styling-rules list"*;
- *"a **'Match breakdown'** section … then the **per-dimension bars** … one per sub-score."*

**Neither is stored.** 009's columns say so in their own comments: `rationale_text` is *"Plain
text, never citation markers"*, and `match_label` is *"The label only, never the underlying
float."* There are no citations and no per-dimension scores in `outfits`.

They are also not recoverable after the fact. The pipeline produces both — `ScoredOutfit.scores`
carries one `DimensionScore` per `SCORE_DIMENSIONS`, and `Rationale.cites` plus
`SuggestResult.sources` carry the citations — but `StylingOutfit` (what the client receives)
flattens them away, and `SaveOutfitRequest` echoes back only what the client has. Re-running the
pipeline later would produce *different* reasoning than the outfit the user actually saved.

### Options

| Option | Assessment |
|---|---|
| **(a) The save route persists them server-side, read from the thread's `last_result`** | `GraphState.last_result` holds the `SuggestResult` in the checkpointer, so the server can take citations and dimension scores from its own pipeline output rather than from the client. **My recommendation.** Citations are grounding proof (Principle IV); provenance the client hands back is unverified by construction. Cost: save couples to thread state, so decide what happens when the thread is gone. |
| (b) Return them in `StylingOutfit`, client echoes them on save | Simple, and symmetrical with how `occasion` already round-trips. But it means a client can assert which styling rules justified an outfit, which is exactly what Principle IV exists to prevent. |
| (c) Detail omits both | Contradicts the design system in two separately-specified places, and removes the only thing distinguishing detail from the gallery card. |

Whichever you choose, **record it — §38 — with the alternatives.** If you take (a), the schema
change is yours and belongs in migration `0010`.

---

## 4. In scope

### 4.1 Routes

List (the gallery), get one (detail), delete, and rename. Extend the existing router rather than
adding a second one; follow `0002`'s **RLS *and* GRANT** pattern for anything new, proven by a
two-user test.

**Ownership is validated in the query, not only by RLS** — 009's own schema comment notes
`item_ids` has no array-level FK and ownership is checked before insert. Reads must do the same.

### 4.2 Outfits gallery (`/outfits`)

Sticky `TopHeader` ("Outfits", subtitle = count), a **"Filter & sort"** pill using the same
Lucide `sliders-horizontal` glyph as `IconButton`'s `filter` keyword — one filter icon across the
app — and a "Clear" link only while filters are active.

A **vertically stacked list of cards**, not an image grid: `radius-lg`, surface fill, bordered,
14px padding, 12px gap. Each card:

- **Header row**: title (truncates) · match-label pill · spacer · favourite heart · "⋯" overflow.
  Both icon controls get 44px hit areas and real `aria-label`s ("Save outfit"/"Unsave outfit",
  "More options"). Date on its own line below.
- **Inline title rename** — tapping the title swaps it for a text input plus a small "Done" pill,
  date still beneath. **On-card, not in the sheet.**
- **Item row**: up to **4** thumbnails; past 4, the first **3** plus a **"+N"** chip in the 4th
  slot (52px). Never more than 4 slots, no scroll, no wrap. Real thumbnails tap through to
  `/closet/:itemId`; the **chip taps through to Outfit detail**.

At desktop this list is the wide pane beside a detail pane, with *"Select an outfit to see its
details."* when nothing is selected.

Empty/error copy is specified verbatim — `outfits.empty.first_run.*`,
`outfits.empty.filtered.*`, `outfits.error.*`. Use it exactly.

### 4.3 Outfit detail (`/outfits/:outfitId`)

`TopHeader` (title = outfit title, subtitle = date) with **two** sibling icon controls: a
favourite heart, then "⋯" → the outfit-menu `BottomSheet`.

One surface card containing, in order:

1. **The item grid — deliberately large tiles**, `aspect-ratio: 1`, `radius-md`: **2 columns
   mobile, 3 tablet/desktop**. No scroll, no cap, no chip; every item shows. Use
   `components/ui/ItemPhoto` so these inherit the 1:1 letterbox and detected backdrop.
2. The description as plain text with **inline numbered citation Badges** (§3).
3. Below a dashed border, the **numbered styling-rules list**.
4. A second dashed divider, then **"Match breakdown"**: a "Match level: {label}" row using the
   same pill as the gallery and pager cards, then **per-dimension bars** (`--color-primary` fill,
   `--color-surface-sunken` track).

**No inline actions on this page.** "Log as worn today", Edit title and Delete live in the
overflow sheet. The heart is the single exception.

### 4.4 The overflow sheet

Rows: **Log as worn today · Edit title · Delete**, Delete in `BottomSheet`'s `danger` tone.

Two decisions here, both yours to make and record:

- **"Log as worn today" on an *outfit*.** `item_wears` (005) is per-item. Does this write one row
  per item in the outfit, or does an outfit-level wear need its own table? 005's handoff already
  asked what "worn twice in one day" means — stay consistent with whatever it decided.
- **Delete.** 005 shipped a hard delete for items with no confirmation, and flagged that as a
  real gap. Decide deliberately here rather than copying it by default.

---

## 5. Explicitly out of scope

Chat history (**011**) · conversational turns (**016**) · any change to `pipeline/`, `scoring/`
or `retrieval/` · re-running generation to reconstruct a saved outfit's reasoning (§3 (c)) ·
sharing or exporting an outfit.

---

## 6. Traps

1. **Do not change pipeline behaviour.** `docs/eval-baselines/` holds three iterations of
   recorded work. If your diff touches `pipeline/`, `scoring/` or `retrieval/`, re-run the evals
   and justify every movement.
2. **No numeric score or percentage anywhere** — the Match breakdown shows bars and a label. The
   float is never text. This is the surface most likely to leak one.
3. **Citations live only here.** Do not add them to the gallery card or the pager.
4. **`GRANT` as well as RLS**, proven by a two-user test.
5. **Regenerate `schema.d.ts`** after the routes land.
6. **One filter glyph** — `sliders-horizontal`, the same as everywhere else.
7. **Do not change `ports.py`** — import-linter contract.
8. **`design/prototype/` is reference only; `../app-legacy` is read-only.**

---

## 7. Definition of done

- [ ] Outfits I saved from the pager appear in the gallery, newest first.
- [ ] Opening one shows every item at 2 columns (mobile) / 3 (desktop), the description with
      citation badges, the rules list, and the Match breakdown.
- [ ] The heart is in sync across gallery card, detail header and overflow row.
- [ ] Inline rename works on the card and persists.
- [ ] A 5-item outfit shows 3 thumbnails + "+2"; the chip opens detail.
- [ ] Filters work; clearing them restores the full list; both empty states use the exact copy.
- [ ] No number, percentage or raw score anywhere on screen.
- [ ] **RLS proven**: user A cannot read, rename or delete user B's outfit.
- [ ] `npx supabase db reset` from empty applies `0001`–`0010`.
- [ ] Backend test count has not dropped (**660** on `rebuild` today).
- [ ] Frontend test count has not dropped (**263** today).
- [ ] `ruff`, `ruff format --check`, `mypy src`, `pytest`, `lint-imports`, `eslint`,
      `tsc --noEmit`, `next build` all clean.
- [ ] Eval baselines unchanged.
- [ ] **Checked in a browser** at `localhost:3000` *and* `127.0.0.1:3000`, both themes, at mobile
      *and* desktop widths — desktop is a two-pane layout this slice introduces.

---

## 8. If you hit a gap

Start new `design-decisions.md` sections at **`## 38`**. §32–36 are 009's; §37 is the
conversational-turns amendment; §21 holds two deferred calendar items.

Named decisions: the §3 persistence choice, outfit-level "worn today", and delete confirmation.
**Record each with its alternatives.**

The failure mode to guard against in `research.md` is not weak reasoning — it is an **incomplete
option list**. §37 exists precisely because §28 was well-argued, correctly rejected the two
options it considered, and never considered the third. Ask what you have not listed.

And: **check what actually reached the database, not that the request succeeded.** Three defects
shipped on this project because a value was accepted with a 2xx and then silently dropped or
defaulted before storage.

---

## 9. Report back with

What you built · how you resolved §3 and what a saved outfit's row actually contains now ·
what "log as worn" does for an outfit · what you decided about delete confirmation · how you
proved RLS · whether the eval baselines moved · the §7 results · **what you saw in a browser at
both widths.**

**Name what you skipped.**
