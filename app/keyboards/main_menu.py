# app/keyboards/main_menu.py
from aiogram.types import (
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

from app.utils.ui import with_owner

# دکمه‌های کیبورد معمولی (فقط داخل ربات) — دزدی اینجا نیست چون فقط در گروه است
BTN_THEFT = "🕵️ دزدی"      # فقط برای گروه؛ دیگر در کیبورد ربات استفاده نمی‌شود
BTN_BASE = "🏰 پایگاه"
BTN_ESTATE = "🏛️ عمارت"
BTN_MARKET = "🏭 بازار"     # 🆕 مرحله ۹
BTN_PROFILE = "👤 پروفایل"
BTN_RANKING = "🏆 رنکینگ"
BTN_ASSISTANT = "🤖 دستیاران"  # 🆕 مرحله ۱۰
BTN_TITLES = "🏷 القاب"      # 🆕 مرحله ۱۱ (دیگر در منوی اصلی نیست؛ فقط داخلِ پروفایل)
BTN_CITY = "🏙️ شهر"        # 🆕 مرحله ۱۲
BTN_DARK_WORLD = "🌑 دنیای سیاه"  # مرحله ۸۷.۱ — اندگیم لول ۵۰+

# کلمات فرمان در گروه/ربات (بدون اسلش)
WORD_MENU = "منو"
WORD_THEFT = "دزدی"
WORD_BASE = "پایگاه"
WORD_ESTATE = "عمارت"
WORD_MARKET = "بازار"       # 🆕 مرحله ۹
WORD_PROFILE = "پروفایل"
WORD_RANKING = "رنکینگ"
WORD_TITLES = "القاب"       # 🆕 مرحله ۱۱
WORD_CITY = "شهر"          # 🆕 مرحله ۱۲
WORD_DARK_WORLD = "دنیای سیاه"
WORD_SPY = "جاسوسی"       # 🆕 مرحله ۱۳
WORD_CONTACTS = "مخاطبین"   # 🆕 مرحله ۱۳ (نامِ جدید در مرحله ۱۳.۶)
BTN_CHAT = "📡 خطِ محرمانه"   # 🆕 مرحله ۱۳.۶ — چت‌مود
WORD_CHAT = "چت مود"          # 🆕 مرحله ۱۳.۶
BTN_SPORTS = "⚽ ورزش"        # 🆕 مرحله ۱۴ — امپراتوریِ ورزشی
WORD_SPORTS = "ورزش"          # 🆕 مرحله ۱۴
BTN_WAREHOUSE = "🏢 انبارِ اصلی"   # 🆕 مرحله ۱۵
WORD_WAREHOUSE = "انبار"          # 🆕 مرحله ۱۵
WORD_MILITARY = "نظامی"        # 🆕 مرحله ۱۹ — سیستمِ نظامی
WORD_ALLIANCE = "اتحادیه"       # 🆕 مرحله ۱۸
WORD_BRAND = "برند"           # 🆕 مرحله ۱۹.۱
WORD_BANK = "بانک"            # 🆕 مرحله ۱۹.۲
WORD_SUBSCRIPTION = "اشتراک ویژه"   # 🆕 مرحله ۲۰
WORD_NEWS = "اخبار"            # 🆕 مرحله ۲۰
BTN_SUBSCRIPTION = "💎 اشتراک ویژه"   # 🆕 مرحله ۲۰
BTN_NEWS = "📰 اخبار"           # 🆕 مرحله ۲۰
BTN_WALKTHROUGH = "🎬 راهنما"   # 🆕 مرحله ۳۰ — دکمه‌ی راهنما در کیبوردِ زیری
WORD_WALKTHROUGH = "راهنما"          # 🆕 مرحله ۳۰
WORD_KEYBOARD = "کیبورد"           # 🆕 مرحله ۳۱ — بازآوریِ کیبوردِ زیرِ کادرِ تایپ
BTN_TRANSFER = "💸 انتقال"        # 🆕 مرحله ۲۱.۱
WORD_TRANSFER = "انتقال"          # 🆕 مرحله ۲۱.۱ — راهنما; فرمانِ واقعی «انتقال <مبلف>» است


def main_menu(show_assistant: bool = False) -> ReplyKeyboardMarkup:
    """کیبوردِ معمولیِ ربات (فقط چت خصوصی). دزدی و فعالیتِ گروهی اینجا نیستند.
    اگر show_assistant=True باشد (یعنی کاربر اولین عمارت را ساخته)، دکمه‌ی دستیار هم اضافه می‌شود.
    """
    builder = ReplyKeyboardBuilder()
    builder.add(
        # ⚡ مرحله ۲۸: ترتیب بر اساسِ اهمیت و توالیِ بازی
        KeyboardButton(text=BTN_BASE),
        KeyboardButton(text=BTN_ESTATE),
        KeyboardButton(text=BTN_MARKET),
        KeyboardButton(text=BTN_WAREHOUSE),
        KeyboardButton(text=BTN_CITY),
        KeyboardButton(text=BTN_DARK_WORLD),
        KeyboardButton(text=BTN_PROFILE),
        KeyboardButton(text=BTN_RANKING),
        KeyboardButton(text=BTN_SPORTS),
        KeyboardButton(text=BTN_CHAT),
        KeyboardButton(text=BTN_WALKTHROUGH),   # 🆕 مرحله ۳۰
    )
    if show_assistant:
        builder.add(KeyboardButton(text=BTN_ASSISTANT))   # 🆕 مرحله ۱۰
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)


