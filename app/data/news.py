# -*- coding: utf-8 -*-
"""داده‌ها و منطقِ خالصِ «اخبارِ روزانه» (مرحله ۲۰).

هر شب ساعتِ ۲۰:۰۰ به وقتِ تهران، خلاصه‌یِ رویدادهایِ مهمِ بازی
(نتیجه‌ی جنگ‌ها، کسبِ القابِ ویژه، رویدادهایِ مهم) منتشر می‌شود.
این فایل فقط منطقِ خالص دارد (بدونِ دیتابیس/ربات) تا تست‌پذیر باشد.
"""
from datetime import datetime, timedelta

try:
    import pytz
    TEHRAN = pytz.timezone("Asia/Tehran")
except Exception:  # pragma: no cover - fallback اگر pytz نباشد
    pytz = None
    TEHRAN = None

from datetime import timezone

POST_HOUR = 20                  # ساعتِ انتشار (به وقتِ تهران)
POST_MINUTE = 0
DIGEST_LOOKBACK_HOURS = 24      # بازه‌ی اخبارِ داخلِ خلاصه
MAX_ITEMS_IN_DIGEST = 30        # حداکثرِ آیتم در هر خلاصه
TEHRAN_OFFSET = timedelta(hours=3, minutes=30)   # fallback: UTC+3:30

DEFAULT_CATEGORY = "event"

# دسته‌هایِ خبر → emoji / label / importance (۱..۳)
CATEGORIES = {
    "war":      {"emoji": "⚔️", "label": "جنگ", "importance": 3},
    "title":    {"emoji": "🏷️", "label": "القاب", "importance": 2},
    "alliance": {"emoji": "🤝", "label": "اتحادیه", "importance": 2},
    "economy":  {"emoji": "💰", "label": "اقتصاد", "importance": 1},
    "event":    {"emoji": "📢", "label": "رویداد", "importance": 1},
}


def category_meta(category: str) -> dict:
    return CATEGORIES.get(category or DEFAULT_CATEGORY, CATEGORIES[DEFAULT_CATEGORY])


def default_importance(category: str) -> int:
    return category_meta(category)["importance"]


def format_item(category: str, text: str) -> str:
    """یک خبر را برای نمایش قالب‌بندی می‌کند."""
    meta = category_meta(category)
    return f"{meta['emoji']} {text}"


def now_tehran(now_utc: datetime | None = None) -> datetime:
    """زمانِ کنونی به وقتِ تهران (طبیعی/naive)."""
    now_utc = now_utc or datetime.utcnow()
    if TEHRAN is not None:
        aware = now_utc.replace(tzinfo=timezone.utc).astimezone(TEHRAN)
        return aware.replace(tzinfo=None)
    return now_utc + TEHRAN_OFFSET


def seconds_until_next_post(now_utc: datetime | None = None) -> int:
    """ثانیه‌های باقی‌مانده تا اولین ۲۰:۰۰ِ بعدی به وقتِ تهران.

    خروجی برای asyncio.sleep است (برحسبِ ثانیه‌ی واقعی).
    """
    now_utc = now_utc or datetime.utcnow()
    teh = now_tehran(now_utc)
    target = teh.replace(hour=POST_HOUR, minute=POST_MINUTE, second=0, microsecond=0)
    if target <= teh:
        target = target + timedelta(days=1)
    delta = target - teh
    return max(1, int(delta.total_seconds()))


def today_label(now_utc: datetime | None = None) -> str:
    """برچسبِ تاریخِ امروز (به وقتِ تهران) — YYYY/MM/DD."""
    teh = now_tehran(now_utc)
    return teh.strftime("%Y/%m/%d")


def compile_digest(items, now_utc: datetime | None = None) -> str:
    """از فهرستی از آیتم‌ها یک متنِ خلاصه‌ی روزانه می‌سازد.

    هر آیتم باید ویژگیِ category و text داشته باشد (مدلِ NewsItem یا دیکشنری).
    آیتم‌ها بر اساسِ importance مرتب می‌شوند.
    """
    label = today_label(now_utc)
    header = f"📰 <b>اخبارِ روزانه‌ی بازی</b> — {label}"
    if not items:
        return header + "\n\nامروز خبرِ مهمی ثبت نشد. 🕊️"

    def _imp(it):
        cat = getattr(it, "category", None) if not isinstance(it, dict) else it.get("category")
        imp = getattr(it, "importance", None) if not isinstance(it, dict) else it.get("importance")
        return imp if imp is not None else default_importance(cat)

    ordered = sorted(items, key=_imp, reverse=True)[:MAX_ITEMS_IN_DIGEST]
    lines = [header, ""]
    for idx, it in enumerate(ordered):
        if isinstance(it, dict):
            cat, text = it.get("category"), it.get("text", "")
        else:
            cat, text = getattr(it, "category", None), getattr(it, "text", "")
        lines.append("• " + format_item(cat, text))
        # 🆕 v1.7.9.1 — خطِ جداکننده بین اخبار
        if idx < len(ordered) - 1:
            lines.append("〰〰〰〰〰〰〰〰")
    lines.append("")
    lines.append(f"🕒 مجموعاً {len(ordered)} خبر در ۲۴ ساعتِ گذشته.")
    return "\n".join(lines)


# --------------------------- صفحه‌بندیِ خلاصه (v1.7.9.1) ---------------------------
DIGEST_PAGE_SIZE = 6


def paginate_items(items, per_page: int = DIGEST_PAGE_SIZE, now_utc: datetime | None = None) -> list[str]:
    """لیستِ آیتم‌ها → صفحه‌های کاملِ خلاصه — اعلامِ تک‌پیامی با دکمه‌های ◀️ ▶️.

    هر خبر با خطِ جداکننده از خبرِ بعدی جدا می‌شود؛ هر صفحه هدر + شماره صفحه دارد.
    """
    label = today_label(now_utc)
    header = f"📰 <b>اخبارِ روزانه‌ی بازی</b> — {label}"
    items = list(items or [])
    if not items:
        return [header + "\n\nامروز خبرِ مهمی ثبت نشد. 🕊️"]

    def _imp(it):
        cat = getattr(it, "category", None) if not isinstance(it, dict) else it.get("category")
        imp = getattr(it, "importance", None) if not isinstance(it, dict) else it.get("importance")
        return imp if imp is not None else default_importance(cat)

    ordered = sorted(items, key=_imp, reverse=True)[:MAX_ITEMS_IN_DIGEST]
    per_page = max(1, int(per_page))
    total_pages = (len(ordered) + per_page - 1) // per_page
    pages: list[str] = []
    for pi in range(total_pages):
        chunk = ordered[pi * per_page:(pi + 1) * per_page]
        lines = [header, f"صفحه‌ی {pi + 1} از {total_pages}", ""]
        for idx, it in enumerate(chunk):
            cat = it.get("category") if isinstance(it, dict) else getattr(it, "category", None)
            text = it.get("text", "") if isinstance(it, dict) else getattr(it, "text", "")
            lines.append("• " + format_item(cat, text))
            if idx < len(chunk) - 1:
                lines.append("〰〰〰〰〰〰〰〰")
        lines.append("")
        lines.append(f"🕒 مجموعاً {len(ordered)} خبر در ۲۴ ساعتِ گذشته.")
        pages.append("\n".join(lines))
    return pages
