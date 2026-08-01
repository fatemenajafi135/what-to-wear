# Research — Feature 008: Styling chat

Four decisions were named by the handoff as deliberately not pre-decided: item resolution,
thread identity, request/latency shape, and the checkpointer's self-created tables. Each is
recorded below with every option actually considered — not just the one picked — per the
handoff's explicit warning that an incomplete option list, not weak reasoning, was feature 001's
real defect.

## 1. Item resolution — how `ScoredOutfit.items` (wardrobe item IDs) become renderable items

**Context**: `ScoredOutfit.items` (`backend/src/whattowear/schema.py:352`) is `list[str]` —
wardrobe item IDs only. The reply needs 56×56 thumbnails with `photo_url`s and deep links to
`/closet/:itemId` (design-system.md § Badge, § Screen anatomy → Recommend item 3).

**Options considered**:

| Option | Description | Rejected because |
|---|---|---|
| A. Resolve server-side (chosen) | The styling route already holds a `SupabaseClosetRepository` scoped to the caller and the caller's access token (for signing); after the graph returns, resolve each outfit item id against `repository.list_wardrobe_items(user_id)` (already fetched once for the readiness gate, no second query) and reuse `ClosetItemView.from_wardrobe_item` + `storage.create_signed_urls` — the exact pattern `closet.py`'s `GET /closet/items` already uses for a page of items (`api/v1/routes/closet.py:174-181`). | — |
| B. Client fetches each item via `GET /closet/items/{id}` | No backend change beyond returning bare ids. | N sequential round trips stacked *after* an already multi-second pipeline call — directly the "works but takes a fortune" experience the handoff calls out. Also re-runs an ownership check per item that the styling route has already effectively done by construction (items only ever come from that user's own wardrobe query). |
| C. New batch "get items by ids" endpoint | Client sends the id list once, gets items back in one round trip. | Solves B's round-trip problem but not its added-latency-after-the-fact problem, and duplicates logic the styling route can do inline with data it already has in hand in the same request — a second endpoint with no independent reason to exist (Quality Bar: "an interface, port, or layer is introduced only when... a measured problem it solves"). |

**Decision**: A. The styling response embeds fully resolved items (`ClosetItemView`-shaped: id,
name, category, `photo_url`, etc.) per outfit, signed with one batched `storage.
create_signed_urls` call per response, mirroring `closet.py`'s existing pattern exactly. This
does widen the response contract beyond the pipeline's own `SuggestResult`, which is expected —
`SuggestResult` is a pipeline-internal shape; the route's own response model is free to extend
it, the same way `ClosetItemView` already extends `WardrobeItem` for its own route.

## 2. Thread identity — where `thread_id` comes from and who owns its lifetime

**Context**: `memory/store.py`'s checkpointer keys all refinement state on `thread_id`
(`config={"configurable": {"thread_id": ...}}`). `pipeline/graph.py`'s own `parse_request`
already mints a `uuid.uuid4()` when the input state has none (graph.py:136, 193). Design system:
"New chat archives the current thread... resets the thread to the greeting state"; 011 (chat
history) is explicitly built "on top of whatever you choose" here.

**Options considered**:

| Option | Description | Rejected because |
|---|---|---|
| A. Client-generated UUID | Client mints a UUID (`crypto.randomUUID()`) the moment the hero state's first message is sent, holds it for the conversation. | Duplicates identity-minting logic the pipeline already owns (`parse_request`'s own `uuid.uuid4()` fallback) in a second place, inviting drift; gives a client the ability to pick an arbitrary id (including guessing another conversation's id) with zero added benefit over letting the server mint it. |
| B. Server-generated, client-held for the session (chosen) | The route never requires `thread_id` on a first send. The pipeline's existing fallback mints one; the route echoes it back in the response. The client holds it in React component state for as long as the Recommend screen stays mounted with an active conversation, and sends it back on every subsequent message in that conversation. "New chat" simply drops the held value client-side — the next send has no `thread_id`, so the pipeline mints a fresh one. | — |
| C. One persistent thread per user, forever | `thread_id` derived deterministically from `user_id` (e.g. `user_id` itself), no separate identity per conversation. | Directly conflicts with "New chat" needing to start a genuinely distinct thread, and with 011 needing multiple, independently listable past conversations per user — a single eternal thread cannot support either. |

**Decision**: B. `thread_id` is owned by the server (the pipeline's existing fallback, unmodified
— Principle I forbids touching this), the client is a transparent holder that never invents an
id and never persists one beyond the mounted conversation (no `localStorage`/`sessionStorage` in
this slice). Consequences, stated explicitly since 011 depends on them:

- A full page reload starts a **new** visible conversation client-side (the held `thread_id` is
  gone), even though the old thread's checkpointed state may still exist in Postgres. This is an
  accepted, documented gap — 011's "Session detail → Continue" flow is exactly what closes it,
  by persisting session metadata (including its `thread_id`) somewhere durable and handing it
  back to Recommend on "Continue." Building that persistence now would be building 011 early,
  which the handoff places out of scope.
- Nothing in this slice enforces that a `thread_id` a client sends actually belongs to the
  caller — `PostgresSaver` keys purely on `thread_id`, not on `user_id`. This is a bounded risk:
  every per-turn wardrobe read still goes through `repository.list_wardrobe_items(user_id)` using
  the *caller's own* verified JWT `sub`, never a value read out of thread state, so a guessed
  `thread_id` cannot leak another user's wardrobe data — worst case is a confusing shared
  refinement history, not a data leak. Left unaddressed here rather than adding an ownership
  table, which would be new schema for a risk with no path to actual data exposure; worth
  revisiting if 011 needs stronger thread/session ownership guarantees anyway.
- "New chat" does **not** call any archival/history endpoint in this slice — the design system's
  copy about archiving into Chat history describes 011's eventual behavior; 008 only needs "New
  chat" to behave sensibly (reset to hero state, disabled on an empty thread per FR-011), which it
  does without 011 existing yet.

## 3. Request shape and latency

**Context**: the pipeline does retrieval plus at least one LLM call and is synchronous, measured
in seconds. The user, when asked directly, chose "no fixed, user-facing wait cap, but a generous
backstop timeout so a stuck request can't hang forever" (spec.md Clarifications) — overriding the
handoff's own suggestion to "set a real timeout" in the tighter, UX-driven sense.

**Options considered**:

| Option | Description | Rejected because |
|---|---|---|
| A. Plain synchronous request/response (chosen) | One `POST`, the route `await`s `get_compiled_graph(repo).invoke(...)`, returns the resolved result in a single JSON body — the same shape every other route in this codebase already uses (`closet.py`, `calendar.py`), consumed with the existing `openapi-fetch` client. A generous backstop timeout (120s) is enforced at the request layer (server-side `asyncio.wait_for` around the invoke call, mirrored by the frontend fetch's `AbortController`), independent of any UX-facing spinner logic. | — |
| B. Streaming (SSE/chunked) | Stream partial tokens/progress as the pipeline runs, for better perceived latency. | The pipeline's only real entry point is `graph.invoke()` (every existing caller, including the eval harness, uses it) — switching to `.stream()` is new, unevaluated invocation behavior, and Principle I forbids a second/altered call path without an eval re-run. Worse, the generation node's own LLM call is a single structured-output call, not incremental token generation, so there is nothing to stream mid-call beyond coarse node-boundary events — not worth the added surface for the perceived-latency win, especially once the user explicitly opted out of a tight wait-time concern. |
| C. Async job + client polling (202 + poll) | Kick off the pipeline as a background job, return a job id, client polls until ready. | No job-queue/worker concept exists anywhere else in this codebase; introducing one is exactly the abstraction the Quality Bar's "simplicity over abstraction" rule forbids without a measured problem it solves — and the measured problem (a long blocking HTTP wait) is precisely what the user said they don't need solved. Single-digit-to-double-digit-second requests don't need job semantics built for minutes-long work. |

**Decision**: A. Plain request/response, with the client showing a persistent "Thinking…"
in-progress row for the full duration (no premature timeout, no countdown), and a 120-second
backstop `asyncio.wait_for` server-side so a genuinely stuck request still surfaces the existing
`recommend.error.body`/retry state instead of hanging forever. The composer is disabled for the
whole in-flight duration (design-system.md "Chat input behavior" — intended, not observed,
behavior) so this can never produce a double-send.

## 4. The checkpointer's self-created tables

**Context**: `memory/store.py::get_checkpointer` builds a `PostgresSaver` and calls `.setup()`
itself on first use, which creates `checkpoints*` tables outside `infra/supabase/migrations/`.
Those tables do not exist in a fresh database until the first real graph invocation.

**Options considered**:

| Option | Description | Rejected because |
|---|---|---|
| A. Accept, documented (chosen) | Leave `.setup()` as the bootstrap mechanism; make it run once, deterministically, at backend process startup rather than lazily on the first request. | — |
| B. Add migration `0007` hand-authoring the checkpoint tables | Pin `checkpoints`/`checkpoint_writes`/etc. as a tracked Supabase migration, matching every other table's story. | `PostgresSaver`'s schema is LangGraph's internal implementation detail, not part of this project's owned domain model — hand-copying it into a migration forks a third-party library's schema that can silently drift the moment LangGraph changes it internally, without the migration file changing at all. That is exactly the "two sources of truth" failure the constitution's Alembic-vs-Supabase rationale already warns about, just aimed at library internals instead of a second migration tool. `.setup()` is documented as idempotent and safe to call on every boot — that's its designed usage contract, not a workaround. |
| C. Do nothing (fully lazy, no startup hook) | Leave `.setup()` to run on whatever request happens to invoke the graph first. | Two real costs: (1) the very first real user request pays the one-time DDL cost in addition to the pipeline's own latency, with no way to tell the two apart from a "why is this one request slow" report; (2) under any concurrent-worker test setup, multiple processes could race `.setup()` against the same database. Neither is severe, but both are avoidable for the cost of one line at startup. |

**Decision**: A. `main.py`'s existing `lifespan` context manager already eagerly constructs the DB
engine at process startup rather than at first request ("still lazy relative to import time, just
not lazy relative to app-run time" — `main.py:56-60`'s own comment). This feature adds one more
line to that same `lifespan` function: warm `pipeline.graph.get_compiled_graph(SupabaseClosetRepository())`
once at startup, which — as a side effect of `build_graph(repo).compile(checkpointer=memory.
get_checkpointer())` — runs `PostgresSaver.setup()` deterministically before any request is
served, using the exact same pattern already established for the database engine. No migration
is added. This is recorded in `docs/design-decisions.md` §24 so the invisibility concern the
handoff raises is addressed by documentation and a startup-time guarantee, not by silence.

## 5. How a chat message maps onto the pipeline's existing request contract

Not one of the four named decisions, but resolved here since it shapes the contract: `pipeline/
graph.py`'s `parse_request` already treats `occasion` as free text on both a fresh thread (a new
ask) and a continuing thread (a refinement utterance parsed by `_parse_refinement_intent`,
graph.py:195). The single-line chat composer's text therefore maps directly onto `SuggestRequest.
occasion` on every send — no client-side parsing into separate mood/formality/temperature fields
is needed; the pipeline already derives those from free text before `ctx` is built (graph.py:307).
The route accepts a small, route-local `{ message: str, thread_id: str | None }` body (matching
every other route's pattern of a route-local request model rather than reusing a pipeline-internal
name like "occasion" at the API boundary) and constructs `SuggestRequest(occasion=message,
thread_id=thread_id)` before invoking the graph.

## 6. Empty-outfit and error copy

`pipeline/graph.py`'s `explain` node already returns a `note` string for the "zero outfits"
case ("Your closet doesn't have enough items to assemble an outfit for this request.") and for
the "refinement narrowed to nothing" case (falls back to the prior result with an explanatory
note) — both already evaluated, unmodified pipeline output. The route surfaces `note` verbatim as
the assistant's plain-text reply when `result.outfits` is empty, rather than inventing new
copy — satisfying FR-003's honesty requirement with existing, tested pipeline behavior. A request
that fails outright (raises, or exceeds the 120s backstop) gets `recommend.error.body`/
`recommend.error.cta` (design-system.md § Recommend) with a retry that resends the same last
message.

## 7. Composer send vs. "Start styling" — what actually calls the backend

Not one of the four named decisions, but discovered while implementing the chat surface:
design-system.md's Recommend anatomy lists two distinct controls — the pinned composer's own
28px send button (item 6) and a separate full-width "Start styling" button that appears once the
user has sent a message, captioned "Uses everything you have told me so far" (item 5) — without
stating what each one does against a real backend.

**Options considered**:

| Option | Description | Rejected because |
|---|---|---|
| A. Composer send is local-only; "Start styling" is the sole trigger (chosen) | The composer appends to the on-screen transcript with no network call. "Start styling" sends everything typed since the last tap as `message`, with the held `thread_id` carrying continuity so a later tap reads as a refinement to the pipeline's own (unmodified) refinement parsing. | — |
| B. Every composer send calls the pipeline immediately, "Start styling" dropped | Simplest possible mapping — one send, one real reply, matching my initial (incorrect) assumption before reading the reference prototype's actual interaction code. | Directly contradicts design-system.md's explicit anatomy item 5 and its verbatim-required copy ("Copy is the real prototype microcopy — ship it verbatim," §9) — the button and caption are specified, not optional. Also reruns a full retrieval+LLM call on every single message with the user given no control over when the expensive, multi-second call fires — worse on exactly the latency/cost axis the handoff itself flags as a concern. |
| C. Composer send calls a real, trivial backend endpoint for a canned acknowledgement | Keeps a "real round trip" discipline for every user action. | The acknowledged text is ephemeral, discarded, and has no reason to be server-authoritative — adds a network round trip and a new endpoint for zero product value. Quality Bar's simplicity rule: no interface without a measured problem it solves. |

**Decision**: A. Confirmed against `design/prototype/What to Wear.dc.html:1834-1861` (reference
only, not ported): `sendMessage()` only ever appends to local state and returns a canned,
non-AI acknowledgement; `startStyling()` is the one path that joins the accumulated user text and
runs generation. The real implementation keeps that shape but drops the prototype's
keyword-sniffed canned acknowledgement text (not present in design-system.md's own copy tables,
§6 — inventing it would violate Principle VIII in the other direction, adding unspecified visual
copy rather than omitting specified copy) and its fake `setTimeout` latency. "Start styling" is
visible once the conversation has ≥1 user message and disabled specifically when nothing is
pending since the last tap, to prevent a no-op duplicate call. Full record: design-decisions.md
§28.
