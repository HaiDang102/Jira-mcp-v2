from __future__ import annotations

from typing import Any

from mcp.server.mcpserver import Context, MCPServer

from app.core.errors import map_exception
from app.schemas.common import (
    ErrorInfo,
    MCPResponse,
    ResponseMeta,
)
from app.schemas.workflow import (
    GetTransitionsInput,
    TransitionExecutionResult,
    TransitionIssueInput,
    TransitionResult,
)


def _to_error_info(exc: Exception) -> ErrorInfo:
    app_error = map_exception(exc)

    return ErrorInfo(
        code=app_error.code,
        message=app_error.message,
        retryable=app_error.retryable,
        details=app_error.details,
    )


def register_workflow_tools(mcp: MCPServer) -> None:
    """Register Jira workflow tools."""

    @mcp.tool(
        name="jira_get_transitions",
        title="Get Jira Issue Transitions",
        description=(
            "Get the workflow transitions currently available "
            "for a Jira issue. This operation is read-only."
        ),
        structured_output=True,
    )
    async def jira_get_transitions(
        request: GetTransitionsInput,
        ctx: Context,
    ) -> MCPResponse[TransitionResult]:

        app_ctx: Any = ctx.request_context.lifespan_context

        meta = ResponseMeta(
            request_id=ctx.request_id,
            operation="jira_get_transitions",
        )

        try:
            result = (
                await app_ctx.workflow_service.get_transitions(
                    request
                )
            )

        except Exception as exc:
            return MCPResponse[TransitionResult](
                ok=False,
                data=None,
                error=_to_error_info(exc),
                meta=meta,
            )

        return MCPResponse[TransitionResult](
            ok=True,
            data=result,
            error=None,
            meta=meta,
        )

    @mcp.tool(
        name="jira_transition_issue",
        title="Transition Jira Issue",
        description=(
            "Transition a Jira issue to another workflow status. "
            "This is a write operation and requires "
            "explicit confirm=true."
        ),
        structured_output=True,
    )
    async def jira_transition_issue(
        request: TransitionIssueInput,
        ctx: Context,
    ) -> MCPResponse[TransitionExecutionResult]:

        app_ctx: Any = ctx.request_context.lifespan_context

        meta = ResponseMeta(
            request_id=ctx.request_id,
            operation="jira_transition_issue",
        )

        if not request.confirm:
            return MCPResponse[TransitionExecutionResult](
                ok=False,
                data=None,
                error=ErrorInfo(
                    code="CONFIRMATION_REQUIRED",
                    message=(
                        "Set confirm=true to transition the "
                        "Jira issue. This operation changes "
                        "the issue workflow status."
                    ),
                    retryable=False,
                ),
                meta=meta,
            )

        try:
            result = (
                await app_ctx.workflow_service.transition_issue(
                    request
                )
            )

        except Exception as exc:
            return MCPResponse[TransitionExecutionResult](
                ok=False,
                data=None,
                error=_to_error_info(exc),
                meta=meta,
            )

        return MCPResponse[TransitionExecutionResult](
            ok=True,
            data=result,
            error=None,
            meta=meta,
        )
