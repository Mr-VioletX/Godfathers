# -*- coding: utf-8 -*-
"""دیتا و منطقِ خالصِ سیستمِ ادمین (مرحله ۲۱).

این فایل هیچ وابستگی‌ای به دیتابیس/aiogram ندارد تا کاملاً قابلِ تست باشد:
  • تعریفِ دسترسی‌ها (permission keys) + برچسبِ فارسی + ایموجی
  • دسترسی‌هایی که فقط مخصوصِ ادمینِ اصلی‌اند (MAIN_ONLY)
  • هش کردن/بررسیِ رمز (sha256 + salt)
  • ساختِ رمزِ اولیه‌ی خوانا
  • متنِ راهنمایِ ادمین (متفاوت براساسِ دسترسی)
"""
import hashlib
import hmac
import json
import secrets

# ---------------------------------------------------------------------------
# دسترسی‌ها (Permissions)
# ---------------------------------------------------------------------------
# هر کلید = یک بخشِ پنلِ ادمین. دکمه‌ی هر بخش فقط وقتی نشان داده می‌شود
# که ادمین آن دسترسی را داشته باشد.
PERMISSIONS: dict[str, dict] = {
    "users": {
        "key": "users",
        "emoji": "👥",
        "label": "مدیریتِ کاربران",
        "desc": "لیستِ کاربران، کاربران لقب‌دار، جستجویِ کاربر با یوزرآیدی، دیدنِ پروفایل، محدود/رفعِ محدودیت (بن/آنبن).",
    },
    "economy": {
        "key": "economy",
        "emoji": "💰",
        "label": "اقتصاد و دارایی",
        "desc": "تعیین/افزایش/کاهشِ ثروت (تکی/گروهی/همه)، ریستِ دارایی، ریستِ وام و هدیهٔ پول (تکی/همگانی).",
    },
    "bulk_wealth": {
        "key": "bulk_wealth",
        "emoji": "💰",
        "label": "مدیریت گروهی ثروت (قدیمی)",
        "desc": "تعیین، افزایش یا کاهش ثروت نقدی و سپرده برای چند کاربر منتخب یا همهٔ کاربران.",
    },
    "bulk_levels": {
        "key": "bulk_levels",
        "emoji": "📈",
        "label": "لول و XP",
        "desc": "تعیین، افزایش، کاهش و ریستِ لول و XP برای کاربران و هدیهٔ XP (تکی/همگانی).",
    },
    "assistants": {
        "key": "assistants",
        "emoji": "🤖",
        "label": "کنترل دستیارها",
        "desc": "مدیریت فعال/غیرفعال‌بودن دستیار اول و دستیار دوم و محدودیت دسترسی آن‌ها.",
    },
    "subscriptions": {
        "key": "subscriptions",
        "emoji": "💎",
        "label": "کنترلِ اشتراک‌ها",
        "desc": "فعال/غیرفعال‌کردنِ اشتراکِ کاربران و تأییدِ درخواست‌هایِ خرید.",
    },
    "titles": {
        "key": "titles",
        "emoji": "🏷️",
        "label": "کنترلِ القاب",
        "desc": "صفِ تأیید، اعطا/حذفِ القاب، ارزیابیِ همه، بررسیِ القابِ کاربر و لقبِ سفارشی.",
    },
    "reports": {
        "key": "reports",
        "emoji": "🚨",
        "label": "گزارشات",
        "desc": "دیدنِ گزارش‌هایِ کاربران و فایل‌ها/آرشیوِ چت‌مود.",
    },
    "news": {
        "key": "news",
        "emoji": "📰",
        "label": "اطلاعیه و اخبار",
        "desc": "ثبتِ خبرِ دستی و انتشارِ فوریِ دایجست.",
    },
    "broadcast": {
        "key": "broadcast",
        "emoji": "📢",
        "label": "پیامِ همگانی",
        "desc": "ارسالِ پیام به همه‌ی کاربرانِ ثبت‌شده.",
    },
    "stats": {
        "key": "stats",
        "emoji": "📊",
        "label": "آمارِ بازی",
        "desc": "دیدنِ آمارِ کلیِ بازی (تعدادِ کاربران، اشتراک‌ها و ...).",
    },
    # 🆕 مرحله ۲۷ — رویدادهایِ بونس (قابلِ واگذاری به ادمینِ فرعی)
    "events": {
        "key": "events",
        "emoji": "🎉",
        "label": "رویدادهایِ بونس",
        "desc": "فعال/غیرفعال‌کردنِ بونسِ XP و بونسِ پول (اونتِ دلخواه) با ضریب و مدتِ مشخص.",
    },
    # 🆕 v1.7.8.2 — کنترلِ بانک و گاوصندوق
    "worldbank": {
        "key": "worldbank",
        "emoji": "🏦",
        "label": "بانک و گاوصندوق",
        "desc": "درصدِ محافظتِ سپرده در جنگ، هزینه و سقفِ گاوصندوق و ریستِ وام.",
    },
    # 🆕 v1.7.8.14 — بخش‌هایی که تا حالا فقط داخلِ «ابزارهایِ ویژه» دفن شده بودند
    # و چون tools جزو MAIN_ONLY است، هیچ‌وقت قابلِ واگذاری به ادمینِ فرعی نبودند.
    # حالا مجوزِ مستقل دارند. توجه: هیچ‌کدام به کسی خودکار داده نمی‌شود؛
    # ادمینِ اصلی مثل قبل همه را دارد و ادمینِ فرعی فقط اگر صریحاً بهش بدهی.
    "force_join": {
        "key": "force_join",
        "emoji": "🔒",
        "label": "جوینِ اجباری",
        "desc": "روشن/خاموش‌کردنِ جوینِ اجباری، افزودن/حذفِ کانال و تنظیمِ لینکِ عضویت.",
    },
    "sections_control": {
        "key": "sections_control",
        "emoji": "🛑",
        "label": "کنترلِ بخش‌ها",
        "desc": "خاموش/روشن‌کردنِ موقتِ بخش‌هایِ بازی برای یک کاربر یا همه (مهارِ باگ).",
    },
    "game_settings": {
        "key": "game_settings",
        "emoji": "⚙️",
        "label": "تنظیماتِ عددیِ بازی",
        "desc": "سقفِ درآمدِ شهر، ضریب‌هایِ اقتصادِ شهر، سقفِ شهرتِ برند، ظرفیتِ سربازخانه، ابرکارخانه، تولیدِ شهر و دستگیری.",
    },
    "ranking_ctrl": {
        "key": "ranking_ctrl",
        "emoji": "🏆",
        "label": "کنترلِ رنکینگ",
        "desc": "روشن/خاموش‌کردنِ گزینه‌هایِ رنکینگ در منویِ بازیکن‌ها.",
    },
    "referral": {
        "key": "referral",
        "emoji": "🔗",
        "label": "پاداشِ لینکِ دعوت",
        "desc": "فعال/غیرفعال‌کردنِ پاداشِ پولی و بونسِ درآمدِ دعوت و تعیینِ مقدارِ آن‌ها.",
    },
    "activity": {
        "key": "activity",
        "emoji": "🕘",
        "label": "فعالیتِ کاربران",
        "desc": "دیدنِ فعالیتِ ۲۴ ساعتِ اخیرِ بازیکن‌ها و فعالیتِ یک کاربرِ خاص با آیدی.",
    },
    # ⬇️ فقط ادمینِ اصلی (MAIN_ONLY)
    "backup": {
        "key": "backup",
        "emoji": "💾",
        "label": "بکاپِ دیتابیس",
        "desc": "تنظیمِ کانالِ بکاپ، فاصلهٔ خودکار و گرفتنِ بکاپِ فوری (فقط ادمینِ اصلی).",
    },
    "tools": {
        "key": "tools",
        "emoji": "🧰",
        "label": "ابزارهایِ ویژه",
        "desc": "ریست و نگهداری (ریستِ کاملِ کاربر، حذف، ریستِ مسابقات/نیروها، تکمیلِ صف‌ها) و تنظیماتِ بازی (فقط ادمینِ اصلی).",
    },
    "channel": {
        "key": "channel",
        "emoji": "📡",
        "label": "کانالِ گزارش",
        "desc": "انتخاب/حذف/تعویضِ کانالِ خصوصیِ دریافتِ فایل‌هایِ چت‌مود (فقط ادمینِ اصلی).",
    },
    "admins": {
        "key": "admins",
        "emoji": "👑",
        "label": "مدیریتِ ادمین‌ها",
        "desc": "انتصاب/عزلِ ادمین، ویرایشِ دسترسی‌ها و ساختِ رمزِ اولیه (فقط ادمینِ اصلی).",
    },
}

