# -*- coding: utf-8 -*-
"""کیبوردهایِ پنلِ ادمین (مرحله ۲۱).

نکته‌یِ مهم: دکمه‌یِ هر بخش فقط وقتی ساخته می‌شود که ادمین آن دسترسی را داشته باشد؛
پس هیچ دکمه‌یِ «قفل‌شده‌»ای وجود ندارد — هر ادمین فقط دکمه‌هایِ خودش را می‌بیند.

پنلِ ادمین مخصوصِ یک نفر است (owner_id) تا فقط خودِ ادمین بتواند با آن کار کند.
همه‌یِ callback‌ها پیشوندِ adm: دارند.
"""
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.data import admin as A
from app.utils.ui import with_owner


def _back(owner_id: int):
    return with_owner("adm:home", owner_id)


def admin_home_kb(owner_id: int, perms: list[str], is_main: bool) -> InlineKeyboardMarkup:
    """خانه‌یِ پنل: فقط دکمه‌یِ بخش‌هایِ مجاز."""
    b = InlineKeyboardBuilder()
    # 🆕 v1.7.8.15 — فقط بخش‌هایِ اصلی؛ زیرمنوها داخلِ منویِ والدِ خودشان‌اند.
    for key in A.home_sections(perms, is_main):
        p = A.PERMISSIONS[key]
        b.button(
            text=f"{p['emoji']} {p['label']}",
            callback_data=with_owner(f"adm:sec:{key}", owner_id),
        )
    # لقبِ دلخواه برایِ خودِ ادمین (برایِ همه‌یِ ادمین‌ها باز است)
    # 🆕 تغییرِ خودخواسته‌یِ رمزِ ورود (هر زمان، برایِ همه‌یِ ادمین‌ها)
    b.button(text="🔑 تغییرِ رمزِ من", callback_data=with_owner("adm:pw:change", owner_id))
    # راهنمایِ مخصوصِ همین ادمین
    b.button(text="📘 راهنمایِ من", callback_data=with_owner("adm:guide", owner_id))
    b.button(text="🚪 خروج از حالتِ ادمین", callback_data=with_owner("adm:exit", owner_id))
    b.adjust(2)
    return b.as_markup()


def back_kb(owner_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="⬅️ بازگشت به پنل", callback_data=_back(owner_id))
    return b.as_markup()


# --------------------------- مدیریتِ کاربران ---------------------------
def admin_users_kb(owner_id: int, can_economy: bool = False, can_users: bool = True, can_bulk_levels: bool = False, can_bulk_wealth: bool = False) -> InlineKeyboardMarkup:
    """کنترلِ کاربر — v1.7.8.19: فقط ابزارهایِ کاربری؛ اقتصاد/لول/گروهی به بخش‌هایِ خودشان منتقل شدند."""
    b = InlineKeyboardBuilder()
    b.button(text="📜 لیستِ کاربران", callback_data=with_owner("adm:ul:0", owner_id))
    b.button(text="🎖️ کاربران لقب‌دار", callback_data=with_owner("adm:u:titled:0", owner_id))
    b.button(text="🔍 جستجو/پروفایلِ کاربر", callback_data=with_owner("adm:u:find", owner_id))
    b.button(text="🚫 محدودیت (بن)", callback_data=with_owner("adm:u:ban", owner_id))
    b.button(text="✅ رفعِ محدودیت", callback_data=with_owner("adm:u:unban", owner_id))
    b.button(text="⬅️ بازگشت", callback_data=_back(owner_id))
    b.adjust(2, 2, 1, 1)
    return b.as_markup()


def admin_economy_kb(owner_id: int) -> InlineKeyboardMarkup:
    b=InlineKeyboardBuilder()
    # تعیین مقدار معین
    b.button(text="🎯 تعیین ثروت یک نفر",callback_data=with_owner("adm:u:wealth",owner_id))
    b.button(text="🎯 تعیین ثروت چند نفر",callback_data=with_owner("adm:wealth:batch:set",owner_id))
    b.button(text="🌐 تعیین ثروت همه",callback_data=with_owner("adm:wealth:all:set",owner_id))
    # افزایش/کاهش
    b.button(text="➕ افزایش ثروت یک نفر",callback_data=with_owner("adm:u:wealthadd",owner_id))
    b.button(text="➕ افزایش ثروت چند نفر",callback_data=with_owner("adm:wealth:batch:add",owner_id))
    b.button(text="🌐 افزایش ثروت همه",callback_data=with_owner("adm:wealth:all:add",owner_id))
    b.button(text="➖ کاهش ثروت یک نفر",callback_data=with_owner("adm:u:wealthsub",owner_id))
    b.button(text="➖ کاهش ثروت چند نفر",callback_data=with_owner("adm:wealth:batch:sub",owner_id))
    b.button(text="🌐 کاهش ثروت همه",callback_data=with_owner("adm:wealth:all:sub",owner_id))
    # reset is a precise zero-value action through the existing set path
    b.button(text="♻️ ریست دارایی یک نفر",callback_data=with_owner("adm:u:wealthreset",owner_id))
    b.button(text="♻️ ریست دارایی چند نفر",callback_data=with_owner("adm:wealth:batch:reset",owner_id))
    b.button(text="♻️ ریست دارایی همه",callback_data=with_owner("adm:wealth:all:reset",owner_id))
    b.button(text="🏦 ریست وام یک نفر",callback_data=with_owner("adm:loan:one",owner_id))
    b.button(text="🏦 ریست وام چند نفر",callback_data=with_owner("adm:loan:batch",owner_id))
    b.button(text="🏦 ریست وام همه",callback_data=with_owner("adm:loan:all",owner_id))
    # v1.7.8.19 — هدایای پول از «ابزارهای ویژه» به اینجا منتقل شد
    b.button(text="🎯 هدیه پول به یک کاربر",callback_data=with_owner("adm:tl:gift1:cash",owner_id))
    b.button(text="🎁 پول به همه",callback_data=with_owner("adm:tl:gift:cash",owner_id))
    b.button(text="⬅️ بازگشت",callback_data=_back(owner_id)); b.adjust(2); return b.as_markup()

