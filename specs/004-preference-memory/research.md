# Phase 0 Research: Preference Memory

The `/speckit.plan` technical prompt (docs/SDD-HANDOFF.md Step 5) already
fixed most technology choices (Postgres/SQLAlchemy/Alembic, no materialized
profile table, endpoint shapes, frontend touch points). This file resolves
the design gaps the prompt left open — each one a genuine implementation
decision, not a spec ambiguity (spec.md's Assumptions already cover the
user-facing forks).

## 1. Reaction identity — what makes two reactions "the same suggestion"?

**Question**: Edge Cases (spec.md) requires that reacting twice to the same
suggestion *replaces* the earlier reaction rather than accumulating. But
per spec.md's own Assumption, no `Suggestion` entity is persisted and no
suggestion id exists anywhere — `/recommend`'s `Outfit` model
(`schema.py`) is just `{items: list[str], rationale: [...]}`, no id field.

**Decision**: Use the reacted-to outfit's own item set as the natural
identity key. `SuggestionFeedbackRow` is unique on `(user_id, item_ids)`
where `item_ids` is stored as a sorted JSONB array (order-independent
comparison). Recording a reaction is an upsert on that key: same user +
same set of items → update verdict/reason/snapshot/created_at in place;
different item set → new row.

**Rationale**: "The outfit consisting of exactly these items" *is* what got
liked or rejected — two suggestions that happen to contain the identical
item set are, for feedback purposes, the same outfit regardless of which
`/recommend` call produced them. This needs no new entity, no client-
generated id, and satisfies the edge case exactly (replace-not-accumulate)
with a natural key instead of invented state.

**Alternative considered**: A client-generated ephemeral `suggestion_key`
(UUID minted by the frontend when rendering an outfit card, passed through
on reaction). Rejected — it adds a field with no server-side meaning beyond
dedup, and the item-set key already provides equivalent dedup semantics
for free.

## 2. Preference derivation algorithm and thresholds

**Question**: spec.md's Assumptions defer the exact repeat-count threshold
to implementation. FR-006/Edge Cases require: pattern-based (not reactive
to one event), and a genuine contradiction (reject blue once, like blue
later) must not erase an otherwise consistent pattern.

