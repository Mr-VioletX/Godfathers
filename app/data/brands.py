# -*- coding: utf-8 -*-
"""مرحله ۲۸ — بخشِ برندسازیِ گسترده: ۵ شرکت/هولدینگ.

۴ شرکتِ تولیدی (هر یک یکتا، فقط یک‌بار قابلِ ساخت):
  🚗 ماشین‌سازی | ⌚ ساعت‌سازی | 💎 جواهرات و طلاجات | 👔 لباس و مُد
و ۱ هولدینگِ تفریحی که محصول تولید نمی‌کند و درآمدش خودکار است:
  🎡 هولدینگ — هتل (پایه) → ایرلاین، مجتمعِ تفریحی، صنعتِ سرگرمی، رسانه

محصولاتِ این بخش کلیدِ جدا دارند پس **نمودارِ قیمتِ مستقل** از کارخانه‌های
عادی دارند. سیستمِ تولید دقیقاً مانندِ کارخانه‌های عادی است (انتخابِ محصول +
درصدِ حجمِ خالیِ انبار + هزینه‌ی متفاوتِ هر محصول).
"""
from __future__ import annotations

import random

BRAND_UNLOCK_LEVEL = 14
MAX_COMPANY_LEVEL = 10
MAX_TRACK_LEVEL = 20
PERCENT_STEPS = (10, 20, 30, 40, 50, 60, 70, 80, 90, 100)

# 🆕 v1.7.8.18 — دکمهٔ «▶️ شروعِ همه‌ی خطوط» همیشه ۱۰۰٪ حجمِ خالیِ انبارِ هر
# محصول را تولید می‌کند (قبلاً درصدِ ذخیره‌شده — معمولاً ۵۰٪ — را می‌گرفت).
START_ALL_PERCENT = 100

# 🆕 v1.7.8.18 — هر محصولِ برند هم دو خطِ تولیدِ مستقلِ خودش را دارد.
LINES_PER_PRODUCT = 2


def lines_per_product(line_level=None):
    """تعدادِ خطِ تولیدِ همزمانِ هر محصولِ برند (فعلاً برایِ همه ۲ خط)."""
    return LINES_PER_PRODUCT

BASE_CAPACITY = 300
CAPACITY_PER_LEVEL = 300

CAPACITY_UPGRADE_BASE = 180_000
SPEED_UPGRADE_BASE = 240_000
EXPANSION_UPGRADE_BASE = 500_000
LINE_UPGRADE_BASE = 400_000

