"""Validated configuration for the deliberately narrow first flow."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.constants import FIXTURE_URLS, PRODUCT_FIELDS, SOURCE_URL


class JobCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    seed_url: str = SOURCE_URL
    page_limit: Literal[1] = 1
    selected_fields: list[str] = Field(
        default_factory=lambda: list(PRODUCT_FIELDS), min_length=1, max_length=6,
    )

    @field_validator("seed_url")
    @classmethod
    def owned_fixture_only(cls, value: str) -> str:
        if value not in FIXTURE_URLS:
            raise ValueError("Select one of the server-owned catalog fixture URLs")
        return value

    @field_validator("selected_fields")
    @classmethod
    def supported_fields(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)) or any(item not in PRODUCT_FIELDS for item in value):
            raise ValueError("Select unique fields from the supported product fields")
        return [item for item in PRODUCT_FIELDS if item in value]
