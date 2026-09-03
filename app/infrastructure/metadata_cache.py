from __future__ import annotations

"""
In-memory TTL cache for Jira metadata that changes infrequently.

The cache is application-scoped and shares the same JiraClient used by
the MCP services. It is intentionally simple: one process, in-memory,
TTL-based caching.
"""

import time
from typing import Any

from app.infrastructure.jira_client import JiraClient


DEFAULT_TTL_SECONDS = 60 * 60  # 1 hour


class MetadataCache:
    def __init__(
        self,
        client: JiraClient,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
    ) -> None:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be greater than 0.")

        self._client = client
        self._ttl = ttl_seconds
        self._store: dict[str, tuple[float, Any]] = {}

    def _get_cached(self, key: str) -> Any | None:
        entry = self._store.get(key)

        if entry is None:
            return None

        expires_at, value = entry

        if time.time() >= expires_at:
            self._store.pop(key, None)
            return None

        return value

    def _set_cached(self, key: str, value: Any) -> None:
        self._store[key] = (
            time.time() + self._ttl,
            value,
        )

    def invalidate(self, key: str | None = None) -> None:
        """
        Remove one cache entry, or clear the entire cache when key=None.
        """
        if key is None:
            self._store.clear()
            return

        self._store.pop(key, None)

    async def get_project_fields(
        self,
        project_key: str,
    ) -> Any:
        normalized_key = project_key.strip().upper()

        if not normalized_key:
            raise ValueError("project_key cannot be empty.")

        cache_key = f"fields:{normalized_key}"
        cached = self._get_cached(cache_key)

        if cached is not None:
            return cached

        data = await self._client.get(
            "/rest/api/2/issue/createmeta",
            params={
                "projectKeys": normalized_key,
                "expand": "projects.issuetypes.fields",
            },
        )

        self._set_cached(cache_key, data)
        return data

    async def get_project_statuses(
        self,
        project_key: str,
    ) -> Any:
        """
        Return Jira project statuses grouped by issue type.

        Jira Server/Data Center exposes this through:
            GET /rest/api/2/project/{projectKey}/statuses
        """
        normalized_key = project_key.strip().upper()

        if not normalized_key:
            raise ValueError("project_key cannot be empty.")

        cache_key = f"statuses:{normalized_key}"
        cached = self._get_cached(cache_key)

        if cached is not None:
            return cached

        data = await self._client.get(
            f"/rest/api/2/project/{normalized_key}/statuses"
        )

        self._set_cached(cache_key, data)
        return data
