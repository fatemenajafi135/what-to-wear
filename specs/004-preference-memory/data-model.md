# Phase 1 Data Model: Preference Memory

## New tables (additive-only Alembic migration `0003_add_suggestion_feedback.py`)

### `suggestion_feedback`

One user's current reaction to one outfit (identified by its item set — see
research.md §1). At most one row per `(user_id, item_ids)` — a later
reaction upserts, it does not accumulate (spec.md Edge Cases).

| Column | Type | Notes |
|---|---|---|
| `id` | UUID, PK, default `uuid4()` | |
| `user_id` | UUID, not null, indexed | Bare opaque UUID from verified JWT `sub`, no local `users` table — same pattern as `wardrobe_items.user_id`. |
| `verdict` | String, not null | `"liked"` \| `"rejected"` (CHECK constraint, mirrors `WardrobeItemRow`'s CheckConstraint style). |
| `reason` | String, nullable | Free text, only meaningful when `verdict = "rejected"` (FR-002); not validated against `verdict` at the DB layer — the API layer ignores `reason` on a `"liked"` reaction. |
| `item_ids` | JSONB, not null | Sorted list of the reacted-to outfit's wardrobe item ids (strings). Sorted so `(user_id, item_ids)` is a stable dedup key regardless of the order `/recommend` returned them in. |
| `item_snapshot` | JSONB, not null | List of `{item_id, category, colors, formality}` — the *attributes at feedback time* for each id in `item_ids`, looked up from `wardrobe_items` when the reaction is recorded. Snapshotted (not re-joined live) because a wardrobe item can later be edited or deleted (Feature 001 PATCH/DELETE) and the learned signal must still reflect what was actually reacted to. |
| `created_at` | TIMESTAMP, server default `now()` | Set on insert; **also updated on upsert** (an updated reaction is "created now" for dedup/recency purposes — see research.md §1). |

Constraints: `CheckConstraint("verdict IN ('liked','rejected')")`. Unique
index on `(user_id, item_ids)` — Postgres can index a JSONB column for
equality via a functional/expression index if needed; simplest correct
approach is to also store a `item_ids_key` derived `String` column
(comma-joined sorted ids) with a plain unique constraint on
`(user_id, item_ids_key)`, avoiding any JSONB-equality edge cases. (Decision
for tasks: add `item_ids_key: Mapped[str]` alongside `item_ids`, computed at
write time — same information, indexable the simple way, consistent with
how the rest of this codebase avoids cleverness over correctness.)

### `preference_signal_dismissal`

Per-user, per-signal suppression cutoff (research.md §3). Not a
materialized profile — stores no derived value, only a timestamp cutoff
used to filter `suggestion_feedback` rows out of a specific signal's
derivation.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID, PK, default `uuid4()` | |
| `user_id` | UUID, not null, indexed | |
| `signal_key` | String, not null | `"color:{hex}"`, `"category:{value}"`, or `"formality_drift"`. |
| `dismissed_at` | TIMESTAMP, not null | Feedback rows with `created_at <= dismissed_at` don't count toward this `signal_key`. |

Unique constraint on `(user_id, signal_key)` — "remove a signal" is an
upsert (update `dismissed_at` to now if a row already exists), not an
insert-only log.

## SQLAlchemy models (`models.py` additions)

```python
class SuggestionFeedbackRow(Base):
    __tablename__ = "suggestion_feedback"
    __table_args__ = (
        CheckConstraint("verdict IN ('liked','rejected')", name="ck_suggestion_feedback_verdict"),
        UniqueConstraint("user_id", "item_ids_key", name="uq_suggestion_feedback_user_items"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    verdict: Mapped[str] = mapped_column(String, nullable=False)
    reason: Mapped[str | None] = mapped_column(String, nullable=True)
    item_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    item_ids_key: Mapped[str] = mapped_column(String, nullable=False)
    item_snapshot: Mapped[list[dict]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now(), nullable=False)


class PreferenceSignalDismissalRow(Base):
    __tablename__ = "preference_signal_dismissal"
    __table_args__ = (UniqueConstraint("user_id", "signal_key", name="uq_pref_dismissal_user_signal"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    signal_key: Mapped[str] = mapped_column(String, nullable=False)
    dismissed_at: Mapped[datetime] = mapped_column(nullable=False)
```

## Pydantic contracts (`schema.py` additions)

```python
Verdict = Literal["liked", "rejected"]

class SubmitFeedbackRequest(BaseModel):
    verdict: Verdict
    reason: Optional[str] = None          # only meaningful when verdict == "rejected"
    item_ids: list[str] = Field(min_length=1)  # the reacted-to outfit's wardrobe item ids

class SuggestionFeedback(BaseModel):
    id: str
    verdict: Verdict
    reason: Optional[str] = None
    item_ids: list[str]
    created_at: str

class PreferenceSignal(BaseModel):
    key: str          # "color:#1b2a4a" / "category:blazer" / "formality_drift"
    summary: str       # plain-language, e.g. "You tend to reject navy items."

class PreferenceProfile(BaseModel):
    signals: list[PreferenceSignal] = Field(default_factory=list)
    has_feedback: bool  # False => "nothing learned yet" state (FR-008), distinct from an empty-but-has-history profile
```

`memory/store.py`'s internal `get_profile(user_id) -> dict[str, str]` keeps
its existing shape (short `key: value` pairs, used only to build
`profile_note`'s prompt string) — it is a different, smaller projection
than the `PreferenceProfile` API response, which carries full sentences for
the frontend (FR-007: "plain-language ... not raw counts or internal
identifiers"). `memory/preferences.py`'s `derive_profile()` is the one
function both call: it returns the structured signal list; `get_profile()`
projects it to short `key: value` strings, the API layer projects it to
`PreferenceSignal.summary` sentences.

## Derivation function signature (`memory/preferences.py`)

```python
@dataclass
class DerivedSignal:
    key: str
    kind: Literal["color", "category", "formality_drift"]
    detail: str          # hex / category value / "less_formal" | "more_formal"
    supporting_count: int

def derive_signals(
    feedback: list[FeedbackRecord],           # plain dataclass, no ORM/session dependency
    dismissals: dict[str, datetime],           # signal_key -> dismissed_at
) -> list[DerivedSignal]: ...
```

Pure function, no DB access — `FeedbackRecord` is a small dataclass mirror
of the row shape (`verdict`, `item_snapshot`, `created_at`) so this module
is unit-testable with hand-built lists (research.md §5).

## Relationships

- `suggestion_feedback.user_id` / `preference_signal_dismissal.user_id` —
  bare opaque UUID, no FK, same pattern as `wardrobe_items.user_id`
  (no local `users` table — research.md, Feature 001 precedent).
- `suggestion_feedback.item_snapshot` — no FK to `wardrobe_items`; it's a
  point-in-time copy, deliberately decoupled so edits/deletes to the live
  item never retroactively change historical feedback (research.md §1's
  snapshot rationale).

## Validation rules

- `SubmitFeedbackRequest.item_ids` must be non-empty and must all belong to
  the caller's own `wardrobe_items` (checked at the API/crud layer, not the
  DB) — any unknown or foreign id → 404, mirroring
  `UnknownCatalogItemIds`'s existing pattern in `crud.py`.
- `reason` on a `"liked"` reaction is accepted but not required; storing it
  is harmless (FR-002 only requires it for rejections) — no validation
  error either way, since it's the exact optional-field.
