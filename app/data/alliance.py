# -*- coding: utf-8 -*-
"""منطقِ خالصِ اتحادیه‌ها و جنگِ اتحادیه (مرحله ۱۸).

هیچ وابستگیِ دیتابیسی ندارد تا به‌راحتی و مستقل تست شود. اعداد اینجا در یک‌جا
جمع‌اند تا در مرحله ۲۱ (قفل و توازنِ نهایی) به‌سادگی تنظیم شوند.
"""
from __future__ import annotations

import random
import re

# --------------------------- ثابت‌ها ---------------------------
FOUND_LEVEL = 15            # حداقلِ سطحِ لازم برای تأسیسِ اتحادیه
FOUND_COST = 1_000_000       # هزینه‌ی تأسیس

MEMBER_CAP_DEFAULT = 20    # سقفِ اعضای اتحادیه‌ی تازه‌تأسیس (سطح ۱)
MEMBER_CAP_MAX = 200       # سقفِ نهایی با ارتقا
MEMBER_CAP_STEP = 20       # افزایشِ سقف در هر سطحِ ارتقا

SUB_PCT_MIN, SUB_PCT_MAX = 5, 20      # بازه‌ی مجازِ درصدِ اشتراکِ عضویت
SUB_DAYS_MIN, SUB_DAYS_MAX = 1, 7     # بازه‌ی مجازِ دوره‌ی اشتراک (روز)

MEMBER_POWER_FACTOR = 0.20            # سهمِ مجموعِ قدرتِ اعضا در قدرتِ اتحادیه

VOTE_HOURS = 3                        # مهلتِ رأی‌گیریِ جنگ (ساعت)
VOTE_PASS_RATIO = 0.5                 # آستانه‌ی تصویبِ حمله (۵۰٪ اعضا)

WAR_LOOT_DAYS = 10
WAR_LOOT_PCT_MIN, WAR_LOOT_PCT_MAX = 5, 20        # غنیمتِ برنده از صندوقِ بازنده
WAR_PENALTY_PCT_MIN, WAR_PENALTY_PCT_MAX = 20, 40  # غرامتِ مهاجم اگر ببازد

ROLE_LEADER = "leader"
ROLE_DEPUTY = "deputy"
ROLE_MEMBER = "member"
ROLE_LABELS = {
    ROLE_LEADER: "👑 رئیس",
    ROLE_DEPUTY: "🎖️ معاون",
    ROLE_MEMBER: "👤 عضو",
}

# --------------------------------------------------------------------------
# 🆕 مرحله ۳۰ — دسترسی‌هایِ معاون (رئیس هرکدام را می‌دهد/پس می‌گیرد)
# --------------------------------------------------------------------------
PERM_REQUESTS = "requests"     # دیدن/تأیید/ردِ درخواست‌های عضویت
PERM_UPGRADE = "upgrade"       # ارتقای سقفِ اعضا و قدرتِ نظامی از صندوق
PERM_WAR = "war"               # پیشنهادِ جنگ و مدیریتِ رأی‌گیری
PERM_SETTINGS = "settings"     # تنظیمات (نام، آیدی، اشتراک، آستانه‌ی قدرت)

PERM_ORDER = (PERM_REQUESTS, PERM_UPGRADE, PERM_WAR, PERM_SETTINGS)
PERM_LABELS = {
    PERM_REQUESTS: "📥 درخواست‌های عضویت",
    PERM_UPGRADE: "⬆️ ارتقای اتحادیه",
    PERM_WAR: "⚔️ جنگِ اتحادیه",
    PERM_SETTINGS: "⚙️ تنظیماتِ اتحادیه",
}
# معاونِ تازه به‌طورِ پیش‌فرض این دو دسترسی را دارد
DEFAULT_DEPUTY_PERMS = (PERM_REQUESTS, PERM_WAR)

_TAG_RE = re.compile(r"^[A-Za-z0-9_]{3,20}$")


def normalize_tag(raw: str) -> str:
    """آیدیِ اتحادیه را یکدست می‌کند: حذفِ @ و فاصله، حروفِ کوچک."""
    return (raw or "").strip().lstrip("@").lower()


def tag_is_valid(raw: str) -> bool:
    """آیدی باید ۳ تا ۲۰ کاراکترِ انگلیسی/عدد/زیرخط باشد."""
    return bool(_TAG_RE.match((raw or "").strip().lstrip("@")))


def clamp_sub_pct(pct: int) -> int:
    return max(SUB_PCT_MIN, min(SUB_PCT_MAX, int(pct)))


def clamp_sub_days(days: int) -> int:
    return max(SUB_DAYS_MIN, min(SUB_DAYS_MAX, int(days)))


