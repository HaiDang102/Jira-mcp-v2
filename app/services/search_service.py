from __future__ import annotations

from typing import Any

from app.infrastructure.jira_client import JiraClient
from app.schemas.search import SearchInput, SearchResult
from app.services.issue_service import IssueService


class SearchService:
    """
    Business/service layer cho Jira Search.

    Responsibilities:
    - Validate/consume SearchInput
    - Gọi JiraClient
    - Mapping Jira search response
    - Không xử lý MCP transport
    """

    def __init__(self, jira_client: JiraClient) -> None:
        self.jira_client = jira_client

    async def search(
        self,
        request: SearchInput,
    ) -> SearchResult:
        params: dict[str, Any] = {
            "jql": request.jql,
            "startAt": request.start_at,
            "maxResults": request.max_results,
        }

        if request.fields:
            params["fields"] = ",".join(request.fields)

        result = await self.jira_client.get(
            "/rest/api/2/search",
            params=params,
        )

        issues = [
            IssueService.map_issue(issue)
            for issue in result.get("issues", [])
        ]

        return SearchResult(
            total=result.get("total", 0),
            start_at=result.get(
                "startAt",
                request.start_at,
            ),
            max_results=result.get(
                "maxResults",
                request.max_results,
            ),
            issues=issues,
        )
