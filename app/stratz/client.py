from __future__ import annotations

import asyncio
from typing import Any

import httpx

from app.config import Settings
from app.stratz.queries import (
    HERO_BUILDS_QUERY,
    HERO_CONSTANTS_QUERY,
    HERO_GLOBAL_STATS_QUERY,
    MATCH_DETAILS_QUERY,
    PLAYER_BUNDLE_QUERY,
    PLAYER_STYLE_BUNDLE_QUERY,
)

STRATZ_USER_AGENT = "STRATZ_API"


class StratzError(RuntimeError):
    pass


class StratzAuthError(StratzError):
    pass


class StratzRateLimitError(StratzError):
    pass


class StratzBlockedError(StratzError):
    pass


class StratzGraphQLError(StratzError):
    def __init__(self, errors: list[dict[str, Any]]) -> None:
        self.errors = errors
        super().__init__(f"STRATZ GraphQL errors: {errors[:2]}")


class StratzClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @property
    def configured(self) -> bool:
        return bool(self.settings.stratz_token)

    async def query(self, query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
        if not self.settings.stratz_token:
            raise StratzAuthError("STRATZ_TOKEN is not configured")

        headers = {
            "Authorization": f"Bearer {self.settings.stratz_token}",
            "Content-Type": "application/json",
            "User-Agent": STRATZ_USER_AGENT,
        }
        payload = {"query": query, "variables": variables or {}}
        last_error: Exception | None = None

        async with httpx.AsyncClient(timeout=15, proxy=self.settings.stratz_proxy_url) as client:
            for attempt in range(1, 4):
                try:
                    response = await client.post(
                        self.settings.stratz_graphql_url, headers=headers, json=payload
                    )
                    content_type = response.headers.get("content-type", "")
                    if response.status_code == 403 and "text/html" in content_type:
                        cf_trace = response.headers.get("cf-ray") or response.headers.get("server-timing")
                        raise StratzBlockedError(
                            "STRATZ returned a Cloudflare challenge (HTTP 403); "
                            "the request did not reach GraphQL"
                            + (f"; Cloudflare trace: {cf_trace}" if cf_trace else "")
                        )
                    if response.status_code in {401, 403}:
                        raise StratzAuthError("STRATZ token was rejected")
                    if response.status_code == 429:
                        raise StratzRateLimitError("STRATZ rate limit reached")
                    if response.status_code >= 500:
                        raise httpx.HTTPStatusError(
                            f"STRATZ HTTP {response.status_code}",
                            request=httpx.Request("POST", self.settings.stratz_graphql_url),
                            response=response,
                        )
                    if response.status_code >= 400:
                        raise StratzError(f"STRATZ HTTP {response.status_code}: {response.text[:300]}")
                    body = response.json()
                    errors = body.get("errors")
                    if errors:
                        raise StratzGraphQLError(errors)
                    data = body.get("data")
                    if not isinstance(data, dict):
                        raise StratzError("STRATZ response did not include a data object")
                    return data
                except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError) as exc:
                    last_error = exc
                    if attempt == 3:
                        break
                    await asyncio.sleep(0.5 * attempt)

        raise StratzError(f"STRATZ request failed: {last_error}") from last_error

    async def fetch_player_bundle(self, account_id: int, take: int = 100) -> dict[str, Any]:
        return await self.query(PLAYER_BUNDLE_QUERY, {"steamAccountId": account_id, "take": take})

    async def fetch_match_details(self, match_id: int) -> dict[str, Any]:
        return await self.query(MATCH_DETAILS_QUERY, {"matchId": match_id})

    async def fetch_player_style_bundle(self, account_id: int, take: int = 20) -> dict[str, Any]:
        return await self.query(PLAYER_STYLE_BUNDLE_QUERY, {"steamAccountId": account_id, "take": take})

    async def fetch_hero_constants(self) -> dict[str, Any]:
        return await self.query(HERO_CONSTANTS_QUERY)

    async def fetch_hero_global_stats(self) -> dict[str, Any]:
        return await self.query(HERO_GLOBAL_STATS_QUERY)

    async def fetch_hero_builds(self, hero_id: int, match_limit: int = 10000) -> dict[str, Any]:
        return await self.query(HERO_BUILDS_QUERY, {"heroId": hero_id, "matchLimit": match_limit})
