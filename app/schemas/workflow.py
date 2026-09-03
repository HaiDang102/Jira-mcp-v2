from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Transition(BaseModel):
    """Một transition mà Jira cho phép thực hiện."""

    id: str
    name: str
    to_status: str


class GetTransitionsInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    issue_key: str = Field(min_length=1)

    @field_validator("issue_key")
    @classmethod
    def normalize_issue_key(cls, value: str) -> str:
        return value.upper()


class TransitionResult(BaseModel):
    """Kết quả READ danh sách transitions hiện có."""

    issue_key: str
    current_status: str
    available_transitions: list[Transition] = Field(
        default_factory=list
    )


class TransitionIssueInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    issue_key: str = Field(min_length=1)

    transition: str = Field(
        min_length=1,
        description="Transition name or ID."
    )

    confirm: bool = Field(
        default=False,
        description="Explicit confirmation before changing workflow."
    )

    @field_validator("issue_key")
    @classmethod
    def normalize_issue_key(cls, value: str) -> str:
        return value.upper()


class TransitionExecutionResult(BaseModel):
    """Kết quả sau khi transition được thực hiện thành công."""

    issue_key: str
    transition_id: str
    transition_name: str
    to_status: str
    confirmed: bool = True
