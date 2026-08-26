import asyncio

from app.infrastructure.jira_client import create_jira_client
from app.schemas.issue import GetIssueInput
from app.services.issue_service import IssueService


async def main():
    client = create_jira_client()

    try:
        service = IssueService(client)

        result = await service.get_issue(
            GetIssueInput(
                issue_key="SP-423"
            )
        )

        print("ISSUE SERVICE: OK")
        print("KEY:", result.key)
        print("SUMMARY:", result.summary)

        if result.status:
            print("STATUS:", result.status.name)

        if result.priority:
            print("PRIORITY:", result.priority.name)

    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())