# -*- coding: utf-8 -*-
"""🆕 بچ ۴ — داده و فرمولِ شهرسازِ جدید (جایگزینِ سیستمِ شهر/کشورِ قدیمی).

مشخصات (طبقِ سندِ طراحی):

v1.7.7:
  • هزینه ساخت ×۵۰ | قیمت منابع ×۵۰ | درآمد لول‌دار ÷۴ | سقف لول ×۲
  • درآمد اصلی = مالیات/جمعیت | رشد سالانه sat≥75 + ظرفیت
  • فروش منابع شهر = ۵۰٪ قیمت خرید

  • هر بازیکن دقیقاً یک شهر دارد (تک‌شهری).
  • خریدِ شهر: ۲۵۰ میلیون دلار ، پیش‌نیازِ لول ۳۹.
  • سقفِ جمعیت: ۲۵ میلیون نفر.
  • مالیات ۰..۳۰٪ (خنثی: ۱۵٪) ، رضایت ۵۰..۱۰۰.
  • انبارِ شهر: ۴۰ سطح، ظرفیت ۲۰k→۱۰۰k واحدِ مصالح.
  • هر ۳ روزِ واقعی = ۱ سالِ بازی (رشدِ جمعیت).
  • تبدیلِ ۵→۱: ۵ واحدِ مسکن از یک رده = ۱ واحدِ رده‌ی بالاتر.
"""
from __future__ import annotations

import math
from datetime import datetime

# ---------------------------------------------------------------------------
# ثابت‌های کلی
# ---------------------------------------------------------------------------
CITY_COST = 250_000_000            # هزینه‌ی خریدِ شهر
CITY_MIN_LEVEL = 39                # پیش‌نیازِ لولِ بازیکن
POP_CAP = 25_000_000               # سقفِ جمعیتِ شهر
# Free capacity offset retained only for compatibility with housing formulas.
BASE_POPULATION = 0
# City population is independent from the 4^N professional-subordinate economy.
STARTING_POPULATION = 100
LEGACY_STARTER_HOUSE_DIVISOR = 4
BATCH_BUILD_MIN = 1
BATCH_BUILD_MAX = 10_000
BATCH_BUILD_PRESETS = (1, 5, 10, 25, 50, 100, 500, 1_000)

# v1.7.6.5 -- Baseline capacity granted per service category when the city
# owns none of that building yet. Without this, min() over the service caps
# collapsed to 0 for any city lacking (for example) an amusement park, which
# pinned supported_population() to base_population and froze growth forever.
SERVICE_BASELINE = 5_000

# Satisfaction the city must reach before its population grows at year end.
GROWTH_MIN_SATISFACTION = 75

TAX_MIN, TAX_MAX, TAX_NEUTRAL = 0, 30, 15
TAX_OPTIONS = (0, 5, 10, 15, 20, 25, 30)
TAX_PER_CAPITA_HOUR = 12.0  # v1.7.7 مالیات‌محور
CITY_HOURLY_INCOME_CAP = 80_000_000  # v1.7.7          # درآمدِ پایه به‌ازای هر نفر/ساعت در مالیاتِ ۱۰۰٪

SAT_MIN, SAT_MAX = 0, 100
SAT_BASE = 60                      # پایه‌ی رضایت
MAX_OFFLINE_HOURS = 24             # سقفِ انباشتِ درآمد/تولیدِ آفلاین

GAME_YEAR_REAL_DAYS = 3            # هر ۳ روزِ واقعی = ۱ سالِ بازی
MAX_GAME_YEARS = 60

# ---------------------------------------------------------------------------
# منابع متنوعِ ساخت‌وساز؛ همه در انبار شهر نگهداری می‌شوند.
# ---------------------------------------------------------------------------
MATERIAL = "materials"  # کلید قدیمی، فقط برای سازگاری نسخه‌های قبلی
MATERIAL_LABEL = "🧱 مصالح"
RESOURCES: dict[str, dict] = {
    "wood": {"name": "🪵 چوب", "price": 12000},
    "stone": {"name": "🪨 سنگ", "price": 10000},
    "steel": {"name": "🔩 فولاد", "price": 45000},
    "cement": {"name": "🧱 سیمان", "price": 28000},
    "oil": {"name": "🛢 نفت", "price": 35000},
    "gas": {"name": "🔥 گاز", "price": 30000},
    "bitumen": {"name": "🛣️ قیر", "price": 42000},
    "plastic": {"name": "🧪 پلاستیک", "price": 32000},
    "glass": {"name": "🪟 شیشه", "price": 38000},
}
RESOURCE_ORDER = tuple(RESOURCES)

# v1.7.7 — فروش منابع شهر = نصف قیمت خرید لحظه‌ای
RESOURCE_SELL_RATE = 0.50

def resource_sell_price(key: str) -> int:
    """قیمت فروش هر واحد = ۵۰٪ قیمت خرید."""
    return max(1, int(resource_price(key) * RESOURCE_SELL_RATE))


def resource_name(key: str) -> str:
    return RESOURCES.get(key, {}).get("name", key)

def resource_price(key: str) -> int:
    """قیمت خرید منبع = پایه × ضریب ادمین × نوسان روزانه."""
    from datetime import datetime
    base = int(RESOURCES.get(key, {}).get("price", 0))
    base = int(round(base * get_resource_price_mult()))
    day = datetime.utcnow().timetuple().tm_yday
    wave = ((hash(f"{key}:{day}") % 31) - 15) / 100
    return max(1, int(round(base * (1 + wave))))

def resource_total(resources: dict | None) -> int:
    return sum(max(0, int((resources or {}).get(k, 0) or 0)) for k in RESOURCE_ORDER)

def resource_text(resources: dict | None, compact: bool = False) -> str:
    resources = resources or {}
    sep = " | " if compact else "\n"
    return sep.join(f"{resource_name(k)}: {int(resources.get(k, 0) or 0):,}" for k in RESOURCE_ORDER)