def admin_level_xp_kb(owner_id: int) -> InlineKeyboardMarkup:
    b=InlineKeyboardBuilder()
    b.button(text="🎯 تعیین لول یک نفر",callback_data=with_owner("adm:u:level",owner_id)); b.button(text="🎯 تعیین لول چند نفر",callback_data=with_owner("adm:lv:batch:set",owner_id)); b.button(text="🌐 تعیین لول همه",callback_data=with_owner("adm:bulk:level",owner_id))
    b.button(text="➕ افزایش لول یک نفر",callback_data=with_owner("adm:u:leveladd",owner_id)); b.button(text="➕ افزایش لول چند نفر",callback_data=with_owner("adm:lv:batch:add",owner_id)); b.button(text="🌐 افزایش لول همه",callback_data=with_owner("adm:lv:all:add",owner_id))
    b.button(text="➖ کاهش لول یک نفر",callback_data=with_owner("adm:u:levelsub",owner_id)); b.button(text="➖ کاهش لول چند نفر",callback_data=with_owner("adm:lv:batch:sub",owner_id)); b.button(text="🌐 کاهش لول همه",callback_data=with_owner("adm:lv:all:sub",owner_id))
    b.button(text="♻️ ریست لول و XP یک نفر",callback_data=with_owner("adm:lv:reset:one",owner_id)); b.button(text="♻️ ریست لول و XP چند نفر",callback_data=with_owner("adm:lv:reset:batch",owner_id)); b.button(text="♻️ ریست لول و XP همه",callback_data=with_owner("adm:lv:reset:all",owner_id))
    # v1.7.8.19 — هدایای XP از «ابزارهای ویژه» به اینجا منتقل شد
    b.button(text="🌟 XP به یک کاربر",callback_data=with_owner("adm:tl:gift1:xp",owner_id))
    b.button(text="✨ XP به همه",callback_data=with_owner("adm:tl:gift:xp",owner_id))
    b.button(text="⬅️ بازگشت",callback_data=_back(owner_id)); b.adjust(2); return b.as_markup()

def admin_assistants_kb(owner_id: int, first_on: bool, second_on: bool) -> InlineKeyboardMarkup:
    b=InlineKeyboardBuilder()
    b.button(text=("🔴 محدود کردن دستیار اول" if first_on else "🟢 فعال کردن دستیار اول"), callback_data=with_owner("adm:asst:first", owner_id))
    b.button(text=("🔴 محدود کردن دستیار دوم" if second_on else "🟢 فعال کردن دستیار دوم"), callback_data=with_owner("adm:asst:second", owner_id))
    b.button(text="👤 فعال/غیرفعال‌کردن برای کاربر", callback_data=with_owner("adm:asst:user", owner_id))
    b.button(text="🚫 محدودیت دستیار کاربران", callback_data=with_owner("adm:ctrl:home", owner_id))
    b.button(text="⬅️ بازگشت", callback_data=_back(owner_id)); b.adjust(2); return b.as_markup()


def admin_assistant_user_kb(owner_id: int, target_id: int, enabled: bool) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(
        text="🔴 غیرفعال‌کردن دستیارهای این کاربر" if enabled else "🟢 فعال‌کردن دستیارهای این کاربر",
        callback_data=with_owner(f"adm:asst:usertog:{target_id}", owner_id),
    )
    b.button(text="↩️ کنترل دستیارها", callback_data=with_owner("adm:sec:assistants", owner_id))
    b.adjust(1)
    return b.as_markup()


def admin_news_broadcast_kb(owner_id: int, can_news: bool = True, can_broadcast: bool = True) -> InlineKeyboardMarkup:
    # 🆕 v1.7.8.15 — «پیامِ همگانی» زیرمنویِ اخبار است و فقط با دسترسیِ broadcast دیده می‌شود.
    b = InlineKeyboardBuilder()
    if can_news:
        b.button(text="📰 مدیریت اخبار", callback_data=with_owner("adm:news:home", owner_id))
    if can_broadcast:
        b.button(text="📢 پیام همگانی", callback_data=with_owner("adm:bc:home", owner_id))
    b.button(text="⬅️ بازگشت", callback_data=_back(owner_id))
    b.adjust(2)
    return b.as_markup()


# --------------------------- 🆕 تأییدِ خروج از حالتِ ادمین ---------------------------
def admin_exit_confirm_kb(owner_id: int) -> InlineKeyboardMarkup:
    """🆕 مرحله ۲۷ — خروج از حالتِ ادمین دو مرحله‌ای شد (جلوگیری از خروجِ اتفاقی)."""
    b = InlineKeyboardBuilder()
    b.button(text="✅ بله، خارج شو", callback_data=with_owner("adm:exitok", owner_id))
    b.button(text="✖ نه، در حالتِ ادمین بمانم", callback_data=with_owner("adm:home", owner_id))
    b.adjust(1)
    return b.as_markup()


# --------------------------- 🆕 رویدادهایِ بونس (XP/پول) ---------------------------
def admin_events_kb(owner_id: int, xp_on: bool, money_on: bool) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(
        text=("🔴 خاموش‌کردنِ بونسِ XP" if xp_on else "✨ فعال‌کردنِ بونسِ XP"),
        callback_data=with_owner(("adm:ev:off:xp" if xp_on else "adm:ev:on:xp"), owner_id),
    )
    b.button(
        text=("🔴 خاموش‌کردنِ بونسِ پول" if money_on else "💰 فعال‌کردنِ بونسِ پول"),
        callback_data=with_owner(("adm:ev:off:money" if money_on else "adm:ev:on:money"), owner_id),
    )
    b.button(text="🏷 نامِ اونت", callback_data=with_owner("adm:ev:title", owner_id))
    b.button(text="📣 اعلامِ اونت به همه", callback_data=with_owner("adm:ev:announce", owner_id))
    b.button(text="🧹 پایانِ همه‌ی رویدادها", callback_data=with_owner("adm:ev:clear", owner_id))
    b.button(text="⬅️ بازگشت", callback_data=_back(owner_id))
    b.adjust(1)
    return b.as_markup()


