# -*- coding: utf-8 -*-
"""داده‌هایِ «اشتراکِ ۴ سطحی» (مرحله ۲۰).

منطقِ خالص (بدونِ دیتابیس) — تعریفِ چهار سطحِ اشتراک و مزایای هر کدام.
free رایگان است؛ سه سطحِ پولی: bronze < silver < gold.
"""

SUBSCRIPTION_DAYS = 30          # مدتِ هر دوره‌ی اشتراک (روز)

TIER_ORDER = ["free", "bronze", "silver", "gold"]

TIERS = {
    "free": {
        "key": "free",
        "name": "رایگان",
        "emoji": "⚪",
        "price": 0,
        "rank": 0,
        "income_pct": 0,
        "discount_pct": 0,
        "bank_bonus_pct": 0,
        "xp_bonus_pct": 0,
        "custom_title": False,
        "news_priority": False,
        "perks": ["دسترسیِ پایه به همه‌ی بخش‌های بازی"],
    },
    "bronze": {
        "key": "bronze",
        "name": "برنزی",
        "emoji": "🥉",
        "price": 2_000_000,
        "rank": 1,
        "income_pct": 5,
        "discount_pct": 5,
        "bank_bonus_pct": 2,
        "xp_bonus_pct": 0,
        "custom_title": False,
        "news_priority": False,
        "perks": [
            "+۵٪ درآمدِ روزانه",
            "۵٪ تخفیف در خریدها",
            "+۲٪ سودِ بانکی",
            "📣 امکانِ اعلامِ آنلاین، فقط همراهِ لقبِ فعال",
        ],
    },
    "silver": {
        "key": "silver",
        "name": "نقره‌ای",
        "emoji": "🥈",
        "price": 6_000_000,
        "rank": 2,
        "income_pct": 12,
        "discount_pct": 10,
        "bank_bonus_pct": 5,
        "xp_bonus_pct": 10,
        "custom_title": False,
        "news_priority": True,
        "perks": [
            "+۱۲٪ درآمدِ روزانه",
            "۱۰٪ تخفیف در خریدها",
            "+۵٪ سودِ بانکی",
            "✨ +۱۰٪ بونس XP در فعالیت‌های بازی",
            "📰 دریافتِ زودهنگامِ اخبارِ روزانه",
            "📣 امکانِ اعلامِ آنلاین، فقط همراهِ لقبِ فعال",
        ],
    },
    "gold": {
        "key": "gold",
        "name": "طلایی",
        "emoji": "🥇",
        "price": 16_000_000,
        "rank": 3,
        "income_pct": 25,
        "discount_pct": 15,
        "bank_bonus_pct": 10,
        "xp_bonus_pct": 20,
        "custom_title": True,
        "news_priority": True,
        "perks": [
            "+۲۵٪ درآمدِ روزانه",
            "۱۵٪ تخفیف در خریدها",
            "+۱۰٪ سودِ بانکی",
            "✨ +۲۰٪ بونس XP در فعالیت‌های بازی",
            "🏷️ لقبِ سفارشیِ اختصاصی",
            "🤖 فعال‌سازی و شخصی‌سازیِ دستیار دوم",
            "📣 امکانِ اعلامِ آنلاین، فقط همراهِ لقبِ فعال",
            "📰 دریافتِ زودهنگامِ اخبارِ روزانه",
        ],
    },
}


def get_tier(key: str) -> dict:
    """دیکشنریِ سطح؛ اگر نامعتبر باشد free برمی‌گردد."""
    return TIERS.get(key or "free", TIERS["free"])


def tier_rank(key: str) -> int:
    return get_tier(key)["rank"]


def paid_tiers() -> list:
    """فهرستِ سطوحِ پولی (به ترتیبِ رتبه)."""
    return [TIERS[k] for k in TIER_ORDER if TIERS[k]["price"] > 0]


def next_tier(key: str) -> dict | None:
    """سطحِ بالاترِ بعدی یا None."""
    rank = tier_rank(key)
    for k in TIER_ORDER:
        if TIERS[k]["rank"] == rank + 1:
            return TIERS[k]
    return None


def price_of(key: str) -> int:
    return get_tier(key)["price"]


def income_bonus_pct(key: str) -> int:
    return get_tier(key)["income_pct"]


def discount_pct(key: str) -> int:
    return get_tier(key)["discount_pct"]


def bank_bonus_pct(key: str) -> int:
    return get_tier(key)["bank_bonus_pct"]

def xp_bonus_pct(key: str) -> int:
    """بونس XP اشتراک: نقره‌ای ۱۰٪ و طلایی ۲۰٪."""
    return int(get_tier(key).get("xp_bonus_pct", 0) or 0)


def allows_custom_title(key: str) -> bool:
    return bool(get_tier(key)["custom_title"])


def has_news_priority(key: str) -> bool:
    return bool(get_tier(key)["news_priority"])


def apply_discount(key: str, amount: int) -> int:
    """قیمتِ پس از اعمالِ تخفیفِ اشتراک."""
    pct = discount_pct(key)
    return int(round(amount * (100 - pct) / 100))


def apply_income_bonus(key: str, amount: int) -> int:
    """درآمدِ پس از اعمالِ بونوسِ درآمد."""
    pct = income_bonus_pct(key)
    return int(round(amount * (100 + pct) / 100))


def badge(key: str) -> str:
    """نشانِ کوتاهِ سطح (اموجی + نام)."""
    t = get_tier(key)
    return f"{t['emoji']} {t['name']}"


# ------------------------- کدِ پیگیریِ خرید -------------------------
import random as _random

# الفبای خوانا: بدونِ O/0/I/1/L تا اشتباه نشود
_TRACK_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def generate_tracking_code(length: int = 6) -> str:
    """کدِ پیگیریِ کوتاه و خوانا مانندِ SUB-XXXXXX (منطقِ خالص، قابلِ تست)."""
    return "SUB-" + "".join(_random.choice(_TRACK_ALPHABET) for _ in range(length))
