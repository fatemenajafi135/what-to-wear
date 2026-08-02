# Handoff — Feature 009: Outfit suggestion pager

**From:** tech lead · **Status:** ready to start · **Branch:** `feat/009-suggestion-pager`,
cut from `rebuild` · **Migration number: `0009`** ·
**`design-decisions.md` sections start at `## 32`**

**Run this alone.** It changes the styling route's response shape, which nothing else can
be building against at the same time.

---

## 1. Mission

**I ask for an outfit and get several suggestions I can page between, save the ones I like,
and give feedback on.**

Feature 008 renders exactly one outfit per reply. The pipeline has always returned a ranked
list; 008 shows `outfits[0]` and discards the rest.

---

## 2. Read §3 first

There is one scoping decision here that determines the shape of the whole slice, and it is
not obvious from the feature plan. Do not start planning until you have read it.

---

## 3. The pager card needs persistence that does not exist

Two elements the design specifies on every pager card have nowhere to go today:

**The favourite heart.** Design system, § Outfit suggestion pager: *"Tapping the heart calls
the same favorite state the gallery card's heart displays, so a saved suggestion shows up
favorited in Outfits too — this is the pattern's **only** path to favoriting a suggestion."*

**The card tap target.** *"The card itself … is tappable → navigates to that suggestion's
Outfit detail."*

Both need a saved outfit with an id. **No outfit is persisted anywhere** — I checked every
migration and the live database: `calendar_connections`, `calendar_oauth_attempts`,
`catalog_items`, `item_wears`, `picked_events`, `user_profile`, `wardrobe_items`. Nothing
else. A suggestion today exists only inside one HTTP response.

### The decision, and my recommendation

**009 owns outfit persistence; 010 owns the screens that browse it.** That is: this slice
adds the table, the save/unsave route, and the heart that writes to it. Feature 010 then
builds the gallery and the detail page on data that already exists, which is a much better
shape for it than building a screen and its storage at once.

The alternatives, so you can argue with this rather than inherit it:

| Option | Why not |
|---|---|
| Defer the heart and the tap-through to 010 | Leaves two specified elements missing from every card, and 010 then has to revisit a screen it does not own. |
| Build the heart with component-local state | A heart that forgets on reload is a lie to the user, and the design explicitly ties it to the gallery's state. |
| Reorder — do 010 first | 010's gallery has nothing to list until suggestions can be saved, so it inherits the same problem pointed the other way. |

If you take the recommendation, keep the schema **minimal**: what it costs to save and
re-read a suggestion, not what a gallery might want. 010 can extend it. Record the decision
either way — §32.

**The tap-through target (`/outfits/:id`) is 010's screen and does not exist.** Wire the card
to navigate there anyway if you build persistence; a 404 on a route not yet built is honest.
Do **not** build Outfit detail — it carries the full citation-backed reasoning and is a slice
of its own.

---

## 4. What already exists

| | Where | State |
|---|---|---|
| The full ranked list | `pipeline.graph` → `SuggestResult.outfits: list[ScoredOutfit]` | Complete — 008 uses `[0]` |
| Score → label | `api/v1/routes/recommend.py::match_label` | Complete, including the `< 0.4` rule |
| Item resolution + signed URLs | `_resolve_outfit` | Complete for one outfit |
| Thumbnail row, 1:1 photos with backdrop | `components/recommend/ItemThumbnailRow`, `components/ui/ItemPhoto` | Complete |
| Chat surface, hero, composer, readiness gate | `components/recommend/*` | Complete (008) |
| `favorite` on a wardrobe item | `wardrobe_items.favorite` | **Not this.** That is a garment favourite (005), unrelated to saving an outfit. |

---

## 5. Scope corrections

### 5.1 Never render a number

Design system, emphatic: *"**No numeric score or percentage is ever displayed anywhere in the
UI.**"* `ScoredOutfit` carries `rank_score` and per-dimension `scores`; only the **label**
reaches the screen. `match_label` already encodes the thresholds — reuse it, do not re-derive
them.

An outfit scoring **< 0.4 is filtered out entirely**, not shown with a discouraging label.
008 already does this for the single outfit; for a list it means filtering before paging, and
an empty result after filtering is the **Empty** state, not an empty pager.

### 5.2 No citations on the pager card

§ Badge: the `citation` tone is *"used **only in Outfit detail's description**, never in the
chat outfit card — the chat card's description is plain text with no citation markers."*

008 renders inline `[n]` citation badges plus a rule list for a **single-outfit reply in the
bubble**. That stays. The pager card's description is plain text. Getting this backwards
builds the thing § Badge explicitly forbids.

### 5.3 Feedback is not persisted, and is not a favourite

The footer's thumbs-down/thumbs-up are *"**pure feedback on the suggestion — not a
save/favorite action**"*, mutually exclusive per card, each toggling off on a second tap,
with *"no persisted effect on the outfit itself (a future build should send this as a signal
to the recommender)"*.

So: component state only. Do **not** wire it to `memory/preferences.py` — `get_derivation_inputs`
is still a stub returning `([], {})`, so anything you feed it goes nowhere and would look
like working personalisation. Record that you left it.

### 5.4 The pager behaves differently at mobile and desktop — deliberately

