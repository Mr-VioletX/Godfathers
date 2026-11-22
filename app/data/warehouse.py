# app/data/warehouse.py
"""انبارِ اصلی (مرحله ۱۵).

پیش‌نیاز: داشتنِ دست‌کم ۳ کارخانه.
مزایا: حجمِ بیشتر + امنیتِ بالاتر در برابرِ غارتِ جاسوس نسبت به انبارِ کارخانه.
توابعِ خالص (pure) — قابلِ تست.
"""
REQUIRED_FACTORIES = 3          # پیش‌نیازِ ساخت
BUILD_COST = 1_000_000           # هزینه‌ی ساختِ انبارِ اصلی
MAX_LEVEL = 50

BASE_VOLUME = 2_000            # ظرفیتِ کلِ انبار در سطح ۱
VOLUME_PER_LEVEL = 2_000       # (قدیمی — دیگر مستقیم استفاده نمی‌شود)
MAX_VOLUME = 1_000_000         # 🆕 v1.7.8.17 — حجمِ نهاییِ انبارِ اصلی در سطحِ ۵۰

# امنیت در برابرِ غارتِ جاسوس (بیشتر از انبارِ کارخانه)
BASE_SECURITY = 0.50          # ۵۰٪ محافظت در سطح ۱
SECURITY_PER_LEVEL = 0.05     # هر سطح +۵٪
SECURITY_CAP = 0.90


def warehouse_volume(level):
    """🆕 v1.7.8.17 — حجمِ انبارِ اصلی.

    سقفِ نهایی از ۱۰۰٬۰۰۰ به ۱٬۰۰۰٬۰۰۰ واحد رسید و سطح‌هایِ میانی
    بینِ حجمِ پایه (سطح ۱) و همین سقفِ جدید (سطح ۵۰) خطی
    درون‌یابی می‌شوند (گرد‌شده به صدتایی).
    """
    lvl = max(1, min(MAX_LEVEL, int(level or 1)))
    if MAX_LEVEL <= 1:
        return BASE_VOLUME
    span = MAX_VOLUME - BASE_VOLUME
    raw = BASE_VOLUME + span * (lvl - 1) / float(MAX_LEVEL - 1)
    return int(round(raw / 100.0) * 100)


def warehouse_security(level):
    """نسبتِ محافظت در برابرِ غارتِ جاسوس (۰..۰.۹)."""
    return min(SECURITY_CAP, BASE_SECURITY + SECURITY_PER_LEVEL * (level - 1))


UPGRADE_BASE_COST = 6_000        # ۴۶: ۱۰۰ برابر ارزان‌تر از قبل (۶۰۰k)
UPGRADE_GROWTH = 1.50
UPGRADE_COST_CAP = 1_000_000_000_000   # سقفِ نهایی: ۱ تریلیارد


def upgrade_cost(level):
    """هزینه‌ی ارتقا از لولِ فعلی به بعدی (سقف: ۱ تریلیارد)."""
    lvl = max(1, int(level or 1))
    return int(min(UPGRADE_COST_CAP, UPGRADE_BASE_COST * (UPGRADE_GROWTH ** (lvl - 1))))


def can_build(factory_count):
    return factory_count >= REQUIRED_FACTORIES
