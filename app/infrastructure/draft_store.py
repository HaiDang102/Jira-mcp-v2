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
    """Base exception for draft store errors."""


class DraftNotFoundError(DraftStoreError):
    """Raised when a draft_id does not exist or has expired."""


class DraftExpiredError(DraftStoreError):
    """Raised when a draft exists but its TTL has passed."""


class DraftAlreadyConfirmedError(DraftStoreError):
    """
    Raised only when the caller explicitly needs to know a draft
    was already confirmed under a DIFFERENT idempotency_key than
    the one supplied. Normal re-confirm with the same key is NOT
    an error — see IdempotencyResult.
    """


# ============================================================
# DATA
# ============================================================

@dataclass
class DraftRecord:
    draft_id: str
    operation: str
    payload: dict[str, Any]
    status: str  # "pending" | "confirmed"
    idempotency_key: str | None
    result: dict[str, Any] | None
    created_at: str
    confirmed_at: str | None


# ============================================================
# STORE
# ============================================================

class DraftStore:
    """
    Persist WRITE/DESTRUCTIVE operation drafts so that:
    - Prepare writes a draft and returns a draft_id (no Jira call yet)
    - Confirm looks up the draft, calls Jira exactly once, and
      remembers the result so retries of the same request don't
      create duplicate issues (mục 9 — Idempotency).

    SQLite file, matching "Draft Store (SQLite/Redis)" trong sơ đồ.
    Redis có thể thay thế sau nếu cần multi-instance deployment.
    """

    def __init__(
        self,
        db_path: str | None = None,
        ttl_hours: float = 24.0,
    ) -> None:
        self.db_path = db_path or getattr(
            settings, "draft_store_path", "jira_mcp_drafts.db"
        )
        self.ttl_hours = ttl_hours

        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

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
        Save a new draft. Does NOT call Jira. Returns draft_id.

        If idempotency_key is provided and a CONFIRMED draft with
        the same key + operation already exists, its draft_id is
        returned instead of creating a new one — this lets Prepare
        itself be safely retried.
        """

        if idempotency_key:
            existing = self._find_by_idempotency_key(
                operation, idempotency_key
            )
            if existing is not None:
                return existing.draft_id

        draft_id = uuid.uuid4().hex[:12]
        now = datetime.now(timezone.utc).isoformat()

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO drafts (
                    draft_id, operation, payload_json, status,
                    idempotency_key, result_json, created_at, confirmed_at
                ) VALUES (?, ?, ?, 'pending', ?, NULL, ?, NULL)
                """,
                (
                    draft_id,
                    operation,
                    json.dumps(payload),
                    idempotency_key,
                    now,
                ),
            )

        return draft_id

    # ========================================================
    # REVIEW / GET
    # ========================================================

    def get_draft(self, draft_id: str) -> DraftRecord:
        """
        Fetch a draft for review or confirmation.
        Raises DraftNotFoundError / DraftExpiredError as needed.
        """

        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM drafts WHERE draft_id = ?",
                (draft_id,),
            ).fetchone()

        if row is None:
            raise DraftNotFoundError(
                f"Draft '{draft_id}' does not exist."
            )

        record = self._row_to_record(row)

        if record.status == "pending" and self._is_expired(record):
            raise DraftExpiredError(
                f"Draft '{draft_id}' has expired. "
                "Please prepare a new draft."
            )

        return record

    # ========================================================
    # CONFIRM / EXECUTE
    # ========================================================

    def mark_confirmed(
        self,
        draft_id: str,
        result: dict[str, Any],
    ) -> None:
        """
        Mark a draft as confirmed and store the Jira result, so a
        retried confirm call returns the same result instead of
        re-calling Jira (idempotency on the EXECUTE step itself).
        """

        now = datetime.now(timezone.utc).isoformat()

        with self._connect() as conn:
            conn.execute(
                """
                UPDATE drafts
                SET status = 'confirmed',
                    result_json = ?,
                    confirmed_at = ?
                WHERE draft_id = ?
                """,
                (json.dumps(result), now, draft_id),
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
                SELECT * FROM drafts
                WHERE operation = ? AND idempotency_key = ?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (operation, idempotency_key),
            ).fetchone()

        if row is None:
            return None

        return self._row_to_record(row)

    def _is_expired(self, record: DraftRecord) -> bool:
        created = datetime.fromisoformat(record.created_at)
        return datetime.now(timezone.utc) > created + timedelta(
            hours=self.ttl_hours
        )

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> DraftRecord:
        return DraftRecord(
            draft_id=row["draft_id"],
            operation=row["operation"],
            payload=json.loads(row["payload_json"]),
            status=row["status"],
            idempotency_key=row["idempotency_key"],
            result=(
                json.loads(row["result_json"])
                if row["result_json"]
                else None
            ),
            created_at=row["created_at"],
            confirmed_at=row["confirmed_at"],
        )


_store_singleton: DraftStore | None = None


def create_draft_store() -> DraftStore:
    """
    Create (or reuse) the application-wide DraftStore instance.
    """

    global _store_singleton

    if _store_singleton is None:
        _store_singleton = DraftStore()

    return _store_singleton