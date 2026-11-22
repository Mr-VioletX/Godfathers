# -*- coding: utf-8 -*-
"""مرحله ۱۷ — داده و فرمول‌های خالصِ جنگِ شخصی، سپر/حالتِ ایمن،
تصرفِ شهر و تأسیسِ کشور.

همه‌ی ثابت‌ها و فرمول‌ها در یک‌جا متمرکز شده‌اند تا توازنِ بازی راحت تنظیم شود.
این ماژول کاملاً خالص است (بدونِ وابستگی به DB) تا مستقل تست شود.
"""
from __future__ import annotations

import random

# --------------------------- شرایطِ بازشدنِ جنگ ---------------------------
WAR_UNLOCK_LEVEL = 10          # حداقل سطح برای بازشدنِ بخشِ جنگ

# --------------------------- قفلِ غنیمت و سپر ---------------------------
LOOT_DAYS = 10                 # مدتِ غنیمت‌گیریِ برنده از بازنده (روز)
SHIELD_DAYS = 7                # سپرِ بازنده پس از پایانِ غنیمت (روز)
ATTACK_COOLDOWN_HOURS = 6      # فاصله‌ی حداقلی بینِ دو حمله‌ی مهاجم (ضدِ اسپم)
SAFE_TOTAL_DAYS = LOOT_DAYS + SHIELD_DAYS  # کلِ دوره‌ی مصونیتِ هدف

# --------------------------- درصدها ---------------------------
LOOT_PCT_MIN = 14              # حداقل غنیمت (قوی→ضعیف)
LOOT_PCT_MAX = 42              # حداکثر غنیمت (ضعیف→قوی)
PENALTY_PCT_MIN = 10           # حداقل غرامتِ باختِ مهاجم (از کلِ دارایی)
PENALTY_PCT_MAX = 40           # حداکثر
INFRA_DAMAGE_SAT = 15          # آسیب به رضایتِ شهرِ فعال هنگامِ باخت (واحد)

WIN_PROB_FLOOR = 0.10
WIN_PROB_CEIL = 0.90


def win_probability(attacker_power: int, defender_power: int) -> float:
    """احتمالِ بردِ مهاجم بر اساسِ نسبتِ قدرت (مهار‌شده در ۰٫۱۰..۰٫۹۰)."""
    a = max(1, int(attacker_power))
    d = max(1, int(defender_power))
    p = a / (a + d)
    return max(WIN_PROB_FLOOR, min(WIN_PROB_CEIL, p))


def _scaled(pct_min: int, pct_max: int, edge: float) -> int:
    """edge در بازه‌ی 0..1 (برتری)؛ خروجی بینِ pct_min..pct_max."""
    edge = max(0.0, min(1.0, edge))
    val = pct_min + (pct_max - pct_min) * edge
    return int(round(max(pct_min, min(pct_max, val))))


def loot_percent(attacker_power: int, defender_power: int) -> int:
    """درصد غنیمت ۱۴..۴۲ — قوی→ضعیف ۱۴٪، ضعیف→قوی ۴۲٪، درون‌یابی خطی.

    هم‌تراز با app.data.ranks.loot_percent_by_power
    """
    try:
        from app.data import ranks as RK
        return int(RK.loot_percent_by_power(attacker_power, defender_power))
    except Exception:
        a = max(1, int(attacker_power))
        d = max(1, int(defender_power))
        # edge: 0 weak attacker, 1 strong attacker
        ratio = a / max(1.0, float(d))
        if ratio >= 1.0 / 0.7:  # att much stronger
            e = 1.0
        elif ratio <= 1.0 / 1.3:
            e = 0.0
        else:
            # map ratio between 1/1.3 and 1/0.7
            lo, hi = 1.0 / 1.3, 1.0 / 0.7
            e = (ratio - lo) / (hi - lo)
            e = max(0.0, min(1.0, e))
        pct = 42 - (42 - 14) * e
        return int(round(max(14, min(42, pct))))


