from __future__ import annotations

"""
Workflow tools. Import order: sau khi `mcp`, `AppContext`, `_map_error`
đã tồn tại trong app.server.
"""

from mcp.server.mcpserver import Context

from app.server import AppContext, _map_error, mcp

from app.schemas.common import (
    ErrorInfo,
    MCPResponse,
    ResponseMeta,
)

from app.schemas.workflow import (
    GetTransitionsInput,
    TransitionIssueInput,
    TransitionResult,
)


# ============================================================
# WORKFLOW — GET TRANSITIONS
# ============================================================

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

    app_ctx: AppContext = (
        ctx.request_context.lifespan_context
    )

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
            error=_map_error(exc),
            meta=meta,
        )

    return MCPResponse[TransitionResult](
        ok=True,
        data=result,
        error=None,
        meta=meta,
    )


# ============================================================
# WORKFLOW — TRANSITION ISSUE
# ============================================================

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
) -> MCPResponse[TransitionResult]:

    app_ctx: AppContext = (
        ctx.request_context.lifespan_context
    )

    meta = ResponseMeta(
        request_id=ctx.request_id,
        operation="jira_transition_issue",
    )

    if not request.confirm:
        return MCPResponse[TransitionResult](
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
        return MCPResponse[TransitionResult](
            ok=False,
            data=None,
            error=_map_error(exc),
            meta=meta,
        )

    return MCPResponse[TransitionResult](
        ok=True,
        data=result,
        error=None,
        meta=meta,
    )
