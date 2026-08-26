from __future__ import annotations

"""
Issue tools: health check, get_issue, create_issue (prepare/confirm),
delete_issue (prepare/confirm — DESTRUCTIVE).

Module này phải được import bởi app/server.py SAU khi `mcp`,
`AppContext`, và `_map_error` đã được định nghĩa, nếu không sẽ bị
circular import (giống lỗi đã gặp với resources/prompts).
"""

from mcp.server.mcpserver import Context

from app.server import AppContext, _map_error, mcp

from app.infrastructure.jira_client import JiraClientError

from app.schemas.common import (
    ErrorInfo,
    MCPResponse,
    ResponseMeta,
)

from app.schemas.draft import (
    ConfirmDraftInput,
    DraftInfo,
)

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


# ============================================================
# HEALTH CHECK
# ============================================================

@mcp.tool(
    name="jira_health_check",
    title="Jira Health Check",
    description=(
        "Check whether the Jira server is reachable "
        "and the configured credentials are valid."
    ),
    structured_output=False,
)
async def jira_health_check(
    ctx: Context,
) -> str:
    """
    Kiểm tra kết nối Jira và PAT.
    """

    app_ctx: AppContext = (
        ctx.request_context.lifespan_context
    )

    try:
        me = await app_ctx.jira_client.get(
            "/rest/api/2/myself"
        )

    except JiraClientError as exc:
        return (
            "Jira MCP server is running, "
            f"but Jira is unreachable: {exc}"
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


# ============================================================
# GET ISSUE
# ============================================================

@mcp.tool(
    name="jira_get_issue",
    title="Get Jira Issue",
    description=(
        "Retrieve a Jira issue by issue key and return "
        "normalized structured issue data."
    ),
    structured_output=True,
)
async def jira_get_issue(
    request: GetIssueInput,
    ctx: Context,
) -> MCPResponse[IssueData]:

    app_ctx: AppContext = (
        ctx.request_context.lifespan_context
    )

    meta = ResponseMeta(
        request_id=ctx.request_id,
        operation="jira_get_issue",
    )

    try:
        issue = await app_ctx.issue_service.get_issue(
            request
        )

    except Exception as exc:
        return MCPResponse[IssueData](
            ok=False,
            data=None,
            error=_map_error(exc),
            meta=meta,
        )

    return MCPResponse[IssueData](
        ok=True,
        data=issue,
        error=None,
        meta=meta,
    )


# ============================================================
# CREATE ISSUE — PREPARE
# ============================================================

@mcp.tool(
    name="jira_create_issue_prepare",
    title="Prepare Create Jira Issue",
    description=(
        "Validate a Jira issue request and save it "
        "as a draft. This operation does not create "
        "the Jira issue."
    ),
    structured_output=True,
)
async def jira_create_issue_prepare(
    request: CreateIssueInput,
    ctx: Context,
) -> MCPResponse[DraftInfo]:

    app_ctx: AppContext = (
        ctx.request_context.lifespan_context
    )

    meta = ResponseMeta(
        request_id=ctx.request_id,
        operation="jira_create_issue_prepare",
    )

    try:
        preview = (
            app_ctx.issue_service
            .build_create_payload(request)
        )

        draft_id = (
            app_ctx.draft_store.create_draft(
                operation="jira_create_issue",
                payload=request.model_dump(
                    mode="json"
                ),
            )
        )

    except Exception as exc:
        return MCPResponse[DraftInfo](
            ok=False,
            data=None,
            error=_map_error(exc),
            meta=meta,
        )

    draft_info = DraftInfo(
        draft_id=draft_id,
        operation="jira_create_issue",
        preview=preview,
        expires_in_hours=24.0,
    )

    return MCPResponse[DraftInfo](
        ok=True,
        data=draft_info,
        error=None,
        meta=meta,
    )


# ============================================================
# CREATE ISSUE — CONFIRM
# ============================================================

@mcp.tool(
    name="jira_create_issue_confirm",
    title="Confirm Create Jira Issue",
    description=(
        "Execute a previously prepared Jira issue draft. "
        "Requires confirm=true."
    ),
    structured_output=True,
)
async def jira_create_issue_confirm(
    request: ConfirmDraftInput,
    ctx: Context,
) -> MCPResponse[CreateIssueResult]:

    app_ctx: AppContext = (
        ctx.request_context.lifespan_context
    )

    meta = ResponseMeta(
        request_id=ctx.request_id,
        operation="jira_create_issue_confirm",
    )

    try:
        draft = app_ctx.draft_store.get_draft(
            request.draft_id
        )

    except Exception as exc:
        return MCPResponse[CreateIssueResult](
            ok=False,
            data=None,
            error=_map_error(exc),
            meta=meta,
        )

    if draft.operation != "jira_create_issue":
        return MCPResponse[CreateIssueResult](
            ok=False,
            data=None,
            error=ErrorInfo(
                code="DRAFT_OPERATION_MISMATCH",
                message=(
                    f"Draft '{request.draft_id}' belongs "
                    f"to operation '{draft.operation}', "
                    "not 'jira_create_issue'."
                ),
                retryable=False,
            ),
            meta=meta,
        )

    if draft.status == "confirmed":
        return MCPResponse[CreateIssueResult](
            ok=True,
            data=CreateIssueResult(
                **(draft.result or {})
            ),
            error=None,
            meta=meta,
        )

    if not request.confirm:
        return MCPResponse[CreateIssueResult](
            ok=False,
            data=None,
            error=ErrorInfo(
                code="CONFIRMATION_REQUIRED",
                message=(
                    "Set confirm=true to execute this "
                    "operation. This action will create "
                    "a real Jira issue."
                ),
                retryable=False,
            ),
            meta=meta,
        )

    try:
        create_input = (
            CreateIssueInput.model_validate(
                draft.payload
            )
        )

        result = (
            await app_ctx.issue_service.create_issue(
                create_input
            )
        )

    except Exception as exc:
        return MCPResponse[CreateIssueResult](
            ok=False,
            data=None,
            error=_map_error(exc),
            meta=meta,
        )

    app_ctx.draft_store.mark_confirmed(
        request.draft_id,
        result.model_dump(mode="json"),
    )

    return MCPResponse[CreateIssueResult](
        ok=True,
        data=result,
        error=None,
        meta=meta,
    )


# ============================================================
# UPDATE ISSUE — PREPARE
# ============================================================

@mcp.tool(
    name="jira_update_issue_prepare",
    title="Prepare Update Jira Issue",
    description=(
        "Validate a Jira issue update request and save it "
        "as a draft. This operation does not modify the "
        "Jira issue."
    ),
    structured_output=True,
)
async def jira_update_issue_prepare(
    request: UpdateIssueInput,
    ctx: Context,
) -> MCPResponse[DraftInfo]:

    app_ctx: AppContext = (
        ctx.request_context.lifespan_context
    )

    meta = ResponseMeta(
        request_id=ctx.request_id,
        operation="jira_update_issue_prepare",
    )

    try:
        preview = (
            app_ctx.issue_service
            .build_update_payload(request)
        )

        draft_id = (
            app_ctx.draft_store.create_draft(
                operation="jira_update_issue",
                payload=request.model_dump(
                    mode="json"
                ),
            )
        )

    except Exception as exc:
        return MCPResponse[DraftInfo](
            ok=False,
            data=None,
            error=_map_error(exc),
            meta=meta,
        )

    draft_info = DraftInfo(
        draft_id=draft_id,
        operation="jira_update_issue",
        preview=preview,
        expires_in_hours=24.0,
    )

    return MCPResponse[DraftInfo](
        ok=True,
        data=draft_info,
        error=None,
        meta=meta,
    )


# ============================================================
# UPDATE ISSUE — CONFIRM
# ============================================================

@mcp.tool(
    name="jira_update_issue_confirm",
    title="Confirm Update Jira Issue",
    description=(
        "Execute a previously prepared Jira issue update. "
        "Requires confirm=true."
    ),
    structured_output=True,
)
async def jira_update_issue_confirm(
    request: ConfirmDraftInput,
    ctx: Context,
) -> MCPResponse[UpdateIssueResult]:

    app_ctx: AppContext = (
        ctx.request_context.lifespan_context
    )

    meta = ResponseMeta(
        request_id=ctx.request_id,
        operation="jira_update_issue_confirm",
    )

    try:
        draft = app_ctx.draft_store.get_draft(
            request.draft_id
        )

    except Exception as exc:
        return MCPResponse[UpdateIssueResult](
            ok=False,
            data=None,
            error=_map_error(exc),
            meta=meta,
        )

    if draft.operation != "jira_update_issue":
        return MCPResponse[UpdateIssueResult](
            ok=False,
            data=None,
            error=ErrorInfo(
                code="DRAFT_OPERATION_MISMATCH",
                message=(
                    f"Draft '{request.draft_id}' belongs "
                    f"to operation '{draft.operation}', "
                    "not 'jira_update_issue'."
                ),
                retryable=False,
            ),
            meta=meta,
        )

    if draft.status == "confirmed":
        return MCPResponse[UpdateIssueResult](
            ok=True,
            data=UpdateIssueResult(
                **(draft.result or {})
            ),
            error=None,
            meta=meta,
        )

    if not request.confirm:
        return MCPResponse[UpdateIssueResult](
            ok=False,
            data=None,
            error=ErrorInfo(
                code="CONFIRMATION_REQUIRED",
                message=(
                    "Set confirm=true to execute this "
                    "operation. This action will modify "
                    "a real Jira issue."
                ),
                retryable=False,
            ),
            meta=meta,
        )

    try:
        update_input = (
            UpdateIssueInput.model_validate(
                draft.payload
            )
        )

        result = (
            await app_ctx.issue_service.update_issue(
                update_input
            )
        )

    except Exception as exc:
        return MCPResponse[UpdateIssueResult](
            ok=False,
            data=None,
            error=_map_error(exc),
            meta=meta,
        )

    app_ctx.draft_store.mark_confirmed(
        request.draft_id,
        result.model_dump(mode="json"),
    )

    return MCPResponse[UpdateIssueResult](
        ok=True,
        data=result,
        error=None,
        meta=meta,
    )


# ============================================================
# DELETE ISSUE — PREPARE (DESTRUCTIVE)
# ============================================================

@mcp.tool(
    name="jira_delete_issue_prepare",
    title="Prepare Delete Jira Issue",
    description=(
        "Validate a destructive delete request and save it as a "
        "draft. Requires a reason. This operation does NOT delete "
        "the Jira issue."
    ),
    structured_output=True,
)
async def jira_delete_issue_prepare(
    request: DeleteIssuePrepareInput,
    ctx: Context,
) -> MCPResponse[DraftInfo]:

    app_ctx: AppContext = (
        ctx.request_context.lifespan_context
    )

    meta = ResponseMeta(
        request_id=ctx.request_id,
        operation="jira_delete_issue_prepare",
    )

    try:
        preview = (
            app_ctx.issue_service
            .build_delete_preview(request)
        )

        draft_id = (
            app_ctx.draft_store.create_draft(
                operation="jira_delete_issue",
                payload=request.model_dump(
                    mode="json"
                ),
            )
        )

    except Exception as exc:
        return MCPResponse[DraftInfo](
            ok=False,
            data=None,
            error=_map_error(exc),
            meta=meta,
        )

    draft_info = DraftInfo(
        draft_id=draft_id,
        operation="jira_delete_issue",
        preview=preview,
        expires_in_hours=24.0,
    )

    return MCPResponse[DraftInfo](
        ok=True,
        data=draft_info,
        error=None,
        meta=meta,
    )


# ============================================================
# DELETE ISSUE — CONFIRM (DESTRUCTIVE)
# ============================================================

@mcp.tool(
    name="jira_delete_issue_confirm",
    title="Confirm Delete Jira Issue",
    description=(
        "Execute a previously prepared Jira issue deletion. "
        "Requires confirm=true. This action is IRREVERSIBLE."
    ),
    structured_output=True,
)
async def jira_delete_issue_confirm(
    request: ConfirmDraftInput,
    ctx: Context,
) -> MCPResponse[DeleteIssueResult]:

    app_ctx: AppContext = (
        ctx.request_context.lifespan_context
    )

    meta = ResponseMeta(
        request_id=ctx.request_id,
        operation="jira_delete_issue_confirm",
    )

    try:
        draft = app_ctx.draft_store.get_draft(
            request.draft_id
        )

    except Exception as exc:
        return MCPResponse[DeleteIssueResult](
            ok=False,
            data=None,
            error=_map_error(exc),
            meta=meta,
        )

    if draft.operation != "jira_delete_issue":
        return MCPResponse[DeleteIssueResult](
            ok=False,
            data=None,
            error=ErrorInfo(
                code="DRAFT_OPERATION_MISMATCH",
                message=(
                    f"Draft '{request.draft_id}' belongs "
                    f"to operation '{draft.operation}', "
                    "not 'jira_delete_issue'."
                ),
                retryable=False,
            ),
            meta=meta,
        )

    if draft.status == "confirmed":
        return MCPResponse[DeleteIssueResult](
            ok=True,
            data=DeleteIssueResult(
                **(draft.result or {})
            ),
            error=None,
            meta=meta,
        )

    if not request.confirm:
        return MCPResponse[DeleteIssueResult](
            ok=False,
            data=None,
            error=ErrorInfo(
                code="CONFIRMATION_REQUIRED",
                message=(
                    "Set confirm=true to execute this deletion. "
                    "This action is IRREVERSIBLE and will "
                    "permanently delete a real Jira issue. "
                    f"Reason on file: "
                    f"{draft.payload.get('reason', '(none)')}"
                ),
                retryable=False,
            ),
            meta=meta,
        )

    try:
        delete_input = (
            DeleteIssuePrepareInput.model_validate(
                draft.payload
            )
        )

        result = (
            await app_ctx.issue_service.delete_issue(
                delete_input.issue_key
            )
        )
        result.reason = delete_input.reason

    except Exception as exc:
        return MCPResponse[DeleteIssueResult](
            ok=False,
            data=None,
            error=_map_error(exc),
            meta=meta,
        )

    app_ctx.draft_store.mark_confirmed(
        request.draft_id,
        result.model_dump(mode="json"),
    )

    return MCPResponse[DeleteIssueResult](
        ok=True,
        data=result,
        error=None,
        meta=meta,
    )
