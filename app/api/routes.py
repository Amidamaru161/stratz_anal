from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analytics.match_breakdowns import game_mode_name, ranked_bucket, ranked_label
from app.analytics.scoring import is_win
from app.api.schemas import (
    AchievementResponse,
    HeroBuildAbilityResponse,
    HeroBuildGuideResponse,
    HeroBuildItemResponse,
    HeroBuildResponse,
    HeroGlobalWinrateResponse,
    HeroStatsResponse,
    JobResponse,
    LeaderboardRow,
    MatchResponse,
    PlayerBreakdowns,
    PlayerSummary,
    RatingResponse,
    StyleScoreResponse,
)
from app.config import Settings, get_settings
from app.database import SessionLocal, get_session
from app.services.analytics import (
    DEFAULT_ANALYTICS_LIMIT,
    build_achievement_payloads,
    build_breakdown_payload,
    build_hero_payload,
    build_rating_payload,
    build_summary_payload,
    seed_achievement_definitions,
)
from app.services.hero_meta import build_global_hero_winrates, build_hero_builds
from app.services.refresh import (
    RefreshCooldownError,
    assert_refresh_allowed,
    create_refresh_job,
    run_refresh_job,
)
from app.services.storage import leaderboard_rows, load_player_matches
from app.services.style import build_player_style_payload
from app.storage.models import AchievementDefinition, RefreshJob
from app.stratz.client import StratzClient, StratzError

router = APIRouter()


def _job_response(job: RefreshJob) -> JobResponse:
    return JobResponse(
        id=job.id,
        accountId=job.account_id,
        status=job.status,
        message=job.message,
        createdAt=job.created_at,
        startedAt=job.started_at,
        finishedAt=job.finished_at,
    )


async def _background_refresh(job_id: str, settings: Settings) -> None:
    session = SessionLocal()
    try:
        await run_refresh_job(session, job_id=job_id, settings=settings)
    finally:
        session.close()


