# Achievement Rules

This folder keeps achievements data-driven.

## Add a hero-flavor achievement

Edit `hero_rules.py` and add one `HeroAchievementRule` to `HERO_RULES`.

```python
HeroAchievementRule(
    id="techies_son_of_shahed",
    hero_id=105,
    hero_name="Techies",
    title="Сын шахеда",
    description="Выиграй 10 игр подряд на Techies. Минное поле одобряет.",
    tier="legendary",
    target=10,
)
```

Supported `kind` values:

- `win_streak`: max consecutive wins on this hero.
- `wins`: total wins on this hero.
- `stat_threshold`: best hero stat, such as `hero_damage` or `tower_damage`.
- `clean_wins`: wins on this hero with deaths at or below `max_deaths`.

Keep titles spicy, but avoid slurs and protected-class insults. The API may display these strings publicly.

