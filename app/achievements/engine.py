from __future__ import annotations

from app.achievements.base_rules import BASE_CATALOG, calculate_base_achievements
from app.achievements.hero_rules import HERO_CATALOG, calculate_hero_achievements
from app.achievements.models import AchievementDefinitionData, AchievementProgress
from app.analytics.dto import PlayerMatch

CATALOG: list[AchievementDefinitionData] = [*BASE_CATALOG, *HERO_CATALOG]


def calculate_achievements(matches: list[PlayerMatch]) -> list[AchievementProgress]:
    return [*calculate_base_achievements(matches), *calculate_hero_achievements(matches)]

