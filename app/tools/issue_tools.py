from __future__ import annotations

from typing import Any

from mcp.server.mcpserver import Context, MCPServer

from app.core.errors import map_exception
from app.safety.write_safety import (
    ConfirmationRequiredError,
    DraftOperationMismatchError,
)
from app.schemas.common import ErrorInfo, MCPResponse, ResponseMeta
from app.schemas.draft import ConfirmDraftInput, DraftInfo
from app.schemas.issue import (
    CreateIssueInput,
    CreateIssueResult,
    DeleteIssuePrepareInput,
    DeleteIssueResult,
    GetIssueInput,
    IssueData,
    UpdateIssueInput,
    UpdateIssueResult,
)


def _to_error_info(exc: Exception) -> ErrorInfo:
    if isinstance(exc, ConfirmationRequiredError):
        return ErrorInfo(
            code="CONFIRMATION_REQUIRED",
            message=str(exc),
            retryable=False,
        )

    if isinstance(exc, DraftOperationMismatchError):
        return ErrorInfo(
            code="DRAFT_OPERATION_MISMATCH",
            message=str(exc),
            retryable=False,
        )

    app_error = map_exception(exc)
    return ErrorInfo(
        code=app_error.code,
        message=app_error.message,
        retryable=app_error.retryable,
        details=app_error.details,
    )