# --------------------------- 🆕 ابزارهایِ ویژه (فقط ادمینِ اصلی) ---------------------------
def admin_tools_kb(owner_id: int) -> InlineKeyboardMarkup:
    """ابزارهای ویژه در سه گروه؛ هر عملیات فقط یک محل نمایش دارد."""
    b = InlineKeyboardBuilder()
    b.button(text="♻️ ریست و نگهداری", callback_data=with_owner("adm:tools:resets", owner_id))
    b.button(text="🕘 فعالیت ۲۴ ساعت اخیر", callback_data=with_owner("adm:act:recent", owner_id))
    b.button(text="🔎 فعالیت کاربر با آیدی", callback_data=with_owner("adm:act:user", owner_id))
    b.button(text="⚙️ تنظیمات بازی", callback_data=with_owner("adm:tools:settings", owner_id))
    b.button(text="⚽ مدیریت فوتبال (سرمربی/بازار/لیگ)", callback_data=with_owner("adm:fball:home", owner_id))
    b.button(text="⚡ تکمیل فوری صف‌های اتحادیه", callback_data=with_owner("adm:allq:complete", owner_id))
    b.button(text="⬅️ بازگشت", callback_data=_back(owner_id))
    b.adjust(1)
    return b.as_markup()

def admin_tools_resets_kb(owner_id: int) -> InlineKeyboardMarkup:
    b=InlineKeyboardBuilder()
    b.button(text="♻️ ریست کامل یک کاربر", callback_data=with_owner("adm:tl:reset", owner_id))
    b.button(text="🗑️ حذف کامل کاربر از دیتابیس", callback_data=with_owner("adm:tl:delete", owner_id))
    b.button(text="🏆 ریست رنکینگ مسابقات", callback_data=with_owner("adm:tl:sportreset", owner_id))
    b.button(text="🪖 پاک کردن نیروهای یک کاربر (بدون لول)", callback_data=with_owner("adm:tl:milreset:one", owner_id))
    b.button(text="💣 پاک کردن نیروهای همه (بدون لول)", callback_data=with_owner("adm:tl:milreset:all", owner_id))
    b.button(text="⚡️ تکمیل فوری صف‌های یک کاربر", callback_data=with_owner("adm:tl:qflush", owner_id))
    b.button(text="🪖 گزارش نظامی کاربر", callback_data=with_owner("adm:tl:milreport", owner_id))
    b.button(text="🏁 نهایی‌سازی جنگ‌های رنکینگ", callback_data=with_owner("adm:rankfinalize", owner_id))
    b.button(text="⬆️ تغییر لول نیروهای کاربر", callback_data=with_owner("adm:tl:millevel", owner_id))
    b.button(text="⬅️ بازگشت", callback_data=with_owner("adm:sec:tools", owner_id)); b.adjust(1); return b.as_markup()

def admin_tools_settings_kb(owner_id: int) -> InlineKeyboardMarkup:
    b=InlineKeyboardBuilder()
    b.button(text="🔗 پاداش لینک دعوت", callback_data=with_owner("adm:ref:home", owner_id))
    b.button(text="🏆 روشن/خاموش رنکینگ", callback_data=with_owner("adm:rankvis:home", owner_id))
    b.button(text="💾 بکاپ دیتابیس", callback_data=with_owner("adm:backup:home", owner_id))
    b.button(text="🛑 کنترل بخش‌ها", callback_data=with_owner("adm:ctrl:home", owner_id))
    b.button(text="🏙️ سقف درآمد ساعتی شهر", callback_data=with_owner("adm:city:income_cap", owner_id))
    b.button(text="📐 ضریب‌های اقتصاد شهر", callback_data=with_owner("adm:city:balance", owner_id))
    b.button(text="🏷️ سقف بونس شهرت برند", callback_data=with_owner("adm:brand:rep_cap", owner_id))
    b.button(text="🪖 سقف ظرفیت سربازخانه", callback_data=with_owner("adm:mil:barracks_cap", owner_id))
    b.button(text="🏭 دسترسی ابرکارخانه", callback_data=with_owner("adm:giga:home", owner_id))
    b.button(text="🏭 تولید و ساخت شهر", callback_data=with_owner("adm:cityprod:home", owner_id))
    b.button(text="🚔 روشن/خاموش کردن دستگیری", callback_data=with_owner("adm:theft:arrest", owner_id))
    b.button(text="🔢 تنظیم عددی بازی", callback_data=with_owner("adm:num:home", owner_id))
    b.button(text="🔒 جوین اجباری کانال", callback_data=with_owner("adm:fj:home", owner_id))
    b.button(text="⬅️ بازگشت", callback_data=with_owner("adm:sec:tools", owner_id)); b.adjust(1); return b.as_markup()


def admin_city_balance_kb(owner_id: int) -> InlineKeyboardMarkup:
    """تنظیم ضریب هزینه / درآمد / قیمت منابع شهر."""
    b = InlineKeyboardBuilder()
    b.button(text="🏗️ ضریب هزینه ساخت", callback_data=with_owner("adm:city:bal:cost", owner_id))
    b.button(text="💰 مقسوم‌علیه درآمد لول‌دار", callback_data=with_owner("adm:city:bal:income", owner_id))
    b.button(text="📦 ضریب قیمت منابع", callback_data=with_owner("adm:city:bal:res", owner_id))
    b.button(text="🔄 بروزرسانی مقادیر", callback_data=with_owner("adm:city:balance", owner_id))
    b.button(text="⬅️ بازگشت", callback_data=with_owner("adm:tools:settings", owner_id))
    b.adjust(1)
    return b.as_markup()



# 🆕 مرحله ۴۶ — تاییدیه‌ی ریستِ نظامی
def admin_cityprod_kb(owner_id: int) -> InlineKeyboardMarkup:
    """🏭 تولید و ساخت شهر — سقف تولید + تکمیل فوری."""
    b = InlineKeyboardBuilder()
    b.button(text="🔢 سقف تولید روزانه (هر واحد)", callback_data=with_owner("adm:cityprod:cap", owner_id))
    b.button(text="🏭 سقف تجمیعی (۴۰+ واحد صنعتی)", callback_data=with_owner("adm:cityprod:aggcap", owner_id))
    b.button(text="⚡ تکمیل فوری ساخت‌وساز (یک کاربر)", callback_data=with_owner("adm:cityprod:flush", owner_id))
    b.button(text="↩️ بازگشت", callback_data=with_owner("adm:tools:settings", owner_id))
    b.adjust(1)
    return b.as_markup()



