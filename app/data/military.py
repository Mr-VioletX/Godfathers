# -*- coding: utf-8 -*-
"""مرحله ۱۹ — سیستمِ نظامیِ گسترده: انواعِ نیرو، ارتقا/آموزش و موتورِ نبردِ
مبتنی بر «سنگ‌کاغذ‌قیچی» (پدافند هوایی ← جنگنده/بمبر/موشک، تانک/سرباز ← اهدافِ زمینی، ...).

این ماژول کاملاً «خالص» است (بدونِ وابستگی به دیتابیس) تا مستقل تست شود؛ منطقِ
پرس‌وجو و اعمالِ نتیجه در app/services/military_service.py قرار دارد.

مفاهیم:
  • هر نیرو یک «کلاسِ حضور» دارد: ground (زمینی) یا air (هوایی) — یعنی هنگامِ حمله
    در کدام رده هدف قرار می‌گیرد.
  • هر نیرو مجموعه‌ای از کلاس‌هایی که می‌تواند بزند دارد (can_hit).
  • ضریب‌های counter (vs) برتری/ضعفِ نوع‌به‌نوع را می‌سازند تا ترکیبِ نیرو و
    استراتژی معنا پیدا کند (مثلاً ضدهوایی فقط هوایی را می‌زند و برابرِ جنگنده
    بسیار قوی است، اما در برابرِ تانک بی‌فایده است).
  • «اسلحه» یک نیروی مستقر نیست؛ تجهیزاتی است که ضریبِ حمله‌ی سربازها را بالا می‌برد.
  • هر نوع نیرو «سطحِ ارتقا/آموزشِ» مخصوصِ خودش را دارد؛ ارتقا روی همه‌ی نیروهای
    موجودِ همان نوع اثر می‌گذارد (به‌نفعِ کسی که از قبل نیروی زیاد داشته)، اما
    خریدِ نیروی جدید در سطحِ بالاتر گران‌تر است.
"""
from __future__ import annotations

import random

# ثابت‌های کلی ------------------------------------------------------------
MILITARY_UNLOCK_LEVEL = 12          # حداقلِ سطحِ بازیکن برای بازشدنِ بخشِ نظامی
MAX_UNIT_LEVEL = 10                 # سقفِ سطحِ ارتقا/آموزشِ هر نوع نیرو
UPGRADE_POWER_STEP = 0.15          # هر سطحِ ارتقا: +۱۵٪ قدرت روی آن نوع
NEW_UNIT_LEVEL_SURCHARGE = 0.45    # خریدِ نیروی جدید در هر سطحِ بالاتر: +۴۵٪ قیمت
MAX_BATTLE_ROUNDS = 6              # سقفِ راندهای شبیه‌سازیِ نبرد
DEFENSE_MITIGATION = 0.10          # ضریبِ کاهشِ آسیب توسطِ دفاعِ هدف

# کلاس‌های حضور
GROUND = "ground"
AIR = "air"

CATEGORY_LABELS = {
    "soldier": "🪖 نیروی پیاده",
    "weapon": "🔫 تسلیحاتِ سبک",
    "tank": "🛡️ زرهی/تانک",
    "aa": "🎯 پدافند هوایی",
    "missile": "🚀 موشکی",
    "fighter": "✈️ جنگنده",
    "bomber": "🛩️ بمب‌افکن",
}
CATEGORY_ORDER = ["soldier", "weapon", "tank", "aa", "missile", "fighter", "bomber"]


