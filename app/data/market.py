# -*- coding: utf-8 -*-
"""بازار و قیمت‌ها.

مرحله ۲۸ — بازطراحیِ کامل:
  • ۵ کارخانه‌ی یکتا وجود دارد و **هر کارخانه محصولاتِ اختصاصیِ خودش** را دارد.
  • «کالای لوکس» از کارخانه‌های عادی برداشته و به بخشِ برندسازی منتقل شد.
  • «فلزات» حالا محلِ تولیدِ مشخص دارد (کارخانه‌ی ذوب‌آهن).
  • نمودارِ قیمت هم بر اساسِ همین محصولاتِ هر کارخانه گروه‌بندی می‌شود.
"""
from __future__ import annotations

import random

PRICE_TICK_MINUTES = 60
MAX_TICKS_PER_REFRESH = 24
HISTORY_LEN = 24
FACTORY_MAX_LEVEL = 5
BUILD_COST_MULT = 6

# ---------------------------------------------------------------------------
# محصولاتِ کارخانه‌های عادی — هر محصول با کلیدِ کارخانه‌ی سازنده‌اش (factory)
# requires = عمارتِ لازم برای بازشدنِ آن کارخانه
# tier = سطحِ محصول در همان کارخانه (۱ = محصولِ پایه)
# ---------------------------------------------------------------------------
PRODUCTS = {
    # ---------- 🧵 کارخانه‌ی نساجی ----------
    "cloth": {
        "name": "🧵 پارچه", "factory": "textile", "requires": "emporio", "tier": 1,
        "raw_cost": 4_000, "produce_hours": 2, "batch": 10,
        "base": 800, "min": 540, "max": 1_300, "volatility": 0.06,
    },
    "leather": {
        "name": "🧳 چرم", "factory": "textile", "requires": "emporio", "tier": 2,
        "raw_cost": 9_000, "produce_hours": 3, "batch": 9,
        "base": 2_000, "min": 1_400, "max": 3_200, "volatility": 0.08,
    },
    "fine_fabric": {
        "name": "🎽 پارچه‌ی نفیس", "factory": "textile", "requires": "emporio", "tier": 3,
        "raw_cost": 18_000, "produce_hours": 4, "batch": 7,
        "base": 5_100, "min": 3_500, "max": 8_200, "volatility": 0.10,
    },

    # ---------- 🥃 کارخانه‌ی نوشیدنی ----------
    "liquor": {
        "name": "🥃 مشروب", "factory": "distillery", "requires": "emporio", "tier": 1,
        "raw_cost": 10_000, "produce_hours": 3, "batch": 10,
        "base": 2_000, "min": 1_400, "max": 3_200, "volatility": 0.09,
    },
    "wine": {
        "name": "🍷 شرابِ کهنه", "factory": "distillery", "requires": "emporio", "tier": 2,
        "raw_cost": 22_000, "produce_hours": 5, "batch": 8,
        "base": 5_500, "min": 3_700, "max": 8_800, "volatility": 0.11,
    },
    "champagne": {
        "name": "🍾 شامپاینِ ویژه", "factory": "distillery", "requires": "emporio", "tier": 3,
        "raw_cost": 40_000, "produce_hours": 7, "batch": 6,
        "base": 13_300, "min": 9_000, "max": 21_300, "volatility": 0.13,
    },

    # ---------- 📻 کارخانه‌ی الکترونیک ----------
    "radio": {
        "name": "📻 رادیو و گرامافون", "factory": "electronics", "requires": "emporio", "tier": 1,
        "raw_cost": 18_000, "produce_hours": 4, "batch": 8,
        "base": 4_500, "min": 3_000, "max": 7_200, "volatility": 0.10,
    },
    "circuit": {
        "name": "🔌 مدارِ چاپی", "factory": "electronics", "requires": "emporio", "tier": 2,
        "raw_cost": 30_000, "produce_hours": 5, "batch": 7,
        "base": 8_600, "min": 5_800, "max": 13_700, "volatility": 0.11,
    },
    "comms": {
        "name": "📡 تجهیزاتِ مخابراتی", "factory": "electronics", "requires": "emporio", "tier": 3,
        "raw_cost": 52_000, "produce_hours": 7, "batch": 5,
        "base": 20_800, "min": 14_000, "max": 33_300, "volatility": 0.14,
    },

    # ---------- ⚙️ کارخانه‌ی ذوب‌آهن (نیازمندِ Fonderia) ----------
    "metals": {
        "name": "🪙 فلزات", "factory": "steel", "requires": "fonderia", "tier": 1,
        "raw_cost": 24_000, "produce_hours": 4, "batch": 8,
        "base": 6_000, "min": 4_000, "max": 9_600, "volatility": 0.12,
    },
    "parts": {
        "name": "⚙️ قطعاتِ فلزی", "factory": "steel", "requires": "fonderia", "tier": 2,
        "raw_cost": 28_000, "produce_hours": 6, "batch": 6,
        "base": 9_300, "min": 6_300, "max": 14_900, "volatility": 0.12,
    },
    "armor_plate": {
        "name": "🛡️ ورقِ زرهی", "factory": "steel", "requires": "fonderia", "tier": 3,
        "raw_cost": 56_000, "produce_hours": 8, "batch": 4,
        "base": 28_000, "min": 18_900, "max": 44_800, "volatility": 0.15,
    },

    # ---------- ⚗️ کارخانه‌ی شیمیایی-دارویی (نیازمندِ Fonderia) ----------
    "meds": {
        "name": "💊 دارو", "factory": "chemical", "requires": "fonderia", "tier": 1,
        "raw_cost": 20_000, "produce_hours": 4, "batch": 8,
        "base": 5_000, "min": 3_400, "max": 8_000, "volatility": 0.10,
    },
    "solvent": {
        "name": "🧪 حلالِ صناعی", "factory": "chemical", "requires": "fonderia", "tier": 2,
        "raw_cost": 34_000, "produce_hours": 6, "batch": 6,
        "base": 11_300, "min": 7_600, "max": 18_100, "volatility": 0.12,
    },
    "explosive": {
        "name": "🧨 موادِ منفجره", "factory": "chemical", "requires": "fonderia", "tier": 3,
        "raw_cost": 60_000, "produce_hours": 9, "batch": 4,
        "base": 30_000, "min": 20_200, "max": 48_000, "volatility": 0.16,
    },
    # ---------- 🏭 ابرکارخانهٔ دون (پرسودترین — گیت ثروت) ----------
    "lux_watch": {
        "name": "⌚ ساعتِ لوکس", "factory": "giga", "requires": "emporio", "tier": 1,
        "raw_cost": 96_000, "produce_hours": 4, "batch": 8,
        # v1.7.8.14 — قیمتِ فروشِ ابرکارخانه ۵ برابر شد (پایه/کف/سقف با هم)
        "base": 160_000, "min": 108_000, "max": 256_000, "volatility": 0.15,
    },
    "smart_gadget": {
        "name": "💻 گجتِ هوشمند", "factory": "giga", "requires": "emporio", "tier": 2,
        "raw_cost": 168_000, "produce_hours": 6, "batch": 6,
        # v1.7.8.14 — قیمتِ فروشِ ابرکارخانه ۵ برابر شد (پایه/کف/سقف با هم)
        "base": 330_000, "min": 222_500, "max": 528_000, "volatility": 0.17,
    },
    "tactical_drone": {
        "name": "🚁 پهپادِ تاکتیکی", "factory": "giga", "requires": "emporio", "tier": 3,
        "raw_cost": 300_000, "produce_hours": 8, "batch": 4,
        # v1.7.8.14 — قیمتِ فروشِ ابرکارخانه ۵ برابر شد (پایه/کف/سقف با هم)
        "base": 750_000, "min": 505_000, "max": 1_200_000, "volatility": 0.20,
    },
}

