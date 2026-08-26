from __future__ import annotations

from typing import Any

from app.infrastructure.jira_client import JiraClient
from app.schemas.workflow import (
    GetTransitionsInput,
    Transition,
    TransitionIssueInput,
    TransitionResult,
)


class WorkflowService:
    """
    Business/service layer cho Jira workflow.

    Responsibilities:
    - Lấy các transition khả dụng của issue
    - Thực hiện transition
    - Mapping Jira API response -> application schema
    - Không xử lý MCP transport
    - Không xử lý HTTP trực tiếp
    """

    def __init__(self, jira_client: JiraClient) -> None:
        self.jira_client = jira_client

    # ========================================================
    # GET TRANSITIONS
    # ========================================================

    async def get_transitions(
        self,
        request: GetTransitionsInput,
    ) -> TransitionResult:
        """
        Lấy danh sách transition mà Jira cho phép
        thực hiện đối với issue.
        """

        issue_key = request.issue_key.strip().upper()

        if not issue_key:
            raise ValueError("Issue key cannot be empty.")

        result = await self.jira_client.get(
            f"/rest/api/2/issue/{issue_key}/transitions"
        )

        # ----------------------------------------------------
        # Lấy trạng thái hiện tại
        # ----------------------------------------------------

        issue = await self.jira_client.get(
            f"/rest/api/2/issue/{issue_key}",
            params={
                "fields": "status",
            },
        )

        fields = issue.get("fields") or {}
        status_data = fields.get("status") or {}

        current_status = status_data.get("name", "")

        # ----------------------------------------------------
        # Mapping transitions
        # ----------------------------------------------------

        transitions: list[Transition] = []

        for item in result.get("transitions", []):
            to_status = item.get("to") or {}

            transitions.append(
                Transition(
                    id=str(item.get("id", "")),
                    name=item.get("name", ""),
                    to_status=to_status.get("name", ""),
                )
            )

        return TransitionResult(
            issue_key=issue_key,
            current_status=current_status,
            available_transitions=transitions,
        )

    # ========================================================
    # EXECUTE TRANSITION
    # ========================================================

    async def transition_issue(
        self,
        request: TransitionIssueInput,
    ) -> dict[str, Any]:
        """
        Thực hiện Jira workflow transition.

        Đây là destructive/write operation.
        Bắt buộc confirm=True.
        """

        issue_key = request.issue_key.strip().upper()

        if not issue_key:
            raise ValueError("Issue key cannot be empty.")

        if not request.confirm:
            raise ValueError(
                "Transition requires explicit confirmation."
            )

        transition_value = request.transition.strip()

        if not transition_value:
            raise ValueError(
                "Transition cannot be empty."
            )

        # ----------------------------------------------------
        # Tìm transition theo ID hoặc name
        # ----------------------------------------------------

        transitions_result = await self.get_transitions(
            GetTransitionsInput(
                issue_key=issue_key
            )
        )

        selected_transition = None

        for transition in transitions_result.available_transitions:
            if (
                transition.id == transition_value
                or transition.name.lower()
                == transition_value.lower()
            ):
                selected_transition = transition
                break

        if selected_transition is None:
            raise ValueError(
                f"Transition '{transition_value}' "
                f"is not available for {issue_key}."
            )

        # ----------------------------------------------------
        # Execute Jira transition
        # ----------------------------------------------------

        await self.jira_client.post(
            f"/rest/api/2/issue/{issue_key}/transitions",
            json={
                "transition": {
                    "id": selected_transition.id
                }
            },
        )

        return {
            "issue_key": issue_key,
            "transition_id": selected_transition.id,
            "transition_name": selected_transition.name,
            "to_status": selected_transition.to_status,
            "confirmed": True,
        }