@router.post("/v1/players/{account_id}/refresh", response_model=JobResponse, status_code=status.HTTP_202_ACCEPTED)
async def refresh_player_endpoint(
    account_id: int,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> JobResponse:
    try:
        assert_refresh_allowed(session, account_id, settings)
    except RefreshCooldownError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc

    job = create_refresh_job(session, account_id)
    background_tasks.add_task(_background_refresh, job.id, settings)
    return _job_response(job)


@router.get("/v1/jobs/{job_id}", response_model=JobResponse)
def get_job(job_id: str, session: Session = Depends(get_session)) -> JobResponse:
    job = session.get(RefreshJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return _job_response(job)


@router.get("/v1/players/{account_id}/summary", response_model=PlayerSummary)
def player_summary(
    account_id: int,
    limit: int = Query(default=DEFAULT_ANALYTICS_LIMIT, ge=1, le=500),
    session: Session = Depends(get_session),
) -> dict:
    try:
        return build_summary_payload(session, account_id, limit)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Player not found; refresh first") from exc


@router.get("/v1/players/{account_id}/breakdowns", response_model=PlayerBreakdowns)
def player_breakdowns(
    account_id: int,
    limit: int = Query(default=DEFAULT_ANALYTICS_LIMIT, ge=1, le=500),
    session: Session = Depends(get_session),
) -> dict:
    try:
        return build_breakdown_payload(session, account_id, limit)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="No breakdown data found; refresh first") from exc


@router.get("/v1/players/{account_id}/matches", response_model=list[MatchResponse])
def player_matches(
    account_id: int,
    limit: int = Query(default=20, ge=1, le=500),
    session: Session = Depends(get_session),
) -> list[MatchResponse]:
    rows = load_player_matches(session, account_id, limit)
    if not rows:
        raise HTTPException(status_code=404, detail="No matches found; refresh first")
    return [
        MatchResponse(
            matchId=row.match_id,
            startedAt=row.start_time,
            durationSeconds=row.duration_seconds,
            heroId=row.hero_id,
            gameMode=row.game_mode,
            gameModeName=game_mode_name(row.game_mode),
            lobbyType=row.lobby_type,
            rankedBucket=ranked_bucket(row),
            rankedLabel=ranked_label(ranked_bucket(row)),
            won=is_win(row),
            kills=row.kills,
            deaths=row.deaths,
            assists=row.assists,
            gpm=row.gold_per_min,
            xpm=row.xp_per_min,
            heroDamage=row.hero_damage,
            towerDamage=row.tower_damage,
            heroHealing=row.hero_healing,
            lastHits=row.last_hits,
            laneRole=row.lane_role,
        )
        for row in rows
    ]


@router.get("/v1/players/{account_id}/heroes", response_model=list[HeroStatsResponse])
def player_heroes(
    account_id: int,
    limit: int = Query(default=DEFAULT_ANALYTICS_LIMIT, ge=1, le=500),
    session: Session = Depends(get_session),
) -> list[dict]:
    rows = build_hero_payload(session, account_id, limit)
    if not rows:
        raise HTTPException(status_code=404, detail="No hero stats found; refresh first")
    return rows


def _hero_build_item_response(row: dict) -> HeroBuildItemResponse:
    return HeroBuildItemResponse(
        itemId=row["item_id"],
        itemName=row["item_name"],
        shortName=row.get("short_name"),
        matchCount=row["match_count"],
        winCount=row["win_count"],
        winRate=row["win_rate"],
        metaScore=row["meta_score"],
        averageTimeMinute=row.get("average_time_minute"),
        averageTimeSeconds=row.get("average_time_seconds"),
        wasGiven=row.get("was_given"),
        equippedMatchCount=row.get("equipped_match_count"),
        equippedWinCount=row.get("equipped_win_count"),
    )


def _hero_build_ability_response(row: dict) -> HeroBuildAbilityResponse:
    return HeroBuildAbilityResponse(
        abilityId=row["ability_id"],
        abilityName=row["ability_name"],
        matchCount=row["match_count"],
        winCount=row["win_count"],
        winRate=row["win_rate"],
        metaScore=row["meta_score"],
        averageTimeMinute=row.get("average_time_minute"),
        averageTimeSeconds=row.get("average_time_seconds"),
    )


def _hero_skill_build_response(row: dict) -> dict:
    return {
        "level": row["level"],
        "abilityId": row["ability_id"],
        "abilityName": row["ability_name"],
        "matchCount": row["match_count"],
        "winCount": row["win_count"],
        "winRate": row["win_rate"],
        "metaScore": row["meta_score"],
    }


def _hero_build_guide_response(row: dict) -> HeroBuildGuideResponse:
    return HeroBuildGuideResponse(
        matchId=row.get("match_id"),
        createdAt=row.get("created_at"),
        itemIds=row["item_ids"],
        itemNames=row["item_names"],
        neutralItemIds=row["neutral_item_ids"],
        neutralItemNames=row["neutral_item_names"],
    )


@router.get("/v1/heroes/winrates", response_model=list[HeroGlobalWinrateResponse])
async def hero_global_winrates(
    limit: int = Query(default=140, ge=1, le=150),
    min_matches: int = Query(default=0, ge=0),
    order_by: str = Query(default="winRate", pattern="^(winRate|matches|heroId)$"),
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> list[HeroGlobalWinrateResponse]:
    try:
        rows = await build_global_hero_winrates(
            session,
            settings,
            min_matches=min_matches,
            limit=limit,
            order_by=order_by,  # type: ignore[arg-type]
        )
    except StratzError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return [
        HeroGlobalWinrateResponse(
            heroId=row["hero_id"],
            name=row["name"],
            displayName=row["display_name"],
            shortName=row["short_name"],
            imageUrl=row["image_url"],
            roles=row["roles"],
            matchCount=row["match_count"],
            winCount=row["win_count"],
            lossCount=row["loss_count"],
            winRate=row["win_rate"],
        )
        for row in rows
    ]


@router.get("/v1/heroes/{hero_id}/builds", response_model=HeroBuildResponse)
async def hero_builds(
    hero_id: int,
    min_matches: int = Query(default=1000, ge=0),
    limit: int = Query(default=10, ge=1, le=30),
    match_limit: int = Query(default=10000, ge=100, le=100000),
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> HeroBuildResponse:
    try:
        payload = await build_hero_builds(
            session,
            settings,
            hero_id=hero_id,
            min_matches=min_matches,
            limit=limit,
            match_limit=match_limit,
        )
    except StratzError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return HeroBuildResponse(
        heroId=payload["hero_id"],
        heroName=payload["hero_name"],
        shortName=payload["short_name"],
        source=payload["source"],
        coreItems=[_hero_build_item_response(row) for row in payload["core_items"]],
        startingItems=[_hero_build_item_response(row) for row in payload["starting_items"]],
        boots=[_hero_build_item_response(row) for row in payload["boots"]],
        neutralItems=[_hero_build_item_response(row) for row in payload["neutral_items"]],
        talents=[_hero_build_ability_response(row) for row in payload["talents"]],
        skillBuild=[_hero_skill_build_response(row) for row in payload["skill_build"]],
        guides=[_hero_build_guide_response(row) for row in payload["guides"]],
    )


@router.get("/v1/players/{account_id}/achievements", response_model=list[AchievementResponse])
def player_achievements(
    account_id: int,
    category: str | None = None,
    unlocked: bool | None = None,
    limit: int = Query(default=DEFAULT_ANALYTICS_LIMIT, ge=1, le=500),
    session: Session = Depends(get_session),
) -> list[dict]:
    try:
        rows = build_achievement_payloads(
            session,
            account_id,
            limit=limit,
            category=category,
            unlocked=unlocked,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="No achievements found; refresh first") from exc
    if not rows:
        raise HTTPException(status_code=404, detail="No achievements found; refresh first")
    return rows


@router.get("/v1/players/{account_id}/rating", response_model=RatingResponse)
def player_rating(
    account_id: int,
    limit: int = Query(default=DEFAULT_ANALYTICS_LIMIT, ge=1, le=500),
    session: Session = Depends(get_session),
) -> dict:
    try:
        return build_rating_payload(session, account_id, limit)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="No rating found; refresh first") from exc


@router.get("/v1/players/{account_id}/style", response_model=StyleScoreResponse)
async def player_style_score(
    account_id: int,
    limit: int = Query(default=20, ge=1, le=500),
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> dict:
    try:
        return await build_player_style_payload(session, settings, account_id, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="No matches found; refresh first") from exc
    except StratzError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/v1/leaderboard", response_model=list[LeaderboardRow])
def leaderboard(
    metric: str = Query(default="overall", pattern="^overall$"),
    limit: int = Query(default=50, ge=1, le=100),
    session: Session = Depends(get_session),
) -> list[LeaderboardRow]:
    result = []
    for rank, (player, rating) in enumerate(leaderboard_rows(session, limit), 1):
        result.append(
            LeaderboardRow(
                rank=rank,
                accountId=player.account_id,
                name=player.name,
                avatar=player.avatar,
                overall=rating.overall,
                position=rating.position,
                winRate=rating.source.get("winrate"),
                matches=None,
                createdAt=rating.created_at,
            )
        )
    return result


@router.get("/v1/achievements", response_model=list[AchievementResponse])
def achievement_catalog(session: Session = Depends(get_session)) -> list[AchievementResponse]:
    seed_achievement_definitions(session)
    session.commit()
    definitions = session.scalars(select(AchievementDefinition).order_by(AchievementDefinition.category, AchievementDefinition.id)).all()
    return [
        AchievementResponse(
            id=item.id,
            title=item.title,
            description=item.description,
            category=item.category,
            tier=item.tier,
            progress=0,
            target=item.target,
            progressPercent=0,
            unlocked=False,
            unavailable=False,
            evidence={},
        )
        for item in definitions
    ]


@router.get("/health")
async def health(
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    db_ok = bool(session.execute(select(1)).scalar_one())
    return {
        "status": "ok" if db_ok else "degraded",
        "database": "ok" if db_ok else "failed",
        "stratzConfigured": StratzClient(settings).configured,
        "environment": settings.environment,
    }
