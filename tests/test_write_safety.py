from __future__ import annotations

import pytest

from app.infrastructure.audit_logger import AuditLogger
from app.infrastructure.draft_store import (
    DraftExpiredError,
    DraftStore,
)
from app.infrastructure.idempotency import IdempotencyManager
from app.safety.write_safety import (
    ConfirmationRequiredError,
    DraftOperationMismatchError,
    WriteSafety,
)


@pytest.fixture
def safety(tmp_path):
    draft_store = DraftStore(
        db_path=str(tmp_path / "drafts.db"),
        ttl_hours=24.0,
    )

    idempotency = IdempotencyManager(
        db_path=tmp_path / "idempotency.db",
        ttl_seconds=24 * 60 * 60,
    )

    audit = AuditLogger(
        db_path=tmp_path / "audit.db",
    )

    return WriteSafety(
        draft_store=draft_store,
        idempotency=idempotency,
        audit=audit,
    )


@pytest.mark.asyncio
async def test_prepare_creates_draft_and_audit(safety):
    draft = await safety.prepare(
        operation="jira_create_issue",
        payload={
            "project_key": "SP",
            "summary": "Test bug",
        },
        preview={
            "fields": {
                "summary": "Test bug",
            }
        },
        request_id="req-001",
    )

    assert draft.operation == "jira_create_issue"
    assert draft.status == "pending"
    assert draft.payload["summary"] == "Test bug"

    logs = await safety.audit.recent(
        operation="jira_create_issue"
    )

    assert len(logs) == 1
    assert logs[0]["status"] == "prepared"
    assert logs[0]["action"] == "prepare"
    assert logs[0]["request_id"] == "req-001"


@pytest.mark.asyncio
async def test_confirm_false_does_not_execute(safety):
    draft = await safety.prepare(
        operation="jira_create_issue",
        payload={"summary": "Test"},
        preview={"summary": "Test"},
    )

    calls = 0

    async def executor(_draft):
        nonlocal calls
        calls += 1
        return {"issue_key": "SP-999"}

    with pytest.raises(ConfirmationRequiredError):
        await safety.execute(
            draft_id=draft.draft_id,
            expected_operation="jira_create_issue",
            confirm=False,
            executor=executor,
        )

    assert calls == 0

    stored = safety.draft_store.get_draft(
        draft.draft_id
    )
    assert stored.status == "pending"


@pytest.mark.asyncio
async def test_confirm_true_executes_once_and_replays(safety):
    draft = await safety.prepare(
        operation="jira_create_issue",
        payload={"summary": "Test"},
        preview={"summary": "Test"},
    )

    calls = 0

    async def executor(_draft):
        nonlocal calls
        calls += 1
        return {
            "issue_key": "SP-999",
            "issue_id": "999",
            "self_url": None,
        }

    first = await safety.execute(
        draft_id=draft.draft_id,
        expected_operation="jira_create_issue",
        confirm=True,
        executor=executor,
    )

    second = await safety.execute(
        draft_id=draft.draft_id,
        expected_operation="jira_create_issue",
        confirm=True,
        executor=executor,
    )

    assert calls == 1

    assert first.replayed is False
    assert first.result["issue_key"] == "SP-999"

    assert second.replayed is True
    assert second.result == first.result

    stored = safety.draft_store.get_draft(
        draft.draft_id
    )

    assert stored.status == "confirmed"
    assert stored.result == first.result


@pytest.mark.asyncio
async def test_wrong_operation_is_rejected(safety):
    draft = await safety.prepare(
        operation="jira_update_issue",
        payload={"issue_key": "SP-123"},
        preview={"issue_key": "SP-123"},
    )

    async def executor(_draft):
        return {"ok": True}

    with pytest.raises(DraftOperationMismatchError):
        await safety.execute(
            draft_id=draft.draft_id,
            expected_operation="jira_delete_issue",
            confirm=True,
            executor=executor,
        )


@pytest.mark.asyncio
async def test_expired_draft_is_rejected(tmp_path):
    draft_store = DraftStore(
        db_path=str(tmp_path / "expired_drafts.db"),
        ttl_hours=-1.0,
    )

    idempotency = IdempotencyManager(
        db_path=tmp_path / "expired_idempotency.db",
    )

    audit = AuditLogger(
        db_path=tmp_path / "expired_audit.db",
    )

    safety = WriteSafety(
        draft_store=draft_store,
        idempotency=idempotency,
        audit=audit,
    )

    draft_id = draft_store.create_draft(
        operation="jira_update_issue",
        payload={"issue_key": "SP-123"},
    )

    async def executor(_draft):
        return {"updated": True}

    with pytest.raises(DraftExpiredError):
        await safety.execute(
            draft_id=draft_id,
            expected_operation="jira_update_issue",
            confirm=True,
            executor=executor,
        )


@pytest.mark.asyncio
async def test_executor_error_is_audited(safety):
    draft = await safety.prepare(
        operation="jira_update_issue",
        payload={"issue_key": "SP-123"},
        preview={"issue_key": "SP-123"},
        request_id="req-error",
        issue_key="SP-123",
    )

    async def executor(_draft):
        raise RuntimeError("simulated Jira failure")

    with pytest.raises(
        RuntimeError,
        match="simulated Jira failure",
    ):
        await safety.execute(
            draft_id=draft.draft_id,
            expected_operation="jira_update_issue",
            confirm=True,
            executor=executor,
            request_id="req-error",
            issue_key="SP-123",
        )

    logs = await safety.audit.recent(
        operation="jira_update_issue"
    )

    assert any(
        row["status"] == "error"
        and row["action"] == "confirm_execute"
        for row in logs
    )

    stored = safety.draft_store.get_draft(
        draft.draft_id
    )

    assert stored.status == "pending"


@pytest.mark.asyncio
async def test_idempotency_cache_prevents_executor_call(safety):
    draft = await safety.prepare(
        operation="jira_create_issue",
        payload={"summary": "Cached operation"},
        preview={"summary": "Cached operation"},
    )

    cached_result = {
        "issue_key": "SP-777",
        "issue_id": "777",
        "self_url": None,
    }

    idempotency_key = (
        f"jira_create_issue:{draft.draft_id}"
    )

    await safety.idempotency.store(
        idempotency_key=idempotency_key,
        operation="jira_create_issue",
        result=cached_result,
    )

    calls = 0

    async def executor(_draft):
        nonlocal calls
        calls += 1
        return {
            "issue_key": "SHOULD-NOT-HAPPEN",
        }

    execution = await safety.execute(
        draft_id=draft.draft_id,
        expected_operation="jira_create_issue",
        confirm=True,
        executor=executor,
    )

    assert calls == 0
    assert execution.replayed is True
    assert execution.result == cached_result

    stored = safety.draft_store.get_draft(
        draft.draft_id
    )

    assert stored.status == "confirmed"
    assert stored.result == cached_result
