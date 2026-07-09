from __future__ import annotations

from typing import Literal

from sqlalchemy.orm import Session

from app.config import Settings
from app.services.storage import save_source_payload, upsert_heroes
from app.stratz.client import StratzClient
from app.stratz.normalizer import (
    normalize_hero_builds,
    normalize_hero_constants,
    normalize_hero_global_winrates,
)

HeroWinrateOrder = Literal["winRate", "matches", "heroId"]


async def build_global_hero_winrates(
    session: Session,
    settings: Settings,
    *,
    min_matches: int = 0,
    limit: int = 140,
    order_by: HeroWinrateOrder = "winRate",
) -> list[dict]:
    payload = await StratzClient(settings).fetch_hero_global_stats()
    save_source_payload(
        session,
        operation="hero_global_stats",
        request_json={},
        response_json=payload,
    )
    upsert_heroes(session, normalize_hero_constants(payload))
    session.commit()

    rows = [
        row for row in normalize_hero_global_winrates(payload) if row["match_count"] >= min_matches
    ]
    sort_keys = {
        "winRate": lambda row: (row["win_rate"], row["match_count"], -row["hero_id"]),
        "matches": lambda row: (row["match_count"], row["win_rate"], -row["hero_id"]),
        "heroId": lambda row: (-row["hero_id"],),
    }
    reverse = order_by != "heroId"
    return sorted(rows, key=sort_keys[order_by], reverse=reverse)[:limit]


async def build_hero_builds(
    session: Session,
    settings: Settings,
    *,
    hero_id: int,
    min_matches: int = 1000,
    limit: int = 10,
    match_limit: int = 10000,
) -> dict:
    payload = await StratzClient(settings).fetch_hero_builds(hero_id, match_limit)
    save_source_payload(
        session,
        operation="hero_builds",
        request_json={
            "heroId": hero_id,
            "minMatches": min_matches,
            "limit": limit,
            "matchLimit": match_limit,
        },
        response_json=payload,
    )
    upsert_heroes(session, normalize_hero_constants(payload))
    session.commit()
    return normalize_hero_builds(payload, hero_id, min_matches=min_matches, limit=limit)
