"""Unit tests for seed_catalog() and seed_eval_baseline_user() (T011).

Run against the real Supabase database via the db_session fixture (rolled
back after each test — see conftest.py), since JSONB columns require the
Postgres dialect and this solo-scale project has no separate test database.
"""

from __future__ import annotations

import json

from sqlalchemy import delete, select, update

from whattowear import crud
from whattowear.memory import store as memory
from whattowear.models import CatalogItemRow, WardrobeItemRow


def _fixture_items() -> list[dict]:
    with open(crud.WARDROBE_FIXTURE, encoding="utf-8") as fh:
        return json.load(fh)


def _fixture_attr_tuple(it: dict) -> tuple:
    return (it["category"], it["formality"], it["warmth"], tuple(it["season"]), tuple(it["colors"]))


def _row_attr_tuple(row) -> tuple:
    return (row.category, row.formality, row.warmth, tuple(row.season), tuple(row.colors))


def _clear_catalog(db_session) -> None:
    # Production catalog/eval-baseline rows already exist (seeded for real via
    # the CLI, plus real wardrobe_items added through manual testing that
    # reference them via catalog_item_id); clear within this test's
    # rolled-back transaction so each test starts from an empty table without
    # touching the real committed data. Null out referencing FKs first so the
    # delete doesn't hit ForeignKeyViolation against those real rows.
    db_session.execute(
        update(WardrobeItemRow).where(WardrobeItemRow.catalog_item_id.isnot(None)).values(catalog_item_id=None)
    )
    db_session.execute(delete(CatalogItemRow))


def _clear_eval_baseline_wardrobe(db_session) -> None:
    db_session.execute(delete(WardrobeItemRow).where(WardrobeItemRow.user_id == crud.EVAL_BASELINE_USER_ID))


def test_seed_catalog_inserts_all_40_fixture_items_with_null_fabric(db_session):
    _clear_catalog(db_session)
    inserted = crud.seed_catalog(db_session)

    assert inserted == 40
    rows = db_session.scalars(select(CatalogItemRow)).all()
    assert len(rows) == 40
    assert all(row.fabric is None for row in rows)
    assert sorted(_row_attr_tuple(r) for r in rows) == sorted(_fixture_attr_tuple(it) for it in _fixture_items())


def test_seed_catalog_is_idempotent(db_session):
    _clear_catalog(db_session)
    first = crud.seed_catalog(db_session)
    second = crud.seed_catalog(db_session)

    assert first == 40
    assert second == 0
    rows = db_session.scalars(select(CatalogItemRow)).all()
    assert len(rows) == 40


def test_seed_eval_baseline_user_matches_fixture_ids_and_attributes(db_session):
    _clear_eval_baseline_wardrobe(db_session)
    inserted = crud.seed_eval_baseline_user(db_session)

    assert inserted == 40
    rows = db_session.scalars(
        select(WardrobeItemRow).where(WardrobeItemRow.user_id == crud.EVAL_BASELINE_USER_ID)
    ).all()
    assert len(rows) == 40
    assert all(row.source == "catalog" for row in rows)
    assert sorted(_row_attr_tuple(r) for r in rows) == sorted(_fixture_attr_tuple(it) for it in _fixture_items())


def test_seed_eval_baseline_user_is_idempotent(db_session):
    _clear_eval_baseline_wardrobe(db_session)
    first = crud.seed_eval_baseline_user(db_session)
    second = crud.seed_eval_baseline_user(db_session)

    assert first == 40
    assert second == 0
    rows = db_session.scalars(
        select(WardrobeItemRow).where(WardrobeItemRow.user_id == crud.EVAL_BASELINE_USER_ID)
    ).all()
    assert len(rows) == 40


def test_seed_eval_baseline_user_has_no_seeded_preferences(db_session):
    crud.seed_eval_baseline_user(db_session)

    assert memory.profile_note(str(crud.EVAL_BASELINE_USER_ID)) is None
