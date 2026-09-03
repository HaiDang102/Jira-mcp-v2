from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from app.infrastructure.audit_logger import AuditLogger
from app.infrastructure.draft_store import DraftRecord, DraftStore
from app.infrastructure.idempotency import IdempotencyManager


class SafetyError(Exception):
    """Base error for the WRITE/DESTRUCTIVE safety layer."""


class ConfirmationRequiredError(SafetyError):
    pass


class DraftOperationMismatchError(SafetyError):
    pass


@dataclass
class SafetyExecution:
    """Result of a safety-controlled execution."""

    result: dict[str, Any]
    replayed: bool = False


class WriteSafety:
    """
    Central safety coordinator for Jira WRITE/DESTRUCTIVE operations.

    Flow:
        Prepare -> Review -> Confirm -> Execute

    Responsibilities:
    - create/retrieve drafts
    - verify draft operation
    - enforce explicit confirmation
    - return stored result for an already-confirmed draft
    - best-effort idempotency for confirm retries
    - audit prepare / execute / replay / error
    """

    def __init__(
        self,
        draft_store: DraftStore,
        idempotency: IdempotencyManager,
        audit: AuditLogger,
    ) -> None:
        self.draft_store = draft_store
        self.idempotency = idempotency
        self.audit = audit

    async def prepare(
        self,
        *,
        operation: str,
        payload: dict[str, Any],
        preview: dict[str, Any],
        request_id: str | None = None,
        issue_key: str | None = None,
    ) -> DraftRecord:
        draft_id = self.draft_store.create_draft(
            operation=operation,
            payload=payload,
        )
        draft = self.draft_store.get_draft(draft_id)

        await self.audit.log(
            operation=operation,
            request_id=request_id,
            issue_key=issue_key,
            action="prepare",
            status="prepared",
            details={
                "draft_id": draft_id,
                "preview": preview,
            },
        )
        return draft

    async def execute(
        self,
        *,
        draft_id: str,
        expected_operation: str,
        confirm: bool,
        executor: Callable[[DraftRecord], Awaitable[dict[str, Any]]],
        request_id: str | None = None,
        issue_key: str | None = None,
    ) -> SafetyExecution:
        draft = self.draft_store.get_draft(draft_id)

        if draft.operation != expected_operation:
            raise DraftOperationMismatchError(
                f"Draft '{draft_id}' belongs to operation "
                f"'{draft.operation}', not '{expected_operation}'."
            )

        # A confirmed draft is safe to replay even when confirm is omitted:
        # no Jira write occurs; the stored result is returned.
        if draft.status == "confirmed":
            await self.audit.log(
                operation=expected_operation,
                request_id=request_id,
                issue_key=issue_key,
                action="replay",
                status="ok",
                details={"draft_id": draft_id},
            )
            return SafetyExecution(
                result=draft.result or {},
                replayed=True,
            )

        if not confirm:
            raise ConfirmationRequiredError(
                "Explicit confirm=true is required before executing "
                "this Jira write operation."
            )

        idempotency_key = f"{expected_operation}:{draft_id}"

        cached = await self.idempotency.check(
            idempotency_key=idempotency_key,
            operation=expected_operation,
        )
        if cached is not None:
            self.draft_store.mark_confirmed(draft_id, cached)
            await self.audit.log(
                operation=expected_operation,
                request_id=request_id,
                issue_key=issue_key,
                action="idempotent_replay",
                status="ok",
                details={"draft_id": draft_id},
            )
            return SafetyExecution(result=cached, replayed=True)

        try:
            result = await executor(draft)

            await self.idempotency.store(
                idempotency_key=idempotency_key,
                operation=expected_operation,
                result=result,
            )
            self.draft_store.mark_confirmed(draft_id, result)

            await self.audit.log(
                operation=expected_operation,
                request_id=request_id,
                issue_key=issue_key,
                action="confirm_execute",
                status="ok",
                details={"draft_id": draft_id},
            )
            return SafetyExecution(result=result, replayed=False)

        except Exception as exc:
            await self.audit.log(
                operation=expected_operation,
                request_id=request_id,
                issue_key=issue_key,
                action="confirm_execute",
                status="error",
                details={
                    "draft_id": draft_id,
                    "error": str(exc),
                },
            )
            raise