# سهم هر ماده در مصرف پایه‌ی یک ساختمان. مقدار پایه همچنان از فیلد mat خوانده می‌شود.
RESOURCE_RECIPES = {
    "small_house": {"wood": .50, "stone": .30, "cement": .20},
    "apartment": {"steel": .25, "cement": .35, "stone": .25, "glass": .15},
    "tower": {"steel": .35, "cement": .30, "glass": .20, "stone": .15},
    "skyscraper": {"steel": .35, "cement": .25, "glass": .25, "plastic": .15},
    "power": {"steel": .35, "cement": .30, "oil": .20, "stone": .15},
    "water": {"steel": .25, "cement": .40, "plastic": .20, "stone": .15},
    "road": {"stone": .30, "cement": .30, "bitumen": .25, "steel": .15},
    "hospital": {"cement": .30, "steel": .25, "glass": .20, "plastic": .25},
    "school": {"wood": .20, "cement": .35, "steel": .20, "glass": .25},
    "bank": {"steel": .35, "cement": .25, "glass": .25, "stone": .15},
    "bourse": {"steel": .30, "glass": .30, "cement": .25, "plastic": .15},
    "grand_market": {"steel": .25, "cement": .25, "glass": .20, "plastic": .15, "wood": .15},
    "park": {"wood": .50, "stone": .35, "cement": .15},
    "amusement": {"steel": .30, "plastic": .30, "cement": .20, "glass": .20},
}

def material_requirements(btype: str, multiplier: int = 1) -> dict[str, int]:
    base = max(0, int(material_cost(btype)) * max(1, int(multiplier)))
    recipe = RESOURCE_RECIPES.get(btype, {"stone": .4, "cement": .3, "steel": .3})
    out, used = {}, 0
    items = list(recipe.items())
    for key, ratio in items[:-1]:
        amount = int(round(base * ratio)); out[key] = amount; used += amount
    if items:
        out[items[-1][0]] = max(0, base - used)
    return {k: v for k, v in out.items() if v > 0}

def requirements_text(req: dict[str, int]) -> str:
    return " + ".join(f"{v:,} {resource_name(k)}" for k, v in req.items()) or "بدون مصالح"

def resource_production_per_hour(counts: dict[str, int] | None) -> dict[str, int]:
    counts = counts or {}
    out = {k: 0 for k in RESOURCE_ORDER}
    for key, info in INDUSTRY.items():
        product = info.get("produce_resource")
        if product:
            out[product] += int(counts.get(key, 0)) * max(0, int(int(info.get("produce_mat", 0) or 0) / get_income_div()))
    return out
# منابعِ زیرساختی (مصرفِ سرانه‌ی جمعیت؛ کسری = افتِ رضایت)
UTILITIES = ("electricity", "water")
UTILITY_LABEL = {"electricity": "⚡ برق", "water": "💧 آب"}
UTILITY_PER_CAPITA = 1 / 20_000    # ۱ واحد به‌ازای هر ۲۰هزار نفر

# ---------------------------------------------------------------------------
# انبارِ شهر — ۴۰ سطح، ظرفیت ۲۰k→۱۰۰k
# ---------------------------------------------------------------------------
WAREHOUSE_MAX_LEVEL = 80  # v1.7.7 ×2
WAREHOUSE_CAP_MIN = 20_000
WAREHOUSE_CAP_MAX = 100_000
WAREHOUSE_COST_L1_BASE = 50_000_000  # پایه؛ ضریب هزینه ادمین اعمال می‌شود
WAREHOUSE_COST_FINAL_BASE = 1_000_000_000_000_000  # پایه
# سازگاری نام‌های قدیمی
WAREHOUSE_COST_L1 = WAREHOUSE_COST_L1_BASE
WAREHOUSE_COST_FINAL = WAREHOUSE_COST_FINAL_BASE


def warehouse_capacity(level: int) -> int:
    """ظرفیتِ انبار در سطحِ داده‌شده (خطی ۲۰k تا ۱۰۰k)."""
    lvl = max(1, min(WAREHOUSE_MAX_LEVEL, int(level or 1)))
    step = (WAREHOUSE_CAP_MAX - WAREHOUSE_CAP_MIN) / (WAREHOUSE_MAX_LEVEL - 1)
    return int(round(WAREHOUSE_CAP_MIN + step * (lvl - 1)))


def warehouse_upgrade_cost(level: int) -> int:
    """هزینه ارتقا انبار — پایه × ضریب هزینه ادمین."""
    cur = max(1, int(level or 1))
    if cur >= WAREHOUSE_MAX_LEVEL:
        return 0
    l1 = float(WAREHOUSE_COST_L1_BASE) * get_cost_mult()
    final = float(WAREHOUSE_COST_FINAL_BASE) * get_cost_mult()
    ratio = (final / l1) ** (1.0 / (WAREHOUSE_MAX_LEVEL - 1))
    return int(l1 * (ratio ** (cur - 1)))


# ---------------------------------------------------------------------------
# ۱) مسکونی (ظرفیتِ جمعیت) — تبدیلِ ۵→۱
# ---------------------------------------------------------------------------
# residents: ظرفیتِ سکونت پر واحد | cost: هزینه‌ی نقدی | mat: مصالحِ لازم
HOUSING: dict[str, dict] = {
    "small_house": {"name": "🏠 خانه‌ی کوچک", "residents": 5,   "cost": 1_000_000,   "mat": 50,  "next": "apartment"},
    "apartment":  {"name": "🏢 آپارتمان",     "residents": 30,  "cost": 8_000_000,   "mat": 90,  "next": "tower"},
    "tower":      {"name": "🏬 برجِ مسکونی", "residents": 120, "cost": 45_000_000,  "mat": 120, "next": "skyscraper"},
    "skyscraper": {"name": "🏙️ آسمان‌خراش",  "residents": 250, "cost": 250_000_000, "mat": 150, "next": None},
}
HOUSING_ORDER = ("small_house", "apartment", "tower", "skyscraper")
CONVERT_RATIO = 3                  # ۵ واحدِ یک رده → ۱ واحدِ رده‌ی بالاتر