# کاتالوگِ نیروها --------------------------------------------------------
# فیلدها:
#   cat: دسته | name: نام | dclass: کلاسِ حضور (ground/air) | can_hit: کلاس‌های قابل‌هدف
#   atk/def/hp: آمارِ پایه | cost: قیمتِ پایه (سطح ۰) | unlock: سطحِ لازمِ بازیکن
#   vs: ضریبِ برتری برحسبِ دسته‌ی هدف | pros/cons: توضیحِ نقاطِ قوت/ضعف
#   wpn_bonus: (فقط اسلحه) میزانِ افزایشِ حمله‌ای که به سربازها می‌دهد
UNITS: dict[str, dict] = {
    # --- نیروی پیاده (زمینی) ---
    "militia": {
        "cat": "soldier", "name": "🚶 شبه‌نظامی", "dclass": GROUND, "can_hit": [GROUND],
        "atk": 6, "def": 5, "hp": 18, "cost": 10_000, "unlock": 12,
        "vs": {"soldier": 1.0},
        "pros": "ارزان و سریع‌الاحداث؛ مناسبِ پُرکردنِ خط.",
        "cons": "ضعیف در برابرِ زره و کاملاً بی‌دفاع برابرِ حملاتِ هوایی.",
    },
    "rifleman": {
        "cat": "soldier", "name": "🪖 تفنگدار", "dclass": GROUND, "can_hit": [GROUND],
        "atk": 11, "def": 9, "hp": 26, "cost": 24_000, "unlock": 12,
        "vs": {"soldier": 1.15},
        "pros": "ستونِ فقراتِ ارتش؛ با تسلیحاتِ سبک بسیار مؤثر.",
        "cons": "در برابرِ تانک و هواپیما آسیب‌پذیر است.",
    },
    "commando": {
        "cat": "soldier", "name": "🥷 کماندو", "dclass": GROUND, "can_hit": [GROUND],
        "atk": 20, "def": 14, "hp": 34, "cost": 64_000, "unlock": 16,
        "vs": {"soldier": 1.3, "aa": 1.4, "missile": 1.4},
        "pros": "نفوذی و کُشنده؛ در انهدامِ پدافند و سکوهای موشکی عالی است.",
        "cons": "گران و همچنان بی‌پوشش در برابرِ حملاتِ هوایی.",
    },
    # --- تسلیحاتِ سبک (تجهیزات؛ حمله‌ی سربازها را بالا می‌برد) ---
    "pistol": {
        "cat": "weapon", "name": "🔫 سلاحِ کمری", "dclass": GROUND, "can_hit": [],
        "atk": 3, "def": 2, "hp": 10, "cost": 6_000, "unlock": 12, "vs": {},
        "wpn_bonus": 3,
        "pros": "ارزان؛ کمی به قدرتِ آتشِ پیاده‌نظام اضافه می‌کند.",
        "cons": "اثرِ محدود؛ برای ارتشِ بزرگ کافی نیست.",
    },
    "rifle": {
        "cat": "weapon", "name": "🔫 تفنگِ تهاجمی", "dclass": GROUND, "can_hit": [],
        "atk": 7, "def": 4, "hp": 18, "cost": 18_000, "unlock": 12, "vs": {},
        "wpn_bonus": 7,
        "pros": "افزایشِ چشمگیرِ حمله‌ی پیاده‌نظام.",
        "cons": "بدونِ سرباز بی‌فایده است.",
    },
    "rpg": {
        "cat": "weapon", "name": "💥 آرپی‌جی", "dclass": GROUND, "can_hit": [],
        "atk": 15, "def": 8, "hp": 34, "cost": 48_000, "unlock": 15, "vs": {},
        "wpn_bonus": 15,
        "pros": "به پیاده‌نظام قدرتِ ضدزرهِ محدود می‌دهد.",
        "cons": "گران؛ فقط وقتی سربازِ کافی داری صرف می‌کند.",
    },
    # --- زرهی/تانک (زمینی؛ قویِ ضدِ زمین) ---
    "apc": {
        "cat": "tank", "name": "🚛 نفربرِ زرهی", "dclass": GROUND, "can_hit": [GROUND],
        "atk": 16, "def": 22, "hp": 70, "cost": 120_000, "unlock": 14,
        "vs": {"soldier": 1.5, "tank": 0.8},
        "pros": "سپرِ خطِ مقدم؛ دفاعِ بالا و کُشنده برابرِ پیاده‌نظام.",
        "cons": "برابرِ تانک‌های سنگین و بمب‌افکن ضعیف است.",
    },
    "tank": {
        "cat": "tank", "name": "🛡️ تانکِ نبرد", "dclass": GROUND, "can_hit": [GROUND],
        "atk": 34, "def": 30, "hp": 120, "cost": 360_000, "unlock": 16,
        "vs": {"soldier": 1.8, "tank": 1.2, "aa": 1.5},
        "pros": "مشتِ آهنینِ نبردِ زمینی؛ همه‌ی اهدافِ زمینی را درهم می‌کوبد.",
        "cons": "در برابرِ بمب‌افکن و موشک بسیار آسیب‌پذیر است.",
    },
    "heavy_tank": {
        "cat": "tank", "name": "🦾 تانکِ سنگین", "dclass": GROUND, "can_hit": [GROUND],
        "atk": 52, "def": 48, "hp": 200, "cost": 800_000, "unlock": 20,
        "vs": {"soldier": 2.0, "tank": 1.5, "aa": 1.8},
        "pros": "برترین سلاحِ زمینی؛ سنگر‌شکن و دیرِنابودشدنی.",
        "cons": "بسیار گران و همچنان طعمه‌ی نیروی هوایی.",
    },
    # --- پدافند هوایی (زمینی؛ فقط هوایی را می‌زند — ضدِ جنگنده/بمبر/موشک) ---
    "aa_gun": {
        "cat": "aa", "name": "🔫 توپِ ضدهوایی", "dclass": GROUND, "can_hit": [AIR],
        "atk": 20, "def": 12, "hp": 40, "cost": 100_000, "unlock": 14,
        "vs": {"fighter": 1.8, "bomber": 1.6, "missile": 1.4},
        "pros": "سپرِ آسمان؛ ارزان‌ترین راهِ مهارِ تهدیدِ هوایی.",
        "cons": "در برابرِ اهدافِ زمینی کاملاً بی‌اثر است.",
    },
    "sam": {
        "cat": "aa", "name": "🎯 سامانه‌ی موشکیِ سام", "dclass": GROUND, "can_hit": [AIR],
        "atk": 46, "def": 20, "hp": 70, "cost": 440_000, "unlock": 18,
        "vs": {"fighter": 2.2, "bomber": 2.4, "missile": 2.0},
        "pros": "وحشتِ خلبان‌ها؛ آسمان را برای دشمن جهنم می‌کند.",
        "cons": "گران و برابرِ یورشِ زمینی بی‌دفاع.",
    },
    # --- موشکی (زمینی؛ هم زمین هم هوا را می‌زند) ---
    "rocket": {
        "cat": "missile", "name": "🚀 راکتِ سبک", "dclass": GROUND, "can_hit": [GROUND, AIR],
        "atk": 30, "def": 6, "hp": 24, "cost": 180_000, "unlock": 16,
        "vs": {"soldier": 1.4, "tank": 1.3, "aa": 1.3, "fighter": 1.1},
        "pros": "آتشِ سنگین و انعطاف‌پذیر روی هر هدف.",
        "cons": "شکننده؛ اگر مستقیم هدف قرار گیرد زود نابود می‌شود.",
    },
    "ballistic": {
        "cat": "missile", "name": "☢️ موشکِ بالستیک", "dclass": GROUND, "can_hit": [GROUND, AIR],
        "atk": 70, "def": 8, "hp": 30, "cost": 680_000, "unlock": 22,
        "vs": {"soldier": 1.6, "tank": 1.7, "aa": 1.7, "bomber": 1.3, "fighter": 1.3},
        "pros": "قدرتِ تخریبِ عظیم؛ می‌تواند خطِ دشمن را متلاشی کند.",
        "cons": "بسیار گران و در برابرِ پدافندِ سام بسیار آسیب‌پذیر.",
    },
    # --- جنگنده (هوایی؛ ضدِ هوا و زمین — به‌ویژه شکارِ بمب‌افکن) ---
    "fighter": {
        "cat": "fighter", "name": "✈️ جنگنده", "dclass": AIR, "can_hit": [AIR, GROUND],
        "atk": 40, "def": 24, "hp": 80, "cost": 560_000, "unlock": 18,
        "vs": {"bomber": 2.2, "fighter": 1.3, "soldier": 1.2, "tank": 0.9},
        "pros": "سلطانِ آسمان؛ برترِ هوایی و شکارچیِ بمب‌افکن.",
        "cons": "در برابرِ پدافندِ متمرکز (سام/ضدهوایی) تلفاتِ سنگین می‌دهد.",
    },
    "jet": {
        "cat": "fighter", "name": "🛫 جنگنده‌ی نسلِ پنجم", "dclass": AIR, "can_hit": [AIR, GROUND],
        "atk": 64, "def": 40, "hp": 120, "cost": 1_200_000, "unlock": 24,
        "vs": {"bomber": 2.6, "fighter": 1.6, "soldier": 1.3, "tank": 1.1, "missile": 1.4},
        "pros": "برترینِ نبردِ هوایی؛ رادارگریز و کُشنده.",
        "cons": "هزینه‌ی نجومی؛ همچنان مقابلِ انبوهِ پدافند ریسک دارد.",
    },
    # --- بمب‌افکن (هوایی؛ ویرانگرِ زمین) ---
    "bomber": {
        "cat": "bomber", "name": "🛩️ بمب‌افکن", "dclass": AIR, "can_hit": [GROUND],
        "atk": 75, "def": 18, "hp": 110, "cost": 900_000, "unlock": 20,
        "vs": {"soldier": 2.2, "tank": 2.0, "aa": 1.8, "missile": 1.8},
        "pros": "باران آتش بر زمین؛ خطِ زمینیِ دشمن را نابود می‌کند.",
        "cons": "کُند و بی‌دفاع؛ بدونِ اسکورتِ جنگنده طعمه‌ی پدافند و جنگنده است.",
    },
    "stealth_bomber": {
        "cat": "bomber", "name": "🦇 بمب‌افکنِ رادارگریز", "dclass": AIR, "can_hit": [GROUND],
        "atk": 120, "def": 34, "hp": 150, "cost": 1_800_000, "unlock": 26,
        "vs": {"soldier": 2.4, "tank": 2.4, "aa": 2.2, "missile": 2.2},
        "pros": "سلاحِ راهبردیِ نهایی؛ ویرانیِ گسترده با ردِ رادارِ کم.",
        "cons": "گران‌ترین نیرو؛ از دست‌دادنش فاجعه است.",
    },
}