def penalty_percent(attacker_power: int, defender_power: int) -> int:
    """غرامتِ باختِ مهاجم (۱۰..۴۰)؛ هرچه مهاجم ضعیف‌تر، غرامتِ بیشتر."""
    a = max(1, int(attacker_power))
    d = max(1, int(defender_power))
    ratio = d / (a + d)          # سهمِ مدافع 0..1
    return _scaled(PENALTY_PCT_MIN, PENALTY_PCT_MAX, (ratio - 0.5) * 2)


def loot_amount(daily_income: int, loot_pct: int, defender_cash: int) -> int:
    """تسویه‌ی یکجای غنیمت = درصد × درآمدِ روزانه × ۱۰ روز، سقف‌خورده با موجودیِ بازنده.

    (در این مرحله غنیمتِ ۱۰روزه به‌صورتِ یکجا تسویه می‌شود تا نیازی به تیکرِ پس‌زمینه نباشد.)
    """
    gross = int(max(0, daily_income) * max(0, loot_pct) / 100) * LOOT_DAYS
    return max(0, min(gross, int(max(0, defender_cash))))


def penalty_amount(attacker_cash: int, penalty_pct: int) -> int:
    """غرامتِ باخت = درصدی از کلِ داراییِ لحظه‌ایِ مهاجم."""
    return max(0, int(max(0, attacker_cash) * max(0, penalty_pct) / 100))


def roll_battle(attacker_power: int, defender_power: int, rng: random.Random | None = None) -> bool:
    """یک نبرد را شبیه‌سازی می‌کند؛ True = بردِ مهاجم."""
    r = rng or random
    return r.random() < win_probability(attacker_power, defender_power)


# --------------------------- تصرفِ شهر (شهرهای فرضی/خنثی) ---------------------------
# این شهرها جدا از سقفِ ۳ شهرِ خریدنی (مرحله ۱۲) شمرده می‌شوند
# و شمارنده‌ی cities_captured را بالا می‌برند (برای القابِ سرزمینی).
NPC_CITIES: dict[str, dict] = {
    "borgo":       {"name": "🏘️ بورگوی کوچک",   "population": 3_000,  "defense": 400,   "reward": 120_000},
    "valdoro":     {"name": "🌾 والدورو",       "population": 5_000,  "defense": 900,   "reward": 220_000},
    "porto_vec":   {"name": "⚓ پورتووکیو",     "population": 8_000,  "defense": 1_600, "reward": 380_000},
    "montecitta":  {"name": "⛰️ مونته‌چیتا",    "population": 12_000, "defense": 2_800, "reward": 600_000},
    "citta_nera":  {"name": "🏙️ چیتانرا",       "population": 18_000, "defense": 4_500, "reward": 950_000},
    "capitale":    {"name": "🟱️ کاپیتاله",      "population": 28_000, "defense": 7_000, "reward": 1_500_000},
}
# 🆕 گسترشِ شهرهای قابلِ تصرف به ۵۰ (۶ شهرِ دستیِ بالا + ۴۴ شهرِ تولیدشده با پیشرفتِ تدریجی)
_EXTRA_NPC_CITIES = [
    ("palermo", "🏙️ پالرمو"), ("napoli", "🏙️ ناپولی"), ("catania", "🏙️ کاتانیا"),
    ("messina", "🏙️ مسینا"), ("siracusa", "🏙️ سیراکوزا"), ("trapani", "🏙️ تراپانی"),
    ("ragusa", "🏙️ راگوزا"), ("enna", "🏙️ انا"), ("agrigento", "🏙️ آگریجنتو"),
    ("caltanissetta", "🏙️ کالتانیستا"), ("marsala", "🏙️ مارسالا"), ("cefalu", "🏙️ چفالو"),
    ("taormina", "🏙️ تائورمینا"), ("gela", "🏙️ جلا"), ("modica", "🏙️ مودیکا"),
    ("noto", "🏙️ نوتو"), ("corleone", "🏙️ کورلئونه"), ("monreale", "🏙️ مونریاله"),
    ("bagheria", "🏙️ باگریا"), ("milazzo", "🏙️ میلاتزو"), ("lipari", "🏙️ لیپاری"),
    ("erice", "🏙️ اریچه"), ("sciacca", "🏙️ شاکا"), ("licata", "🏙️ لیکاتا"),
    ("vittoria", "🏙️ ویتوریا"), ("avola", "🏙️ آوولا"), ("augusta", "🏙️ آگوستا"),
    ("paterno", "🏙️ پاترنو"), ("acireale", "🏙️ آچیریاله"), ("adrano", "🏙️ آدرانو"),
    ("bronte", "🏙️ برونته"), ("randazzo", "🏙️ رانداتزو"), ("nicosia", "🏙️ نیکوزیا"),
    ("piazza", "🏙️ پیاتزا"), ("gangi", "🏙️ گانجی"), ("petralia", "🏙️ پترالیا"),
    ("mistretta", "🏙️ میستره‌تا"), ("troina", "🏙️ تروینا"), ("regalbuto", "🏙️ رگالبوتو"),
    ("leonforte", "🏙️ لئونفورته"), ("calascibetta", "🏙️ کالاشیبتا"), ("villarosa", "🏙️ ویلاروزا"),
    ("barrafranca", "🏙️ بارافرانکا"), ("pietraperzia", "🏙️ پیتراپرتزیا"),
]
for _i, (_k, _nm) in enumerate(_EXTRA_NPC_CITIES):
    NPC_CITIES[_k] = {
        "name": _nm,
        "population": 34_000 + _i * 2_500,
        "defense": 8_500 + _i * 900,
        "reward": 1_700_000 + _i * 220_000,
    }

