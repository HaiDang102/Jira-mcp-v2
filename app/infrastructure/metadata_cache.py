from __future__ import annotations

"""
In-memory TTL cache cho metadata ít thay đổi của Jira: fields, issue types,
statuses theo project. Giúp tránh gọi Jira API lặp lại cho dữ liệu gần như
tĩnh (mục Infrastructure Layer trong sơ đồ).

Cách dùng:
    cache = MetadataCache(client)
    fields = await cache.get_project_fields("SP")   # gọi Jira lần đầu, cache 1h
    fields = await cache.get_project_fields("SP")   # lần 2 lấy từ cache, không gọi Jira
"""

import time
from typing import Any

from app.infrastructure.jira_client import JiraClient


DEFAULT_TTL_SECONDS = 60 * 60  # 1h — metadata Jira ít khi đổi trong ngày


class MetadataCache:
    def __init__(
        self,
        client: JiraClient,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
    ) -> None:
        self._client = client
        self._ttl = ttl_seconds
        self._store: dict[str, tuple[float, Any]] = {}

    def _get_cached(self, key: str) -> Any | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        expires_at, value = entry
        if time.time() >= expires_at:
            del self._store[key]
            return None
        return value

    def _set_cached(self, key: str, value: Any) -> None:
        self._store[key] = (time.time() + self._ttl, value)

    def invalidate(self, key: str | None = None) -> None:
        """Xóa 1 key cụ thể, hoặc toàn bộ cache nếu key=None."""
        if key is None:
            self._store.clear()
        else:
            self._store.pop(key, None)

    async def get_project_fields(self, project_key: str) -> Any:
        cache_key = f"fields:{project_key}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        data = await self._client.get(
            "/rest/api/2/issue/createmeta",
            params={
                "projectKeys": project_key,
                "expand": "projects.issuetypes.fields",
            },
        )
        self._set_cached(cache_key, data)
        return data

    async def get_issue_types(self, project_key: str) -> Any:
        cache_key = f"issuetypes:{project_key}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        data = await self._client.get(f"/rest/api/2/project/{project_key}/statuses")
        self._set_cached(cache_key, data)
        return data

    async def get_statuses(self, project_key: str) -> Any:
        cache_key = f"statuses:{project_key}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        data = await self._client.get(f"/rest/api/2/project/{project_key}/statuses")
        self._set_cached(cache_key, data)
        return data