# محصولاتِ قدیمی که دیگر در کارخانه‌های عادی ساخته نمی‌شوند (فقط برای خواندنِ
# موجودی/قیمتِ باقی‌مانده از نسخه‌های پیشین). «کالای لوکس» به برندسازی رفت.
LEGACY_PRODUCTS = {
    "luxury": {
        "name": "💎 کالای لوکس (قدیمی)", "factory": None, "requires": "fonderia", "tier": 9,
        "raw_cost": 44_000, "produce_hours": 8, "batch": 4,
        "base": 22_000, "min": 14_800, "max": 35_200, "volatility": 0.15,
    },
}


def _brand_products():
    """محصولاتِ بخشِ برندسازی (کلیدهای جدا، نمودارِ قیمتِ جدا)."""
    try:
        from app.data.brands import BRAND_PRODUCTS

        return BRAND_PRODUCTS
    except Exception:   # pragma: no cover
        return {}


def get_product(key):
    """جست‌وجویِ محصول در کارخانه‌های عادی، محصولاتِ قدیمی و محصولاتِ برند."""
    p = PRODUCTS.get(key)
    if p is not None:
        return p
    p = LEGACY_PRODUCTS.get(key)
    if p is not None:
        return p
    return _brand_products().get(key)


def products_of_factory(factory_key):
    """کلیدِ محصولاتِ یک کارخانه‌ی مشخص، به ترتیبِ سطح."""
    items = [(k, p) for k, p in PRODUCTS.items() if p.get("factory") == factory_key]
    items.sort(key=lambda kv: kv[1].get("tier", 1))
    return [k for k, _ in items]