UNIT_ORDER = list(UNITS.keys())


def get_unit(key: str) -> dict | None:
    return UNITS.get(key)


def units_in_category(cat: str) -> list[str]:
    return [k for k in UNIT_ORDER if UNITS[k]["cat"] == cat]


def unlocked_units(player_level: int) -> list[str]:
    lvl = int(player_level or 1)
    return [k for k in UNIT_ORDER if UNITS[k]["unlock"] <= lvl]


# قیمت و ارتقا -----------------------------------------------------------
def level_multiplier(level: int) -> float:
    """ضریبِ قدرتِ ناشی از سطحِ ارتقا/آموزش (روی حمله/دفاع/جانِ همان نوع)."""
    return 1.0 + UPGRADE_POWER_STEP * max(0, int(level))


def buy_cost(unit_key: str, level: int) -> int:
    """قیمتِ خریدِ یک واحد در سطحِ فعلیِ آن نوع.
    هرچه سطحِ ارتقای آن نوع بالاتر باشد، واحدِ جدید گران‌تر است."""
    u = UNITS.get(unit_key)
    if not u:
        return 0
    return int(u["cost"] * (1.0 + NEW_UNIT_LEVEL_SURCHARGE * max(0, int(level))))


def upgrade_cost(unit_key: str, level: int, count: int) -> int:
    """هزینه‌ی ارتقای یک نوع از سطحِ فعلی به بعدی.
    چون ارتقا روی «همه‌ی» واحدهای موجود اثر می‌گذارد، هزینه با تعدادِ واحدها
    (کمی) بالا می‌رود تا منطقی بماند، اما همچنان به‌صرفه است."""
    u = UNITS.get(unit_key)
    if not u:
        return 0
    base = int(u["cost"] * 22.0 * (int(level) + 1))
    scale = 1.0 + min(2.0, max(0, int(count)) / 25.0)
    return int(base * scale)


