from __future__ import annotations

import pytest

from app.infrastructure.metadata_cache import MetadataCache


class FakeJiraClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict | None]] = []

    async def get(
        self,
        path: str,
        params: dict | None = None,
    ):
        self.calls.append((path, params))

        if path == "/rest/api/2/issue/createmeta":
            return {
                "projects": [
                    {
                        "key": params["projectKeys"],
                        "issuetypes": [],
                    }
                ]
            }

        if path.endswith("/statuses"):
            return [
                {
                    "name": "Bug",
                    "statuses": [],
                }
            ]

        raise AssertionError(f"Unexpected Jira path: {path}")


@pytest.mark.asyncio
async def test_project_fields_are_cached():
    client = FakeJiraClient()
    cache = MetadataCache(client, ttl_seconds=3600)

    first = await cache.get_project_fields("sp")
    second = await cache.get_project_fields("SP")

    assert first == second
    assert len(client.calls) == 1
    assert client.calls[0][0] == "/rest/api/2/issue/createmeta"
    assert client.calls[0][1]["projectKeys"] == "SP"


@pytest.mark.asyncio
async def test_project_statuses_are_cached():
    client = FakeJiraClient()
    cache = MetadataCache(client, ttl_seconds=3600)

    first = await cache.get_project_statuses("sp")
    second = await cache.get_project_statuses("SP")

    assert first == second
    assert len(client.calls) == 1
    assert client.calls[0][0] == "/rest/api/2/project/SP/statuses"


@pytest.mark.asyncio
async def test_invalidate_one_key_forces_reload():
    client = FakeJiraClient()
    cache = MetadataCache(client, ttl_seconds=3600)

    await cache.get_project_fields("SP")
    cache.invalidate("fields:SP")
    await cache.get_project_fields("SP")

    assert len(client.calls) == 2


@pytest.mark.asyncio
async def test_invalidate_all_forces_reload():
    client = FakeJiraClient()
    cache = MetadataCache(client, ttl_seconds=3600)

    await cache.get_project_fields("SP")
    await cache.get_project_statuses("SP")

    cache.invalidate()

    await cache.get_project_fields("SP")
    await cache.get_project_statuses("SP")

    assert len(client.calls) == 4


@pytest.mark.asyncio
async def test_expired_entry_is_reloaded(monkeypatch):
    client = FakeJiraClient()
    cache = MetadataCache(client, ttl_seconds=10)

    clock = {"now": 1000.0}

    monkeypatch.setattr(
        "app.infrastructure.metadata_cache.time.time",
        lambda: clock["now"],
    )

    await cache.get_project_fields("SP")

    clock["now"] = 1009.0
    await cache.get_project_fields("SP")

    assert len(client.calls) == 1

    clock["now"] = 1010.0
    await cache.get_project_fields("SP")

    assert len(client.calls) == 2


def test_invalid_ttl_is_rejected():
    client = FakeJiraClient()

    with pytest.raises(
        ValueError,
        match="ttl_seconds must be greater than 0",
    ):
        MetadataCache(client, ttl_seconds=0)
