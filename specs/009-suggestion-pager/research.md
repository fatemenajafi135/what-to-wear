# Research — Feature 009: Outfit suggestion pager

The handoff named one open decision (§3, persistence) and warned the failure mode to guard
against is an **incomplete option list**, not weak reasoning (feature 001's real defect).
Research below covers that decision plus two further design-system ambiguities found while
reading the pager spec closely, and the mechanical approach for the mobile/desktop paging split
the handoff calls out as a likely-to-be-gotten-backwards trap.

## 1. Outfit persistence — schema shape and the favorite/save mechanic

Full reasoning, every option considered, and the schema itself: `docs/design-decisions.md` §32.
Summary: 009 owns a minimal `outfits` table (RLS + GRANT per the `0002` pattern) and the
save/toggle-favorite route pair; 010 owns the gallery/detail screens that read it. The heart's
first tap inserts (`favorite = true`); its second tap flips the same boolean via the identical
`UPDATE ... RETURNING` pattern `supabase_closet.py::toggle_favorite` already uses for wardrobe
items — it does not delete the row, so an out-of-scope-for-this-feature "saved but unfavorited"
state stays representable for 010's overflow-menu Delete action to control independently.

**Why `item_ids uuid[]` and not a join table**: no per-item metadata (position aside, which array
order already gives for free) is read or written anywhere in this slice's scope; a join table is
schema for a need 010 might have, not one 009 does (Quality Bar: no abstraction without a
measured problem). Re-resolving items from `wardrobe_items` by id at read time (not persisting a
resolved snapshot) keeps a saved outfit's display current with any later edit to those items,
mirroring the existing "resolve server-side, don't cache" convention (design-decisions.md §24).

## 2. The pager card carries no citations — resolving design-system.md's self-contradiction

Full reasoning: `docs/design-decisions.md` §33. § Badge and the dedicated § Outfit suggestion
pager component section both explicitly and repeatedly forbid a citation `Badge` on a pager card;
one clause in the more general § Screen anatomy → Recommend paragraph says the opposite ("its own
citation-bearing reasoning block and rule list"). Treated as a stale artifact of that paragraph
describing the pager by analogy to 008's single-outfit citation pattern one sentence earlier,
never reconciled when the pager's own later, far more detailed section was added. The two
component-level sections win — same "component spec over screen-anatomy aside" reasoning this
document has applied to prior contradictions, not a new rule invented for this feature.

**Consequence for the response contract**: since every outfit-bearing reply now renders through
the (citation-free) pager, including the one-outfit case (§4 below), `SendMessageResponse.
citations` and the `[n]`-marker embedding in `_resolve_outfit` have no remaining renderer at all
and are removed outright rather than kept as unused dead weight (design-decisions.md §35).
Citation data is not lost forever — it lives on the pipeline's own unmodified `ScoredOutfit.
rationale`/`SuggestResult.sources` (Principle I), available to feature 010 (Outfit detail, which
does need citations) to re-resolve when it's built.

## 3. The meta line's `{occasion} · {formality|weather}`

Full reasoning: `docs/design-decisions.md` §34. Neither field exists on `ScoredOutfit` — both
live on `SuggestResult.context` (one `Context` per reply, shared by every card in that reply's
pager, since one `Context` describes the one request that produced all of them). `{occasion}` =
`context.occasion`. `{formality|weather}` = `context.condition` when the pipeline detected
weather context, else `context.formality`'s label — weather preferred because it's the more
specific, opt-in signal; formality is the correct fallback because `Context.formality` is a
required field, never absent.

**Rejected**: deriving formality from the outfit's own resolved items (a mode/majority
computation) instead of `context.formality` — would silently diverge from what the user actually
asked for and introduces new per-outfit computation with no existing pipeline equivalent, which
Principle I counsels against.

## 4. Response shape: `outfit` → `outfits`, and what happens to the single-outfit case

Full reasoning: `docs/design-decisions.md` §35. `SendMessageResponse.outfit: StylingOutfit | None`
becomes `outfits: list[StylingOutfit]` (empty list is the "nothing surfaced" case — matches the
pager's own Empty group-state instead of introducing a second, redundant null-vs-empty
distinction). Every reply with ≥1 surfaced outfit renders through the pager, **including exactly
one** (FR-003: single card, no arrows/indicator) — the handoff's mission is explicit that this
"replac[es] 008's single flat item-thumbnail-row rendering entirely," so there is no remaining
outfit count at which the old bubble-plus-citations treatment still applies. `StylingOutfit`
gains `id: str | None` (the saved-outfit id once saved this session, `None` until then) as the
frontend's only signal for a card's heart fill state — no client-side favorite cache is needed
because conversation state itself is never persisted across a reload (design-decisions.md §25),
so a stale "was this saved" question never arises within one mounted session.

**Alternatives considered and rejected**:

| Option | Rejected because |
|---|---|
| Keep `outfit: StylingOutfit \| None` for the top pick, add a separate `alternatives: list[StylingOutfit]` | Two fields the frontend would have to merge into one ordered list defeats the purpose of a single pager track, and creates an artificial "primary vs. alternate" distinction the design system never draws — every card in the pager is presented as an equal peer, not a top pick plus runners-up. |
| Keep the null/non-null distinction for "no outfit" instead of collapsing to an empty list | Forces the frontend to check two different falsy shapes (`null` vs. `[]`) for what the design system treats as one Empty state; collapsing to a single empty-list check is strictly simpler with no information lost — a genuinely failed request is already a distinct HTTP-level error path, not encoded in this field. |

## 5. Mobile vs. desktop pager mechanics — implementation approach

**Context**: design-system.md § Outfit suggestion pager, "Pager mechanics" is fully explicit and
leaves no open design decision — this section records the *implementation* approach, not a new
design choice, since the handoff names this split as a likely-to-be-gotten-backwards trap.

**Mobile** (viewport < 768px, matching the existing §5 breakpoint): the track is a flex row with
`overflow: hidden`, transformed via `transform: translateX(calc(-100% * var(--index)))` (a CSS
custom property set from the `index` state), `transition: transform 200ms` gated on
`prefers-reduced-motion` (existing app-wide reduced-motion pattern, reused not reinvented). No
`overflow-x: auto`/`scroll-snap` at this tier — the design is explicit that native swipe must not
exist at all here, so the track gets no scroll affordance whatsoever; only the arrow buttons
mutate `index`.

**Tablet/desktop** (≥768px): the same track becomes `overflow-x: auto`, `scroll-snap-type: x
mandatory`, each card `scroll-snap-align: center` and `flex: 0 0 92%`, scrollbar hidden
(`scrollbar-width: none` + WebKit equivalent — existing pattern already used elsewhere in the
codebase for hidden-scrollbar rows). A `scroll` listener (debounced via `requestAnimationFrame`,
not a raw per-event handler) recomputes `index` from `scrollLeft / cardWidth` so the arrow
buttons and position indicator stay in sync with manual drag/scroll, and the arrow buttons
themselves call `scrollTo({ left: index * cardWidth, behavior: reducedMotion ? "auto" : "smooth" })`
rather than mutating a transform — the two tiers use genuinely different mechanisms (transform vs.
native scroll), not one mechanism with a CSS override, because the design explicitly wants no
native scroll capability to exist at all on mobile, not merely a visually-hidden one.

**One `SuggestionPager` component, two CSS-driven code paths**: both tiers share the same React
state (`index`, `count`) and the same `PagerControls`; only the track's own markup/CSS and the
`onIndexChange` wiring differ per tier, selected via the existing `@media` breakpoint mechanism
(no JS viewport detection, matching Principle IX's "CSS-only breakpoints" convention already
established for `TabBar`).