def military_reset_confirm_kb(owner_id: int, scope: str, target: int = 0) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    cb = f"adm:tl:milresetok:{scope}:{target}"
    b.button(text="✅ بله، ریست کن", callback_data=with_owner(cb, owner_id))
    b.button(text="✖ انصراف", callback_data=with_owner("adm:sec:tools", owner_id))
    b.adjust(1)
    return b.as_markup()


def tools_reset_confirm_kb(owner_id: int, target: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="✅ بله، ریست کن", callback_data=with_owner(f"adm:tl:resetok:{target}", owner_id))
    b.button(text="✖ انصراف", callback_data=with_owner("adm:sec:tools", owner_id))
    b.adjust(1)
    return b.as_markup()


def sports_reset_confirm_kb(owner_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="✅ بله، ریست کن", callback_data=with_owner("adm:tl:sportresetok", owner_id))
    b.button(text="✖ انصراف", callback_data=with_owner("adm:sec:tools", owner_id))
    b.adjust(1)
    return b.as_markup()


# --------------------------- 🆕 v1.7.8.14 — بخش‌هایِ مستقلِ جدید ---------------------------
def admin_game_settings_kb(owner_id: int) -> InlineKeyboardMarkup:
    """⚙️ تنظیماتِ عددیِ بازی.

    عمداً جدا از admin_tools_settings_kb ساخته شده: آن یکی بکاپ و جوینِ
    اجباری را هم دارد، پس اگر همان را به ادمینِ فرعی نشان می‌دادیم،
    دسترسیِ اضافی نشت می‌کرد.
    """
    b = InlineKeyboardBuilder()
    b.button(text="🏙️ سقف درآمد ساعتی شهر", callback_data=with_owner("adm:city:income_cap", owner_id))
    b.button(text="📐 ضریب‌های اقتصاد شهر", callback_data=with_owner("adm:city:balance", owner_id))
    b.button(text="🏷️ سقف بونس شهرت برند", callback_data=with_owner("adm:brand:rep_cap", owner_id))
    b.button(text="🪖 سقف ظرفیت سربازخانه", callback_data=with_owner("adm:mil:barracks_cap", owner_id))
    b.button(text="🏭 دسترسی ابرکارخانه", callback_data=with_owner("adm:giga:home", owner_id))
    b.button(text="🏗️ تولید و ساخت شهر", callback_data=with_owner("adm:cityprod:home", owner_id))
    b.button(text="🔢 تنظیم عددی بازی", callback_data=with_owner("adm:num:home", owner_id))
    b.button(text="🚔 روشن/خاموش کردن دستگیری", callback_data=with_owner("adm:theft:arrest", owner_id))
    b.button(text="⬅️ بازگشت", callback_data=_back(owner_id))
    b.adjust(1)
    return b.as_markup()


def admin_activity_kb(owner_id: int) -> InlineKeyboardMarkup:
    """🕘 فعالیتِ کاربران به‌عنوانِ یک بخشِ مستقل."""
    b = InlineKeyboardBuilder()
    b.button(text="🕘 فعالیت ۲۴ ساعت اخیر", callback_data=with_owner("adm:act:recent", owner_id))
    b.button(text="🔎 فعالیت یک کاربر با آیدی", callback_data=with_owner("adm:act:user", owner_id))
    b.button(text="⬅️ بازگشت", callback_data=_back(owner_id))
    b.adjust(1)
    return b.as_markup()


# --------------------------- اشتراک ---------------------------
def admin_sub_kb(
    owner_id: int,
    is_main: bool = False,
    notify_main_on: bool = True,
    has_sales_admin: bool = False,
) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="💎 فعال‌سازیِ اشتراک (دسترسیِ ویژه)", callback_data=with_owner("adm:sub:on", owner_id))
    b.button(text="⚪ غیرفعال‌سازیِ اشتراک", callback_data=with_owner("adm:sub:off", owner_id))
    b.button(text="📥 درخواست‌هایِ خرید", callback_data=with_owner("adm:sub:reqs", owner_id))
    b.button(text="💳 منتظر پرداخت/رسید", callback_data=with_owner("adm:sub:awaitpay", owner_id))
    # 🆕 v1.7.6.3 — فهرستِ کسانی که رسید فرستاده‌اند + فعال‌سازی از همان‌جا
    b.button(text="🧾 رسیدهای ارسال‌شده", callback_data=with_owner("adm:sub:receipts", owner_id))
    b.button(text="🏦 تنظیم روش پرداخت", callback_data=with_owner("adm:sub:paymethod", owner_id))
    b.button(text="📜 تاریخچه‌ی کاملِ خریدها", callback_data=with_owner("adm:sub:allhist", owner_id))
    b.button(text="🔎 پیگیری با کدِ سفارش", callback_data=with_owner("adm:sub:track", owner_id))
    if is_main:
        b.button(text="��� قیمت‌گذاریِ سطوح", callback_data=with_owner("adm:sub:price", owner_id))
        sales_label = "👤 تغییرِ ادمینِ فروش" if has_sales_admin else "👤 تعیینِ ادمینِ فروش"
        b.button(text=sales_label, callback_data=with_owner("adm:sub:salesadmin", owner_id))
        notify_label = "🔕 غیرفعال‌کردنِ اطلاعِ من از درخواست‌ها" if notify_main_on else "🔔 فعال‌کردنِ اطلاعِ من از درخواست‌ها"
        b.button(text=notify_label, callback_data=with_owner("adm:sub:notifytoggle", owner_id))
    b.button(text="⬅️ بازگشت", callback_data=_back(owner_id))
    b.adjust(1)
    return b.as_markup()