def register_issue_tools(mcp: MCPServer) -> None:
    """Register Jira issue tools."""

    @mcp.tool(
        name="jira_health_check",
        title="Jira Health Check",
        description=(
            "Check whether the Jira server is reachable "
            "and the configured credentials are valid."
        ),
        structured_output=False,
    )
    async def jira_health_check(ctx: Context) -> str:
        app_ctx: Any = ctx.request_context.lifespan_context

        try:
            me = await app_ctx.jira_client.get("/rest/api/2/myself")
        except Exception as exc:
            app_error = map_exception(exc)
            return (
                "Jira MCP server is running, but Jira is unreachable: "
                f"{app_error.message}"
            )

        display_name = (
            (me or {}).get("displayName")
            or (me or {}).get("name")
            or "unknown user"
        )
        return (
            "Jira MCP server is running. "
            f"Connected to Jira as: {display_name}"
        )

    @mcp.tool(
        name="jira_get_issue",
        title="Get Jira Issue",
        description="Retrieve a Jira issue by key.",
        structured_output=True,
    )
    async def jira_get_issue(
        request: GetIssueInput,
        ctx: Context,
    ) -> MCPResponse[IssueData]:
        app_ctx: Any = ctx.request_context.lifespan_context
        meta = ResponseMeta(
            request_id=ctx.request_id,
            operation="jira_get_issue",
        )
        try:
            result = await app_ctx.issue_service.get_issue(request)
            return MCPResponse[IssueData](
                ok=True, data=result, error=None, meta=meta
            )
        except Exception as exc:
            return MCPResponse[IssueData](
                ok=False, data=None, error=_to_error_info(exc), meta=meta
            )

    @mcp.tool(
        name="jira_create_issue_prepare",
        title="Prepare Create Jira Issue",
        description=(
            "Validate and save a create-issue draft. "
            "No Jira issue is created."
        ),
        structured_output=True,
    )
    async def jira_create_issue_prepare(
        request: CreateIssueInput,
        ctx: Context,
    ) -> MCPResponse[DraftInfo]:
        app_ctx: Any = ctx.request_context.lifespan_context
        meta = ResponseMeta(
            request_id=ctx.request_id,
            operation="jira_create_issue_prepare",
        )
        try:
            preview = app_ctx.issue_service.build_create_payload(request)
            draft = await app_ctx.write_safety.prepare(
                operation="jira_create_issue",
                payload=request.model_dump(mode="json"),
                preview=preview,
                request_id=ctx.request_id,
            )
            return MCPResponse[DraftInfo](
                ok=True,
                data=DraftInfo(
                    draft_id=draft.draft_id,
                    operation=draft.operation,
                    preview=preview,
                    expires_in_hours=app_ctx.draft_store.ttl_hours,
                ),
                error=None,
                meta=meta,
            )
        except Exception as exc:
            return MCPResponse[DraftInfo](
                ok=False, data=None, error=_to_error_info(exc), meta=meta
            )

    @mcp.tool(
        name="jira_create_issue_confirm",
        title="Confirm Create Jira Issue",
        description="Execute a prepared create-issue draft.",
        structured_output=True,
    )
    async def jira_create_issue_confirm(
        request: ConfirmDraftInput,
        ctx: Context,
    ) -> MCPResponse[CreateIssueResult]:
        app_ctx: Any = ctx.request_context.lifespan_context
        meta = ResponseMeta(
            request_id=ctx.request_id,
            operation="jira_create_issue_confirm",
        )

        async def execute(draft):
            create_input = CreateIssueInput.model_validate(draft.payload)
            result = await app_ctx.issue_service.create_issue(create_input)
            return result.model_dump(mode="json")

        try:
            execution = await app_ctx.write_safety.execute(
                draft_id=request.draft_id,
                expected_operation="jira_create_issue",
                confirm=request.confirm,
                executor=execute,
                request_id=ctx.request_id,
            )
            result = CreateIssueResult(**execution.result)
            return MCPResponse[CreateIssueResult](
                ok=True, data=result, error=None, meta=meta
            )
        except Exception as exc:
            return MCPResponse[CreateIssueResult](
                ok=False, data=None, error=_to_error_info(exc), meta=meta
            )

    @mcp.tool(
        name="jira_update_issue_prepare",
        title="Prepare Update Jira Issue",
        description=(
            "Validate and save an update-issue draft. "
            "No Jira issue is modified."
        ),
        structured_output=True,
    )
    async def jira_update_issue_prepare(
        request: UpdateIssueInput,
        ctx: Context,
    ) -> MCPResponse[DraftInfo]:
        app_ctx: Any = ctx.request_context.lifespan_context
        meta = ResponseMeta(
            request_id=ctx.request_id,
            operation="jira_update_issue_prepare",
        )
        try:
            preview = app_ctx.issue_service.build_update_payload(request)
            draft = await app_ctx.write_safety.prepare(
                operation="jira_update_issue",
                payload=request.model_dump(mode="json"),
                preview=preview,
                request_id=ctx.request_id,
                issue_key=request.issue_key,
            )
            return MCPResponse[DraftInfo](
                ok=True,
                data=DraftInfo(
                    draft_id=draft.draft_id,
                    operation=draft.operation,
                    preview=preview,
                    expires_in_hours=app_ctx.draft_store.ttl_hours,
                ),
                error=None,
                meta=meta,
            )
        except Exception as exc:
            return MCPResponse[DraftInfo](
                ok=False, data=None, error=_to_error_info(exc), meta=meta
            )

    @mcp.tool(
        name="jira_update_issue_confirm",
        title="Confirm Update Jira Issue",
        description="Execute a prepared update-issue draft.",
        structured_output=True,
    )
    async def jira_update_issue_confirm(
        request: ConfirmDraftInput,
        ctx: Context,
    ) -> MCPResponse[UpdateIssueResult]:
        app_ctx: Any = ctx.request_context.lifespan_context
        meta = ResponseMeta(
            request_id=ctx.request_id,
            operation="jira_update_issue_confirm",
        )

        async def execute(draft):
            update_input = UpdateIssueInput.model_validate(draft.payload)
            result = await app_ctx.issue_service.update_issue(update_input)
            return result.model_dump(mode="json")

        try:
            execution = await app_ctx.write_safety.execute(
                draft_id=request.draft_id,
                expected_operation="jira_update_issue",
                confirm=request.confirm,
                executor=execute,
                request_id=ctx.request_id,
            )
            result = UpdateIssueResult(**execution.result)
            return MCPResponse[UpdateIssueResult](
                ok=True, data=result, error=None, meta=meta
            )
        except Exception as exc:
            return MCPResponse[UpdateIssueResult](
                ok=False, data=None, error=_to_error_info(exc), meta=meta
            )

    @mcp.tool(
        name="jira_delete_issue_prepare",
        title="Prepare Delete Jira Issue",
        description=(
            "Validate and save a destructive delete draft. "
            "No Jira issue is deleted."
        ),
        structured_output=True,
    )
    async def jira_delete_issue_prepare(
        request: DeleteIssuePrepareInput,
        ctx: Context,
    ) -> MCPResponse[DraftInfo]:
        app_ctx: Any = ctx.request_context.lifespan_context
        meta = ResponseMeta(
            request_id=ctx.request_id,
            operation="jira_delete_issue_prepare",
        )
        try:
            preview = app_ctx.issue_service.build_delete_preview(request)
            draft = await app_ctx.write_safety.prepare(
                operation="jira_delete_issue",
                payload=request.model_dump(mode="json"),
                preview=preview,
                request_id=ctx.request_id,
                issue_key=request.issue_key,
            )
            return MCPResponse[DraftInfo](
                ok=True,
                data=DraftInfo(
                    draft_id=draft.draft_id,
                    operation=draft.operation,
                    preview=preview,
                    expires_in_hours=app_ctx.draft_store.ttl_hours,
                ),
                error=None,
                meta=meta,
            )
        except Exception as exc:
            return MCPResponse[DraftInfo](
                ok=False, data=None, error=_to_error_info(exc), meta=meta
            )

    @mcp.tool(
        name="jira_delete_issue_confirm",
        title="Confirm Delete Jira Issue",
        description=(
            "Execute a prepared Jira issue deletion. "
            "Requires confirm=true and is irreversible."
        ),
        structured_output=True,
    )
    async def jira_delete_issue_confirm(
        request: ConfirmDraftInput,
        ctx: Context,
    ) -> MCPResponse[DeleteIssueResult]:
        app_ctx: Any = ctx.request_context.lifespan_context
        meta = ResponseMeta(
            request_id=ctx.request_id,
            operation="jira_delete_issue_confirm",
        )

        async def execute(draft):
            delete_input = DeleteIssuePrepareInput.model_validate(
                draft.payload
            )
            result = await app_ctx.issue_service.delete_issue(
                delete_input.issue_key
            )
            result.reason = delete_input.reason
            return result.model_dump(mode="json")

        try:
            execution = await app_ctx.write_safety.execute(
                draft_id=request.draft_id,
                expected_operation="jira_delete_issue",
                confirm=request.confirm,
                executor=execute,
                request_id=ctx.request_id,
            )
            result = DeleteIssueResult(**execution.result)
            return MCPResponse[DeleteIssueResult](
                ok=True, data=result, error=None, meta=meta
            )
        except Exception as exc:
            return MCPResponse[DeleteIssueResult](
                ok=False, data=None, error=_to_error_info(exc), meta=meta
            )
