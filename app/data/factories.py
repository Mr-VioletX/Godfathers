# -*- coding: utf-8 -*-
"""مرحله ۲۸ — بازطراحیِ کاملِ کارخانه‌ها.

قوانینِ جدید:
  1) در کلِ بازی **۵ کارخانه** وجود دارد و هر کدام **فقط یک‌بار** قابلِ ساخت است
     (دیگر «کارخانه #۱ / #۲» وجود ندارد — هر کارخانه یکتا و نام‌دار است).
  2) هر کارخانه محصولاتِ مربوط به خودش را دارد (سه سطحِ محصول).
  3) تولید به‌صورتِ **درصدی از حجمِ خالیِ باقی‌مانده‌ی انبار** انجام می‌شود
     (پله‌های ۱۰ درصدی: ۱۰٪ تا ۱۰۰٪) و کاربر درصد را انتخاب می‌کند.

توابعِ این ماجول خالِص (pure) هستند تا مستقل تست شوند.
"""
from __future__ import annotations

from app.data.market import PRODUCTS, get_product, products_of_factory

EMPORIO_KEY = "emporio"
FONDERIA_KEY = "fonderia"

MAX_TRACK_LEVEL = 20

# v1.7.8.5 — گیتِ دسترسیِ ابرکارخانهٔ دون
GIGA_KEY = "giga"
GIGA_MAX_NET_WORTH = 300_000_000_000     # زیر ۳۰۰ میلیارد ثروتِ خالص
GIGA_PERSIST_BELOW = 300_000_000_000     # بازیکنانِ زیر ۳۰۰ میلیارد که بازش کرده‌اند، برایشان باز می‌ماند

BASE_CAPACITY = 400
CAPACITY_PER_LEVEL = 400

CAPACITY_UPGRADE_BASE = 600_000
SPEED_UPGRADE_BASE = 900_000
EXPANSION_UPGRADE_BASE = 1_200_000
LINE_UPGRADE_BASE = 1_600_000

# درصدهای انتخابیِ تولید (پله ۱۰٪)
PERCENT_STEPS = (10, 20, 30, 40, 50, 60, 70, 80, 90, 100)
DEFAULT_PERCENT = 50

# 🆕 v1.7.8.18 — دکمهٔ «▶️ شروعِ همه‌ی خط‌ها» همیشه ۱۰۰٪ حجمِ خالیِ انبارِ هر
# محصول را تولید می‌کند (قبلاً درصدِ ذخیره‌شده — معمولاً ۵۰٪ — را می‌گرفت).
START_ALL_PERCENT = 100

# 🆕 v1.7.8.18 — هر محصول دو خطِ تولیدِ مستقلِ خودش را دارد؛ پس تا وقتی در
# انبارِ اختصاصیِ همان محصول جا باشد، می‌توان همزمان دو سفارش برایش شروع کرد
# (چه از صفحهٔ محصول، چه از صفِ ساخت).
LINES_PER_PRODUCT = 2


def lines_per_product(line_level=None):
    """تعدادِ خطِ تولیدِ همزمانِ هر محصول (فعلاً برایِ همه ۲ خط)."""
    return LINES_PER_PRODUCT

# ---------------------------------------------------------------------------
# ۵ کارخانه‌ی یکتای بازی
# ---------------------------------------------------------------------------
FACTORY_TYPES: dict[str, dict] = {
    "textile": {
        "key": "textile",
        "name": "🧵 کارخانه‌ی نساجی",
        "requires": EMPORIO_KEY,
        "build_cost": 500_000,
        "desc": "پارچه، چرم و پارچه‌ی نفیس — ورودیِ ارزان با گردشِ سریع.",
    },
    "distillery": {
        "key": "distillery",
        "name": "🥃 کارخانه‌ی نوشیدنی",
        "requires": EMPORIO_KEY,
        "build_cost": 840_000,
        "desc": "مشروب، شرابِ کهنه و شامپاین — سودِ متوسط با نوسانِ خوب.",
    },
    "electronics": {
        "key": "electronics",
        "name": "📻 کارخانه‌ی الکترونیک",
        "requires": EMPORIO_KEY,
        "build_cost": 1_400_000,
        "desc": "رادیو، مدارِ چاپی و تجهیزاتِ مخابراتی — سودِ بالاتر.",
    },
    "steel": {
        "key": "steel",
        "name": "⚙️ کارخانه‌ی ذوب‌آهن و قطعات",
        "requires": FONDERIA_KEY,
        "build_cost": 2_000_000,
        "desc": "فلزات، قطعاتِ فلزی و ورقِ زرهی — موادِ پایه‌ی تسلیحات.",
    },
    "chemical": {
        "key": "chemical",
        "name": "⚗️ کارخانه‌ی شیمیایی-دارویی",
        "requires": FONDERIA_KEY,
        "build_cost": 2_600_000,
        "desc": "دارو، حلالِ صناعی و موادِ منفجره — پرسودترین کارخانه‌ی عادی.",
    },
    "giga": {
        "key": "giga",
        "name": "🏭 ابرکارخانهٔ دون",
        "requires": EMPORIO_KEY,
        "build_cost": 8_000_000,
        "desc": "ساعتِ لوکس، گجتِ هوشمند و پهپادِ تاکتیکی — پرسودترین کارخانه‌ی کلِ بازی. مخصوص ثروتِ خالصِ زیر ۳۰۰ میلیارد.",
    },
}

