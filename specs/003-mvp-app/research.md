# Phase 0 Research: MVP App

All items below were resolvable from the existing codebase, the locked stack
(constitution Technology Constraints), and the SDD-HANDOFF Step 4 prompt — no
`NEEDS CLARIFICATION` markers remain.

## 1. Frontend scaffolding

- **Decision**: Next.js 15, App Router, TypeScript, npm (not pnpm/yarn — no
  existing convention in this repo to match, npm is the zero-extra-install
  default).
- **Rationale**: Locked stack (constitution: "Frontend is Next.js on Vercel").
  App Router is the current Next.js default and matches Vercel's zero-config
  deploy path.
- **Alternatives considered**: Vite + React (rejected — constitution locks
  Next.js specifically, likely for Vercel's first-class deploy integration).

## 2. Auth

- **Decision**: `@supabase/supabase-js` client-side, email/password
  sign-up/sign-in, default localStorage session persistence. No backend auth
  code changes — the existing `get_current_user_id` JWT dependency
  (ES256/JWKS) already verifies whatever Supabase issues.
- **Rationale**: SDD-HANDOFF Step 4 prompt states this explicitly. Supabase
  Auth JS's default session persistence directly satisfies FR-002 ("keep a
  signed-in session valid across normal app use") with zero custom code.
- **Alternatives considered**: NextAuth/Auth.js with a Supabase adapter
  (rejected — adds an abstraction layer for a single auth provider that's
  already the locked stack; violates simplicity-over-abstraction with no
  second provider to justify it).

## 3. Contract types (constitution Principle VII)

- **Decision**: `openapi-typescript` (dev dependency) generates
  `frontend/lib/api-types.ts` from a checked-in `frontend/openapi.json`
  snapshot (fetched from the backend's own `/openapi.json`, which FastAPI
  already serves for free). Regenerated via a manual `npm run gen:types`
  script whenever the backend contract changes. A single hand-written
  `apiFetch<T>()` wrapper in `lib/api-client.ts` attaches the Supabase JWT and
  applies the generated types — no generated client class.
- **Rationale**: Satisfies "frontend consumes generated types from OpenAPI, no
  hand-maintained duplicate types" with the smallest possible surface — types
  only, not a full generated SDK (that would be an abstraction with no second
  implementation to justify it, per the Quality Bar).
- **Alternatives considered**: `orval` / `openapi-generator` full client
  codegen (rejected — heavier, generates request functions + often a
  react-query layer neither needed nor asked for this feature).

## 4. Vision extraction call

- **Decision**: New `vision.py` module reuses `config.get_chat_model()`
  (same one gateway-config layer everything else uses) with
  `.with_structured_output(ExtractedAttributes)` — the identical pattern
  `pipeline/generator.py` already uses for `GenOutput`. The image is passed as
  a multimodal human message (base64 data URL content part), a
  LangChain/ChatOpenAI-supported input shape. Model selection: reuse
  `CHAT_MODEL` (`config.CHAT_MODEL`, default `openai/gpt-5.4-mini`, which is
  multimodal) with an optional `WTW_VISION_MODEL` env override for a
  dedicated vision-tier model later, without new required config today.
- **Rationale**: Reuses the exact structured-output pattern already validated
  in `generator.py` rather than inventing a second way to call the LLM
  (Principle I in spirit — one gateway config layer, one calling convention).
- **Alternatives considered**: A dedicated vision provider SDK (rejected — the
  constitution requires every model call go through the one gateway config
  layer, no direct provider SDK calls).

## 5. Photo storage

- **Decision**: New `storage.py` uploads directly to Supabase Storage
  (bucket `wardrobe-photos`, one-time manual bucket creation — see
  quickstart.md) using **the caller's own verified bearer token** (already
  available from `get_current_user_id`'s dependency chain), not a service-role
  key. Object path: `{user_id}/{uuid4}-{original_filename}`. A per-user-folder
  Storage RLS policy (manual one-time Supabase dashboard config, same
  precedent as Feature 001's manual project setup) restricts each user to
  their own folder.
- **Rationale**: No new backend secret to manage; keeps the "backend holds
  only what it needs" posture from Feature 001's auth design (public JWKS key
  only, no service key). Passing the user's own token through to Storage
  means Postgres-level RLS on `storage.objects` — not application code —
  enforces per-user isolation, consistent with FR-007's "never see another
  user's data."
- **Alternatives considered**: Service-role key in the backend (rejected —
  introduces a new high-privilege secret purely to avoid one dashboard
  policy click; also a wider blast radius than the JWKS-only posture Feature
  001 deliberately chose).

## 6. Quality Bar: golden set for the new LLM-dependent path

- **Decision**: A new `vision_cases:` top-level section in
  `data/golden_set.yaml` (sits alongside, doesn't touch, the existing
  `cases:` list the harness already loads), each entry pointing at a sample
  photo under `data/fixtures/vision_samples/` with **loose** expected
  properties (category, formality-is-one-of, warmth range) — photo attribute
  extraction is inherently less exact than "does this outfit satisfy a hard
  constraint." A new, separate `eval/vision_harness.py` script checks
  extraction output against these cases. It does not modify or plug into the
  existing `eval/harness.py` no-regression gate.
- **Rationale**: Satisfies the Quality Bar ("LLM-dependent paths require an
  entry in `data/golden_set.yaml`") without rewriting or coupling to the
  existing, already-evaluated harness (Principle I) — this is a new,
  independent LLM-dependent path, not a change to the graded retrieval/
  generation pipeline the existing harness measures.
- **Alternatives considered**: Folding vision cases into the existing `cases:`
  schema (rejected — that schema is `(occasion, mood, weather) → outfit
  properties`, structurally wrong shape for `photo → attributes`; forcing it
  in would be the kind of rewrite-to-fit Principle I warns against).

## 7. CORS

- **Decision**: Add `CORSMiddleware` to `api.py`, origins from a new
  `WTW_CORS_ORIGINS` env var (comma-separated; defaults to `*` for local
  dev), set to the deployed Vercel origin in Railway's production env.
- **Rationale**: A browser frontend on a different origin (Vercel) calling
  the backend (Railway) cannot function without this — a hard technical
  prerequisite of FR-012 ("public web address"), not a scope add-on.
- **Alternatives considered**: None — this is a strict requirement once
  frontend and backend are on different domains, not a design choice.

## 8. Deployment

- **Decision**: Backend on Railway — `uv run uvicorn whattowear.api:app
  --host 0.0.0.0 --port $PORT` as the start command, env vars (all already
  in `.env.example`, plus `WTW_CORS_ORIGINS`) set in Railway's dashboard, not
  committed. Frontend on Vercel — standard Next.js zero-config deploy, env
  vars (`NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`,
  `NEXT_PUBLIC_API_BASE_URL`) set in Vercel's dashboard. Both platforms'
  default git-push-to-deploy is sufficient — no custom CI/CD pipeline for
  this feature (deferred to Feature 005).
- **Rationale**: Both platforms are already the locked stack; this is "bare
  public reachability," explicitly scoped to exclude the full 005 hardening
  (LiteLLM gateway, semantic cache, guardrails).
- **Alternatives considered**: Docker + a custom CI pipeline (rejected —
  explicitly deferred to Feature 005 per SDD-HANDOFF Step 4/5).