def sub_price_tier_kb(owner_id: int, effective: list[dict]) -> InlineKeyboardMarkup:
    """🆕 انتخابِ سطح برایِ قیمت‌گذاری؛ effective از subscription_service.effective_tiers می‌آید."""
    b = InlineKeyboardBuilder()
    for tier in effective:
        if tier["key"] == "free":
            continue
        b.button(
            text=f"{tier['emoji']} {tier['name']} — {tier['price']:,}$",
            callback_data=with_owner(f"adm:sub:pricetier:{tier['key']}", owner_id),
        )
    b.button(text="⬅️ بازگشت", callback_data=with_owner("adm:sec:subscriptions", owner_id))
    b.adjust(1)
    return b.as_markup()


def sub_requests_kb(owner_id: int, requests: list) -> InlineKeyboardMarkup:
    """🆕 دکمه‌هایِ تأیید/ردِ هر درخواستِ درِ انتظار."""
    b = InlineKeyboardBuilder()
    for rec in requests:
        code = rec.tracking_code
        b.button(text=f"✅ تأیید برای پرداخت {code}", callback_data=with_owner(f"adm:sub:preok:{code}", owner_id))
        b.button(text=f"🚫 رد {code}", callback_data=with_owner(f"adm:sub:reject:{code}", owner_id))
    b.button(text="⬅️ بازگشت", callback_data=with_owner("adm:sec:subscriptions", owner_id))
    b.adjust(2)
    return b.as_markup()


def sub_receipts_kb(owner_id: int, rows: list) -> InlineKeyboardMarkup:
    """🆕 v1.7.6.3 — برای هر رسید: مشاهده، تأیید + فعال‌سازیِ اشتراک، رد.

    عمداً پیشوندهایِ جداگانه (recok/recno) دارد تا پس از عمل، همین فهرست
    دوباره ساخته شود و ادمین به فهرستِ دیگری پرت نشود.
    """
    b = InlineKeyboardBuilder()
    for rec in rows or []:
        code = rec.tracking_code
        b.button(text=f"👁 مشاهدهٔ رسید {code}", callback_data=with_owner(f"adm:sub:seerec:{code}", owner_id))
        b.button(text=f"⚡ تأیید و فعال‌سازی {code}", callback_data=with_owner(f"adm:sub:recok:{code}", owner_id))
        b.button(text=f"🚫 رد {code}", callback_data=with_owner(f"adm:sub:recno:{code}", owner_id))
    b.button(text="🔄 بروزرسانی", callback_data=with_owner("adm:sub:receipts", owner_id))
    b.button(text="⬅️ بازگشت", callback_data=with_owner("adm:sec:subscriptions", owner_id))
    b.adjust(1)
    return b.as_markup()


def sub_tier_kb(owner_id: int) -> InlineKeyboardMarkup:
    """انتخابِ سطحِ اشتراک برایِ فعال‌سازی."""
    from app.data import subscription as S

    b = InlineKeyboardBuilder()
    for key in S.TIER_ORDER:
        if key == "free":
            continue
        tier = S.get_tier(key)
        b.button(text=f"{tier['emoji']} {tier['name']}", callback_data=with_owner(f"adm:sub:tier:{key}", owner_id))
    b.button(text="⬅️ بازگشت", callback_data=with_owner("adm:sec:subscriptions", owner_id))
    b.adjust(1)
    return b.as_markup()


# --------------------------- القاب ---------------------------
def admin_titles_kb(owner_id: int) -> InlineKeyboardMarkup:
    """کنترلِ القاب — v1.7.8.19: همه‌ی ابزارهایِ لقب یک‌جا (صف، اعطا، ارزیابی، بررسی، سفارشی)."""
    b = InlineKeyboardBuilder()
    b.button(text="✅ صف تایید لقب", callback_data=with_owner("adm:titleapprovals", owner_id))
    b.button(text="🎖️ اعطای لقب به کاربر", callback_data=with_owner("adm:tl:gifttitle", owner_id))
    b.button(text="🔄 ارزیابی القاب همه", callback_data=with_owner("adm:tl:evaltitles", owner_id))
    b.button(text="🔎 بررسیِ القابِ کاربر", callback_data=with_owner("adm:t:inspect", owner_id))
    b.button(text="🏷️ لقبِ دلخواه برایِ کاربر", callback_data=with_owner("adm:t:custom", owner_id))
    b.button(text="🧹 حذفِ لقبِ دلخواهِ کاربر", callback_data=with_owner("adm:t:clear", owner_id))
    b.button(text="🏷️ لقبِ دلخواهِ من", callback_data=with_owner("adm:mytitle", owner_id))
    b.button(text="⬅️ بازگشت", callback_data=_back(owner_id))
    b.adjust(1)
    return b.as_markup()


# --------------------------- کانالِ گزارش (فقط ادمینِ اصلی) ---------------------------


def admin_force_join_kb(owner_id: int, enabled: bool, channels: list | None = None) -> InlineKeyboardMarkup:
    """پنل عضویت اجباری کانال‌ها."""
    b = InlineKeyboardBuilder()
    channels = channels or []
    if enabled:
        b.button(text="🟢 سیستم روشن — خاموش کردن", callback_data=with_owner("adm:fj:off", owner_id))
    else:
        b.button(text="⚪ سیستم خاموش — روشن کردن", callback_data=with_owner("adm:fj:on", owner_id))
    b.button(text="➕ افزودن کانال", callback_data=with_owner("adm:fj:add", owner_id))
    for ch in channels[:15]:
        cid = int(ch.get("id") or 0)
        title = str(ch.get("title") or cid)[:22]
        mode = str(ch.get("link_mode") or "auto")
        icon = "🌐" if mode == "public" else ("🔐" if mode == "private" else "⚙️")
        b.button(text=f"{icon} {title}", callback_data=with_owner(f"adm:fj:ch:{cid}", owner_id))
    b.button(text="🔄 بروزرسانی", callback_data=with_owner("adm:fj:home", owner_id))
    b.button(text="⬅️ بازگشت", callback_data=_back(owner_id))
    b.adjust(1)
    return b.as_markup()


