from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class DraftInfo(BaseModel):
    """
    Kết quả trả về từ bước Prepare (mục 4 — bước 1).

    Dùng chung cho mọi WRITE/DESTRUCTIVE operation, không chỉ
    riêng jira_create_issue.
    """

    draft_id: str = Field(
        description="Draft identifier. Pass this to the confirm tool."
    )

    operation: str = Field(
        description="The operation this draft will perform when confirmed."
    )

    preview: dict[str, Any] = Field(
        description=(
            "Exact payload that will be sent to Jira when confirmed. "
            "Show this to the user for review before confirming."
        )
    )

    expires_in_hours: float = Field(
        default=24.0,
        description="Draft TTL. After this, the draft must be re-prepared.",
    )


class ConfirmDraftInput(BaseModel):
    """
    Input chuẩn cho bước Confirm (mục 4 — bước 3).

    Dùng chung cho mọi WRITE/DESTRUCTIVE operation dựa trên draft.
    """

    draft_id: str = Field(
        min_length=1,
        description="The draft_id returned by the corresponding prepare tool.",
    )

    confirm: bool = Field(
        default=False,
        description=(
            "Must be explicitly set to true to execute the operation. "
            "If false, the operation is not performed."
        ),
    )