# --------------------------- ارتقا ---------------------------
def member_cap_for_level(level: int) -> int:
    """سقفِ اعضا در یک سطح: سطح ۱ = ۲۰، هر سطح +۲۰ تا سقفِ ۲۰۰."""
    lvl = max(1, int(level))
    return min(MEMBER_CAP_MAX, MEMBER_CAP_DEFAULT + (lvl - 1) * MEMBER_CAP_STEP)


def cap_is_maxed(level: int) -> bool:
    return member_cap_for_level(level) >= MEMBER_CAP_MAX


def cap_upgrade_cost(level: int) -> int:
    """هزینه‌ی ارتقای سطحِ سقفِ اعضا (خطیِ ملایم بر حسبِ سطحِ فعلی)."""
    return 2_000_000 * max(1, int(level))


def mil_upgrade_cost(mil_level: int) -> int:
    """هزینه‌ی ارتقای قدرتِ نظامیِ اتحادیه."""
    return 1_000_000 * (max(0, int(mil_level)) + 1)


def mil_power_for_level(mil_level: int) -> int:
    """قدرتِ نظامیِ به‌دست‌آمده از سطحِ نظامیِ اتحادیه (هر سطح +۲۵۰)."""
    return max(0, int(mil_level)) * 250


# --------------------------- قدرت و رنک ---------------------------
def alliance_power(military_power: int, members_power_sum: int) -> int:
    """قدرتِ اتحادیه = قدرتِ نظامی + ۲۰٪ مجموعِ قدرتِ اعضا."""
    return int(max(0, military_power) + MEMBER_POWER_FACTOR * max(0, members_power_sum))


def income_bonus_pct(level: int) -> int:
    """بونوسِ درصدیِ درآمدِ اعضا بسته به سطحِ اتحادیه (۵٪ در سطح ۱ تا سقفِ ۱۵٪)."""
    return min(15, 5 + (max(1, int(level)) - 1) * 2)


# --------------------------- رأی‌گیری ---------------------------
def vote_passes(yes_votes: int, member_count: int) -> bool:
    """آیا با تعدادِ آرای موافق، حمله تصویب می‌شود؟ (۵۰٪ یا بیشترِ اعضا)"""
    if member_count <= 0:
        return False
    return (yes_votes / member_count) >= VOTE_PASS_RATIO


# --------------------------- جنگ ---------------------------
def war_win_probability(att_power: int, def_power: int) -> float:
    a = max(1, int(att_power))
    d = max(1, int(def_power))
    return max(0.10, min(0.90, a / (a + d)))


def _scaled(lo: int, hi: int, t: float) -> int:
    t = max(0.0, min(1.0, t))
    return int(round(lo + (hi - lo) * t))


def war_loot_percent(att_power: int, def_power: int) -> int:
    """درصدِ غنیمت (۵ تا ۲۰) — هرچه مهاجم قوی‌تر، بیشتر."""
    a = max(1, int(att_power))
    d = max(1, int(def_power))
    ratio = a / (a + d)
    return _scaled(WAR_LOOT_PCT_MIN, WAR_LOOT_PCT_MAX, (ratio - 0.5) * 2)


def war_penalty_percent(att_power: int, def_power: int) -> int:
    """درصدِ غرامتِ مهاجمِ بازنده (۲۰ تا ۴۰) — هرچه مدافع قوی‌تر، بیشتر."""
    a = max(1, int(att_power))
    d = max(1, int(def_power))
    ratio = d / (a + d)
    return _scaled(WAR_PENALTY_PCT_MIN, WAR_PENALTY_PCT_MAX, (ratio - 0.5) * 2)


def war_loot_amount(def_treasury: int, loot_pct: int) -> int:
    """مبلغِ غنیمت از صندوقِ حریف، سقف‌خورده با موجودیِ صندوق."""
    gross = int(max(0, def_treasury) * max(0, loot_pct) / 100)
    return max(0, min(gross, int(max(0, def_treasury))))


def war_penalty_amount(att_treasury: int, penalty_pct: int) -> int:
    """مبلغِ غرامت از صندوقِ مهاجم، سقف‌خورده با موجودیِ صندوق."""
    gross = int(max(0, att_treasury) * max(0, penalty_pct) / 100)
    return max(0, min(gross, int(max(0, att_treasury))))


def roll_alliance_battle(att_power: int, def_power: int, rng: random.Random | None = None) -> bool:
    """True یعنی اتحادیه‌ی مهاجم پیروز شد."""
    r = rng or random
    return r.random() < war_win_probability(att_power, def_power)