def admin_force_join_channel_kb(owner_id: int, ch: dict) -> InlineKeyboardMarkup:
    """منوی یک کانال: عمومی / خصوصی / لینک / حذف."""
    b = InlineKeyboardBuilder()
    cid = int(ch.get("id") or 0)
    mode = str(ch.get("link_mode") or "auto")
    if mode != "public":
        b.button(text="🌐 تنظیم روی عمومی", callback_data=with_owner(f"adm:fj:mode:{cid}:public", owner_id))
    if mode != "private":
        b.button(text="🔐 تنظیم روی خصوصی", callback_data=with_owner(f"adm:fj:mode:{cid}:private", owner_id))
    b.button(text="🔗 تنظیم/تغییر لینک دعوت", callback_data=with_owner(f"adm:fj:setlink:{cid}", owner_id))
    b.button(text="🗑 حذف این کانال", callback_data=with_owner(f"adm:fj:del:{cid}", owner_id))
    b.button(text="⬅️ بازگشت به لیست", callback_data=with_owner("adm:fj:home", owner_id))
    b.adjust(1)
    return b.as_markup()

def admin_channel_kb(owner_id: int, has_channel: bool) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    if has_channel:
        b.button(text="🔁 تعویضِ کانالِ گزارش", callback_data=with_owner("adm:ch:set", owner_id))
        b.button(text="🗑 حذفِ کانالِ گزارش", callback_data=with_owner("adm:ch:remove", owner_id))
        b.button(text="🧪 تستِ ارسال", callback_data=with_owner("adm:ch:test", owner_id))
    else:
        b.button(text="📡 انتخابِ کانالِ گزارش", callback_data=with_owner("adm:ch:set", owner_id))
    b.button(text="⬅️ بازگشت", callback_data=_back(owner_id))
    b.adjust(1)
    return b.as_markup()


# --------------------------- اخبار / همگانی ---------------------------
def admin_news_kb(owner_id: int, is_main: bool = False, has_news_channel: bool = False) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="📝 ثبتِ خبرِ دستی", callback_data=with_owner("adm:news:add", owner_id))
    b.button(text="🚀 انتشارِ فوریِ دایجست", callback_data=with_owner("adm:news:digest", owner_id))
    if is_main:
        if has_news_channel:
            b.button(text="🔁 تعویضِ کانالِ اخبار", callback_data=with_owner("adm:nc:set", owner_id))
            b.button(text="🗑 حذفِ کانالِ اخبار", callback_data=with_owner("adm:nc:remove", owner_id))
            b.button(text="🧪 تستِ ارسال", callback_data=with_owner("adm:nc:test", owner_id))
        else:
            b.button(text="📡 انتخابِ کانالِ اخبار", callback_data=with_owner("adm:nc:set", owner_id))
    b.button(text="⬅️ بازگشت", callback_data=_back(owner_id))
    b.adjust(1)
    return b.as_markup()


def admin_broadcast_kb(owner_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="📢 نوشتنِ پیامِ همگانی", callback_data=with_owner("adm:bc:new", owner_id))
    b.button(text="⬅️ بازگشت", callback_data=_back(owner_id))
    b.adjust(1)
    return b.as_markup()


# 🆕 پیش‌نمایشِ پیامِ همگانی قبل از ارسال — امکانِ ویرایشِ متن یا ارسالِ نهایی
def admin_broadcast_confirm_kb(owner_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="📤 ارسالِ نهایی به همه", callback_data=with_owner("adm:bc:send", owner_id))
    b.button(text="✏️ ویرایشِ متن", callback_data=with_owner("adm:bc:edit", owner_id))
    b.button(text="✖ انصراف", callback_data=with_owner("adm:cancel", owner_id))
    b.adjust(1)
    return b.as_markup()


# --------------------------- گزارش‌هایِ چت‌مود ---------------------------
def admin_reports_kb(owner_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="🚨 گزارش‌هایِ باز (شکایات)", callback_data=with_owner("adm:rep:open", owner_id))
    b.button(text="🗂 آخرین جلساتِ چت", callback_data=with_owner("adm:rep:sessions", owner_id))
    b.button(text="🚨 گزارش اسپم", callback_data=with_owner("adm:rep:spam", owner_id))
    b.button(text="🚨 اسپم‌های جدید", callback_data=with_owner("adm:rep:spamnew:0", owner_id))
    b.button(text="📜 تاریخچه اسپم", callback_data=with_owner("adm:rep:spamhist:0", owner_id))
    b.button(text="📡 کانال گزارش", callback_data=with_owner("adm:sec:channel", owner_id))
    b.button(text="⬅️ بازگشت", callback_data=_back(owner_id))
    b.adjust(2)
    return b.as_markup()


# --------------------------- مدیریتِ ادمین‌ها (فقط ادمینِ اصلی) ---------------------------
def admin_admins_kb(owner_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="📋 فهرستِ ادمین‌ها", callback_data=with_owner("adm:a:list", owner_id))
    b.button(text="➕ انتصابِ ادمین", callback_data=with_owner("adm:a:add", owner_id))
    b.button(text="🛠 ویرایشِ دسترسی‌ها", callback_data=with_owner("adm:a:edit", owner_id))
    b.button(text="❌ عزلِ ادمین", callback_data=with_owner("adm:a:revoke", owner_id))
    b.button(text="⬅️ بازگشت", callback_data=_back(owner_id))
    b.adjust(1, 2, 1, 1)
    return b.as_markup()


def perms_picker_kb(owner_id: int, selected: list[str]) -> InlineKeyboardMarkup:
    """انتخابگرِ دسترسی‌ها (تیک/برداشتنِ تیک) + دکمه‌یِ تأیید."""
    b = InlineKeyboardBuilder()
    for key in A.GRANTABLE:
        p = A.PERMISSIONS[key]
        mark = "✅" if key in selected else "⬜"
        b.button(
            text=f"{mark} {p['emoji']} {p['label']}",
            callback_data=with_owner(f"adm:perm:toggle:{key}", owner_id),
        )
    b.button(text="💾 تأیید و ذخیره", callback_data=with_owner("adm:perm:save", owner_id))
    b.button(text="✖ انصراف", callback_data=with_owner("adm:sec:admins", owner_id))
    b.adjust(1)
    return b.as_markup()


def cancel_kb(owner_id: int) -> None:
    """🆕 دگر دکمه‌ی شیشه‌ای نشان نمی‌دهد (گاهی گیر می‌کرد روی لودینگ می‌موند). فقط کلمه‌ی متنیِ «انصراف» (هندل شده توسطِ handle_cancel_word) عملیات را لغو می‌کند."""
    return None


