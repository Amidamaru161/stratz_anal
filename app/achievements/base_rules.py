from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Callable
from datetime import timedelta
from typing import Any

from app.achievements.models import AchievementDefinitionData, AchievementProgress, progress_result
from app.analytics.dto import PlayerMatch
from app.analytics.scoring import build_card, infer_position, is_win


def max_streak(values: list[bool], target: bool = True) -> int:
    best = current = 0
    for value in values:
        if value is target:
            current += 1
            best = max(best, current)
        else:
            current = 0
    return best


BASE_CATALOG: list[AchievementDefinitionData] = [
    AchievementDefinitionData("hot_streak_3", "Hot Streak III", "Win 3 games in a row.", "win_form", "bronze", 3),
    AchievementDefinitionData("hot_streak_5", "Hot Streak V", "Win 5 games in a row.", "win_form", "silver", 5),
    AchievementDefinitionData("hot_streak_10", "Hot Streak X", "Win 10 games in a row.", "win_form", "gold", 10),
    AchievementDefinitionData("tilt_resistant", "Tilt Resistant", "Win after 3 losses in a row.", "win_form", "silver", 1),
    AchievementDefinitionData("clutch_late_game", "Late Game Clutch", "Win a game lasting 50+ minutes.", "win_form", "silver", 1),
    AchievementDefinitionData("signature_hero", "Signature Hero", "10+ games and 60%+ winrate on one hero.", "hero_mastery", "gold", 1),
    AchievementDefinitionData("hero_spammer", "Hero Spammer", "Play one hero 10+ times in the last 30 games.", "hero_mastery", "bronze", 10),
    AchievementDefinitionData("hero_loyalist", "Hero Loyalist", "Play one hero 25+ times in the last 100 games.", "hero_mastery", "silver", 25),
    AchievementDefinitionData("wide_pool", "Wide Pool", "Win with 10 different heroes.", "hero_mastery", "silver", 10),
    AchievementDefinitionData("cursed_breaker", "Cursed Breaker", "Win on a hero after 3 losses in a row.", "hero_mastery", "gold", 1),
    AchievementDefinitionData("deathless_win", "Deathless Win", "Win with 0 deaths.", "performance", "silver", 1),
    AchievementDefinitionData("kda_5", "KDA Machine", "Reach 5+ KDA in a game.", "performance", "bronze", 5),
    AchievementDefinitionData("kda_10", "KDA Monster", "Reach 10+ KDA in a game.", "performance", "silver", 10),
    AchievementDefinitionData("farming_machine", "Farming Machine", "Reach 700+ GPM.", "performance", "silver", 700),
    AchievementDefinitionData("xp_machine", "XP Machine", "Reach 800+ XPM.", "performance", "silver", 800),
    AchievementDefinitionData("damage_dealer", "Damage Dealer", "Deal 40k+ hero damage.", "performance", "gold", 40000),
    AchievementDefinitionData("tower_melter", "Tower Melter", "Deal 8k+ tower damage.", "performance", "gold", 8000),
    AchievementDefinitionData("support_engine", "Support Engine", "Get 25+ assists in one game.", "performance", "silver", 25),
    AchievementDefinitionData("healer", "Healer", "Heal 10k+ hero HP in one game.", "performance", "silver", 10000),
    AchievementDefinitionData("clean_game", "Clean Game", "Win with <=2 deaths and 50%+ kill participation.", "performance", "gold", 1),
    AchievementDefinitionData("carry_core", "Carry Core", "Infer carry role and high farm score.", "role", "silver", 1),
    AchievementDefinitionData("mid_pressure", "Mid Pressure", "Infer mid role and high fighting score.", "role", "silver", 1),
    AchievementDefinitionData("offlane_impact", "Offlane Impact", "Infer offlane role and high impact/survival.", "role", "silver", 1),
    AchievementDefinitionData("support_brain", "Support Brain", "Infer support role and high utility.", "role", "silver", 1),
    AchievementDefinitionData("flex_player", "Flex Player", "Play 3+ inferred roles in 50 games.", "role", "gold", 3),
    AchievementDefinitionData("weekly_grinder", "Weekly Grinder", "Play 10+ games in 7 days.", "activity", "bronze", 10),
    AchievementDefinitionData("marathon_day", "Marathon Day", "Play 5+ games in one day.", "activity", "silver", 5),
    AchievementDefinitionData("returning_player", "Returning Player", "Play after a 14+ day break.", "activity", "bronze", 1),
    AchievementDefinitionData("chaos_enjoyer", "Chaos Enjoyer", "Play 3 games in a row lasting 45+ minutes.", "fun", "bronze", 3),
    AchievementDefinitionData("glass_cannon", "Glass Cannon", "Deal 35k+ hero damage with 10+ deaths.", "fun", "bronze", 1),
]


def _best_match_value(matches: list[PlayerMatch], attr: str) -> tuple[float, dict[str, Any]]:
    best_value = 0.0
    evidence: dict[str, Any] = {}
    for match in matches:
        value = float(getattr(match, attr))
        if value > best_value:
            best_value = value
            evidence = {"matchId": match.match_id, attr: value}
    return best_value, evidence


