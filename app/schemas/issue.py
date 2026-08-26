from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, ConfigDict


# ============================================================
# JIRA USER
# ============================================================

class JiraUser(BaseModel):
    """
    Thông tin user Jira tối thiểu cần dùng trong MCP.
    """

    model_config = ConfigDict(extra="allow")

    account_id: str | None = None
    username: str | None = None
    display_name: str | None = None
    email: str | None = None


# ============================================================
# JIRA STATUS
# ============================================================

class JiraStatus(BaseModel):
    """
    Trạng thái hiện tại của Jira issue.
    """

    model_config = ConfigDict(extra="allow")

    id: str | None = None
    name: str
    description: str | None = None


# ============================================================
# JIRA PRIORITY
# ============================================================

class JiraPriority(BaseModel):
    """
    Priority của Jira issue.
    """

    model_config = ConfigDict(extra="allow")

    id: str | None = None
    name: str


# ============================================================
# JIRA ISSUE TYPE
# ============================================================

class JiraIssueType(BaseModel):
    """
    Loại Jira issue: Bug, Task, Story...
    """

    model_config = ConfigDict(extra="allow")

    id: str | None = None
    name: str


# ============================================================
# JIRA PROJECT
# ============================================================

class JiraProject(BaseModel):
    """
    Thông tin project của issue.
    """

    model_config = ConfigDict(extra="allow")

    id: str | None = None
    key: str
    name: str | None = None


# ============================================================
# ISSUE DATA
# ============================================================

class IssueData(BaseModel):
    """
    Dữ liệu Jira Issue được chuẩn hóa để trả về MCP.
    """

    model_config = ConfigDict(extra="allow")

    id: str | None = None

    key: str

    self_url: str | None = Field(
        default=None,
        description="Jira REST API URL of the issue.",
    )

    summary: str

    description: str | None = None

    project: JiraProject | None = None

    issue_type: JiraIssueType | None = None

    status: JiraStatus | None = None

    priority: JiraPriority | None = None

    assignee: JiraUser | None = None

    reporter: JiraUser | None = None

    labels: list[str] = Field(
        default_factory=list
    )

    components: list[str] = Field(
        default_factory=list
    )

    environment: str | None = None

    created: str | None = None

    updated: str | None = None

    raw_fields: dict[str, Any] = Field(
        default_factory=dict,
        description="Original Jira fields when required.",
    )


# ============================================================
# GET ISSUE INPUT
# ============================================================

class GetIssueInput(BaseModel):
    """
    Input cho jira_get_issue.
    """

    issue_key: str = Field(
        min_length=1,
        description="Jira issue key, for example SP-123.",
    )

    expand: list[str] = Field(
        default_factory=list,
        description="Optional Jira expansion parameters.",
    )


# ============================================================
# CREATE ISSUE INPUT
# ============================================================

class CreateIssueInput(BaseModel):
    """
    Input chuẩn để tạo Jira issue.

    Đây là input ở application layer.
    Không chứa HTTP-specific details.
    """

    project_key: str = Field(
        default="SP",
        min_length=1,
        max_length=20,
    )

    issue_type: str = Field(
        default="Bug",
        min_length=1,
        max_length=100,
    )

    summary: str = Field(
        min_length=1,
        max_length=255,
    )

    description: str | None = None

    steps_to_reproduce: str | None = None

    expected_result: str | None = None

    actual_result: str | None = None

    test_environment: list[str] = Field(
        default_factory=list
    )

    priority: str | None = None

    assignee: str | None = None

    reporter: str | None = None

    labels: list[str] = Field(
        default_factory=list
    )

    components: list[str] = Field(
        default_factory=list
    )

    epic_key: str | None = None

    parent_key: str | None = None

    custom_fields: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional Jira custom fields.",
    )


# ============================================================
# UPDATE ISSUE INPUT
# ============================================================

class UpdateIssueInput(BaseModel):
    """
    Input chuẩn để cập nhật Jira issue.
    """

    issue_key: str = Field(
        min_length=1,
    )

    summary: str | None = Field(
        default=None,
        max_length=255,
    )

    description: str | None = None

    priority: str | None = None

    assignee: str | None = None

    labels: list[str] | None = None

    components: list[str] | None = None

    environment: str | None = None

    custom_fields: dict[str, Any] | None = None


# ============================================================
# CREATE ISSUE RESULT
# ============================================================

class CreateIssueResult(BaseModel):
    """
    Kết quả sau khi Jira tạo issue thành công.
    """

    issue_key: str

    issue_id: str | None = None

    self_url: str | None = None


# ============================================================
# UPDATE ISSUE RESULT
# ============================================================

class UpdateIssueResult(BaseModel):
    """
    Kết quả sau khi Jira update issue thành công.
    """

    issue_key: str

    updated: bool = True
# ============================================================
# DELETE ISSUE — PREPARE
# ============================================================

class DeleteIssuePrepareInput(BaseModel):
    """
    Input cho jira_delete_issue_prepare.

    Delete là DESTRUCTIVE operation — bắt buộc phải có `reason`
    ngay từ bước Prepare (mục 7: "DESTRUCTIVE — xóa, cần confirm
    + lý do"). Bước Prepare KHÔNG có field `confirm`; confirm chỉ
    xảy ra ở bước riêng (ConfirmDraftInput), giống create_issue.
    """

    issue_key: str = Field(
        min_length=1,
        description="Jira issue key sẽ bị xóa, ví dụ SP-123.",
    )

    reason: str = Field(
        min_length=5,
        max_length=500,
        description=(
            "Lý do xóa issue — bắt buộc, dùng để ghi vào draft "
            "preview và audit trail."
        ),
    )


# ============================================================
# DELETE ISSUE RESULT
# ============================================================

class DeleteIssueResult(BaseModel):
    """
    Kết quả sau khi Jira xóa issue thành công.
    """

    issue_key: str

    deleted: bool = True

    reason: str | None = None