**Decision** — `memory/preferences.py`, pure functions over a list of
`SuggestionFeedbackRow`-shaped data (no DB access in this module, so it's
independently unit-testable per the constitution's Quality Bar):

- `MIN_SIGNAL_COUNT = 3` (module constant).
- **Rejected colors**: for each hex color appearing in any snapshot, compute
  `net = rejection_count(color) - like_count(color)`. Included in the
  profile if `net >= MIN_SIGNAL_COUNT`. The subtraction is what satisfies
  the contradiction edge case — one stray "liked" instance of an otherwise
  consistently-rejected color reduces, but doesn't erase, the signal.
- **Avoided categories**: identical net-score logic keyed on the snapshot's
  `category` field (the item taxonomy's existing category string, not the
  coarser category group — matches how items are actually described back
  to the user).
- **Formality drift**: computed only when the user has at least
  `MIN_SIGNAL_COUNT` liked *and* `MIN_SIGNAL_COUNT` rejected outfits with
  formality data (both sides needed for "drift" to mean anything — a
  one-sided sample can't establish a direction). Direction is
  `avg(FORMALITY_ORDER[rejected]) - avg(FORMALITY_ORDER[liked])`: `>= 1`
  full enum step means "wants less formal than suggested"; `<= -1` means
  "wants more formal"; otherwise no drift signal is reported yet.
- A user with feedback below every threshold gets an empty profile (User
  Story 3, AC2 — "nothing learned yet", not an error). Signals are
  independent — a user can have a color signal with no formality signal.

**Rationale**: Every rule is a simple, deterministic count/average with a
fixed threshold — reproducible, unit-testable without touching the DB or an
LLM, and each piece degrades gracefully to "no signal yet" rather than
guessing from insufficient data.

**Alternatives considered**: A decay-weighted or recency-weighted score
(more recent feedback counts more). Rejected as unnecessary complexity for
a solo-scale project — the net-count threshold already satisfies every
FR/AC in the spec, and a recency weighting scheme has no spec requirement
driving it (YAGNI, per the constitution's simplicity clause).

## 3. Removing one signal / clearing the whole profile without a profile table

**Question**: The technical prompt says no materialized profile table — the
profile is computed on read. But FR-009 requires removing *one* derived
signal without touching the rest, and FR-010 requires clearing the whole
profile, and Edge Cases (US4, AC3) require that a cleared signal can be
*re-learned* from new feedback later — not permanently blocked. With only
raw feedback rows, there's no clean way to "delete a signal" without either
deleting the feedback that produced it (which would also delete it from the
user's feedback history, not just their derived profile) or introducing
some tiny piece of state.

**Decision**: One small additional table, `preference_signal_dismissal`
(`user_id`, `signal_key`, `dismissed_at`), upserted on `(user_id,
signal_key)`. `derive_profile()` excludes, per signal, any feedback rows
with `created_at <= dismissed_at` for that `(user_id, signal_key)` pair when
computing that specific signal. `signal_key` is one of `color:{hex}`,
`category:{value}`, or the literal `formality_drift`.

- **Remove one signal** (FR-009): upsert a dismissal row for that one
  `signal_key`, `dismissed_at = now()`. Only that signal's future
  derivation is affected.
- **Clear entire profile** (FR-010): compute the current profile, then
  upsert a dismissal row (dismissed_at = now()) for every signal_key
  currently present. Same primitive, applied to every present key — no
  separate "clear all" code path.
- **Re-learning** (Edge Cases / US4 AC3): new feedback rows created *after*
  `dismissed_at` count again, so the same signal reappears once
  `MIN_SIGNAL_COUNT` new events re-establish it.

**Rationale**: This is not a materialized *profile* (it stores no derived
value, only a per-signal timestamp cutoff) — consistent with the technical
prompt's "no separate materialized preference profile table, compute on
read" instruction. It's the minimum state needed to satisfy FR-009/FR-010/
the re-learning edge case, reusing one mechanism for both "remove one" and
"clear all" rather than building two.

**Alternative considered**: Deleting the underlying `SuggestionFeedback`
rows that contributed to a dismissed signal. Rejected — it would silently
destroy the user's actual feedback/reaction history (which the spec treats
as a record: reasons "may be shown back to the user alongside their
feedback history"), conflating "I don't want this to influence suggestions
anymore" with "this never happened."

## 4. `profile_note(user_id)` staying signature-compatible

**Question**: The technical prompt requires `pipeline/run.py` and
`pipeline/generator.py` to need zero changes, but `run.py` calls
`memory.profile_note(user_id)` with no DB session in scope (it's a plain
function call inside `recommend()`, not a FastAPI request handler with a
`Depends(get_session)` session).

**Decision**: `memory/store.py`'s Postgres-backed `get_profile()` opens and
closes its own short-lived session via `db.SessionLocal()` directly
(already exported at module level in `db.py` for exactly this kind of
non-request-scoped use), rather than accepting a session parameter.
`profile_note(user_id)`'s signature and return shape (`Optional[str]`,
`"key: value; key: value"` joined string, `None` when nothing learned)
stay byte-for-byte unchanged, so `generator.py`'s existing prompt-injection
logic (`pipeline/generator.py:96-97`, "soft preference, never overrides
constraints") needs no change either — that framing already satisfies
FR-005 (learned preference never overrides an explicit request).

**Rationale**: This is the one concrete way to satisfy "zero changes to
run.py/generator.py" while switching the backing store — matches how
`crud.py`'s free functions already take an explicit `Session` at API call
sites, but `memory/store.py` sits partly outside the request lifecycle
(also called by `remember_interaction`, which is explicitly out of scope
and staying in-memory).

## 5. Testing approach

**Decision**: Match Feature 001/003 exactly — integration tests for the 4
new endpoints run against the live Supabase DB through the existing
rollback-transaction fixture (`backend/tests/conftest.py`); no mocking of
Postgres. `memory/preferences.py`'s `derive_profile()`/threshold logic gets
plain unit tests with hand-built feedback data (no DB, no fixture) since
it's pure Python, per the constitution's "deterministic logic requires
unit tests." No LLM-dependent path is added by this feature (derivation is
non-LLM per spec.md's Assumptions), so no new `data/golden_set.yaml` entry
is required — the existing entries covering `/recommend` generation are
unaffected since `profile_note`'s contract is unchanged.
