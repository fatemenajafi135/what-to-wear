# Research: Production Hardening

## 1. LLM routing layer (FR-008/009/010)

**Decision**: Swap `config.py`'s model factories (`get_chat_model`,
`get_judge_model`, `get_embeddings`) from constructing `langchain_openai`
classes (`ChatOpenAI`, `OpenAIEmbeddings`) to constructing their
`langchain-litellm` equivalents (`ChatLiteLLM`, and litellm's embedding path
via `langchain_litellm`'s embedding wrapper or a thin direct
`litellm.embedding()` call — see note below), still pointed at the existing
Vercel AI Gateway (`GATEWAY_BASE_URL`) as an OpenAI-compatible `api_base`.
Every call site (`vision.py`, `pipeline/generator.py`, `external/trends.py`,
`eval/judge.py`) keeps calling `get_chat_model(...).with_structured_output(X)`
/ `.invoke(...)` completely unchanged — they consume a LangChain
`BaseChatModel`, and `ChatLiteLLM` implements that same interface. This is
the "one explicit config layer" the module's own docstring already commits
to; only what's inside the factory functions changes.

**Rationale**: FR-008 requires one consistent code path for every provider
call, not multiple ad hoc call sites — `config.py` already *is* that one
path (a real, pre-existing constraint, not new to this feature); routing all
calls through `litellm.completion()`/`litellm.acompletion()` under the hood
gets automatic retry (FR-009: `num_retries` / `RetryPolicy`, tenacity-backed)
and per-call cost/usage tracking for free, without rewriting five call
sites' invocation code.

**Alternatives considered**:
- *Standalone LiteLLM proxy service*: rejected outright per this feature's
  own framing ("LiteLLM as an in-process SDK... not a standalone proxy
  service") and the constitution's simplicity clause — a second network hop
  and a second deployable for a solo project with one backend service.
- *Hand-rolled retry wrapper around the existing `ChatOpenAI` calls*: works,
  but duplicates what `litellm` already does correctly (distinguishing
  `RateLimitError`/`Timeout`/`InternalServerError` — retry — from
  `BadRequestError`/`AuthenticationError` — don't), and doesn't give
  LangSmith-visible cost/usage the way routing the actual provider call
  through litellm does.

**Risk flagged for implementation**: a known upstream issue
(`langchain-ai/langchain#28176`) reports `with_structured_output` raising a
`BadRequestError` on `tool_choice` validation for `ChatLiteLLM` + OpenAI-style
models in some versions. Mitigation, in order: (a) pin a current
`langchain-litellm` release and verify empirically against the gateway with
a smoke test (`vision.py`'s extraction call and `generator.py`'s outfit-gen
call, both already covered by existing tests/eval cases) before relying on
it; (b) if the bug reproduces, pass `method="json_mode"` to
`with_structured_output(...)` at each of the four call sites — litellm
supports JSON-mode structured output uniformly across OpenAI-style models,
and every model this project targets is OpenAI-style via the gateway. This
is a one-line-per-call-site change, not a redesign, so it doesn't need to be
decided now — a task in tasks.md verifies this and applies the fallback only
if needed.

**Embeddings**: `langchain-litellm` does not (as of research) ship a
dedicated embeddings class; `get_embeddings()` keeps using
`langchain_openai.OpenAIEmbeddings` pointed at the same gateway URL — FR-008
says "all calls to AI model providers," and the spec's own scope is
retries/visibility for the styling pipeline's LLM calls (generation,
extraction, judge, trend lookup), not the embedding calls that already work
today and aren't in this feature's problem statement (no reported issue with
embedding calls). Re-litigating the embeddings path isn't required to satisfy
FR-008/009/010 for the feature's actual pain point (ad hoc chat-completion
call sites), and forcing it through litellm too would be scope creep without
a concrete problem to fix.

**Cost/usage visibility (FR-010)**: per this session's clarification, the
constitution's existing mandatory LangSmith tracing (`config.py`'s
`_require_langsmith()`, already fails fast without it) satisfies this
requirement once litellm calls are traced with cost fields populated.
`langchain-litellm`'s `ChatLiteLLM` calls go through LangChain's standard
callback system, so existing LangSmith tracing picks them up the same way it
already traces `ChatOpenAI` calls today — no separate cost dashboard or
persisted "provider call record" table is built.

## 2. Reusing prior results without re-running the pipeline (FR-006/007, US3)

**Decision**: an explicit, application-level Redis cache around the whole
`/suggest` graph invocation in `api.py` — not LiteLLM's built-in Redis
*semantic* cache. The cache stores/returns a full `SuggestResult` keyed by:

```
sha256(user_id | normalized_occasion | mood | formality | temp_band | season | wardrobe_fingerprint)
```

