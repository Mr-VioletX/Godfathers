# -*- coding: utf-8 -*-
"""v1.7.6 — فهرست منابع XP برای راهنمای کاربران."""

XP_SOURCES = [
    ("دزدی موفق", "theft", "بسته به نوع دزدی"),
    ("جنگ (پیروزی)", "war", "حدود ۱۴–۴۲+ بر اساس نسبت قدرت"),
    ("ورزش / ارتقای تیم", "sports_upgrade", "متغیر"),
    ("ساخت پایگاه", "base_buy", "۱۰۰"),
    ("ارتقای پایگاه", "base_upgrade", "متغیر با سطح"),
    ("ارتقا سطح پایگاه", "base_tierup", "۵۰–۴۰۰"),
    ("ساخت کارخانه", "factory_build", "۱۵–۲۵۰"),
    ("گسترش کارخانه", "factory_expand", "۸–۱۵۰"),
    ("ارتقای کارخانه", "factory_upgrade", "متغیر"),
    ("تولید/جمع‌آوری کارخانه", "factory_produce", "بر اساس واحد"),
    ("فروش محصول کارخانه", "factory_sell", "بر اساس واحد"),
    ("ساخت انبار اصلی", "warehouse_build", "۱۲۵"),
    ("ارتقای انبار", "warehouse_upgrade", "متغیر"),
    ("فروش از انبار", "warehouse_sell", "متغیر"),
    ("ثبت برند", "brand_found", "۲۵۰"),
    ("ارتقای برند", "brand_upgrade", "متغیر"),
    ("کمپین تبلیغاتی", "brand_campaign", "۸–۱۵۰"),
    ("خرید شرکت برند", "brand_company_buy", "۱۰–۲۵۰"),
    ("گسترش/ارتقای شرکت برند", "brand_company_expand / upgrade", "متغیر"),
    ("خرید/ارتقای هولدینگ", "holding_*", "متغیر"),
    ("تأسیس اتحادیه", "alliance_found", "۲۵۰"),
    ("ارتقای اتحادیه", "alliance_upgrade", "۱۰–۱۵۰"),
    ("تأسیس/ارتقای عمارت", "estate_*", "۱۵۰–۵۰۰"),
    ("استخدام حرفه‌ای", "hire_professional", "متغیر"),
    ("جمع‌آوری درآمد عمارت", "estate_collect_all", "۵–۲۰۰"),
    ("خرید/ارتقای نظامی", "military_buy / upgrade", "متغیر"),
    ("استخدام/ارتقای جاسوس", "spy_hire / spy_upgrade", "متغیر"),
    ("ارتقای کاپاتولو", "kapatolo_upgrade", "متغیر"),
    ("ارتقای دستیار", "assistant_upgrade", "متغیر"),
    ("اشتراک لقب سفارشی", "titles_subscription", "۱۵۰"),
]

# بونس‌ها
XP_BONUSES = [
    "اشتراک نقره‌ای: +۱۰٪ XP",
    "اشتراک طلایی: +۲۰٪ XP",
    "رویداد ادمین (بونس XP): ضریب اعلام‌شده",
]


def guide_text() -> str:
    lines = ["⭐ <b>منابع کسب XP</b>", ""]
    for name, key, approx in XP_SOURCES:
        lines.append(f"• <b>{name}</b> — {approx}")
    lines += ["", "✨ <b>بونس‌ها</b>"]
    for b in XP_BONUSES:
        lines.append(f"• {b}")
    lines.append("\nهمه XP از مسیر مرکزی leveling عبور می‌کند (سقف سطح ۵۰).")
    return "\n".join(lines)
