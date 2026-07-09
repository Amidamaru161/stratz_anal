from __future__ import annotations

import asyncio

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.analytics.dto import PlayerMatch
from app.analytics.style import ITEM_SLOT_FIELDS, build_style_score
from app.config import Settings
from app.services.storage import load_player_matches, save_source_payload, upsert_match_bundle
from app.storage.models import Player, SourcePayload
from app.stratz.client import StratzAuthError, StratzClient, StratzGraphQLError
from app.stratz.normalizer import extract_matches, normalize_hero_builds

STYLE_META_MIN_MATCHES = 100
STYLE_META_LIMIT = 30
STYLE_META_MATCH_LIMIT = 5_000
STYLE_DETAIL_FETCH_LIMIT = 100
STYLE_DETAIL_FALLBACK_TAKES = (20,)
STYLE_META_CONCURRENCY = 4


def _cached_hero_meta(session: Session, hero_id: int) -> dict | None:
    payloads = session.scalars(
        select(SourcePayload)
        .where(SourcePayload.operation == "hero_builds")
        .order_by(desc(SourcePayload.fetched_at), desc(SourcePayload.id))
    ).all()
    for payload in payloads:
        if payload.request_json.get("heroId") != hero_id:
            continue
        return normalize_hero_builds(
            payload.response_json,
            hero_id,
            min_matches=STYLE_META_MIN_MATCHES,
            limit=STYLE_META_LIMIT,
        )
    return None


def _has_style_data(match: object) -> bool:
    raw = getattr(match, "raw", {})
    player = raw.get("player") if isinstance(raw, dict) else None
    if not isinstance(player, dict):
        return False
    return bool(player.get("abilities")) or any(player.get(field) for field in ITEM_SLOT_FIELDS)


async def _hydrate_style_details(
    session: Session,
    client: StratzClient,
    account_id: int,
    matches: list[PlayerMatch],
) -> int:
    missing = [match for match in matches if not _has_style_data(match)]
    if not missing:
        return 0
    requested_take = min(len(matches), STYLE_DETAIL_FETCH_LIMIT)
    candidate_takes = [requested_take]
    candidate_takes.extend(take for take in STYLE_DETAIL_FALLBACK_TAKES if take < requested_take)
    last_error: StratzAuthError | StratzGraphQLError | None = None
    for take in candidate_takes:
        try:
            payload = await client.fetch_player_style_bundle(account_id, take)
            break
        except (StratzAuthError, StratzGraphQLError) as exc:
            last_error = exc
    else:
        assert last_error is not None
        raise last_error
    save_source_payload(
        session,
        operation="player_style_bundle",
        account_id=account_id,
        request_json={"accountId": account_id, "take": take, "requestedTake": requested_take},
        response_json=payload,
    )
    for match_payload in extract_matches(payload):
        upsert_match_bundle(session, account_id, match_payload)
    session.flush()
    return min(len(missing), take)


async def build_player_style_payload(
    session: Session,
    settings: Settings,
    account_id: int,
    *,
    limit: int,
) -> dict:
    if session.get(Player, account_id) is None:
        raise ValueError("Player not found")
    matches = load_player_matches(session, account_id, limit)
    if not matches:
        raise ValueError("No matches found")

    client = StratzClient(settings)
    await _hydrate_style_details(session, client, account_id, matches)
    matches = load_player_matches(session, account_id, limit)
    styled_matches = [match for match in matches if _has_style_data(match)]

    hero_ids = sorted({match.hero_id for match in styled_matches if match.hero_id is not None})
    meta_by_hero: dict[int, dict] = {}
    missing_hero_ids = []
    for hero_id in hero_ids:
        cached = _cached_hero_meta(session, hero_id)
        if cached is not None:
            meta_by_hero[hero_id] = cached
            continue
        missing_hero_ids.append(hero_id)

    for offset in range(0, len(missing_hero_ids), STYLE_META_CONCURRENCY):
        batch = missing_hero_ids[offset : offset + STYLE_META_CONCURRENCY]
        payloads = await asyncio.gather(
            *(client.fetch_hero_builds(hero_id, STYLE_META_MATCH_LIMIT) for hero_id in batch),
            return_exceptions=True,
        )
        for hero_id, payload in zip(batch, payloads, strict=True):
            if isinstance(payload, Exception):
                continue
            save_source_payload(
                session,
                operation="hero_builds",
                request_json={
                    "heroId": hero_id,
                    "minMatches": STYLE_META_MIN_MATCHES,
                    "limit": STYLE_META_LIMIT,
                    "matchLimit": STYLE_META_MATCH_LIMIT,
                    "consumer": "style_score",
                },
                response_json=payload,
            )
            meta_by_hero[hero_id] = normalize_hero_builds(
                payload,
                hero_id,
                min_matches=STYLE_META_MIN_MATCHES,
                limit=STYLE_META_LIMIT,
            )

    result = build_style_score(matches, meta_by_hero)
    session.commit()
    return {
        "accountId": account_id,
        "limit": limit,
        "matchesConsidered": len(matches),
        "metaHeroes": len(meta_by_hero),
        "styleScore": result["style_score"],
        "label": result["label"],
        "itemScore": result["item_score"],
        "skillScore": result["skill_score"],
        "ratedMatches": result["rated_matches"],
        "matches": [
            {
                "matchId": row["match_id"],
                "heroId": row["hero_id"],
                "heroName": meta_by_hero.get(row["hero_id"], {}).get("hero_name"),
                "score": row["score"],
                "itemScore": row["item_score"],
                "skillScore": row["skill_score"],
                "itemOrderAvailable": row["item_order_available"],
                "reason": row["reason"],
                "actualItems": row["actual_items"],
                "metaItems": row["meta_items"],
                "actualSkills": row["actual_skills"],
                "metaSkills": row["meta_skills"],
            }
            for row in result["matches"]
        ],
    }
