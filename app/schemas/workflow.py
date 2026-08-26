from __future__ import annotations

from pydantic import BaseModel, Field


# ============================================================
# TRANSITION
# ============================================================

class Transition(BaseModel):
    """
    Một transition mà Jira cho phép thực hiện.
    """

    id: str

    name: str

    to_status: str


# ============================================================
# GET TRANSITIONS INPUT
# ============================================================

class GetTransitionsInput(BaseModel):

    issue_key: str = Field(
        min_length=1
    )


# ============================================================
# GET TRANSITIONS RESULT
# ============================================================

class TransitionResult(BaseModel):

    issue_key: str

    current_status: str

    available_transitions: list[Transition] = Field(
        default_factory=list
    )


# ============================================================
# TRANSITION ISSUE INPUT
# ============================================================

class TransitionIssueInput(BaseModel):

    issue_key: str = Field(
        min_length=1
    )

    transition: str = Field(
        min_length=1,
        description="Transition name or ID."
    )

    confirm: bool = Field(
        default=False,
        description="Explicit confirmation before changing workflow."
    )