# ---------------------------------------------------------------------------
# ۲) زیرساخت (هزینه‌ی ساخت = نقد + ۵۰..۱۵۰ واحدِ مصالح)
# ---------------------------------------------------------------------------
# sat: امتیازِ رضایت پر سطح | util/produce: تولیدِ زیرساختی
# mat: مصالحِ لازم برای هر سطح | max_level: سقفِ سطح
INFRA: dict[str, dict] = {
    "power":    {"name": "⚡ نیروگاهِ برق", "cost": 20_000_000, "mat": 120, "util": "electricity", "produce": 400, "max_level": 20, "requires": ("road",)},
    "water":    {"name": "💧 تصفیه‌ی آب",  "cost": 18_000_000, "mat": 110, "util": "water",       "produce": 400, "max_level": 20, "requires": ("road", "power")},
    "road":     {"name": "🛣️ شبکه‌ی حمل‌ونقل", "cost": 12_000_000, "mat": 80, "sat": 1, "max_level": 15},
    "hospital": {"name": "🏥 بیمارستان",   "cost": 75_000_000, "mat": 140, "sat": 4, "service_capacity": 250_000, "requires": ("road", "water", "power", "steel_mill")},
    "school":   {"name": "🏫 مدرسه/دانشگاه", "cost": 14_000_000, "mat": 90, "sat": 1, "prod_reduce": 0.05, "max_level": 15, "requires": ("road", "power")},
}
INFRA_ORDER = ("power", "water", "road", "hospital", "school")


# ---------------------------------------------------------------------------
# ۳) رفاهی/تجاری — سقفِ تعداد بر اساسِ جمعیت
# ---------------------------------------------------------------------------
# ratio_pop: یک واحد به‌ازای هر N نفر | max_abs: سقفِ مطلق | income: درآمدِ ساعتیِ هر واحد
WELFARE: dict[str, dict] = {
    "bank":         {"name": "🏦 بانک",          "cost": 60_000_000, "mat": 130, "ratio_pop": 125_000, "income": 220_000, "sat": 1, "requires": ("road", "power")},
    "bourse":       {"name": "📈 بورس",          "cost": 90_000_000, "mat": 150, "max_abs": 10, "income": 380_000, "requires": ("bank", "power")},
    "grand_market": {"name": "🏬 بازارِ بزرگ",   "cost": 70_000_000, "mat": 140, "max_abs": 5,  "income": 300_000, "sat": 1, "requires": ("road", "power")},
    "park":         {"name": "🌳 پارک",          "cost": 8_000_000,  "mat": 60,  "ratio_pop": 20_000, "income": 0, "sat": 3},
    "amusement":    {"name": "🎡 شهربازی",       "cost": 40_000_000, "mat": 120, "ratio_pop": 20_000, "income": 90_000, "sat": 2, "requires": ("park", "power", "road")},
}
WELFARE_ORDER = ("bank", "bourse", "grand_market", "park", "amusement")


# ---------------------------------------------------------------------------
# ۴) صنعت — تولیدِ مصالح (ذخیره در انبار)
# ---------------------------------------------------------------------------
# produce_mat: مصالحِ تولیدی در ساعت پر سطح
INDUSTRY: dict[str, dict] = {
    "factory":   {"name": "🏭 چوب‌بری", "cost": 25_000_000, "mat": 80, "produce_mat": 60, "produce_resource": "wood", "max_level": 20, "requires": ("road",)},
    "quarry":    {"name": "⛏️ معدن سنگ", "cost": 32_000_000, "mat": 100, "produce_mat": 80, "produce_resource": "stone", "max_level": 20, "requires": ("road",)},
    "cement":    {"name": "🏗️ کارخانه‌ی سیمان", "cost": 40_000_000, "mat": 110, "produce_mat": 110, "produce_resource": "cement", "max_level": 20, "requires": ("quarry", "power")},
    "steel_mill": {"name": "🏭 فولادسازی", "cost": 65_000_000, "mat": 140, "produce_mat": 70, "produce_resource": "steel", "max_level": 20, "requires": ("power", "road")},
    "refinery":  {"name": "🛢 پالایشگاه", "cost": 80_000_000, "mat": 150, "produce_mat": 65, "produce_resource": "oil", "max_level": 20, "requires": ("power", "road")},
    "plastic":   {"name": "🧪 پتروشیمی", "cost": 95_000_000, "mat": 160, "produce_mat": 60, "produce_resource": "plastic", "max_level": 20, "requires": ("refinery", "power")},
    "glassworks": {"name": "🪟 شیشه‌سازی", "cost": 70_000_000, "mat": 140, "produce_mat": 55, "produce_resource": "glass", "max_level": 20, "requires": ("quarry", "power")},
}
INDUSTRY_ORDER = ("factory", "quarry", "cement", "steel_mill", "refinery", "plastic", "glassworks", "petrochemical", "vehicle", "furniture", "electronics")

