# -*- coding: utf-8 -*-
"""🆕 مرحله ۴۶ (بچ ۳) — داده و فرمول‌های خالصِ رنکینگ: کاپ، لیگ، غنیمت و XP.

این ماژول کاملاً خالص است (بدونِ DB) تا مستقل تست شود.

قواعد:
  • شش لیگ بر اساسِ بازه‌ی کاپ.
  • بردِ مهاجمِ ضعیف‌تر (۳۰٪+ ضعیف‌تر) → ۴۲ کاپ؛ بازنده ۲۱ کاپ از دست می‌دهد.
  • بردِ مهاجمِ قوی‌تر (۳۰٪+ قوی‌تر) → ۱۴ کاپ؛ بازنده ۷ کاپ از دست می‌دهد.
  • بینِ این دو حالت، مقدار به‌صورتِ خطی محاسبه می‌شود.
  • کاپ هرگز منفی نمی‌شود.
  • غنیمت: ۱۴٪ (قوی→ضعیف) تا ۴۲٪ (ضعیف→قوی) از ثروتِ قابل‌غارت (نقد + ۳۰٪ سپرده − گاوصندوق).
  • حمله فقط به ۵۰ نفرِ بالا و ۵۰ نفرِ پایینِ خود در رتبه‌بندیِ کلی.
"""
from __future__ import annotations

# --------------------------- لیگ‌ها ---------------------------
# (کلید، نام، کمینه‌ی کاپ، بیشینه‌ی کاپ یا None برای بی‌نهایت)
LEAGUES: list[tuple[str, str, int, int | None]] = [
    ("bronze",  "🥉 لیگِ برنزی",    0,    499),
    ("silver",  "🥈 لیگِ نقره‌ای",   500,  999),
    ("gold",    "🥇 لیگِ طلایی",    1000, 1999),
    ("diamond", "💎 لیگِ الماسی",   2000, 3499),
    ("mythic",  "🔱 لیگِ اسطوره‌ای", 3500, 4999),
    ("legend",  "👑 لیگِ افسانه‌ای", 5000, None),
]
LEAGUE_COUNT = len(LEAGUES)
LEAGUE_KEYS = [x[0] for x in LEAGUES]
LEAGUE_NAMES = {x[0]: x[1] for x in LEAGUES}

# --------------------------- ثابت‌ها ---------------------------
CUP_WIN_MAX = 42          # بردِ مهاجمِ ۳۰٪+ ضعیف‌تر
CUP_WIN_MIN = 14          # بردِ مهاجمِ ۳۰٪+ قوی‌تر
CUP_LOSS_MAX = 21         # کسرِ متناظر با ۴۲
CUP_LOSS_MIN = 7          # کسرِ متناظر با ۱۴

LOOT_MAX_PCT = 42         # ٪ از داراییِ نقدیِ بازنده (سقف)
LOOT_MIN_PCT = 14         # ٪ از کلِ ثروتِ بازنده (کف)

WIN_XP = 42               # بیشترین XP یک پیروزی
XP_MIN = 14               # کمترین XP یک پیروزی (بردِ آسان)

ATTACK_WINDOW = 50        # ±۵۰ نفر در رتبه‌بندیِ کلی
RANKED_COOLDOWN_HOURS = 72        # هر ۳ روز یک بار به هر نفر
CLASSIC_COOLDOWN_HOURS = 24       # کلاسیک: روزی یک بار
NEW_LEAGUE_SHIELD_HOURS = 24      # سپرِ ۱ روزه هنگامِ ورود به لیگِ تازه

RATIO_STRONG = 0.7        # قدرتِ حریف ≤ ۷۰٪ قدرتِ مهاجم → مهاجم ۳۰٪+ قوی‌تر
RATIO_WEAK = 1.3          # قدرتِ حریف ≥ ۱۳۰٪ قدرتِ مهاجم → مهاجم ۳۰٪+ ضعیف‌تر


# --------------------------- لیگ ---------------------------
def league_index(cups: int) -> int:
    """شماره‌ی لیگ (۰..۵) بر اساسِ کاپ."""
    c = max(0, int(cups))
    for i, (_k, _n, lo, hi) in enumerate(LEAGUES):
        if c >= lo and (hi is None or c <= hi):
            return i
    return 0


def league_key(cups: int) -> str:
    return LEAGUES[league_index(cups)][0]


def league_name(cups: int) -> str:
    return LEAGUES[league_index(cups)][1]


def league_name_by_index(idx: int) -> str:
    idx = max(0, min(int(idx), LEAGUE_COUNT - 1))
    return LEAGUES[idx][1]


def league_range_text(idx: int) -> str:
    idx = max(0, min(int(idx), LEAGUE_COUNT - 1))
    _k, _n, lo, hi = LEAGUES[idx]
    return f"{lo:,}+" if hi is None else f"{lo:,}–{hi:,}"


def next_league_gap(cups: int) -> int:
    """چند کاپ تا لیگِ بعدی مانده (۰ = در بالاترین لیگ)."""
    idx = league_index(cups)
    if idx >= LEAGUE_COUNT - 1:
        return 0
    return max(0, LEAGUES[idx + 1][2] - max(0, int(cups)))


