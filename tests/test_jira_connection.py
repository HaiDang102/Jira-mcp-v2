import asyncio

from app.infrastructure.jira_client import create_jira_client


async def main():
    client = create_jira_client()

    try:
        result = await client.get("/rest/api/2/myself")

        print("JIRA CONNECTION: OK")
        print("USER:", result.get("displayName"))
        print("USERNAME:", result.get("name"))

    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())