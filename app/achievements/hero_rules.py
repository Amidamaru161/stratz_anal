from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from app.achievements.base_rules import max_streak
from app.achievements.models import AchievementDefinitionData, AchievementProgress, progress_result
from app.analytics.dto import PlayerMatch
from app.analytics.scoring import is_win

HeroRuleKind = Literal["win_streak", "wins", "stat_threshold", "clean_wins"]


@dataclass(frozen=True)
class HeroAchievementRule:
    id: str
    hero_id: int
    hero_name: str
    title: str
    description: str
    tier: str
    target: float
    kind: HeroRuleKind = "win_streak"
    stat: str | None = None
    max_deaths: int | None = None

    @property
    def definition(self) -> AchievementDefinitionData:
        return AchievementDefinitionData(
            id=self.id,
            title=self.title,
            description=self.description,
            category="hero_flavor",
            tier=self.tier,
            target=self.target,
        )


HERO_RULES: list[HeroAchievementRule] = [
    HeroAchievementRule(
        id="techies_son_of_shahed",
        hero_id=105,
        hero_name="Techies",
        title="Сын шахеда",
        description="Выиграй 10 игр подряд на Techies. Минное поле одобряет.",
        tier="legendary",
        target=10,
    ),
    HeroAchievementRule("pudge_hookaholic", 14, "Pudge", "Хукоголик", "Выиграй 10 игр подряд на Pudge.", "gold", 10),
    HeroAchievementRule("invoker_piano_without_notes", 74, "Invoker", "Пианист без нот", "Выиграй 10 игр подряд на Invoker.", "gold", 10),
    HeroAchievementRule("meepo_family_contract", 82, "Meepo", "Мобилизация чурок", "Выиграй 5 игр подряд на Meepo.", "gold", 5),
    HeroAchievementRule("tinker_button_maniac", 34, "Tinker", "Кнопочный душнила", "Выиграй 10 игр подряд на Tinker.", "gold", 10),
    HeroAchievementRule("sniper_balcony_grandpa", 35, "Sniper", "Дед с хуем на балконе", "Выиграй 10 игр подряд на Sniper.", "silver", 10),
    HeroAchievementRule("anti_mage_afk_forest", 1, "Anti-Mage", "АФК лес, потом GG проебали", "Выиграй 10 игр подряд на Anti-Mage.", "gold", 10),
    HeroAchievementRule("shadow_fiend_zxc_ministry", 11, "Shadow Fiend", "Неформал дед инсайд", "Выиграй 10 игр подряд на Shadow Fiend.", "gold", 10),
    HeroAchievementRule("phantom_assassin_crit_to_morale", 44, "Phantom Assassin", "Крит по морали", "Выиграй 10 игр подряд на Phantom Assassin.", "gold", 10),
    HeroAchievementRule("axe_spin_doctor", 2, "Axe", "Вертушка судьбы", "Выиграй 10 игр подряд на Axe.", "silver", 10),
    HeroAchievementRule("crystal_maiden_arcane_on_boots", 5, "Crystal Maiden", "Аркана на тапках", "Выиграй 10 игр подряд на Crystal Maiden.", "silver", 10),
    HeroAchievementRule("lion_finger_explained", 26, "Lion", "Палец объяснил", "Выиграй 10 игр подряд на Lion.", "silver", 10),
    HeroAchievementRule("witch_doctor_maledict_enjoyer", 30, "Witch Doctor", "Маледикт терапевт", "Выиграй 10 игр подряд на Witch Doctor.", "silver", 10),
    HeroAchievementRule("earthshaker_echo_couch", 7, "Earthshaker", "Эхо с дивана", "Выиграй 10 игр подряд на Earthshaker.", "silver", 10),
    HeroAchievementRule("juggernaut_spin_to_win", 8, "Juggernaut", "Крутилка без мыслей", "Выиграй 10 игр подряд на Juggernaut.", "silver", 10),
    HeroAchievementRule("riki_where_is_detection", 32, "Riki", "Где сентри?", "Выиграй 10 игр подряд на Riki.", "silver", 10),
    HeroAchievementRule("broodmother_real_estate", 61, "Broodmother", "Риэлтор паутины", "Выиграй 10 игр подряд на Broodmother.", "gold", 10),
    HeroAchievementRule("arc_warden_two_accounts", 113, "Arc Warden", "Два аккаунта в одной игре", "Выиграй 10 игр подряд на Arc Warden.", "gold", 10),
    HeroAchievementRule("faceless_void_chrono_lawyer", 41, "Faceless Void", "Хуйсос безглазый", "Выиграй 10 игр подряд на Faceless Void.", "silver", 10),
    HeroAchievementRule("chen_zoo_director", 66, "Chen", "Директор зоопарка", "Выиграй 5 игр подряд на Chen.", "gold", 5),
    HeroAchievementRule("io_ball_of_anxiety", 91, "Io", "Шар тревожности", "Выиграй 5 игр подряд на Io.", "gold", 5),
    HeroAchievementRule("huskar_low_hp_lifestyle", 59, "Huskar", "Жизнь на красном HP", "Выиграй 10 игр подряд на Huskar.", "silver", 10),
    HeroAchievementRule("ursa_roshan_landlord", 70, "Ursa", "Хозяин Рошпита", "Выиграй 10 игр подряд на Ursa.", "silver", 10),
    HeroAchievementRule("storm_spirit_mana_credit", 17, "Storm Spirit", "Мана в кредит", "Выиграй 10 игр подряд на Storm Spirit.", "gold", 10),
    HeroAchievementRule("alchemist_chemical_salary", 73, "Alchemist", "Забрал пенсию у бабки", "Выиграй 10 игр подряд на Alchemist.", "silver", 10),
    HeroAchievementRule(
        id="ogre_magi_ludik_ebanny",
        hero_id=84,
        hero_name="Ogre Magi",
        title="Лудик ебанный",
        description="Сделай 30k+ hero damage на Ogre Magi.",
        tier="gold",
        target=30000,
        kind="stat_threshold",
        stat="hero_damage",
    ),
    HeroAchievementRule(
        id="zeus_damage_cloud",
        hero_id=22,
        hero_name="Zeus",
        title="Облако с претензией",
        description="Сделай 45k+ hero damage на Zeus.",
        tier="gold",
        target=45000,
        kind="stat_threshold",
        stat="hero_damage",
    ),
    HeroAchievementRule(
        id="clinkz_tower_arson",
        hero_id=56,
        hero_name="Clinkz",
        title="Поджог недвижимости",
        description="Сделай 10k+ tower damage на Clinkz.",
        tier="gold",
        target=10000,
        kind="stat_threshold",
        stat="tower_damage",
    ),
    HeroAchievementRule(
        id="dazzle_no_one_dies",
        hero_id=50,
        hero_name="Dazzle",
        title="Никто не умер, я сказал",
        description="Выиграй 5 игр на Dazzle с 3 или меньше смертями.",
        tier="silver",
        target=5,
        kind="clean_wins",
        max_deaths=3,
    ),
]