def can_upgrade(level: int) -> bool:
    return int(level) < MAX_UNIT_LEVEL


# 🆕 مرحله ۴۵ — زمانِ پرورشِ نیرو (صف). ساختِ نیرو آنی نیست.
# 🆕 مرحله ۶۷ — همهٔ زمان‌ها دقیقاً نصف شدند و هیچ دو نیرویی زمان‌ِ یکسان ندارد.
# این جدول فقط زمان‌ِ دسته‌های ناشناخته را پوشش می‌دهد (fallback).
TRAIN_SECONDS_PER_UNIT = {
    "soldier": 80,
    "weapon": 65,
    "tank": 380,
    "aa": 280,
    "missile": 560,
    "fighter": 710,
    "bomber": 860,
}
# زمان‌ِ دقیق‌ِ هر واحد (ثانیه) — مرجع‌ِ قطعی.
# همهٔ مقادیر نسبت به نسخهٔ قبل نصف شده‌اند و همه یکتا هستند.
TRAIN_SECONDS_BY_UNIT = {
    "militia": 75, "rifleman": 110, "commando": 210,
    "pistol": 60, "rifle": 105, "rpg": 180,
    "apc": 375, "tank": 525, "heavy_tank": 750,
    "aa_gun": 275, "sam": 450,
    "rocket": 550, "ballistic_missile": 825,
    "fighter": 700, "jet": 1000,
    "bomber": 850, "stealth_bomber": 1250,
}
TRAIN_DEFAULT_PER_UNIT = 150
TRAIN_MIN_SECONDS = 30                 # کف فنیِ صف؛ زمان هر واحد طبق جدول ۱۰× شده است
TRAIN_MAX_SECONDS = 365 * 24 * 60 * 60  # سقف فنی یک‌سال؛ زمان بچ‌ها دیگر روی ۶۰ ساعت قطع نمی‌شود

def train_seconds_per_unit(unit_key: str) -> int:
    """🆕 مرحله ۶۷ — زمان‌ِ قطعی‌ِ ساخت‌ِ یک واحد از این نوع (ثانیه).

    مرجع‌ِ یکتای‌ِ زمان است؛ هم نمایش، هم ثبت‌ِ صف و هم تحویل‌ِ نیرو از همین عدد
    استفاده می‌کنند تا دیگر هیچ‌وقت بچ‌ِ بزرگ‌تر از بچ‌ِ کوچک‌تر زودتر تمام نشود.
    """
    u = UNITS.get(unit_key)
    if not u:
        return int(TRAIN_DEFAULT_PER_UNIT)
    return int(TRAIN_SECONDS_BY_UNIT.get(
        unit_key,
        TRAIN_SECONDS_PER_UNIT.get(u["cat"], TRAIN_DEFAULT_PER_UNIT),
    ))


def train_seconds(unit_key: str, qty: int) -> int:
    """زمانِ لازم (ثانیه) برای پرورشِ qty واحد از یک نوع.

    کاملاً خطی و قابل‌پیش‌بینی: qty × زمان‌ِ هر واحد.
    """
    per = train_seconds_per_unit(unit_key)
    total = per * max(1, int(qty))
    return int(max(TRAIN_MIN_SECONDS, min(TRAIN_MAX_SECONDS, total)))


# 🆕 v1.7.3 — زمان ارتقا فقط به نوع نیرو + لول مقصد بستگی دارد (نه تعداد).
# بازه: ۵ تا ۲۴ ساعت. واحدهای ساده‌تر از ۵h شروع می‌شوند؛ پیشرفته‌تر پایه بالاتر.
UPGRADE_BASE_HOURS_BY_UNIT = {
    "militia": 5.0, "rifleman": 5.5, "commando": 7.0,
    "pistol": 5.0, "rifle": 5.5, "rpg": 6.5,
    "apc": 7.5, "tank": 9.0, "heavy_tank": 11.0,
    "aa_gun": 7.0, "sam": 9.5,
    "rocket": 8.5, "ballistic": 12.0,
    "fighter": 10.0, "jet": 13.0,
    "bomber": 11.5, "stealth_bomber": 14.0,
}
UPGRADE_BASE_HOURS_BY_CAT = {
    "soldier": 5.5, "weapon": 5.5, "tank": 9.0, "aa": 8.0,
    "missile": 10.0, "fighter": 11.0, "bomber": 12.0,
}
UPGRADE_MIN_HOURS = 5.0
UPGRADE_MAX_HOURS = 24.0


