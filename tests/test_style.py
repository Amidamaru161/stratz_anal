from __future__ import annotations

from app.analytics.dto import PlayerMatch
from app.analytics.style import build_style_score


def test_style_score_rewards_deviation_from_meta_order_and_skill_build() -> None:
    match = PlayerMatch(
        match_id=1,
        account_id=42,
        hero_id=84,
        raw={
            "player": {
                "item0Id": 999,
                "item1Id": 998,
                "abilities": [
                    {"time": 10, "abilityId": 2, "level": 1, "isTalent": False},
                    {"time": 20, "abilityId": 1, "level": 2, "isTalent": False},
                ],
            }
        },
    )
    meta = {
        84: {
            "core_items": [
                {"item_id": 65, "average_time_minute": 10, "meta_score": 95},
                {"item_id": 180, "average_time_minute": 15, "meta_score": 90},
            ],
            "skill_build": [
                {"level": 1, "ability_id": 1, "match_count": 1000, "meta_score": 90},
                {"level": 2, "ability_id": 2, "match_count": 900, "meta_score": 80},
            ],
        }
    }

    payload = build_style_score([match], meta)

    assert payload["style_score"] == 100.0
    assert payload["label"] == "Вне патча"
    assert payload["matches"][0]["item_order_available"] is False
    assert payload["matches"][0]["item_score"] == 100.0
    assert payload["matches"][0]["skill_score"] == 100.0


def test_style_score_reports_unavailable_when_match_has_no_build_data() -> None:
    match = PlayerMatch(match_id=1, account_id=42, hero_id=84)

    payload = build_style_score([match], {84: {"core_items": [], "skill_build": []}})

    assert payload["style_score"] is None
    assert payload["rated_matches"] == 0
    assert payload["label"] == "Недостаточно данных"