def _best_threshold(achievement_id: str, matches: list[PlayerMatch], attr: str, target: float) -> AchievementProgress:
    value, evidence = _best_match_value(matches, attr)
    return progress_result(achievement_id, value, target, evidence)


def _tilt_resistant(matches: list[PlayerMatch]) -> AchievementProgress:
    chronological = sorted(matches, key=lambda item: item.start_time or item.match_id)
    losses = 0
    for match in chronological:
        if is_win(match) and losses >= 3:
            return progress_result("tilt_resistant", 1, 1, {"matchId": match.match_id})
        losses = 0 if is_win(match) else losses + 1
    return progress_result("tilt_resistant", min(losses, 3) / 3, 1)


def _cursed_breaker(matches: list[PlayerMatch]) -> AchievementProgress:
    chronological = sorted(matches, key=lambda item: item.start_time or item.match_id)
    losses_by_hero: dict[int, int] = defaultdict(int)
    best = 0
    for match in chronological:
        if match.hero_id is None:
            continue
        if is_win(match):
            if losses_by_hero[match.hero_id] >= 3:
                return progress_result("cursed_breaker", 1, 1, {"matchId": match.match_id, "heroId": match.hero_id})
            losses_by_hero[match.hero_id] = 0
        else:
            losses_by_hero[match.hero_id] += 1
            best = max(best, losses_by_hero[match.hero_id])
    return progress_result("cursed_breaker", min(best / 3, 1), 1)


def _signature_hero(matches: list[PlayerMatch]) -> AchievementProgress:
    by_hero: dict[int, list[PlayerMatch]] = defaultdict(list)
    for match in matches:
        if match.hero_id is not None:
            by_hero[match.hero_id].append(match)
    best_score = 0.0
    best_evidence: dict[str, Any] = {}
    for hero_id, rows in by_hero.items():
        games = len(rows)
        wins = sum(1 for row in rows if is_win(row))
        winrate = wins / games * 100 if games else 0
        progress = min(games / 10, 1) * min(winrate / 60, 1)
        if progress > best_score:
            best_score = progress
            best_evidence = {"heroId": hero_id, "games": games, "wins": wins, "winRate": round(winrate, 1)}
        if games >= 10 and winrate >= 60:
            return progress_result("signature_hero", 1, 1, best_evidence)
    return progress_result("signature_hero", best_score, 1, best_evidence)


def _role_progress(matches: list[PlayerMatch], achievement_id: str, role: str) -> AchievementProgress:
    card = build_card(matches)
    rows = {row["label"]: row["value"] for row in card["rows"]}
    role_matches = card["position"] == role
    if achievement_id == "carry_core":
        score = rows.get("FRM", 0)
        unlocked = role_matches and score >= 75
    elif achievement_id == "mid_pressure":
        score = rows.get("FGT", 0)
        unlocked = role_matches and score >= 75
    elif achievement_id == "offlane_impact":
        score = (rows.get("IMP", 0) + rows.get("SUR", 0)) / 2
        unlocked = role_matches and score >= 70
    else:
        score = rows.get("UTL", 0)
        unlocked = role_matches and score >= 75
    return AchievementProgress(
        id=achievement_id,
        progress=1 if unlocked else min(score / 75, 0.99),
        target=1,
        unlocked=unlocked,
        evidence={"position": card["position"], "score": round(score, 1)},
    )


def _flex_player(matches: list[PlayerMatch]) -> AchievementProgress:
    recent = matches[:50]
    buckets = [recent[i : i + 10] for i in range(0, len(recent), 10) if recent[i : i + 10]]
    roles = {infer_position(bucket) for bucket in buckets}
    roles.discard("FLX")
    return progress_result("flex_player", len(roles), 3, {"roles": sorted(roles)})


def _returning_player(matches: list[PlayerMatch]) -> AchievementProgress:
    chronological = [m for m in sorted(matches, key=lambda item: item.start_time or item.match_id) if m.start_time]
    longest_days = 0
    evidence: dict[str, Any] = {}
    for previous, current in zip(chronological, chronological[1:], strict=False):
        gap = current.start_time - previous.start_time  # type: ignore[operator]
        days = gap.days
        if days > longest_days:
            longest_days = days
            evidence = {"matchId": current.match_id, "gapDays": days}
        if gap >= timedelta(days=14):
            return progress_result("returning_player", 1, 1, evidence)
    return progress_result("returning_player", min(longest_days / 14, 1), 1, evidence)


def _clean_game(matches: list[PlayerMatch]) -> AchievementProgress:
    best = 0.0
    evidence: dict[str, Any] = {}
    has_team_kills = any(match.team_kills for match in matches)
    if not has_team_kills:
        return AchievementProgress("clean_game", 0, 1, False, unavailable=True, evidence={"reason": "team_kills_missing"})
    for match in matches:
        if not match.team_kills:
            continue
        participation = (match.kills + match.assists) / max(1, match.team_kills)
        score = min(participation / 0.5, 1)
        if is_win(match) and match.deaths <= 2 and participation >= 0.5:
            return progress_result(
                "clean_game",
                1,
                1,
                {"matchId": match.match_id, "deaths": match.deaths, "killParticipation": round(participation, 3)},
            )
        if score > best:
            best = score
            evidence = {"matchId": match.match_id, "killParticipation": round(participation, 3)}
    return progress_result("clean_game", best, 1, evidence)


