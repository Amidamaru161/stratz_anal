from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import JSON


class Base(DeclarativeBase):
    pass


SqliteBigIntegerPk = BigInteger().with_variant(Integer, "sqlite")


class Player(Base):
    __tablename__ = "players"

    account_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), default="")
    avatar: Mapped[str | None] = mapped_column(Text)
    rank_tier: Mapped[int | None] = mapped_column(Integer)
    leaderboard_rank: Mapped[int | None] = mapped_column(Integer)
    last_refreshed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    ratings: Mapped[list[RatingSnapshot]] = relationship(back_populates="player")


class Hero(Base):
    __tablename__ = "heroes"

    hero_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(255))
    short_name: Mapped[str | None] = mapped_column(String(255))
    image_url: Mapped[str | None] = mapped_column(Text)
    roles: Mapped[list[str]] = mapped_column(JSON, default=list)
    raw_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class Match(Base):
    __tablename__ = "matches"

    match_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    start_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_seconds: Mapped[int | None] = mapped_column(Integer)
    radiant_win: Mapped[bool | None] = mapped_column(Boolean)
    game_mode: Mapped[int | None] = mapped_column(Integer)
    lobby_type: Mapped[int | None] = mapped_column(Integer)
    raw_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MatchPlayer(Base):
    __tablename__ = "match_players"

    match_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("matches.match_id", ondelete="CASCADE"), primary_key=True
    )
    player_slot: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    hero_id: Mapped[int | None] = mapped_column(Integer)
    is_tracked: Mapped[bool] = mapped_column(Boolean, default=False)
    win: Mapped[bool | None] = mapped_column(Boolean)
    kills: Mapped[int] = mapped_column(Integer, default=0)
    deaths: Mapped[int] = mapped_column(Integer, default=0)
    assists: Mapped[int] = mapped_column(Integer, default=0)
    gold_per_min: Mapped[int] = mapped_column(Integer, default=0)
    xp_per_min: Mapped[int] = mapped_column(Integer, default=0)
    hero_damage: Mapped[int] = mapped_column(Integer, default=0)
    tower_damage: Mapped[int] = mapped_column(Integer, default=0)
    hero_healing: Mapped[int] = mapped_column(Integer, default=0)
    last_hits: Mapped[int] = mapped_column(Integer, default=0)
    lane_role: Mapped[int | None] = mapped_column(Integer)
    team_kills: Mapped[int | None] = mapped_column(Integer)
    raw_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class PlayerMatchIndex(Base):
    __tablename__ = "player_match_index"

    account_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("players.account_id", ondelete="CASCADE"), primary_key=True
    )
    match_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("matches.match_id", ondelete="CASCADE"), primary_key=True
    )
    start_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    hero_id: Mapped[int | None] = mapped_column(Integer)
    player_slot: Mapped[int | None] = mapped_column(Integer)
    radiant_win: Mapped[bool | None] = mapped_column(Boolean)
    game_mode: Mapped[int | None] = mapped_column(Integer)
    lobby_type: Mapped[int | None] = mapped_column(Integer)
    kills: Mapped[int] = mapped_column(Integer, default=0)
    deaths: Mapped[int] = mapped_column(Integer, default=0)
    assists: Mapped[int] = mapped_column(Integer, default=0)
    raw_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class SourcePayload(Base):
    __tablename__ = "source_payloads"

    id: Mapped[int] = mapped_column(SqliteBigIntegerPk, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(50))
    operation: Mapped[str] = mapped_column(String(100))
    account_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    match_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    request_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    response_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RefreshJob(Base):
    __tablename__ = "refresh_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    account_id: Mapped[int] = mapped_column(BigInteger, index=True)
    status: Mapped[str] = mapped_column(String(30), default="queued")
    message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AchievementDefinition(Base):
    __tablename__ = "achievement_definitions"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(80))
    tier: Mapped[str] = mapped_column(String(40))
    target: Mapped[float] = mapped_column(Float)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class PlayerAchievement(Base):
    __tablename__ = "player_achievements"

    account_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("players.account_id", ondelete="CASCADE"), primary_key=True
    )
    achievement_id: Mapped[str] = mapped_column(
        String(80), ForeignKey("achievement_definitions.id", ondelete="CASCADE"), primary_key=True
    )
    progress: Mapped[float] = mapped_column(Float, default=0)
    target: Mapped[float] = mapped_column(Float, default=1)
    unlocked: Mapped[bool] = mapped_column(Boolean, default=False)
    unavailable: Mapped[bool] = mapped_column(Boolean, default=False)
    unlocked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class RatingSnapshot(Base):
    __tablename__ = "rating_snapshots"

    id: Mapped[int] = mapped_column(SqliteBigIntegerPk, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("players.account_id", ondelete="CASCADE"), index=True
    )
    overall: Mapped[int] = mapped_column(Integer)
    position: Mapped[str] = mapped_column(String(20))
    breakdown: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    source: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    player: Mapped[Player] = relationship(back_populates="ratings")
