from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field


T = TypeVar("T")


class ErrorInfo(BaseModel):
    """Chuẩn hóa thông tin lỗi trả về từ MCP."""

    code: str = Field(
        description="Machine-readable error code."
    )

    message: str = Field(
        description="Human-readable error message."
    )

    retryable: bool = Field(
        default=False,
        description="Whether the operation can be safely retried."
    )

    details: dict[str, Any] = Field(
        default_factory=dict,
        description="Optional machine-readable error context."
    )


class ResponseMeta(BaseModel):
    """Metadata dùng chung cho mọi response."""

    request_id: str | None = Field(
        default=None,
        description="Unique request identifier."
    )

    operation: str | None = Field(
        default=None,
        description="Operation performed by the MCP server."
    )


class MCPResponse(BaseModel, Generic[T]):
    """Response envelope chuẩn cho MCP Jira."""

    ok: bool = Field(
        description="Whether the operation succeeded."
    )

    data: T | None = Field(
        default=None,
        description="Operation result."
    )

    error: ErrorInfo | None = Field(
        default=None,
        description="Error information when operation fails."
    )

    meta: ResponseMeta | None = Field(
        default=None,
        description="Response metadata."
    )
