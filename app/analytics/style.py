from __future__ import annotations

from collections import defaultdict
from typing import Any

from app.analytics.dto import PlayerMatch

ITEM_SLOT_FIELDS = (
    "item0Id",
    "item1Id",
    "item2Id",
    "item3Id",
    "item4Id",
    "item5Id",
    "backpack0Id",
    "backpack1Id",
    "backpack2Id",
)


def _as_int(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _player_raw(match: PlayerMatch) -> dict[str, Any]:
    player = match.raw.get("player") if isinstance(match.raw, dict) else None
    return player if isinstance(player, dict) else {}


def _actual_items(match: PlayerMatch) -> tuple[list[int], bool]:
    player = _player_raw(match)
    final_items = [
        item_id
        for field in ITEM_SLOT_FIELDS
        if (item_id := _as_int(player.get(field))) not in (None, 0)
    ]
    return list(dict.fromkeys(final_items)), False


def _actual_skills(match: PlayerMatch) -> list[tuple[int, int]]:
    player = _player_raw(match)
    events = player.get("abilities") or []

    result: list[tuple[int, int, int]] = []
    for event in events:
        if not isinstance(event, dict) or event.get("isTalent"):
            continue
        ability_id = _as_int(event.get("abilityId"))
        level = _as_int(event.get("level"))
        if ability_id and level and level <= 25:
            result.append((level, _as_int(event.get("time")) or 0, ability_id))
    result.sort()
    return [(level, ability_id) for level, _, ability_id in result]


def _meta_item_order(meta: dict[str, Any]) -> list[int]:
    items = meta.get("core_items") or []
    ordered = sorted(
        items,
        key=lambda item: (
            item.get("average_time_minute") is None,
            item.get("average_time_minute") or 10_000,
            -(item.get("meta_score") or 0),
        ),
    )
    return [item_id for item in ordered if (item_id := _as_int(item.get("item_id"))) is not None]


def _meta_skills(meta: dict[str, Any]) -> dict[int, int]:
    by_level: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in meta.get("skill_build") or []:
        level = _as_int(row.get("level"))
        ability_id = _as_int(row.get("ability_id"))
        if level and ability_id:
            by_level[level].append(row)
    expected = {}
    for level, rows in by_level.items():
        best = max(rows, key=lambda row: (row.get("match_count") or 0, row.get("meta_score") or 0))
        ability_id = _as_int(best.get("ability_id"))
        if ability_id:
            expected[level] = ability_id
    return expected


def _item_deviation(actual: list[int], expected: list[int]) -> float | None:
    if not actual or not expected:
        return None
    meta_window = set(expected[: max(1, len(actual))])
    actual_set = set(actual)
    novelty = sum(item_id not in meta_window for item_id in actual_set) / len(actual_set)
    omissions = sum(item_id not in actual_set for item_id in meta_window) / len(meta_window)
    return round((0.75 * novelty + 0.25 * omissions) * 100, 1)


def _skill_deviation(actual: list[tuple[int, int]], expected: dict[int, int]) -> float | None:
    comparable = [(level, ability_id) for level, ability_id in actual if level in expected]
    if not comparable:
        return None
    mismatches = sum(ability_id != expected[level] for level, ability_id in comparable)
    return round(mismatches / len(comparable) * 100, 1)


def style_label(score: float | None) -> str:
    if score is None:
        return "Недостаточно данных"
    if score < 20:
        return "Мета-адепт"
    if score < 40:
        return "Небольшой твист"
    if score < 60:
        return "Дота-дизайнер"
    if score < 80:
        return "Архитектор хаоса"
    return "Вне патча"


def build_style_score(matches: list[PlayerMatch], meta_by_hero: dict[int, dict[str, Any]]) -> dict[str, Any]:
    rows = []
    item_scores: list[float] = []
    skill_scores: list[float] = []
    total_scores: list[float] = []

    for match in matches:
        if match.hero_id is None or match.hero_id not in meta_by_hero:
            rows.append(
                {
                    "match_id": match.match_id,
                    "hero_id": match.hero_id,
                    "score": None,
                    "item_score": None,
                    "skill_score": None,
                    "item_order_available": False,
                    "reason": "meta_unavailable",
                    "actual_items": [],
                    "meta_items": [],
                    "actual_skills": [],
                    "meta_skills": {},
                }
            )
            continue

        meta = meta_by_hero[match.hero_id]
        actual_items, item_order_available = _actual_items(match)
        expected_items = _meta_item_order(meta)
        actual_skills = _actual_skills(match)
        expected_skills = _meta_skills(meta)
        item_score = _item_deviation(actual_items, expected_items)
        skill_score = _skill_deviation(actual_skills, expected_skills)
        available = [(0.65, item_score), (0.35, skill_score)]
        available = [(weight, score) for weight, score in available if score is not None]
        score = None
        if available:
            weight_total = sum(weight for weight, _ in available)
            score = round(sum(weight * value for weight, value in available) / weight_total, 1)
            total_scores.append(score)
        if item_score is not None:
            item_scores.append(item_score)
        if skill_score is not None:
            skill_scores.append(skill_score)
        rows.append(
            {
                "match_id": match.match_id,
                "hero_id": match.hero_id,
                "score": score,
                "item_score": item_score,
                "skill_score": skill_score,
                "item_order_available": item_order_available,
                "reason": None if score is not None else "match_build_unavailable",
                "actual_items": actual_items,
                "meta_items": expected_items[:10],
                "actual_skills": [{"level": level, "abilityId": ability_id} for level, ability_id in actual_skills],
                "meta_skills": expected_skills,
            }
        )

    score = round(sum(total_scores) / len(total_scores), 1) if total_scores else None
    return {
        "style_score": score,
        "label": style_label(score),
        "rated_matches": len(total_scores),
        "item_score": round(sum(item_scores) / len(item_scores), 1) if item_scores else None,
        "skill_score": round(sum(skill_scores) / len(skill_scores), 1) if skill_scores else None,
        "matches": rows,
    }
