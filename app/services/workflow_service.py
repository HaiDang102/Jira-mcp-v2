from __future__ import annotations

from app.infrastructure.jira_client import JiraClient
from app.schemas.workflow import (
    GetTransitionsInput,
    Transition,
    TransitionExecutionResult,
    TransitionIssueInput,
    TransitionResult,
)


class WorkflowService:
    """
    Business/service layer cho Jira workflow.

    Responsibilities:
    - Lấy transition khả dụng
    - Validate transition ID/name
    - Thực hiện transition qua JiraClient
    - Mapping Jira response -> application schema
    - Không xử lý MCP transport

    Confirmation guard vẫn được giữ tạm ở đây cho đến khi
    Safety Layer được tách riêng.
    """

    def __init__(self, jira_client: JiraClient) -> None:
        self.jira_client = jira_client

    async def get_transitions(
        self,
        request: GetTransitionsInput,
    ) -> TransitionResult:
        transition_response = await self.jira_client.get(
            f"/rest/api/2/issue/{request.issue_key}/transitions"
        )

        issue = await self.jira_client.get(
            f"/rest/api/2/issue/{request.issue_key}",
            params={"fields": "status"},
        )

        fields = issue.get("fields") or {}
        status_data = fields.get("status") or {}

        transitions: list[Transition] = []

        for item in transition_response.get("transitions", []):
            to_status = item.get("to") or {}

            transitions.append(
                Transition(
                    id=str(item.get("id", "")),
                    name=item.get("name", ""),
                    to_status=to_status.get("name", ""),
                )
            )

        return TransitionResult(
            issue_key=request.issue_key,
            current_status=status_data.get("name", ""),
            available_transitions=transitions,
        )

    async def transition_issue(
        self,
        request: TransitionIssueInput,
    ) -> TransitionExecutionResult:
        if not request.confirm:
            raise ValueError(
                "Transition requires explicit confirmation."
            )

        transitions_result = await self.get_transitions(
            GetTransitionsInput(
                issue_key=request.issue_key
            )
        )

        selected_transition: Transition | None = None

        for transition in transitions_result.available_transitions:
            if (
                transition.id == request.transition
                or transition.name.casefold()
                == request.transition.casefold()
            ):
                selected_transition = transition
                break

        if selected_transition is None:
            raise ValueError(
                f"Transition '{request.transition}' "
                f"is not available for {request.issue_key}."
            )

        await self.jira_client.post(
            f"/rest/api/2/issue/{request.issue_key}/transitions",
            json={
                "transition": {
                    "id": selected_transition.id
                }
            },
        )

        return TransitionExecutionResult(
            issue_key=request.issue_key,
            transition_id=selected_transition.id,
            transition_name=selected_transition.name,
            to_status=selected_transition.to_status,
            confirmed=True,
        )
