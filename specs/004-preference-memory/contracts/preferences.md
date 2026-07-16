# Contract: Preference Memory Endpoints

All four endpoints reuse the existing `get_current_user_id` JWT dependency
(`auth.py`, unchanged) and the existing `get_session` DB dependency
(`db.py`, unchanged) — same pattern as every `/wardrobe/items` endpoint.
`user_id` always comes from the verified `sub` claim, never a request body
or path field (constitution/Feature 002 Phase 1 precedent — no exceptions
here).

## `POST /preferences/feedback`

Record (or replace) a reaction to a specific outfit. FR-001, FR-002.

**Request** (`SubmitFeedbackRequest`):
```json
{
  "verdict": "rejected",
  "reason": "too formal for a coffee date",
  "item_ids": ["a1b2...", "c3d4..."]
}
```

**Behavior**:
1. Resolve `item_ids` against the caller's own `wardrobe_items` — any id
   that doesn't exist or belongs to another user → `404` (matches
   `UnknownCatalogItemIds`'s existing 404 pattern in `crud.py`).
2. Build `item_snapshot` from the resolved rows' current
   `category`/`colors`/`formality`.
3. Upsert on `(user_id, item_ids_key)` (research.md §1): if a feedback row
   already exists for this exact item set, replace its
   `verdict`/`reason`/`item_snapshot`/`created_at`; otherwise insert.

**Response** `201` (`SuggestionFeedback`):
```json
{
  "id": "e5f6...",
  "verdict": "rejected",
  "reason": "too formal for a coffee date",
  "item_ids": ["a1b2...", "c3d4..."],
  "created_at": "2026-07-16T18:04:00Z"
}
```

**Errors**: `401` no/invalid token. `404` an `item_id` isn't in the
caller's own wardrobe. `422` empty `item_ids` or invalid `verdict`.

---

## `GET /preferences`

View the derived, plain-language preference profile. FR-007, FR-008.

**Response** `200` (`PreferenceProfile`):

With learned signals:
```json
{
  "has_feedback": true,
  "signals": [
    {"key": "color:#1b2a4a", "summary": "You tend to reject navy items."},
    {"key": "category:blazer", "summary": "You tend to avoid blazers."},
    {"key": "formality_drift", "summary": "You usually want suggestions less formal than what's given."}
  ]
}
```

No feedback yet (FR-008 — a clear empty state, not an error):
```json
{ "has_feedback": false, "signals": [] }
```

Feedback exists but no signal has crossed `MIN_SIGNAL_COUNT` yet — also a
valid, non-error state distinct from "no feedback at all":
```json
{ "has_feedback": true, "signals": [] }
```

**Errors**: `401` only.

---

## `DELETE /preferences/signals/{signal_key}`

Remove one derived signal without affecting the rest of the profile.
FR-009, Edge Cases (re-learnable, not a permanent block).

`signal_key` is URL-encoded, e.g. `color:%231b2a4a`, `category:blazer`,
`formality_drift` — the same `key` returned by `GET /preferences`.

**Behavior**: upsert a `preference_signal_dismissal` row for
`(user_id, signal_key)` with `dismissed_at = now()` (research.md §3). Does
not touch `suggestion_feedback` rows — the underlying feedback history is
untouched, only that one signal's future derivation is suppressed until
enough *new* feedback re-establishes it.

**Response**: `204` on success (idempotent — dismissing an already-absent
signal is not an error, it's still true after the call that the signal is
absent).

**Errors**: `401` only. No `404` for an unknown `signal_key` — dismissing a
signal that was never present is a no-op, not an error (simpler contract,
matches "remove a signal" being safe to call speculatively from the UI).

---

## `DELETE /preferences`

Clear the entire derived profile in one action. FR-010, SC-004.

**Behavior**: compute the current profile's signal keys, then apply the
same dismissal upsert (as `DELETE /preferences/signals/{signal_key}`) to
every key present right now — one mechanism, reused (research.md §3). A
user with no current signals gets a no-op `204`.

**Response**: `204`.

**Errors**: `401` only.

---

## Isolation (FR-011, all four endpoints)

Every query is scoped by the verified `user_id` from the JWT — there is no
code path where one user's feedback, profile, or dismissal state is
readable or writable by another user's token, matching the existing
`/wardrobe/items` isolation guarantee exactly (same dependency, same
per-row `user_id` filter pattern).