# --------------------------- 🆕 مرحله ۲۹ — لیستِ کاربران ---------------------------
USERS_PER_PAGE = 10


def users_list_kb(
    owner_id: int,
    rows: list,
    page: int,
    pages: int,
    query: str | None = None,
) -> InlineKeyboardMarkup:
    """لیستِ کاربران: هر صفحه ۱۰ کاربر + پیمایش + جستجو."""
    b = InlineKeyboardBuilder()
    tail = f":{query}" if query else ""
    for p in rows:
        name = (p.name or "—")[:24]
        b.button(
            text=f"👤 {name} — {p.tg_user_id}",
            callback_data=with_owner(f"adm:up:{p.tg_user_id}", owner_id),
        )
    rows_layout = [1] * len(rows)
    if pages > 1:
        prev_p = (page - 1) % pages
        next_p = (page + 1) % pages
        b.button(text="◀️ قبلی", callback_data=with_owner(f"adm:ul:{prev_p}{tail}", owner_id))
        b.button(text=f"{page + 1}/{pages}", callback_data="ui:noop")
        b.button(text="بعدی ▶️", callback_data=with_owner(f"adm:ul:{next_p}{tail}", owner_id))
        rows_layout.append(3)
        b.button(text="🔢 رفتن به صفحه‌ی ...", callback_data=with_owner(f"adm:ulg{tail}", owner_id))
        rows_layout.append(1)
    b.button(text="🔎 جستجوی نام", callback_data=with_owner("adm:uls", owner_id))
    b.button(text="🆔 جستجوی آیدی", callback_data=with_owner("adm:u:find", owner_id))
    rows_layout.append(2)
    if query:
        b.button(text="✖ پاک‌کردنِ جستجو", callback_data=with_owner("adm:ul:0", owner_id))
        rows_layout.append(1)
    b.button(text="⬅️ بازگشت", callback_data=with_owner("adm:sec:users", owner_id))
    rows_layout.append(1)
    b.adjust(*rows_layout)
    return b.as_markup()


def user_card_kb(owner_id: int, back_page: int = 0, query: str | None = None) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    tail = f":{query}" if query else ""
    b.button(text="⬅️ بازگشت به لیست", callback_data=with_owner(f"adm:ul:{back_page}{tail}", owner_id))
    b.button(text="🏠 پنل", callback_data=_back(owner_id))
    b.adjust(1, 1)
    return b.as_markup()



