from __future__ import annotations

import pytest

from app.infrastructure.jira_client import create_jira_client
from app.schemas.workflow import (
    GetTransitionsInput,
    TransitionIssueInput,
)
from app.services.workflow_service import WorkflowService


# ============================================================
# TEST GET TRANSITIONS
# ============================================================


@pytest.mark.asyncio
async def test_get_transitions():
    """
    Test đọc danh sách workflow transitions của Jira issue.

    Đây là READ operation nên không thay đổi dữ liệu Jira.
    """

    client = create_jira_client()

    try:
        service = WorkflowService(client)

        result = await service.get_transitions(
            GetTransitionsInput(
                issue_key="SP-423",
            )
        )

        # Basic assertions
        assert result is not None
        assert result.issue_key == "SP-423"
        assert result.current_status is not None
        assert result.available_transitions is not None

        print("\nWORKFLOW SERVICE: OK")
        print("ISSUE:", result.issue_key)
        print("CURRENT STATUS:", result.current_status)

        print("AVAILABLE TRANSITIONS:")

        for transition in result.available_transitions:
            print(
                f"- ID={transition.id} "
                f"| NAME={transition.name} "
                f"| TO={transition.to_status}"
            )

    finally:
        await client.close()


# ============================================================
# TEST CONFIRMATION SAFETY
# ============================================================


@pytest.mark.asyncio
async def test_transition_requires_confirmation():
    """
    Test safety:

    confirm=False
    => WorkflowService phải từ chối transition.

    Test này không được thực hiện Jira transition.
    """

    client = create_jira_client()

    try:
        service = WorkflowService(client)

        with pytest.raises(ValueError) as exc_info:
            await service.transition_issue(
                TransitionIssueInput(
                    issue_key="SP-416",
                    transition="81",
                    confirm=False,
                )
            )

        assert str(exc_info.value)

        print("\nCONFIRMATION SAFETY: OK")
        print("ERROR:", exc_info.value)

    finally:
        await client.close()