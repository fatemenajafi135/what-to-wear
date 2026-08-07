# Research — Feature 011: Chat history

The handoff names two open decisions (§3.1, §3.2) and warns the failure mode to guard against is
an **incomplete option list**, not weak reasoning — and names §2 (the `kind` discriminator) as
an instruction that will read as over-engineering but isn't. Research below covers both named
decisions, a third gap found while reading the handoff against already-decided sections (the
same shape of gap §33/§36 each found in earlier features), and the smaller mechanical choices
the plan depends on.

## 1. What a "session" is, and what writes one

Full reasoning, every option considered: `docs/design-decisions.md` §44.

Summary: a `sessions` row is written the moment a thread's first user message reaches
`POST /recommend/messages` — not on "New chat," not on any explicit archive action. The row's
primary key **is** `thread_id` itself (no second, independently generated id — the pipeline
already mints exactly one id per logical conversation, §25). Consequence: "New chat" needs no
backend change at all; by the time a session could be archived, it already has been, continuously,
since its first message. The existing disabled-on-empty-thread guard is kept for UX reasons
(no confusing no-op reset), not because it still prevents a blank archive — under written-on-start
a blank session is never created in the first place.

Rejected: archive-on-demand (fails the handoff's own DoD — "reload and find it in Chat history"
implies no prior "New chat" tap is required) and treating the pipeline's LangGraph checkpointer
as the read model for history (opaque, not list-queryable, and the exact fragility §42 already
moved *away* from for a narrower problem).

## 2. How outfits link back to their conversation, and what a pre-existing outfit shows

Full reasoning, every option considered: `docs/design-decisions.md` §45.

Summary: `outfits` gains one nullable `thread_id uuid references sessions(id) on delete set
null`, set only for outfits `send_message` creates from this feature onward (the value is
already in scope at that call site, §42). No backfill, no heuristic guess for pre-existing rows
— they stay `thread_id IS NULL` and therefore correctly, automatically count toward zero
sessions. The outfit count shown on a Chat-history row / Session detail's "View in Outfits"
button is always a live `COUNT(*) WHERE thread_id = :session_id`, never a denormalized counter
(matching the `outfit_wears`/"most worn" precedent, §41, of computing rather than caching).

## 3. What "citation Badges" in the archived view actually renders

Full reasoning: `docs/design-decisions.md` §46. Not one of the handoff's two named decisions — a
gap found reading handoff §4.3 against §33/§35, both already decided: no live chat surface shows
citation Badges *at all* today (the pager card is plain text; the older bubble-plus-inline-`[n]`
path was removed outright once the pager shipped). "Same bubble treatment as Recommend" is read
as the visual chassis, not that removed content path. The archived assistant bubble for a
`styling_reply` turn instead renders each outfit that turn produced via that outfit's own
already-grounded `rationale_with_citations`/`citations` (§38, unaffected by this feature),
through the same citation-token-splitting helper `RationaleWithCitations.tsx` already uses for
Outfit detail — with the thumbnail grid and rule list that component also renders deliberately
left out, matching the handoff's own explicit asymmetry.

## 4. The `messages.kind` discriminator — scope of the check constraint today

Handoff §2: give the message row a `kind` discriminator "from the start," with 016 (already
scoped, decision at §37) later adding `conversational_turn` and `wrap_up` "as new values, not a
new schema." Read literally, this means 016's own migration is expected to widen this feature's
CHECK constraint — a one-line `ALTER TABLE ... DROP CONSTRAINT ... ADD CONSTRAINT ...` — not that
this feature should pre-authorize two enum values nothing can ever write yet.

**Decision**: `kind text not null check (kind in ('user_message', 'styling_reply'))` — the two
values this feature actually writes. The column and the concept exist from day one (the
accommodation the handoff asks for); the two not-yet-reachable values are 016's own one-line
migration to add, not dead/speculative surface shipped early. This matches the handoff's own
closing instruction most literally: "do not build anything else speculatively for 016... 
anticipate the shape, not the feature" — a CHECK constraint permitting unreachable values is
closer to building for 016 than a comment noting where it will extend the constraint.

`role` (user vs. assistant, needed to align a bubble left/right) is **not** a separate column —
it is fully determined by `kind` for all four values this and 016's own spec name
(`user_message` → user; every other kind → assistant), so a second column could only ever drift
from the first, never add information. Derived in the repository layer, matching this codebase's
general "compute, don't duplicate" bias (§41, §45).

## 5. Message count on a Chat-history row

`spec.md`'s Assumptions section: total turns (user + assistant), not user-only — the most literal
reading of design-system.md's "message-count text" with no further qualifier, and consistent
with `messages` covering both roles as one entity.

## 6. RLS + GRANT + query-level ownership — no new pattern

Both new tables (`sessions`, `messages`) and the new `outfits.thread_id` column follow `0002`'s
established shape exactly (Constitution + handoff trap #3): `for all using (auth.uid() =
user_id) with check (...)`, plus the non-optional table-level `grant ... to authenticated` `0002`
first documented as silently required (the pooler role's default ACL grants `authenticated` no
SELECT on a table `postgres` creates). Every repository method additionally filters
`WHERE user_id = :user_id` at the query level, since this backend's own connection has BYPASSRLS
and query-level filtering — not RLS — is what isolates *this app's* traffic; RLS is defense in
depth for any other access path (Studio, PostgREST, a future edge function), proven independent
of the app's own connection by a direct-port, `SET ROLE authenticated` two-user test — the same
shape as `test_outfits_rls.py`.

`messages.user_id` is denormalized (present on the message row itself, not only reachable via a
`sessions` join), matching `outfit_wears`/`item_wears`'s own convention — RLS policies and
ownership filters read a flat column directly rather than requiring a subquery/join to reach the
owning user on every row check.

## 7. No pagination

`GET /recommend/sessions` returns every session for the user unpaginated, matching
`GET /recommend/outfits`'s own existing shape at the same personal-app scale. Revisit only if a
real user's session count makes this observably slow — not a speculative concern to design around
now (Quality Bar: no abstraction without a measured problem).