# بازطراحیِ کاملِ شهر: همه‌ی سازه‌ها واحدی‌اند؛ هر واحد ظرفیت/تولید مستقل دارد.
# مقادیر ثابت‌اند و تنها قیمت مواد اولیه در بازار شهر نوسان دارد.
INFRA.update({
    "solar_power": {"name": "☀️ نیروگاه خورشیدی", "cost": 32_000_000, "mat": 120, "util": "electricity", "produce": 250, "requires": ("road",)},
    "fossil_power": {"name": "🔥 نیروگاه فسیلی", "cost": 45_000_000, "mat": 150, "util": "electricity", "produce": 700, "requires": ("road", "refinery")},
    "desalination": {"name": "🌊 آب‌شیرین‌کن", "cost": 35_000_000, "mat": 140, "util": "water", "produce": 650, "requires": ("power", "road")},
    "university": {"name": "🎓 دانشگاه", "cost": 80_000_000, "mat": 140, "sat": 3, "requires": ("school", "power")},
    "clinic": {"name": "🩺 کلینیک", "cost": 22_000_000, "mat": 100, "sat": 1, "service_capacity": 50_000, "requires": ("road", "water")},
    "gas_station": {"name": "⛽ پمپ بنزین", "cost": 18_000_000, "mat": 80, "sat": 1, "requires": ("road", "petrochemical")},
    "bridge": {"name": "🌉 پل ترافیکی", "cost": 65_000_000, "mat": 150, "sat": 2, "requires": ("road", "steel_mill")},
    "metro": {"name": "🚇 مترو", "cost": 180_000_000, "mat": 150, "sat": 4, "requires": ("power", "steel_mill")},
    "brt": {"name": "🚌 اتوبوس تندرو", "cost": 45_000_000, "mat": 110, "sat": 2, "requires": ("road", "vehicle")},
    "farm": {"name": "🌾 زمین کشاورزی", "cost": 12_000_000, "mat": 60, "produce_food": 100, "requires": ("water",)},
    "ranch": {"name": "🐄 دامداری", "cost": 20_000_000, "mat": 90, "produce_food": 130, "requires": ("water", "farm")},
    "slaughterhouse": {"name": "🥩 کشتارگاه", "cost": 35_000_000, "mat": 120, "produce_food": 200, "requires": ("ranch", "power")},
    "garden": {"name": "🍎 باغ", "cost": 15_000_000, "mat": 70, "produce_food": 80, "requires": ("water",)},
    "police": {"name": "👮 ایستگاه پلیس", "cost": 30_000_000, "mat": 100, "sat": 2, "requires": ("road", "power")},
    "fire": {"name": "🚒 آتش‌نشانی", "cost": 28_000_000, "mat": 100, "sat": 2, "requires": ("road", "water")},
})
INFRA_ORDER = tuple(INFRA)
WELFARE.update({
    "shop": {"name": "🏪 مغازه کوچک", "cost": 10_000_000, "mat": 70, "income": 45_000, "sat": 1, "requires": ("road", "farm") , "next": "food_store"},
    "food_store": {"name": "🍞 فروشگاه مواد غذایی", "cost": 25_000_000, "mat": 90, "income": 100_000, "sat": 2, "requires": ("shop", "slaughterhouse"), "next": "bazaar"},
    "home_store": {"name": "🛋️ فروشگاه لوازم خانگی", "cost": 40_000_000, "mat": 110, "income": 145_000, "sat": 2, "requires": ("furniture", "road")},
    "electronics_store": {"name": "📺 فروشگاه الکترونیک", "cost": 55_000_000, "mat": 120, "income": 190_000, "sat": 2, "requires": ("electronics", "road")},
    "bazaar": {"name": "🛒 بازارچه", "cost": 80_000_000, "mat": 140, "income": 350_000, "sat": 2, "requires": ("food_store", "power"), "next": "market"},
    "market": {"name": "🏬 بازار", "cost": 180_000_000, "mat": 150, "income": 750_000, "sat": 3, "requires": ("bazaar", "power"), "next": "mall"},
    "mall": {"name": "🏢 مال تجاری", "cost": 450_000_000, "mat": 150, "income": 1_800_000, "sat": 4, "requires": ("market", "metro")},
    "cinema": {"name": "🎬 سینما", "cost": 38_000_000, "mat": 100, "sat": 2, "requires": ("power", "road")},
    "restaurant": {"name": "🍽️ رستوران", "cost": 30_000_000, "mat": 90, "sat": 2, "requires": ("food_store", "power")},
    "cafe": {"name": "☕ کافه", "cost": 15_000_000, "mat": 70, "sat": 1, "requires": ("road",)},
    "bar": {"name": "🍸 بار", "cost": 35_000_000, "mat": 100, "sat": 2, "requires": ("road", "power")},
    "casino": {"name": "🎰 کازینو", "cost": 150_000_000, "mat": 150, "sat": 3, "requires": ("bank", "power")},
    "aquarium": {"name": "🐠 آکواریوم", "cost": 120_000_000, "mat": 140, "sat": 3, "requires": ("water", "power")},
    "pool": {"name": "🏊 استخر", "cost": 65_000_000, "mat": 120, "sat": 2, "requires": ("water", "power")},
    "library": {"name": "📚 کتابخانه", "cost": 35_000_000, "mat": 90, "sat": 2, "requires": ("school",)},
    "hall": {"name": "🏛️ سالن اجتماعات", "cost": 70_000_000, "mat": 120, "sat": 2, "requires": ("road", "power")},
    "amphitheater": {"name": "🎭 آمفی‌تئاتر", "cost": 100_000_000, "mat": 140, "sat": 3, "requires": ("hall", "power")},
})
WELFARE_ORDER = tuple(WELFARE)
INDUSTRY.update({
    "petrochemical": {"name": "🧪 پتروشیمی", "cost": 150_000_000, "mat": 150, "produce_mat": 120, "produce_resource": "plastic", "requires": ("refinery", "power")},
    "vehicle": {"name": "🚗 ماشین و موتورسازی", "cost": 180_000_000, "mat": 150, "produce_mat": 80, "produce_resource": "steel", "requires": ("steel_mill", "power", "water")},
    "furniture": {"name": "🛋️ مبلمان", "cost": 95_000_000, "mat": 130, "produce_mat": 90, "produce_resource": "wood", "requires": ("factory", "plastic", "power")},
    "electronics": {"name": "💻 لوازم خانگی و الکترونیکی", "cost": 220_000_000, "mat": 150, "produce_mat": 75, "produce_resource": "glass", "requires": ("steel_mill", "petrochemical", "power")},
})
# خانه‌ها مطابق مشخصات جدید
# v1.7.8.4 — مسکونی ۶ طبقه؛ هر ردهٔ بالاتر کمی گران‌تر (قیمت/نفر صعودی)
# تبدیل ۳به۱: ۳ واحد ردهٔ پایین ≈ ۱ واحد ردهٔ بالا (ظرفیت برابر، خرید مستقیم کمی گران‌تر)
HOUSING.update({
    "small_house": {"name": "🏠 خانه کوچک", "residents": 6, "cost": 3_000_000, "mat": 50, "next": "medium_house", "requires": ("road", "power", "water")},
    "medium_house": {"name": "🏡 خانه متوسط", "residents": 18, "cost": 9_600_000, "mat": 70, "next": "big_house", "requires": ("road", "power", "water")},
    "big_house": {"name": "🏘️ خانه بزرگ", "residents": 55, "cost": 31_000_000, "mat": 100, "next": "apartment", "requires": ("road", "power", "water")},
    "apartment": {"name": "🏢 آپارتمان", "residents": 170, "cost": 100_000_000, "mat": 130, "next": "large_apartment", "requires": ("road", "power", "water", "steel_mill")},
    "large_apartment": {"name": "🏬 آپارتمان بزرگ", "residents": 520, "cost": 325_000_000, "mat": 150, "next": "skyscraper", "requires": ("road", "power", "water", "steel_mill", "glassworks")},
    "skyscraper": {"name": "🏙️ آسمان‌خراش", "residents": 1600, "cost": 1_050_000_000, "mat": 180, "next": None, "requires": ("road", "power", "water", "steel_mill", "glassworks")},
})
# ترتیبِ صریح — کلید قدیمی tower فقط برای سازگاری داده‌های قبلی می‌ماند و در منو نیست
HOUSING_ORDER = ("small_house", "medium_house", "big_house", "apartment", "large_apartment", "skyscraper")



