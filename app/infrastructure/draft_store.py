from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator

from app.config import settings


# ============================================================
# ERRORS
# ============================================================


class DraftStoreError(Exception):
    """Base exception for DraftStore infrastructure errors."""


class DraftNotFoundError(DraftStoreError):
    """Raised when a draft_id does not exist."""


class DraftExpiredError(DraftStoreError):
    """Raised when a pending draft has exceeded its TTL."""


class DraftAlreadyConfirmedError(DraftStoreError):
    """
    Raised when confirmation conflicts with an already confirmed draft.

    Normal retries using the same idempotency context should return
    the stored result instead of executing the Jira operation again.
    """


# ============================================================
# DATA
# ============================================================


@dataclass
class DraftRecord:
    draft_id: str
    operation: str
    payload: dict[str, Any]
    status: str
    idempotency_key: str | None
    result: dict[str, Any] | None
    created_at: str
    confirmed_at: str | None


# ============================================================
# STORE
# ============================================================


class DraftStore:
    """
    SQLite-backed storage for WRITE/DESTRUCTIVE operation drafts.

    Flow:

        PREPARE
            ↓
        create_draft()
            ↓
        REVIEW
            ↓
        get_draft()
            ↓
        CONFIRM / EXECUTE
            ↓
        mark_confirmed()

    The stored Jira result allows confirm requests to be retried
    without executing the same Jira operation multiple times.
    """

    def __init__(
        self,
        db_path: str | None = None,
        ttl_hours: float = 24.0,
    ) -> None:
        self.db_path = db_path or getattr(
            settings,
            "draft_store_path",
            "jira_mcp_drafts.db",
        )
        self.ttl_hours = ttl_hours

        Path(self.db_path).parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self._init_schema()

    # ========================================================
    # CONNECTION
    # ========================================================

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row

        try:
            yield conn
            conn.commit()

        except Exception:
            conn.rollback()
            raise

        finally:
            conn.close()

    # ========================================================
    # SCHEMA
    # ========================================================

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS drafts (
                    draft_id TEXT PRIMARY KEY,
                    operation TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    idempotency_key TEXT,
                    result_json TEXT,
                    created_at TEXT NOT NULL,
                    confirmed_at TEXT
                )
                """
            )

            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_drafts_idempotency_key
                ON drafts (idempotency_key)
                """
            )

    # ========================================================
    # PREPARE
    # ========================================================

    def create_draft(
        self,
        operation: str,
        payload: dict[str, Any],
        idempotency_key: str | None = None,
    ) -> str:
        """
        Persist a new operation draft.

        This method NEVER calls Jira.

        If an idempotency key already identifies an existing draft
        for the same operation, reuse that draft instead of creating
        another one.
        """

        if not operation.strip():
            raise ValueError("operation must not be empty.")

        if idempotency_key:
            existing = self._find_by_idempotency_key(
                operation=operation,
                idempotency_key=idempotency_key,
            )

            if existing is not None:
                return existing.draft_id

        draft_id = uuid.uuid4().hex[:12]
        now = datetime.now(timezone.utc).isoformat()

        payload_json = json.dumps(
            payload,
            ensure_ascii=False,
        )

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO drafts (
                    draft_id,
                    operation,
                    payload_json,
                    status,
                    idempotency_key,
                    result_json,
                    created_at,
                    confirmed_at
                )
                VALUES (?, ?, ?, 'pending', ?, NULL, ?, NULL)
                """,
                (
                    draft_id,
                    operation,
                    payload_json,
                    idempotency_key,
                    now,
                ),
            )

        return draft_id

    # ========================================================
    # REVIEW
    # ========================================================

    def get_draft(
        self,
        draft_id: str,
    ) -> DraftRecord:
        """
        Fetch a draft for review or confirmation.

        Raises:
            DraftNotFoundError
            DraftExpiredError
        """

        if not draft_id.strip():
            raise ValueError("draft_id must not be empty.")

        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT *
                FROM drafts
                WHERE draft_id = ?
                """,
                (draft_id,),
            ).fetchone()

        if row is None:
            raise DraftNotFoundError(
                f"Draft '{draft_id}' does not exist."
            )

        record = self._row_to_record(row)

        if (
            record.status == "pending"
            and self._is_expired(record)
        ):
            raise DraftExpiredError(
                f"Draft '{draft_id}' has expired. "
                "Please prepare a new draft."
            )

        return record

    # ========================================================
    # CONFIRM
    # ========================================================

    def mark_confirmed(
        self,
        draft_id: str,
        result: dict[str, Any],
    ) -> None:
        """
        Mark a draft as confirmed and persist the Jira result.

        The stored result can later be returned for a repeated
        confirmation instead of calling Jira again.
        """

        if not draft_id.strip():
            raise ValueError("draft_id must not be empty.")

        now = datetime.now(timezone.utc).isoformat()

        result_json = json.dumps(
            result,
            ensure_ascii=False,
        )

        with self._connect() as conn:
            cursor = conn.execute(
                """
                UPDATE drafts
                SET
                    status = 'confirmed',
                    result_json = ?,
                    confirmed_at = ?
                WHERE draft_id = ?
                """,
                (
                    result_json,
                    now,
                    draft_id,
                ),
            )

            if cursor.rowcount == 0:
                raise DraftNotFoundError(
                    f"Draft '{draft_id}' does not exist."
                )

    # ========================================================
    # HELPERS
    # ========================================================

    def _find_by_idempotency_key(
        self,
        operation: str,
        idempotency_key: str,
    ) -> DraftRecord | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT *
                FROM drafts
                WHERE operation = ?
                  AND idempotency_key = ?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (
                    operation,
                    idempotency_key,
                ),
            ).fetchone()

        if row is None:
            return None

        return self._row_to_record(row)

    def _is_expired(
        self,
        record: DraftRecord,
    ) -> bool:
        created_at = datetime.fromisoformat(
            record.created_at
        )

        expires_at = created_at + timedelta(
            hours=self.ttl_hours
        )

        return datetime.now(timezone.utc) > expires_at

    @staticmethod
    def _row_to_record(
        row: sqlite3.Row,
    ) -> DraftRecord:
        result_json = row["result_json"]

        return DraftRecord(
            draft_id=row["draft_id"],
            operation=row["operation"],
            payload=json.loads(
                row["payload_json"]
            ),
            status=row["status"],
            idempotency_key=row["idempotency_key"],
            result=(
                json.loads(result_json)
                if result_json
                else None
            ),
            created_at=row["created_at"],
            confirmed_at=row["confirmed_at"],
        )


# ============================================================
# FACTORY / SINGLETON
# ============================================================


_store_singleton: DraftStore | None = None


def create_draft_store() -> DraftStore:
    """Create or reuse the application-wide DraftStore."""

    global _store_singleton

    if _store_singleton is None:
        _store_singleton = DraftStore()

    return _store_singleton