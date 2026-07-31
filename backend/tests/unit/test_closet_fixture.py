"""adapters/closet_fixture.py — the eval/test ClosetRepository binding.

Deferred from T007 to right after T008 (schema.py lands) — see
specs/007-ai-port/tasks.md.
"""

from __future__ import annotations

from whattowear.adapters.closet_fixture import FixtureClosetRepository


def test_wardrobe_and_catalog_are_the_same_forty_item_fixture() -> None:
    repo = FixtureClosetRepository()
    wardrobe = repo.list_wardrobe_items("any-user-id")
    catalog = repo.list_catalog_items()
    assert len(wardrobe) == 40
    assert [item.id for item in wardrobe] == [item.id for item in catalog]


def test_any_user_id_gets_the_same_wardrobe() -> None:
    repo = FixtureClosetRepository()
    assert [i.id for i in repo.list_wardrobe_items("user-a")] == [i.id for i in repo.list_wardrobe_items("user-b")]


def test_get_derivation_inputs_is_always_empty() -> None:
    """Matches crud.seed_eval_baseline_user's documented guarantee: the eval
    baseline user is seeded with closet items only, never feedback, so
    memory.profile_note() stays None (research.md §5)."""
    repo = FixtureClosetRepository()
    feedback, dismissals = repo.get_derivation_inputs("any-user-id")
    assert feedback == []
    assert dismissals == {}


def test_items_are_real_wardrobe_item_instances_with_normalized_hex() -> None:
    repo = FixtureClosetRepository()
    item = repo.list_wardrobe_items("any-user-id")[0]
    assert all(c.startswith("#") and len(c) == 7 for c in item.colors)
