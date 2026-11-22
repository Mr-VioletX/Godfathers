# -*- coding: utf-8 -*-
"""v1.7.9.4 — فوتبال منیجر F2: ثابت‌ها و فرمول‌های خالصِ سرمربی/استادیوم/سوشال/تمرین.

همه‌ی اعداد از سند A12 (v2) — بدون وابستگی به دیتابیس تا مستقل تست شود.
"""
from __future__ import annotations

import random

# --------------------------- سرمربی ---------------------------
COACH_STYLES: dict[str, dict] = {
    "full_attack":  {"name": "فول‌اتک",     "effect": "+گل‌زنی، −دفاع، خستگی بیشتر"},
    "full_defense": {"name": "فول‌دیفنس",    "effect": "+دفاع، −خلق موقعیت، مصدومیت کمی کمتر"},
    "possession":   {"name": "بازی مالکانه", "effect": "پایداری فرم، کمتر کارت، تمپو یکنواخت"},
    "counter":      {"name": "ضدحمله",      "effect": "بونوس وقتی ضعیف‌تری؛ در برتری کمتر از اتک"},
}
STYLE_ORDER = ["full_attack", "full_defense", "possession", "counter"]

STYLE_CHANGE_COST = 200_000          # دلار بازی — بیش از ۱ تعویض رایگان در هفته
STYLE_FREE_PER_WEEK = 1
COACH_LEVEL_MAX = 100

# XP هر برد رسمی (لیگ/UCL/دوستانه رتبه‌دار) — سیم‌کشی در F4 فعال می‌شود
COACH_XP_LEAGUE = 2
COACH_XP_STRONGER = 3
COACH_XP_UCL = 4
COACH_XP_TITLE = 10


def coach_xp_needed(level: int) -> int:
    """XP لازم برای سطح n ← n+1: 3 + floor(n/5)."""
    return 3 + max(0, int(level)) // 5


def coach_star_mult(stars: int) -> float:
    """هر ستاره +۵٪ قدرت بازیکنانِ داخل زمین (تا ۵⭐ = +۲۵٪)."""
    return 1.0 + 0.05 * max(1, min(5, int(stars)))


# ساخت ستاره (تا ۴⭐) — ۵⭐ فقط فروش واقعی
STAR_BUILD: dict[int, tuple[int, int]] = {   # ستاره‌ی هدف: (هزینه دلار بازی، حداقل سطح سرمربی)
    2: (5_000_000, 20),
    3: (15_000_000, 40),
    4: (40_000_000, 65),
}
STAR_MAX_BUILD = 4


# --------------------------- استادیوم ---------------------------
# (ظرفیت, هزینه‌ی ارتقا به آن سطح) — ۱۰ سطح
STADIUM_LEVELS: list[tuple[int, int]] = [
    # Internal index 0 is displayed as level 1.  The level-10 upgrade is capped
    # exactly at 100 billion game dollars; intermediate levels climb smoothly.
    (12_500, 0),
    (20_000, 100_000_000),
    (30_000, 350_000_000),
    (40_000, 900_000_000),
    (55_000, 2_500_000_000),
    (70_000, 6_000_000_000),
    (85_000, 15_000_000_000),
    (100_000, 35_000_000_000),
    (112_000, 65_000_000_000),
    (125_000, 100_000_000_000),
]
STADIUM_MAX_LEVEL = len(STADIUM_LEVELS) - 1
STADIUM_LEVEL_COUNT = len(STADIUM_LEVELS)


def stadium_display_level(level: int) -> int:
    return max(0, min(STADIUM_MAX_LEVEL, int(level))) + 1
TICKET_PRICE_BY_LEVEL = [20, 26, 32, 38, 44, 52, 60, 66, 73, 80]   # دلار بازی


def stadium_capacity(level: int) -> int:
    return STADIUM_LEVELS[max(0, min(STADIUM_MAX_LEVEL, int(level)))][0]


def stadium_upgrade_cost(level: int) -> int:
    """هزینه‌ی ارتقا از سطحِ فعلی به بعدی."""
    nxt = int(level) + 1
    if nxt > STADIUM_MAX_LEVEL:
        return 0
    return STADIUM_LEVELS[nxt][1]


