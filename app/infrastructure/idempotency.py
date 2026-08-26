from __future__ import annotations

"""
Idempotency layer for WRITE tools (mục 9 trong sơ đồ).

Cách dùng:
    manager = IdempotencyManager()
    cached = await manager.check(idempotency_key)
    if cached is not None:
        return cached  # trả về kết quả cũ, KHÔNG gọi Jira lại

    result = await do_the_actual_write(...)
    await manager.store(idempotency_key, result)
    return result

Mỗi request WRITE nên cung cấp idempotency_key (ví dụ:
"bug-SAALEM-login-001"). Key được lưu kèm kết quả trong bảng
idempotency_log, TTL mặc định 24h.
"""

import json
import sqlite3
import time
from pathlib import Path
from typing import Any


DEFAULT_DB_PATH = Path("jira_mcp_idempotency.db")
DEFAULT_TTL_SECONDS = 24 * 60 * 60  # 24h, theo mục 9 trong sơ đồ


class IdempotencyManager:
    def __init__(
        self,
        db_path: Path | str = DEFAULT_DB_PATH,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
    ) -> None:
        self.db_path = str(db_path)
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

    async def check(self, idempotency_key: str) -> Any | None:
        """
        Trả về kết quả đã lưu nếu key đã tồn tại và chưa hết TTL,
        ngược lại trả về None (nghĩa là: thực thi và lưu kết quả mới).
        """
        if not idempotency_key:
            return None

        with self._connect() as conn:
            self._purge_expired(conn)
            conn.commit()

            row = conn.execute(
                "SELECT result_json FROM idempotency_log "
                "WHERE idempotency_key = ?",
                (idempotency_key,),
            ).fetchone()

            if row is None:
                return None

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
            conn.execute(
                """
                INSERT INTO idempotency_log
                    (idempotency_key, operation, result_json, created_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(idempotency_key) DO UPDATE SET
                    operation = excluded.operation,
                    result_json = excluded.result_json,
                    created_at = excluded.created_at
                """,
                (
                    idempotency_key,
                    operation,
                    json.dumps(result, ensure_ascii=False, default=str),
                    time.time(),
                ),
            )
            conn.commit()
