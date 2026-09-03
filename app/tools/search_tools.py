from __future__ import annotations

from typing import Any

from mcp.server.mcpserver import Context, MCPServer

from app.core.errors import map_exception
from app.schemas.common import (
    ErrorInfo,
    MCPResponse,
    ResponseMeta,
)
from app.schemas.search import (
    SearchInput,
    SearchResult,
)


def _to_error_info(exc: Exception) -> ErrorInfo:
    app_error = map_exception(exc)

    return ErrorInfo(
        code=app_error.code,
        message=app_error.message,
        retryable=app_error.retryable,
    )


def register_search_tools(mcp: MCPServer) -> None:
    """Register Jira search tools."""

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

        app_ctx: Any = (
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
                error=_to_error_info(exc),
                meta=meta,
            )

        return MCPResponse[SearchResult](
            ok=True,
            data=result,
            error=None,
            meta=meta,
        )