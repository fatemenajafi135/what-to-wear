# Deferred work

Work that is **decided and parked**, not forgotten and not in progress. The feature plan
(`feature-plan.md`) tracks slices; this tracks everything that fell out of a slice with a
"later" attached to it.

Same purpose as `ios-verification-backlog.md`, which says it best: this file exists so
*"we'll come back to it"* never silently becomes *"we forgot about it."*

## How to use it

- **A slice that defers something adds a row here**, with the decision record that explains it.
  A deferral with no written reasoning is not a deferral, it is an omission.
- **Nothing here blocks a feature.** If it blocks one, it belongs in that feature's handoff.
- **Check the "stale" section before implementing** — the rebuild has already overtaken several
  gaps inherited from the prototype.

---

## Open

| # | Item | Where it's specified | Why it's parked |
|---|---|---|---|
| 1 | **Outfits gallery has no pagination** — `list_outfits` returns every row and signs a thumbnail for each. Defensible when saving needed a heart tap; §42's auto-save now adds ~4 rows per styling request. `wtw_closet_page_size` + "Load more" (004) is the established pattern to copy. | Found in the 010 review, 2026-08-02 | Cheap now, awkward later. Fold into whatever touches Outfits next rather than spinning a branch. |
| 2 | **Outfits filter facets** (Occasion / Weather / Formality) — 010 ships sort only. | `design-decisions.md` §41 | No reliable data shape: `occasion` is free text and `meta_line` collapses weather-or-formality into one string. **§41's option (b) is the recommended fix** — bucket into fixed categories at save time from the pipeline's own `Context`. Written up so it needn't be re-derived. |
| 3 | **Calendar shows a fixed 7-day window** | `design-decisions.md` §21 | It's a design change, not a constant tweak — needs a product decision about what the window should be. |
| 4 | **Calendar has no caching** — correct, just slow on a slow link. | `design-decisions.md` §21 | Measured and accepted. Revisit if it becomes a real complaint. |
| 5 | **Preference memory derives nothing.** `SupabaseClosetRepository.get_derivation_inputs` returns `([], {})`, so `memory/preferences.py` — ported whole in 007 — has never had an input. | `repositories/supabase_closet.py` docstring | Its own comment says "feature 010's territory"; **010 shipped without it**, so this is now orphaned rather than assigned. Anything wired to it looks like personalisation while doing nothing. Needs an owning slice. |
| 6 | **001 visual conformance audit** — components have never been checked against `design-system.md` §3's padding / size / per-state tables. | Owed from the 001 review | Never done. Not a defect list, a verification pass. Needs no branch. |
| 7 | **Offline is display-only** — the banner shows and actions disable, but nothing is queued for retry. Copy deliberately promises nothing. | `known-gaps.md` §0 | A real queue means IndexedDB + Background Sync + per-item retry UI. Scoped in `known-gaps.md`; belongs with 014. |
| 8 | **No account deletion, no data export, no password change** — `known-gaps.md` calls these "near-mandatory before shipping" given the app stores photos and body data. | `known-gaps.md` §0.6 | Not in any slice. Should become one before any real launch. |
| 9 | **Full RTL** — logical properties are already used throughout, but mirroring is unverified and numerals/typeface choices are unresolved. | `known-gaps.md` §0.5 | Deferred by design, with the groundwork deliberately laid. |
| 10 | **iOS behaviour is built blind** — 24 items awaiting a physical iPhone. | `ios-verification-backlog.md` | Blocked on hardware, not on a decision. |
| 11 | **`Button.tsx` href-mode renders a default anchor underline** — the same artifact 011 fixed on History rows, still present on the shared component. | Flagged in 011's browser-verification pass, 2026-08-03 | Correctly left out of 011: a cross-cutting change to a widely-used component doesn't belong in a feature branch. Wherever it lands, check every `href`-mode Button, not just the one that surfaced it. |

---

## Registers this consolidates

This file is an index, not a replacement. The detail lives where it was decided:

| Register | Holds |
|---|---|
| `docs/design-decisions.md` | Every decision, including the deferred ones (§21, §41). Amend forward, never edit history. |
| `docs/ios-verification-backlog.md` | Everything needing a physical iPhone. |
| `design/known-gaps.md` | What the **prototype** deliberately left undone. Predates the rebuild — see below. |
| `docs/feature-plan.md` | The slices themselves. |

---

## Stale — inherited from the prototype, since overtaken

`known-gaps.md` documents what the *prototype* lacked. The rebuild has implemented several, so
these entries no longer describe reality. Worth clearing when someone next edits that file, so
it doesn't keep reading as an open list:

| Entry | Status |
|---|---|
| §0.7 Greeting is hardcoded | **Done** — feature 008, `lib/recommend/timeOfDayGreeting.ts` |
| §0.8 Match scores are hardcoded | **Done** — real scores from the pipeline's own scorers (009/010) |
| §1 True `:focus-visible`, not bare `:focus` | **Done** — `design-decisions.md` §4 replaced the shadow ring with `outline` + `outline-offset`; `styles/globals.css` uses `:focus-visible` |
| §2 Switch semantics | Already marked RESOLVED in that file |