- `normalized_occasion`/`mood`/`formality` are lower-cased/stripped — this is
  what makes two textually-different-but-equivalent requests hit the same
  key (spec's Assumptions: "match closely enough... not simply identical
  request text"), without embedding-similarity fuzziness.
- `temp_band`/`season` reuse `context_assembler`'s own existing banding
  logic (already computed today, not a new concept) rather than the raw
  `temp_c` float, so two requests a few degrees apart correctly collapse to
  one cache entry.
- `wardrobe_fingerprint` is a hash of that user's current wardrobe rows
  (`id`, `updated_at` pairs, sorted) — any add/edit/remove changes this hash,
  so a stale entry is never returned (FR-007) as a natural consequence of the
  key changing, with no separate invalidation-on-write hook needed. A short
  TTL (e.g. 1 hour) is kept underneath as the safety net the spec's
  Assumptions explicitly allow, in case a hash collision or clock skew ever
  produces a false key match.
- Scope: **only the first turn of a conversation** (no incoming `thread_id`,
  or a `thread_id` the checkpointer has no prior state for) is eligible for
  a cache read/write. A refinement turn ("warmer", "alternatives") always
  goes through the graph — refinements are inherently stateful
  (`original_context`/`last_result`/`refinement_deltas` carried by the
  checkpointer) and aren't idempotent the way a fresh request is; caching
  them isn't required by any user story here and would risk serving a
  refinement's result to an unrelated fresh request with a coincidentally
  matching key.

**Wiring**: `api.py`'s `suggest_endpoint` already needs the user's wardrobe
before it can compute a cache key at all. `context_assembler.load_wardrobe`
is called once in the handler; on a cache hit, the graph is never invoked
(zero retrieval calls, zero LLM calls — satisfying "no new AI-provider usage
recorded" from US3's Independent Test and the sub-second SC-003 target,
since no Qdrant/KB/rerank/LLM round trip happens). On a miss, the
already-loaded wardrobe is passed into `graph.invoke(..., wardrobe=...)` —
`GraphState.wardrobe` already exists as an explicit override precisely for
this ("bypassing DB load", currently used only by `eval/test_users.py`) — so
the cache doesn't cause a second wardrobe fetch inside `gather_context`.

**Rationale for not using LiteLLM's semantic cache for this**: LiteLLM's
Redis semantic cache (`litellm.cache = Cache(type="redis-semantic", ...)`)
operates at the granularity of individual `litellm.completion()` calls,
matched by embedding-similarity over the prompt text. It cannot skip
retrieval (Qdrant hybrid search, KB queries, Cohere rerank — none of which
call `litellm.completion()`), so it structurally cannot satisfy "reuse the
prior result instead of re-running the full retrieval-and-generation
pipeline" — only the LLM-call sliver of it. It also introduces a real
correctness risk this system can't accept: a documented upstream bug
(`BerriAI/litellm#12234`, "semantic cache incorrectly matches completely
different queries to the same cache entry") is exactly the failure mode
this feature's own Assumptions section anticipated and pre-authorized a
fallback for ("unless investigation shows fuzzy-matching risk... an explicit
[mechanism] is needed instead of TTL/semantic reliance alone"). A false
cache hit here isn't a staleness inconvenience — grounding a suggestion in
the *wrong* user's closet state would violate constitution Principle IV. An
exact key over normalized, already-well-defined fields is simpler than
embedding similarity, fully deterministic (unit-testable), and — per the
per-user-scope clarification already resolved — never risks a cross-user
match by construction (the user id is literally part of the key). LiteLLM's
own retry/cost-tracking role (§1) is unaffected by this choice; the two are
independent uses of "the locked Redis backend," not competing
implementations of the same thing.

**Alternatives considered**:
- *TTL-only cache, no closet-state key component*: rejected in spec.md's own
  Assumptions already (correctness violation on a post-edit stale serve).
- *Explicit invalidation hook on wardrobe mutation (delete the cache entry
  in `crud.py`'s add/update/delete functions)*: works, but requires the
  cache layer to know about every wardrobe-mutating code path and keep that
  list in sync forever. The fingerprint-in-the-key approach gets the same
  correctness property "for free" from data that's already loaded, so this
  is unneeded extra surface area (simplicity clause).

## 3. Output grounding guardrail (FR-003/004/005, US2)

**Decision**: a new pure function in a new small module,
`pipeline/grounding.py` — `verify_outfit_grounding(item_ids, wardrobe_by_id,
catalog_ids)  -> bool` — plus a new graph node, `verify_grounding`, inserted
between `score_and_rank` and `explain` in `pipeline/graph.py`. It filters
`scored_outfits` down to only those whose every `item_id` exists in
`ctx.wardrobe` (already loaded, already in `GraphState`) or the shared
catalog (`crud.list_catalog_items`, one cheap query against a small, shared
table), dropping any that don't (FR-004). `explain`'s existing "fewer than 3
outfits" / "no outfits at all" note logic (already handles the generation
step legitimately producing fewer than 3-5 outfits) applies unchanged to
whatever count of outfits survives verification — no new "no suggestion
available" path needs to be built (FR-005 is already covered by the
existing `explain` fallback).

**Why check the catalog too, even though no outfit can contain a
catalog-only item today**: Feature 002 Phase 3 made an explicit, documented
decision that catalog substitution is out of scope *for outfit generation*
— an unfillable slot omits the outfit, the closet is the only source
`generate_outfits` draws from. That's a decision about *what generation is
allowed to do*, not a reason to narrow *what the grounding check is allowed
to accept* — the constitution's own Principle IV and this feature's Key
Entities both define grounding as "closet or catalog," and satisfying that
literally costs one extra cheap query, not a new abstraction or a repository
pattern (the simplicity clause is about not building unneeded interfaces,
not about skipping a one-line defensive check that's already dirt cheap).
`/speckit.analyze` flagged the closet-only version as a literal-compliance
gap against Principle IV; this revision closes it.

**How this is "a bug catcher, not a gate that can plausibly fire on real
behavior"**: `generate_outfits` already only builds outfits out of
`ctx.wardrobe` and `_is_slot_complete` already only reasons over
`wardrobe_by_id`. The guardrail is the safety net the constitution demands
should the LLM step ever hallucinate an item id not in the pruned candidate
set it was shown, or a future change to `generate_outfits` regress that
guarantee — exercised in tests by directly constructing a `GraphState` with
a bad id injected into `scored_outfits`, matching the spec's own Independent
Test for US2 ("deliberately make one outfit's item list reference a
nonexistent item id").

**Alternatives considered**:
- *Closet-only check (no catalog query)*: was the original decision here;
  rejected on analyze review as an unnecessary literal-compliance gap
  against Principle IV for negligible savings (one small, shared-table
  query per suggestion).
- *Checking in `api.py` after `graph.invoke` returns, instead of a graph
  node*: works too, and is simpler in one sense (no new node/edge), but
  moves a deterministic, constitution-mandated check out of the graph that
  already owns "everything after generation" (`score_and_rank`/`explain`),
  splitting the pipeline's authoritative structure across two files for no
  benefit. Keeping it as a node also means `eval/harness.py` (which invokes
  the compiled graph directly, not `api.py`) exercises the same guardrail
  the live endpoint does — required by constitution Principle I (no forked
  pipeline path between the API and the eval harness).

## 3a. Health check reports dependency failures (FR-012)

**Decision**: `GET /health` (`api.py`) currently returns a static `{"status":
"ok"}` unconditionally — it cannot today surface the spec's own Edge Case
("backend can't reach the database or vector store... surfaced as a clear
health-check failure, not a silent partial outage"). `/speckit.analyze`
flagged this as a coverage gap (no FR, no task) against an Edge Case that
was already in the approved spec. Fix: `/health` does a cheap reachability
check against Postgres (reuse `memory.store._reachable`'s pattern — a
short-timeout connect, not a real query) and Qdrant (`kb.get_kb()`'s client,
a lightweight collection-info call), returning `503` with which dependency
failed if either is unreachable, `200 {"status": "ok"}` otherwise.

**Rationale**: this is exactly what "reachable/deployed on Railway" needs to
be operationally meaningful (US1) — a process that's up but can't reach its
DB is not actually serving anything, and Railway's own health-check-based
restart behavior needs an honest signal to act on.

## 4. Deploy (US1) — carried over from Feature 003, not re-planned

**Decision**: reuse `specs/003-mvp-app/quickstart.md`'s already-documented
Railway start command, env vars, and Supabase Storage bucket/RLS steps
verbatim — this feature performs those three still-outstanding manual steps
(or confirms they're already done), it doesn't redesign the deployment
approach. See this feature's `quickstart.md` for the consolidated
walk-through (a pointer, not a duplicate).

**Status check needed before any live-URL-dependent implementation task**:
whether the Supabase Storage bucket, Railway project, and Vercel project
already exist is unknown to this session — these are owner-only dashboard
steps per Feature 003's own handoff notes. `tasks.md` marks the
deploy-dependent tasks accordingly; the code-only groundwork (§1-3 above)
has no dependency on them and proceeds regardless.

## 5. New dependencies

- `litellm` (direct SDK) + `langchain-litellm` (the `ChatLiteLLM` LangChain
  adapter) — add to `backend/pyproject.toml`.
- `redis` (the standard `redis-py` client, sync) — add to
  `backend/pyproject.toml`. No new abstraction over it; `pipeline/cache.py`
  calls `redis.Redis.from_url(...)` directly, matching the "no repository
  pattern for one backend" simplicity guidance.
- New env vars (added to `backend/.env.example`): `REDIS_URL` (Railway's
  Redis addon connection string; falls back to a local `redis://localhost:
  6379/0` for dev, and the cache degrades to "always miss, process fresh"
  per the spec's own Edge Cases if Redis is unreachable — never raises).
