from __future__ import annotations

"""
MCP Prompts — reusable templates that guide the LLM client on how to
draft well-formed Jira content before calling a WRITE tool.

Like resources, this module must be imported by app/server.py before
`list_prompts()` is called:

    from app.prompts import jira_prompts  # noqa: F401  (registers prompts)
"""

from app.server import mcp


@mcp.prompt("jira_bug_report")
def jira_bug_report(
    summary: str,
    steps_to_reproduce: str,
    expected_result: str,
    actual_result: str,
    environment: str = "",
    priority: str = "Medium",
    evidence: str = "",
) -> str:
    """Hướng dẫn tạo bug theo chuẩn QA."""
    return f"""Tạo một Jira bug issue theo chuẩn QA với các trường sau:

- Summary: {summary}
- Steps to reproduce:
{steps_to_reproduce}
- Expected result: {expected_result}
- Actual result: {actual_result}
- Environment: {environment or "(chưa cung cấp — hỏi lại user nếu cần)"}
- Priority: {priority}
- Evidence: {evidence or "(đính kèm screenshot/log nếu có)"}

Sau khi soạn xong nội dung, gọi tool tạo issue WRITE (ví dụ jira_create_issue)
theo đúng luồng Prepare -> Review -> Confirm -> Execute. Không tạo issue trực
tiếp mà chưa qua bước Review với người dùng.
"""


@mcp.prompt("jira_feature_request")
def jira_feature_request(
    summary: str,
    description: str,
    business_value: str = "",
    acceptance_criteria: str = "",
    priority: str = "Medium",
) -> str:
    """Hướng dẫn tạo feature request."""
    return f"""Tạo một Jira feature request với các trường sau:

- Summary: {summary}
- Description: {description}
- Business value: {business_value or "(chưa cung cấp)"}
- Acceptance criteria:
{acceptance_criteria or "(chưa cung cấp — nên hỏi lại user trước khi tạo draft)"}
- Priority: {priority}

Soạn draft trước, cho user review, chỉ execute (tạo thật trên Jira) sau khi
user xác nhận rõ ràng (YES/CONFIRM).
"""


@mcp.prompt("jira_task_create")
def jira_task_create(
    summary: str,
    description: str = "",
    assignee: str = "",
    due_date: str = "",
    priority: str = "Medium",
) -> str:
    """Hướng dẫn tạo task thông thường."""
    return f"""Tạo một Jira task với các trường sau:

- Summary: {summary}
- Description: {description or "(chưa cung cấp)"}
- Assignee: {assignee or "(chưa gán, để trống hoặc hỏi user)"}
- Due date: {due_date or "(không có hạn)"}
- Priority: {priority}

Luôn đi qua luồng Prepare (draft) -> Review -> Confirm -> Execute trước khi
gọi tool WRITE thực sự tạo task trên Jira.
"""
