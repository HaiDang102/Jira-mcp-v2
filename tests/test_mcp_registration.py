from __future__ import annotations

import pytest

from app.server import mcp


EXPECTED_TOOLS = {
    "jira_health_check",
    "jira_get_issue",
    "jira_create_issue_prepare",
    "jira_create_issue_confirm",
    "jira_update_issue_prepare",
    "jira_update_issue_confirm",
    "jira_delete_issue_prepare",
    "jira_delete_issue_confirm",
    "jira_search_issue",
    "jira_get_transitions",
    "jira_transition_issue",
}

EXPECTED_RESOURCES = {
    "jira://me",
}

EXPECTED_RESOURCE_TEMPLATES = {
    "jira://project/{key}",
    "jira://project/{key}/fields",
    "jira://issue/{issue_key}",
    "jira://issue/{issue_key}/comments",
    "jira://issue/{issue_key}/changelog",
    "jira://project/{key}/workflow",
}

EXPECTED_PROMPTS = {
    "jira_bug_report",
    "jira_task_create",
}


@pytest.mark.asyncio
async def test_registered_tools():
    tools = await mcp.list_tools()
    names = [tool.name for tool in tools]

    assert len(names) == len(set(names)), "Duplicate MCP tool registration detected."
    assert set(names) == EXPECTED_TOOLS


@pytest.mark.asyncio
async def test_registered_resources():
    resources = await mcp.list_resources()
    uris = [str(resource.uri) for resource in resources]

    assert len(uris) == len(set(uris)), "Duplicate MCP resource registration detected."
    assert set(uris) == EXPECTED_RESOURCES


@pytest.mark.asyncio
async def test_registered_resource_templates():
    templates = await mcp.list_resource_templates()
    uris = [str(template.uri_template) for template in templates]

    assert len(uris) == len(set(uris)), (
        "Duplicate MCP resource-template registration detected."
    )
    assert set(uris) == EXPECTED_RESOURCE_TEMPLATES


@pytest.mark.asyncio
async def test_registered_prompts():
    prompts = await mcp.list_prompts()
    names = [prompt.name for prompt in prompts]

    assert len(names) == len(set(names)), "Duplicate MCP prompt registration detected."
    assert set(names) == EXPECTED_PROMPTS


@pytest.mark.asyncio
async def test_write_tools_have_prepare_confirm_pairs():
    tools = await mcp.list_tools()
    names = {tool.name for tool in tools}

    for operation in ("create_issue", "update_issue", "delete_issue"):
        prepare = f"jira_{operation}_prepare"
        confirm = f"jira_{operation}_confirm"

        assert prepare in names
        assert confirm in names


@pytest.mark.asyncio
async def test_core_read_tools_are_exposed():
    tools = await mcp.list_tools()
    names = {tool.name for tool in tools}

    assert {
        "jira_health_check",
        "jira_get_issue",
        "jira_search_issue",
        "jira_get_transitions",
    }.issubset(names)
