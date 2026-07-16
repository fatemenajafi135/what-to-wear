# Quickstart: Wardrobe Item Photos

## Prerequisites

- `backend/.env` filled in as usual (no new env vars this feature).
- `uv run alembic upgrade head` (picks up the new `photo_path` migration).
- The Feature 003/005 `wardrobe-photos` Storage bucket + RLS policies must
  already exist — this feature reads from them, doesn't create them. If
  `specs/003-mvp-app/quickstart.md`'s Prerequisites haven't been done in
  this environment, do those first.
- Frontend: `frontend/.env.local` as usual (no new vars) — the existing
  `NEXT_PUBLIC_SUPABASE_URL`/`NEXT_PUBLIC_SUPABASE_ANON_KEY` are what the
  signed-URL call uses.

## Validation: US1 — see a real photo, or the swatch fallback (SC-001, SC-002, SC-003)

1. **Backend round-trip** (SC-001's data half): `POST
   /wardrobe/items/extract` a photo, then `POST /wardrobe/items/upload`
   with the returned `photo_path`. `GET /wardrobe/items` afterward — the
   new item's `photo_path` field is present and non-null. Add a second
   item via `POST /wardrobe/items` (catalog path) — its `photo_path` is
   `null`.
2. **Frontend rendering** (SC-001, SC-002): open `/closet` in a browser,
   signed in as a user with at least one photo-uploaded item and at least
   one catalog item.
   - The photo-uploaded item's card shows its real photo, plus its color
     swatch(es)/hex and pattern tag — unchanged from today.
   - The catalog item's card shows only its color swatch(es), exactly as
     before this feature — no image, no broken-image icon.
   - **Owner-only check (FR-007)**: sign in as a *different* user and view
     their own `/closet`. Confirm they never see the first user's photo —
     this should already hold via the existing Feature 003/005 RLS
     policies (unchanged by this feature), but re-verify it here since
     this is the first time those policies are exercised from a
     client-side signed-URL call rather than the upload flow.
3. **Graceful degradation** (SC-003, FR-006): with a photo-uploaded item's
   card rendered once (confirming the photo shows normally), simulate a
   signed-URL failure — e.g. temporarily rename/delete the object in the
   Supabase Storage dashboard, or revoke network access to Supabase in
   devtools — and reload. Expect: the card falls back to swatch-only,
   same as a catalog item; no broken `<img>`, no error toast, no console
   crash (a caught/logged error is fine).
4. **Pre-existing items unaffected** (SC-002): any item already in the
   database before this migration ran continues to render swatch-only
   (its `photo_path` is `null` — nothing to backfill, per spec.md's Edge
   Cases).

## What's NOT covered here

No eval-harness run — this feature touches no retrieval/generation code
(constitution Principle I gate is N/A per plan.md's Constitution Check).
No new endpoint to contract-test. No LLM calls anywhere in this feature's
own logic, so no AI-cost tradeoff applies to its own tests either.