def spam_reports_kb(owner_id: int, rows: list, page: int, pages: int, mode: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for r in rows:
        b.button(text=f"📨 ارسال مشخصات #{r.id}", callback_data=with_owner(f"adm:rep:spamsend:{r.id}:{mode}:{page}", owner_id))
    if pages > 1:
        b.button(text="◀️ قبلی", callback_data=with_owner(f"adm:rep:{mode}:{(page-1)%pages}", owner_id))
        b.button(text=f"{page+1}/{pages}", callback_data="ui:noop")
        b.button(text="بعدی ▶️", callback_data=with_owner(f"adm:rep:{mode}:{(page+1)%pages}", owner_id))
    b.button(text="↩️ بازگشت", callback_data=with_owner("adm:sec:reports", owner_id))
    b.adjust(1)
    return b.as_markup()


def admin_control_kb(owner_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="🛑 خاموش‌کردنِ بخش‌ها", callback_data=with_owner("adm:ctrl:add", owner_id))
    b.button(text="📋 محدودیت‌های فعال", callback_data=with_owner("adm:ctrl:list", owner_id))
    b.button(text="🧹 حذف همه محدودیت‌ها", callback_data=with_owner("adm:ctrl:clearall", owner_id))
    b.button(text="🧪 تست‌کنندگان (دسترسی به بخش‌های خاموش)", callback_data=with_owner("adm:ctrl:testers", owner_id))
    b.button(text="⬅️ بازگشت", callback_data=with_owner("adm:home", owner_id))
    b.adjust(1)
    return b.as_markup()

def admin_numbers_kb(owner_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="✏️ ثبت/تغییر عدد", callback_data=with_owner("adm:num:set", owner_id))
    b.button(text="📋 لیست تنظیمات", callback_data=with_owner("adm:num:list", owner_id))
    b.button(text="⬅️ بازگشت", callback_data=with_owner("adm:home", owner_id))
    b.adjust(1)
    return b.as_markup()

def titled_users_kb(owner_id: int, rows: list, page: int, pages: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for uid, name, cnt in rows:
        b.button(text=f"🎖️ {name or uid} ({cnt})", callback_data=with_owner(f"adm:u:titledcard:{uid}:{page}", owner_id))
    if pages > 1:
        b.button(text="◀️ قبلی", callback_data=with_owner(f"adm:u:titled:{(page-1)%pages}", owner_id))
        b.button(text=f"{page+1}/{pages}", callback_data="ui:noop")
        b.button(text="بعدی ▶️", callback_data=with_owner(f"adm:u:titled:{(page+1)%pages}", owner_id))
    b.button(text="↩️ بازگشت", callback_data=with_owner("adm:sec:users", owner_id))
    b.adjust(1)
    return b.as_markup()

def titled_user_actions_kb(owner_id: int, target_id: int, page: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="✏️ تغییر لقب فعال/دلخواه", callback_data=with_owner(f"adm:t:custom:{target_id}", owner_id))
    b.button(text="🧹 حذف لقب فعال", callback_data=with_owner(f"adm:t:clear:{target_id}", owner_id))
    b.button(text="↩️ برگشت به کاربران لقب‌دار", callback_data=with_owner(f"adm:u:titled:{page}", owner_id))
    b.adjust(1)
    return b.as_markup()


# 🆕 کیبوردِ انتخابِ دامنه‌ی خاموش‌کردن (همه / چند کاربر)
def admin_control_scope_kb(owner_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="🌐 برای همه", callback_data=with_owner("adm:ctrl:scope:all", owner_id))
    b.button(text="👤 چند کاربرِ انتخابی", callback_data=with_owner("adm:ctrl:scope:sel", owner_id))
    b.button(text="⬅️ بازگشت", callback_data=with_owner("adm:ctrl:home", owner_id))
    b.adjust(1)
    return b.as_markup()


# 🆕 کیبوردِ دکمه‌ایِ بخش‌ها با تیکِ روشن/خاموش
def admin_control_sections_kb(owner_id: int, sections, restricted, scope: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for key, label in sections:
        mark = "🚫" if key in restricted else "✅"
        b.button(text=f"{mark} {label}", callback_data=with_owner(f"adm:ctrl:tog:{scope}:{key}", owner_id))
    b.button(text="⬅️ بازگشت", callback_data=with_owner("adm:ctrl:home", owner_id))
    n = len(sections)
    rows = [2] * (n // 2)
    if n % 2:
        rows.append(1)
    rows.append(1)  # back
    b.adjust(*rows)
    return b.as_markup()


def referral_admin_kb(owner_id: int, cfg: dict) -> InlineKeyboardMarkup:
    b=InlineKeyboardBuilder()
    b.button(text=("💰 خاموش‌کردن پاداش پولی" if cfg["cash_on"] else "💰 فعال‌کردن پاداش پولی"),callback_data=with_owner("adm:ref:cash:toggle",owner_id))
    b.button(text="✏️ مبلغ پول",callback_data=with_owner("adm:ref:cash:amount",owner_id))
    b.button(text=("📈 خاموش‌کردن بونس درآمد" if cfg["bonus_on"] else "📈 فعال‌کردن بونس درآمد"),callback_data=with_owner("adm:ref:bonus:toggle",owner_id))
    b.button(text="✏️ درصد بونس",callback_data=with_owner("adm:ref:bonus:amount",owner_id))
    b.button(text="⬅️ بازگشت",callback_data=with_owner("adm:sec:tools",owner_id)); b.adjust(1); return b.as_markup()


# --------------------------- 🆕 v1.7.2 — حذف کامل / رنکینگ / بکاپ ---------------------------
def tools_delete_confirm_kb(owner_id: int, target: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="✅ بله، کامل حذف کن", callback_data=with_owner(f"adm:tl:deleteok:{target}", owner_id))
    b.button(text="✖ انصراف", callback_data=with_owner("adm:sec:tools", owner_id))
    b.adjust(1)
    return b.as_markup()


def rank_visibility_kb(owner_id: int, vis: dict, categories) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for code, label, _unit in categories:
        on = vis.get(code, True)
        mark = "✅" if on else "🚫"
        b.button(text=f"{mark} {label}", callback_data=with_owner(f"adm:rankvis:tog:{code}", owner_id))
    extras = [
        ("global", "🌍 رتبه‌بندی کلی"),
        ("league", "🏅 لیگ‌ها"),
        ("war_ranked", "⚔️ جنگ رنکینگ"),
        ("power_formula", "⚡ فرمول قدرت"),
    ]
    for code, label in extras:
        on = vis.get(code, True)
        mark = "✅" if on else "🚫"
        b.button(text=f"{mark} {label}", callback_data=with_owner(f"adm:rankvis:tog:{code}", owner_id))
    b.button(text="⬅️ بازگشت", callback_data=with_owner("adm:tools:settings", owner_id))
    b.adjust(1)
    return b.as_markup()


def backup_admin_kb(owner_id: int, cfg: dict) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    hours = int(cfg.get("interval_hours") or 0)
    ch = cfg.get("channel_id")
    b.button(
        text=("📡 تغییر کانال بکاپ" if ch else "📡 تعیین کانال بکاپ"),
        callback_data=with_owner("adm:backup:channel", owner_id),
    )
    if ch:
        b.button(text="🗑 حذف کانال بکاپ", callback_data=with_owner("adm:backup:chclear", owner_id))
    b.button(
        text=f"⏱️ فاصله خودکار: {hours} ساعت" if hours > 0 else "⏱️ فاصله خودکار: خاموش",
        callback_data=with_owner("adm:backup:hours", owner_id),
    )
    b.button(text="⚡️ بکاپ فوری (چنل + ربات)", callback_data=with_owner("adm:backup:now", owner_id))
    b.button(text="⬅️ بازگشت", callback_data=with_owner("adm:tools:settings", owner_id))
    b.adjust(1)
    return b.as_markup()



def admin_worldbank_kb(owner_id: int, can_loan: bool = True) -> InlineKeyboardMarkup:
    """🆕 v1.7.8.2 — پنلِ بانک و گاوصندوق.

    دکمهٔ ریستِ وام فقط وقتی ساخته می‌شود که ادمین دسترسیِ اقتصاد داشته باشد؛
    تا هیچ دکمهٔ قفل‌شده‌ای نبیند (همان قاعدهٔ بالای این فایل).
    """
    b = InlineKeyboardBuilder()
    rows: list[int] = []
    b.button(text="🛡 درصد محافظت سپرده", callback_data=with_owner("adm:wb:pct", owner_id))
    b.button(text="♻️ بازگشت به پیش‌فرض", callback_data=with_owner("adm:wb:reset", owner_id))
    rows.append(2)
    b.button(text="💵 هزینه گاوصندوق Lv1", callback_data=with_owner("adm:wb:cost1", owner_id))
    b.button(text="💵 هزینه گاوصندوق Lv100", callback_data=with_owner("adm:wb:cost100", owner_id))
    rows.append(2)
    b.button(text="📦 سقف گاوصندوق Lv1", callback_data=with_owner("adm:wb:cap1", owner_id))
    b.button(text="📦 سقف گاوصندوق Lv100", callback_data=with_owner("adm:wb:cap100", owner_id))
    rows.append(2)
    if can_loan:
        b.button(text="🏦 ریست وام یک نفر", callback_data=with_owner("adm:loan:one", owner_id))
        b.button(text="🏦 ریست وام چند نفر", callback_data=with_owner("adm:loan:batch", owner_id))
        b.button(text="🏦 ریست وام همه", callback_data=with_owner("adm:loan:all", owner_id))
        rows += [2, 1]
    b.button(text="⬅️ بازگشت", callback_data=with_owner("adm:home", owner_id))
    rows.append(1)
    b.adjust(*rows)
    return b.as_markup()