# ---------------------------------------------------------------------------
# محصولاتِ برند (کلیدِ قیمت مستقل)
# ---------------------------------------------------------------------------
BRAND_PRODUCTS: dict[str, dict] = {
    # 🚗 ماشین‌سازی — از عادی تا لوکس
    "car_eco": {
        "name": "🚙 خودروی اقتصادی", "company": "automotive", "tier": 1,
        "raw_cost": 120_000, "produce_hours": 5, "batch": 5,
        "base": 48_000, "min": 32_400, "max": 76_800, "volatility": 0.07,
    },
    "car_family": {
        "name": "🚐 خودروی خانوادگی", "company": "automotive", "tier": 2,
        "raw_cost": 240_000, "produce_hours": 7, "batch": 4,
        "base": 120_000, "min": 81_000, "max": 192_000, "volatility": 0.09,
    },
    "car_sport": {
        "name": "🏎️ خودروی اسپورت", "company": "automotive", "tier": 3,
        "raw_cost": 520_000, "produce_hours": 9, "batch": 3,
        "base": 346_700, "min": 234_000, "max": 554_700, "volatility": 0.12,
    },
    "car_lux": {
        "name": "🚗 لیموزینِ لوکس", "company": "automotive", "tier": 4,
        "raw_cost": 1_040_000, "produce_hours": 12, "batch": 2,
        "base": 1_040_000, "min": 702_000, "max": 1_664_000, "volatility": 0.15,
    },

    # ⌚ ساعت‌سازی
    "watch_steel": {
        "name": "⌚ ساعتِ فولادی", "company": "watch", "tier": 1,
        "raw_cost": 60_000, "produce_hours": 4, "batch": 6,
        "base": 20_000, "min": 13_500, "max": 32_000, "volatility": 0.08,
    },
    "watch_gold": {
        "name": "🕰️ ساعتِ طلا", "company": "watch", "tier": 2,
        "raw_cost": 180_000, "produce_hours": 6, "batch": 4,
        "base": 90_000, "min": 60_800, "max": 144_000, "volatility": 0.11,
    },
    "watch_haute": {
        "name": "💠 ساعتِ اُوت‌هورلوژری", "company": "watch", "tier": 3,
        "raw_cost": 480_000, "produce_hours": 10, "batch": 2,
        "base": 480_000, "min": 324_000, "max": 768_000, "volatility": 0.16,
    },

    # 💎 جواهرات و طلاجات
    "jewel_silver": {
        "name": "🔗 زیورِ نقره", "company": "jewelry", "tier": 1,
        "raw_cost": 50_000, "produce_hours": 3, "batch": 8,
        "base": 12_500, "min": 8_400, "max": 20_000, "volatility": 0.09,
    },
    "jewel_gold": {
        "name": "🧿 طلای دست‌ساز", "company": "jewelry", "tier": 2,
        "raw_cost": 190_000, "produce_hours": 6, "batch": 5,
        "base": 76_000, "min": 51_300, "max": 121_600, "volatility": 0.12,
    },
    "jewel_diamond": {
        "name": "💎 جواهرِ الماس", "company": "jewelry", "tier": 3,
        "raw_cost": 600_000, "produce_hours": 11, "batch": 2,
        "base": 600_000, "min": 405_000, "max": 960_000, "volatility": 0.18,
    },

    # 👔 لباس و مُد
    "apparel_ready": {
        "name": "👕 پوشاکِ آماده", "company": "apparel", "tier": 1,
        "raw_cost": 36_000, "produce_hours": 3, "batch": 10,
        "base": 7_200, "min": 4_900, "max": 11_500, "volatility": 0.08,
    },
    "apparel_designer": {
        "name": "👔 لباسِ دیزاینر", "company": "apparel", "tier": 2,
        "raw_cost": 140_000, "produce_hours": 5, "batch": 6,
        "base": 46_700, "min": 31_500, "max": 74_700, "volatility": 0.11,
    },
    "apparel_couture": {
        "name": "👗 هوت‌کوتور", "company": "apparel", "tier": 3,
        "raw_cost": 420_000, "produce_hours": 9, "batch": 3,
        "base": 280_000, "min": 189_000, "max": 448_000, "volatility": 0.15,
    },
}

# ---------------------------------------------------------------------------
# ۵ شرکت/هولدینگ
# ---------------------------------------------------------------------------
COMPANIES: dict[str, dict] = {
    "automotive": {
        "key": "automotive", "name": "🚗 شرکتِ ماشین‌سازی", "kind": "producer",
        "cost": 5_000_000, "default_name": "ماشین‌سازیِ من",
        "desc": "چند سطح خودرو — از اقتصادی تا لیموزینِ لوکس.",
    },
    "watch": {
        "key": "watch", "name": "⌚ شرکتِ ساعت‌سازی", "kind": "producer",
        "cost": 3_600_000, "default_name": "مانوفاکتورِ ساعتِ من",
        "desc": "ساعتِ فولادی، طلا و اُوت‌هورلوژری.",
    },
    "jewelry": {
        "key": "jewelry", "name": "💎 شرکتِ جواهرات و طلاجات", "kind": "producer",
        "cost": 4_400_000, "default_name": "جواهریِ من",
        "desc": "نقره، طلای دست‌ساز و جواهرِ الماس — جایگاهِ تولیدِ کالای لوکس.",
    },
    "apparel": {
        "key": "apparel", "name": "👔 شرکتِ لباس و مُد", "kind": "producer",
        "cost": 3_000_000, "default_name": "مُد‌خانه‌ی من",
        "desc": "پوشاکِ آماده، دیزاینر و هوت‌کوتور.",
    },
    "holding": {
        "key": "holding", "name": "🎡 هولدینگِ تفریحی", "kind": "holding",
        "cost": 6_000_000, "default_name": "هولدینگِ من",
        "desc": "محصول تولید نمی‌کند — درآمدِ خودکار از هتل، ایرلاین، مجتمعِ تفریحی، سرگرمی و رسانه.",
    },
}

COMPANY_ORDER = ["automotive", "watch", "jewelry", "apparel", "holding"]
HOLDING_KEY = "holding"


def get_company(key):
    return COMPANIES.get(key)


