from __future__ import annotations

import asyncio

from app.infrastructure.jira_client import create_jira_client
from app.schemas.workflow import (
    GetTransitionsInput,
    TransitionIssueInput,
)
from app.services.workflow_service import WorkflowService


# ============================================================
# TEST GET TRANSITIONS
# ============================================================

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
                issue_key="SP-423"
            )
        )

        print("WORKFLOW SERVICE: OK")
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

async def test_transition_requires_confirmation():
    """
    Test safety:

    confirm=False
    => không được phép thực hiện transition.

    Test này KHÔNG gọi Jira POST nếu WorkflowService
    được thiết kế đúng theo nguyên tắc confirmation.
    """

    client = create_jira_client()

    try:
        service = WorkflowService(client)

        try:
            await service.transition_issue(
                TransitionIssueInput(
                    issue_key="SP-416",
                    transition="81",
                    confirm=False,
                )
            )

        except ValueError as exc:
            print("CONFIRMATION SAFETY: OK")
            print("ERROR:", exc)

        else:
            print(
                "WARNING: transition_issue() "
                "did not reject confirm=False"
            )

    finally:
        await client.close()


# ============================================================
# MAIN
# ============================================================

async def main():
    await test_get_transitions()
    print()
    await test_transition_requires_confirmation()


if __name__ == "__main__":
    asyncio.run(main())