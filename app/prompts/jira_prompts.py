from __future__ import annotations

from mcp.server.mcpserver import MCPServer


def register_jira_prompts(mcp: MCPServer) -> None:
    """Register reusable Jira prompts."""

    @mcp.prompt("jira_bug_report")
    def jira_bug_report(
        summary: str,
        error_description: str,
        steps_to_reproduce: str,
        actual_result: str,
        expected_result: str,
        assignee: str = "",
        start_date: str = "",
        due_date: str = "",
        priority: str = "Medium",
        labels: str = "",
        epic_link: str = "",
        environment: str = "",
        evidence: str = "",
    ) -> str:
        """
        Guide the LLM to create a complete QA bug report and respect
        Prepare -> Review -> Confirm -> Execute.
        """

        return f"""Bạn đang chuẩn bị một Jira Bug cho QA.

Thông tin đầu vào:

Summary:
{summary}

Mô tả lỗi:
{error_description}

Các bước tái hiện:
{steps_to_reproduce}

Kết quả thực tế:
{actual_result}

Kết quả mong đợi:
{expected_result}

Assignee: {assignee or "(chưa cung cấp)"}
Start Date: {start_date or "(chưa cung cấp)"}
Due Date: {due_date or "(chưa cung cấp)"}
Priority: {priority}
Labels: {labels or "(không có)"}
Epic Link: {epic_link or "(không có)"}
Environment: {environment or "(chưa cung cấp)"}
Evidence: {evidence or "(không có)"}

QUY TẮC BẮT BUỘC:

1. Không tự bịa Assignee, Start Date, Due Date, Epic Link hoặc Evidence.
2. Nếu thiếu field mà user yêu cầu phải có, hỏi lại user trước khi Prepare.
3. Bug phải có đủ:
   - Summary
   - Mô tả lỗi
   - Các bước tái hiện lỗi
   - Kết quả thực tế
   - Kết quả mong đợi
4. Priority, Labels, Assignee, Start Date, Due Date, Epic Link phải được
   đưa vào request khi user đã cung cấp.
5. Chỉ sử dụng Jira username hợp lệ cho Assignee/Reporter.
6. Sau khi đủ dữ liệu, gọi jira_create_issue_prepare trước.
7. Hiển thị toàn bộ draft cho user review, bao gồm:
   Summary, Assignee, Priority, Labels, Start Date, Due Date, Epic Link,
   Description và custom fields.
8. Sau PREPARE phải DỪNG. Không tự gọi jira_create_issue_confirm.
9. Chỉ khi user xác nhận rõ ràng thì mới gọi jira_create_issue_confirm
   với confirm=true.
10. Không retry bằng cách tạo draft mới khi confirm đã thành công.
"""

    @mcp.prompt("jira_task_create")
    def jira_task_create(
        summary: str,
        description: str = "",
        assignee: str = "",
        due_date: str = "",
        priority: str = "Medium",
    ) -> str:
        return f"""Soạn Jira Task:

Summary: {summary}
Description: {description or "(chưa cung cấp)"}
Assignee: {assignee or "(chưa chỉ định)"}
Due Date: {due_date or "(không có)"}
Priority: {priority}

Không tự bịa dữ liệu. Luôn dùng flow:
Prepare -> Review -> Confirm -> Execute.
"""