# --------------------------- ضریبِ برتری ---------------------------
def _edge(att_power: int, def_power: int) -> float:
    """۰ = مهاجم ۳۰٪+ ضعیف‌تر، ۱ = مهاجم ۳۰٪+ قوی‌تر (خطی در بین)."""
    a = max(1, int(att_power))
    d = max(1, int(def_power))
    ratio = d / a                      # >1 یعنی حریف قوی‌تر است
    if ratio >= RATIO_WEAK:
        return 0.0
    if ratio <= RATIO_STRONG:
        return 1.0
    return (RATIO_WEAK - ratio) / (RATIO_WEAK - RATIO_STRONG)


def cup_reward(att_power: int, def_power: int) -> int:
    """کاپِ برنده (۱۴..۴۲) — هرچه حریف قوی‌تر، کاپِ بیشتر."""
    e = _edge(att_power, def_power)
    val = CUP_WIN_MAX - (CUP_WIN_MAX - CUP_WIN_MIN) * e
    return int(round(max(CUP_WIN_MIN, min(CUP_WIN_MAX, val))))


def cup_penalty(att_power: int, def_power: int) -> int:
    """کاپی که بازنده از دست می‌دهد (۷..۲۱) — نیمی از پاداشِ برنده."""
    gain = cup_reward(att_power, def_power)
    return int(round(max(CUP_LOSS_MIN, min(CUP_LOSS_MAX, gain / 2))))


def apply_cups(current: int, delta: int) -> int:
    """کاپ هرگز منفی نمی‌شود."""
    return max(0, int(current) + int(delta))


# --------------------------- غنیمت ---------------------------
def loot_percent_by_power(att_power: int, def_power: int) -> int:
    """درصد غنیمت بر اساس نسبت قدرت مهاجم/مدافع.

    • مهاجم خیلی قوی‌تر (حریف ≤۷۰٪ قدرت) → ۱۴٪
    • مهاجم خیلی ضعیف‌تر (حریف ≥۱۳۰٪ قدرت) و برد → ۴۲٪
    • بین این دو: درون‌یابی خطی
    """
    e = _edge(att_power, def_power)  # 0=مهاجم ضعیف‌تر، 1=مهاجم قوی‌تر
    # e=1 (قوی) → MIN 14؛ e=0 (ضعیف) → MAX 42
    pct = LOOT_MAX_PCT - (LOOT_MAX_PCT - LOOT_MIN_PCT) * e
    return int(round(max(LOOT_MIN_PCT, min(LOOT_MAX_PCT, pct))))


def ranked_loot(defender_cash: int, defender_wealth: int, att_power: int, def_power: int) -> int:
    """غنیمت از ثروتِ قابل‌غارت (defender_wealth از قبل فیلتر شده).

    درصد ۱۴..۴۲ بر اساس قدرت؛ سقف = ثروت قابل‌غارت (و نقد+سپرده غارت‌پذیر).
    پارامتر defender_cash برای سازگاری نگه داشته شده (سقف نهایی در caller).
    """
    wealth = max(0, int(defender_wealth))
    if wealth <= 0:
        return 0
    pct = loot_percent_by_power(att_power, def_power)
    amount = wealth * pct // 100
    return max(0, min(wealth, amount))


def classic_loot(defender_wealth: int, defender_cash: int, pct: int | None = None,
                 att_power: int = 1, def_power: int = 1) -> int:
    """غنیمت کلاسیک: همان منطق ۱۴..۴۲٪ از ثروت قابل‌غارت (با درون‌یابی قدرت).

    اگر pct داده شود همان استفاده می‌شود؛ وگرنه از loot_percent_by_power.
    """
    wealth = max(0, int(defender_wealth))
    if wealth <= 0:
        return 0
    if pct is None:
        pct = loot_percent_by_power(att_power, def_power)
    gross = wealth * max(0, int(pct)) // 100
    return max(0, min(wealth, gross))


# --------------------------- تجربه ---------------------------
def win_xp(att_power: int, def_power: int) -> int:
    """۴۲ XP برای بردِ سخت، ۱۴ XP برای بردِ آسان. بازنده XP نمی‌گیرد."""
    e = _edge(att_power, def_power)
    val = WIN_XP - (WIN_XP - XP_MIN) * e
    return int(round(max(XP_MIN, min(WIN_XP, val))))


# --------------------------- پنجره‌ی حمله ---------------------------
def window_bounds(my_index: int, total: int, window: int = ATTACK_WINDOW) -> tuple[int, int]:
    """بازه‌ی ایندکسِ مجازِ حمله در رتبه‌بندیِ کلی (۰-پایه، هر دو سر شامل)."""
    lo = max(0, int(my_index) - int(window))
    hi = min(max(0, int(total) - 1), int(my_index) + int(window))
    return lo, hi


def in_window(my_index: int, target_index: int, total: int, window: int = ATTACK_WINDOW) -> bool:
    lo, hi = window_bounds(my_index, total, window)
    return lo <= int(target_index) <= hi


def preview_text(att_power: int, def_power: int) -> str:
    """خلاصه‌ی پاداش/جریمه‌ی رنکینگ برای نمایش پیش از حمله."""
    gain = cup_reward(att_power, def_power)
    pen = cup_penalty(att_power, def_power)
    return (
        f"🏅 بردی: <b>+{gain}</b> کاپ | باختی: <b>−{pen}</b> کاپ\n"
        f"⭐ تجربه‌ی برد: +{win_xp(att_power, def_power)} XP"
    )