NPC_CITY_ORDER = list(NPC_CITIES.keys())


def get_npc_city(key: str) -> dict | None:
    return NPC_CITIES.get(key)


def capture_success_chance(attacker_power: int, city_defense: int) -> float:
    """احتمالِ تصرفِ شهرِ فرضی (مانندِ نبرد، اما مدافع = دفاعِ شهر)."""
    return win_probability(attacker_power, city_defense)


def roll_capture(attacker_power: int, city_defense: int, rng: random.Random | None = None) -> bool:
    r = rng or random
    return r.random() < capture_success_chance(attacker_power, city_defense)


# --------------------------- تأسیسِ کشور ---------------------------
COUNTRY_FOUND_MIN_CITIES = 3      # حداقل تعدادِ شهر (خریدنی + تصرفی)
COUNTRY_FOUND_MIN_POP = 500_000     # 🆕 پچ: محدودیتِ تأسیسِ کشور روی جمعیتِ ۳۰۰ هزار تنظیم شد

# رده‌ی کشور بر اساسِ تعدادِ شهر و مجموعِ جمعیت (از بزرگ به کوچک)
# 🆕 مرحله ۲۹: چون حداقلِ جمعیتِ تأسیس روی ۱۰۰ هزار تنظیم شد، آستانه‌های رده‌های
# بالاتر هم متناسب با همان مقیاس (بالاترِ ۱۰۰ هزار) تنظیم شدند تا کشور با همان
# جمعیتِ اولیه مستقیم رده‌ی بالا نگیرد؛ رده فقط با رشدِ جمعیت پس از تأسیس ارتقا می‌یابد.
COUNTRY_TIERS = [
    ("empire", "👑 امپراتوری",   8, 1_000_000),
    ("large",  "🏰 کشورِ بزرگ", 6, 500_000),
    ("medium", "🏙️ کشورِ متوسط", 4, 250_000),
    ("small",  "🚩 کشورِ کوچک", 3, COUNTRY_FOUND_MIN_POP),
]
COUNTRY_TIER_NAME = {k: n for k, n, _c, _p in COUNTRY_TIERS}


def can_found_country(num_cities: int, total_pop: int) -> bool:
    return num_cities >= COUNTRY_FOUND_MIN_CITIES and total_pop >= COUNTRY_FOUND_MIN_POP


def country_tier(num_cities: int, total_pop: int) -> tuple[str, str] | None:
    """بالاترین رده‌ی واجدِ شرایط را (key, name) برمی‌گرداند یا None."""
    for key, name, min_c, min_pop in COUNTRY_TIERS:
        if num_cities >= min_c and total_pop >= min_pop:
            return key, name
    return None


