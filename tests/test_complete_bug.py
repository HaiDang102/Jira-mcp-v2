from __future__ import annotations

from datetime import date

import pytest

from app.schemas.issue import CreateIssueInput
from app.services.issue_service import IssueService


class DummyJiraClient:
    pass


def test_complete_bug_payload(monkeypatch):
    monkeypatch.setattr(
        "app.services.issue_service.settings.jira_start_date_field_id",
        "customfield_20001",
    )
    monkeypatch.setattr(
        "app.services.issue_service.settings.jira_epic_link_field_id",
        "customfield_20002",
    )

    service = IssueService(DummyJiraClient())

    request = CreateIssueInput(
        project_key="SP",
        issue_type="Bug",
        summary="[MCP TEST] Full Bug",
        error_description="Hệ thống cho phép hoàn thành sai luồng.",
        steps_to_reproduce=[
            "Mở hồ sơ.",
            "Thực hiện thao tác gây lỗi.",
        ],
        actual_result="Hồ sơ vẫn hoàn thành.",
        expected_result="Hệ thống phải chặn thao tác.",
        evidence="Hồ sơ 2501.CC.26.000182",
        assignee="nam.pd",
        start_date=date(2026, 8, 25),
        due_date=date(2026, 8, 26),
        priority="High",
        labels=["CCDK", "UAT"],
        epic_key="SP-100",
        environment="UAT",
    )

    payload = service.build_create_payload(request)
    fields = payload["fields"]

    assert fields["project"]["key"] == "SP"
    assert fields["issuetype"]["name"] == "Bug"
    assert fields["assignee"]["name"] == "nam.pd"
    assert fields["priority"]["name"] == "High"
    assert fields["labels"] == ["CCDK", "UAT"]
    assert fields["duedate"] == "2026-08-26"
    assert fields["customfield_20001"] == "2026-08-25"
    assert fields["customfield_20002"] == "SP-100"

    description = fields["description"]
    assert "h3. Mô tả lỗi" in description
    assert "h3. Các bước tái hiện lỗi" in description
    assert "h3. Kết quả thực tế" in description
    assert "h3. Kết quả mong đợi" in description
    assert "h3. Minh chứng" in description
    assert "*Priority:* High" in description
    assert "*Epic Link:* SP-100" in description


def test_bug_requires_qa_sections():
    with pytest.raises(ValueError):
        CreateIssueInput(
            project_key="SP",
            issue_type="Bug",
            summary="Bug thiếu dữ liệu",
        )


def test_start_date_requires_config(monkeypatch):
    monkeypatch.setattr(
        "app.services.issue_service.settings.jira_start_date_field_id",
        None,
    )

    service = IssueService(DummyJiraClient())

    request = CreateIssueInput(
        project_key="SP",
        issue_type="Bug",
        summary="[MCP TEST] Start Date",
        error_description="Mô tả lỗi.",
        steps_to_reproduce=["Bước 1."],
        actual_result="Sai.",
        expected_result="Đúng.",
        start_date=date(2026, 8, 25),
    )

    with pytest.raises(
        ValueError,
        match="JIRA_START_DATE_FIELD_ID",
    ):
        service.build_create_payload(request)