# ترتیبِ نمایشِ دکمه‌ها در پنل
# 🐞 v1.7.8.14 — سه دسترسیِ «bulk_wealth»، «broadcast» و «channel» در PERMISSIONS
# تعریف شده بودند اما در این لیست نبودند. چون هم admin_home_kb و هم
# normalize_perms فقط روی همین لیست حلقه می‌زنند، آن سه بخش نه هرگز دکمه
# داشتند (حتی برای ادمینِ اصلی) و نه هرگز قابلِ واگذاری بودند — عملاً مرده.
PERMISSION_ORDER = [
    # کاربران و اقتصاد
    "users", "economy", "bulk_wealth", "bulk_levels", "worldbank",
    # محتوا و ارتباط با کاربر
    "assistants", "subscriptions", "titles", "news", "broadcast", "reports",
    # آمار، رویداد و فعالیت
    "stats", "events", "activity",
    # 🆕 v1.7.8.14 — بخش‌هایی که تا حالا داخلِ «ابزارهایِ ویژه» قفل بودند
    "force_join", "sections_control", "game_settings", "ranking_ctrl", "referral",
    # فقط ادمینِ اصلی
    "channel", "backup", "admins", "tools",
]

# دسترسی‌هایی که هرگز قابلِ واگذاری به ادمینِ فرعی نیستند (فقط ادمینِ اصلی):
# backup عمداً اینجاست: خروجی‌اش یک نسخهٔ کامل از دیتابیسِ بازی است.
MAIN_ONLY = {"channel", "admins", "tools", "backup"}

