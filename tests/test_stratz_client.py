from __future__ import annotations

import asyncio

import httpx
import pytest

from app.config import Settings
from app.stratz.client import (
    StratzAuthError,
    StratzBlockedError,
    StratzClient,
    StratzGraphQLError,
    StratzRateLimitError,
)


@pytest.mark.asyncio
async def test_stratz_client_success(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_post(self, url, headers=None, json=None):
        return httpx.Response(200, json={"data": {"ok": True}})

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    client = StratzClient(Settings(stratz_token="token"))
    assert await client.query("query { ok }") == {"ok": True}


@pytest.mark.asyncio
async def test_stratz_client_auth_error(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_post(self, url, headers=None, json=None):
        return httpx.Response(401, json={})

    async def no_sleep(_: float) -> None:
        return None

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    monkeypatch.setattr(asyncio, "sleep", no_sleep)
    with pytest.raises(StratzAuthError):
        await StratzClient(Settings(stratz_token="token")).query("query { ok }")


@pytest.mark.asyncio
async def test_stratz_client_rate_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_post(self, url, headers=None, json=None):
        return httpx.Response(429, json={})

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    with pytest.raises(StratzRateLimitError):
        await StratzClient(Settings(stratz_token="token")).query("query { ok }")


@pytest.mark.asyncio
async def test_stratz_client_cloudflare_challenge(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_post(self, url, headers=None, json=None):
        return httpx.Response(403, headers={"content-type": "text/html"}, text="Just a moment")

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    with pytest.raises(StratzBlockedError):
        await StratzClient(Settings(stratz_token="token")).query("query { ok }")


@pytest.mark.asyncio
async def test_stratz_client_graphql_error(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_post(self, url, headers=None, json=None):
        return httpx.Response(200, json={"errors": [{"message": "bad query"}]})

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    with pytest.raises(StratzGraphQLError):
        await StratzClient(Settings(stratz_token="token")).query("query { ok }")


@pytest.mark.asyncio
async def test_fetch_player_style_bundle_uses_requested_history_size(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_query(self, query, variables=None):
        assert "PlayerStyleBundle" in query
        assert variables == {"steamAccountId": 42, "take": 20}
        return {"player": {"matches": []}}

    monkeypatch.setattr(StratzClient, "query", fake_query)

    assert await StratzClient(Settings(stratz_token="token")).fetch_player_style_bundle(42, 20) == {
        "player": {"matches": []}
    }