def upgrade_base_hours(unit_key: str) -> float:
    u = UNITS.get(unit_key) or {}
    if unit_key in UPGRADE_BASE_HOURS_BY_UNIT:
        return float(UPGRADE_BASE_HOURS_BY_UNIT[unit_key])
    return float(UPGRADE_BASE_HOURS_BY_CAT.get(u.get("cat"), 8.0))


def upgrade_seconds(unit_key: str, qty: int, target_level: int) -> int:
    """🆕 v1.7.3 — زمان ارتقا مستقل از تعداد نیرو.

    qty فقط برای سازگاری امضا نگه داشته شده و استفاده نمی‌شود.
    هر نوع نیرو پایهٔ خودش را دارد (از ۵h) و با بالا رفتن لول مقصد
    تا سقف ۲۴ ساعت افزایش می‌یابد.
    """
    _ = qty  # عمداً نادیده — ارتقا روی کل پشته یک زمان ثابت دارد
    base = max(UPGRADE_MIN_HOURS, min(UPGRADE_MAX_HOURS, upgrade_base_hours(unit_key)))
    t = max(1, int(target_level or 1))
    # لول ۱→۲ نزدیک پایه؛ لول MAX نزدیک ۲۴h
    frac = (t - 1) / max(1, MAX_UNIT_LEVEL - 1)
    hours = base + (UPGRADE_MAX_HOURS - base) * frac
    hours = max(UPGRADE_MIN_HOURS, min(UPGRADE_MAX_HOURS, hours))
    return int(round(hours * 3600))


def fmt_eta(seconds: int) -> str:
    """زمانِ باقی‌مانده را به شکلِ خوانا (فارسی) برمی‌گرداند."""
    s = max(0, int(seconds))
    if s < 60:
        return f"{s} ثانیه"
    m, s = divmod(s, 60)
    if m < 60:
        return f"{m} دقیقه" + (f" و {s} ثانیه" if s else "")
    h, m = divmod(m, 60)
    return f"{h} ساعت" + (f" و {m} دقیقه" if m else "")


# محاسبه‌ی قدرت ----------------------------------------------------------
def unit_power(unit_key: str, count: int, level: int) -> int:
    """قدرتِ نمایشی/رنکینگِ یک پشته‌ی نیرو (برای رتبه‌بندی و تطبیق)."""
    u = UNITS.get(unit_key)
    if not u or count <= 0:
        return 0
    base = u["atk"] + u["def"] + u["hp"] * 0.5
    if u["cat"] == "weapon":
        base = u.get("wpn_bonus", 0) * 3
    return int(base * count * level_multiplier(level))


def army_power(stacks: list[tuple[str, int, int]]) -> int:
    """قدرتِ کلِ ارتش. stacks = [(unit_key, count, level), ...]."""
    return int(sum(unit_power(k, c, lv) for k, c, lv in stacks))


def weapon_multiplier(stacks: list[tuple[str, int, int]]) -> float:
    """ضریبِ افزایشِ حمله‌ی سربازها بر اساسِ تسلیحاتِ سبکِ موجود.
    هرچه پوششِ تسلیحاتِ بیشتری نسبت به تعدادِ سرباز داشته باشی، بونوسِ بیشتری
    (تا سقفِ ۲٫۲ برابر) می‌گیری."""
    soldier_count = sum(c for k, c, lv in stacks if UNITS.get(k, {}).get("cat") == "soldier")
    if soldier_count <= 0:
        return 1.0
    wpn_score = 0.0
    for k, c, lv in stacks:
        u = UNITS.get(k)
        if u and u["cat"] == "weapon":
            wpn_score += u.get("wpn_bonus", 0) * c * level_multiplier(lv)
    # نرمال‌سازی نسبت به تعدادِ سرباز
    coverage = wpn_score / (soldier_count * 12.0)
    return 1.0 + min(1.2, coverage)


# موتورِ نبرد ------------------------------------------------------------
class _Stack:
    __slots__ = ("key", "cat", "dclass", "can_hit", "vs", "atk", "defense", "hp_each",
                 "count", "start", "pending")

    def __init__(self, key: str, count: int, level: int, wpn_mult: float):
        u = UNITS[key]
        self.key = key
        self.cat = u["cat"]
        self.dclass = u["dclass"]
        self.can_hit = set(u["can_hit"])
        self.vs = dict(u.get("vs", {}))
        mult = level_multiplier(level)
        atk = u["atk"] * mult
        if self.cat == "soldier":
            atk *= wpn_mult
        self.atk = atk
        self.defense = u["def"] * mult
        self.hp_each = max(1.0, u["hp"] * mult)
        self.count = float(count)
        self.start = float(count)
        self.pending = 0.0

    @property
    def alive(self) -> bool:
        return self.count > 0.5 and self.hp_each > 0

    @property
    def total_hp(self) -> float:
        return max(0.0, self.count) * self.hp_each


def _build_side(stacks: list[tuple[str, int, int]]) -> list[_Stack]:
    wpn = weapon_multiplier(stacks)
    out = []
    for key, count, level in stacks:
        u = UNITS.get(key)
        if not u or count <= 0:
            continue
        if not u["can_hit"]:      # تسلیحات مستقر نمی‌شوند
            continue
        out.append(_Stack(key, count, level, wpn))
    return out


