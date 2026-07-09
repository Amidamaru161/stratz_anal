from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.config import Settings
from app.services.analytics import sync_player_achievements, sync_rating
from app.services.storage import (
    load_player_matches,
    save_source_payload,
    upsert_heroes,
    upsert_match_bundle,
    upsert_player,
)
from app.storage.models import Player, RefreshJob
from app.stratz.client import StratzClient
from app.stratz.normalizer import extract_matches, normalize_hero_constants, normalize_player


class RefreshCooldownError(RuntimeError):
    pass


def _as_aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def create_refresh_job(session: Session, account_id: int) -> RefreshJob:
    job = RefreshJob(id=str(uuid.uuid4()), account_id=account_id, status="queued")
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


def assert_refresh_allowed(session: Session, account_id: int, settings: Settings) -> None:
    player = session.get(Player, account_id)
    if not player or not player.last_refreshed_at:
        return
    last_refreshed_at = _as_aware_utc(player.last_refreshed_at)
    cooldown_until = last_refreshed_at + timedelta(seconds=settings.refresh_cooldown_seconds)
    if datetime.now(UTC) < cooldown_until:
        raise RefreshCooldownError(f"Refresh cooldown active until {cooldown_until.isoformat()}")


async def run_refresh_job(
    session: Session,
    *,
    job_id: str,
    settings: Settings,
    client: StratzClient | None = None,
) -> None:
    job = session.get(RefreshJob, job_id)
    if job is None:
        raise ValueError(f"Unknown refresh job: {job_id}")

    client = client or StratzClient(settings)
    job.status = "running"
    job.started_at = datetime.now(UTC)
    session.commit()

    try:
        await refresh_player(session, job.account_id, settings=settings, client=client)
    except Exception as exc:
        job.status = "failed"
        job.message = str(exc)
        job.finished_at = datetime.now(UTC)
        session.commit()
        raise
    else:
        job.status = "done"
        job.message = None
        job.finished_at = datetime.now(UTC)
        session.commit()


async def refresh_player(
    session: Session,
    account_id: int,
    *,
    settings: Settings,
    client: StratzClient,
) -> dict[str, Any]:
    player_bundle = await client.fetch_player_bundle(account_id, settings.match_history_limit)
    save_source_payload(
        session,
        operation="player_bundle",
        account_id=account_id,
        request_json={"accountId": account_id, "take": settings.match_history_limit},
        response_json=player_bundle,
    )

    player_payload = normalize_player(player_bundle, account_id)
    upsert_player(session, player_payload)

    try:
        heroes_payload = await client.fetch_hero_constants()
    except Exception:
        heroes_payload = {}
    else:
        save_source_payload(
            session,
            operation="hero_constants",
            request_json={},
            response_json=heroes_payload,
        )
        upsert_heroes(session, normalize_hero_constants(heroes_payload))

    matches = extract_matches(player_bundle)
    for match_payload in matches:
        upsert_match_bundle(session, account_id, match_payload)

    session.flush()
    normalized_matches = load_player_matches(session, account_id, settings.match_history_limit)
    card = sync_rating(session, account_id, normalized_matches)
    achievements = sync_player_achievements(session, account_id, normalized_matches)
    session.commit()
    return {
        "accountId": account_id,
        "matches": len(normalized_matches),
        "overall": card["overall"],
        "achievements": sum(1 for item in achievements if item.unlocked),
    }
