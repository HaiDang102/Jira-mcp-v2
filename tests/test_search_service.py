import asyncio

from app.infrastructure.jira_client import create_jira_client
from app.schemas.search import SearchInput
from app.services.search_service import SearchService


async def main():
    client = create_jira_client()

    try:
        service = SearchService(client)

        result = await service.search(
            SearchInput(
                jql="project = SP ORDER BY created DESC",
                max_results=5,
                start_at=0,
            )
        )

        print("SEARCH SERVICE: OK")
        print("TOTAL:", result.total)
        print("START AT:", result.start_at)
        print("MAX RESULTS:", result.max_results)

        for issue in result.issues:
            print(f"- {issue.key}: {issue.summary}")

    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())