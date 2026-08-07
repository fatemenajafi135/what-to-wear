# Quickstart — Feature 010: Outfits gallery + detail

Validates the feature end-to-end once implemented. See `contracts/recommend-outfits.md` for
exact request/response shapes and `data-model.md` for the schema.

## Prerequisites

```bash
cd backend && uv sync
cd frontend && npm ci
npx supabase start          # local Postgres + auth
npx supabase db reset       # applies 0001-0010 from empty — must succeed cleanly
docker compose up -d        # Qdrant, needed only so the styling assistant can produce
                             # a real, cited outfit to save — this feature doesn't query it itself
```

`backend/.env` needs a real `AI_GATEWAY_API_KEY` (or equivalent) — a saved outfit with real
citations can only come from actually running the styling assistant once. An empty
`whattowear_kb` collection produces outfits with no citations, which will look like this
feature's own bug rather than an empty-corpus artifact — verify the KB is populated first if
citations are unexpectedly always empty.

## Run

```bash
cd backend && uv run uvicorn whattowear.main:app --reload
cd frontend && npm run generate:api-types && npm run dev
```

## Validation scenarios

1. **Save an outfit with real citations** — sign in, go to `/recommend`, ask for an outfit,
   save one from the pager (heart tap). Then, directly against Postgres:
   ```sql
   select title, citations, dimension_scores, rationale_with_citations
   from outfits order by created_at desc limit 1;
   ```
   `citations` and `dimension_scores` must be non-empty arrays (not `'[]'`) whenever the pipeline
   reply that produced the saved outfit itself had citations — confirms §38's server-side capture
   actually reached the row, not just a `201`.

2. **Gallery renders it** — open `/outfits`. The just-saved outfit appears, title = its original
   occasion (§36's seeding, until renamed), match-level pill, item thumbnails (≤4, "+N" past
   4 — save/generate a 5+-item outfit to check the chip), newest-first.

3. **Detail shows the full reasoning** — tap the card. Every item renders at the large 2-col
   (mobile)/3-col (tablet/desktop) grid, no scroll/cap/chip. The description shows `[1]`/`[2]`-
   style `Badge`s inline wherever `citations` is non-empty, the numbered rule list below it, and
   the Match breakdown shows a label + one bar per dimension — confirm via browser inspector that
   no element's text content is ever a bare number or `NN%` anywhere on the page.

4. **Log as worn today, twice** — from the overflow sheet, tap "Log as worn today" twice in a
   row. Confirm exactly one row exists in `outfit_wears` for `(outfit_id, today)` and exactly one
   row per outfit item in `item_wears` for `(item_id, today)` — not two.

5. **Rename** — tap the gallery card's title, change it, tap Done. Confirm the new title shows
   on both the gallery card and (after navigating in) the detail page's `TopHeader`.

6. **Delete requires confirmation** — from the overflow sheet, tap Delete. Confirm a dialog
   appears (title `Delete {title}?`, body `This can't be undone.`) and the outfit is **not** yet
   removed. Tap Cancel — outfit still present. Reopen, tap Delete, then confirm — outfit is now
   gone from the gallery and a direct `GET /api/v1/recommend/outfits/{id}` 404s.

7. **RLS + ownership, two users** — run `pytest backend/tests/integration/test_outfits_rls.py
   backend/tests/integration/test_outfit_wears_rls.py -v`. Confirm user B cannot `SELECT`,
   `UPDATE`, or `DELETE` user A's outfit or wear rows, and cannot forge an `outfit_wears` insert
   against an outfit that isn't theirs (composite FK rejection, mirroring
   `TestItemWearsRLS::test_user_cannot_insert_a_wear_row_against_another_users_item`).

8. **Desktop two-pane** — resize to ≥1024px on `/outfits`. Confirm the gallery list narrows into
   a left pane beside a right pane reading "Select an outfit to see its details." until a card is
   clicked, at which point the detail pane fills in without a full navigation (mirrors `/closet`'s
   existing behavior).

9. **Offline disables actions** — toggle devtools offline, confirm wear/rename/favorite/delete
   controls are disabled or fail cleanly rather than appearing to succeed.

10. **Test counts and CI gates** — `uv run pytest` (backend, must be ≥ 660 passing),
    `npm test` (frontend, must be ≥ 263 passing), `ruff check`, `ruff format --check`,
    `mypy src`, `lint-imports`, `eslint`, `tsc --noEmit`, `next build` all clean.