# دسته‌بندیِ کلی برای منو
CATEGORIES = {
    "housing":  {"name": "🏘️ مسکونی",  "table": HOUSING,  "order": HOUSING_ORDER},
    "infra":    {"name": "🛠️ زیرساخت", "table": INFRA,    "order": INFRA_ORDER},
    "welfare":  {"name": "🎪 رفاه/تجارت", "table": WELFARE, "order": WELFARE_ORDER},
    "industry": {"name": "🏭 صنعت",    "table": INDUSTRY, "order": INDUSTRY_ORDER},
}
CATEGORY_ORDER = ("housing", "infra", "welfare", "industry")



# ---------------------------------------------------------------------------
# v1.7.7.5 — ضریب‌های اقتصاد شهر (قابل تنظیم از ادمین‌مود)
# جداول ساختمان = مقادیر پایه؛ ضریب‌ها در accessorها اعمال می‌شوند.
# ---------------------------------------------------------------------------
CITY_COST_MULT_KEY = "city.cost_mult"
CITY_INCOME_DIV_KEY = "city.income_div"
CITY_RESOURCE_PRICE_MULT_KEY = "city.resource_price_mult"
CITY_LEVEL_MULT_KEY = "city.level_mult"

# پیش‌فرض‌ها (آخرین خواسته کاربر)
DEFAULT_COST_MULT = 25
DEFAULT_INCOME_DIV = 2
DEFAULT_RESOURCE_PRICE_MULT = 50
DEFAULT_LEVEL_MULT = 2

# کش runtime — با refresh_city_balance_settings از DB به‌روز می‌شود
_runtime_cost_mult = DEFAULT_COST_MULT
_runtime_income_div = DEFAULT_INCOME_DIV
_runtime_resource_price_mult = DEFAULT_RESOURCE_PRICE_MULT
_runtime_level_mult = DEFAULT_LEVEL_MULT
_levels_scaled = False  # max_level فقط یک‌بار × level_mult روی جداول


def get_cost_mult() -> float:
    return float(_runtime_cost_mult or DEFAULT_COST_MULT)


def get_income_div() -> float:
    d = float(_runtime_income_div or DEFAULT_INCOME_DIV)
    return d if d > 0 else 1.0


def get_resource_price_mult() -> float:
    return float(_runtime_resource_price_mult or DEFAULT_RESOURCE_PRICE_MULT)


def get_level_mult() -> float:
    return float(_runtime_level_mult or DEFAULT_LEVEL_MULT)


def set_runtime_balance(
    cost_mult: float | None = None,
    income_div: float | None = None,
    resource_price_mult: float | None = None,
    level_mult: float | None = None,
) -> None:
    global _runtime_cost_mult, _runtime_income_div, _runtime_resource_price_mult, _runtime_level_mult
    if cost_mult is not None:
        _runtime_cost_mult = max(0.01, float(cost_mult))
    if income_div is not None:
        _runtime_income_div = max(0.01, float(income_div))
    if resource_price_mult is not None:
        _runtime_resource_price_mult = max(0.01, float(resource_price_mult))
    if level_mult is not None:
        _runtime_level_mult = max(1.0, float(level_mult))


def balance_snapshot() -> dict:
    return {
        "cost_mult": get_cost_mult(),
        "income_div": get_income_div(),
        "resource_price_mult": get_resource_price_mult(),
        "level_mult": get_level_mult(),
    }


def _scale_max_levels_once() -> None:
    """سقف لول پایه را × level_mult پیش‌فرض یک‌بار در import مقیاس می‌دهد."""
    global _levels_scaled
    if _levels_scaled:
        return
    lm = int(DEFAULT_LEVEL_MULT)
    if lm <= 1:
        _levels_scaled = True
        return
    for table in (HOUSING, INFRA, WELFARE, INDUSTRY):
        for _k, b in table.items():
            if isinstance(b, dict) and b.get("max_level") is not None:
                try:
                    ml = int(b["max_level"])
                    if ml > 1:
                        b["max_level"] = int(ml * lm)
                except Exception:
                    pass
    _levels_scaled = True


_scale_max_levels_once()




def get_building(btype: str) -> dict | None:
    for cat in CATEGORIES.values():
        if btype in cat["table"]:
            return cat["table"][btype]
    return None


def category_of(btype: str) -> str | None:
    for ckey, cat in CATEGORIES.items():
        if btype in cat["table"]:
            return ckey
    return None


def building_name(btype: str) -> str:
    b = get_building(btype)
    return b["name"] if b else btype


def normalize_build_amount(value) -> int | None:
    """Return a safe integer batch amount; reject booleans, fractions and bounds."""
    if isinstance(value, bool):
        return None
    try:
        text = str(value).strip().replace(",", "").replace("٬", "")
        amount = int(text)
    except (TypeError, ValueError):
        return None
    return amount if BATCH_BUILD_MIN <= amount <= BATCH_BUILD_MAX else None


def starting_house_count() -> int:
    residents = max(1, int(HOUSING["small_house"]["residents"]))
    return int(math.ceil(STARTING_POPULATION / residents))


def legacy_starter_house_count(old_base_population: int) -> int:
    old = max(0, int(old_base_population or 0))
    return max(1, int(math.ceil(old / LEGACY_STARTER_HOUSE_DIVISOR)))