# 🛡️ v1.7.8.14 — تورِ ایمنی: اگر بعداً کلیدِ جدیدی به PERMISSIONS اضافه شود و
# یادمان برود در PERMISSION_ORDER بنویسیم، دیگر بی‌صدا ناپدید نمی‌شود
# (دقیقاً باگی که broadcast/channel/bulk_wealth را مرده کرده بود).
for _k in list(PERMISSIONS):
    if _k not in PERMISSION_ORDER:
        PERMISSION_ORDER.append(_k)

# دسترسی‌هایی که ادمینِ اصلی می‌تواند به دیگران بدهد:
GRANTABLE = [k for k in PERMISSION_ORDER if k not in MAIN_ONLY]


# ---------------------------------------------------------------------------
# 🆕 v1.7.8.15 — ساختارِ درختیِ منو
#
# در v1.7.8.14 هر ۲۳ دسترسی یک دکمه‌ی مستقل در خانه‌ی پنل گرفت و پنل
# خیلی شلوغ شد. حالا فقط بخش‌هایِ اصلی در خانه می‌مانند (مثلِ استایلِ قبل) و
# بقیه به‌صورتِ «زیرمنو» داخلِ منویِ مرتبطِ خودشان نشان داده می‌شوند.
#
# ⚠️ PERMISSION_ORDER / GRANTABLE / MAIN_ONLY دست‌نخورده‌اند؛ یعنی منطقِ
#    واگذاریِ دسترسی به ادمینِ فرعی هیچ تغییری نکرده و فقط «جایِ دکمه» عوض شده.
# ---------------------------------------------------------------------------
SUBSECTIONS: dict[str, list[str]] = {
    "users": ["bulk_wealth", "bulk_levels"],
    "economy": ["game_settings"],
    "news": ["broadcast"],
    "reports": ["activity"],
    "stats": ["ranking_ctrl"],
    "channel": ["force_join"],
    "tools": ["sections_control", "referral", "backup"],
}

PARENT_OF: dict[str, str] = {
    child: parent for parent, kids in SUBSECTIONS.items() for child in kids
}