def _deal_damage(attackers: list[_Stack], defenders: list[_Stack]) -> dict:
    """آسیبِ یک راند از مهاجم به مدافع را محاسبه و در pending ذخیره می‌کند.
    آسیبِ نیرویی که هدفِ معتبر (از کلاسِ قابل‌هدفش) نداشته باشد، هدر می‌رود.
    """
    wasted = {}
    for s in attackers:
        if not s.alive:
            continue
        targets = [d for d in defenders if d.alive and d.dclass in s.can_hit]
        if not targets:
            wasted[s.cat] = wasted.get(s.cat, 0.0) + s.atk * s.count
            continue
        total_atk = s.atk * s.count
        weights = [t.count * s.vs.get(t.cat, 1.0) for t in targets]
        wsum = sum(weights) or 1.0
        for t, w in zip(targets, weights):
            share = total_atk * (w / wsum)
            mult = s.vs.get(t.cat, 1.0)
            raw = share * mult
            mitig = t.defense * t.count * DEFENSE_MITIGATION
            effective = max(share * 0.1, raw - mitig)
            kills = effective / t.hp_each
            t.pending += kills
    return wasted


# =====================================================================
# 🆕 مرحله ۷۰ — کفِ تلفات: هیچ نبردِ واقعی‌ای با «تلفاتِ صفر» تمام نمی‌شود
# =====================================================================
# چرا لازم بود؟ تسلیحاتِ سبک (can_hit خالی) در میدان مستقر نمی‌شوند؛ پس اگر ارتشِ
# یک طرف فقط تسلیحات بود، _build_side خالی می‌شد و موتور «تلفاتِ صفر» برمی‌گرداند.
# همچنین در نبردهای بسیار نامتوازن، آسیبِ راند می‌توانست به صفر گِرد شود.
MIN_CASUALTY_FRACTION_WINNER = 0.008   # حداقل ۰٫۸٪ از هر پشته‌ی برنده
MIN_CASUALTY_FRACTION_LOSER = 0.02     # حداقل ۲٪ از هر پشته‌ی بازنده
MIN_CASUALTY_UNITS = 1                 # دستِ‌کم یک واحد از هر پشته‌ی درگیر
HELPLESS_LOSS_FRACTION = 0.20          # طرفِ بدونِ نیروی مستقر: ۲۰٪ از کلِ نیرو


def _helpless_losses(stacks: list[tuple[str, int, int]] | None, *, enemy_power_ratio: float = 1.0) -> dict:
    """تلفاتِ طرفی که هیچ نیروی مستقرشدنی ندارد (مثلاً فقط تسلیحات).

    v1.7.2: درصد تلفات با نسبت قدرت دشمن مقیاس می‌شود.
    """
    ratio = max(0.25, min(3.0, float(enemy_power_ratio or 1.0)))
    frac = HELPLESS_LOSS_FRACTION * (0.6 + 0.5 * min(2.0, ratio))
    frac = max(0.08, min(0.55, frac))
    out: dict = {}
    for key, count, _lv in (stacks or []):
        c = int(count or 0)
        if c <= 0 or not UNITS.get(key):
            continue
        out[key] = min(c, max(MIN_CASUALTY_UNITS, int(round(c * frac))))
    return out


def _floor_losses(side: list[_Stack], fraction: float) -> dict:
    """کفِ تلفات برای هر پشته‌ی مستقرشده."""
    out: dict = {}
    for s in side:
        c = int(round(s.start))
        if c <= 0:
            continue
        out[s.key] = min(c, max(MIN_CASUALTY_UNITS, int(c * fraction)))
    return out


def _with_min_losses(side: list[_Stack], losses: dict, *, won: bool) -> dict:
    """تلفاتِ شبیه‌سازی را با کفِ تلفات ادغام می‌کند (بیشترِ دو مقدار)."""
    fraction = MIN_CASUALTY_FRACTION_WINNER if won else MIN_CASUALTY_FRACTION_LOSER
    out = dict(losses or {})
    for key, n in _floor_losses(side, fraction).items():
        out[key] = max(int(out.get(key, 0)), int(n))
    return {k: int(v) for k, v in out.items() if int(v) > 0}


def _merge_support_losses(
    raw_stacks: list[tuple[str, int, int]] | None,
    deployed: list[_Stack],
    losses: dict,
    *,
    won: bool,
) -> dict:
    """تلفات تسلیحات/پشتیبانی که در میدان مستقر نمی‌شوند."""
    out = dict(losses or {})
    start_dep = sum(float(s.start) for s in deployed) or 0.0
    lost_dep = sum(float(out.get(s.key, 0)) for s in deployed)
    if start_dep <= 0:
        ratio = MIN_CASUALTY_FRACTION_LOSER if not won else MIN_CASUALTY_FRACTION_WINNER
    else:
        ratio = max(0.0, min(0.85, lost_dep / start_dep))
    support_ratio = ratio * (0.70 if won else 0.90)
    support_ratio = max(
        MIN_CASUALTY_FRACTION_WINNER if won else MIN_CASUALTY_FRACTION_LOSER,
        support_ratio,
    )
    for key, count, _lv in (raw_stacks or []):
        u = UNITS.get(key)
        if not u or int(count or 0) <= 0:
            continue
        if u.get("can_hit"):
            continue
        c = int(count)
        lost = min(c, max(MIN_CASUALTY_UNITS, int(round(c * support_ratio))))
        if lost > 0:
            out[key] = max(int(out.get(key, 0)), lost)
    return {k: int(v) for k, v in out.items() if int(v) > 0}


