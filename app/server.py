from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass

from mcp.server.mcpserver import MCPServer

from app.infrastructure.audit_logger import (
    AuditLogger,
    create_audit_logger,
)
from app.infrastructure.draft_store import (
    DraftStore,
    create_draft_store,
)
from app.infrastructure.idempotency import IdempotencyManager
from app.infrastructure.jira_client import JiraClient, create_jira_client
from app.infrastructure.metadata_cache import MetadataCache
from app.prompts.jira_prompts import register_jira_prompts
from app.resources.jira_resources import register_jira_resources
from app.safety.write_safety import WriteSafety
from app.services.issue_service import IssueService
from app.services.search_service import SearchService
from app.services.workflow_service import WorkflowService
from app.tools.issue_tools import register_issue_tools
from app.tools.search_tools import register_search_tools
from app.tools.workflow_tools import register_workflow_tools


@dataclass
class AppContext:
    """Shared application dependencies for the MCP lifespan."""

    jira_client: JiraClient
    issue_service: IssueService
    search_service: SearchService
    workflow_service: WorkflowService
    draft_store: DraftStore
    idempotency: IdempotencyManager
    audit_logger: AuditLogger
    metadata_cache: MetadataCache
    write_safety: WriteSafety


@asynccontextmanager
async def lifespan(server: MCPServer):
    jira_client = create_jira_client()
    draft_store = create_draft_store()
    idempotency = IdempotencyManager()
    audit_logger = create_audit_logger()
    metadata_cache = MetadataCache(jira_client)

    context = AppContext(
        jira_client=jira_client,
        issue_service=IssueService(jira_client=jira_client),
        search_service=SearchService(jira_client=jira_client),
        workflow_service=WorkflowService(jira_client=jira_client),
        draft_store=draft_store,
        idempotency=idempotency,
        audit_logger=audit_logger,
        metadata_cache=metadata_cache,
        write_safety=WriteSafety(
            draft_store=draft_store,
            idempotency=idempotency,
            audit=audit_logger,
        ),
    )

    try:
        yield context
    finally:
        await jira_client.close()


mcp = MCPServer(
    name="jira-mcp",
    title="Jira MCP Server",
    description="Production-oriented MCP server for interacting with Jira.",
    instructions=(
        "Use Jira tools to retrieve and manage Jira issues. "
        "Respect tool schemas and return structured data. "
        "Write and destructive operations require explicit confirmation."
    ),
    version="2.0.0",
    lifespan=lifespan,
)


register_issue_tools(mcp)
register_search_tools(mcp)
register_workflow_tools(mcp)
register_jira_resources(mcp)
register_jira_prompts(mcp)


if __name__ == "__main__":
    mcp.run(transport="stdio")
