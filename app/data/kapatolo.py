# -*- coding: utf-8 -*-
"""مرحله ۱۶ — بخشِ «کول‌داونِ دزدی» در عمارتِ کاپولا + پایگاه‌های پساکاپولا.

این ماژول سه چیز را تعریف می‌کند:
  1) کول‌داونِ بینِ دزدی‌ها که با ارتقای بخشی از کاپولا از ۵ دقیقه تا ۲ دقیقه کم می‌شود (۲۰ لِوِل).
  2) انتقالِ ویژگی‌هایِ مثبتِ پایگاهِ تخصصیِ تیرِ ۴ به کاپولا (پیام و توضیح).
  3) چهار «پایگاهِ پساکاپولا» با نام‌های تازه که فقط روی درآمدِ کاپولا اثر می‌گذارند
     و پیش‌نیازِ ساختِ عمارت‌های بعدی‌اند (برای تمایز از پایگاه‌های اولیه در کد).
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# ۱) کول‌داونِ دزدی — بخشی از عمارتِ کاپولا
# ---------------------------------------------------------------------------
KAPATOLO_COOLDOWN_MAX_LEVEL = 20   # ۲۰ لِوِل
COOLDOWN_BASE_MIN = 2.0            # دقیقه در لِوِل ۰ (پیش از ارتقا)
COOLDOWN_FLOOR_MIN = 1.0           # دقیقه در لِوِلِ مکس


def cooldown_seconds(cd_level: int) -> int:
    """طولِ کول‌داونِ دزدی (ثانیه) بر اساسِ لِوِلِ بخشِ کول‌داونِ کاپولا."""
    lvl = max(0, min(KAPATOLO_COOLDOWN_MAX_LEVEL, int(cd_level or 0)))
    span = COOLDOWN_BASE_MIN - COOLDOWN_FLOOR_MIN            # ۱ دقیقه
    minutes = COOLDOWN_BASE_MIN - span * (lvl / KAPATOLO_COOLDOWN_MAX_LEVEL)
    return int(round(minutes * 60))


def cooldown_minutes(cd_level: int) -> float:
    return round(cooldown_seconds(cd_level) / 60, 2)


# 🆕 مرحله ۳۰ — نمایشِ کول‌داون به صورتِ دقیقه و ثانیه (نه اعشاریِ دقیقه)
def fmt_mmss(total_seconds) -> str:
    """۱۸۰ ثانیه ← «۳ دقیقه و ۰ ثانیه» / ۱۶۵ ← «۲ دقیقه و ۴۵ ثانیه»"""
    total = max(0, int(round(float(total_seconds or 0))))
    m, s = divmod(total, 60)
    if m and s:
        return f"{m} دقیقه و {s} ثانیه"
    if m:
        return f"{m} دقیقه"
    return f"{s} ثانیه"


def cooldown_mmss(cd_level: int) -> str:
    """کول‌داونِ دزدی به صورتِ «دقیقه و ثانیه»."""
    return fmt_mmss(cooldown_seconds(cd_level))


def cooldown_saving_mmss(cd_level: int) -> str:
    """مقدارِ کاهشِ زمان نسبت به لِوِلِ ۰ (دقیقه و ثانیه)."""
    return fmt_mmss(cooldown_seconds(0) - cooldown_seconds(cd_level))


def cooldown_upgrade_cost(cd_level: int) -> int:
    """هزینه‌ی ارتقای بخشِ کول‌داون از لِوِلِ فعلی به بعدی."""
    return 200_000 * (int(cd_level or 0) + 1)


# ---------------------------------------------------------------------------
# ۲) پیام/توضیحِ تبدیلِ پایگاهِ تخصصی → کاپولا
# ---------------------------------------------------------------------------
CUPOLA_BUILT_MESSAGE = (
    "🏛️ <b>تو عمارتِ کاپولا را ساختی!</b>\n"
    "تمامِ ویژگی‌هایِ مثبتِ پایگاهِ تخصصی (مخفی‌کاری، خزانه، بازیابی) اکنون به کاپولا منتقل شده و فقط همان اعمال می‌شود.\n"
    "پایگاه‌هایی که بعد می‌سازی دیگر اثرِ جداگانه روی دزدی ندارند؛ فقط روی درآمدِ کاپولا اثر می‌گذارند و با ارتقایشان از پایگاه به عمارت، می‌توانی عمارت‌هایِ دیگر را بسازی."
)


# ---------------------------------------------------------------------------
# ۳) چهار پایگاهِ پساکاپولا (نام‌های تازه؛ فقط روی درآمدِ کاپولا اثر دارند)
#    order → ترتیب | income_pct → درصدِ افزایشِ درآمدِ کاپولا به‌ازای هر لِوِلِ پایگاه
#    becomes → کلیدِ عمارتی که با ارتقای این پایگاه ساخته می‌شود (اثرِ درآمدی برداشته می‌شود)
# ---------------------------------------------------------------------------
POST_KAPATOLO_BASES = {
    "tenuta": {
        "key": "tenuta", "order": 1, "name": "🍇 Tenuta (تنوتا / ملکِ روستایی)",
        "build_cost": 400_000, "income_pct": 0.05, "becomes": "fortezza",
    },
    "cantina": {
        "key": "cantina", "order": 2, "name": "🍾 Cantina (کانتینا / سردابِ شراب)",
        "build_cost": 600_000, "income_pct": 0.06, "becomes": "emporio",
    },
    "darsena": {
        "key": "darsena", "order": 3, "name": "⚓ Darsena (دارسنا / اسکلهٔ خصوصی)",
        "build_cost": 800_000, "income_pct": 0.07, "becomes": "porto_nero",
    },
    "foresteria": {
        "key": "foresteria", "order": 4, "name": "🏨 Foresteria (فورستریا / مهمان‌سرا)",
        "build_cost": 1_000_000, "income_pct": 0.08, "becomes": "banco",
    },
}


def get_post_base(key: str):
    return POST_KAPATOLO_BASES.get(key)


def post_base_income_line(key: str, level: int) -> str | None:
    b = POST_KAPATOLO_BASES.get(key)
    if not b:
        return None
    return f"{b['name']}: +{b['income_pct'] * level * 100:.0f}٪ درآمدِ کاپولا"