# --------------------------- پیام‌های حالتِ ایمن ---------------------------
SAFE_MESSAGES = [
    "🛡️ این قلمرو زیرِ آتش‌بسِ اجباری است — تا {n} روزِ دیگر دروازه‌ها به روی مهاجمان بسته‌اند.",
    "🕊️ هنوز گَردِ جنگِ قبلی ننشسته؛ {n} روز تا پایانِ مصونیت.",
    "⛓️ حمله ممکن نیست: هدف در دورانِ بازسازی است ({n} روزِ باقی‌مانده).",
]


def safe_mode_message(days_left: int, rng: random.Random | None = None) -> str:
    r = rng or random
    return r.choice(SAFE_MESSAGES).format(n=max(1, int(days_left)))


# --------------------------- هم‌ترازیِ قدرت (منعِ حمله به ضعیف‌ترها) — مرحله ۱۸ ---------------------------
WEAK_TARGET_RATIO = 0.5      # هدف باید حداقل ۵۰٪ قدرتِ مهاجم را داشته باشد
PROTECT_POWER_FLOOR = 300    # زیرِ این قدرت، محدودیتی نیست (محافظت از تازه‌کارها)


def min_target_power(attacker_power: int) -> int:
    """حداقلِ قدرتِ مجاز برای هدف؛ ۰ یعنی بدونِ محدودیت (مهاجمِ تازه‌کار)."""
    if int(attacker_power) <= PROTECT_POWER_FLOOR:
        return 0
    return int(int(attacker_power) * WEAK_TARGET_RATIO)


def attack_allowed(attacker_power: int, target_power: int) -> bool:
    """آیا مهاجم مجاز است به این هدف حمله کند؟ (جلوگیری از زورگیریِ خیلی‌ضعیف‌ترها)."""
    return int(target_power) >= min_target_power(attacker_power)


# --------------------------- جنگِ کشور علیه کشور — مرحله ۱۸ ---------------------------
COUNTRY_TIER_POWER = {"small": 1.0, "medium": 1.5, "large": 2.2, "empire": 3.0}
COUNTRY_WAR_COOLDOWN_HOURS = 12
COUNTRY_WAR_SHIELD_HOURS = 24
COUNTRY_LOOT_PCT_MIN, COUNTRY_LOOT_PCT_MAX = 8, 25
COUNTRY_PENALTY_PCT_MIN, COUNTRY_PENALTY_PCT_MAX = 8, 30


def country_power(tier: str, total_pop: int, owner_power: int) -> int:
    """قدرتِ کشور = (قدرتِ رزمیِ مالک + جمعیت/۱۰) × ضریبِ رده."""
    mult = COUNTRY_TIER_POWER.get(tier, 1.0)
    base = max(0, int(owner_power)) + max(0, int(total_pop)) // 10
    return int(base * mult)


def country_loot_percent(att_power: int, def_power: int) -> int:
    a = max(1, int(att_power))
    d = max(1, int(def_power))
    return _scaled(COUNTRY_LOOT_PCT_MIN, COUNTRY_LOOT_PCT_MAX, (a / (a + d) - 0.5) * 2)


def country_penalty_percent(att_power: int, def_power: int) -> int:
    a = max(1, int(att_power))
    d = max(1, int(def_power))
    return _scaled(COUNTRY_PENALTY_PCT_MIN, COUNTRY_PENALTY_PCT_MAX, (d / (a + d) - 0.5) * 2)


def country_loot_amount(defender_cash: int, pct: int) -> int:
    gross = int(max(0, defender_cash) * max(0, pct) / 100)
    return max(0, min(gross, int(max(0, defender_cash))))


def country_penalty_amount(attacker_cash: int, pct: int) -> int:
    gross = int(max(0, attacker_cash) * max(0, pct) / 100)
    return max(0, min(gross, int(max(0, attacker_cash))))


def roll_country_battle(att_power: int, def_power: int, rng: random.Random | None = None) -> bool:
    """True یعنی کشورِ مهاجم پیروز شد."""
    r = rng or random
    return r.random() < win_probability(att_power, def_power)