# خانه‌ی پنل = هر دسترسی‌ای که والد ندارد (۱۳ بخش)
HOME_ORDER: list[str] = [k for k in PERMISSION_ORDER if k not in PARENT_OF]


def children_of(key: str) -> list[str]:
    """زیرمنوهایِ یک بخش."""
    return list(SUBSECTIONS.get(key, ()))


def parent_of(key: str) -> str | None:
    """والدِ یک زیرمنو (اگر زیرمنو باشد)."""
    return PARENT_OF.get(key)


def can_see_section(key: str, perms, is_main: bool) -> bool:
    """آیا این بخش برایِ ادمین قابلِ دیدن است؟

    یا خودش دسترسی دارد، یا دستِ‌کم به یکی از زیرمنوهایش دسترسی دارد
    (وگرنه ادمینی که فقط «جوینِ اجباری» را دارد هیچ راهی به آن نداشت).
    """
    if is_main or key in perms:
        return True
    return any(c in perms for c in SUBSECTIONS.get(key, ()))


def home_sections(perms, is_main: bool) -> list[str]:
    """بخش‌هایی که در خانه‌ی پنل دکمه دارند."""
    return [k for k in HOME_ORDER if can_see_section(k, perms, is_main)]


def perm(key: str) -> dict | None:
    return PERMISSIONS.get(key)


def perm_label(key: str) -> str:
    p = PERMISSIONS.get(key)
    return f"{p['emoji']} {p['label']}" if p else key


def is_valid_perm(key: str) -> bool:
    return key in PERMISSIONS


def normalize_perms(perms) -> list[str]:
    """ورودی را به لیستِ کلیدهایِ معتبر، یکتا و مرتّب تبدیل می‌کند."""
    if not perms:
        return []
    if isinstance(perms, str):
        try:
            perms = json.loads(perms)
        except Exception:
            perms = [p.strip() for p in perms.replace(";", ",").split(",")]
    seen = []
    for k in perms:
        k = str(k).strip()
        if k in PERMISSIONS and k not in seen:
            seen.append(k)
    return [k for k in PERMISSION_ORDER if k in seen]


def dumps_perms(perms) -> str:
    return json.dumps(normalize_perms(perms))


# ---------------------------------------------------------------------------
# رمزِ عبور (هش + salt) — بدونِ وابستگیِ خارجی
# ---------------------------------------------------------------------------
def hash_password(password: str, salt: str | None = None) -> str:
    """رمز را با saltِ تصادفی هش می‌کند. خروجی: "<salt>$<hex>"."""
    salt = salt or secrets.token_hex(8)
    digest = hashlib.sha256((salt + ":" + (password or "")).encode("utf-8")).hexdigest()
    return f"{salt}${digest}"


def verify_password(password: str, stored: str | None) -> bool:
    if not stored or "$" not in stored:
        return False
    salt, _, digest = stored.partition("$")
    check = hashlib.sha256((salt + ":" + (password or "")).encode("utf-8")).hexdigest()
    return hmac.compare_digest(check, digest)


# الفبایِ خوانا (بدونِ O/0/I/1/l) برای رمزِ اولیه
_PW_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789"


def generate_initial_password(length: int = 8) -> str:
    """رمزِ اولیه‌ی تصادفیِ خوانا (منطقِ خالص، قابلِ تست)."""
    return "".join(secrets.choice(_PW_ALPHABET) for _ in range(max(4, length)))


# حداقلِ طولِ رمزِ جدیدِ انتخابیِ ادمین
MIN_PASSWORD_LEN = 4


def password_ok(pw: str) -> tuple[bool, str]:
    pw = (pw or "").strip()
    if len(pw) < MIN_PASSWORD_LEN:
        return False, f"رمز باید حداقل {MIN_PASSWORD_LEN} کاراکتر باشد."
    if len(pw) > 64:
        return False, "رمز خیلی بلند است (حداکثر ۶۴ کاراکتر)."
    if "\n" in pw or " " in pw:
        return False, "رمز نباید فاصله یا خطِ جدید داشته باشد."
    # 🆕 رمز حتماً باید فقط انگلیسی/ASCII باشد (نه فارسی/یونیکد) تا موقعِ ذخیره‌سازی/مقایسه‌ی هش
    # دچارِ خطا نشود.
    if not pw.isascii():
        return False, "رمز باید فقط با حروف/اعدادِ انگلیسی نوشته شود (فارسی یا هر کاراکترِ غیرانگلیسی مجاز نیست)."
    return True, pw


