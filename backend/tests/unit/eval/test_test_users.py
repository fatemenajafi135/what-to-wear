"""Smoke tests for eval/test_users.py — hand-built personas for manual
exploration, not part of the golden-set gate. Never had a test in the
legacy suite (UNREF, __main__-guarded); this confirms the three personas
construct validly and stay retrievable by id."""

from __future__ import annotations

from whattowear.eval.test_users import AMARA, LEO, MAYA, TEST_USERS, get_test_user


def test_all_three_personas_are_registered() -> None:
    assert set(TEST_USERS) == {"test-maya", "test-leo", "test-amara"}


def test_get_test_user_returns_the_matching_persona() -> None:
    assert get_test_user("test-maya") is MAYA
    assert get_test_user("test-leo") is LEO
    assert get_test_user("test-amara") is AMARA


def test_every_persona_has_a_non_empty_wardrobe_of_valid_items() -> None:
    for user in TEST_USERS.values():
        assert len(user.wardrobe) > 0
        for item in user.wardrobe:
            assert item.colors  # hex-converted at construction; would have raised if invalid
