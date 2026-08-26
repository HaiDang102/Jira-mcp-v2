from __future__ import annotations

"""
Search tools. Import order: sau khi `mcp`, `AppContext`, `_map_error`
đã tồn tại trong app.server.
"""

from mcp.server.mcpserver import Context

from app.server import AppContext, _map_error, mcp

from app.schemas.common import (
    MCPResponse,
    ResponseMeta,
)

from app.schemas.search import (
    SearchInput,
    SearchResult,
)


# ============================================================
# SEARCH ISSUE
# ============================================================

@mcp.tool(
    name="jira_search_issue",
    title="Search Jira Issues",
    description=(
        "Search Jira issues using JQL and return "
        "a paginated list of normalized issues."
    ),
    structured_output=True,
)
async def jira_search_issue(
    request: SearchInput,
    ctx: Context,
) -> MCPResponse[SearchResult]:

    app_ctx: AppContext = (
        ctx.request_context.lifespan_context
    )

    meta = ResponseMeta(
        request_id=ctx.request_id,
        operation="jira_search_issue",
    )

    try:
        result = await app_ctx.search_service.search(
            request
        )

    except Exception as exc:
        return MCPResponse[SearchResult](
            ok=False,
            data=None,
            error=_map_error(exc),
            meta=meta,
        )

    return MCPResponse[SearchResult](
        ok=True,
        data=result,
        error=None,
        meta=meta,
    )
