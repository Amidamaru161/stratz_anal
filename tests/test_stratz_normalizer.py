from __future__ import annotations

from app.stratz.normalizer import (
    extract_matches,
    normalize_hero_builds,
    normalize_hero_global_winrates,
    normalize_match,
    normalize_player,
    normalize_player_match,
)


def test_normalize_player_bundle() -> None:
    payload = {
        "player": {
            "steamAccount": {
                "name": "Dotka Enjoyer",
                "fullAvatar": "https://avatar",
                "seasonRank": 55,
                "leaderboardRank": 123,
            },
            "matches": [],
        }
    }
    assert normalize_player(payload, 42)["name"] == "Dotka Enjoyer"
    assert extract_matches(payload) == []


def test_normalize_match_and_tracked_player() -> None:
    payload = {
        "id": 100,
        "startDateTime": 1783344361,
        "durationSeconds": 3600,
        "radiantWin": True,
        "gameMode": "TURBO",
        "lobbyType": "UNRANKED",
        "players": [
            {
                "steamAccountId": 42,
                "heroId": 8,
                "playerSlot": 0,
                "numKills": 12,
                "numDeaths": 3,
                "numAssists": 9,
                "goldPerMinute": 650,
                "experiencePerMinute": 700,
            },
            {"steamAccountId": 43, "playerSlot": 1, "numKills": 8},
        ],
    }
    match = normalize_match(payload)
    assert match["match_id"] == 100
    assert match["game_mode"] == 23
    assert match["lobby_type"] == 0
    player_match = normalize_player_match(payload, 42)
    assert player_match is not None
    assert player_match.win is True
    assert player_match.team_kills == 20


def test_normalize_hero_global_winrates() -> None:
    payload = {
        "heroStats": {
            "stats": [
                {"heroId": 84, "matchCount": 1000, "winCount": 550},
                {"heroId": 14, "matchCount": 500, "winCount": 225},
            ]
        },
        "constants": {
            "heroes": [
                {
                    "id": 84,
                    "name": "npc_dota_hero_ogre_magi",
                    "displayName": "Ogre Magi",
                    "shortName": "ogre_magi",
                    "roles": ["Support", "Nuker"],
                }
            ]
        },
    }

    rows = normalize_hero_global_winrates(payload)

    assert rows[0]["hero_id"] == 84
    assert rows[0]["display_name"] == "Ogre Magi"
    assert rows[0]["match_count"] == 1000
    assert rows[0]["win_count"] == 550
    assert rows[0]["loss_count"] == 450
    assert rows[0]["win_rate"] == 55.0
    assert rows[1]["display_name"] == "Hero 14"


def test_normalize_hero_builds_aggregates_items_and_names() -> None:
    payload = {
        "heroStats": {
            "itemFullPurchase": [
                {"heroId": 84, "itemId": 65, "time": 10, "matchCount": 100, "winCount": 55},
                {"heroId": 84, "itemId": 65, "time": 20, "matchCount": 200, "winCount": 125},
                {"heroId": 84, "itemId": 1, "time": 12, "matchCount": 5, "winCount": 5},
            ],
            "itemStartingPurchase": [
                {"heroId": 84, "itemId": 44, "wasGiven": False, "matchCount": 120, "winCount": 60}
            ],
            "itemBootPurchase": [
                {"heroId": 84, "itemId": 180, "timeAverage": 700, "matchCount": 150, "winCount": 90}
            ],
            "itemNeutral": [
                {
                    "heroId": 84,
                    "itemId": 123,
                    "matchCount": 100,
                    "winCount": 50,
                    "equippedMatchCount": 80,
                    "equippedMatchWinCount": 48,
                }
            ],
            "talent": [
                {"heroId": 84, "abilityId": 403, "timeAverage": 1200, "matchCount": 300, "winCount": 180}
            ],
            "abilityMinLevel": [
                {"heroId": 84, "abilityId": 5438, "level": 1, "matchCount": 250, "winCount": 130},
                {"heroId": 84, "abilityId": 5439, "level": 1, "matchCount": 100, "winCount": 70},
            ],
            "guide": [
                {
                    "heroId": 84,
                    "matchCount": 1,
                    "guides": [{"matchId": 10, "itemIds": [65, 180], "neutralItemIds": [123]}],
                }
            ],
        },
        "constants": {
            "heroes": [{"id": 84, "name": "npc_dota_hero_ogre_magi", "displayName": "Ogre Magi"}],
            "items": [
                {"id": 65, "name": "item_hand_of_midas", "displayName": "Hand of Midas"},
                {"id": 44, "name": "item_tango", "displayName": "Tango"},
                {"id": 180, "name": "item_arcane_boots", "displayName": "Arcane Boots"},
                {"id": 123, "name": "item_pupil_gift", "displayName": "Pupil's Gift"},
            ],
            "abilities": [
                {"id": 403, "name": "special_bonus_unique_ogre_magi"},
                {"id": 5438, "name": "ogre_magi_fireblast"},
                {"id": 5439, "name": "ogre_magi_ignite"},
            ],
        },
    }

    builds = normalize_hero_builds(payload, 84, min_matches=10, limit=5)

    assert builds["hero_name"] == "Ogre Magi"
    assert builds["core_items"][0]["item_name"] == "Hand of Midas"
    assert builds["core_items"][0]["match_count"] == 300
    assert builds["core_items"][0]["win_count"] == 180
    assert builds["core_items"][0]["win_rate"] == 60.0
    assert builds["core_items"][0]["average_time_minute"] == 16.7
    assert builds["starting_items"][0]["was_given"] is False
    assert builds["boots"][0]["average_time_seconds"] == 700
    assert builds["boots"][0]["average_time_minute"] == 11.7
    assert builds["neutral_items"][0]["win_rate"] == 60.0
    assert builds["talents"][0]["ability_name"] == "special_bonus_unique_ogre_magi"
    assert builds["skill_build"][0]["ability_name"] == "ogre_magi_fireblast"
    assert builds["guides"][0]["item_names"] == ["Hand of Midas", "Arcane Boots"]
