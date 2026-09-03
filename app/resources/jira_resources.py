from __future__ import annotations

"""
MCP Resources — read-only Jira data exposed via jira:// URIs.

Resources are registered explicitly through register_jira_resources(mcp)
to avoid circular imports with app.server.
"""

from mcp.server.mcpserver import MCPServer

from app.infrastructure.jira_client import create_jira_client


def _client():
    """
    Create a Jira client using the application's standard configuration.

    Resources are read-only. A client is created per resource call and
    closed immediately after use.
    """
    return create_jira_client()


def register_jira_resources(mcp: MCPServer) -> None:
    """Register all Jira MCP resources."""

    @mcp.resource("jira://project/{key}")
    async def get_project(key: str) -> dict:
        """Thông tin project, ví dụ: jira://project/SP."""
        client = _client()
        try:
            return await client.get(f"/rest/api/2/project/{key}")
        finally:
            await client.close()

    @mcp.resource("jira://project/{key}/fields")
    async def get_project_fields(key: str) -> dict:
        """
        Metadata field dùng khi tạo issue của project.

        Ví dụ:
            jira://project/SP/fields
        """
        client = _client()
        try:
            return await client.get(
                "/rest/api/2/issue/createmeta",
                params={
                    "projectKeys": key,
                    "expand": "projects.issuetypes.fields",
                },
            )
        finally:
            await client.close()

    @mcp.resource("jira://issue/{issue_key}")
    async def get_issue_detail(issue_key: str) -> dict:
        """Chi tiết issue, ví dụ: jira://issue/SP-123."""
        client = _client()
        try:
            return await client.get(
                f"/rest/api/2/issue/{issue_key}"
            )
        finally:
            await client.close()

    @mcp.resource("jira://issue/{issue_key}/comments")
    async def get_issue_comments(issue_key: str) -> dict:
        """Danh sách comment của issue."""
        client = _client()
        try:
            return await client.get(
                f"/rest/api/2/issue/{issue_key}/comment"
            )
        finally:
            await client.close()

    @mcp.resource("jira://issue/{issue_key}/changelog")
    async def get_issue_changelog(issue_key: str) -> dict:
        """Lịch sử thay đổi của issue."""
        client = _client()
        try:
            return await client.get(
                f"/rest/api/2/issue/{issue_key}",
                params={"expand": "changelog"},
            )
        finally:
            await client.close()

    @mcp.resource("jira://project/{key}/workflow")
    async def get_project_workflow(key: str) -> dict:
        """
        Danh sách status theo issue type của project.

        Jira Server/Data Center không có một REST endpoint đơn giản
        trả về toàn bộ workflow của project, nên endpoint statuses
        được dùng như một read-only representation phù hợp.
        """
        client = _client()
        try:
            return await client.get(
                f"/rest/api/2/project/{key}/statuses"
            )
        finally:
            await client.close()

    @mcp.resource("jira://me")
    async def get_current_user() -> dict:
        """Thông tin Jira user hiện tại."""
        client = _client()
        try:
            return await client.get("/rest/api/2/myself")
        finally:
            await client.close()
