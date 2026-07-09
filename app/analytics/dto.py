from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class PlayerMatch:
    match_id: int
    account_id: int
    start_time: datetime | None = None
    duration_seconds: int | None = None
    hero_id: int | None = None
    player_slot: int | None = None
    radiant_win: bool | None = None
    win: bool | None = None
    game_mode: int | None = None
    lobby_type: int | None = None
    kills: int = 0
    deaths: int = 0
    assists: int = 0
    gold_per_min: int = 0
    xp_per_min: int = 0
    hero_damage: int = 0
    tower_damage: int = 0
    hero_healing: int = 0
    last_hits: int = 0
    lane_role: int | None = None
    team_kills: int | None = None
    raw: dict[str, Any] = field(default_factory=dict)