def simulate_battle(
    attacker: list[tuple[str, int, int]],
    defender: list[tuple[str, int, int]],
    rng: random.Random | None = None,
) -> dict:
    """نبردِ کامل را شبیه‌سازی می‌کند.

    ورودی: فهرستِ پشته‌ها (unit_key, count, level) برای هر طرف.
    خروجی dict شامل:
      attacker_won: bool
      att_losses / def_losses: {unit_key: تعدادِ تلفات}
      att_power_left / def_power_left: قدرتِ باقی‌مانده
      rounds: تعدادِ راندها
      log: فهرستِ رخدادهای خواندنی برای گزارش
    """
    r = rng or random
    A = _build_side(attacker)
    D = _build_side(defender)
    log: list[str] = []

    if not A:
        # 🆕 مرحله ۷۰/۷۲ — مهاجم نیروی مستقرشدنی ندارد (مثلاً فقط تسلیحاتِ سبک)
        def_pwr = max(1, _side_power(D))
        att_raw = max(1, army_power(attacker or []))
        return {"attacker_won": False,
                "att_losses": _helpless_losses(attacker, enemy_power_ratio=def_pwr / att_raw),
                "def_losses": _floor_losses(D, MIN_CASUALTY_FRACTION_WINNER),
                "att_power_left": 0, "def_power_left": _side_power(D),
                "rounds": 1,
                "log": ["⚠️ مهاجم هیچ نیروی مستقرشدنی نداشت و آرایشش فرو ریخت."]}
    if not D:
        # 🆕 مرحله ۷۰/۷۲ — مدافع فقط تسلیحات/بی‌دفاع: تلفات متناسب با فشار مهاجم
        att_pwr = max(1, _side_power(A))
        def_raw = max(1, army_power(defender or []))
        win_frac = max(MIN_CASUALTY_FRACTION_WINNER,
                       min(0.04, MIN_CASUALTY_FRACTION_WINNER * (def_raw / att_pwr) * 3))
        return {"attacker_won": True,
                "att_losses": _floor_losses(A, win_frac),
                "def_losses": _helpless_losses(defender, enemy_power_ratio=att_pwr / def_raw),
                "att_power_left": _side_power(A), "def_power_left": 0,
                "rounds": 1,
                "log": ["💥 مدافع نیروی مستقرشدنی نداشت — پادگان/انبار تسلیحاتش آسیب دید!"]}

    rounds = 0
    for _ in range(MAX_BATTLE_ROUNDS):
        if _side_hp(A) <= 0 or _side_hp(D) <= 0:
            break
        rounds += 1
        for s in A + D:
            s.pending = 0.0
        w_att = _deal_damage(A, D)
        w_def = _deal_damage(D, A)
        for s in A + D:
            # کمی نوسانِ تصادفی برای واقعی‌بودن
            s.count = max(0.0, s.count - s.pending * r.uniform(0.85, 1.15))
        if rounds == 1:
            for cat, amt in w_att.items():
                if amt > 0:
                    log.append(f"⚠️ بخشی از نیروی «{CATEGORY_LABELS.get(cat, cat)}»‌ات هدفِ معتبر نداشت و آتشش هدر رفت.")
            for cat, amt in w_def.items():
                if amt > 0:
                    log.append(f"🎯 پدافند/آرایشِ تو باعث شد بخشی از آتشِ «{CATEGORY_LABELS.get(cat, cat)}»ِ دشمن هدر برود.")

    att_hp, def_hp = _side_hp(A), _side_hp(D)
    att_frac = att_hp / max(1.0, _side_start_hp(A))
    def_frac = def_hp / max(1.0, _side_start_hp(D))
    attacker_won = (def_hp <= 0) or (att_hp > 0 and att_frac >= def_frac)

    att_loss = _with_min_losses(A, _losses(A), won=attacker_won)
    def_loss = _with_min_losses(D, _losses(D), won=not attacker_won)
    # 🆕 v1.7.2 — تلفات پشتیبانی/تسلیحاتِ سبک متناسب با تلفات نیروهای مستقر
    att_loss = _merge_support_losses(attacker, A, att_loss, won=attacker_won)
    def_loss = _merge_support_losses(defender, D, def_loss, won=not attacker_won)
    return {
        "attacker_won": attacker_won,
        "att_losses": att_loss,
        "def_losses": def_loss,
        "att_power_left": _side_power(A),
        "def_power_left": _side_power(D),
        "rounds": rounds,
        "log": log,
    }


def _side_hp(side: list[_Stack]) -> float:
    return sum(s.total_hp for s in side)


def _side_start_hp(side: list[_Stack]) -> float:
    return sum(s.start * s.hp_each for s in side) or 1.0