def _healer(matches: list[PlayerMatch]) -> AchievementProgress:
    if not any(match.hero_healing for match in matches):
        return AchievementProgress("healer", 0, 10000, False, unavailable=True, evidence={"reason": "hero_healing_missing"})
    value, evidence = _best_match_value(matches, "hero_healing")
    return progress_result("healer", value, 10000, evidence)


def calculate_base_achievements(matches: list[PlayerMatch]) -> list[AchievementProgress]:
    matches = sorted(matches, key=lambda item: item.start_time or item.match_id, reverse=True)
    wins = [is_win(match) for match in matches]
    hero_counts_30 = Counter(match.hero_id for match in matches[:30] if match.hero_id is not None)
    hero_counts_100 = Counter(match.hero_id for match in matches[:100] if match.hero_id is not None)
    won_heroes = {match.hero_id for match in matches if match.hero_id is not None and is_win(match)}
    dates = Counter(match.start_time.date().isoformat() for match in matches if match.start_time)
    recent_week = []
    if matches and matches[0].start_time:
        cutoff = matches[0].start_time - timedelta(days=7)
        recent_week = [match for match in matches if match.start_time and match.start_time >= cutoff]

    longest_late_streak = max_streak([(match.duration_seconds or 0) >= 45 * 60 for match in matches])
    best_kda = max(((match.kills + match.assists) / max(1, match.deaths) for match in matches), default=0)
    best_kda_match = max(matches, key=lambda m: (m.kills + m.assists) / max(1, m.deaths), default=None)

    calculators: dict[str, Callable[[], AchievementProgress]] = {
        "hot_streak_3": lambda: progress_result("hot_streak_3", max_streak(wins), 3),
        "hot_streak_5": lambda: progress_result("hot_streak_5", max_streak(wins), 5),
        "hot_streak_10": lambda: progress_result("hot_streak_10", max_streak(wins), 10),
        "tilt_resistant": lambda: _tilt_resistant(matches),
        "clutch_late_game": lambda: progress_result(
            "clutch_late_game",
            1 if any(is_win(match) and (match.duration_seconds or 0) >= 50 * 60 for match in matches) else 0,
            1,
        ),
        "signature_hero": lambda: _signature_hero(matches),
        "hero_spammer": lambda: progress_result("hero_spammer", hero_counts_30.most_common(1)[0][1] if hero_counts_30 else 0, 10),
        "hero_loyalist": lambda: progress_result("hero_loyalist", hero_counts_100.most_common(1)[0][1] if hero_counts_100 else 0, 25),
        "wide_pool": lambda: progress_result("wide_pool", len(won_heroes), 10, {"heroIds": sorted(won_heroes)}),
        "cursed_breaker": lambda: _cursed_breaker(matches),
        "deathless_win": lambda: progress_result(
            "deathless_win",
            1 if any(is_win(match) and match.deaths == 0 for match in matches) else 0,
            1,
        ),
        "kda_5": lambda: progress_result("kda_5", best_kda, 5, {"matchId": best_kda_match.match_id if best_kda_match else None}),
        "kda_10": lambda: progress_result("kda_10", best_kda, 10, {"matchId": best_kda_match.match_id if best_kda_match else None}),
        "farming_machine": lambda: _best_threshold("farming_machine", matches, "gold_per_min", 700),
        "xp_machine": lambda: _best_threshold("xp_machine", matches, "xp_per_min", 800),
        "damage_dealer": lambda: _best_threshold("damage_dealer", matches, "hero_damage", 40000),
        "tower_melter": lambda: _best_threshold("tower_melter", matches, "tower_damage", 8000),
        "support_engine": lambda: _best_threshold("support_engine", matches, "assists", 25),
        "healer": lambda: _healer(matches),
        "clean_game": lambda: _clean_game(matches),
        "carry_core": lambda: _role_progress(matches, "carry_core", "CRY"),
        "mid_pressure": lambda: _role_progress(matches, "mid_pressure", "MID"),
        "offlane_impact": lambda: _role_progress(matches, "offlane_impact", "OFF"),
        "support_brain": lambda: _role_progress(matches, "support_brain", "SUP"),
        "flex_player": lambda: _flex_player(matches),
        "weekly_grinder": lambda: progress_result("weekly_grinder", len(recent_week), 10),
        "marathon_day": lambda: progress_result("marathon_day", max(dates.values(), default=0), 5),
        "returning_player": lambda: _returning_player(matches),
        "chaos_enjoyer": lambda: progress_result("chaos_enjoyer", longest_late_streak, 3),
        "glass_cannon": lambda: progress_result(
            "glass_cannon",
            1 if any(match.hero_damage >= 35000 and match.deaths >= 10 for match in matches) else 0,
            1,
        ),
    }

    return [calculators[item.id]() for item in BASE_CATALOG]
