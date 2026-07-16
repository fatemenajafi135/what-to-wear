# Quickstart: MVP App

Validates all four P1 user stories end-to-end, plus the public-deployment
success criteria. Run the backend steps from `backend/`, frontend steps from
`frontend/`.

## Prerequisites

- Backend `.env` filled per `backend/.env.example`, plus a new
  `WTW_CORS_ORIGINS` (e.g. `http://localhost:3000` for local dev).
- A Supabase project (already provisioned in Feature 001) with:
  - A new Storage bucket named `wardrobe-photos` (one-time, Supabase
    dashboard) with an RLS policy restricting each authenticated user to
    read/write only their own `{user_id}/...` folder path.
  - Email/password auth enabled (default).
- Migration applied: `uv run alembic upgrade head` (picks up
  `0002_add_pattern_fit.py`).
- Frontend `.env.local`: `NEXT_PUBLIC_SUPABASE_URL`,
  `NEXT_PUBLIC_SUPABASE_ANON_KEY`, `NEXT_PUBLIC_API_BASE_URL=http://localhost:8000`.

## Setup

```bash
# backend
cd backend
uv sync --group dev
uv run alembic upgrade head
uv run python -m whattowear.crud seed-catalog
uv run uvicorn whattowear.api:app --reload

# frontend (separate terminal)
cd frontend
npm install
npm run gen:types   # regenerates lib/api-types.ts from the running backend's /openapi.json
npm run dev
```

## Validation: US1 — Sign in to a private account

1. Open `http://localhost:3000`. Not signed in → redirected to `/sign-in`.
2. Create an account (email/password). **Expect**: redirected to a screen
   that's the signed-in user's own (e.g. closet or home).
3. Reload the page. **Expect**: still signed in, no credential re-entry
   (FR-002).
4. Sign out, sign back in with the same credentials. **Expect**: same
   account, same (empty, at this point) closet.

## Validation: US2 — Add an item to my closet from a photo

1. From the signed-in app, go to "Add item," submit a clear photo of a single
   garment.
2. **Expect**: a pre-filled draft — category, colors, fabric, warmth,
   formality, season, pattern, fit — not yet saved (contract:
   `wardrobe-items-extract.md`).
3. Change at least one field, save.
4. **Expect**: item appears in the closet view with the corrected value, not
   the originally extracted one (contract: `wardrobe-items-upload.md`).
5. Submit a blurry/no-garment photo. **Expect**: a clear "couldn't process
   that photo" state, not a crash or silent empty item — user can retry or
   fill in fields manually and still save.

## Validation: US3 — View my closet

1. With items from US2 plus any catalog-seeded items, open the closet view.
2. **Expect**: every owned item appears with category, colors, and other
   attributes visible.
3. Sign in as a second, different account. **Expect**: empty state (or that
   account's own items only) — never the first account's items.

## Validation: US4 — Get an outfit suggestion

1. In the suggestion screen, type a free-text request (e.g. "something for a
   casual dinner tonight").
2. **Expect**: an outfit built only from items owned by the signed-in user,
   with a written rationale (calls the existing `/recommend`, JWT-gated,
   unchanged).
3. Repeat with a closet too sparse to dress the occasion. **Expect**: a clear
   "closet doesn't have enough" explanation, not an error or a fabricated
   outfit.

## Validation: responsive (SC-004)

Resize the browser to a phone-width viewport (e.g. 375px) and to a
laptop-width viewport (e.g. 1440px). **Expect**: all four flows above remain
fully usable at both sizes.

## Validation: public deployment (SC-005)

1. Deploy backend to Railway (start command:
   `uv run uvicorn whattowear.api:app --host 0.0.0.0 --port $PORT`; env vars
   set in the Railway dashboard, including `WTW_CORS_ORIGINS` set to the
   Vercel origin).
2. Deploy frontend to Vercel (env vars in the Vercel dashboard, incl.
   `NEXT_PUBLIC_API_BASE_URL` pointed at the Railway URL).
3. From a browser that has never touched the local dev environment, repeat
   US1–US4 against the public URLs. **Expect**: fully usable, same as local.

## Validation: Quality Bar (vision golden set)

```bash
cd backend
uv run python -m whattowear.eval.vision_harness
```

**Expect**: each `vision_cases:` entry in `data/golden_set.yaml` reports
pass/fail against its loose expected properties (category match,
formality-in-set, warmth-in-range). This is a separate, lightweight check —
it does not run or affect the existing `eval/harness.py` no-regression gate,
which is unaffected by this feature (no retrieval/generation code changed).
