# -*- coding: utf-8 -*-
"""مرحله ۱۹.۱ — منطقِ خالصِ «برندسازی» + v1.7.6 کول‌داونِ جدا + درآمدِ شهرت."""
from __future__ import annotations

BRAND_UNLOCK_LEVEL = 14
BRAND_FOUND_COST = 600_000
MAX_BRAND_LEVEL = 12

UPGRADE_BASE_COST = 60_000_000
UPGRADE_GROWTH = 1.6

# هر کمپین کول‌داونِ مستقل دارد.
CAMPAIGNS = {
    "flyer": {"name": "📰 تراکت و بنر", "cost": 100_000, "rep": 8, "cooldown_h": 2},
    "radio": {"name": "📻 تبلیغِ رادیویی", "cost": 300_000, "rep": 25, "cooldown_h": 4},
    "tv": {"name": "📺 تیزرِ تلویزیونی", "cost": 1_000_000, "rep": 90, "cooldown_h": 8},
    "influencer": {"name": "📱 اینفلوئنسرِ مجازی", "cost": 2_400_000, "rep": 220, "cooldown_h": 12},
    "stadium": {"name": "🏟️ اسپانسرِ استادیوم", "cost": 6_000_000, "rep": 600, "cooldown_h": 24},
}
CAMPAIGN_ORDER = ["flyer", "radio", "tv", "influencer", "stadium"]

TIERS = [
    (0, "🆕 تازه‌کار"),
    (500, "📈 شناخته‌شده"),
    (2_000, "⭐ محبوب"),
    (6_000, "🏅 معتبر"),
    (15_000, "👑 ایکونیک"),
    (40_000, "🌍 جهانی"),
]


def upgrade_cost(level: int) -> int:
    lvl = max(1, int(level))
    return int(UPGRADE_BASE_COST * (UPGRADE_GROWTH ** (lvl - 1)))


def can_upgrade(level: int) -> bool:
    return int(level) < MAX_BRAND_LEVEL


def income_bonus_pct(level: int) -> int:
    """قدیمی — دیگر روی درآمد برند اعمال نمی‌شود (فقط شهرت)."""
    return 0


# کلید تنظیم عددی ادمین (GameNumberSetting) — تداخل با سقف شهر/سربازخانه ندارد
BRAND_REP_CAP_KEY = "brand.reputation_income_cap_pct"
BRAND_REP_CAP_DEFAULT = 40  # درصد
BRAND_REP_STEP = 500        # هر چند شهرت
BRAND_REP_STEP_PCT = 2      # چند درصد بابت هر پله


def reputation_income_bonus_pct(reputation: int, cap_pct: int | None = None) -> int:
    """بونس درآمد برند/هولدینگ فقط از شهرت.

    هر BRAND_REP_STEP شهرت = +BRAND_REP_STEP_PCT٪
    سقف از ادمین (cap_pct) یا پیش‌فرض BRAND_REP_CAP_DEFAULT.
    سطح برند اثر ندارد.
    """
    rep = max(0, int(reputation or 0))
    cap = BRAND_REP_CAP_DEFAULT if cap_pct is None else max(0, int(cap_pct))
    raw = (rep // BRAND_REP_STEP) * BRAND_REP_STEP_PCT
    return min(cap, int(raw))


def total_income_bonus_pct(level: int = 0, reputation: int = 0, cap_pct: int | None = None) -> int:
    """سازگاری با کد قدیم — فقط شهرت؛ level نادیده."""
    return int(reputation_income_bonus_pct(reputation, cap_pct=cap_pct))


def brand_income_bonus_hint(reputation: int, cap_pct: int | None = None) -> str:
    rep = max(0, int(reputation or 0))
    cap = BRAND_REP_CAP_DEFAULT if cap_pct is None else max(0, int(cap_pct))
    pct = reputation_income_bonus_pct(rep, cap_pct=cap)
    step = BRAND_REP_STEP
    rem = step - (rep % step) if (rep % step) else (step if pct < cap else 0)
    if cap <= 0:
        nxt = "سقف بونس توسط ادمین ۰٪ است"
    elif pct >= cap:
        nxt = f"سقف بونس شهرت پر است (+{cap}٪ — تنظیم ادمین)"
    else:
        nxt = f"تا +{BRAND_REP_STEP_PCT}٪ بعدی: {rem:,} شهرت | سقف ادمین: +{cap}٪"
    return (
        f"📈 بونس درآمد (فقط شهرت): +{pct}٪"
        f" — هر {step:,} شهرت = +{BRAND_REP_STEP_PCT}٪"
        f" | {nxt}"
    )


def get_campaign(key: str):
    return CAMPAIGNS.get(key)


def tier_for(reputation: int):
    label = TIERS[0][1]
    for threshold, name in TIERS:
        if reputation >= threshold:
            label = name
        else:
            break
    return label


def next_tier(reputation: int):
    for threshold, name in TIERS:
        if reputation < threshold:
            return threshold, name
    return None


def prestige_value(level: int, reputation: int) -> int:
    return int(level) * 5_000 + int(reputation) * 20