def company_products(company_key):
    items = [(k, p) for k, p in BRAND_PRODUCTS.items() if p["company"] == company_key]
    items.sort(key=lambda kv: kv[1]["tier"])
    return [k for k, _ in items]


def get_brand_product(key):
    return BRAND_PRODUCTS.get(key)


def unlocked_company_products(company_key, expansion_level):
    keys = company_products(company_key)
    return keys[: max(1, int(expansion_level or 1))]


def company_capacity(capacity_level):
    """⚠️ قدیمی — از v1.7.8.17 ظرفیتِ شرکت جمعِ انبارِ محصولاتش است.

    فقط برایِ سازگاری با کدِ قدیم مانده؛ از company_total_capacity(rows) استفاده کن.
    """
    return BASE_CAPACITY + CAPACITY_PER_LEVEL * (max(1, int(capacity_level or 1)) - 1)


# ---------------------------------------------------------------------------
# 🆕 v1.7.8.17 — انبارِ اختصاصیِ هر محصولِ برند (دقیقاً مانندِ کارخانه)
#   سطح ۱ ← ۵٬۰۰۰ واحد  |  سطح ۱۰ ← ۱۵٬۰۰۰ واحد
# ظرفیتِ شرکت = جمعِ انبارِ محصولاتش و دیگر مستقل ارتقا نمی‌شود.
# ---------------------------------------------------------------------------
PRODUCT_CAP_BASE = 5_000
PRODUCT_CAP_MAX = 15_000
PRODUCT_CAP_MAX_LEVEL = 10
PRODUCT_CAP_UPGRADE_BASE = 500_000

# 🆕 v1.7.8.17 — بیشینهٔ سفارش‌هایِ منتظر در صفِ ساختِ هر شرکت
QUEUE_MAX = 10


def product_capacity(level):
    """ظرفیتِ انبارِ یک محصولِ برند در سطحِ داده‌شده."""
    lvl = max(1, min(PRODUCT_CAP_MAX_LEVEL, int(level or 1)))
    if PRODUCT_CAP_MAX_LEVEL <= 1:
        return PRODUCT_CAP_BASE
    span = PRODUCT_CAP_MAX - PRODUCT_CAP_BASE
    raw = PRODUCT_CAP_BASE + span * (lvl - 1) / float(PRODUCT_CAP_MAX_LEVEL - 1)
    return int(round(raw / 100.0) * 100)


def product_capacity_upgrade_cost(level):
    """هزینهٔ ارتقایِ انبارِ یک محصولِ برند."""
    return _geom(PRODUCT_CAP_UPGRADE_BASE, level)


def company_total_capacity(rows):
    """ظرفیتِ کلِ شرکت = جمعِ ظرفیتِ انبارِ محصولاتِ بازشده‌اش."""
    return sum(product_capacity(getattr(r, "capacity_level", 1)) for r in rows)


def speed_factor(speed_level):
    return 1.0 / (1.0 + 0.15 * (max(1, int(speed_level or 1)) - 1))


def effective_produce_hours(product_key, speed_level):
    p = BRAND_PRODUCTS.get(product_key) or {"produce_hours": 4}
    return max(0.1, p["produce_hours"] * speed_factor(speed_level))