def _side_power(side: list[_Stack]) -> int:
    return int(sum(unit_power(s.key, int(round(s.count)), 0) for s in side))


def _losses(side: list[_Stack]) -> dict:
    out = {}
    for s in side:
        lost = int(round(max(0.0, s.start - s.count)))
        if lost > 0:
            out[s.key] = lost
    return out


# رده‌بندیِ قدرتِ نظامی (برای نمایش/القاب) --------------------------------
MILITARY_RANKS = [
    (0, "🁢 بی‌ارتش"),
    (2_000, "🪖 شبه‌نظامی"),
    (10_000, "🎖️ گروهان"),
    (40_000, "🏵️ تیپ"),
    (120_000, "⭐ لشکر"),
    (300_000, "🌟 سپاه"),
    (700_000, "👑 ارتشِ امپراتوری"),
]


def military_rank(power: int) -> str:
    name = MILITARY_RANKS[0][1]
    for threshold, label in MILITARY_RANKS:
        if power >= threshold:
            name = label
    return name


# =====================================================================
# 🆕 مرحله ۴۶ — پیش‌بینیِ نبرد (درصدِ پیروزی + برآوردِ تلفات)
# =====================================================================
GROUND_CATS = ("soldier", "weapon", "tank")
AIR_CATS = ("fighter", "bomber")


def army_weakness(stacks) -> str:
    """ریسکِ واقعیِ تک‌بُعدی بودنِ ارتش را متنی برمی‌گرداند (خالی = متوازن)."""
    cats = set()
    for k, c, _lv in (stacks or []):
        u = get_unit(k)
        if u and int(c) > 0:
            cats.add(u["cat"])
    missing = []
    if not (cats & set(GROUND_CATS)):
        missing.append("زمینی")
    if not (cats & set(AIR_CATS)):
        missing.append("هوایی")
    if "aa" not in cats:
        missing.append("پدافند")
    if not missing:
        return ""
    return (
        "ارتشت تک‌بُعدی است — نداری: " + "، ".join(missing) +
        ". حریف دقیقاً از همین نقطه‌ضعف می‌زند."
    )


def predict_battle(attacker, defender, samples: int = 15, seed: int | None = None) -> dict:
    """چند بار نبرد را شبیه‌سازی می‌کند تا درصدِ پیروزی و بازه‌ی تلفات به‌دست آید."""
    att = [(k, int(c), int(lv)) for k, c, lv in (attacker or []) if int(c) > 0]
    dfn = [(k, int(c), int(lv)) for k, c, lv in (defender or []) if int(c) > 0]
    base = {"weakness": army_weakness(att)}
    if not att:
        base.update(win_prob=0.0, att_loss_min=0, att_loss_max=0, def_loss_min=0, def_loss_max=0)
        return base
    if not dfn:
        base.update(win_prob=1.0, att_loss_min=0, att_loss_max=0, def_loss_min=0, def_loss_max=0)
        return base
    wins = 0
    al, dl = [], []
    n = max(1, int(samples))
    for i in range(n):
        r = random.Random((int(seed or 7) * 7919) + i)
        try:
            res = simulate_battle(list(att), list(dfn), r)
        except Exception:
            continue
        wins += 1 if res.get("attacker_won") else 0
        al.append(sum(int(v) for v in (res.get("att_losses") or {}).values()))
        dl.append(sum(int(v) for v in (res.get("def_losses") or {}).values()))
    if not al:
        base.update(win_prob=0.5, att_loss_min=0, att_loss_max=0, def_loss_min=0, def_loss_max=0)
        return base
    base.update(
        win_prob=wins / float(len(al)),
        att_loss_min=min(al), att_loss_max=max(al),
        def_loss_min=min(dl), def_loss_max=max(dl),
    )
    return base


BARRACKS_BASE_CAPACITY = 10_000
BARRACKS_DEFAULT_MAX_CAPACITY = 2_000_000
BARRACKS_BASE_COST = 500_000_000
BARRACKS_FINAL_COST = 1_000_000_000_000
BARRACKS_BASE_LEVELS = 50

def barracks_levels(max_capacity: int) -> int:
    return max(BARRACKS_BASE_LEVELS, int((max(1, int(max_capacity)) + 39_999) // 40_000))
def barracks_capacity(level: int, max_capacity: int=BARRACKS_DEFAULT_MAX_CAPACITY) -> int:
    levels=barracks_levels(max_capacity); return min(int(max_capacity), BARRACKS_BASE_CAPACITY + int((max_capacity-BARRACKS_BASE_CAPACITY)*(max(0,level-1))/max(1,levels-1)))
def barracks_upgrade_cost(level: int, max_capacity: int=BARRACKS_DEFAULT_MAX_CAPACITY) -> int:
    levels=barracks_levels(max_capacity); return int(BARRACKS_BASE_COST + (BARRACKS_FINAL_COST-BARRACKS_BASE_COST)*(max(0,level-1)/max(1,levels-1)))
def fmt_money(value: int) -> str:
    value=int(value)
    return f"{value/1_000_000_000_000:.2f}t" if value >= 1_000_000_000_000 else f"{value:,}"