# ---------------------------------------------------------------------------
# راهنمایِ ادمین (متفاوت براساسِ دسترسی)
# ---------------------------------------------------------------------------
# کلماتِ ورود/خروج و راهنما (فقط متنی — دکمه ندارند)
ENTER_WORDS = {"ادمین مود", "ادمین‌مود", "حالت ادمین", "admin", "adminmode"}
EXIT_WORDS = {
    "خروج از حالت ادمین مود",
    "خروج از حالتِ ادمین مود",
    "خروج از حالت ادمین‌مود",
    "خروج از ادمین مود",
    "خروج از ادمین‌مود",
    "خروج ادمین",
}
HELP_ADMIN_WORDS = {"راهنمای ادمین", "راهنمای ادمین‌ها", "راهنمای ادمینها"}
HELP_MAIN_WORDS = {"راهنمای ادمین اصلی", "راهنمای ادمینِ اصلی"}
# 🆕 فقط ادمینِ اصلی: بازنشانیِ رمزِ ورود از مقدارِ ADMIN_PASSWORD در فایلِ .env
SYNC_PW_WORDS = {"همگام‌سازی رمز از فایل", "همگام سازی رمز از فایل", "ریست رمز از فایل"}
# 🆕 کلماتی که درهر مرحله‌ی ورود/تعیینِ رمز اگر فرستاده شوند، عملیات لغو می‌شود
# و دیگر رمز خواسته نمی‌شود.
CANCEL_WORDS = {"انصراف", "لغو", "/cancel"}


# 🆕 مرحله ۲۷ — پیامِ یکدستِ «دسترسی نداری» (رفعِ باگِ سطحِ دسترسیِ ادمینِ فرعی:
# دیگر هیچ دکمه‌یِ خارج از دسترسی نمایش داده نمی‌شود و هر مرحله‌یِ فرم هم دوباره چک می‌شود)
def denied_text(perm_key: str) -> str:
    p = PERMISSIONS.get(perm_key)
    if p:
        return f"⛔ دسترسیِ «{p['emoji']} {p['label']}» را نداری. از ادمینِ اصلی بخواه دسترسی بدهد."
    return "⛔ دسترسی نداری."


def help_text(is_main: bool, perms: list[str]) -> str:
    """متنِ راهنما — برای ادمینِ اصلی کامل، برای فرعی فقط بخش‌هایِ مجاز."""
    lines: list[str] = []
    if is_main:
        lines.append("👑 <b>راهنمایِ ادمینِ اصلی (خدایِ بازی)</b>")
        lines.append("")
        lines.append("تو به همه‌ی بخش‌ها دسترسیِ کامل داری. فهرستِ توانایی‌ها:")
        keys = PERMISSION_ORDER
    else:
        lines.append("🛡️ <b>راهنمایِ ادمین</b>")
        lines.append("")
        if perms:
            lines.append("تو به بخش‌هایِ زیر دسترسی داری:")
        else:
            lines.append("فعلاً هیچ دسترسیِ فعالی نداری؛ از ادمینِ اصلی بخواه دسترسی بدهد.")
        keys = perms
    for k in keys:
        p = PERMISSIONS.get(k)
        if p:
            lines.append(f"• {p['emoji']} <b>{p['label']}</b> — {p['desc']}")
    lines.append("")
    lines.append("ℹ️ کلماتِ متنی: ورود با «ادمین مود»، خروج با «خروج از حالت ادمین مود».")
    if is_main:
        lines.append("ℹ️ راهنمایِ کاملِ خودرا با «راهنمای ادمین اصلی» ببین (فقط در حالتِ ادمین).")
    else:
        lines.append("ℹ️ راهنما را با «راهنمای ادمین» دوباره ببین (فقط در حالتِ ادمین).")
    return "\n".join(lines)
