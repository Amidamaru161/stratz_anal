from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AchievementDefinitionData:
    id: str
    title: str
    description: str
    category: str
    tier: str
    target: float


@dataclass(frozen=True)
class AchievementProgress:
    id: str
    progress: float
    target: float
    unlocked: bool
    unavailable: bool = False
    evidence: dict[str, Any] | None = None

    @property
    def progress_percent(self) -> float:
        if self.target <= 0:
            return 100.0 if self.unlocked else 0.0
        return round(min(max(self.progress / self.target * 100, 0), 100), 1)


def progress_result(
    achievement_id: str,
    progress: float,
    target: float,
    evidence: dict[str, Any] | None = None,
) -> AchievementProgress:
    return AchievementProgress(
        id=achievement_id,
        progress=progress,
        target=target,
        unlocked=progress >= target,
        evidence=evidence or {},
    )

