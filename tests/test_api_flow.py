from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import Settings
from app.services.analytics import (
    seed_achievement_definitions,
    sync_player_achievements,
    sync_rating,
)
from app.services.refresh import RefreshCooldownError, assert_refresh_allowed
from app.services.storage import load_player_matches, upsert_match_bundle, upsert_player
from app.storage.models import Player, SourcePayload
from app.stratz.client import StratzClient


def seed_player(session: Session) -> None:
    upsert_player(
        session,
        {
            "account_id": 42,
            "name": "Dotka Enjoyer",
            "avatar": None,
            "rank_tier": 55,
            "leaderboard_rank": 123,
        },
    )
    for i in range(1, 8):
        upsert_match_bundle(
            session,
            42,
            {
                "id": 1000 + i,
                "startDateTime": datetime(2026, 7, i, tzinfo=UTC).isoformat(),
                "durationSeconds": 3300,
                "radiantWin": True,
                "gameMode": 22 if i <= 3 else 23 if i <= 5 else 18,
                "lobbyType": 7 if i <= 3 else 0,
                "players": [
                    {
                        "steamAccountId": 42,
                        "heroId": 8,
                        "playerSlot": 0,
                        "isVictory": True,
                        "numKills": 14,
                        "numDeaths": 2,
                        "numAssists": 16,
                        "goldPerMinute": 710,
                        "experiencePerMinute": 830,
                        "heroDamage": 41000,
                        "towerDamage": 8500,
                        "heroHealing": 11000,
                        "numLastHits": 250,
                        "item0Id": 999,
                        "item1Id": 998,
                        "abilities": [
                            {"time": 10, "abilityId": 2, "level": 1, "isTalent": False},
                            {"time": 20, "abilityId": 1, "level": 2, "isTalent": False},
                        ],
                    },
                    {"steamAccountId": 43, "playerSlot": 1, "numKills": 10},
                ],
            },
        )
    session.flush()
    matches = load_player_matches(session, 42, 100)
    sync_rating(session, 42, matches)
    sync_player_achievements(session, 42, matches)
    seed_achievement_definitions(session)
    session.commit()


def test_summary_matches_achievements_and_leaderboard(client: TestClient, session: Session) -> None:
    seed_player(session)

    summary = client.get("/v1/players/42/summary")
    assert summary.status_code == 200
    assert summary.json()["card"]["overall"] >= 35
    assert any(
        row["label"] == "Ranked All Pick" and row["matches"] == 3
        for row in summary.json()["breakdowns"]["byGameMode"]
    )
    assert any(
        row["bucket"] == "ranked" and row["matches"] == 3
        for row in summary.json()["breakdowns"]["byRanked"]
    )

    limited_summary = client.get("/v1/players/42/summary?limit=3")
    assert limited_summary.status_code == 200
    assert limited_summary.json()["matches"] == 3
    assert limited_summary.json()["card"]["source"]["limit"] == 3

    matches = client.get("/v1/players/42/matches?limit=500")
    assert matches.status_code == 200
    assert len(matches.json()) == 7

    breakdowns = client.get("/v1/players/42/breakdowns?limit=3")
    assert breakdowns.status_code == 200
    assert breakdowns.json()["matches"] == 3
    assert breakdowns.json()["limit"] == 3
    assert any(row["label"] == "Ability Draft" and row["matches"] == 2 for row in breakdowns.json()["byGameMode"])

    heroes = client.get("/v1/players/42/heroes?limit=3")
    assert heroes.status_code == 200

    achievements = client.get("/v1/players/42/achievements?limit=3")
    assert achievements.status_code == 200
    assert len(achievements.json()) >= 25
    assert any(item["evidence"].get("limit") == 3 for item in achievements.json())

    rating = client.get("/v1/players/42/rating?limit=3")
    assert rating.status_code == 200
    assert rating.json()["source"]["limit"] == 3

    leaderboard = client.get("/v1/leaderboard")
    assert leaderboard.status_code == 200
    assert leaderboard.json()[0]["accountId"] == 42


def test_catalog_endpoint_seeds_hero_flavor_achievements(client: TestClient) -> None:
    response = client.get("/v1/achievements")

    assert response.status_code == 200
    body = response.json()
    assert any(item["id"] == "techies_son_of_shahed" for item in body)
    assert any(item["category"] == "hero_flavor" for item in body)


