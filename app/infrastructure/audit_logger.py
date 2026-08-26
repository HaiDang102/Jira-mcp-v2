from __future__ import annotations

"""
Audit Log — ghi lại mọi thao tác ai/gì/khi nào/kết quả (mục Infrastructure
Layer trong sơ đồ). Dùng SQLite riêng để không lẫn với draft_store.

Cách dùng trong tool WRITE/DESTRUCTIVE:

    audit = AuditLogger()
    await audit.log(
        operation="jira.update_issue",
        actor=current_user,          # ai gọi
        request_id=request_id,
        issue_key="SP-123",
        action="confirm_execute",
        status="ok",                  # "ok" | "error" | "prepared" | "confirmed"
        details={"fields_changed": ["summary", "priority"]},
    )
"""

import json
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any


DEFAULT_DB_PATH = Path("jira_mcp_audit.db")


class AuditLogger:
    def __init__(self, db_path: Path | str = DEFAULT_DB_PATH) -> None:
        self.db_path = str(db_path)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_log (
                    id          TEXT PRIMARY KEY,
                    ts          REAL NOT NULL,
                    operation   TEXT NOT NULL,
                    actor       TEXT,
                    request_id  TEXT,
                    issue_key   TEXT,
                    action      TEXT,
                    status      TEXT NOT NULL,
                    details_json TEXT
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_audit_operation "
                "ON audit_log(operation)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_audit_issue_key "
                "ON audit_log(issue_key)"
            )
            conn.commit()

    async def log(
        self,
        *,
        operation: str,
        status: str,
        actor: str | None = None,
        request_id: str | None = None,
        issue_key: str | None = None,
        action: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO audit_log
                    (id, ts, operation, actor, request_id,
                     issue_key, action, status, details_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"audit_{uuid.uuid4().hex[:12]}",
                    time.time(),
                    operation,
                    actor,
                    request_id,
                    issue_key,
                    action,
                    status,
                    json.dumps(details or {}, ensure_ascii=False, default=str),
                ),
            )
            conn.commit()

    async def recent(
        self,
        limit: int = 50,
        operation: str | None = None,
    ) -> list[dict[str, Any]]:
        """Dùng để debug / expose qua resource jira://audit nếu cần."""
        query = "SELECT * FROM audit_log"
        params: tuple[Any, ...] = ()

        if operation:
            query += " WHERE operation = ?"
            params = (operation,)

        query += " ORDER BY ts DESC LIMIT ?"
        params = params + (limit,)

        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]
