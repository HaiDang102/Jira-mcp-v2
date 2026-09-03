from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


# ============================================================
# JIRA READ MODELS
# ============================================================


class JiraUser(BaseModel):
    model_config = ConfigDict(extra="allow")

    account_id: str | None = None
    username: str | None = None
    display_name: str | None = None
    email: str | None = None


class JiraStatus(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str | None = None
    name: str
    description: str | None = None


class JiraPriority(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str | None = None
    name: str


class JiraIssueType(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str | None = None
    name: str


class JiraProject(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str | None = None
    key: str
    name: str | None = None


class IssueData(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str | None = None
    key: str
    self_url: str | None = None

    summary: str
    description: str | None = None

    project: JiraProject | None = None
    issue_type: JiraIssueType | None = None
    status: JiraStatus | None = None
    priority: JiraPriority | None = None
    assignee: JiraUser | None = None
    reporter: JiraUser | None = None

    labels: list[str] = Field(default_factory=list)
    components: list[str] = Field(default_factory=list)

    environment: str | None = None
    created: str | None = None
    updated: str | None = None
    due_date: str | None = None

    raw_fields: dict[str, Any] = Field(default_factory=dict)


# ============================================================
# INPUT MODELS
# ============================================================


class GetIssueInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    issue_key: str = Field(min_length=1)
    expand: list[str] = Field(default_factory=list)

    @field_validator("issue_key")
    @classmethod
    def normalize_issue_key(cls, value: str) -> str:
        return value.upper()


class CreateIssueInput(BaseModel):
    """
    Rich create-issue schema.

    For issue_type=Bug, the QA fields below are validated so the MCP
    does not create a vague one-line bug report.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    project_key: str = Field(default="SP", min_length=1, max_length=20)
    issue_type: str = Field(default="Bug", min_length=1, max_length=100)
    summary: str = Field(min_length=5, max_length=255)

    # QA bug content
    error_description: str | None = Field(
        default=None,
        description="Mô tả lỗi / bối cảnh nghiệp vụ.",
    )
    steps_to_reproduce: list[str] = Field(
        default_factory=list,
        description="Các bước tái hiện lỗi theo thứ tự.",
    )
    actual_result: str | None = None
    expected_result: str | None = None
    evidence: str | None = Field(
        default=None,
        description="Hồ sơ, ảnh, log, link hoặc dữ liệu minh chứng.",
    )

    # People
    assignee: str | None = Field(
        default=None,
        description="Jira username của người xử lý.",
    )
    reporter: str | None = Field(
        default=None,
        description="Jira username của reporter nếu Jira cho phép set.",
    )

    # Dates
    start_date: date | None = Field(
        default=None,
        description="Ngày bắt đầu. Jira custom field ID cấu hình trong .env.",
    )
    due_date: date | None = Field(
        default=None,
        description="Jira standard Due Date (duedate).",
    )

    # Classification
    priority: str | None = Field(default="Medium")
    labels: list[str] = Field(default_factory=list)
    components: list[str] = Field(default_factory=list)
    epic_key: str | None = Field(
        default=None,
        description="Epic Link. Custom field ID cấu hình trong .env.",
    )

    # Environment / technical
    environment: str | None = None
    test_environment: list[str] = Field(default_factory=list)

    custom_fields: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional Jira fields, normally customfield_xxxxx keys.",
    )

    @field_validator("project_key")
    @classmethod
    def normalize_project_key(cls, value: str) -> str:
        return value.upper()

    @field_validator("epic_key")
    @classmethod
    def normalize_epic_key(cls, value: str | None) -> str | None:
        return value.upper() if value else value

    @field_validator("labels")
    @classmethod
    def normalize_labels(cls, values: list[str]) -> list[str]:
        # preserve order while removing empty/duplicate labels
        seen: set[str] = set()
        result: list[str] = []
        for item in values:
            value = item.strip()
            if value and value not in seen:
                seen.add(value)
                result.append(value)
        return result

    @field_validator("steps_to_reproduce")
    @classmethod
    def normalize_steps(cls, values: list[str]) -> list[str]:
        return [item.strip() for item in values if item and item.strip()]

    @model_validator(mode="after")
    def validate_bug_completeness(self):
        if self.issue_type.casefold() != "bug":
            return self

        missing: list[str] = []

        if not self.error_description:
            missing.append("error_description")
        if not self.steps_to_reproduce:
            missing.append("steps_to_reproduce")
        if not self.actual_result:
            missing.append("actual_result")
        if not self.expected_result:
            missing.append("expected_result")

        if missing:
            raise ValueError(
                "Bug report is incomplete. Missing required QA fields: "
                + ", ".join(missing)
            )

        return self


class UpdateIssueInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    issue_key: str = Field(min_length=1)
    summary: str | None = Field(default=None, max_length=255)
    description: str | None = None
    priority: str | None = None
    assignee: str | None = None
    labels: list[str] | None = None
    components: list[str] | None = None
    environment: str | None = None
    due_date: date | None = None
    custom_fields: dict[str, Any] | None = None

    @field_validator("issue_key")
    @classmethod
    def normalize_issue_key(cls, value: str) -> str:
        return value.upper()


class DeleteIssuePrepareInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    issue_key: str = Field(min_length=1)
    reason: str = Field(min_length=5, max_length=500)

    @field_validator("issue_key")
    @classmethod
    def normalize_issue_key(cls, value: str) -> str:
        return value.upper()


# ============================================================
# RESULT MODELS
# ============================================================


class CreateIssueResult(BaseModel):
    issue_key: str
    issue_id: str | None = None
    self_url: str | None = None


class UpdateIssueResult(BaseModel):
    issue_key: str
    updated: bool = True


class DeleteIssueResult(BaseModel):
    issue_key: str
    deleted: bool = True
    reason: str | None = None