FACTORY_ORDER = ["textile", "distillery", "electronics", "steel", "chemical", "giga"]
FACTORY_COUNT = len(FACTORY_ORDER)


def get_factory_type(key):
    return FACTORY_TYPES.get(key)


def factory_name(key):
    t = FACTORY_TYPES.get(key)
    return t["name"] if t else str(key)


def factory_type_build_cost(key):
    t = FACTORY_TYPES.get(key)
    return int(t["build_cost"]) if t else 0


def factory_requires(key):
    t = FACTORY_TYPES.get(key)
    return t["requires"] if t else EMPORIO_KEY


def products_for_factory(key):
    """محصولاتِ اختصاصیِ همین کارخانه (به ترتیبِ سطح)."""
    return products_of_factory(key)


def factory_of_product(product_key):
    p = get_product(product_key) or {}
    return p.get("factory")


# ---- سازگاری با کدِ قدیم (دسته‌ی emporio/fonderia) ----
def category_of(product_key):
    p = get_product(product_key)
    return p["requires"] if p else EMPORIO_KEY


def products_for_category(category):
    return [k for k, p in PRODUCTS.items() if p["requires"] == category]


# ---------------------------------------------------------------------------
# ظرفیت، سرعت، خطوط و تولیدِ درصدی
# ---------------------------------------------------------------------------
def factory_capacity(capacity_level):
    """⚠️ قدیمی — از v1.7.8.17 ظرفیتِ کارخانه جمعِ انبارِ محصولاتش است.

    فقط برایِ سازگاری با کدِ قدیم نگه داشته شده؛ از فاکتوریِ جدید
    به‌جایِ آن از factory_total_capacity(rows) استفاده کن.
    """
    return BASE_CAPACITY + CAPACITY_PER_LEVEL * (max(1, int(capacity_level or 1)) - 1)


# ---------------------------------------------------------------------------
# 🆕 v1.7.8.17 — انبارِ اختصاصیِ هر محصول
#
# هر محصولِ بازشده انبارِ مستقلِ خودش را دارد (۱۰ سطح).
#   سطح ۱  ← ۵٬۰۰۰ واحد
#   سطح ۱۰ ← ۱۵٬۰۰۰ واحد
# سطح‌هایِ میانی به‌صورتِ خطی درون‌یابی و به صدتایی گرد می‌شوند.
# ظرفیتِ خودِ کارخانه دیگر مستقل ارتقا نمی‌شود؛ جمعِ همین‌هاست.
# ---------------------------------------------------------------------------
PRODUCT_CAP_BASE = 5_000
PRODUCT_CAP_MAX = 15_000
PRODUCT_CAP_MAX_LEVEL = 10
PRODUCT_CAP_UPGRADE_BASE = 500_000

# 🆕 v1.7.8.17 — بیشینهٔ سفارش‌هایِ منتظر در صفِ ساختِ هر کارخانه
QUEUE_MAX = 10


def product_capacity(level):
    """ظرفیتِ انبارِ یک محصول در سطحِ داده‌شده."""
    lvl = max(1, min(PRODUCT_CAP_MAX_LEVEL, int(level or 1)))
    if PRODUCT_CAP_MAX_LEVEL <= 1:
        return PRODUCT_CAP_BASE
    span = PRODUCT_CAP_MAX - PRODUCT_CAP_BASE
    raw = PRODUCT_CAP_BASE + span * (lvl - 1) / float(PRODUCT_CAP_MAX_LEVEL - 1)
    return int(round(raw / 100.0) * 100)


