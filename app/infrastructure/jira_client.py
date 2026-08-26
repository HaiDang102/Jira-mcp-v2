from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from app.config import settings


logger = logging.getLogger(__name__)


class JiraClientError(Exception):
    """Base exception for Jira client errors."""


class JiraAuthenticationError(JiraClientError):
    """Raised when Jira authentication fails."""


class JiraPermissionError(JiraClientError):
    """Raised when Jira returns 403."""


class JiraNotFoundError(JiraClientError):
    """Raised when Jira resource does not exist."""


class JiraRateLimitError(JiraClientError):
    """Raised when Jira rate-limits the request."""


class JiraServerError(JiraClientError):
    """Raised when Jira returns a 5xx response."""


class JiraClient:
    """
    Low-level asynchronous Jira REST API client.

    Responsibilities:
    - HTTP communication
    - Authentication
    - Timeout
    - Basic error mapping

    This class MUST NOT contain business logic.
    """

    def __init__(
        self,
        base_url: str,
        token: str,
        timeout: float = 30.0,
        connect_timeout: float = 10.0,
        max_retries: int = 3,
        backoff_base: float = 0.5,
        backoff_max: float = 8.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self.backoff_max = backoff_max

        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            timeout=httpx.Timeout(
                timeout,
                connect=connect_timeout,
            ),
        )

    async def close(self) -> None:
        """Close HTTP connection pool."""
        await self._client.aclose()

    async def __aenter__(self) -> "JiraClient":
        return self

    async def __aexit__(
        self,
        exc_type: Any,
        exc_value: Any,
        traceback: Any,
    ) -> None:
        await self.close()

    async def request(
        self,
        method: str,
        path: str,
        **kwargs: Any,
    ) -> Any:
        """
        Send a request to Jira REST API.

        Retries automatically on:
        - 429 (rate limit) — honors Retry-After header when present
        - 5xx (server error)
        - Transient connection/timeout errors

        Does NOT retry on 4xx client errors (401/403/404/400...),
        since those will not succeed on retry.
        """

        attempt = 0

        while True:
            try:
                response = await self._client.request(
                    method=method,
                    url=path,
                    **kwargs,
                )

            except (
                httpx.TimeoutException,
                httpx.RequestError,
            ) as exc:
                if attempt >= self.max_retries:
                    raise JiraClientError(
                        f"Jira connection failed after "
                        f"{attempt + 1} attempt(s): {exc}"
                    ) from exc

                await self._sleep_backoff(attempt)
                attempt += 1
                continue

            try:
                self._raise_for_status(response)

            except (
                JiraRateLimitError,
                JiraServerError,
            ) as exc:
                if attempt >= self.max_retries:
                    raise

                retry_after = self._parse_retry_after(response)

                logger.warning(
                    "Jira request retry %s/%s for %s %s (%s)",
                    attempt + 1,
                    self.max_retries,
                    method,
                    path,
                    exc,
                )

                await self._sleep_backoff(
                    attempt,
                    retry_after,
                )

                attempt += 1
                continue

            if not response.content:
                return None

            content_type = response.headers.get(
                "content-type",
                "",
            )

            if "application/json" in content_type:
                return response.json()

            return response.text

    async def _sleep_backoff(
        self,
        attempt: int,
        retry_after: float | None = None,
    ) -> None:
        """
        Sleep before the next retry attempt.

        Uses the server-provided Retry-After value when given,
        otherwise falls back to exponential backoff.
        """

        if retry_after is not None:
            delay = retry_after
        else:
            delay = min(
                self.backoff_base * (2 ** attempt),
                self.backoff_max,
            )

        await asyncio.sleep(delay)

    @staticmethod
    def _parse_retry_after(
        response: httpx.Response,
    ) -> float | None:
        """
        Parse the Retry-After header (seconds) from a 429 response.
        """

        value = response.headers.get("Retry-After")

        if value is None:
            return None

        try:
            return float(value)
        except ValueError:
            return None

    async def get(
        self,
        path: str,
        **kwargs: Any,
    ) -> Any:
        return await self.request(
            "GET",
            path,
            **kwargs,
        )

    async def post(
        self,
        path: str,
        **kwargs: Any,
    ) -> Any:
        return await self.request(
            "POST",
            path,
            **kwargs,
        )

    async def put(
        self,
        path: str,
        **kwargs: Any,
    ) -> Any:
        return await self.request(
            "PUT",
            path,
            **kwargs,
        )

    async def delete(
        self,
        path: str,
        **kwargs: Any,
    ) -> Any:
        return await self.request(
            "DELETE",
            path,
            **kwargs,
        )

    @staticmethod
    def _raise_for_status(
        response: httpx.Response,
    ) -> None:

        status = response.status_code

        if status == 401:
            raise JiraAuthenticationError(
                "Jira authentication failed."
            )

        if status == 403:
            raise JiraPermissionError(
                "Jira permission denied."
            )

        if status == 404:
            raise JiraNotFoundError(
                "Jira resource not found."
            )

        if status == 429:
            raise JiraRateLimitError(
                "Jira rate limit exceeded."
            )

        if 500 <= status <= 599:
            raise JiraServerError(
                f"Jira server error: HTTP {status}."
            )

        if status >= 400:
            body = response.text[:500]

            raise JiraClientError(
                f"Jira API error: HTTP {status}: {body}"
            )


def create_jira_client() -> JiraClient:
    """
    Create JiraClient from application configuration.
    """

    return JiraClient(
        base_url=settings.jira_base_url,
        token=settings.jira_pat,
        timeout=settings.jira_timeout,
        connect_timeout=settings.jira_connect_timeout,
        max_retries=settings.jira_max_retries,
    )