# مرحله جدید — تلفات نظامی و سخت‌ترشدن تصرف شهر با گسترش قلمرو
PERSONAL_WIN_ATTACKER_LOSS = 0.03
PERSONAL_WIN_DEFENDER_LOSS = 0.08
PERSONAL_LOSE_ATTACKER_LOSS = 0.09
PERSONAL_LOSE_DEFENDER_LOSS = 0.04
COUNTRY_WIN_ATTACKER_LOSS = 0.04
COUNTRY_WIN_DEFENDER_LOSS = 0.10
COUNTRY_LOSE_ATTACKER_LOSS = 0.12
COUNTRY_LOSE_DEFENDER_LOSS = 0.05
CAPTURE_WIN_ATTACKER_LOSS = 0.05
CAPTURE_LOSE_ATTACKER_LOSS = 0.11
ALLIANCE_WIN_ATTACKER_LOSS = 0.025
ALLIANCE_WIN_DEFENDER_LOSS = 0.055
ALLIANCE_LOSE_ATTACKER_LOSS = 0.07
ALLIANCE_LOSE_DEFENDER_LOSS = 0.03
CITY_DEFENSE_PER_CAPTURED_CITY = 0.18
CITY_REWARD_COST_PER_CAPTURED_CITY = 0.12


def scaled_city_defense(base_defense: int, owned_city_count: int) -> int:
    owned = max(0, int(owned_city_count or 0))
    return int(max(1, int(base_defense)) * (1.0 + CITY_DEFENSE_PER_CAPTURED_CITY * owned))


def scaled_city_reward(base_reward: int, owned_city_count: int) -> int:
    owned = max(0, int(owned_city_count or 0))
    return int(max(0, int(base_reward)) * (1.0 + CITY_REWARD_COST_PER_CAPTURED_CITY * owned))


# =====================================================================
# 🆕 تلفاتِ منطقیِ نبرد — وابسته به نسبتِ قدرتِ خود/حریف (نه درصدِ ثابتِ ارتش)
# =====================================================================
# فلسفه‌ی فرمول:
#   • تلفات نباید «درصدِ ثابتی از کلِ ارتش» باشد؛ چون با ارتشِ میلیونی حتی ۵٪
#     می‌شود ۱۰۰٬۰۰۰ کشته که بازسازی‌اش کمرشکن است.
#   • تلفات باید به «مقاومتِ واقعیِ حریف» و «نسبتِ قدرتِ دو طرف» گره بخورد:
#       - هرچه از حریف قوی‌تر باشی → تلفاتت به‌شدت کمتر.
#       - هرچه نبرد نزدیک‌تر/سخت‌تر باشد → تلفاتِ بیشتر.
#   • یک «سقفِ مطلق» بر پایه‌ی قدرتِ خودِ حریف هست؛ یعنی زدنِ شهرِ ۱۰۰۰قدرتی
#     نمی‌تواند بیشتر از ~۱۰۰۰ نیرو ازت بگیرد، هرچقدر هم ارتشت بزرگ باشد.
#   • یک «سقفِ کسری» هم هست تا هیچ نبردی یک‌باره بخشِ بزرگی از ارتشت را نبَرد.

LOSS_ENEMY_POWER_CAP = 1.0        # سقفِ تلفاتِ برنده ≈ قدرتِ حریف × این ضریب (برحسبِ تعدادِ نیرو)
LOSS_LOSER_CAP_BONUS = 1.5        # بازنده می‌تواند تا این ضریبِ بیشتر از سقفِ حریف تلفات بدهد
LOSS_MAX_ARMY_FRACTION = 0.12     # سقف مسیر combat_losses (زنده از battle_live با سخت‌کپ ۲۵٪)
LOSS_PRESSURE_EXPONENT = 1.35     # هرچه بزرگ‌تر، افتِ تلفات هنگامِ برتریِ قدرت تندتر است
LOSS_LOSER_MULT = 2.2             # بازنده‌ی نبرد تلفاتِ بیشتری می‌دهد