def home_comeback_bonus(capacity: int, attendance: int, self_power: float, opp_power: float) -> float:
    """بونوس کامبک خانگی (سند ۴.۳) — سقف +۷٪."""
    capacity = max(1, int(capacity))
    ratio = max(1.0, min(1.5, (opp_power / max(1.0, self_power)) if self_power < opp_power else 1.0))
    bonus = 0.02 * (capacity / 125_000) + 0.03 * (max(0, attendance) / capacity) + 0.02 * ratio
    return min(0.07, bonus)


# --------------------------- سوشال‌مدیا ---------------------------
SOCIAL_POSTS_PER_DAY = 2
FANS_MIN, FANS_MAX = 250, 2_000
FOLLOWERS_PER_FAN = 8
SOCIAL_POWER_CAP_PCT = 25
SOCIAL_POWER_PER_FOLLOWERS = 20_000_000

# مایلستون‌ها: فالوور ← (پاداش دلار بازی، یادداشت)
SOCIAL_MILESTONES: list[tuple[int, int, str]] = [
    (100_000, 500_000, "🎁 ۱۰۰هزار فالوور"),
    (1_000_000, 2_000_000, "🎁 ۱ میلیون فالوور"),
    (5_000_000, 5_000_000, "🎁 ۵ میلیون فالوور"),
    (20_000_000, 20_000_000, "🎁 ۲۰ میلیون فالوور (+۱٪ پاور تیم فعال شد)"),
]


def roll_fans_gain(rng: random.Random | None = None) -> int:
    """جذب طرفدار هر پست: ۵۰٪ → ۲۵۰–۶۰۰ | ۳۵٪ → ۶۰۱–۱۲۰۰ | ۱۵٪ → ۱۲۰۱–۲۰۰۰."""
    r = rng or random
    roll = r.random()
    if roll < 0.50:
        return r.randint(250, 600)
    if roll < 0.85:
        return r.randint(601, 1_200)
    return r.randint(1_201, 2_000)


