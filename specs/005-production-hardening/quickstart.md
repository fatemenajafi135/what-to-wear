# Quickstart: Production Hardening

## Prerequisites

- `backend/.env` filled in as usual (see `CLAUDE.md`), plus the two new vars
  this feature adds: `REDIS_URL` (Railway's Redis addon, or
  `redis://localhost:6379/0` for local dev — `docker run -d -p 6379:6379
  redis:7-alpine` works) and nothing new for LiteLLM (it reuses the existing
  `AI_GATEWAY_API_KEY`/`AI_GATEWAY_BASE_URL`).
- `uv sync --group dev` (picks up the new `litellm`, `langchain-litellm`,
  `redis` dependencies).
- The three Feature-003 manual deploy steps (Supabase Storage
  `wardrobe-photos` bucket + RLS, Railway backend + Redis addon, Vercel
  frontend) — see `specs/003-mvp-app/quickstart.md`'s Prerequisites and
  "Validation: public deployment" sections for the exact steps; this feature
  performs them if not already done, it doesn't redefine them.

## Validation: US1 — publicly reachable (SC-001)

From a machine that has never run this project locally: visit the public
Vercel URL, sign up, sign in, add one item by photo, request a suggestion.
Expect: works exactly like the local dev flow, no terminal needed. (Same
steps as `specs/003-mvp-app/quickstart.md`'s "Validation: public deployment"
— this feature is what makes that section finally executable end-to-end.)

Also (FR-012): `curl <backend-url>/health` returns `200 {"status": "ok"}`
under normal operation; temporarily pointing `DATABASE_URL`/`DATABASE_URL_DIRECT`
or `WTW_QDRANT_URL` at something unreachable and re-checking returns `503`
naming the failed dependency, instead of a false "ok".

## Validation: US2 — grounding guardrail (SC-002)

1. Unit test: call `pipeline.grounding.verify_outfit_grounding` directly with
   an item id not present in a small fixture wardrobe. Expect: `False`.
2. Integration test: construct a `GraphState` (or monkeypatch
   `generate_outfits`'s output) so one candidate outfit contains a
   non-existent item id, invoke the compiled graph. Expect: that outfit is
   absent from `result.outfits`; any other, valid outfits in the same
   response are still present; if it was the only one, the existing
   zero-outfit `note` fires instead of an error.
3. Normal-path regression: run the existing eval harness golden set — every
   case's outfits still fully verify (they always did; this just proves the
   new check doesn't reject good output).

## Validation: US3 — cache (SC-003)

1. `POST /suggest` with a fresh occasion/context for a test user with a
   non-empty closet. Note the latency and confirm a LangSmith trace was
   created for the LLM call.
2. Repeat the *same* request immediately. Expect: response in well under a
   second, byte-identical `result` (modulo it being served from cache), and
   no new LangSmith-traced LLM call for this second request.
3. Edit that user's closet (add/remove/patch one item), then repeat the same
   request a third time. Expect: full pipeline runs again (new LangSmith
   trace), not the now-stale cached result.
4. With `REDIS_URL` pointed at an unreachable host: repeat step 1. Expect:
   the request still succeeds (processed fresh), confirming the cache
   degrades gracefully rather than failing the request (spec Edge Cases).

## Validation: US4 — routing/retry/visibility (SC-004/005)

1. Point `AI_GATEWAY_BASE_URL` (or mock the transport) at something that
   returns one transient error (e.g. a 503) then succeeds — confirm
   `/suggest` still returns a normal successful result, no error surfaced to
   the caller.
2. Open the project's LangSmith dashboard after a few `/suggest` calls;
   confirm cost/usage fields are populated on the traced LLM calls — this is
   the whole of FR-010/SC-005 per this session's clarification (no new
   dashboard to check).

## Gate before merging

Re-run `uv run python -m whattowear.eval.harness` — `retrieval_recall` must
stay byte-identical to `backend/artifacts/eval_runs/`'s baseline (this
feature touches the LLM call path and adds a post-generation filter, both of
which the no-regression gate covers per constitution Principle I).
