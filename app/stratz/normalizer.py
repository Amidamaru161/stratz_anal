from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.analytics.dto import PlayerMatch

GAME_MODE_ENUM_IDS = {
    "NONE": None,
    "UNKNOWN": None,
    "ALL_PICK": 1,
    "CAPTAINS_MODE": 2,
    "RANDOM_DRAFT": 3,
    "SINGLE_DRAFT": 4,
    "ALL_RANDOM": 5,
    "LEAST_PLAYED": 12,
    "CUSTOM": 15,
    "CAPTAINS_DRAFT": 16,
    "ABILITY_DRAFT": 18,
    "ALL_RANDOM_DEATH_MATCH": 20,
    "SOLO_MID": 21,
    "ALL_PICK_RANKED": 22,
    "TURBO": 23,
    "MUTATION": 24,
}

LOBBY_TYPE_ENUM_IDS = {
    "UNRANKED": 0,
    "NORMAL": 0,
    "PRACTICE": 1,
    "TOURNAMENT": 2,
    "TUTORIAL": 3,
    "COOP_BOT": 4,
    "TEAM_MATCH": 5,
    "SOLO_QUEUE": 6,
    "RANKED": 7,
    "RANKED_MATCHMAKING": 7,
}


def _pick(data: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in data and data[key] is not None:
            return data[key]
    return default


def _int_or_none(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _enum_id_or_none(value: Any, mapping: dict[str, int | None]) -> int | None:
    if isinstance(value, str):
        normalized = value.strip().upper()
        if normalized in mapping:
            return mapping[normalized]
    return _int_or_none(value)


def _float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _bool_or_none(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return bool(value)
    if isinstance(value, str):
        return value.lower() in {"true", "1", "yes", "radiant"}
    return None


def parse_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if isinstance(value, (int, float)):
        timestamp = value / 1000 if value > 10_000_000_000 else value
        return datetime.fromtimestamp(timestamp, UTC)
    if isinstance(value, str):
        normalized = value.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            as_int = _int_or_none(value)
            return parse_datetime(as_int) if as_int is not None else None
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    return None


def normalize_player(data: dict[str, Any], account_id: int) -> dict[str, Any]:
    player = data.get("player") or data
    steam = player.get("steamAccount") or player.get("steam_account") or player.get("profile") or {}
    return {
        "account_id": account_id,
        "name": _pick(steam, "name", "personaName", "personaname", default=f"Player {account_id}"),
        "avatar": _pick(steam, "fullAvatar", "avatarFull", "avatarfull", "avatar", "avatarmedium"),
        "rank_tier": _int_or_none(_pick(steam, "seasonRank", "rankTier", "rank_tier")),
        "leaderboard_rank": _int_or_none(
            _pick(steam, "seasonLeaderboardRank", "leaderboardRank", "leaderboard_rank")
        ),
    }


def extract_matches(data: dict[str, Any]) -> list[dict[str, Any]]:
    player = data.get("player") or data
    matches = player.get("matches") or data.get("matches") or []
    return matches if isinstance(matches, list) else []


def normalize_hero_constants(data: dict[str, Any]) -> list[dict[str, Any]]:
    constants = data.get("constants") or data
    heroes = constants.get("heroes") or []
    normalized = []
    for hero in heroes:
        language = hero.get("language") or {}
        stats = hero.get("stats") or {}
        display_name = _pick(language, "displayName") or _pick(hero, "displayName", "localizedName", "name")
        raw_roles = _pick(hero, "roles", default=_pick(stats, "roles", default=[])) or []
        roles = [
            str(_pick(role, "roleId", "name", "id") if isinstance(role, dict) else role)
            for role in raw_roles
            if role is not None
        ]
        normalized.append(
            {
                "hero_id": int(hero["id"]),
                "name": _pick(hero, "name", default=f"hero_{hero['id']}"),
                "display_name": display_name or f"Hero {hero['id']}",
                "short_name": _pick(hero, "shortName", "short_name"),
                "image_url": _pick(hero, "imageUrl", "image", "icon"),
                "roles": roles,
                "raw_json": hero,
            }
        )
    return normalized


def normalize_hero_global_winrates(data: dict[str, Any]) -> list[dict[str, Any]]:
    hero_stats = data.get("heroStats") or data.get("hero_stats") or {}
    rows = hero_stats.get("stats") or []
    heroes = {hero["hero_id"]: hero for hero in normalize_hero_constants(data)}
    normalized = []
    for row in rows:
        hero_id = _int_or_none(_pick(row, "heroId", "hero_id"))
        if hero_id is None:
            continue
        match_count = _int_or_none(_pick(row, "matchCount", "match_count")) or 0
        win_count = _int_or_none(_pick(row, "winCount", "win_count")) or 0
        hero = heroes.get(hero_id, {})
        normalized.append(
            {
                "hero_id": hero_id,
                "name": hero.get("name") or f"hero_{hero_id}",
                "display_name": hero.get("display_name") or f"Hero {hero_id}",
                "short_name": hero.get("short_name"),
                "image_url": hero.get("image_url"),
                "roles": hero.get("roles") or [],
                "match_count": match_count,
                "win_count": win_count,
                "loss_count": max(match_count - win_count, 0),
                "win_rate": round(win_count / match_count * 100, 2) if match_count else 0,
            }
        )
    return normalized


def normalize_hero_builds(
    data: dict[str, Any],
    hero_id: int,
    *,
    min_matches: int = 1000,
    limit: int = 10,
) -> dict[str, Any]:
    hero_stats = data.get("heroStats") or {}
    constants = data.get("constants") or {}
    item_names = _constant_name_map(constants.get("items") or [])
    ability_names = _constant_name_map(constants.get("abilities") or [])
    heroes = {hero["hero_id"]: hero for hero in normalize_hero_constants(data)}
    hero = heroes.get(hero_id, {})

    core_items = _aggregate_item_rows(
        hero_stats.get("itemFullPurchase") or [],
        item_names,
        min_matches=min_matches,
        limit=limit,
        time_field="time",
        time_unit="minute",
    )
    starting_items = _aggregate_item_rows(
        hero_stats.get("itemStartingPurchase") or [],
        item_names,
        min_matches=min_matches,
        limit=limit,
        group_extra="wasGiven",
    )
    boots = _aggregate_item_rows(
        hero_stats.get("itemBootPurchase") or [],
        item_names,
        min_matches=min_matches,
        limit=limit,
        time_field="timeAverage",
        time_unit="second",
    )
    neutral_items = _aggregate_neutral_rows(
        hero_stats.get("itemNeutral") or [],
        item_names,
        min_matches=min_matches,
        limit=limit,
    )
    talents = _aggregate_ability_rows(
        hero_stats.get("talent") or [],
        ability_names,
        min_matches=min_matches,
        limit=limit,
        time_field="timeAverage",
    )
    skill_build = _skill_build_rows(
        hero_stats.get("abilityMinLevel") or [],
        ability_names,
        min_matches=min_matches,
    )
    guides = _guide_rows(hero_stats.get("guide") or [], item_names, hero_id=hero_id)

    return {
        "hero_id": hero_id,
        "hero_name": hero.get("display_name") or f"Hero {hero_id}",
        "short_name": hero.get("short_name"),
        "source": {
            "api": "STRATZ",
            "minMatches": min_matches,
            "limit": limit,
            "matchLimit": "STRATZ heroStats.itemFullPurchase matchLimit",
        },
        "core_items": core_items,
        "starting_items": starting_items,
        "boots": boots,
        "neutral_items": neutral_items,
        "talents": talents,
        "skill_build": skill_build,
        "guides": guides,
    }


def _constant_name_map(rows: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    result = {}
    for row in rows:
        row_id = _int_or_none(row.get("id"))
        if row_id is None:
            continue
        language = row.get("language") or {}
        result[row_id] = {
            "id": row_id,
            "name": _pick(language, "displayName") or _pick(row, "displayName", "name"),
            "internal_name": _pick(row, "name"),
            "short_name": _pick(row, "shortName", "short_name"),
        }
    return result


def _win_rate(win_count: int, match_count: int) -> float:
    return round(win_count / match_count * 100, 2) if match_count else 0.0


def _meta_score(match_count: int, win_rate: float, max_match_count: int) -> float:
    popularity = match_count / max(max_match_count, 1)
    return round((0.65 * popularity + 0.35 * (win_rate / 100)) * 100, 2)


def _apply_meta_sort(rows: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    max_match_count = max((row["match_count"] for row in rows), default=0)
    for row in rows:
        row["meta_score"] = _meta_score(row["match_count"], row["win_rate"], max_match_count)
    return sorted(rows, key=lambda row: (row["meta_score"], row["match_count"], row["win_rate"]), reverse=True)[
        :limit
    ]


def _aggregate_item_rows(
    rows: list[dict[str, Any]],
    item_names: dict[int, dict[str, Any]],
    *,
    min_matches: int,
    limit: int,
    time_field: str | None = None,
    time_unit: str | None = None,
    group_extra: str | None = None,
) -> list[dict[str, Any]]:
    groups: dict[tuple[int, Any], dict[str, Any]] = {}
    for row in rows:
        item_id = _int_or_none(_pick(row, "itemId", "item_id"))
        if item_id is None:
            continue
        extra = _pick(row, group_extra) if group_extra else None
        key = (item_id, extra)
        match_count = _int_or_none(_pick(row, "matchCount", "match_count")) or 0
        win_count = _int_or_none(_pick(row, "winCount", "win_count")) or 0
        current = groups.setdefault(
            key,
            {
                "item_id": item_id,
                "item_name": item_names.get(item_id, {}).get("name") or f"Item {item_id}",
                "short_name": item_names.get(item_id, {}).get("short_name"),
                "match_count": 0,
                "win_count": 0,
                "time_weighted_sum": 0.0,
                "time_weight": 0,
            },
        )
        if group_extra:
            current[_snake_case(group_extra)] = extra
        current["match_count"] += match_count
        current["win_count"] += win_count
        if time_field:
            time_value = _float_or_none(_pick(row, time_field))
            if time_value is not None and match_count:
                current["time_weighted_sum"] += time_value * match_count
                current["time_weight"] += match_count

    normalized = []
    for row in groups.values():
        if row["match_count"] < min_matches:
            continue
        row["win_rate"] = _win_rate(row["win_count"], row["match_count"])
        if time_field and row["time_weight"]:
            average = row.pop("time_weighted_sum") / row.pop("time_weight")
            if time_unit == "minute":
                row["average_time_minute"] = round(average, 1)
            else:
                row["average_time_seconds"] = round(average, 1)
                row["average_time_minute"] = round(average / 60, 1)
        else:
            row.pop("time_weighted_sum", None)
            row.pop("time_weight", None)
        normalized.append(row)
    return _apply_meta_sort(normalized, limit)


def _aggregate_neutral_rows(
    rows: list[dict[str, Any]],
    item_names: dict[int, dict[str, Any]],
    *,
    min_matches: int,
    limit: int,
) -> list[dict[str, Any]]:
    normalized = []
    for row in rows:
        item_id = _int_or_none(_pick(row, "itemId", "item_id"))
        if item_id is None:
            continue
        equipped_match_count = _int_or_none(_pick(row, "equippedMatchCount")) or 0
        equipped_win_count = _int_or_none(_pick(row, "equippedMatchWinCount")) or 0
        match_count = equipped_match_count or _int_or_none(_pick(row, "matchCount", "match_count")) or 0
        win_count = equipped_win_count or _int_or_none(_pick(row, "winCount", "win_count")) or 0
        if match_count < min_matches:
            continue
        normalized.append(
            {
                "item_id": item_id,
                "item_name": item_names.get(item_id, {}).get("name") or f"Item {item_id}",
                "short_name": item_names.get(item_id, {}).get("short_name"),
                "match_count": match_count,
                "win_count": win_count,
                "equipped_match_count": equipped_match_count,
                "equipped_win_count": equipped_win_count,
                "win_rate": _win_rate(win_count, match_count),
            }
        )
    return _apply_meta_sort(normalized, limit)


def _aggregate_ability_rows(
    rows: list[dict[str, Any]],
    ability_names: dict[int, dict[str, Any]],
    *,
    min_matches: int,
    limit: int,
    time_field: str | None = None,
) -> list[dict[str, Any]]:
    normalized = []
    for row in rows:
        ability_id = _int_or_none(_pick(row, "abilityId", "ability_id"))
        if ability_id is None:
            continue
        match_count = _int_or_none(_pick(row, "matchCount", "match_count")) or 0
        win_count = _int_or_none(_pick(row, "winCount", "win_count")) or 0
        if match_count < min_matches:
            continue
        payload = {
            "ability_id": ability_id,
            "ability_name": ability_names.get(ability_id, {}).get("name") or f"Ability {ability_id}",
            "match_count": match_count,
            "win_count": win_count,
            "win_rate": _win_rate(win_count, match_count),
        }
        if time_field:
            average = _float_or_none(_pick(row, time_field))
            if average is not None:
                payload["average_time_seconds"] = round(average, 1)
                payload["average_time_minute"] = round(average / 60, 1)
        normalized.append(payload)
    return _apply_meta_sort(normalized, limit)


def _skill_build_rows(
    rows: list[dict[str, Any]],
    ability_names: dict[int, dict[str, Any]],
    *,
    min_matches: int,
) -> list[dict[str, Any]]:
    by_level: dict[int, dict[str, Any]] = {}
    for row in rows:
        level = _int_or_none(_pick(row, "level"))
        ability_id = _int_or_none(_pick(row, "abilityId", "ability_id"))
        if level is None or ability_id is None or ability_id <= 0:
            continue
        match_count = _int_or_none(_pick(row, "matchCount", "match_count")) or 0
        win_count = _int_or_none(_pick(row, "winCount", "win_count")) or 0
        if match_count < min_matches:
            continue
        existing = by_level.get(level)
        if existing and existing["match_count"] >= match_count:
            continue
        by_level[level] = {
            "level": level,
            "ability_id": ability_id,
            "ability_name": ability_names.get(ability_id, {}).get("name") or f"Ability {ability_id}",
            "match_count": match_count,
            "win_count": win_count,
            "win_rate": _win_rate(win_count, match_count),
        }
    result = list(by_level.values())
    max_match_count = max((row["match_count"] for row in result), default=0)
    for row in result:
        row["meta_score"] = _meta_score(row["match_count"], row["win_rate"], max_match_count)
    return sorted(result, key=lambda row: row["level"])


def _guide_rows(
    rows: list[dict[str, Any]],
    item_names: dict[int, dict[str, Any]],
    *,
    hero_id: int,
) -> list[dict[str, Any]]:
    guides = []
    for group in rows:
        if _int_or_none(_pick(group, "heroId", "hero_id")) != hero_id:
            continue
        for guide in group.get("guides") or []:
            item_ids = [_int_or_none(item_id) for item_id in guide.get("itemIds") or []]
            item_ids = [item_id for item_id in item_ids if item_id is not None]
            neutral_item_ids = [_int_or_none(item_id) for item_id in guide.get("neutralItemIds") or []]
            neutral_item_ids = [item_id for item_id in neutral_item_ids if item_id is not None]
            created_at = parse_datetime(_pick(guide, "createdDateTime", "created_at"))
            guides.append(
                {
                    "match_id": _int_or_none(_pick(guide, "matchId", "match_id")),
                    "created_at": created_at,
                    "item_ids": item_ids,
                    "item_names": [
                        item_names.get(item_id, {}).get("name") or f"Item {item_id}"
                        for item_id in item_ids
                    ],
                    "neutral_item_ids": neutral_item_ids,
                    "neutral_item_names": [
                        item_names.get(item_id, {}).get("name") or f"Item {item_id}"
                        for item_id in neutral_item_ids
                    ],
                }
            )
    return guides


def _snake_case(value: str) -> str:
    result = []
    for index, char in enumerate(value):
        if char.isupper() and index:
            result.append("_")
        result.append(char.lower())
    return "".join(result)


def normalize_match(match: dict[str, Any]) -> dict[str, Any]:
    return {
        "match_id": int(_pick(match, "id", "matchId", "match_id")),
        "start_time": parse_datetime(_pick(match, "startDateTime", "start_time", "startTime")),
        "duration_seconds": _int_or_none(_pick(match, "durationSeconds", "duration", "duration_seconds")),
        "radiant_win": _bool_or_none(_pick(match, "didRadiantWin", "radiantWin", "radiant_win")),
        "game_mode": _enum_id_or_none(_pick(match, "gameMode", "game_mode"), GAME_MODE_ENUM_IDS),
        "lobby_type": _enum_id_or_none(_pick(match, "lobbyType", "lobby_type"), LOBBY_TYPE_ENUM_IDS),
        "raw_json": match,
    }


def normalize_match_player(
    match: dict[str, Any], player: dict[str, Any], tracked_account_id: int | None = None
) -> dict[str, Any]:
    normalized_match = normalize_match(match)
    account_id = _int_or_none(_pick(player, "steamAccountId", "accountId", "account_id"))
    player_slot = _int_or_none(_pick(player, "playerSlot", "player_slot"))
    is_radiant = _bool_or_none(_pick(player, "isRadiant"))
    if player_slot is None and is_radiant is not None:
        player_slot = 0 if is_radiant else 128
    win = _bool_or_none(_pick(player, "isVictory", "win", "won"))
    if win is None and player_slot is not None and normalized_match["radiant_win"] is not None:
        win = (player_slot < 128 and normalized_match["radiant_win"]) or (
            player_slot >= 128 and not normalized_match["radiant_win"]
        )
    return {
        "match_id": normalized_match["match_id"],
        "account_id": account_id,
        "player_slot": player_slot if player_slot is not None else 0,
        "hero_id": _int_or_none(_pick(player, "heroId", "hero_id")),
        "is_tracked": bool(account_id == tracked_account_id) if tracked_account_id is not None else False,
        "win": win,
        "kills": _int_or_none(_pick(player, "numKills", "kills")) or 0,
        "deaths": _int_or_none(_pick(player, "numDeaths", "deaths")) or 0,
        "assists": _int_or_none(_pick(player, "numAssists", "assists")) or 0,
        "gold_per_min": _int_or_none(_pick(player, "goldPerMinute", "gold_per_min", "gpm")) or 0,
        "xp_per_min": _int_or_none(_pick(player, "experiencePerMinute", "xp_per_min", "xpm")) or 0,
        "hero_damage": _int_or_none(_pick(player, "heroDamage", "hero_damage")) or 0,
        "tower_damage": _int_or_none(_pick(player, "towerDamage", "tower_damage")) or 0,
        "hero_healing": _int_or_none(_pick(player, "heroHealing", "hero_healing")) or 0,
        "last_hits": _int_or_none(_pick(player, "numLastHits", "last_hits")) or 0,
        "lane_role": _int_or_none(_pick(player, "lane", "laneRole", "lane_role", "role", "position")),
        "raw_json": player,
    }


def normalize_player_match(match: dict[str, Any], tracked_account_id: int) -> PlayerMatch | None:
    players = match.get("players") or []
    tracked = None
    for player in players:
        account_id = _int_or_none(_pick(player, "steamAccountId", "accountId", "account_id"))
        if account_id == tracked_account_id:
            tracked = player
            break
    if not tracked:
        return None
    match_row = normalize_match(match)
    player_row = normalize_match_player(match, tracked, tracked_account_id)
    team_kills = _team_kills(players, player_row["player_slot"])
    return PlayerMatch(
        match_id=match_row["match_id"],
        account_id=tracked_account_id,
        start_time=match_row["start_time"],
        duration_seconds=match_row["duration_seconds"],
        hero_id=player_row["hero_id"],
        player_slot=player_row["player_slot"],
        radiant_win=match_row["radiant_win"],
        win=player_row["win"],
        game_mode=match_row["game_mode"],
        lobby_type=match_row["lobby_type"],
        kills=player_row["kills"],
        deaths=player_row["deaths"],
        assists=player_row["assists"],
        gold_per_min=player_row["gold_per_min"],
        xp_per_min=player_row["xp_per_min"],
        hero_damage=player_row["hero_damage"],
        tower_damage=player_row["tower_damage"],
        hero_healing=player_row["hero_healing"],
        last_hits=player_row["last_hits"],
        lane_role=player_row["lane_role"],
        team_kills=team_kills,
        raw={"match": match, "player": tracked},
    )


def _team_kills(players: list[dict[str, Any]], player_slot: int) -> int | None:
    if not players:
        return None
    target_radiant = player_slot < 128
    total = 0
    found = False
    for player in players:
        slot = _int_or_none(_pick(player, "playerSlot", "player_slot"))
        is_radiant = _bool_or_none(_pick(player, "isRadiant"))
        if slot is not None:
            same_team = (slot < 128) == target_radiant
        elif is_radiant is not None:
            same_team = is_radiant == target_radiant
        else:
            continue
        if same_team:
            found = True
            total += _int_or_none(_pick(player, "numKills", "kills")) or 0
    return total if found else None