def social_power_pct(social_followers: int) -> int:
    """هر ۲۰M فالوور = +۱٪ پاور تیم (سقف ۲۵٪)."""
    return min(SOCIAL_POWER_CAP_PCT, max(0, int(social_followers)) // SOCIAL_POWER_PER_FOLLOWERS)


# --------------------------- کمپ و تمرین ---------------------------
CAMP_COSTS = [4_000_000, 12_000_000, 30_000_000]   # کمپ ۱/۲/۳
CAMP_MAX = 3
CAMP_POWER_PER_SESSION = [1, 2, 3]                  # کمپ۱ ← +۱، کمپ۲ ← +۲، کمپ۳ ← +۳ (جمع‌شونده)
TRAIN_SESSIONS_PER_DAY = 3

# بازده نزولی (v2): تا +۶۰ روی پایه اثر کامل، تا +۱۲۰ نصف، بالاتر ربع
DR_FULL_TO = 60
DR_HALF_TO = 120

# Injury is rolled ONCE for the whole squad, never independently per player.
# At the 4% baseline a 20-player squad therefore has a 0.20% equivalent risk
# per player (4 / 20), instead of twenty separate 4% rolls.
INJURY_TEAM_BASE_PCT = 4.0
INJURY_TEAM_MIN_PCT = 0.5
INJURY_TEAM_MAX_PCT = 10.0
INJURY_HEALTHY_FLOOR = 11
INJURY_STYLE_MODIFIER = {
    "full_attack": 1.00,
    "full_defense": -0.75,
    "possession": -0.25,
    "counter": 0.00,
}
# Backward-compatible names now refer to the team-level range.
INJURY_BASE_PCT = INJURY_TEAM_BASE_PCT
INJURY_MIN_PCT = INJURY_TEAM_MIN_PCT
INJURY_MAX_PCT = INJURY_TEAM_MAX_PCT
FATIGUE_PER_SESSION = 15
FATIGUE_DECAY_PER_HOUR = 8
FATIGUE_TIRED_THRESHOLD = 80      # بالاتر از این فقط ۵۰٪ پاور تمرین


def camp_power_per_session(camps: int) -> int:
    """جمع اثر کمپ‌های ساخته‌شده در هر جلسه (۱/۲/۳ کمپ ← ۱/۳/۶)."""
    return sum(CAMP_POWER_PER_SESSION[:max(0, min(CAMP_MAX, int(camps)))])


def diminishing_gain(current_bonus: int, gain: int) -> int:
    """بازده نزولی روی training_bonus: تا ۶۰ کامل، تا ۱۲۰ نصف، بالاتر ربع."""
    current_bonus = max(0, int(current_bonus))
    gain = max(0, int(gain))
    out = 0.0
    remaining = float(gain)
    full_room = max(0.0, DR_FULL_TO - current_bonus)
    take = min(remaining, full_room)
    out += take
    remaining -= take
    current_bonus += take
    if remaining > 0:
        half_room = max(0.0, DR_HALF_TO - current_bonus)
        take = min(remaining, half_room)
        out += take / 2
        remaining -= take
        current_bonus += take
    if remaining > 0:
        out += remaining / 4
    return int(round(out))


def team_injury_chance(average_fatigue: float, session_index: int, coach_style: str = "") -> float:
    """Percentage chance of at most one injury across the entire squad.

    Baseline is 4% per training session.  Only average fatigue, repeated sessions
    and coach style modify the team event; roster size never multiplies risk.
    """
    fatigue = max(0.0, min(100.0, float(average_fatigue)))
    session_no = max(1, min(TRAIN_SESSIONS_PER_DAY, int(session_index)))
    chance = INJURY_TEAM_BASE_PCT
    chance += max(0.0, fatigue - 50.0) * 0.06       # +0..3 at fatigue 50..100
    chance += (session_no - 1) * 0.75               # session 2/3: +0.75/+1.50
    chance += INJURY_STYLE_MODIFIER.get(str(coach_style or ""), 0.0)
    return round(max(INJURY_TEAM_MIN_PCT, min(INJURY_TEAM_MAX_PCT, chance)), 3)


def player_equivalent_injury_chance(team_chance_pct: float, healthy_players: int) -> float:
    """Display-only equivalent share of the single team event per healthy card."""
    count = max(1, int(healthy_players))
    return round(max(0.0, float(team_chance_pct)) / count, 3)


def roll_team_injury_index(
    fatigues: list[int],
    team_chance_pct: float,
    rng: random.Random | None = None,
    healthy_roster_size: int | None = None,
) -> int | None:
    """Roll once, then select at most one fatigue-weighted player.

    No injury is allowed when only eleven selectable healthy players remain.
    """
    roster_size = len(fatigues) if healthy_roster_size is None else max(0, int(healthy_roster_size))
    if roster_size <= INJURY_HEALTHY_FLOOR or not fatigues:
        return None
    r = rng or random
    chance = max(0.0, min(100.0, float(team_chance_pct)))
    if r.random() * 100.0 >= chance:
        return None
    weights = [1.0 + max(0, min(100, int(fatigue))) / 25.0 for fatigue in fatigues]
    target = r.random() * sum(weights)
    cursor = 0.0
    for index, weight in enumerate(weights):
        cursor += weight
        if target <= cursor:
            return index
    return len(weights) - 1


def injury_chance(player_power: float, fatigue: int, session_index: int) -> float:
    """Compatibility wrapper; result is a TEAM chance and must be rolled once."""
    del player_power
    return team_injury_chance(fatigue, session_index)


def injury_days(rng: random.Random | None = None) -> int:
    """۱–۵ روز، وزن به سمت ۱–۲."""
    r = rng or random
    roll = r.random()
    if roll < 0.45:
        return 1
    if roll < 0.75:
        return 2
    if roll < 0.90:
        return 3
    return r.randint(4, 5)


def fatigue_after(current: int) -> int:
    return min(100, max(0, int(current)) + FATIGUE_PER_SESSION)


def fatigue_decayed(stored: int, hours_passed: float) -> int:
    """خستگی با گذر زمان کم می‌شود (تنبل — هنگام خواندن)."""
    return max(0, int(stored) - int(hours_passed * FATIGUE_DECAY_PER_HOUR))
