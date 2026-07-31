from __future__ import annotations

from datetime import date, timedelta

import pytest
from pydantic import ValidationError

from whattowear.schemas.profile import BodySizeUpdate, StylePreferencesUpdate


def test_style_tags_reject_out_of_vocabulary() -> None:
    with pytest.raises(ValidationError):
        StylePreferencesUpdate(style_tags=["Not A Real Tag"], colour_tags=[], brands_to_avoid=[])


def test_colour_tags_reject_out_of_vocabulary() -> None:
    with pytest.raises(ValidationError):
        StylePreferencesUpdate(style_tags=[], colour_tags=["Neon"], brands_to_avoid=[])


def test_brands_to_avoid_trims_and_dedupes() -> None:
    update = StylePreferencesUpdate(style_tags=[], colour_tags=[], brands_to_avoid=[" Brand X ", "Brand X", "Brand Y"])
    assert update.brands_to_avoid == ["Brand X", "Brand Y"]


def test_brands_to_avoid_rejects_empty_string() -> None:
    with pytest.raises(ValidationError):
        StylePreferencesUpdate(style_tags=[], colour_tags=[], brands_to_avoid=["   "])


def test_empty_brands_to_avoid_is_valid() -> None:
    update = StylePreferencesUpdate(style_tags=["Classic"], colour_tags=[], brands_to_avoid=[])
    assert update.brands_to_avoid == []


def test_body_shape_rejects_out_of_vocabulary() -> None:
    with pytest.raises(ValidationError):
        BodySizeUpdate(body_shape="triangle")


def test_gender_accepts_null() -> None:
    update = BodySizeUpdate(gender=None)
    assert update.gender is None


def test_top_size_rejects_out_of_vocabulary() -> None:
    with pytest.raises(ValidationError):
        BodySizeUpdate(top_size="4XL")


def test_bottom_size_accepts_documented_range() -> None:
    update = BodySizeUpdate(bottom_size="08")
    assert update.bottom_size == "08"


def test_birth_date_in_the_past_is_valid() -> None:
    update = BodySizeUpdate(birth_date=date(1990, 5, 12))
    assert update.birth_date == date(1990, 5, 12)


def test_birth_date_in_the_future_is_rejected() -> None:
    with pytest.raises(ValidationError):
        BodySizeUpdate(birth_date=date.today() + timedelta(days=1))


def test_birth_date_null_is_valid() -> None:
    update = BodySizeUpdate(birth_date=None)
    assert update.birth_date is None
