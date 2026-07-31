"""Pydantic request/response models for `api/v1/routes/profile.py`.

See specs/013-profile-settings/contracts/profile-settings-api.md — this module is the
implementation of that contract; the frontend never hand-writes a matching type, it consumes
`openapi-typescript`'s generation of this module's JSON Schema (Constitution Principle VII).
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field, field_validator

STYLE_TAGS = {"Classic", "Minimal", "Bold", "Casual", "Edgy"}
COLOUR_TAGS = {"Neutral tones", "Jewel tones", "Pastels", "Monochrome", "Earth tones"}
BODY_SHAPES = {"hourglass", "pear", "rectangle", "apple", "inverted_triangle"}
GENDERS = {"woman", "man", "non_binary", "prefer_not_to_say"}
TOP_SIZES = {"XXS", "XS", "S", "M", "L", "XL", "XXL", "XXXL"}
BOTTOM_SIZES = {f"{n:02d}" for n in range(0, 21, 2)}


def _validate_membership(values: list[str], vocabulary: set[str], field_name: str) -> list[str]:
    invalid = [v for v in values if v not in vocabulary]
    if invalid:
        raise ValueError(f"{field_name} contains values outside the allowed set: {invalid}")
    return values


def _validate_brands_to_avoid(values: list[str]) -> list[str]:
    trimmed = [v.strip() for v in values]
    if any(not v for v in trimmed):
        raise ValueError("brands_to_avoid entries must not be empty")
    seen: list[str] = []
    for value in trimmed:
        if value not in seen:
            seen.append(value)
    return seen


class ProfileResponse(BaseModel):
    style_tags: list[str] = Field(default_factory=list)
    colour_tags: list[str] = Field(default_factory=list)
    brands_to_avoid: list[str] = Field(default_factory=list)
    body_shape: str | None = None
    gender: str | None = None
    birth_date: date | None = None
    height: str | None = None
    top_size: str | None = None
    bottom_size: str | None = None
    shoe_size: str | None = None
    notifications_enabled: bool = True


class StylePreferencesUpdate(BaseModel):
    style_tags: list[str]
    colour_tags: list[str]
    brands_to_avoid: list[str]

    @field_validator("style_tags")
    @classmethod
    def _check_style_tags(cls, v: list[str]) -> list[str]:
        return _validate_membership(v, STYLE_TAGS, "style_tags")

    @field_validator("colour_tags")
    @classmethod
    def _check_colour_tags(cls, v: list[str]) -> list[str]:
        return _validate_membership(v, COLOUR_TAGS, "colour_tags")

    @field_validator("brands_to_avoid")
    @classmethod
    def _check_brands_to_avoid(cls, v: list[str]) -> list[str]:
        return _validate_brands_to_avoid(v)


class BodySizeUpdate(BaseModel):
    body_shape: str | None = None
    gender: str | None = None
    birth_date: date | None = None
    height: str | None = None
    top_size: str | None = None
    bottom_size: str | None = None
    shoe_size: str | None = None

    @field_validator("body_shape")
    @classmethod
    def _check_body_shape(cls, v: str | None) -> str | None:
        if v is not None and v not in BODY_SHAPES:
            raise ValueError(f"body_shape must be one of {sorted(BODY_SHAPES)} or null")
        return v

    @field_validator("gender")
    @classmethod
    def _check_gender(cls, v: str | None) -> str | None:
        if v is not None and v not in GENDERS:
            raise ValueError(f"gender must be one of {sorted(GENDERS)} or null")
        return v

    @field_validator("top_size")
    @classmethod
    def _check_top_size(cls, v: str | None) -> str | None:
        if v is not None and v not in TOP_SIZES:
            raise ValueError(f"top_size must be one of {sorted(TOP_SIZES)} or null")
        return v

    @field_validator("bottom_size")
    @classmethod
    def _check_bottom_size(cls, v: str | None) -> str | None:
        if v is not None and v not in BOTTOM_SIZES:
            raise ValueError(f"bottom_size must be one of {sorted(BOTTOM_SIZES)} or null")
        return v

    @field_validator("birth_date")
    @classmethod
    def _check_birth_date(cls, v: date | None) -> date | None:
        if v is not None and v > date.today():
            raise ValueError("birth_date must not be in the future")
        return v


class NotificationsUpdate(BaseModel):
    notifications_enabled: bool
