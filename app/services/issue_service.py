from __future__ import annotations

from typing import Any

from app.infrastructure.jira_client import JiraClient
from app.schemas.issue import (
    CreateIssueInput,
    CreateIssueResult,
    DeleteIssuePrepareInput,
    DeleteIssueResult,
    GetIssueInput,
    IssueData,
    JiraIssueType,
    JiraPriority,
    JiraProject,
    JiraStatus,
    JiraUser,
    UpdateIssueInput,
    UpdateIssueResult,
)


class IssueService:
    """
    Business/service layer cho Jira Issue.

    Responsibilities:
    - Validate business input
    - Gọi JiraClient
    - Chuyển Jira API response thành application schema
    - Không xử lý MCP transport
    - Không xử lý HTTP trực tiếp
    """

    def __init__(self, jira_client: JiraClient) -> None:
        self.jira_client = jira_client

    # ========================================================
    # GET ISSUE
    # ========================================================

    async def get_issue(
        self,
        request: GetIssueInput,
    ) -> IssueData:
        """
        Get một Jira issue theo issue key.
        """

        issue_key = request.issue_key.strip().upper()

        if not issue_key:
            raise ValueError("Issue key cannot be empty.")

        params = {}

        if request.expand:
            params["expand"] = ",".join(request.expand)

        result = await self.jira_client.get(
            f"/rest/api/2/issue/{issue_key}",
            params=params,
        )

        return self._map_issue(result)

    # ========================================================
    # CREATE ISSUE
    # ========================================================

    def build_create_payload(
        self,
        request: CreateIssueInput,
    ) -> dict[str, Any]:
        """
        Build the Jira REST API request body from CreateIssueInput.

        Tách riêng khỏi create_issue() để tool `prepare` có thể
        show preview chính xác những gì sẽ gửi lên Jira, mà KHÔNG
        gọi Jira API (đúng nguyên tắc Prepare không side-effect).
        """

        fields: dict[str, Any] = {
            "project": {"key": request.project_key},
            "issuetype": {"name": request.issue_type},
            "summary": request.summary,
        }

        description = self._build_description(request)
        if description:
            fields["description"] = description

        if request.priority:
            fields["priority"] = {"name": request.priority}

        if request.assignee:
            fields["assignee"] = {"name": request.assignee}

        if request.reporter:
            fields["reporter"] = {"name": request.reporter}

        if request.labels:
            fields["labels"] = request.labels

        if request.components:
            fields["components"] = [
                {"name": name} for name in request.components
            ]

        if request.test_environment:
            fields["environment"] = "\n".join(
                request.test_environment
            )

        if request.epic_key:
            fields["customfield_10008"] = request.epic_key
            # NOTE: Epic Link field ID thay đổi theo từng Jira
            # instance. Chỉnh lại "customfield_10008" cho khớp
            # với instance thật (xem qua /rest/api/2/field).

        if request.parent_key:
            fields["parent"] = {"key": request.parent_key}

        if request.custom_fields:
            fields.update(request.custom_fields)

        return {"fields": fields}

    @staticmethod
    def _build_description(request: CreateIssueInput) -> str | None:
        """
        Compose the Jira description field from either a free-form
        description, or the structured bug-report sections (Steps
        to Reproduce / Expected / Actual), matching the
        `jira_bug_report` prompt template (mục 6).
        """

        parts: list[str] = []

        if request.description:
            parts.append(request.description)

        if request.steps_to_reproduce:
            parts.append(
                f"h3. Steps to Reproduce\n{request.steps_to_reproduce}"
            )

        if request.expected_result:
            parts.append(
                f"h3. Expected Result\n{request.expected_result}"
            )

        if request.actual_result:
            parts.append(
                f"h3. Actual Result\n{request.actual_result}"
            )

        if not parts:
            return None

        return "\n\n".join(parts)

    async def create_issue(
        self,
        request: CreateIssueInput,
    ) -> CreateIssueResult:
        """
        Create một Jira issue mới.

        CHỈ được gọi từ bước Execute (sau khi user đã Confirm),
        không bao giờ gọi trực tiếp từ Prepare.
        """

        payload = self.build_create_payload(request)

        result = await self.jira_client.post(
            "/rest/api/2/issue",
            json=payload,
        )

        return CreateIssueResult(
            issue_key=result.get("key", ""),
            issue_id=result.get("id"),
            self_url=result.get("self"),
        )

    # ========================================================
    # UPDATE ISSUE
    # ========================================================

    def build_update_payload(
        self,
        request: UpdateIssueInput,
    ) -> dict[str, Any]:
        """
        Build the Jira REST API PUT body từ UpdateIssueInput.

        Chỉ đưa vào payload những field mà user THỰC SỰ muốn đổi
        (khác None) — tránh vô tình xóa field khác do PUT full
        object. Tách riêng để tool `prepare` show preview mà
        KHÔNG gọi Jira API.
        """

        fields: dict[str, Any] = {}

        if request.summary is not None:
            fields["summary"] = request.summary

        if request.description is not None:
            fields["description"] = request.description

        if request.priority is not None:
            fields["priority"] = {"name": request.priority}

        if request.assignee is not None:
            fields["assignee"] = {"name": request.assignee}

        if request.labels is not None:
            fields["labels"] = request.labels

        if request.components is not None:
            fields["components"] = [
                {"name": name} for name in request.components
            ]

        if request.environment is not None:
            fields["environment"] = request.environment

        if request.custom_fields:
            fields.update(request.custom_fields)

        if not fields:
            raise ValueError(
                "No fields to update — provide at least one field."
            )

        return {"fields": fields}

    async def update_issue(
        self,
        request: UpdateIssueInput,
    ) -> UpdateIssueResult:
        """
        Cập nhật một Jira issue đã tồn tại.

        CHỈ được gọi từ bước Execute (sau khi user đã Confirm).
        Jira REST API trả 204 No Content khi PUT thành công, nên
        JiraClient.put() sẽ trả về None — không có gì để map,
        chỉ cần không raise exception là coi như thành công.
        """

        issue_key = request.issue_key.strip().upper()

        if not issue_key:
            raise ValueError("Issue key cannot be empty.")

        payload = self.build_update_payload(request)

        await self.jira_client.put(
            f"/rest/api/2/issue/{issue_key}",
            json=payload,
        )

        return UpdateIssueResult(
            issue_key=issue_key,
            updated=True,
        )

    # ========================================================
    # DELETE ISSUE
    # ========================================================

    def build_delete_preview(
        self,
        request: DeleteIssuePrepareInput,
    ) -> dict[str, Any]:
        """
        Build preview cho draft xóa issue. KHÔNG gọi Jira API —
        chỉ dùng để show cho user review trước khi confirm.
        """

        return {
            "issue_key": request.issue_key.strip().upper(),
            "reason": request.reason,
            "action": "DELETE (irreversible)",
        }

    async def delete_issue(
        self,
        issue_key: str,
    ) -> DeleteIssueResult:
        """
        Xóa một Jira issue.

        CHỈ được gọi từ bước Execute (sau khi user đã Confirm),
        không bao giờ gọi trực tiếp từ Prepare.
        """

        issue_key = issue_key.strip().upper()

        if not issue_key:
            raise ValueError("Issue key cannot be empty.")

        await self.jira_client.delete(
            f"/rest/api/2/issue/{issue_key}"
        )

        return DeleteIssueResult(
            issue_key=issue_key,
            deleted=True,
        )

    # ========================================================
    # MAPPER
    # ========================================================

    @staticmethod
    def _map_issue(data: dict) -> IssueData:
        """
        Convert raw Jira API response into IssueData.
        """

        fields = data.get("fields") or {}

        project_data = fields.get("project")
        issue_type_data = fields.get("issuetype")
        status_data = fields.get("status")
        priority_data = fields.get("priority")
        assignee_data = fields.get("assignee")
        reporter_data = fields.get("reporter")

        project = None

        if project_data:
            project = JiraProject(
                id=project_data.get("id"),
                key=project_data.get("key", ""),
                name=project_data.get("name"),
            )

        issue_type = None

        if issue_type_data:
            issue_type = JiraIssueType(
                id=issue_type_data.get("id"),
                name=issue_type_data.get("name", ""),
            )

        status = None

        if status_data:
            status = JiraStatus(
                id=status_data.get("id"),
                name=status_data.get("name", ""),
                description=status_data.get("description"),
            )

        priority = None

        if priority_data:
            priority = JiraPriority(
                id=priority_data.get("id"),
                name=priority_data.get("name", ""),
            )

        assignee = None

        if assignee_data:
            assignee = JiraUser(
                account_id=assignee_data.get("accountId"),
                username=assignee_data.get("name"),
                display_name=assignee_data.get("displayName"),
                email=assignee_data.get("emailAddress"),
            )

        reporter = None

        if reporter_data:
            reporter = JiraUser(
                account_id=reporter_data.get("accountId"),
                username=reporter_data.get("name"),
                display_name=reporter_data.get("displayName"),
                email=reporter_data.get("emailAddress"),
            )

        components = [
            component.get("name", "")
            for component in fields.get("components", [])
            if component.get("name")
        ]

        labels = fields.get("labels") or []

        environment = fields.get("environment")

        return IssueData(
            id=data.get("id"),
            key=data.get("key", ""),
            self_url=data.get("self"),
            summary=fields.get("summary", ""),
            description=fields.get("description"),
            project=project,
            issue_type=issue_type,
            status=status,
            priority=priority,
            assignee=assignee,
            reporter=reporter,
            labels=labels,
            components=components,
            environment=environment,
            created=fields.get("created"),
            updated=fields.get("updated"),
            raw_fields=fields,
        )