# ضریبِ پایه‌ی «شدتِ تلفات» برای هر نقش/نوعِ نبرد (سهمِ حالتِ برد؛ باخت با LOSS_LOSER_MULT بزرگ‌تر می‌شود)
CASUALTY_INTENSITY = {
    "personal_attacker": 0.90,
    "personal_defender": 0.70,
    "capture_attacker":  0.80,
    "country_attacker":  1.00,
    "country_defender":  0.80,
    "alliance_attacker": 0.60,
    "alliance_defender": 0.50,
}


def loss_pressure(own_power: int, enemy_power: int) -> float:
    """«فشارِ نبرد» در بازه‌ی ~۰..۱ = سهمِ قدرتِ حریف از کلِ نبرد، با توان.

    نزدیکِ ۱ یعنی حریف هم‌قدرت/قوی‌تر (نبردِ سخت، تلفاتِ زیاد)،
    نزدیکِ ۰ یعنی حریف بسیار ضعیف‌تر (تلفاتِ ناچیز).
    """
    a = max(1, int(own_power))
    d = max(1, int(enemy_power))
    ratio = d / (a + d)              # سهمِ قدرتِ حریف (۰..۱)
    return ratio ** LOSS_PRESSURE_EXPONENT


# 🆕 کیفیتِ ارتش: میانگینِ سطحِ ارتقا تلفات را کم می‌کند (ارتشِ فوق‌تخصص کمتر تلفات می‌دهد)
QUALITY_MITIGATION_PER_LEVEL = 0.04   # هر ۱ سطحِ میانگین: ۴٪ تلفاتِ کمتر
QUALITY_MITIGATION_MAX = 0.40          # سقفِ کاهش: ۴۰٪ (در میانگینِ سطحِ ۱۰)


def quality_mitigation(avg_level: float) -> float:
    """ضریبِ کاهشِ تلفات بر اساسِ میانگینِ سطحِ ارتقایِ ارتش (۱.۰ = بدونِ کاهش)."""
    lv = max(0.0, float(avg_level))
    reduction = min(QUALITY_MITIGATION_MAX, QUALITY_MITIGATION_PER_LEVEL * lv)
    return 1.0 - reduction


def combat_losses(
    troop_count: int,
    own_power: int,
    enemy_power: int,
    *,
    won: bool,
    base_intensity: float,
) -> int:
    """تعدادِ نیرویی که در یک نبرد از دست می‌رود (خروجی: عددِ صحیحِ ۰..troop_count).

    وابسته به:
      • troop_count : تعدادِ کلِ نیروی خودت (تلفات نسبتِ به این عدد سنجیده و بعد سقف می‌خورد)
      • own_power   : قدرتِ نظامیِ خودت
      • enemy_power : قدرتِ حریف (بازیکن، کشور، اتحادیه یا دفاعِ شهر)
      • won         : برنده‌ی نبرد بودی یا نه (بازنده تلفاتِ بیشتری می‌دهد)
      • base_intensity : شدتِ پایه‌ی نوعِ نبرد (از CASUALTY_INTENSITY)

    منطق:
      losses ≈ troop_count × intensity × pressure   (سقف‌خورده با کسرِ ارتش)
      سپس min با سقفِ مطلقِ وابسته به قدرتِ حریف.
    """
    troops = max(0, int(troop_count))
    if troops <= 0:
        return 0

    pressure = loss_pressure(own_power, enemy_power)
    intensity = max(0.0, float(base_intensity))
    if not won:
        intensity *= LOSS_LOSER_MULT

    # کسرِ تلفات از کلِ ارتش (با سقفِ کسری تا حجمِ زیاد یک‌باره از بین نرود)
    frac = min(LOSS_MAX_ARMY_FRACTION, intensity * pressure)
    losses = int(round(troops * frac))

    # سقفِ مطلق بر پایه‌ی قدرتِ واقعیِ حریف
    d = max(1, int(enemy_power))
    hard_cap = int(d * LOSS_ENEMY_POWER_CAP)
    if not won:
        hard_cap = int(hard_cap * LOSS_LOSER_CAP_BONUS) + 1
    losses = min(losses, hard_cap)

    # اگر حریف کاملاً بی‌قدرت بود، ممکن است تلفات صفر شود — همان درست است.
    return max(0, min(troops, losses))
