from __future__ import annotations

from typing import Any

from app.infrastructure.draft_store import (
    DraftAlreadyConfirmedError,
    DraftExpiredError as DraftStoreExpiredError,
    DraftNotFoundError as DraftStoreNotFoundError,
)
from app.infrastructure.jira_client import (
    JiraAuthenticationError,
    JiraClientError,
    JiraNotFoundError,
    JiraPermissionError,
    JiraRateLimitError,
    JiraServerError,
)


# ============================================================
# ERROR CODES
# ============================================================


class ErrorCode:
    """Stable machine-readable application error codes."""

    # Validation
    VALIDATION_ERROR = "VALIDATION_ERROR"

    # Resource
    ISSUE_NOT_FOUND = "ISSUE_NOT_FOUND"
    PROJECT_NOT_FOUND = "PROJECT_NOT_FOUND"
    NOT_FOUND = "NOT_FOUND"

    # Authentication / authorization
    AUTH_FAILED = "AUTH_FAILED"
    PERMISSION_DENIED = "PERMISSION_DENIED"

    # Jira / infrastructure
    RATE_LIMITED = "RATE_LIMITED"
    JIRA_SERVER_ERROR = "JIRA_SERVER_ERROR"
    JIRA_CLIENT_ERROR = "JIRA_CLIENT_ERROR"

    # Safety / confirmation
    CONFIRMATION_REQUIRED = "CONFIRMATION_REQUIRED"
    DRAFT_NOT_FOUND = "DRAFT_NOT_FOUND"
    DRAFT_EXPIRED = "DRAFT_EXPIRED"
    DRAFT_ALREADY_EXECUTED = "DRAFT_ALREADY_EXECUTED"

    # Idempotency
    IDEMPOTENCY_KEY_MISSING = "IDEMPOTENCY_KEY_MISSING"

    # Fallback
    INTERNAL_ERROR = "INTERNAL_ERROR"


# ============================================================
# BASE APPLICATION ERROR
# ============================================================


class AppError(Exception):
    """
    Base application-level exception.

    Every AppError exposes:
    - code: stable machine-readable error code
    - retryable: whether retry may succeed
    - details: optional structured context
    """

    code: str = ErrorCode.INTERNAL_ERROR
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
        self.code = code if code is not None else self.__class__.code
        self.retryable = (
            retryable
            if retryable is not None
            else self.__class__.retryable
        )
        self.details = details or {}


# ============================================================
# APPLICATION ERRORS
# ============================================================


class ValidationError(AppError):
    code = ErrorCode.VALIDATION_ERROR
    retryable = False


class NotFoundError(AppError):
    code = ErrorCode.NOT_FOUND
    retryable = False


class AuthenticationError(AppError):
    code = ErrorCode.AUTH_FAILED
    retryable = False


class PermissionDeniedError(AppError):
    code = ErrorCode.PERMISSION_DENIED
    retryable = False


class RateLimitError(AppError):
    code = ErrorCode.RATE_LIMITED
    retryable = True


class JiraServerAppError(AppError):
    code = ErrorCode.JIRA_SERVER_ERROR
    retryable = True


class JiraClientAppError(AppError):
    code = ErrorCode.JIRA_CLIENT_ERROR
    retryable = False


# ============================================================
# SAFETY / CONFIRMATION ERRORS
# ============================================================


class ConfirmationRequiredError(AppError):
    code = ErrorCode.CONFIRMATION_REQUIRED
    retryable = False


class DraftNotFoundAppError(AppError):
    code = ErrorCode.DRAFT_NOT_FOUND
    retryable = False


class DraftExpiredAppError(AppError):
    code = ErrorCode.DRAFT_EXPIRED
    retryable = False


class DraftAlreadyExecutedError(AppError):
    code = ErrorCode.DRAFT_ALREADY_EXECUTED
    retryable = False


class IdempotencyKeyMissingError(AppError):
    code = ErrorCode.IDEMPOTENCY_KEY_MISSING
    retryable = False


# ============================================================
# EXCEPTION MAPPING
# ============================================================


def map_exception(exc: Exception) -> AppError:
    """
    Translate lower-level exceptions into stable application errors.

    MCP tools should use this mapper instead of depending directly
    on JiraClient/DraftStore exception details.
    """

    # Already normalized
    if isinstance(exc, AppError):
        return exc

    # -------------------------
    # Draft Store
    # -------------------------

    if isinstance(exc, DraftStoreNotFoundError):
        return DraftNotFoundAppError(str(exc))

    if isinstance(exc, DraftStoreExpiredError):
        return DraftExpiredAppError(str(exc))

    if isinstance(exc, DraftAlreadyConfirmedError):
        return DraftAlreadyExecutedError(str(exc))

    # -------------------------
    # Jira
    # -------------------------

    if isinstance(exc, JiraAuthenticationError):
        return AuthenticationError(str(exc))

    if isinstance(exc, JiraPermissionError):
        return PermissionDeniedError(str(exc))

    if isinstance(exc, JiraNotFoundError):
        return NotFoundError(str(exc))

    if isinstance(exc, JiraRateLimitError):
        return RateLimitError(str(exc))

    if isinstance(exc, JiraServerError):
        return JiraServerAppError(str(exc))

    if isinstance(exc, JiraClientError):
        return JiraClientAppError(str(exc))

    # -------------------------
    # Validation
    # -------------------------

    if isinstance(exc, ValueError):
        return ValidationError(str(exc))

    # -------------------------
    # Unknown
    # -------------------------

    return AppError(
        "An unexpected error occurred.",
        code=ErrorCode.INTERNAL_ERROR,
        retryable=False,
        details={
            "exception_type": type(exc).__name__,
        },
    )


# Backward-compatible alias.
# Có thể bỏ alias này sau khi toàn bộ code chuyển sang map_exception().
def map_jira_exception(exc: Exception) -> AppError:
    return map_exception(exc)