from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.achievements.engine import CATALOG, calculate_achievements
from app.achievements.hero_rules import HERO_RULES
from app.analytics.dto import PlayerMatch


def _achievement_map(matches: list[PlayerMatch]):
    return {item.id: item for item in calculate_achievements(matches)}


def test_catalog_contains_mvp_minimum() -> None:
    assert len(CATALOG) >= 25


def test_win_streak_and_performance_achievements() -> None:
    matches = [
        PlayerMatch(
            match_id=i,
            account_id=10,
            start_time=datetime(2026, 7, 20 - i, tzinfo=UTC),
            win=True,
            kills=15,
            deaths=0 if i == 1 else 2,
            assists=20,
            gold_per_min=720,
            xp_per_min=840,
            hero_damage=42000,
            tower_damage=9000,
            hero_healing=12000,
            team_kills=50,
        )
        for i in range(1, 6)
    ]
    achievements = _achievement_map(matches)
    assert achievements["hot_streak_5"].unlocked
    assert achievements["deathless_win"].unlocked
    assert achievements["kda_10"].unlocked
    assert achievements["farming_machine"].unlocked
    assert achievements["healer"].unlocked
    assert achievements["clean_game"].unlocked


def test_activity_achievements() -> None:
    base = datetime(2026, 7, 8, tzinfo=UTC)
    matches = [
        PlayerMatch(match_id=i, account_id=10, start_time=base - timedelta(hours=i), win=i % 2 == 0)
        for i in range(12)
    ]
    achievements = _achievement_map(matches)
    assert achievements["weekly_grinder"].unlocked
    assert achievements["marathon_day"].unlocked


def test_techies_flavor_achievement_unlocks_after_10_hero_wins_in_a_row() -> None:
    base = datetime(2026, 7, 8, tzinfo=UTC)
    matches = [
        PlayerMatch(
            match_id=i,
            account_id=10,
            start_time=base + timedelta(hours=i),
            hero_id=105,
            win=True,
        )
        for i in range(10)
    ]

    achievements = _achievement_map(matches)

    assert achievements["techies_son_of_shahed"].unlocked
    assert achievements["techies_son_of_shahed"].progress == 10
    assert achievements["techies_son_of_shahed"].evidence["heroName"] == "Techies"


def test_hero_win_streak_ignores_other_heroes_but_resets_on_same_hero_loss() -> None:
    base = datetime(2026, 7, 8, tzinfo=UTC)
    matches = [
        PlayerMatch(match_id=1, account_id=10, start_time=base, hero_id=105, win=True),
        PlayerMatch(match_id=2, account_id=10, start_time=base + timedelta(hours=1), hero_id=14, win=False),
        PlayerMatch(match_id=3, account_id=10, start_time=base + timedelta(hours=2), hero_id=105, win=True),
        PlayerMatch(match_id=4, account_id=10, start_time=base + timedelta(hours=3), hero_id=105, win=False),
        PlayerMatch(match_id=5, account_id=10, start_time=base + timedelta(hours=4), hero_id=105, win=True),
    ]

    achievements = _achievement_map(matches)

    assert achievements["techies_son_of_shahed"].progress == 2


def test_ogre_magi_damage_flavor_achievement_unlocks_at_30k_damage() -> None:
    match = PlayerMatch(
        match_id=777,
        account_id=10,
        hero_id=84,
        hero_damage=30500,
        win=True,
    )

    achievements = _achievement_map([match])

    assert achievements["ogre_magi_ludik_ebanny"].unlocked
    assert achievements["ogre_magi_ludik_ebanny"].progress == 30500
    assert achievements["ogre_magi_ludik_ebanny"].evidence["heroName"] == "Ogre Magi"
    assert achievements["ogre_magi_ludik_ebanny"].evidence["hero_damage"] == 30500


def test_hero_rule_catalog_is_data_driven() -> None:
    rule_ids = {rule.id for rule in HERO_RULES}
    catalog_ids = {item.id for item in CATALOG}
    techies_rule = next(rule for rule in HERO_RULES if rule.id == "techies_son_of_shahed")
    ogre_rule = next(rule for rule in HERO_RULES if rule.id == "ogre_magi_ludik_ebanny")

    assert "techies_son_of_shahed" in rule_ids
    assert "ogre_magi_ludik_ebanny" in rule_ids
    assert rule_ids.issubset(catalog_ids)
    assert techies_rule.title == "Сын шахеда"
    assert ogre_rule.title == "Лудик ебанный"