- **Mobile**: the track shows exactly one card, `overflow: hidden`, **no native swipe at all**.
  A CSS `transform: translateX(-100% × index)` slide is the only way the visible card changes.
  Paging is arrow-button-only, *"precisely so there's a single unambiguous way to move between
  suggestions on a touch screen."*
- **Tablet/desktop**: a native horizontal scroller, `scroll-snap-type: x mandatory`,
  `scroll-snap-align: center`, cards at ~92% width so neighbours peek, hidden scrollbar. The
  same arrow row still works, and a `scroll` listener keeps the index in sync.

Prev/next are **real `<button>`s below the track**, in their own control row with the position
indicator between them — not overlaid on the card. 32px visual circle, 44px hit area, real
`disabled` at the ends, `aria-label` "Previous suggestion" / "Next suggestion". **Both
controls and the indicator are hidden outright — not disabled — at exactly one card.**

### 5.5 Thumbnails wrap, never scroll

Inside a card the thumbnail grid **wraps onto more rows** — 4 columns mobile, 8 tablet/desktop,
56px at 6px gap. Never a horizontal scroller: the card already sits in a horizontally-paging
track, and nested same-axis scrolling makes the gesture ambiguous. An outfit can carry 1 to
about 10 items; the card grows.

---

## 6. In scope

- Migration `0009` (if you take §3's recommendation), following `0002`'s **RLS *and* GRANT**
  pattern, proven by a two-user test.
- The styling route returns **all** surfaced outfits, not `outfits[0]`. This changes
  `SendMessageResponse` — regenerate `schema.d.ts`.
- Save/unsave a suggestion.
- The pager: card, header pill, heart, description, thumbnail grid, meta line, feedback footer,
  control row, and all four **group states** (Loading skeleton / Ready / Empty / Error) with
  the design's exact copy.
- Reduced-motion gating on the slide.

## 7. Explicitly out of scope

Outfits gallery and Outfit detail (**010**) · chat history (**011**) · feeding feedback to the
recommender (§5.3) · any change to `pipeline/`, `scoring/` or `retrieval/` · implementing
preference memory.

---

## 8. Traps

1. **Do not change pipeline behaviour.** `docs/eval-baselines/` holds recorded runs from three
   iterations. If your diff touches `pipeline/`, `scoring/` or `retrieval/`, re-run the evals
   and justify every movement. The cheapest correct answer is not to touch them.
2. **Do not change `ports.py`** — import-linter contract.
3. **No numbers on screen** (§5.1).
4. **Citations on the bubble, never on the card** (§5.2).
5. **`GRANT` as well as RLS** on any new table.
6. **Regenerate `schema.d.ts`** after the response shape changes.
7. **Qdrant must be running and populated** or replies come back with no citations and it
   looks like a pipeline bug.
8. **`design/prototype/` is reference only; `../app-legacy` is read-only.**

---

## 9. Definition of done

- [ ] One styling request returns several suggestions; arrows page between them; the indicator
      reads "2 of 4".
- [ ] At exactly one suggestion, the arrows and indicator are **absent**, not greyed.
- [ ] An outfit scoring below the floor never appears; a reply with none left shows **Empty**,
      not an empty pager.
- [ ] The heart persists across a reload (or its absence is recorded per §3).
- [ ] Thumbs are mutually exclusive, toggle off, and persist nothing.
- [ ] No number, percentage or raw score anywhere on screen.
- [ ] No citation badge on a pager card.
- [ ] Thumbnails wrap to more rows; the track never scrolls horizontally on mobile.
- [ ] `npx supabase db reset` from empty applies `0001`–`0009`.
- [ ] Backend test count has not dropped (**644** on `rebuild` today).
- [ ] Frontend test count has not dropped (**247** today).
- [ ] `ruff`, `ruff format --check`, `mypy src`, `pytest`, `lint-imports`, `eslint`,
      `tsc --noEmit`, `next build` all clean.
- [ ] Eval baselines unchanged, or re-recorded with justification.
- [ ] **Checked in a browser** at `localhost:3000` *and* `127.0.0.1:3000`, both themes, and at
      mobile *and* desktop widths — the pager genuinely differs between them.

---

## 10. If you hit a gap

Start new `design-decisions.md` sections at **`## 32`**. §21 holds two deferred calendar items;
everything else there is decided.

The named decision is §3 — outfit persistence — and it is the one to get right before writing
code. **Record it with the alternatives above, and say which you chose and why.**

When you write `research.md`, the failure mode to guard against is not weak reasoning — it is
an **incomplete option list**. Feature 001 shipped a defect whose decision record was
well-argued but never considered the option that turned out correct. Ask what you have not
listed.

One more, learned the hard way across 006 and 008: **check what actually landed in the
database, not just that the request succeeded.** Two separate defects shipped because an
attribute was extracted, accepted by the API, and then silently dropped or defaulted before
storage. A 201 proves nothing about what was stored.

---

## 11. Report back with

What you built · what you decided about outfit persistence and why · how paging differs
between mobile and desktop and how you verified both · what you did with the feedback controls ·
whether the eval baselines moved · the §9 results · **what you saw in a browser at both
widths**, and **what a saved outfit actually looks like in the database**.

**Name what you skipped.** A report admitting two gaps is worth more than one claiming a clean
sweep.
