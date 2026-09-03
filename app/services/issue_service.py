from __future__ import annotations

from typing import Any

from app.config import settings
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
    Business/service layer for Jira issues.

    The service builds Jira payloads, executes Jira requests and maps
    responses. Draft/confirmation/idempotency stay outside this class.
    """

    def __init__(self, jira_client: JiraClient) -> None:
        self.jira_client = jira_client

    # ========================================================
    # GET
    # ========================================================

    async def get_issue(self, request: GetIssueInput) -> IssueData:
        params: dict[str, Any] = {}
        if request.expand:
            params["expand"] = ",".join(request.expand)

        result = await self.jira_client.get(
            f"/rest/api/2/issue/{request.issue_key}",
            params=params,
        )
        return self.map_issue(result)

    # ========================================================
    # CREATE
    # ========================================================

    def build_create_payload(
        self,
        request: CreateIssueInput,
    ) -> dict[str, Any]:
        fields: dict[str, Any] = {
            "project": {"key": request.project_key},
            "issuetype": {"name": request.issue_type},
            "summary": request.summary,
        }

        description = self._build_bug_description(request)
        if description:
            fields["description"] = description

        if request.priority:
            fields["priority"] = {"name": request.priority}

        if request.assignee:
            # Jira Server/Data Center typically uses username via "name".
            fields["assignee"] = {"name": request.assignee}

        if request.reporter:
            fields["reporter"] = {"name": request.reporter}

        if request.labels:
            fields["labels"] = request.labels

        if request.components:
            fields["components"] = [
                {"name": name} for name in request.components
            ]

        environment_parts: list[str] = []
        if request.environment:
            environment_parts.append(request.environment)
        if request.test_environment:
            environment_parts.append(
                "Test environment: " + ", ".join(request.test_environment)
            )
        if environment_parts:
            fields["environment"] = "\n".join(environment_parts)

        if request.due_date:
            fields["duedate"] = request.due_date.isoformat()

        if request.start_date:
            field_id = settings.jira_start_date_field_id
            if not field_id:
                raise ValueError(
                    "start_date was provided but "
                    "JIRA_START_DATE_FIELD_ID is not configured in .env."
                )
            fields[field_id] = request.start_date.isoformat()

        if request.epic_key:
            field_id = settings.jira_epic_link_field_id
            if not field_id:
                raise ValueError(
                    "epic_key was provided but "
                    "JIRA_EPIC_LINK_FIELD_ID is not configured in .env."
                )
            fields[field_id] = request.epic_key

        if request.custom_fields:
            fields.update(request.custom_fields)

        return {"fields": fields}

    @staticmethod
    def _build_bug_description(
        request: CreateIssueInput,
    ) -> str | None:
        """
        Build a complete QA-style description using Jira wiki markup.
        """

        if request.issue_type.casefold() != "bug":
            return request.error_description

        lines: list[str] = []

        lines.extend([
            "h3. Mô tả lỗi",
            request.error_description or "",
            "",
            "h3. Các bước tái hiện lỗi",
        ])

        for index, step in enumerate(
            request.steps_to_reproduce,
            start=1,
        ):
            lines.append(f"{index}. {step}")

        lines.extend([
            "",
            "h3. Kết quả thực tế",
            request.actual_result or "",
            "",
            "h3. Kết quả mong đợi",
            request.expected_result or "",
        ])

        if request.evidence:
            lines.extend([
                "",
                "h3. Minh chứng",
                request.evidence,
            ])

        lines.extend([
            "",
            "h3. Thông tin bổ sung",
            f"*Priority:* {request.priority or '(chưa chỉ định)'}",
            (
                "*Labels:* "
                + (", ".join(request.labels) if request.labels else "(không có)")
            ),
            f"*Assignee:* {request.assignee or '(chưa chỉ định)'}",
            (
                "*Start Date:* "
                + (
                    request.start_date.isoformat()
                    if request.start_date
                    else "(chưa chỉ định)"
                )
            ),
            (
                "*Due Date:* "
                + (
                    request.due_date.isoformat()
                    if request.due_date
                    else "(chưa chỉ định)"
                )
            ),
            f"*Epic Link:* {request.epic_key or '(không có)'}",
        ])

        if request.environment or request.test_environment:
            env_parts: list[str] = []
            if request.environment:
                env_parts.append(request.environment)
            if request.test_environment:
                env_parts.append(", ".join(request.test_environment))
            lines.append("*Environment:* " + " | ".join(env_parts))

        return "\n".join(lines).strip()

    async def create_issue(
        self,
        request: CreateIssueInput,
    ) -> CreateIssueResult:
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
    # UPDATE
    # ========================================================

    def build_update_payload(
        self,
        request: UpdateIssueInput,
    ) -> dict[str, Any]:
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
        if request.due_date is not None:
            fields["duedate"] = request.due_date.isoformat()
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
        payload = self.build_update_payload(request)

        await self.jira_client.put(
            f"/rest/api/2/issue/{request.issue_key}",
            json=payload,
        )

        return UpdateIssueResult(
            issue_key=request.issue_key,
            updated=True,
        )

    # ========================================================
    # DELETE
    # ========================================================

    def build_delete_preview(
        self,
        request: DeleteIssuePrepareInput,
    ) -> dict[str, Any]:
        return {
            "issue_key": request.issue_key,
            "reason": request.reason,
            "action": "DELETE (irreversible)",
        }

    async def delete_issue(
        self,
        issue_key: str,
    ) -> DeleteIssueResult:
        normalized_key = issue_key.strip().upper()
        if not normalized_key:
            raise ValueError("Issue key cannot be empty.")

        await self.jira_client.delete(
            f"/rest/api/2/issue/{normalized_key}"
        )

        return DeleteIssueResult(
            issue_key=normalized_key,
            deleted=True,
        )

    # ========================================================
    # MAPPER
    # ========================================================

    @staticmethod
    def map_issue(data: dict[str, Any]) -> IssueData:
        fields = data.get("fields") or {}

        project_data = fields.get("project")
        issue_type_data = fields.get("issuetype")
        status_data = fields.get("status")
        priority_data = fields.get("priority")
        assignee_data = fields.get("assignee")
        reporter_data = fields.get("reporter")

        project = (
            JiraProject(
                id=project_data.get("id"),
                key=project_data.get("key", ""),
                name=project_data.get("name"),
            )
            if project_data
            else None
        )

        issue_type = (
            JiraIssueType(
                id=issue_type_data.get("id"),
                name=issue_type_data.get("name", ""),
            )
            if issue_type_data
            else None
        )

        status = (
            JiraStatus(
                id=status_data.get("id"),
                name=status_data.get("name", ""),
                description=status_data.get("description"),
            )
            if status_data
            else None
        )

        priority = (
            JiraPriority(
                id=priority_data.get("id"),
                name=priority_data.get("name", ""),
            )
            if priority_data
            else None
        )

        assignee = (
            JiraUser(
                account_id=assignee_data.get("accountId"),
                username=assignee_data.get("name"),
                display_name=assignee_data.get("displayName"),
                email=assignee_data.get("emailAddress"),
            )
            if assignee_data
            else None
        )

        reporter = (
            JiraUser(
                account_id=reporter_data.get("accountId"),
                username=reporter_data.get("name"),
                display_name=reporter_data.get("displayName"),
                email=reporter_data.get("emailAddress"),
            )
            if reporter_data
            else None
        )

        components = [
            component.get("name", "")
            for component in fields.get("components", [])
            if component.get("name")
        ]

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
            labels=fields.get("labels") or [],
            components=components,
            environment=fields.get("environment"),
            created=fields.get("created"),
            updated=fields.get("updated"),
            due_date=fields.get("duedate"),
            raw_fields=fields,
        )
