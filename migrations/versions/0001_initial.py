"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-07-08
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None

sqlite_big_integer_pk = sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def upgrade() -> None:
    op.create_table(
        "players",
        sa.Column("account_id", sa.BigInteger(), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("avatar", sa.Text(), nullable=True),
        sa.Column("rank_tier", sa.Integer(), nullable=True),
        sa.Column("leaderboard_rank", sa.Integer(), nullable=True),
        sa.Column("last_refreshed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "heroes",
        sa.Column("hero_id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("short_name", sa.String(length=255), nullable=True),
        sa.Column("image_url", sa.Text(), nullable=True),
        sa.Column("roles", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("raw_json", sa.JSON(), nullable=False, server_default="{}"),
    )

    op.create_table(
        "matches",
        sa.Column("match_id", sa.BigInteger(), primary_key=True),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("radiant_win", sa.Boolean(), nullable=True),
        sa.Column("game_mode", sa.Integer(), nullable=True),
        sa.Column("lobby_type", sa.Integer(), nullable=True),
        sa.Column("raw_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("fetched_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "source_payloads",
        sa.Column("id", sqlite_big_integer_pk, primary_key=True, autoincrement=True),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("operation", sa.String(length=100), nullable=False),
        sa.Column("account_id", sa.BigInteger(), nullable=True),
        sa.Column("match_id", sa.BigInteger(), nullable=True),
        sa.Column("request_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("response_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("fetched_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_source_payloads_account_operation", "source_payloads", ["account_id", "operation"])
    op.create_index("ix_source_payloads_match_operation", "source_payloads", ["match_id", "operation"])

    op.create_table(
        "refresh_jobs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("account_id", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_refresh_jobs_account_created", "refresh_jobs", ["account_id", "created_at"])

    op.create_table(
        "match_players",
        sa.Column("match_id", sa.BigInteger(), nullable=False),
        sa.Column("account_id", sa.BigInteger(), nullable=True),
        sa.Column("player_slot", sa.Integer(), nullable=False),
        sa.Column("hero_id", sa.Integer(), nullable=True),
        sa.Column("is_tracked", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("win", sa.Boolean(), nullable=True),
        sa.Column("kills", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("deaths", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("assists", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("gold_per_min", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("xp_per_min", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("hero_damage", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tower_damage", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("hero_healing", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_hits", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("lane_role", sa.Integer(), nullable=True),
        sa.Column("team_kills", sa.Integer(), nullable=True),
        sa.Column("raw_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.ForeignKeyConstraint(["match_id"], ["matches.match_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("match_id", "player_slot"),
    )
    op.create_index("ix_match_players_account", "match_players", ["account_id"])

    op.create_table(
        "player_match_index",
        sa.Column("account_id", sa.BigInteger(), nullable=False),
        sa.Column("match_id", sa.BigInteger(), nullable=False),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("hero_id", sa.Integer(), nullable=True),
        sa.Column("player_slot", sa.Integer(), nullable=True),
        sa.Column("radiant_win", sa.Boolean(), nullable=True),
        sa.Column("game_mode", sa.Integer(), nullable=True),
        sa.Column("lobby_type", sa.Integer(), nullable=True),
        sa.Column("kills", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("deaths", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("assists", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("raw_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.ForeignKeyConstraint(["account_id"], ["players.account_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["match_id"], ["matches.match_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("account_id", "match_id"),
    )
    op.create_index("ix_player_match_index_start", "player_match_index", ["account_id", "start_time"])

    op.create_table(
        "achievement_definitions",
        sa.Column("id", sa.String(length=80), primary_key=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("category", sa.String(length=80), nullable=False),
        sa.Column("tier", sa.String(length=40), nullable=False),
        sa.Column("target", sa.Float(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
    )

    op.create_table(
        "player_achievements",
        sa.Column("account_id", sa.BigInteger(), nullable=False),
        sa.Column("achievement_id", sa.String(length=80), nullable=False),
        sa.Column("progress", sa.Float(), nullable=False, server_default="0"),
        sa.Column("target", sa.Float(), nullable=False, server_default="1"),
        sa.Column("unlocked", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("unavailable", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("unlocked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("evidence", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["players.account_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["achievement_id"], ["achievement_definitions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("account_id", "achievement_id"),
    )

    op.create_table(
        "rating_snapshots",
        sa.Column("id", sqlite_big_integer_pk, primary_key=True, autoincrement=True),
        sa.Column("account_id", sa.BigInteger(), nullable=False),
        sa.Column("overall", sa.Integer(), nullable=False),
        sa.Column("position", sa.String(length=20), nullable=False),
        sa.Column("breakdown", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("source", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["players.account_id"], ondelete="CASCADE"),
    )
    op.create_index("ix_rating_snapshots_account_created", "rating_snapshots", ["account_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_rating_snapshots_account_created", table_name="rating_snapshots")
    op.drop_table("rating_snapshots")
    op.drop_table("player_achievements")
    op.drop_table("achievement_definitions")
    op.drop_index("ix_player_match_index_start", table_name="player_match_index")
    op.drop_table("player_match_index")
    op.drop_index("ix_match_players_account", table_name="match_players")
    op.drop_table("match_players")
    op.drop_index("ix_refresh_jobs_account_created", table_name="refresh_jobs")
    op.drop_table("refresh_jobs")
    op.drop_index("ix_source_payloads_match_operation", table_name="source_payloads")
    op.drop_index("ix_source_payloads_account_operation", table_name="source_payloads")
    op.drop_table("source_payloads")
    op.drop_table("matches")
    op.drop_table("heroes")
    op.drop_table("players")
