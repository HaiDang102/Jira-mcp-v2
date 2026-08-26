from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass

from mcp.server.mcpserver import MCPServer

from app.infrastructure.draft_store import (
    DraftExpiredError,
    DraftNotFoundError,
    DraftStore,
    create_draft_store,
)

from app.infrastructure.jira_client import (
    JiraAuthenticationError,
    JiraClient,
    JiraClientError,
    JiraNotFoundError,
    JiraPermissionError,
    JiraRateLimitError,
    JiraServerError,
    create_jira_client,
)

from app.schemas.common import ErrorInfo

from app.services.issue_service import IssueService
from app.services.search_service import SearchService
from app.services.workflow_service import WorkflowService


# ============================================================
# APPLICATION CONTEXT
# ============================================================

@dataclass
class AppContext:
    """
    Shared application dependencies.

    Một JiraClient được dùng chung cho toàn bộ MCP server.
    Các service sử dụng chung JiraClient này.
    """

    jira_client: JiraClient
    issue_service: IssueService
    search_service: SearchService
    workflow_service: WorkflowService
    draft_store: DraftStore


# ============================================================
# LIFESPAN
# ============================================================

@asynccontextmanager
async def lifespan(server: MCPServer):
    """
    Application lifecycle.

    Khi server start:
        - tạo JiraClient
        - tạo IssueService
        - tạo SearchService
        - tạo WorkflowService
        - tạo DraftStore

    Khi server shutdown:
        - đóng JiraClient
    """

    jira_client = create_jira_client()

    issue_service = IssueService(
        jira_client=jira_client
    )

    search_service = SearchService(
        jira_client=jira_client
    )

    workflow_service = WorkflowService(
        jira_client=jira_client
    )

    draft_store = create_draft_store()

    context = AppContext(
        jira_client=jira_client,
        issue_service=issue_service,
        search_service=search_service,
        workflow_service=workflow_service,
        draft_store=draft_store,
    )

    try:
        yield context

    finally:
        await jira_client.close()


# ============================================================
# MCP SERVER
# ============================================================

mcp = MCPServer(
    name="jira-mcp",
    title="Jira MCP Server",
    description=(
        "Production-oriented MCP server "
        "for interacting with Jira."
    ),
    instructions=(
        "Use Jira tools to retrieve and manage Jira issues. "
        "Respect tool schemas and return structured data. "
        "Destructive operations require explicit confirmation."
    ),
    version="2.0.0",
    lifespan=lifespan,
)


# ============================================================
# ERROR MAPPING
# ============================================================
# Dùng chung bởi mọi tool trong app/tools/*.py

_ERROR_CODE_MAP: tuple[
    tuple[type[Exception], str, bool],
    ...
] = (
    (
        JiraAuthenticationError,
        "AUTH_FAILED",
        False,
    ),
    (
        JiraPermissionError,
        "PERMISSION_DENIED",
        False,
    ),
    (
        JiraNotFoundError,
        "ISSUE_NOT_FOUND",
        False,
    ),
    (
        JiraRateLimitError,
        "RATE_LIMITED",
        True,
    ),
    (
        JiraServerError,
        "JIRA_SERVER_ERROR",
        True,
    ),
    (
        DraftNotFoundError,
        "DRAFT_NOT_FOUND",
        False,
    ),
    (
        DraftExpiredError,
        "DRAFT_EXPIRED",
        False,
    ),
)


def _map_error(exc: Exception) -> ErrorInfo:
    """
    Convert application exception into standard ErrorInfo.
    """

    for exc_type, code, retryable in _ERROR_CODE_MAP:
        if isinstance(exc, exc_type):
            return ErrorInfo(
                code=code,
                message=str(exc),
                retryable=retryable,
            )

    if isinstance(exc, ValueError):
        return ErrorInfo(
            code="VALIDATION_ERROR",
            message=str(exc),
            retryable=False,
        )

    if isinstance(exc, JiraClientError):
        return ErrorInfo(
            code="JIRA_CLIENT_ERROR",
            message=str(exc),
            retryable=False,
        )

    return ErrorInfo(
        code="INTERNAL_ERROR",
        message="An unexpected error occurred.",
        retryable=False,
    )


# ============================================================
# TOOL / RESOURCE / PROMPT REGISTRATION
# ============================================================
# QUAN TRỌNG: các import dưới đây PHẢI đặt SAU khi `mcp`,
# `AppContext`, và `_map_error` đã được định nghĩa ở trên.
# Mỗi module trong app/tools, app/resources, app/prompts đều
# có dòng `from app.server import mcp` (và một số còn cần
# AppContext, _map_error) — import chúng sớm hơn sẽ gây
# circular import (NameError/ImportError khi khởi động).

from app.tools import (  # noqa: F401,E402
    issue_tools,
    search_tools,
    workflow_tools,
)
from app.resources import jira_resources  # noqa: F401,E402
from app.prompts import jira_prompts  # noqa: F401,E402


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    mcp.run(
        transport="stdio"
    )
