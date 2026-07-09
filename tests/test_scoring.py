from __future__ import annotations

from datetime import UTC, datetime

from app.analytics.dto import PlayerMatch
from app.analytics.scoring import build_card, infer_position, is_win


def test_is_win_from_slot_and_radiant_result() -> None:
    assert is_win(PlayerMatch(match_id=1, account_id=10, player_slot=0, radiant_win=True))
    assert is_win(PlayerMatch(match_id=2, account_id=10, player_slot=128, radiant_win=False))
    assert not is_win(PlayerMatch(match_id=3, account_id=10, player_slot=128, radiant_win=True))


def test_build_card_preserves_legacy_shape() -> None:
    matches = [
        PlayerMatch(
            match_id=i,
            account_id=10,
            start_time=datetime(2026, 7, i, tzinfo=UTC),
            win=i % 2 == 0,
            kills=10,
            deaths=3,
            assists=14,
            gold_per_min=650,
            xp_per_min=780,
            hero_damage=30000,
            tower_damage=5500,
            last_hits=220,
        )
        for i in range(1, 11)
    ]
    card = build_card(matches)
    assert set(card) == {"overall", "position", "rows", "source"}
    assert 35 <= card["overall"] <= 99
    assert [row["label"] for row in card["rows"]] == ["IMP", "FRM", "FGT", "SUR", "OBJ", "UTL"]


def test_infer_support_from_assists_and_low_farm() -> None:
    matches = [
        PlayerMatch(match_id=i, account_id=10, assists=20, last_hits=60, tower_damage=500, gold_per_min=380)
        for i in range(1, 7)
    ]
    assert infer_position(matches) == "SUP"

