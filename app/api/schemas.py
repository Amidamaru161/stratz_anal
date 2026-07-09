from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class JobResponse(BaseModel):
    id: str
    accountId: int
    status: str
    message: str | None = None
    createdAt: datetime | None = None
    startedAt: datetime | None = None
    finishedAt: datetime | None = None


class CardRow(BaseModel):
    label: str
    value: int


class PlayerCard(BaseModel):
    overall: int
    position: str
    rows: list[CardRow]
    source: dict[str, Any]
    createdAt: datetime | None = None


class GameModeBreakdownRow(BaseModel):
    gameMode: int | None = None
    label: str
    matches: int
    wins: int
    losses: int
    winRate: float
    kills: int
    deaths: int
    assists: int
    kda: float
    avgKills: float
    avgDeaths: float
    avgAssists: float


class RankedBreakdownRow(BaseModel):
    bucket: str
    label: str
    matches: int
    wins: int
    losses: int
    winRate: float
    kills: int
    deaths: int
    assists: int
    kda: float
    avgKills: float
    avgDeaths: float
    avgAssists: float


class MatchBreakdowns(BaseModel):
    byGameMode: list[GameModeBreakdownRow]
    byRanked: list[RankedBreakdownRow]


class PlayerBreakdowns(MatchBreakdowns):
    accountId: int
    matches: int
    limit: int


class PlayerSummary(BaseModel):
    accountId: int
    name: str
    avatar: str | None = None
    rankTier: int | None = None
    leaderboardRank: int | None = None
    lastRefreshedAt: datetime | None = None
    matches: int
    wins: int
    losses: int
    winRate: float
    kills: int
    deaths: int
    assists: int
    kda: float
    recentForm: list[str]
    card: PlayerCard
    breakdowns: MatchBreakdowns


class MatchResponse(BaseModel):
    matchId: int
    startedAt: datetime | None = None
    durationSeconds: int | None = None
    heroId: int | None = None
    gameMode: int | None = None
    gameModeName: str
    lobbyType: int | None = None
    rankedBucket: str
    rankedLabel: str
    won: bool
    kills: int
    deaths: int
    assists: int
    gpm: int
    xpm: int
    heroDamage: int
    towerDamage: int
    heroHealing: int
    lastHits: int
    laneRole: int | None = None


class HeroStatsResponse(BaseModel):
    heroId: int
    games: int
    wins: int
    losses: int
    winRate: float
    avgKills: float
    avgDeaths: float
    avgAssists: float
    kda: float
    avgGpm: float
    avgXpm: float
    recentForm: list[str]


class HeroGlobalWinrateResponse(BaseModel):
    heroId: int
    name: str
    displayName: str
    shortName: str | None = None
    imageUrl: str | None = None
    roles: list[str]
    matchCount: int
    winCount: int
    lossCount: int
    winRate: float


class HeroBuildItemResponse(BaseModel):
    itemId: int
    itemName: str
    shortName: str | None = None
    matchCount: int
    winCount: int
    winRate: float
    metaScore: float
    averageTimeMinute: float | None = None
    averageTimeSeconds: float | None = None
    wasGiven: bool | None = None
    equippedMatchCount: int | None = None
    equippedWinCount: int | None = None


class HeroBuildAbilityResponse(BaseModel):
    abilityId: int
    abilityName: str
    matchCount: int
    winCount: int
    winRate: float
    metaScore: float
    averageTimeMinute: float | None = None
    averageTimeSeconds: float | None = None


class HeroSkillBuildResponse(BaseModel):
    level: int
    abilityId: int
    abilityName: str
    matchCount: int
    winCount: int
    winRate: float
    metaScore: float


class HeroBuildGuideResponse(BaseModel):
    matchId: int | None = None
    createdAt: datetime | None = None
    itemIds: list[int]
    itemNames: list[str]
    neutralItemIds: list[int]
    neutralItemNames: list[str]


class HeroBuildResponse(BaseModel):
    heroId: int
    heroName: str
    shortName: str | None = None
    source: dict[str, Any]
    coreItems: list[HeroBuildItemResponse]
    startingItems: list[HeroBuildItemResponse]
    boots: list[HeroBuildItemResponse]
    neutralItems: list[HeroBuildItemResponse]
    talents: list[HeroBuildAbilityResponse]
    skillBuild: list[HeroSkillBuildResponse]
    guides: list[HeroBuildGuideResponse]


class AchievementResponse(BaseModel):
    id: str
    title: str
    description: str
    category: str
    tier: str
    progress: float
    target: float
    progressPercent: float
    unlocked: bool
    unavailable: bool
    unlockedAt: datetime | None = None
    evidence: dict[str, Any] = Field(default_factory=dict)


class RatingResponse(BaseModel):
    accountId: int
    overall: int
    position: str
    breakdown: dict[str, Any]
    source: dict[str, Any]
    createdAt: datetime

    model_config = ConfigDict(from_attributes=True)


class StyleSkillChoice(BaseModel):
    level: int
    abilityId: int


class StyleMatchResponse(BaseModel):
    matchId: int
    heroId: int | None = None
    heroName: str | None = None
    score: float | None = None
    itemScore: float | None = None
    skillScore: float | None = None
    itemOrderAvailable: bool
    reason: str | None = None
    actualItems: list[int]
    metaItems: list[int]
    actualSkills: list[StyleSkillChoice]
    metaSkills: dict[int, int]


class StyleScoreResponse(BaseModel):
    accountId: int
    limit: int
    matchesConsidered: int
    metaHeroes: int
    styleScore: float | None = None
    label: str
    itemScore: float | None = None
    skillScore: float | None = None
    ratedMatches: int
    matches: list[StyleMatchResponse]


class LeaderboardRow(BaseModel):
    rank: int
    accountId: int
    name: str
    avatar: str | None = None
    overall: int
    position: str
    winRate: float | None = None
    matches: int | None = None
    createdAt: datetime