HERO_CATALOG = [rule.definition for rule in HERO_RULES]


def calculate_hero_achievements(matches: list[PlayerMatch]) -> list[AchievementProgress]:
    matches = sorted(matches, key=lambda item: item.start_time or item.match_id, reverse=True)
    return [_calculate_rule(rule, matches) for rule in HERO_RULES]


def _calculate_rule(rule: HeroAchievementRule, matches: list[PlayerMatch]) -> AchievementProgress:
    hero_matches = [match for match in matches if match.hero_id == rule.hero_id]
    if rule.kind == "win_streak":
        return _hero_win_streak(rule, hero_matches)
    if rule.kind == "wins":
        wins = [match for match in hero_matches if is_win(match)]
        return progress_result(rule.id, len(wins), rule.target, _hero_evidence(rule, wins))
    if rule.kind == "stat_threshold":
        return _hero_stat_threshold(rule, hero_matches)
    if rule.kind == "clean_wins":
        clean_wins = [
            match
            for match in hero_matches
            if is_win(match) and rule.max_deaths is not None and match.deaths <= rule.max_deaths
        ]
        return progress_result(rule.id, len(clean_wins), rule.target, _hero_evidence(rule, clean_wins))
    raise ValueError(f"Unknown hero achievement rule kind: {rule.kind}")


def _hero_win_streak(rule: HeroAchievementRule, hero_matches: list[PlayerMatch]) -> AchievementProgress:
    chronological = sorted(hero_matches, key=lambda item: item.start_time or item.match_id)
    streak = max_streak([is_win(match) for match in chronological])
    streak_matches = _last_best_streak_matches(chronological, int(streak))
    return progress_result(rule.id, streak, rule.target, _hero_evidence(rule, streak_matches))


def _hero_stat_threshold(rule: HeroAchievementRule, hero_matches: list[PlayerMatch]) -> AchievementProgress:
    if not rule.stat:
        return AchievementProgress(rule.id, 0, rule.target, False, unavailable=True, evidence={"reason": "stat_not_configured"})
    best_value = 0.0
    best_match: PlayerMatch | None = None
    for match in hero_matches:
        value = float(getattr(match, rule.stat, 0))
        if value > best_value:
            best_value = value
            best_match = match
    evidence = _hero_evidence(rule, [best_match] if best_match else [])
    if best_match:
        evidence[rule.stat] = best_value
    return progress_result(rule.id, best_value, rule.target, evidence)


def _last_best_streak_matches(matches: list[PlayerMatch], streak: int) -> list[PlayerMatch]:
    if streak <= 0:
        return []
    current: list[PlayerMatch] = []
    best: list[PlayerMatch] = []
    for match in matches:
        if is_win(match):
            current.append(match)
            if len(current) >= len(best):
                best = list(current)
        else:
            current = []
    return best[-streak:]


def _hero_evidence(rule: HeroAchievementRule, matches: list[PlayerMatch]) -> dict[str, Any]:
    return {
        "heroId": rule.hero_id,
        "heroName": rule.hero_name,
        "matchIds": [match.match_id for match in matches],
    }