def main_inline_menu(is_private: bool, owner_id: int) -> InlineKeyboardMarkup:
    """منوی شیشه‌ایِ مخصوصِ یک کاربر (هم در ربات، هم در گروه).
    - دزدی و «فعالیتِ گروهی» فقط در گروه نمایش داده می‌شوند.
    - جنگ/جاسوسی فعلاً فقط در ربات.
    - 🆕 مرحله ۱۲: عمارت/بازار/دستیار/شهر به منوی گروه هم اضافه شدند تا
      دکمه‌های گروه با امکاناتِ ربات هماهنگ باشند. مدیریتِ این بخش‌ها فقط
      داخلِ خودِ ربات ممکن است؛ اگر کاربر داخلِ گروه بزند، خودِ هندلر او را
      با پیام «فقط داخلِ ربات» راهنمایی می‌کند.
    """
    builder = InlineKeyboardBuilder()
    # ⚡ مرحله ۲۸: ترتیبِ منوی شیشه‌ای بر اساسِ اهمیت و توالیِ بازی:
    # درآمد و تولید ← شهر ← جنگ ← اقتصادِ پیشرفته ← اجتماعی ← فرعی
    if not is_private:
        builder.button(text="🕵️ دزدی", callback_data=with_owner("menu:theft", owner_id))
    builder.button(text="🏰 پایگاه", callback_data=with_owner("menu:base", owner_id))
    builder.button(text="🏛️ عمارت", callback_data=with_owner("menu:estate", owner_id))
    builder.button(text="🏭 بازار", callback_data=with_owner("menu:market", owner_id))
    if is_private:
        # 🔄 مرحله ۱۵.۵: انبار فقط داخلِ خودِ ربات
        builder.button(text="🏢 انبار", callback_data=with_owner("menu:warehouse", owner_id))
    builder.button(text="🏙️ شهر", callback_data=with_owner("menu:city", owner_id))
    builder.button(text="🌑 دنیای سیاه", callback_data=with_owner("menu:darkworld", owner_id))
    if is_private:
        builder.button(text="⚔️ جنگ", callback_data=with_owner("menu:war", owner_id))
        builder.button(text="🎖️ نظامی", callback_data=with_owner("menu:military", owner_id))
        builder.button(text="🏦 بانک مافیایی", callback_data=with_owner("menu:worldbank", owner_id))
    # 🆕 مرحله ۲۹: دکمه‌ی «برند» قبلاً فقط در ربات بود؛ حالا در گروه هم نمایش داده می‌شود
    builder.button(text="🏷️ برند", callback_data=with_owner("menu:branding", owner_id))
    builder.button(text="⚽ ورزش", callback_data=with_owner("menu:sports", owner_id))
    builder.button(text="🛡️ اتحادیه", callback_data=with_owner("menu:alliance", owner_id))
    if is_private:
        builder.button(text="🕶️ جاسوسی", callback_data=with_owner("menu:spy", owner_id))
        builder.button(text="👥 مخاطبین", callback_data=with_owner("menu:contacts", owner_id))
    builder.button(text="👤 پروفایل", callback_data=with_owner("menu:profile", owner_id))
    builder.button(text="🏆 رنکینگ", callback_data=with_owner("menu:ranking", owner_id))
    builder.button(text="💸 انتقال", callback_data=with_owner("transfer:info", owner_id))
    builder.button(text="🤖 دستیاران", callback_data=with_owner("menu:assistant", owner_id))
    builder.button(text="💎 اشتراک", callback_data=with_owner("menu:sub", owner_id))
    builder.button(text="📰 اخبار", callback_data=with_owner("menu:news", owner_id))
    if is_private:
        builder.button(text="🎬 راهنما", callback_data=with_owner("menu:walkthrough", owner_id))
    builder.adjust(2)
    return builder.as_markup()
