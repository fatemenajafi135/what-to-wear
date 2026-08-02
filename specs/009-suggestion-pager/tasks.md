# Tasks: Outfit suggestion pager

**Input**: Design documents from `/specs/009-suggestion-pager/` (plan.md, research.md,
data-model.md, contracts/recommend.md, quickstart.md)

**Tests**: included. The constitution's Quality Bar requires unit tests for deterministic logic,
and the handoff's Definition of Done requires backend/frontend test counts to not drop
(644 / 247 today) plus a two-user RLS+GRANT proof for the new table — not optional here.

**Organization**: grouped by user story from spec.md, in priority order (P1, P1, P2, P2, P3).

## Phase 1: Setup

- [ ] T001 Create `infra/supabase/migrations/0009_outfits.sql`: the `outfits` table, RLS policy,
      and GRANT per design-decisions.md §32 / data-model.md (`create table outfits (...)`,
      `enable row level security`, `for all using (auth.uid() = user_id) with check (...)`,
      `grant select, insert, update, delete on outfits to authenticated`, plus the existing
      `set_updated_at` trigger convention). Verify locally with
      `npx supabase db reset` (applies `0001`-`0009` clean).

## Phase 2: Foundational (blocks all user stories)

- [ ] T002 Create `backend/src/whattowear/repositories/supabase_outfits.py`:
      `SupabaseOutfitRepository` mirroring `supabase_closet.py`'s session/JWT-claim pattern —
      `create(user_id, occasion, meta_line, rationale_text, match_label, item_ids) -> str` and
      `toggle_favorite(user_id, outfit_id) -> bool | None` (same `UPDATE ... RETURNING` shape as
      `toggle_favorite` for wardrobe items).
- [ ] T003 [P] `backend/tests/unit/test_supabase_outfits_repository.py` (or integration, matching
      whatever `supabase_closet.py`'s own tests do): `create` returns a real id and the row is
      readable back with all fields populated; `toggle_favorite` flips `true`→`false`→`true` and
      returns `None` for another user's id or a nonexistent id.
- [ ] T004 In `backend/src/whattowear/api/v1/routes/recommend.py`: change `StylingOutfit` to add
      `id: str | None` and `meta_line: str`; remove the `[n]`-marker embedding from
      `_resolve_outfit` (rationale_text is now always plain); remove `CitedRule` usage from the
      response path and delete `SendMessageResponse.citations`; change
      `SendMessageResponse.outfit: StylingOutfit | None` to `outfits: list[StylingOutfit]`.
- [ ] T005 In `recommend.py`'s `send_message`: resolve **every** entry in `result.outfits` (not
      just `[0]`) via `_resolve_outfit`, dropping any that returns `None` (below-floor); compute
      `meta_line` once per response from `final_state`'s `Context`. No formality→label mapping
      exists anywhere in the codebase today (checked: backend and frontend both only have the
      raw `Formality` literal, e.g. `"business_casual"`) — add a small local
      `_FORMALITY_LABELS: dict[str, str]` in `recommend.py` itself (Title Case, underscore→space,
      e.g. `"business_casual" -> "Business casual"`), not an imported shared constant, since
      nothing else needs it yet. `meta_line = f"{context.occasion} · {context.condition or
      _FORMALITY_LABELS[context.formality]}"` (research.md §3), set on every resolved
      `StylingOutfit`; `reply_text` is set only when the resolved list is empty (same
      fallback-note logic as today, now keyed on `not outfits` rather than `outfit is None`).
- [ ] T006 [P] Add `POST /recommend/outfits` and `POST /recommend/outfits/{outfit_id}/favorite` to
      `recommend.py` per contracts/recommend.md: `SaveOutfitRequest`, `SavedOutfitResponse`; the
      save route validates every `item_ids` entry against
      `repository.list_wardrobe_items(user_id)` before calling
      `SupabaseOutfitRepository.create(...)`, raising `422` on any id the caller doesn't own; the
      favorite route calls `toggle_favorite`, raising `404` when it returns `None`.
