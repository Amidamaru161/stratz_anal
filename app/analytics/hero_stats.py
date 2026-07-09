from __future__ import annotations

from collections import defaultdict
from typing import Any

from app.analytics.dto import PlayerMatch
from app.analytics.scoring import is_win


def build_hero_stats(matches: list[PlayerMatch]) -> list[dict[str, Any]]:
    grouped: dict[int, list[PlayerMatch]] = defaultdict(list)
    for match in matches:
        if match.hero_id is not None:
            grouped[match.hero_id].append(match)

    result = []
    for hero_id, rows in grouped.items():
        games = len(rows)
        wins = sum(1 for row in rows if is_win(row))
        kills = sum(row.kills for row in rows)
        deaths = sum(row.deaths for row in rows)
        assists = sum(row.assists for row in rows)
        recent = rows[:5]
        result.append(
            {
                "heroId": hero_id,
                "games": games,
                "wins": wins,
                "losses": games - wins,
                "winRate": round(wins / games * 100, 1) if games else 0,
                "avgKills": round(kills / games, 1) if games else 0,
                "avgDeaths": round(deaths / games, 1) if games else 0,
                "avgAssists": round(assists / games, 1) if games else 0,
                "kda": round((kills + assists) / max(1, deaths), 2),
                "avgGpm": round(sum(row.gold_per_min for row in rows) / games, 1) if games else 0,
                "avgXpm": round(sum(row.xp_per_min for row in rows) / games, 1) if games else 0,
                "recentForm": ["W" if is_win(row) else "L" for row in recent],
            }
        )
    return sorted(result, key=lambda item: (item["games"], item["winRate"]), reverse=True)

