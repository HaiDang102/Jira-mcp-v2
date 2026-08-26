from __future__ import annotations

"""
MCP Resources — read-only data exposed via jira:// URIs.

Resources are always safe (READ-only): no confirmation flow needed.
They call JiraClient directly since there's no business logic here,
just data retrieval + light shaping.

IMPORTANT: this module must be imported by app/server.py BEFORE the
server starts / before `list_resources()` is called, otherwise the
@mcp.resource decorators never run and the resource count stays 0.
Add near your other imports in server.py:

    from app.resources import jira_resources  # noqa: F401  (registers resources)
"""

from app.server import mcp
from app.infrastructure.jira_client import create_jira_client


def _client():
    # Reuses the same construction path as the rest of the app.
    # If you already keep a single shared JiraClient instance on app
    # startup (e.g. in server.py's lifespan), swap this for that
    # shared instance instead of creating a new one per call.
    return create_jira_client()


@mcp.resource("jira://project/{key}")
async def get_project(key: str) -> dict:
    """Thông tin project (jira://project/SP)."""
    client = _client()
    try:
        return await client.get(f"/rest/api/2/project/{key}")
    finally:
        await client.close()


@mcp.resource("jira://project/{key}/fields")
async def get_project_fields(key: str) -> dict:
    """Danh sách fields của project (jira://project/SP/fields)."""
    client = _client()
    try:
        # Jira Server/DC: createmeta gives per-project field metadata
        return await client.get(
            "/rest/api/2/issue/createmeta",
            params={"projectKeys": key, "expand": "projects.issuetypes.fields"},
        )
    finally:
        await client.close()


@mcp.resource("jira://issue/{issue_key}")
async def get_issue_detail(issue_key: str) -> dict:
    """Chi tiết issue (jira://issue/SP-123)."""
    client = _client()
    try:
        return await client.get(f"/rest/api/2/issue/{issue_key}")
    finally:
        await client.close()


@mcp.resource("jira://issue/{issue_key}/comments")
async def get_issue_comments(issue_key: str) -> dict:
    """Danh sách comments (jira://issue/SP-123/comments)."""
    client = _client()
    try:
        return await client.get(f"/rest/api/2/issue/{issue_key}/comment")
    finally:
        await client.close()


@mcp.resource("jira://issue/{issue_key}/changelog")
async def get_issue_changelog(issue_key: str) -> dict:
    """Lịch sử thay đổi (jira://issue/SP-123/changelog)."""
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
    """Workflow của project (jira://project/SP/workflow)."""
    client = _client()
    try:
        # Jira Server/DC doesn't expose a single "workflow of project"
        # endpoint directly; statuses-per-issuetype is the closest safe
        # read-only proxy. Adjust to your Jira's actual workflow scheme
        # endpoint if you have project admin scope.
        return await client.get(f"/rest/api/2/project/{key}/statuses")
    finally:
        await client.close()


@mcp.resource("jira://me")
async def get_current_user() -> dict:
    """Thông tin user hiện tại (jira://me)."""
    client = _client()
    try:
        return await client.get("/rest/api/2/myself")
    finally:
        await client.close()
