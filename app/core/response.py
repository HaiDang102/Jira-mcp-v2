from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from app.core.errors import AppError
from app.config import settings

SERVER_NAME = "jira-mcp"


def new_request_id() -> str:
    return f"req_{uuid.uuid4().hex[:12]}"


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _base_meta(
    request_id: str | None,
    project: str | None,
) -> dict[str, Any]:
    meta: dict[str, Any] = {
        "request_id": request_id or new_request_id(),
        "timestamp": _timestamp(),
        "server": SERVER_NAME,
    }
    if project:
        meta["project"] = project
    return meta


def ok_response(
    operation: str,
    data: Any,
    *,
    request_id: str | None = None,
    project: str | None = None,
    extra_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Build the standard success envelope:

    {
      "ok": true,
      "operation": "jira.get_issue",
      "data": {...},
      "meta": {"request_id": ..., "timestamp": ..., "server": ..., "project": ...}
    }
    """

    meta = _base_meta(request_id, project)
    if extra_meta:
        meta.update(extra_meta)

    return {
        "ok": True,
        "operation": operation,
        "data": data,
        "meta": meta,
    }


def err_response(
    operation: str,
    error: AppError | Exception,
    *,
    request_id: str | None = None,
    project: str | None = None,
    extra_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Build the standard error envelope:

    {
      "ok": false,
      "operation": "jira.update_issue",
      "error": {"code": "ISSUE_NOT_FOUND", "message": "...", "retryable": false},
      "meta": {"request_id": ..., ...}
    }
    """

    if isinstance(error, AppError):
        code = error.code
        message = error.message
        retryable = error.retryable
        details = error.details
    else:
        code = "UNKNOWN_ERROR"
        message = str(error)
        retryable = False
        details = {}

    meta = _base_meta(request_id, project)
    if extra_meta:
        meta.update(extra_meta)

    error_payload: dict[str, Any] = {
        "code": code,
        "message": message,
        "retryable": retryable,
    }
    if details:
        error_payload["details"] = details

    return {
        "ok": False,
        "operation": operation,
        "error": error_payload,
        "meta": meta,
    }
