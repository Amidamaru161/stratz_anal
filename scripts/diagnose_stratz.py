from __future__ import annotations

import asyncio
import base64
import json
from datetime import UTC, datetime
from typing import Any

import httpx

from app.config import Settings
from app.stratz.client import STRATZ_USER_AGENT


def _decode_payload(token: str | None) -> dict[str, Any]:
    if not token:
        return {"present": False}
    parts = token.split(".")
    result: dict[str, Any] = {
        "present": True,
        "length": len(token),
        "segments": len(parts),
        "starts_like_jwt": token.startswith("eyJ"),
        "has_whitespace": any(ch.isspace() for ch in token),
    }
    if len(parts) != 3:
        return result
    payload = parts[1] + "=" * (-len(parts[1]) % 4)
    data = json.loads(base64.urlsafe_b64decode(payload.encode()).decode())
    result["payload"] = {key: data.get(key) for key in ["SteamId", "APIUser", "iss"]}
    for key in ["nbf", "iat", "exp"]:
        if key in data:
            result["payload"][key] = datetime.fromtimestamp(data[key], UTC).isoformat()
    return result


async def main() -> int:
    settings = Settings()
    print("STRATZ token check:")
    print(json.dumps(_decode_payload(settings.stratz_token), ensure_ascii=False, indent=2))

    if not settings.stratz_token:
        return 1

    headers = {
        "Authorization": f"Bearer {settings.stratz_token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": STRATZ_USER_AGENT,
    }
    async with httpx.AsyncClient(timeout=15, proxy=settings.stratz_proxy_url) as client:
        response = await client.post(
            settings.stratz_graphql_url,
            headers=headers,
            json={"query": "query { __typename }"},
        )

    report = {
        "status_code": response.status_code,
        "content_type": response.headers.get("content-type"),
        "server": response.headers.get("server"),
        "cf_ray": response.headers.get("cf-ray"),
        "cf_mitigated": response.headers.get("cf-mitigated"),
        "server_timing": response.headers.get("server-timing"),
    }
    if "application/json" in (response.headers.get("content-type") or ""):
        report["json"] = response.json()
    else:
        report["body_preview"] = response.text[:500]
    print("\nSTRATZ network check:")
    print(json.dumps(report, ensure_ascii=False, indent=2))

    return 0 if response.is_success else 2


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
