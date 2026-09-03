from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DraftInfo(BaseModel):
    """Kết quả trả về từ bước Prepare."""

    draft_id: str = Field(
        description="Draft identifier. Pass this to the confirm tool."
    )

    operation: str = Field(
        description="The operation this draft will perform when confirmed."
    )

    preview: dict[str, Any] = Field(
        description=(
            "Payload/preview của operation để user review "
            "trước khi confirm."
        )
    )

    expires_in_hours: float = Field(
        default=24.0,
        gt=0,
        description="Draft TTL in hours.",
    )


class ConfirmDraftInput(BaseModel):
    """Input dùng chung cho bước Confirm."""

    model_config = ConfigDict(str_strip_whitespace=True)

    draft_id: str = Field(
        min_length=1,
        description="draft_id returned by the prepare tool.",
    )

    confirm: bool = Field(
        default=False,
        description=(
            "Must be explicitly true before the operation is executed."
        ),
    )
