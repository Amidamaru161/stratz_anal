from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Select, desc, func, select
from sqlalchemy.orm import Session

from app.analytics.dto import PlayerMatch
from app.storage.models import (
    Hero,
    Match,
    MatchPlayer,
    Player,
    PlayerMatchIndex,
    RatingSnapshot,
    SourcePayload,
)
from app.stratz.normalizer import normalize_match, normalize_match_player


def utc_now() -> datetime:
    return datetime.now(UTC)


def save_source_payload(
    session: Session,
    *,
    operation: str,
    request_json: dict[str, Any],
    response_json: dict[str, Any],
    account_id: int | None = None,
    match_id: int | None = None,
) -> None:
    session.add(
        SourcePayload(
            source="stratz",
            operation=operation,
            account_id=account_id,
            match_id=match_id,
            request_json=request_json,
            response_json=response_json,
        )
    )


def upsert_player(session: Session, payload: dict[str, Any]) -> Player:
    player = session.get(Player, payload["account_id"]) or Player(account_id=payload["account_id"])
    player.name = payload["name"]
    player.avatar = payload.get("avatar")
    player.rank_tier = payload.get("rank_tier")
    player.leaderboard_rank = payload.get("leaderboard_rank")
    player.last_refreshed_at = utc_now()
    session.add(player)
    return player


def upsert_heroes(session: Session, heroes: list[dict[str, Any]]) -> None:
    for payload in heroes:
        session.merge(
            Hero(
                hero_id=payload["hero_id"],
                name=payload["name"],
                display_name=payload["display_name"],
                short_name=payload.get("short_name"),
                image_url=payload.get("image_url"),
                roles=payload.get("roles") or [],
                raw_json=payload.get("raw_json") or {},
            )
        )


def upsert_match_bundle(session: Session, account_id: int, match_payload: dict[str, Any]) -> None:
    match_row = normalize_match(match_payload)
    match = Match(
        match_id=match_row["match_id"],
        start_time=match_row["start_time"],
        duration_seconds=match_row["duration_seconds"],
        radiant_win=match_row["radiant_win"],
        game_mode=match_row["game_mode"],
        lobby_type=match_row["lobby_type"],
        raw_json=match_row["raw_json"],
        fetched_at=utc_now(),
    )
    session.merge(match)

    players = match_payload.get("players") or []
    normalized_players = [normalize_match_player(match_payload, player, account_id) for player in players]
    team_kills_by_side = _team_kills_by_side(normalized_players)
    tracked_player = None
    for player_row in normalized_players:
        player_row["team_kills"] = (
            team_kills_by_side["radiant"]
            if player_row["player_slot"] < 128
            else team_kills_by_side["dire"]
        )
        session.merge(MatchPlayer(**player_row))
        if player_row["account_id"] == account_id:
            tracked_player = player_row

    if tracked_player is not None:
        session.merge(
            PlayerMatchIndex(
                account_id=account_id,
                match_id=match_row["match_id"],
                start_time=match_row["start_time"],
                hero_id=tracked_player["hero_id"],
                player_slot=tracked_player["player_slot"],
                radiant_win=match_row["radiant_win"],
                game_mode=match_row["game_mode"],
                lobby_type=match_row["lobby_type"],
                kills=tracked_player["kills"],
                deaths=tracked_player["deaths"],
                assists=tracked_player["assists"],
                raw_json=tracked_player["raw_json"],
            )
        )


def _team_kills_by_side(players: list[dict[str, Any]]) -> dict[str, int]:
    result = {"radiant": 0, "dire": 0}
    for player in players:
        side = "radiant" if player["player_slot"] < 128 else "dire"
        result[side] += player["kills"]
    return result


def load_player_matches(session: Session, account_id: int, limit: int = 500) -> list[PlayerMatch]:
    stmt: Select[tuple[PlayerMatchIndex, MatchPlayer, Match]] = (
        select(PlayerMatchIndex, MatchPlayer, Match)
        .join(
            MatchPlayer,
            (MatchPlayer.match_id == PlayerMatchIndex.match_id)
            & (MatchPlayer.account_id == PlayerMatchIndex.account_id),
        )
        .join(Match, Match.match_id == PlayerMatchIndex.match_id)
        .where(PlayerMatchIndex.account_id == account_id)
        .order_by(desc(PlayerMatchIndex.start_time), desc(PlayerMatchIndex.match_id))
        .limit(limit)
    )
    rows = session.execute(stmt).all()
    return [
        PlayerMatch(
            match_id=index.match_id,
            account_id=account_id,
            start_time=index.start_time,
            duration_seconds=match.duration_seconds,
            hero_id=player.hero_id,
            player_slot=player.player_slot,
            radiant_win=match.radiant_win,
            win=player.win,
            game_mode=match.game_mode,
            lobby_type=match.lobby_type,
            kills=player.kills,
            deaths=player.deaths,
            assists=player.assists,
            gold_per_min=player.gold_per_min,
            xp_per_min=player.xp_per_min,
            hero_damage=player.hero_damage,
            tower_damage=player.tower_damage,
            hero_healing=player.hero_healing,
            last_hits=player.last_hits,
            lane_role=player.lane_role,
            team_kills=player.team_kills,
            raw={"match": match.raw_json, "player": player.raw_json},
        )
        for index, player, match in rows
    ]


def latest_rating(session: Session, account_id: int) -> RatingSnapshot | None:
    return session.scalar(
        select(RatingSnapshot)
        .where(RatingSnapshot.account_id == account_id)
        .order_by(desc(RatingSnapshot.created_at), desc(RatingSnapshot.id))
        .limit(1)
    )


def save_rating(session: Session, account_id: int, card: dict[str, Any]) -> RatingSnapshot:
    snapshot = RatingSnapshot(
        account_id=account_id,
        overall=card["overall"],
        position=card["position"],
        breakdown={"rows": card["rows"]},
        source=card["source"],
    )
    session.add(snapshot)
    return snapshot


def leaderboard_rows(session: Session, limit: int) -> list[tuple[Player, RatingSnapshot]]:
    latest_created = (
        select(
            RatingSnapshot.account_id,
            func.max(RatingSnapshot.created_at).label("created_at"),
        )
        .group_by(RatingSnapshot.account_id)
        .subquery()
    )
    stmt = (
        select(Player, RatingSnapshot)
        .join(RatingSnapshot, RatingSnapshot.account_id == Player.account_id)
        .join(
            latest_created,
            (latest_created.c.account_id == RatingSnapshot.account_id)
            & (latest_created.c.created_at == RatingSnapshot.created_at),
        )
        .order_by(desc(RatingSnapshot.overall), desc(Player.last_refreshed_at))
        .limit(limit)
    )
    return list(session.execute(stmt).all())
