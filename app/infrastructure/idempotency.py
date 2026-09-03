from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any

from app.config import PROJECT_ROOT


DEFAULT_DB_PATH = PROJECT_ROOT / "jira_mcp_idempotency.db"
DEFAULT_TTL_SECONDS = 24 * 60 * 60


class IdempotencyConflictError(Exception):
    """Raised when a key is reused for a different operation."""


class IdempotencyManager:
    """SQLite-backed best-effort idempotency cache for Jira WRITE operations."""

    def __init__(
        self,
        db_path: Path | str = DEFAULT_DB_PATH,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
    ) -> None:
        path = Path(db_path)
        if not path.is_absolute():
            path = PROJECT_ROOT / path

        path.parent.mkdir(parents=True, exist_ok=True)

        self.db_path = str(path)
        self.ttl_seconds = ttl_seconds
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS idempotency_log (
                    idempotency_key TEXT PRIMARY KEY,
                    operation       TEXT NOT NULL,
                    result_json     TEXT NOT NULL,
                    created_at      REAL NOT NULL
                )
                """
            )
            conn.commit()

    def _purge_expired(self, conn: sqlite3.Connection) -> None:
        cutoff = time.time() - self.ttl_seconds
        conn.execute(
            "DELETE FROM idempotency_log WHERE created_at < ?",
            (cutoff,),
        )

    async def check(
        self,
        idempotency_key: str,
        operation: str | None = None,
    ) -> Any | None:
        if not idempotency_key:
            return None

        with self._connect() as conn:
            self._purge_expired(conn)

            row = conn.execute(
                """
                SELECT operation, result_json
                FROM idempotency_log
                WHERE idempotency_key = ?
                """,
                (idempotency_key,),
            ).fetchone()
            conn.commit()

        if row is None:
            return None

        if operation is not None and row["operation"] != operation:
            raise IdempotencyConflictError(
                f"Idempotency key '{idempotency_key}' is already "
                f"used by operation '{row['operation']}'."
            )

        return json.loads(row["result_json"])

    async def store(
        self,
        idempotency_key: str,
        operation: str,
        result: Any,
    ) -> None:
        if not idempotency_key:
            return

        with self._connect() as conn:
            existing = conn.execute(
                """
                SELECT operation
                FROM idempotency_log
                WHERE idempotency_key = ?
                """,
                (idempotency_key,),
            ).fetchone()

            if existing is not None and existing["operation"] != operation:
                raise IdempotencyConflictError(
                    f"Idempotency key '{idempotency_key}' is already "
                    f"used by operation '{existing['operation']}'."
                )

            conn.execute(
                """
                INSERT INTO idempotency_log
                    (idempotency_key, operation, result_json, created_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(idempotency_key) DO UPDATE SET
                    result_json = excluded.result_json,
                    created_at = excluded.created_at
                """,
                (
                    idempotency_key,
                    operation,
                    json.dumps(
                        result,
                        ensure_ascii=False,
                        default=str,
                    ),
                    time.time(),
                ),
            )
            conn.commit()