- [ ] T007 [P] `backend/tests/integration/test_recommend_routes.py`: extend for the changed
      `send_message` response shape (multiple outfits, floor filtering, `meta_line` present,
      no `citations` key) and the two new routes (save happy path + ownership-violation `422`;
      favorite toggle + `404` for another user's/nonexistent id).
- [ ] T008 [P] `backend/tests/integration/test_outfits_isolation.py`: two-user RLS+GRANT proof
      mirroring the existing closet isolation test — user A saves an outfit, user B's
      list/attempt to toggle it is rejected/invisible.
- [ ] T009 Run `npm run generate:api-types` (backend running) to regenerate
      `frontend/lib/api/schema.d.ts` against the changed contract (handoff trap #6) — commit the
      regenerated file once T004-T006 are stable.

## Phase 3: User Story 1 - Page between several suggestions (P1)

**Goal**: every surfaced outfit (not just the top-ranked one) renders as its own card in a
pager; paging via arrows works; a single-outfit reply shows one card with no arrows/indicator.

**Independent Test**: send a request producing multiple outfits; confirm a pager (not a flat
card) with a working "1 of N" indicator and prev/next controls; confirm a single-outfit reply
shows no indicator/arrows at all.

- [ ] T010 [P] [US1] Create `frontend/components/recommend/PagerControls.tsx` +
      `.module.css`: prev/next `<button>`s (32px visual / 44px hit area, `disabled` at the ends,
      `aria-label` "Previous suggestion"/"Next suggestion") + "N of M" indicator between them;
      renders `null` entirely when `count <= 1` (FR-003).
- [ ] T011 [P] [US1] `frontend/components/recommend/PagerControls.test.tsx`: renders nothing at
      count 1; renders controls + correct "N of M" at count > 1; `disabled` at first/last index;
      calls `onPrev`/`onNext` on click; not present in tab order when hidden.
- [ ] T012 [P] [US1] Create `frontend/components/recommend/OutfitCard.tsx` + `.module.css`:
      header row (title text, match-label pill per § Scores styling, heart `IconButton` at far
      right), plain-text description (no citation parsing — plain `<p>`, unlike
      `ChatMessageList`'s `renderWithCitations`), `ItemThumbnailRow` (reused, unchanged), meta
      line, feedback footer placeholder (wired in Phase 5). Props: one `StylingOutfit`, `saved:
      boolean`, `onToggleHeart`, `onCardTap`.
- [ ] T013 [P] [US1] `frontend/components/recommend/OutfitCard.test.tsx`: renders title/pill/
      heart/description/thumbnails/meta line; description contains no citation `Badge`; body tap
      (outside heart/thumbnails) fires `onCardTap`; heart tap fires `onToggleHeart` and does not
      also fire `onCardTap` (event doesn't bubble to the card tap handler).
- [ ] T014 [US1] Create `frontend/components/recommend/SuggestionPager.tsx` + `.module.css`:
      owns `index` state (reset to 0 on a new `outfits` array), renders the mobile-tier track
      (`overflow: hidden`, `transform: translateX(-100% * index)`) — desktop mechanics land in
      Phase 6 behind the same component; renders one `OutfitCard` per outfit plus
      `PagerControls` below the track; `index` clamped to `[0, outfits.length - 1]`.
- [ ] T015 [US1] In `frontend/components/recommend/ChatMessageList.tsx`: replace the
      `message.outfit && <ItemThumbnailRow .../>` branch with
      `message.outfits && message.outfits.length > 0 && <SuggestionPager outfits={message.outfits} .../>`;
      remove the now-dead `CitedRuleList`/`renderWithCitations` usage on the outfit path (kept
      only if still reachable from a citation-bearing non-outfit reply — confirm against
      research.md §2/§4 and remove entirely if not).
- [ ] T016 [P] [US1] `frontend/components/recommend/SuggestionPager.test.tsx`: renders N cards
      for N outfits with a working indicator; single-outfit array renders one card, no
      indicator/arrows; index resets to 0 when the `outfits` prop changes identity (new reply).
- [ ] T017 [US1] Update `frontend/components/recommend/RecommendChat.tsx` /
      `ChatMessageList.tsx`'s `ChatMessage` type (and any test fixtures) from `outfit?:
      StylingOutfit | null` to `outfits?: StylingOutfit[]`, sourced from the regenerated
      `schema.d.ts` (T009).

**Checkpoint**: multiple-outfit replies page correctly; single-outfit replies degrade to one
static card. Independently demoable without Phase 4-6 work (heart/feedback can be inert stubs).

## Phase 4: User Story 2 - Save a suggestion (P1)

**Goal**: the heart persists a saved outfit durably; a second tap toggles it off without
deleting; ownership is enforced; the card body navigates toward `/outfits/:id`.

**Independent Test**: tap a heart, confirm a row exists via a direct DB read with all fields
populated: tap again, confirm the row survives with `favorite = false`; confirm a second user
can never reach the first user's row.

- [ ] T018 [US2] In `OutfitCard.tsx`: wire the heart `IconButton` (existing `heart`/`heartFilled`
      keywords, verified already present in `IconButton.tsx`) to filled/outline based on `saved`
      (derived from `outfit.id != null` in the parent, per data-model.md's `savedIds` state).
      Their default `aria-label`s ("Save"/"Unsave") are already used elsewhere for the wardrobe-
      item favorite heart — pass an explicit `label="Save outfit"`/`"Unsave outfit"` override
      here so this control reads correctly in context, per design-system.md's Outfit-detail heart
      wording.
- [ ] T019 [US2] In `SuggestionPager.tsx` (or a thin parent wiring the API calls — decide at
      implement time whether the API call lives in `SuggestionPager` or is threaded down as a
      prop from `RecommendChat.tsx`, matching how the rest of the screen already centralizes
      network calls): on first heart tap, `POST /api/v1/recommend/outfits` with the card's own
      `occasion`/`meta_line`/`rationale_text`/`match_label`/`item_ids` (already in hand from the
      response — no re-fetch); on subsequent taps, `POST /api/v1/recommend/outfits/{id}/favorite`.
      Update local `savedIds`/heart-fill state from the response, not by assuming success before
      the call resolves.
- [ ] T020 [P] [US2] `frontend/components/recommend/SuggestionPager.test.tsx` (extend): first
      heart tap calls the save endpoint with the right body and updates fill state from the
      response id; second tap calls the favorite-toggle endpoint with that id.
- [ ] T021 [US2] Wire `OutfitCard`'s card-body tap (outside heart/thumbnails/feedback) to
      navigate to `/outfits/{id}` once saved (Next.js `router.push`, existing pattern elsewhere
      in the app) — a 404 there is expected (010 not built) and is not a defect to chase.
- [ ] T022 [P] [US2] Confirm via `docs/handoffs/009-suggestion-pager.md` §10's own instruction:
      after implementing, manually `psql` into the local Supabase DB and read back a row created
      through the real UI flow (not just via the integration test) — record the actual row
      contents in the final report, not just that the `POST` returned `2xx`.

**Checkpoint**: saving/unsaving works end to end against a real local Postgres, independent of
Phase 3-6.

## Phase 5: User Story 3 - Feedback is not persisted (P2)

**Goal**: thumbs-up/down are mutually exclusive, toggle off, and touch no network call.

**Independent Test**: tap thumbs, confirm mutual exclusivity and toggle-off; confirm zero
network requests fire from any of it; confirm no state survives a reload.

- [ ] T023 [P] [US3] In `OutfitCard.tsx`: implement the feedback footer —
      `feedback: "up" | "down" | null` local state (lifted to `SuggestionPager` per data-model.md
      so paging away and back doesn't reset a card's own choice, keyed by card index), two
      `IconButton`s (existing `thumbsUp`/`thumbsDown` keywords, verified already present in
      `IconButton.tsx`), mutually exclusive, each toggles off on repeat tap, filled-solid styling
      per § Outfit suggestion pager item 5.
- [ ] T024 [P] [US3] `OutfitCard.test.tsx` (extend): thumbs-up then thumbs-down deselects the
      first; tapping the active thumb again clears it; **no `apiClient` call of any kind fires**
      from any feedback interaction (assert the fetch/mock spy was never called).

**Checkpoint**: feedback fully functional and provably inert over the network — independent of
every other phase.

## Phase 6: User Story 4 - Mobile vs. desktop pager mechanics (P2)

**Goal**: mobile has no native swipe at all (arrow-only); tablet/desktop has a native
scroll-snap track kept in sync with the arrows via a scroll listener; both respect
reduced-motion.

**Independent Test**: at a mobile viewport, confirm swiping the track does nothing; at
tablet/desktop, confirm dragging the track changes the visible card and updates the indicator.

- [ ] T025 [US4] In `SuggestionPager.module.css`: mobile-tier rules (< 768px, matching the
      existing breakpoint convention) — track `overflow: hidden`, `transform` transition gated by
      `@media (prefers-reduced-motion: no-preference)` (existing app-wide pattern — locate and
      reuse, don't reinvent); tablet/desktop-tier rules (≥ 768px) — `overflow-x: auto`,
      `scroll-snap-type: x mandatory`, cards `flex: 0 0 92%` + `scroll-snap-align: center`,
      hidden scrollbar (`scrollbar-width: none` + `::-webkit-scrollbar { display: none }`).
- [ ] T026 [US4] In `SuggestionPager.tsx`: add a `scroll` listener (rAF-debounced) active only at
      the desktop tier that recomputes `index` from `scrollLeft`/card width and keeps
      `PagerControls` in sync; arrow-button clicks at this tier call `scrollTo({ left: index *
      cardWidth, behavior })` instead of mutating the transform directly; `behavior` reads
      `prefers-reduced-motion` ("auto" when reduced, "smooth" otherwise).
- [ ] T027 [P] [US4] `SuggestionPager.test.tsx` (extend, jsdom-appropriate — mock
      `scrollTo`/`scrollLeft` as jsdom doesn't implement real scroll geometry): a simulated
      `scroll` event updates `index`; an arrow click at the "desktop" code path calls `scrollTo`
      with the expected offset; the mobile code path never calls `scrollTo` at all.
- [ ] T028 [US4] **Manual browser verification** (not automatable in jsdom): at a real/emulated
      mobile viewport confirm touch-drag does not move the track; at tablet/desktop confirm
      native drag/scroll works and stays in sync with the arrows; toggle OS/devtools
      reduced-motion and confirm no sliding/smooth-scroll animation at either tier. Record the
      result in the final report per handoff §11 (this is the item explicitly called out as
      needing real-browser checking at both widths).

**Checkpoint**: pager mechanics verified correct and genuinely different per tier, in a real
browser, both motion-preference states.

## Phase 7: User Story 5 - Empty and Error group states (P3)

**Goal**: zero surfaced outfits renders the Empty message, never an empty-looking pager; a
failed request renders the distinct Error card with retry.

**Independent Test**: force zero outfits above the floor → Empty message; force a request
failure → Error card + working retry.

- [ ] T029 [P] [US5] In `ChatMessageList.tsx` (or a small new `PagerEmptyState`/reuse of the
      existing error-card pattern in `RecommendChat.tsx`): when an assistant message has
      `outfits: []` and a non-null `reply_text`, render the Empty copy ("I couldn't put an
      outfit together from that — try loosening a constraint or adding a few more pieces.",
      linking to Add item) instead of an empty `SuggestionPager`.
- [ ] T030 [P] [US5] Create `frontend/components/recommend/PagerSkeletonCard.tsx` +
      `.module.css`: the group's own Loading treatment (pulse blocks for title/meta, a
      description-shaped bar, three 56×56 thumbnail placeholders, no arrows/indicator) shown in
      place of the pager the instant a Start-styling call begins, distinct from the existing
      "Thinking…" row.
- [ ] T031 [P] [US5] `backend/tests/integration/test_recommend_routes.py` (extend): a mocked
      pipeline result where every candidate scores below 0.4 produces `outfits: []` +
      non-null `reply_text`, never a `404`/empty-array-with-no-explanation.
- [ ] T032 [P] [US5] Frontend tests for the Empty message rendering and the existing Error-card
      retry path still working unchanged with the new response shape (`ChatMessageList.test.tsx`/
      `RecommendChat.test.tsx`, extending existing coverage rather than duplicating it).

**Checkpoint**: all five user stories independently verified; full feature demoable end to end.

## Phase 8: Polish & cross-cutting

- [ ] T033 [P] Confirm `backend/tests` count ≥ 644 and `frontend` test count ≥ 247 (handoff §9)
      after all phases; run `uv run ruff check .`, `uv run ruff format --check .`,
      `uv run mypy src`, `uv run pytest -q`, `uv run lint-imports` (backend) and `npm run lint`,
      `npx tsc --noEmit`, `npm run build` (frontend) — all clean.
- [ ] T034 [P] Confirm no diff under `backend/src/whattowear/pipeline/`, `scoring/`, or
      `retrieval/`; state this explicitly in the final report rather than silently skipping the
      eval-baseline re-run (handoff trap #1).
- [ ] T035 Full quickstart.md pass: both widths, both themes, in an actual browser at
      `localhost:3000` and `127.0.0.1:3000` (handoff §9's own double-origin check).

## Dependencies

- Phase 1 (T001) blocks Phase 2 (repository/routes need the table).
- Phase 2 (T002-T009) blocks every user-story phase — all of them depend on the changed response
  shape and/or the persistence routes.
- US1 (Phase 3) and US2 (Phase 4) are both P1 and independent of each other (US2 only needs
  `OutfitCard`'s heart slot to exist, not the pager's paging logic) — can be built in either
  order or in parallel by different people once Phase 2 lands.
- US3 (Phase 5) only needs `OutfitCard` to exist (Phase 3's T012) — independent of US2/US4.
- US4 (Phase 6) extends `SuggestionPager` from Phase 3 — depends on T014 existing, not on US2/3.
- US5 (Phase 7) depends on the Phase 2 response shape (`outfits: []` case) and reuses existing
  Error-card wiring from 008 — independent of US2/3/4.

## Parallel execution examples

- Within Phase 2: T003, T006, T007, T008 can run in parallel once T002/T004/T005 land (different
  files, no shared state).
- Within Phase 3: T010/T011 (PagerControls) and T012/T013 (OutfitCard) are parallel tracks before
  T014 (SuggestionPager) needs both.
- Phase 4 (US2) and Phase 5 (US3) can proceed in parallel once Phase 3's T012 (OutfitCard) exists,
  since they touch different slices of the same file — coordinate on that file rather than
  parallelizing literal edits to it.

## Implementation strategy

**MVP** = Phase 1 + Phase 2 + Phase 3 (US1): the pager renders and pages correctly. Ship-worthy
on its own only in the sense of being independently testable — the handoff's actual Definition of
Done requires persistence (US2) too, since the heart and tap-through are named as required on
every card, not an optional enhancement. Recommended real build order: Phase 1 → 2 → 3 → 4 (US1
then US2, both P1) → 5 → 6 → 7 → 8.