def product_capacity_upgrade_cost(level):
    """هزینهٔ ارتقایِ انبارِ یک محصول از سطحِ فعلی به بعدی."""
    return _geom_cost(PRODUCT_CAP_UPGRADE_BASE, level)


def factory_total_capacity(rows):
    """ظرفیتِ کلِ کارخانه = جمعِ ظرفیتِ انبارِ محصولاتِ بازشده‌اش."""
    return sum(product_capacity(getattr(r, "capacity_level", 1)) for r in rows)


def speed_factor(speed_level):
    return 1.0 / (1.0 + 0.15 * (max(1, int(speed_level or 1)) - 1))


def effective_produce_hours(product_key, speed_level):
    p = get_product(product_key) or {"produce_hours": 2}
    return max(0.1, p["produce_hours"] * speed_factor(speed_level))


def max_products(expansion_level):
    return max(1, int(expansion_level or 1))


def max_lines(line_level):
    return max(1, int(line_level or 1))


def unlocked_products(factory_key, expansion_level):
    """محصولاتی که با سطحِ گسترشِ فعلی قابلِ تولیدند."""
    keys = products_for_factory(factory_key)
    return keys[: max_products(expansion_level)]


def normalize_percent(pct):
    """درصدِ ورودی را به پله‌ی ۱۰٪ گرد می‌کند (۱۰..۱۰۰)."""
    try:
        v = int(pct or DEFAULT_PERCENT)
    except Exception:
        v = DEFAULT_PERCENT
    v = max(10, min(100, (v // 10) * 10 or 10))
    return v


def units_for_percent(free_room, pct):
    """تعدادِ واحدِ تولید = درصدی از حجمِ خالیِ باقی‌مانده‌ی انبار."""
    room = max(0, int(free_room or 0))
    if room <= 0:
        return 0
    return max(1, int(room * normalize_percent(pct) // 100))


def unit_raw_cost(product_key, speed_level=1):
    """هزینه‌ی موادِ اولیه‌ی هر واحد (خطِ سریع‌تر کمی گران‌تر است)."""
    p = get_product(product_key) or {}
    base = int(p.get("raw_cost", 0))
    batch = max(1, int(p.get("batch", 1)))
    per_unit = base / batch
    return max(1, int(round(per_unit * (1.0 + 0.02 * (max(1, int(speed_level or 1)) - 1)))))


def raw_cost_for_units(product_key, units, speed_level=1):
    return unit_raw_cost(product_key, speed_level) * max(0, int(units or 0))


def unit_sale_hint(product_key):
    p = get_product(product_key) or {}
    batch = max(1, int(p.get("batch", 1)))
    return int(int(p.get("raw_cost", 0)) / batch), int(p.get("base", 0))


# ---- سازگاری: تولیدِ دسته‌ایِ قدیم ----
def output_multiplier(capacity_level, line_level):
    cap = max(1, int(capacity_level or 1))
    ln = max(1, int(line_level or 1))
    return 1.0 + 0.05 * (cap - 1) + 0.03 * (ln - 1)


def batch_output(product_key, capacity_level, line_level):
    p = get_product(product_key) or {}
    base = int(p.get("batch", 0))
    return max(1, int(round(base * output_multiplier(capacity_level, line_level))))


def raw_cost(product_key, speed_level=1):
    p = get_product(product_key) or {}
    base = int(p.get("raw_cost", 0))
    return int(base * (1.0 + 0.02 * (max(1, int(speed_level or 1)) - 1)))


def warehouse_share_percent(warehouse_level):
    lvl = max(1, int(warehouse_level or 1))
    return min(50, 10 + 4 * (lvl - 1))


def split_to_warehouse(units, warehouse_level):
    units = max(0, int(units or 0))
    if units <= 0:
        return 0, 0
    pct = warehouse_share_percent(warehouse_level)
    to_wh = int(units * pct // 100)
    return to_wh, units - to_wh


def xp_for_units(units):
    return int(max(5, min(400, int(units or 0) // 2)))


def _geom_cost(base, level):
    lvl = max(1, int(level or 1))
    return int(base * lvl * (1.0 + 0.5 * (lvl - 1)))


def capacity_upgrade_cost(level):
    return _geom_cost(CAPACITY_UPGRADE_BASE, level)


def speed_upgrade_cost(level):
    return _geom_cost(SPEED_UPGRADE_BASE, level)


def expansion_upgrade_cost(level):
    return _geom_cost(EXPANSION_UPGRADE_BASE, level)


def line_upgrade_cost(level):
    return _geom_cost(LINE_UPGRADE_BASE, level)
