from __future__ import annotations

from typing import Any

from app.infrastructure.jira_client import (
    JiraAuthenticationError,
    JiraClientError,
    JiraNotFoundError,
    JiraPermissionError,
    JiraRateLimitError,
    JiraServerError,
)


class ErrorCode:
    """Stable machine-readable error codes used in response.meta.error.code."""

    VALIDATION_ERROR = "VALIDATION_ERROR"
    ISSUE_NOT_FOUND = "ISSUE_NOT_FOUND"
    PROJECT_NOT_FOUND = "PROJECT_NOT_FOUND"
    NOT_FOUND = "NOT_FOUND"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    AUTH_FAILED = "AUTH_FAILED"
    RATE_LIMITED = "RATE_LIMITED"
    SERVER_ERROR = "SERVER_ERROR"
    UNKNOWN_ERROR = "UNKNOWN_ERROR"

    # Safety / confirmation layer
    CONFIRMATION_REQUIRED = "CONFIRMATION_REQUIRED"
    DRAFT_NOT_FOUND = "DRAFT_NOT_FOUND"
    DRAFT_EXPIRED = "DRAFT_EXPIRED"
    DRAFT_ALREADY_EXECUTED = "DRAFT_ALREADY_EXECUTED"

    # Idempotency
    IDEMPOTENCY_KEY_MISSING = "IDEMPOTENCY_KEY_MISSING"


class AppError(Exception):
    """
    Base application error. Every AppError knows:
    - a stable `code` (see ErrorCode)
    - whether the failed operation is safe to `retryable`
    - optional `details` for extra machine-readable context
    """

    code: str = ErrorCode.UNKNOWN_ERROR
    retryable: bool = False

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        retryable: bool | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code
        if retryable is not None:
            self.retryable = retryable
        self.details = details or {}


class ValidationError(AppError):
    code = ErrorCode.VALIDATION_ERROR
    retryable = False


class NotFoundError(AppError):
    code = ErrorCode.NOT_FOUND
    retryable = False


class PermissionDeniedError(AppError):
    code = ErrorCode.PERMISSION_DENIED
    retryable = False


class ConfirmationRequiredError(AppError):
    """
    Raised by a WRITE/DESTRUCTIVE tool when called without an approved,
    confirmed draft. The tool response should surface draft_id so the
    caller can review then confirm.
    """

    code = ErrorCode.CONFIRMATION_REQUIRED
    retryable = False


class DraftNotFoundError(AppError):
    code = ErrorCode.DRAFT_NOT_FOUND
    retryable = False


class DraftExpiredError(AppError):
    code = ErrorCode.DRAFT_EXPIRED
    retryable = False


class DraftAlreadyExecutedError(AppError):
    code = ErrorCode.DRAFT_ALREADY_EXECUTED
    retryable = False


def map_jira_exception(exc: Exception) -> AppError:
    """
    Translate a low-level JiraClientError (from infrastructure/jira_client.py)
    into an AppError with a stable code + correct retryable flag, so tools
    never need to know about httpx/Jira specifics.
    """

    if isinstance(exc, JiraNotFoundError):
        return NotFoundError(str(exc), code=ErrorCode.NOT_FOUND, retryable=False)

    if isinstance(exc, JiraAuthenticationError):
        return AppError(str(exc), code=ErrorCode.AUTH_FAILED, retryable=False)

    if isinstance(exc, JiraPermissionError):
        return PermissionDeniedError(
            str(exc), code=ErrorCode.PERMISSION_DENIED, retryable=False
        )

    if isinstance(exc, JiraRateLimitError):
        return AppError(str(exc), code=ErrorCode.RATE_LIMITED, retryable=True)

    if isinstance(exc, JiraServerError):
        return AppError(str(exc), code=ErrorCode.SERVER_ERROR, retryable=True)

    if isinstance(exc, JiraClientError):
        return AppError(str(exc), code=ErrorCode.SERVER_ERROR, retryable=True)

    return AppError(str(exc), code=ErrorCode.UNKNOWN_ERROR, retryable=False)