def test_style_endpoint_scores_build_deviation(client: TestClient, session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    seed_player(session)

    async def fake_fetch_hero_builds(self: StratzClient, hero_id: int, match_limit: int = 10000) -> dict:
        assert hero_id == 8
        return {
            "heroStats": {
                "itemFullPurchase": [
                    {"heroId": 8, "itemId": 65, "time": 10, "matchCount": 1000, "winCount": 550},
                    {"heroId": 8, "itemId": 180, "time": 15, "matchCount": 900, "winCount": 500},
                ],
                "itemStartingPurchase": [],
                "itemBootPurchase": [],
                "itemNeutral": [],
                "talent": [],
                "abilityMinLevel": [
                    {"heroId": 8, "abilityId": 1, "level": 1, "matchCount": 1000, "winCount": 550},
                    {"heroId": 8, "abilityId": 2, "level": 2, "matchCount": 900, "winCount": 500},
                ],
                "abilityMaxLevel": [],
                "guide": [],
            },
            "constants": {"heroes": [], "items": [], "abilities": []},
        }

    monkeypatch.setattr(StratzClient, "fetch_hero_builds", fake_fetch_hero_builds)

    response = client.get("/v1/players/42/style?limit=3")

    assert response.status_code == 200
    body = response.json()
    assert body["matchesConsidered"] == 3
    assert body["ratedMatches"] == 3
    assert body["styleScore"] == 100.0
    assert body["label"] == "Вне патча"
    assert session.query(SourcePayload).filter_by(operation="hero_builds").count() == 1


def test_global_hero_winrates_endpoint(client: TestClient, session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_fetch_hero_global_stats(self: StratzClient) -> dict:
        return {
            "heroStats": {
                "stats": [
                    {"heroId": 84, "matchCount": 1000, "winCount": 550},
                    {"heroId": 14, "matchCount": 100, "winCount": 70},
                    {"heroId": 1, "matchCount": 20, "winCount": 20},
                ]
            },
            "constants": {
                "heroes": [
                    {"id": 84, "name": "npc_dota_hero_ogre_magi", "displayName": "Ogre Magi"},
                    {"id": 14, "name": "npc_dota_hero_pudge", "displayName": "Pudge"},
                    {"id": 1, "name": "npc_dota_hero_antimage", "displayName": "Anti-Mage"},
                ]
            },
        }

    monkeypatch.setattr(StratzClient, "fetch_hero_global_stats", fake_fetch_hero_global_stats)

    response = client.get("/v1/heroes/winrates?min_matches=100&limit=2")

    assert response.status_code == 200
    body = response.json()
    assert [item["heroId"] for item in body] == [14, 84]
    assert body[0]["displayName"] == "Pudge"
    assert body[0]["winRate"] == 70.0
    assert body[1]["matchCount"] == 1000
    assert session.query(SourcePayload).filter_by(operation="hero_global_stats").count() == 1


def test_hero_builds_endpoint(client: TestClient, session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_fetch_hero_builds(self: StratzClient, hero_id: int, match_limit: int = 10000) -> dict:
        assert hero_id == 84
        assert match_limit == 5000
        return {
            "heroStats": {
                "itemFullPurchase": [
                    {"heroId": 84, "itemId": 65, "time": 12, "matchCount": 100, "winCount": 60}
                ],
                "itemStartingPurchase": [],
                "itemBootPurchase": [
                    {
                        "heroId": 84,
                        "itemId": 180,
                        "timeAverage": 700,
                        "matchCount": 120,
                        "winCount": 70,
                    }
                ],
                "itemNeutral": [],
                "talent": [
                    {"heroId": 84, "abilityId": 403, "timeAverage": 1100, "matchCount": 110, "winCount": 66}
                ],
                "abilityMinLevel": [
                    {"heroId": 84, "abilityId": 5438, "level": 1, "matchCount": 100, "winCount": 55}
                ],
                "abilityMaxLevel": [],
                "guide": [
                    {
                        "heroId": 84,
                        "matchCount": 1,
                        "guides": [{"matchId": 9001, "itemIds": [65], "neutralItemIds": []}],
                    }
                ],
            },
            "constants": {
                "heroes": [{"id": 84, "name": "npc_dota_hero_ogre_magi", "displayName": "Ogre Magi"}],
                "items": [
                    {"id": 65, "name": "item_hand_of_midas", "displayName": "Hand of Midas"},
                    {"id": 180, "name": "item_arcane_boots", "displayName": "Arcane Boots"},
                ],
                "abilities": [
                    {"id": 403, "name": "special_bonus_unique_ogre_magi"},
                    {"id": 5438, "name": "ogre_magi_fireblast"},
                ],
            },
        }

    monkeypatch.setattr(StratzClient, "fetch_hero_builds", fake_fetch_hero_builds)

    response = client.get("/v1/heroes/84/builds?min_matches=10&limit=5&match_limit=5000")

    assert response.status_code == 200
    body = response.json()
    assert body["heroId"] == 84
    assert body["heroName"] == "Ogre Magi"
    assert body["coreItems"][0]["itemName"] == "Hand of Midas"
    assert body["coreItems"][0]["winRate"] == 60.0
    assert body["boots"][0]["averageTimeMinute"] == 11.7
    assert body["talents"][0]["abilityName"] == "special_bonus_unique_ogre_magi"
    assert body["skillBuild"][0]["abilityName"] == "ogre_magi_fireblast"
    assert body["guides"][0]["itemNames"] == ["Hand of Midas"]
    assert session.query(SourcePayload).filter_by(operation="hero_builds").count() == 1


def test_refresh_cooldown_handles_sqlite_naive_datetimes(session: Session) -> None:
    session.add(
        Player(
            account_id=99,
            name="Naive Time Enjoyer",
            last_refreshed_at=datetime.now(UTC).replace(tzinfo=None),
        )
    )
    session.commit()

    with pytest.raises(RefreshCooldownError):
        assert_refresh_allowed(session, 99, Settings(refresh_cooldown_seconds=900))