def normalize_percent(pct):
    try:
        v = int(pct or 50)
    except Exception:
        v = 50
    return max(10, min(100, (v // 10) * 10 or 10))


def units_for_percent(free_room, pct):
    room = max(0, int(free_room or 0))
    if room <= 0:
        return 0
    return max(1, int(room * normalize_percent(pct) // 100))


def unit_raw_cost(product_key, speed_level=1):
    p = BRAND_PRODUCTS.get(product_key) or {}
    batch = max(1, int(p.get("batch", 1)))
    per_unit = int(p.get("raw_cost", 0)) / batch
    return max(1, int(round(per_unit * (1.0 + 0.02 * (max(1, int(speed_level or 1)) - 1)))))


def raw_cost_for_units(product_key, units, speed_level=1):
    return unit_raw_cost(product_key, speed_level) * max(0, int(units or 0))


def _geom(base, level):
    lvl = max(1, int(level or 1))
    return int(base * lvl * (1.0 + 0.5 * (lvl - 1)))


def capacity_upgrade_cost(level):
    return _geom(CAPACITY_UPGRADE_BASE, level)


def speed_upgrade_cost(level):
    return _geom(SPEED_UPGRADE_BASE, level)


def expansion_upgrade_cost(level):
    return _geom(EXPANSION_UPGRADE_BASE, level)


def line_upgrade_cost(level):
    return _geom(LINE_UPGRADE_BASE, level)


def max_lines(line_level):
    return max(1, int(line_level or 1))


# ---------------------------------------------------------------------------
# هولدینگِ تفریحی — واحدها و مسیرهای ارتقا
# هتل اولین واحدِ پایه است که با خریدِ هولدینگ باز می‌شود.
# ---------------------------------------------------------------------------
HOLDING_UNITS: dict[str, dict] = {
    "hotel": {
        "key": "hotel", "name": "🏨 هتل", "default_name": "هتلِ من", "base": True,
        "cost": 0, "income": 90_000,
        "tracks": {
            "rooms": {"name": "🛏️ اتاق‌ها و سوئیت‌ها", "cost": 300_000, "gain": 0.12},
            "service": {"name": "🧹 کیفیتِ خدمات", "cost": 240_000, "gain": 0.10},
            "restaurant": {"name": "🍽️ رستورانِ لوکس", "cost": 400_000, "gain": 0.14},
            "spa": {"name": "💆 اسپا و استخر", "cost": 360_000, "gain": 0.12},
            "casino": {"name": "🎰 سالنِ بازی", "cost": 640_000, "gain": 0.20},
        },
    },
    "airline": {
        "key": "airline", "name": "✈️ ایرلاین", "default_name": "ایرلاینِ من", "base": False,
        "cost": 3_200_000, "income": 150_000,
        "tracks": {
            "fleet": {"name": "🛫 ناوگانِ هواپیما", "cost": 800_000, "gain": 0.16},
            "routes": {"name": "🗺️ مسیرهای پروازی", "cost": 600_000, "gain": 0.14},
            "firstclass": {"name": "🪑 کلاسِ یک", "cost": 1_000_000, "gain": 0.18},
            "cargo": {"name": "📦 بخشِ باری", "cost": 700_000, "gain": 0.13},
        },
    },
    "resort": {
        "key": "resort", "name": "🎢 مجتمعِ تفریحی", "default_name": "مجتمعِ من", "base": False,
        "cost": 2_400_000, "income": 120_000,
        "tracks": {
            "rides": {"name": "🎡 شهرِ بازی", "cost": 520_000, "gain": 0.15},
            "waterpark": {"name": "🌊 پارکِ آبی", "cost": 600_000, "gain": 0.15},
            "mall": {"name": "🛍️ مرکزِ خرید", "cost": 680_000, "gain": 0.16},
            "golf": {"name": "⛳ زمینِ گلف", "cost": 560_000, "gain": 0.12},
        },
    },
    "entertainment": {
        "key": "entertainment", "name": "🎬 صنعتِ سرگرمی", "default_name": "استودیوی من", "base": False,
        "cost": 2_800_000, "income": 135_000,
        "tracks": {
            "studio": {"name": "🎥 استودیوی فیلم", "cost": 640_000, "gain": 0.16},
            "music": {"name": "🎵 کمپانیِ موسیقی", "cost": 520_000, "gain": 0.13},
            "events": {"name": "🎪 رویداد و کنسرت", "cost": 480_000, "gain": 0.12},
            "stars": {"name": "⭐ قراردادِ ستاره‌ها", "cost": 840_000, "gain": 0.19},
        },
    },
    "media": {
        "key": "media", "name": "📺 رسانه", "default_name": "رسانه‌ی من", "base": False,
        "cost": 2_200_000, "income": 105_000,
        "tracks": {
            "tv": {"name": "📡 شبکه‌ی تلویزیونی", "cost": 600_000, "gain": 0.15},
            "press": {"name": "📰 روزنامه و مجله", "cost": 400_000, "gain": 0.11},
            "digital": {"name": "📱 رسانه‌ی دیجیتال", "cost": 560_000, "gain": 0.14},
            "ads": {"name": "📣 آژانسِ تبلیغات", "cost": 680_000, "gain": 0.16},
        },
    },
}

HOLDING_UNIT_ORDER = ["hotel", "airline", "resort", "entertainment", "media"]
HOLDING_TRACK_MAX = 10
HOLDING_MAX_OFFLINE_HOURS = 24


def get_holding_unit(key):
    return HOLDING_UNITS.get(key)


def unit_track(unit_key, track_key):
    u = HOLDING_UNITS.get(unit_key) or {}
    return (u.get("tracks") or {}).get(track_key)


def unit_track_cost(unit_key, track_key, level):
    t = unit_track(unit_key, track_key)
    if not t:
        return 0
    lvl = max(0, int(level or 0))
    return int(t["cost"] * (1 + 0.6 * lvl))


def unit_income_per_hour(unit_key, tracks: dict | None) -> int:
    """درآمدِ ساعتیِ یک واحدِ هولدینگ با توجه به سطحِ مسیرهای ارتقایش."""
    u = HOLDING_UNITS.get(unit_key)
    if not u:
        return 0
    rate = float(u["income"])
    lv = tracks or {}
    bonus = 0.0
    for tkey, t in (u.get("tracks") or {}).items():
        bonus += float(t["gain"]) * max(0, int(lv.get(tkey, 0) or 0))
    return int(rate * (1.0 + bonus))


def holding_total_income(units) -> int:
    """units = لیستِ (unit_key, tracks_dict)."""
    return sum(unit_income_per_hour(k, t) for k, t in units)


# ---------------------------------------------------------------------------
# 📈 نمودارِ قیمتِ مستقلِ محصولاتِ برند
# قیمت‌ها در همان جدولِ market_prices نگه داشته می‌شوند (کلیدها متفاوت‌اند)
# ولی موتورِ حرکتِ قیمتِ جدا دارند: نوسانِ بیشتر + روندِ روزانه.
# ---------------------------------------------------------------------------
BRAND_PRICE_TICK_MINUTES = 60
BRAND_HISTORY_LEN = 24
BRAND_MAX_TICKS = 48


def brand_initial_price(product_key):
    p = BRAND_PRODUCTS.get(product_key) or {"base": 1000}
    return float(p["base"])


def _brand_next_price(product_key, prev):
    p = BRAND_PRODUCTS.get(product_key)
    if not p:
        return prev
    v = float(p["volatility"])
    noise = random.uniform(-v, +v)
    drift = (float(p["base"]) - prev) / float(p["base"]) * 0.04
    nxt = prev * (1 + drift + noise)
    return round(max(float(p["min"]), min(float(p["max"]), nxt)), 2)


def brand_advance_price(product_key, prev_price, history, ticks):
    price = prev_price
    hist = list(history or [])
    for _ in range(min(int(ticks or 0), BRAND_MAX_TICKS)):
        price = _brand_next_price(product_key, price)
        hist.append(price)
    return price, hist[-BRAND_HISTORY_LEN:]


def brand_ticks_elapsed(updated_at, now):
    if updated_at is None:
        return 0
    minutes = (now - updated_at).total_seconds() / 60.0
    return int(minutes // BRAND_PRICE_TICK_MINUTES)


_BSPARK = "▁▂▃▄▅▆▇█"


def brand_sparkline(values):
    vals = list(values or [])
    if not vals:
        return "—"
    lo, hi = min(vals), max(vals)
    if hi - lo < 1e-9:
        return _BSPARK[0] * len(vals)
    out = []
    for x in vals:
        idx = int((x - lo) / (hi - lo) * (len(_BSPARK) - 1))
        out.append(_BSPARK[idx])
    return "".join(out)


def brand_price_arrow(history):
    h = list(history or [])
    if len(h) < 2:
        return "➡️"
    if h[-1] > h[-2]:
        return "📈"
    if h[-1] < h[-2]:
        return "📉"
    return "➡️"


def company_of_product(product_key):
    p = BRAND_PRODUCTS.get(product_key)
    return p["company"] if p else None


def company_name(company_key):
    c = COMPANIES.get(company_key)
    return c["name"] if c else company_key


def producer_companies():
    return [k for k in COMPANY_ORDER if COMPANIES[k]["kind"] == "producer"]


def batch_output(product_key, capacity_level, line_level):
    """بروندادِ پایه‌ی یک دوره‌ی تولید (وقتی کاربر درصد انتخاب نکرده)."""
    p = BRAND_PRODUCTS.get(product_key) or {"batch": 1}
    return max(1, int(p.get("batch", 1)) * max(1, int(capacity_level or 1)))


def xp_for_units(product_key, units):
    p = BRAND_PRODUCTS.get(product_key) or {"tier": 1}
    return max(1, int(int(p.get("tier", 1)) * max(1, int(units or 0)) // 2))
