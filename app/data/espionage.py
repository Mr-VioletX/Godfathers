# app/data/espionage.py
"""ثابت‌ها و توابعِ خالصِ سیستمِ جاسوسی (مرحله ۱۳).

همه‌ی مقادیرِ عددی اینجا متمرکز شده‌اند تا بالانسِ بازی را
در یک جا تغییر دهی. توابع هیچ وابستگیای به دیتابیس ندارند.
"""
from __future__ import annotations

# ---------- ظرفیت و سطح ----------
MAX_SPIES = 5                 # حداکثر جاسوسِ هر کاربر
MAX_SPY_LEVEL = 10            # سقفِ ارتقای هر جاسوس

# هزینهٔ استخدامِ جاسوسِ n‌ام (هر کدام گران‌تر از قبلی)
HIRE_COSTS = [1_000_000, 3_000_000, 8_000_000, 20_000_000, 50_000_000]

# ---------- درآمد/غارت (درصدی از درآمدِ روزانهٔ هدف) ----------
BASE_INCOME_PCT = 1.0         # درصدِ پایه در سطح ۱
INCOME_PER_LEVEL = 0.5        # افزایش به‌ازای هر سطح
INCOME_CAP_PCT = 10.0         # سقفِ درصدِ غارت

# ---------- احتمالِ دستگیری ----------
BASE_CAPTURE_PCT = 30.0       # احتمالِ پایهٔ دستگیری در هر گزارش
CAPTURE_PER_LEVEL = 2.0       # کاهش به‌ازای هر سطح
CAPTURE_FLOOR_PCT = 5.0       # کفِ حداقلی (هیچ‌وقت زیرِ این نمی‌رود)

# ---------- زمانِ چرخهٔ گزارش ----------
BASE_MISSION_SECONDS = 24 * 3600      # ۲۴ ساعت
MISSION_REDUCE_PER_LEVEL = 30 * 60    # ۳۰ دقیقه کاهش به‌ازای هر سطح
MISSION_FLOOR_SECONDS = 6 * 3600      # کفِ ۶ ساعت

# ---------- غرامت و مرگِ جاسوس ----------
RANSOM_DEADLINE_HOURS = 48    # فرصتِ پرداختِ غرامت
RANSOM_BASE_FACTOR = 1.0      # غرامت = هزینهٔ استخدام × این ضریب
RANSOM_REDUCE_PER_LEVEL = 0.08
RANSOM_FLOOR_FACTOR = 0.30

DEATH_PENALTY_PCT = 10.0      # ۱۰٪ از درآمدِ روزانهٔ کاربر
DEATH_PENALTY_DAYS = 3        # تا ۳ روز به هدف منتقل می‌شود

# ---------- ارتقا ----------
UPGRADE_BASE_COST = 4_000_000

STATUS_LABELS = {
    "idle": "🟢 آماده (در پایگاه)",
    "active": "🕵️ در مأموریت",
    "captured": "🔒 دستگیر‌شده",
    "dead": "☠️ کشته‌شده",
}


def hire_cost(slot: int) -> int:
    """هزینهٔ استخدامِ جاسوسِ اسلاتِ slot (۱..۵)."""
    slot = max(1, min(MAX_SPIES, slot))
    return HIRE_COSTS[slot - 1]


def upgrade_cost(level: int) -> int:
    """هزینهٔ ارتقا از سطحِ فعلی به سطحِ بعدی."""
    return UPGRADE_BASE_COST * (2 ** (level - 1))


def income_pct(level: int) -> float:
    """درصدِ درآمدِ هدف که جاسوس به فرستنده می‌رساند."""
    return min(INCOME_CAP_PCT, BASE_INCOME_PCT + (level - 1) * INCOME_PER_LEVEL)


# غارت و درآمد یکی است
loot_pct = income_pct


def capture_pct(level: int, extra_reduction_pct: float = 0.0) -> float:
    """احتمالِ دستگیری (درصد).

    extra_reduction_pct: کاهشِ اضافی از عمارت‌های جاسوسی (Ombra/Senato)
    برحسبِ واحدِ درصد (مثلاً ۱۵.۰).
    """
    val = BASE_CAPTURE_PCT - (level - 1) * CAPTURE_PER_LEVEL - extra_reduction_pct
    return max(CAPTURE_FLOOR_PCT, val)


def mission_seconds(level: int) -> int:
    """طولِ چرخهٔ یک گزارش (ثانیه)."""
    return max(
        MISSION_FLOOR_SECONDS,
        BASE_MISSION_SECONDS - (level - 1) * MISSION_REDUCE_PER_LEVEL,
    )


def ransom_cost(slot: int, level: int) -> int:
    """هزینهٔ پرداختِ غرامت برای آزادیِ جاسوسِ دستگیر‌شده."""
    factor = max(RANSOM_FLOOR_FACTOR, RANSOM_BASE_FACTOR - (level - 1) * RANSOM_REDUCE_PER_LEVEL)
    return int(hire_cost(slot) * factor)


def report_accuracy(level: int, spy_bonus: float = 0.0) -> float:
    """دقتِ گزارش (۰..۱). سطحِ پایین = اطلاعاتِ تقریبی.

    spy_bonus: افزایشِ دقت از عمارتِ Ombra (کسری مثلاً ۰.۲).
    """
    return min(1.0, 0.5 + (level - 1) * 0.05 + spy_bonus)


def spy_stat_block(slot: int, level: int, extra_reduction_pct: float = 0.0) -> str:
    """خلاصهٔ خوانای مشخصاتِ یک جاسوس در سطحِ مشخص."""
    ms = mission_seconds(level)
    return (
        f"💰 غارت: <b>{income_pct(level):.1f}٪</b> از درآمدِ روزانهٔ هدف\n"
        f"🎯 احتمالِ دستگیری: <b>{capture_pct(level, extra_reduction_pct):.0f}٪</b>\n"
        f"⏱ چرخهٔ گزارش: هر <b>{ms // 3600}</b> ساعت\n"
        f"🧧 غرامتِ آزادی: <b>{ransom_cost(slot, level):,}</b>$"
    )