def normalize_population_seed(base_population: int, population: int) -> tuple[int, int, bool]:
    """Remove phantom 4^N starter population while preserving earned growth."""
    old_base = max(0, int(base_population or 0))
    old_population = max(0, int(population or 0))
    if old_base == STARTING_POPULATION:
        new_population = max(STARTING_POPULATION, min(POP_CAP, old_population or STARTING_POPULATION))
        return STARTING_POPULATION, new_population, new_population != old_population
    if old_base <= 0:
        new_population = max(STARTING_POPULATION, min(POP_CAP, old_population or STARTING_POPULATION))
        return STARTING_POPULATION, new_population, True
    earned_growth = max(0, old_population - old_base)
    return STARTING_POPULATION, min(POP_CAP, STARTING_POPULATION + earned_growth), True


def batch_build_quote(btype: str, amount) -> dict:
    """Dependency-free quote using identical per-unit rounding to old builds."""
    normalized = normalize_build_amount(amount)
    building = get_building(btype)
    if normalized is None or not building:
        return {}
    unit_resources = material_requirements(btype)
    return {
        "btype": btype,
        "amount": normalized,
        "unit_cash": int(building.get("cost", 0) or 0),
        "cash": int(building.get("cost", 0) or 0) * normalized,
        "resources": {key: int(value) * normalized for key, value in unit_resources.items()},
        "seconds": build_seconds(btype),
    }


def build_cost(btype: str) -> int:
    b = get_building(btype)
    if not b:
        return 0
    return max(0, int(round(int(b.get("cost", 0) or 0) * get_cost_mult())))


def material_cost(btype: str) -> int:
    b = get_building(btype)
    return int(b.get("mat", 0)) if b else 0


def max_level_of(btype: str) -> int:
    b = get_building(btype)
    return int(b.get("max_level", 1)) if b else 1


def upgrade_cost(btype: str, level: int) -> int:
    """هزینه‌ی ارتقا از سطحِ فعلی به بعدی (برای زیرساخت/صنعت)."""
    base = build_cost(btype)
    return int(base * (0.6 + 0.25 * max(1, int(level))))


# ---------------------------------------------------------------------------
# ظرفیتِ سکونت، جمعیت، رضایت، درآمد
# ---------------------------------------------------------------------------
def housing_capacity(counts: dict[str, int] | None) -> int:
    """مجموعِ ظرفیتِ سکونتِ واحدهای مسکونی."""
    counts = counts or {}
    total = BASE_POPULATION
    for k in HOUSING_ORDER:
        total += int(counts.get(k, 0)) * int(HOUSING[k]["residents"])
    return min(POP_CAP, total)


def utility_production(counts: dict[str, int] | None) -> dict[str, int]:
    """تولیدِ برق/آب از زیرساخت‌ها."""
    counts = counts or {}
    out = {u: 0 for u in UTILITIES}
    for k, b in INFRA.items():
        u = b.get("util")
        if u:
            out[u] += int(counts.get(k, 0)) * max(0, int(int(b.get("produce", 0) or 0) / get_income_div()))
    return out


def utility_report(counts: dict[str, int] | None, population: int) -> dict[str, dict]:
    """برای هر زیرساخت: تولید، نیاز و کسری."""
    prod = utility_production(counts)
    need = max(1, int(math.ceil(population * UTILITY_PER_CAPITA)))
    rep = {}
    for u in UTILITIES:
        rep[u] = {"produce": prod[u], "need": need, "deficit": max(0, need - prod[u])}
    return rep


def material_production_per_hour(counts: dict[str, int] | None) -> int:
    """جمع کل تولید منابع در ساعت (برای نمایش سازگار قدیمی)."""
    return sum(resource_production_per_hour(counts).values())


def welfare_cap(btype: str, population: int) -> int:
    """سقفِ مجازِ تعدادِ یک ساختمانِ رفاهی بر اساسِ جمعیت/سقفِ مطلق."""
    b = WELFARE.get(btype)
    if not b:
        return 0
    if b.get("max_abs"):
        return int(b["max_abs"])
    ratio = b.get("ratio_pop")
    # فقط سقف‌های صریح (بورس و بازار بزرگ) محدودند؛ سایر امکانات محدودیت تعداد ندارند.
    return 999


def satisfaction_of(counts: dict[str, int] | None, tax_rate: int, population: int) -> int:
    """رضایت = پایه + رفاه/زیرساخت − مالیات − کسریِ زیرساختی − ازدحام."""
    counts = counts or {}
    sat = float(SAT_BASE)
    for tbl in (INFRA, WELFARE):
        for k, b in tbl.items():
            s = b.get("sat")
            if s:
                sat += int(counts.get(k, 0)) * s
    # مالیات: بالاتر از خنثی = نارضایتی، پایین‌تر = رضایت
    sat -= (int(tax_rate) - TAX_NEUTRAL) * 1.2
    # کسریِ زیرساختی
    rep = utility_report(counts, population)
    for r in rep.values():
        if r["deficit"] > 0:
            sat -= 12
    # ازدحام: جمعیت نزدیکِ ظرفیتِ مسکن = افتِ رضایت
    cap = housing_capacity(counts)
    if cap > 0 and population > cap * 0.9:
        sat -= 10
    return max(SAT_MIN, min(SAT_MAX, int(round(sat))))


def service_capacities(counts: dict[str, int] | None) -> dict[str, int]:
    """v1.7.6.5 -- capacity granted by each service family, labelled.

    A family the city has not built yet yields SERVICE_BASELINE rather than
    zero, so one missing building can no longer pin the whole city to its
    base population.
    """
    counts = counts or {}
    util = utility_production(counts)
    out: dict[str, int] = {}
    for key in UTILITIES:
        produced = int(util.get(key, 0) or 0)
        out[key] = (
            int(produced / UTILITY_PER_CAPITA) if produced else SERVICE_BASELINE
        )
    out['road'] = max(SERVICE_BASELINE, int(counts.get('road', 0)) * 100_000)
    out['health'] = max(
        SERVICE_BASELINE,
        int(counts.get('hospital', 0)) * 250_000
        + int(counts.get('clinic', 0)) * 50_000,
    )
    out['education'] = max(
        SERVICE_BASELINE,
        int(counts.get('school', 0)) * 75_000
        + int(counts.get('university', 0)) * 250_000,
    )
    out['leisure'] = max(
        SERVICE_BASELINE,
        int(counts.get('park', 0)) * 20_000
        + int(counts.get('amusement', 0)) * 20_000,
    )
    out['finance'] = max(SERVICE_BASELINE, int(counts.get('bank', 0)) * 125_000)
    return out


