from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.issue import IssueData


# ============================================================
# SEARCH INPUT
# ============================================================

class SearchInput(BaseModel):
    """
    Input cho Jira JQL search.
    """

    jql: str = Field(
        min_length=1,
        description="Jira Query Language (JQL)."
    )

    max_results: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Maximum number of issues to return."
    )

    start_at: int = Field(
        default=0,
        ge=0,
        description="Pagination offset."
    )

    fields: list[str] = Field(
        default_factory=list,
        description="Optional list of Jira fields."
    )


# ============================================================
# SEARCH RESULT
# ============================================================

class SearchResult(BaseModel):
    """
    Chuẩn hóa kết quả search từ Jira.
    """

    total: int

    start_at: int

    max_results: int

    issues: list[IssueData] = Field(
        default_factory=list
    )