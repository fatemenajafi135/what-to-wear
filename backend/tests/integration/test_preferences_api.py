"""Integration tests for the four /preferences endpoints (Feature 004:
preference-memory) against the real Supabase DB via the rollback-transaction
fixture (conftest.py) -- same pattern as test_wardrobe_add.py.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from whattowear.api import app
from whattowear.auth import get_current_user_id
from whattowear.db import get_session
from whattowear.models import WardrobeItemRow


@pytest.fixture
def client(db_session):
    app.dependency_overrides[get_session] = lambda: (yield db_session)
    yield TestClient(app), db_session
    app.dependency_overrides.pop(get_session, None)
    app.dependency_overrides.pop(get_current_user_id, None)


def _as_user(user_id) -> None:
    app.dependency_overrides[get_current_user_id] = lambda: str(user_id)


def _wardrobe_item(session, user_id, **overrides) -> WardrobeItemRow:
    defaults = dict(
        user_id=uuid.UUID(str(user_id)),
        category="top",
        colors=["#1b2a4a"],
        formality="casual",
        warmth=1,
        season=["summer"],
        source="catalog",
    )
    defaults.update(overrides)
    row = WardrobeItemRow(**defaults)
    session.add(row)
    session.commit()
    return row


# --- User Story 1: react to a suggestion --------------------------------------


class TestSubmitFeedback:
    def test_liked_reaction_recorded(self, client):
        c, session = client
        user_id = uuid.uuid4()
        item = _wardrobe_item(session, user_id)
        _as_user(user_id)

        r = c.post("/preferences/feedback", json={"verdict": "liked", "item_ids": [str(item.id)]})

        assert r.status_code == 201
        body = r.json()
        assert body["verdict"] == "liked"
        assert body["item_ids"] == [str(item.id)]
        assert body["reason"] is None

    def test_rejected_reaction_with_reason_recorded(self, client):
        c, session = client
        user_id = uuid.uuid4()
        item = _wardrobe_item(session, user_id)
        _as_user(user_id)

        r = c.post(
            "/preferences/feedback",
            json={"verdict": "rejected", "reason": "too formal", "item_ids": [str(item.id)]},
        )

        assert r.status_code == 201
        body = r.json()
        assert body["verdict"] == "rejected"
        assert body["reason"] == "too formal"

    def test_rejected_reaction_without_reason_recorded(self, client):
        c, session = client
        user_id = uuid.uuid4()
        item = _wardrobe_item(session, user_id)
        _as_user(user_id)

        r = c.post("/preferences/feedback", json={"verdict": "rejected", "item_ids": [str(item.id)]})

        assert r.status_code == 201
        assert r.json()["reason"] is None

    def test_reacting_twice_to_same_items_replaces_not_accumulates(self, client):
        c, session = client
        user_id = uuid.uuid4()
        item = _wardrobe_item(session, user_id)
        _as_user(user_id)

        first = c.post("/preferences/feedback", json={"verdict": "liked", "item_ids": [str(item.id)]})
        second = c.post(
            "/preferences/feedback",
            json={"verdict": "rejected", "reason": "changed my mind", "item_ids": [str(item.id)]},
        )

        assert first.status_code == 201 and second.status_code == 201
        assert first.json()["id"] == second.json()["id"]  # same row, replaced

        # confirm exactly one row exists for this (user, item set) at the DB level
        from sqlalchemy import select

        from whattowear.models import SuggestionFeedbackRow

        rows = session.scalars(select(SuggestionFeedbackRow).where(SuggestionFeedbackRow.user_id == user_id)).all()
        assert len(rows) == 1
        assert rows[0].verdict == "rejected"

    def test_unknown_item_id_returns_404(self, client):
        c, _ = client
        _as_user(uuid.uuid4())

        r = c.post("/preferences/feedback", json={"verdict": "liked", "item_ids": [str(uuid.uuid4())]})

        assert r.status_code == 404

    def test_foreign_item_id_returns_404(self, client):
        c, session = client
        owner, other = uuid.uuid4(), uuid.uuid4()
        item = _wardrobe_item(session, owner)
        _as_user(other)

        r = c.post("/preferences/feedback", json={"verdict": "liked", "item_ids": [str(item.id)]})

        assert r.status_code == 404

    def test_missing_bearer_token_returns_401(self, client):
        c, session = client
        item = _wardrobe_item(session, uuid.uuid4())
        app.dependency_overrides.pop(get_current_user_id, None)

        r = c.post("/preferences/feedback", json={"verdict": "liked", "item_ids": [str(item.id)]})

        assert r.status_code == 401

    def test_empty_item_ids_returns_422(self, client):
        c, _ = client
        _as_user(uuid.uuid4())

        r = c.post("/preferences/feedback", json={"verdict": "liked", "item_ids": []})

        assert r.status_code == 422


# --- User Story 3: see what the system has learned ----------------------------

MIN_SIGNAL_COUNT = 3  # memory.preferences.MIN_SIGNAL_COUNT — kept in sync explicitly, not imported,
# so this test file also acts as a regression guard if the threshold constant ever moves.


def _reject_color(c, session, user_id, hex_color, n) -> list[str]:
    feedback_ids = []
    for _ in range(n):
        item = _wardrobe_item(session, user_id, category=f"filler-{uuid.uuid4()}", colors=[hex_color])
        r = c.post("/preferences/feedback", json={"verdict": "rejected", "item_ids": [str(item.id)]})
        assert r.status_code == 201
        feedback_ids.append(r.json()["id"])
    return feedback_ids


class TestGetPreferences:
    def test_brand_new_user_has_no_feedback_state(self, client):
        c, _ = client
        _as_user(uuid.uuid4())

        r = c.get("/preferences")

        assert r.status_code == 200
        assert r.json() == {"has_feedback": False, "signals": []}

    def test_feedback_below_threshold_has_feedback_but_no_signals(self, client):
        c, session = client
        user_id = uuid.uuid4()
        _as_user(user_id)
        _reject_color(c, session, user_id, "#1b2a4a", MIN_SIGNAL_COUNT - 1)

        r = c.get("/preferences")

        assert r.status_code == 200
        assert r.json() == {"has_feedback": True, "signals": []}

    def test_crossed_threshold_shows_plain_language_signal_no_raw_hex(self, client):
        c, session = client
        user_id = uuid.uuid4()
        _as_user(user_id)
        _reject_color(c, session, user_id, "#1b2a4a", MIN_SIGNAL_COUNT)

        r = c.get("/preferences")

        assert r.status_code == 200
        body = r.json()
        assert body["has_feedback"] is True
        assert len(body["signals"]) == 1
        signal = body["signals"][0]
        assert signal["key"] == "color:#1b2a4a"
        assert "#1b2a4a" not in signal["summary"]  # FR-007: no raw hex in the plain-language text
        assert signal["summary"]  # non-empty human sentence

    def test_cross_user_isolation(self, client):
        c, session = client
        user_a, user_b = uuid.uuid4(), uuid.uuid4()
        _as_user(user_a)
        _reject_color(c, session, user_a, "#1b2a4a", MIN_SIGNAL_COUNT)

        _as_user(user_b)
        r = c.get("/preferences")

        assert r.json() == {"has_feedback": False, "signals": []}


# --- User Story 4: clear or correct a learned preference ----------------------


class TestRemoveAndClearPreferences:
    def test_remove_one_signal_leaves_others_intact(self, client):
        c, session = client
        user_id = uuid.uuid4()
        _as_user(user_id)
        _reject_color(c, session, user_id, "#1b2a4a", MIN_SIGNAL_COUNT)
        for _ in range(MIN_SIGNAL_COUNT):
            item = _wardrobe_item(session, user_id, category="blazer")
            c.post("/preferences/feedback", json={"verdict": "rejected", "item_ids": [str(item.id)]})

        r = c.delete("/preferences/signals/color:%231b2a4a")
        assert r.status_code == 204

        remaining = c.get("/preferences").json()["signals"]
        assert [s["key"] for s in remaining] == ["category:blazer"]

    def test_clear_entire_profile_resets_to_no_feedback_equivalent_state(self, client):
        c, session = client
        user_id = uuid.uuid4()
        _as_user(user_id)
        _reject_color(c, session, user_id, "#1b2a4a", MIN_SIGNAL_COUNT)

        r = c.delete("/preferences")
        assert r.status_code == 204

        profile = c.get("/preferences").json()
        assert profile["signals"] == []

    def test_dismissing_an_absent_signal_is_a_no_op_not_404(self, client):
        c, _ = client
        _as_user(uuid.uuid4())

        r = c.delete("/preferences/signals/color:%23000000")

        assert r.status_code == 204

    def test_new_feedback_after_dismissal_re_establishes_the_signal(self, client):
        c, session = client
        user_id = uuid.uuid4()
        _as_user(user_id)
        _reject_color(c, session, user_id, "#1b2a4a", MIN_SIGNAL_COUNT)
        c.delete("/preferences/signals/color:%231b2a4a")
        assert c.get("/preferences").json()["signals"] == []

        new_feedback_ids = _reject_color(c, session, user_id, "#1b2a4a", MIN_SIGNAL_COUNT)
        # Postgres's now() is transaction-time, not statement-time: every row
        # inserted within this test's single rolled-back transaction gets the
        # identical created_at, so the "new" batch above isn't naturally after
        # the dismissal's (real, Python-clock) cutoff the way it would be
        # across separate requests in production. Push just this new batch's
        # created_at forward explicitly so the re-establishment logic under
        # test is actually exercised, without touching the earlier
        # (still-dismissed) batch's rows.
        from datetime import datetime, timedelta, timezone

        from sqlalchemy import update

        from whattowear.models import SuggestionFeedbackRow

        session.execute(
            update(SuggestionFeedbackRow)
            .where(SuggestionFeedbackRow.id.in_(uuid.UUID(i) for i in new_feedback_ids))
            .values(created_at=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(seconds=5))
        )
        session.commit()

        signals = c.get("/preferences").json()["signals"]
        assert [s["key"] for s in signals] == ["color:#1b2a4a"]
