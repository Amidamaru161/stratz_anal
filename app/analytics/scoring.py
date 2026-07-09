from __future__ import annotations

from collections import Counter
from typing import Any

from app.analytics.dto import PlayerMatch


def is_win(match: PlayerMatch) -> bool:
    if match.win is not None:
        return match.win
    if match.player_slot is None or match.radiant_win is None:
        return False
    return (match.player_slot < 128 and match.radiant_win) or (
        match.player_slot >= 128 and not match.radiant_win
    )


def clamp_score(value: float, low: int = 35, high: int = 99) -> int:
    return max(low, min(high, round(value)))


def metric_score(value: float, target: float, low: int = 40, high: int = 99) -> int:
    if target <= 0:
        return low
    return clamp_score(low + (high - low) * min(max(value, 0) / target, 1), low, high)


def infer_position(matches: list[PlayerMatch]) -> str:
    lane_roles = [item.lane_role for item in matches if item.lane_role]
    if lane_roles:
        role = Counter(lane_roles).most_common(1)[0][0]
        return {1: "CRY", 2: "MID", 3: "OFF", 4: "SUP", 5: "SUP"}.get(role, "FLX")

    games = max(1, len(matches))
    avg_kills = sum(item.kills for item in matches) / games
    avg_assists = sum(item.assists for item in matches) / games
    avg_gpm = sum(item.gold_per_min for item in matches) / games
    avg_xpm = sum(item.xp_per_min for item in matches) / games
    avg_hero_damage = sum(item.hero_damage for item in matches) / games
    avg_tower_damage = sum(item.tower_damage for item in matches) / games
    avg_healing = sum(item.hero_healing for item in matches) / games
    avg_last_hits = sum(item.last_hits for item in matches) / games

    if avg_last_hits >= 200 and avg_tower_damage >= 4500:
        return "CRY"
    if avg_assists >= 16 and avg_last_hits <= 130 and avg_tower_damage < 3200:
        return "SUP"

    scores = {
        "CRY": 0.34 * min(avg_last_hits / 260, 1)
        + 0.26 * min(avg_tower_damage / 7000, 1)
        + 0.25 * min(avg_gpm / 760, 1)
        + 0.15 * min(avg_kills / 12, 1),
        "MID": 0.32 * min(avg_kills / 13, 1)
        + 0.26 * min(avg_xpm / 950, 1)
        + 0.25 * min(avg_hero_damage / 36000, 1)
        + 0.17 * min(avg_last_hits / 220, 1),
        "OFF": 0.27 * min(avg_assists / 18, 1)
        + 0.25 * min(avg_hero_damage / 30000, 1)
        + 0.23 * min(avg_tower_damage / 5200, 1)
        + 0.25 * min((avg_kills + avg_assists) / 24, 1),
        "SUP": 0.42 * min(avg_assists / 22, 1)
        + 0.22 * min(avg_healing / 3500, 1)
        + 0.2 * max(0, 1 - avg_last_hits / 180)
        + 0.16 * max(0, 1 - avg_gpm / 620),
    }
    return max(scores, key=scores.get)


def weighted_overall(position: str, rows: list[dict[str, Any]]) -> int:
    values = {row["label"]: row["value"] for row in rows}
    weights = {
        "CRY": {"IMP": 0.2, "FRM": 0.25, "FGT": 0.2, "SUR": 0.1, "OBJ": 0.2, "UTL": 0.05},
        "MID": {"IMP": 0.25, "FRM": 0.18, "FGT": 0.25, "SUR": 0.12, "OBJ": 0.1, "UTL": 0.1},
        "OFF": {"IMP": 0.25, "FRM": 0.1, "FGT": 0.2, "SUR": 0.2, "OBJ": 0.15, "UTL": 0.1},
        "SUP": {"IMP": 0.25, "FRM": 0.05, "FGT": 0.1, "SUR": 0.15, "OBJ": 0.1, "UTL": 0.35},
        "FLX": {"IMP": 0.2, "FRM": 0.16, "FGT": 0.18, "SUR": 0.16, "OBJ": 0.14, "UTL": 0.16},
    }
    role_weights = weights.get(position, weights["FLX"])
    return clamp_score(sum(values.get(key, 35) * weight for key, weight in role_weights.items()))


def build_card(matches: list[PlayerMatch]) -> dict[str, Any]:
    games = max(1, len(matches))
    wins = sum(1 for row in matches if is_win(row))
    kills = sum(item.kills for item in matches)
    deaths = sum(item.deaths for item in matches)
    assists = sum(item.assists for item in matches)

    avg_kills = kills / games
    avg_deaths = deaths / games
    avg_assists = assists / games
    avg_gpm = sum(item.gold_per_min for item in matches) / games
    avg_xpm = sum(item.xp_per_min for item in matches) / games
    avg_hero_damage = sum(item.hero_damage for item in matches) / games
    avg_tower_damage = sum(item.tower_damage for item in matches) / games
    avg_healing = sum(item.hero_healing for item in matches) / games
    avg_last_hits = sum(item.last_hits for item in matches) / games
    winrate = wins / games * 100
    recent = matches[:10]
    recent_winrate = sum(1 for row in recent if is_win(row)) / max(1, len(recent)) * 100
    kda = (kills + assists) / max(1, deaths)
    position = infer_position(matches)

    impact = (
        0.34 * winrate
        + 0.24 * metric_score(kda, 4.6)
        + 0.18 * metric_score(avg_assists, 18)
        + 0.24 * metric_score(avg_hero_damage, 28000)
    )
    farm = (
        0.5 * metric_score(avg_gpm, 760)
        + 0.3 * metric_score(avg_last_hits, 260)
        + 0.2 * metric_score(avg_xpm, 950)
    )
    fighting = (
        0.42 * metric_score(avg_kills, 12)
        + 0.38 * metric_score(avg_hero_damage, 30000)
        + 0.2 * metric_score(avg_assists, 18)
    )
    survival = 0.58 * (99 - metric_score(avg_deaths, 12, 0, 64)) + 0.42 * metric_score(kda, 5.0)
    objective = 0.68 * metric_score(avg_tower_damage, 5200) + 0.32 * metric_score(
        avg_last_hits, 210
    )
    utility = (
        0.45 * metric_score(avg_assists, 20)
        + 0.25 * metric_score(avg_healing, 3500)
        + 0.3 * metric_score((avg_gpm + avg_xpm) / 2, 900)
    )
    rows = [
        {"label": "IMP", "value": clamp_score(impact)},
        {"label": "FRM", "value": clamp_score(farm)},
        {"label": "FGT", "value": clamp_score(fighting)},
        {"label": "SUR", "value": clamp_score(survival)},
        {"label": "OBJ", "value": clamp_score(objective)},
        {"label": "UTL", "value": clamp_score(utility)},
    ]
    return {
        "overall": weighted_overall(position, rows),
        "position": position,
        "rows": rows,
        "source": {
            "winrate": round(winrate, 1),
            "recentWinrate": round(recent_winrate, 1),
            "avgKills": round(avg_kills, 1),
            "avgDeaths": round(avg_deaths, 1),
            "avgAssists": round(avg_assists, 1),
            "avgGpm": round(avg_gpm, 1),
            "avgXpm": round(avg_xpm, 1),
            "avgHeroDamage": round(avg_hero_damage),
            "avgTowerDamage": round(avg_tower_damage),
            "avgHealing": round(avg_healing),
            "avgLastHits": round(avg_last_hits, 1),
            "roleWeights": position,
        },
    }

