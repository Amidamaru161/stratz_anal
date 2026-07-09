from __future__ import annotations

from app.analytics.dto import PlayerMatch
from app.analytics.scoring import is_win

GAME_MODE_NAMES = {
    1: "All Pick",
    2: "Captains Mode",
    3: "Random Draft",
    4: "Single Draft",
    5: "All Random",
    12: "Least Played",
    15: "Custom",
    16: "Captains Draft",
    18: "Ability Draft",
    20: "All Random Death Match",
    21: "Solo Mid",
    22: "Ranked All Pick",
    23: "Turbo",
    24: "Mutation",
}

RANKED_GAME_MODES = {22}
RANKED_LOBBY_TYPES = {7}


def game_mode_name(game_mode: int | None) -> str:
    if game_mode is None:
        return "Unknown"
    return GAME_MODE_NAMES.get(game_mode, f"Mode {game_mode}")


def ranked_bucket(match: PlayerMatch) -> str:
    if match.game_mode in RANKED_GAME_MODES or match.lobby_type in RANKED_LOBBY_TYPES:
        return "ranked"
    if match.game_mode is None and match.lobby_type is None:
        return "unknown"
    return "unranked"


def ranked_label(bucket: str) -> str:
    return {
        "ranked": "Ranked",
        "unranked": "Unranked",
        "unknown": "Unknown",
    }.get(bucket, bucket.title())


def build_match_breakdowns(matches: list[PlayerMatch]) -> dict[str, list[dict]]:
    return {
        "byGameMode": _build_game_mode_breakdown(matches),
        "byRanked": _build_ranked_breakdown(matches),
    }


def _build_game_mode_breakdown(matches: list[PlayerMatch]) -> list[dict]:
    buckets: dict[int | None, list[PlayerMatch]] = {}
    for match in matches:
        buckets.setdefault(match.game_mode, []).append(match)
    rows = [
        {
            "gameMode": game_mode,
            "label": game_mode_name(game_mode),
            **_stats_for(rows),
        }
        for game_mode, rows in buckets.items()
    ]
    return sorted(rows, key=lambda row: (row["matches"], row["wins"], row["winRate"]), reverse=True)


def _build_ranked_breakdown(matches: list[PlayerMatch]) -> list[dict]:
    buckets = {"ranked": [], "unranked": [], "unknown": []}
    for match in matches:
        buckets[ranked_bucket(match)].append(match)
    rows = [
        {
            "bucket": bucket,
            "label": ranked_label(bucket),
            **_stats_for(rows),
        }
        for bucket, rows in buckets.items()
        if rows
    ]
    order = {"ranked": 0, "unranked": 1, "unknown": 2}
    return sorted(rows, key=lambda row: order.get(row["bucket"], 99))


def _stats_for(matches: list[PlayerMatch]) -> dict:
    games = len(matches)
    wins = sum(1 for match in matches if is_win(match))
    kills = sum(match.kills for match in matches)
    deaths = sum(match.deaths for match in matches)
    assists = sum(match.assists for match in matches)
    return {
        "matches": games,
        "wins": wins,
        "losses": games - wins,
        "winRate": round(wins / games * 100, 1) if games else 0,
        "kills": kills,
        "deaths": deaths,
        "assists": assists,
        "kda": round((kills + assists) / max(1, deaths), 2),
        "avgKills": round(kills / games, 1) if games else 0,
        "avgDeaths": round(deaths / games, 1) if games else 0,
        "avgAssists": round(assists / games, 1) if games else 0,
    }