def supported_population(counts: dict[str, int] | None, base_population: int = 0) -> int:
    """Largest population the current infrastructure genuinely supports.

    Housing is a hard ceiling: to grow you must build homes. Service families
    are also ceilings, but an unbuilt family falls back to SERVICE_BASELINE
    instead of zero.
    """
    counts = counts or {}
    limits = [housing_capacity(counts)]
    limits.extend(service_capacities(counts).values())
    room = min(POP_CAP, min(limits) if limits else 0)
    return max(int(base_population or 0), room)


def growth_blocker(counts: dict[str, int] | None, population: int,
                   satisfaction: int, base_population: int = 0) -> str | None:
    """Why population will not grow this game year, or None if it will."""
    if int(satisfaction) < GROWTH_MIN_SATISFACTION:
        return 'satisfaction'
    cap = supported_population(counts, base_population)
    if int(population) >= int(cap):
        counts = counts or {}
        if housing_capacity(counts) <= int(population):
            return 'housing'
        worst, worst_key = None, 'service'
        for key, value in service_capacities(counts).items():
            if worst is None or value < worst:
                worst, worst_key = value, key
        return worst_key
    return None


def citizen_needs(counts: dict[str, int] | None, population: int) -> list[str]:
    """نیازهای فعلی مردم که باید در بالای پنل شهر دیده شوند."""
    counts = counts or {}
    population = max(1, int(population or 0))
    needs: list[str] = []
    cap = housing_capacity(counts)
    if cap < population:
        needs.append(f"مسکن برای {population - cap:,} نفر")
    utility = utility_report(counts, population)
    for key in UTILITIES:
        row = utility[key]
        if row["deficit"]:
            needs.append(f"{UTILITY_LABEL[key]} ({row['deficit']:,} واحد کمبود)")
    # این خدمات با رشد جمعیت لازم می‌شوند؛ کمبودشان رضایت و رشد آینده را محدود می‌کند.
    service_rules = (
        ("road", "🛣️ حمل‌ونقل", 100_000),
        ("hospital", "🏥 بیمارستان/درمان", 250_000),
        ("school", "🏫 آموزش", 75_000),
        ("park", "🌳 پارک", 20_000),
        ("amusement", "🎡 شهربازی", 20_000),
        ("bank", "🏦 بانک", 125_000),
    )
    for btype, label, ratio in service_rules:
        needed = max(1, math.ceil(population / ratio))
        have = int(counts.get(btype, 0))
        if have < needed:
            needs.append(f"{label} ({needed - have} مورد نیاز)")
    return needs


def city_production_capacity(counts: dict[str, int] | None) -> dict[str, int]:
    """توان تولید غیرقابل برداشت صنایع؛ برای مصرف فروشگاه‌ها و زیرساخت‌ها."""
    counts = counts or {}
    return {
        "food": sum(int(counts.get(k, 0)) * int(v.get("produce_food", 0)) for k, v in INFRA.items()),
        "fuel": int(counts.get("refinery", 0)) * 100 + int(counts.get("petrochemical", 0)) * 140,
        "vehicles": int(counts.get("vehicle", 0)) * 40,
        "furniture": int(counts.get("furniture", 0)) * 65,
        "electronics": int(counts.get("electronics", 0)) * 55,
    }


def city_production_consumption(counts: dict[str, int] | None) -> dict[str, int]:
    counts = counts or {}
    return {
        "food": int(counts.get("food_store", 0)) * 35 + int(counts.get("restaurant", 0)) * 20,
        "fuel": int(counts.get("fossil_power", 0)) * 35 + int(counts.get("gas_station", 0)) * 20 + int(counts.get("road", 0)) * 5,
        "vehicles": int(counts.get("brt", 0)) * 10,
        "furniture": int(counts.get("home_store", 0)) * 25,
        "electronics": int(counts.get("electronics_store", 0)) * 20,
    }


def industry_output_text(btype: str, level: int) -> str:
    info = INDUSTRY.get(btype, {})
    product = info.get("produce_resource")
    rate = int(info.get("produce_mat", 0)) * max(0, int(level or 0))
    return f"{resource_name(product)}: {rate:,}/ساعت" if product else "تولید ندارد"


def satisfaction_status(sat: int) -> str:
    if sat < 30:
        return "🚨 بحرانی (−۵۰٪ درآمد)"
    if sat < 50:
        return "⚠️ ناراضی"
    if sat < 70:
        return "😐 متوسط"
    if sat < 90:
        return "🙂 راضی"
    return "😍 عالی"


def commerce_income_per_hour(counts: dict[str, int] | None) -> int:
    """درآمد ساعتی تجارت — پایه ÷ ضریب درآمد ادمین."""
    counts = counts or {}
    total = 0
    div = get_income_div()
    for k, b in WELFARE.items():
        base_inc = int(b.get("income", 0) or 0)
        inc = int(base_inc / div) if div else base_inc
        total += int(counts.get(k, 0)) * max(0, inc)
    return int(total)


def income_rate_per_hour(counts: dict[str, int] | None, tax_rate: int,
                         population: int, satisfaction: int) -> int:
    """v1.7.7 — درآمد اصلی = مالیات × جمعیت؛ تجارت فرعی."""
    parts = income_breakdown_parts(counts, tax_rate, population, satisfaction)
    return int(parts["total"])


def income_breakdown_parts(counts: dict[str, int] | None, tax_rate: int,
                           population: int, satisfaction: int) -> dict:
    """جداسازی مالیات vs تجارت برای UI و محاسبه."""
    pop = max(0, int(population or 0))
    tax = pop * (int(tax_rate) / 100.0) * float(TAX_PER_CAPITA_HOUR)
    tax_multiplier = 1.0
    if satisfaction < 30:
        tax_multiplier = 0.5
    elif satisfaction < 50:
        tax_multiplier = 0.8
    elif satisfaction >= 90:
        tax_multiplier = 1.1
    tax_part = int(tax * tax_multiplier)
    commerce = int(commerce_income_per_hour(counts))
    total = min(CITY_HOURLY_INCOME_CAP, tax_part + commerce)
    return {"tax": tax_part, "commerce": commerce, "total": total, "tax_mult": tax_multiplier}


