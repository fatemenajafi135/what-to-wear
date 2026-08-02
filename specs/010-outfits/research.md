# Research — Feature 010: Outfits gallery + detail

The handoff named one open decision as its headline gap (§3, citation/score persistence) plus
two further named-but-undecided questions (outfit-level "worn today", delete confirmation), and
warned — as it has on every prior feature — that the failure mode to guard against is an
**incomplete option list**, not weak reasoning. A fourth gap (filter-facet data shape) surfaced
while drafting the spec and was resolved the same way: named, alternatives listed, decided
explicitly rather than guessed. All four decisions were made *before* this planning phase, via
`/speckit-clarify` and direct research into the pipeline/repository code, and are recorded in
full in `docs/design-decisions.md`. This document summarizes each and points there, matching how
`specs/009-suggestion-pager/research.md` referenced `docs/design-decisions.md` §32-36 rather than
re-deriving them.

## 1. Citation and per-dimension score persistence

Full reasoning, schema, and every option considered: `docs/design-decisions.md` §38.

Summary: `SaveOutfitRequest` gains a required `thread_id`. The save route calls
`get_compiled_graph(repo).get_state({"configurable": {"thread_id": thread_id}})` and reads
`last_result: SuggestResult | None` off the snapshot — the same field the graph's own
`score_and_rank`/`explain` nodes already populate for refinement turns. It checks
`state["user_id"] == caller's user_id` before trusting anything from the snapshot (the
checkpointer has no RLS of its own — this is application-level ownership checking on a second
piece of per-user state, the same discipline the handoff names for the `outfits` table itself).
The specific `ScoredOutfit` being saved is matched by exact ordered equality against
`outfit.items` (already a true invariant end-to-end: `SuggestionPager.tsx` sends `item_ids` in
`StylingOutfit.items`'s own order, itself sourced unchanged from `ScoredOutfit.items`).

Two new text/jsonb columns hold what's needed to render inline badges identically to how 008 once
did it, before 009 removed the (then-unused) citation path: `rationale_with_citations` (the
`[n]`-marked-up text, resurrecting `bdc9ad4`'s exact marker convention) and `citations`
(`[{number, text}]`, resurrecting the old `CitedRule` shape). `dimension_scores`
(`[{dimension, value}]`) holds the bar data — `reason` is deliberately not persisted (no design
surface renders it). When the thread's checkpointed state is unavailable (evicted, restarted, a
`thread_id` the client never sent, or a match not found), the save still succeeds with empty
citations/scores — the same honest-empty treatment Constitution IV already requires for "nothing
to cite," extended to "can no longer prove what was cited."

**Why not recompute at read time**: explicitly out of scope per the handoff — re-running the
pipeline produces different reasoning than what the user actually saved, and this feature has no
business calling `pipeline/` at all (Constitution I).

## 2. Outfit-level "worn today" also logs every item

Full reasoning, schema, and every option considered: `docs/design-decisions.md` §39.

Summary: resolved via `/speckit-clarify`, reversing the initial recommendation on review. Logging
an outfit as worn writes (a) one `outfit_wears` row (new table, same per-day-unique shape as
005's `item_wears`, needed because "Most worn" is a listed Outfits sort facet and `item_wears`
alone can't answer it for an outfit), and (b) one `item_wears` upsert per item still owned by the
caller, using the exact statement `supabase_closet.py::record_wear` already uses. Both writes
happen in one repository call/transaction; each side's idempotency is per-row
(`unique (outfit_id, worn_date)` / `unique (item_id, worn_date)`), so a retried request after a
partial failure is always safe. An item the outfit references but the user no longer owns is
silently skipped for (b), never a failure of the whole action.

## 3. Delete requires confirmation

Full reasoning: `docs/design-decisions.md` §40.

Summary: reuses feature 005's exact bespoke confirmation `<dialog>` (§22.2) — title
`Delete {outfit title}?`, body `This can't be undone.`, outline Cancel + danger-toned Delete,
`showModal()`/focus-trap/restore — parameterized by outfit title instead of item name. Every
reason 005 gave for confirming a closet-item delete (a single tap in a multi-row danger-toned menu
item, no recovery path) applies identically to a saved outfit, which by this feature also carries
its own persisted reasoning (§38) — losing it to a mis-tap is the same or a higher-stakes mistake,
not a lower one.

## 4. Filter facets dropped; sort-only ships

Full reasoning and every option considered: `docs/design-decisions.md` §41.

Summary: resolved via `/speckit-clarify`. `outfits` has no reliable structured data to filter
occasion/weather/formality by (`occasion` is pipeline-normalized free text; `meta_line` collapses
formality-or-weather into one string per §34, indistinguishable from each other once stored). The
product owner explicitly deprioritized building the bucketing needed to fix this properly
("keep it somewhere so we don't miss it, but it's not important for now") rather than declining it
— so this feature ships **sort only** (date added default, favorited-first, most worn via the new
`outfit_wears` count) and the "Filter & sort" pill becomes a sort-only trigger for this slice, with
no facet chips, no active-filter count badge, and no "Clear" link (nothing is ever in a filtered
state). §41 records the rejected bucketing approach in enough detail that a future feature can
implement it directly rather than re-deriving it.

## 5. Frontend citation rendering — resurrecting rather than reinventing

Not a named gap, but a real implementation decision worth recording here since it isn't in
design-decisions.md (a rendering-pattern choice, not a product/data decision). Feature 008 built a
working `[n]`-token parser (`ChatMessageList.tsx`'s `CITATION_TOKEN` regex + `renderWithCitations`)
and a `CitedRuleList` component; 009 deleted both once every outfit reply moved to the
citation-free pager (§33/§35), leaving `Badge`'s `citation` tone as the only surviving piece.
Outfit detail needs the exact same rendering — numbered `[n]` tokens replaced with `Badge`
components inline, plus a below-the-fold numbered list — so this feature resurrects that removed
code (visible via `git show c545533:frontend/components/recommend/ChatMessageList.tsx` and
`.../CitedRuleList.tsx`) into new, Outfit-detail-scoped components (`RationaleWithCitations.tsx`,
`CitedRuleList.tsx` under `app/(app)/outfits/[outfitId]/`) rather than writing a new parser from
scratch. **Rejected**: storing pre-split React-renderable segments instead of a marked-up string
plus a regex parse at render time — the regex approach is already proven, tested code with a known
correct behavior; reintroducing it costs less and risks less than a new representation.

## 6. Two-pane desktop layout — mirroring Closet's mechanism exactly

Not a named gap. `design-system.md` §5 requires a desktop two-pane master-detail for the Outfits
gallery, the same requirement Closet already satisfies. Closet's mechanism (confirmed by direct
inspection, not assumed): one shared grid component (`ClosetGrid`) rendered by both `/closet/
page.tsx` (with an empty detail-placeholder pane) and `/closet/[itemId]/page.tsx` (with the grid
in a `.gridPane` beside real detail content), toggled by a shared `page.module.css`'s
`.twoPane`/`.gridPane`/`.detailPane` media-query classes — plain CSS visibility, not Next.js
parallel routes and not client-side layout state. Outfits mirrors this exactly (`OutfitsGrid.tsx`
standing in for `ClosetGrid`) rather than introducing a second desktop-layout mechanism into the
codebase for no reason (Quality Bar: no abstraction without a measured problem — an existing,
working mechanism already solves this).