def factory_build_cost(product_key):
    p = get_product(product_key) or {}
    return int(p.get("raw_cost", 0)) * BUILD_COST_MULT


def factory_upgrade_cost(current_level):
    return 80_000 * (2 ** (max(1, int(current_level)) - 1))


def production_units(product_key, level):
    p = get_product(product_key) or {}
    return int(p.get("batch", 0)) * max(1, int(level))


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


def _next_price(product_key, prev):
    p = get_product(product_key)
    if not p:
        return prev
    v = p["volatility"]
    noise = random.uniform(-v, +v)
    drift = (p["base"] - prev) / p["base"] * 0.05
    nxt = prev * (1 + drift + noise)
    return round(_clamp(nxt, p["min"], p["max"]), 2)


def initial_price(product_key):
    p = get_product(product_key) or {"base": 100}
    return float(p["base"])


def heal_price(product_key, price, history, history_len=None):
    """قیمتِ ذخیره‌شده در دیتابیس را با بازه‌ی فعلیِ کد هماهنگ می‌کند.

    وقتی base/min/max یک محصول در کد عوض می‌شود، ردیفِ قدیمیِ جدولِ
    market_prices بیرون از بازه‌ی جدید باقی می‌مانَد و کاربر قیمتِ اشتباه
    می‌بیند. این تابع قیمتِ بیرون‌ازبازه را به «پایه»ی جدید برمی‌گردانَد و
    مقادیرِ بیرون‌ازبازه را از تاریخچه پاک می‌کند تا نمودار هم درست شود.

    در حالتِ عادی (قیمت داخلِ بازه) هیچ تغییری نمی‌دهد و changed=False است.

    خروجی: (price, history, changed)
    """
    p = get_product(product_key)
    if not p:
        return price, list(history or []), False
    try:
        lo = float(p["min"])
        hi = float(p["max"])
        base = float(p["base"])
    except (KeyError, TypeError, ValueError):
        return price, list(history or []), False
    if lo > hi:
        lo, hi = hi, lo
    limit = int(history_len or HISTORY_LEN)
    changed = False

    try:
        cur = float(price)
    except (TypeError, ValueError):
        cur, changed = base, True
    if cur < lo or cur > hi:
        cur, changed = _clamp(base, lo, hi), True

    clean = []
    for v in (history or []):
        try:
            fv = float(v)
        except (TypeError, ValueError):
            changed = True
            continue
        if lo <= fv <= hi:
            clean.append(round(fv, 2))
        else:
            changed = True
    if not clean:
        clean = [round(cur, 2)]
    if len(clean) > limit:
        clean, changed = clean[-limit:], True
    return round(cur, 2), clean, changed


def advance_price(product_key, prev_price, history, ticks):
    price = prev_price
    hist = list(history)
    for _ in range(min(ticks, MAX_TICKS_PER_REFRESH)):
        price = _next_price(product_key, price)
        hist.append(price)
    hist = hist[-HISTORY_LEN:]
    return price, hist


def ticks_elapsed(updated_at, now):
    if updated_at is None:
        return 0
    minutes = (now - updated_at).total_seconds() / 60.0
    return int(minutes // PRICE_TICK_MINUTES)


_SPARK = "▁▂▃▄▅▆▇█"


def sparkline(values):
    if not values:
        return "—"
    lo, hi = min(values), max(values)
    if hi - lo < 1e-9:
        return _SPARK[0] * len(values)
    out = []
    for x in values:
        idx = int((x - lo) / (hi - lo) * (len(_SPARK) - 1))
        out.append(_SPARK[idx])
    return "".join(out)


def price_arrow(history):
    if len(history) < 2:
        return "➡️"
    if history[-1] > history[-2]:
        return "📈"
    if history[-1] < history[-2]:
        return "📉"
    return "➡️"