# ---------------------------------------------------------------------------
# رشدِ جمعیت (هر ۳ روزِ واقعی = ۱ سالِ بازی)
# ---------------------------------------------------------------------------
def game_years_elapsed(since, now=None) -> float:
    if not since:
        return 0.0
    now = now or datetime.utcnow()
    try:
        days = max(0.0, (now - since).total_seconds() / 86400.0)
    except Exception:
        return 0.0
    return days / float(GAME_YEAR_REAL_DAYS)


def annual_growth_rate(satisfaction: int) -> float:
    """🆕 v1.8.0.0 — نرخِ پرشدنِ ظرفیتِ خالی در سال بر اساسِ رضایت (۷۵←۲۵٪ … ۱۰۰←۱۰۰٪)."""
    sat = int(satisfaction or 0)
    if sat < GROWTH_MIN_SATISFACTION:
        return 0.0
    frac = 0.25 + (min(100, sat) - GROWTH_MIN_SATISFACTION) / (100 - GROWTH_MIN_SATISFACTION) * 0.75
    return max(0.25, min(1.0, frac))




def grow_population(population: int, capacity: int, satisfaction: int, years: float = 1) -> int:
    """رشد جمعیت پایان سال بازی — sat≥75؛ درصدِ ظرفیتِ خالی بر اساسِ رضایت پر می‌شود.

    🆕 v1.8.0.0 — رضایت ۱۰۰ ← کل ظرفیتِ خالی در یک سال پر می‌شود؛ رضایت ۷۵ (حداقل)
    ← ۲۵٪ ظرفیت در هر سال؛ بین این دو به‌صورت خطی.
    """
    pop = max(0, int(population or 0))
    cap = max(0, int(capacity or 0))
    sat = int(satisfaction or 0)
    if sat < GROWTH_MIN_SATISFACTION or pop >= cap:
        return pop
    try:
        y = float(years or 0)
    except Exception:
        y = 0.0
    if y <= 0:
        return pop
    fill_frac = annual_growth_rate(sat)
    empty = cap - pop
    new_pop = float(pop) + empty * fill_frac * y
    return int(min(cap, max(pop, round(new_pop))))
def game_calendar_text(founded_at, now=None) -> str:
    cal = game_calendar(founded_at, now=now)
    return (
        f"📅 تاریخ شهر: <b>{cal['label']}</b>\n"
        f"⏳ تا پایان سال بازی: <b>{cal['timer_label']}</b>"
    )

def hours_between(a, b) -> float:
    try:
        return max(0.0, (b - a).total_seconds() / 3600.0)
    except Exception:
        return 0.0


# ---------------------------------------------------------------------------
# v1.7.8.3 — مصالح ×۱۰ (تولید + نیاز ساخت) و زمان ساخت ۱ تا ۲۴ ساعت
# ---------------------------------------------------------------------------
MAT_SCALE = 10
for _tbl in (HOUSING, INFRA, WELFARE, INDUSTRY):
    for _b in _tbl.values():
        if "mat" in _b:
            _b["mat"] = int(_b["mat"]) * MAT_SCALE
        for _pf in ("produce_mat", "produce", "produce_food"):
            if _pf in _b:
                _b[_pf] = int(_b[_pf]) * MAT_SCALE

BUILD_MIN_SECONDS = 3600          # حداقل ۱ ساعت
BUILD_MAX_SECONDS = 86400         # حداکثر ۲۴ ساعت
BUILD_HOUR_COST = 15_000_000      # هر ۱۵ میلیون هزینه ≈ ۱ ساعت ساخت


def build_seconds_for_cost(cost: int) -> int:
    """زمان ساخت بر اساس ارزش: حداقل ۱ ساعت، حداکثر ۲۴ ساعت."""
    c = max(0, int(cost or 0))
    sec = int((c / float(BUILD_HOUR_COST)) * 3600)
    return int(max(BUILD_MIN_SECONDS, min(BUILD_MAX_SECONDS, sec)))


def build_seconds(btype: str) -> int:
    b = get_building(btype) or {}
    return build_seconds_for_cost(int(b.get("cost", 0) or 0))


def fmt_duration(seconds: int) -> str:
    sec = max(0, int(seconds or 0))
    h, rem = divmod(sec, 3600)
    m, s2 = divmod(rem, 60)
    if h:
        return f"{h} ساعت" + (f" و {m} دقیقه" if m else "")
    if m:
        return f"{m} دقیقه"
    return f"{s2} ثانیه"


# v1.7.8.5 — سقف تولید روزانهٔ مواد (قابل تنظیم از ادمین‌مود)
PROD_DAILY_CAP_KEY = "city.prod_daily_cap"
DEFAULT_PROD_DAILY_CAP = 1000
_runtime_prod_daily_cap = DEFAULT_PROD_DAILY_CAP


def get_prod_daily_cap() -> int:
    try:
        return max(1, int(_runtime_prod_daily_cap or DEFAULT_PROD_DAILY_CAP))
    except Exception:
        return DEFAULT_PROD_DAILY_CAP


def set_prod_daily_cap(value) -> None:
    global _runtime_prod_daily_cap
    try:
        _runtime_prod_daily_cap = max(1, int(float(value)))
    except Exception:
        _runtime_prod_daily_cap = DEFAULT_PROD_DAILY_CAP


# سقف تجمیعی: کاربران با بیش از ۴۰ واحد صنعتی — سقف کل تولید روزانه (ادمین)
PROD_AGG_CAP_KEY = "city.prod_agg_cap"
DEFAULT_PROD_AGG_CAP = 40_000
PROD_AGG_MIN_UNITS = 40          # آستانهٔ تعداد واحد صنعتی
_runtime_prod_agg_cap = DEFAULT_PROD_AGG_CAP


def get_prod_agg_cap() -> int:
    try:
        return max(1, int(_runtime_prod_agg_cap or DEFAULT_PROD_AGG_CAP))
    except Exception:
        return DEFAULT_PROD_AGG_CAP


def set_prod_agg_cap(value) -> None:
    global _runtime_prod_agg_cap
    try:
        _runtime_prod_agg_cap = max(1, int(float(value)))
    except Exception:
        _runtime_prod_agg_cap = DEFAULT_PROD_AGG_CAP
