from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analytics.achievements import CATALOG, AchievementProgress, calculate_achievements
from app.analytics.dto import PlayerMatch
from app.analytics.hero_stats import build_hero_stats
from app.analytics.match_breakdowns import build_match_breakdowns
from app.analytics.scoring import build_card, is_win
from app.services.storage import load_player_matches, save_rating
from app.storage.models import AchievementDefinition, Player, PlayerAchievement

DEFAULT_ANALYTICS_LIMIT = 500


def seed_achievement_definitions(session: Session) -> None:
    for item in CATALOG:
        existing = session.get(AchievementDefinition, item.id)
        definition = existing or AchievementDefinition(id=item.id)
        definition.title = item.title
        definition.description = item.description
        definition.category = item.category
        definition.tier = item.tier
        definition.target = item.target
        definition.enabled = True
        session.add(definition)
    session.flush()


def sync_player_achievements(
    session: Session, account_id: int, matches: list[PlayerMatch]
) -> list[AchievementProgress]:
    seed_achievement_definitions(session)
    now = datetime.now(UTC)
    progress_items = calculate_achievements(matches)
    for progress in progress_items:
        existing = session.get(PlayerAchievement, (account_id, progress.id))
        unlocked_at = existing.unlocked_at if existing else None
        if progress.unlocked and unlocked_at is None:
            unlocked_at = now
        session.merge(
            PlayerAchievement(
                account_id=account_id,
                achievement_id=progress.id,
                progress=progress.progress,
                target=progress.target,
                unlocked=progress.unlocked,
                unavailable=progress.unavailable,
                unlocked_at=unlocked_at,
                evidence=progress.evidence or {},
            )
        )
    return progress_items


def sync_rating(session: Session, account_id: int, matches: list[PlayerMatch]) -> dict[str, Any]:
    card = build_card(matches)
    save_rating(session, account_id, card)
    return card


def build_summary_payload(
    session: Session, account_id: int, limit: int = DEFAULT_ANALYTICS_LIMIT
) -> dict[str, Any]:
    player = session.get(Player, account_id)
    if player is None:
        raise ValueError("player_not_found")
    matches = load_player_matches(session, account_id, limit)
    games = len(matches)
    wins = sum(1 for row in matches if is_win(row))
    kills = sum(row.kills for row in matches)
    deaths = sum(row.deaths for row in matches)
    assists = sum(row.assists for row in matches)
    card_payload = build_card(matches)
    card_payload["source"]["limit"] = limit
    return {
        "accountId": player.account_id,
        "name": player.name,
        "avatar": player.avatar,
        "rankTier": player.rank_tier,
        "leaderboardRank": player.leaderboard_rank,
        "lastRefreshedAt": player.last_refreshed_at,
        "matches": games,
        "wins": wins,
        "losses": games - wins,
        "winRate": round(wins / games * 100, 1) if games else 0,
        "kills": kills,
        "deaths": deaths,
        "assists": assists,
        "kda": round((kills + assists) / max(1, deaths), 2),
        "recentForm": ["W" if is_win(row) else "L" for row in matches[:10]],
        "card": card_payload,
        "breakdowns": build_match_breakdowns(matches),
    }


def build_hero_payload(
    session: Session, account_id: int, limit: int = DEFAULT_ANALYTICS_LIMIT
) -> list[dict[str, Any]]:
    return build_hero_stats(load_player_matches(session, account_id, limit))


def build_breakdown_payload(
    session: Session, account_id: int, limit: int = DEFAULT_ANALYTICS_LIMIT
) -> dict[str, Any]:
    player = session.get(Player, account_id)
    if player is None:
        raise ValueError("player_not_found")
    matches = load_player_matches(session, account_id, limit)
    if not matches:
        raise ValueError("matches_not_found")
    return {
        "accountId": account_id,
        "matches": len(matches),
        "limit": limit,
        **build_match_breakdowns(matches),
    }


def build_rating_payload(
    session: Session, account_id: int, limit: int = DEFAULT_ANALYTICS_LIMIT
) -> dict[str, Any]:
    player = session.get(Player, account_id)
    if player is None:
        raise ValueError("player_not_found")
    matches = load_player_matches(session, account_id, limit)
    if not matches:
        raise ValueError("matches_not_found")
    card = build_card(matches)
    card["source"]["limit"] = limit
    return {
        "accountId": account_id,
        "overall": card["overall"],
        "position": card["position"],
        "breakdown": {"rows": card["rows"]},
        "source": card["source"],
        "createdAt": datetime.now(UTC),
    }


def build_achievement_payloads(
    session: Session,
    account_id: int,
    *,
    limit: int = DEFAULT_ANALYTICS_LIMIT,
    category: str | None = None,
    unlocked: bool | None = None,
) -> list[dict[str, Any]]:
    player = session.get(Player, account_id)
    if player is None:
        raise ValueError("player_not_found")
    matches = load_player_matches(session, account_id, limit)
    if not matches:
        raise ValueError("matches_not_found")

    seed_achievement_definitions(session)
    progress_by_id = {item.id: item for item in calculate_achievements(matches)}
    unlocked_at_by_id = {
        item.achievement_id: item.unlocked_at
        for item in session.scalars(
            select(PlayerAchievement).where(PlayerAchievement.account_id == account_id)
        )
    }
    definitions = sorted(CATALOG, key=lambda item: (item.category, item.tier, item.id))
    result = []
    for definition in definitions:
        progress = progress_by_id[definition.id]
        if category and definition.category != category:
            continue
        if unlocked is not None and progress.unlocked != unlocked:
            continue
        result.append(
            {
                "id": definition.id,
                "title": definition.title,
                "description": definition.description,
                "category": definition.category,
                "tier": definition.tier,
                "progress": progress.progress,
                "target": progress.target,
                "progressPercent": progress.progress_percent,
                "unlocked": progress.unlocked,
                "unavailable": progress.unavailable,
                "unlockedAt": unlocked_at_by_id.get(definition.id) if progress.unlocked else None,
                "evidence": {**(progress.evidence or {}), "limit": limit},
            }
        )
    return result
