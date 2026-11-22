# app/keyboards/assistant_menu.py
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.utils.ui import with_owner
from app.data.assistant import ASSISTANT_COST, next_upgrade


def back_only_menu(owner_id):
    """فقط دکمه‌ی «بازگشت به منو» — برای حالتِ قفل یا نبودِ پیش‌نیاز."""
    b = InlineKeyboardBuilder()
    b.button(text="↩️ بازگشت به منو", callback_data=with_owner("menu:main", owner_id))
    b.adjust(1)
    return b.as_markup()


def buy_menu(owner_id):
    """وقتی دستیار هنوز خریده نشده."""
    b = InlineKeyboardBuilder()
    b.button(
        text=f"🛒 خریدِ دستیار ({ASSISTANT_COST:,}$)",
        callback_data=with_owner("assistant:buy", owner_id),
    )
    b.button(text="↩️ بازگشت به منو", callback_data=with_owner("menu:main", owner_id))
    b.adjust(1)
    return b.as_markup()


def panel_menu(owner_id):
    """پنلِ اصلیِ دستیار (در ربات) — 🆕 v1.7.5 دکمه‌های پویا."""
    b = InlineKeyboardBuilder()
    b.button(text="💓 نبض امپراتوری", callback_data=with_owner("assistant:pulse", owner_id))
    b.button(text="🎯 فرصت‌یاب", callback_data=with_owner("assistant:ops", owner_id))
    b.button(text="⚔️ آمادگی جنگ", callback_data=with_owner("assistant:war", owner_id))
    b.button(text="🎖️ مأموریت روزانه", callback_data=with_owner("assistant:mission", owner_id))
    b.button(text="📡 رصد میدان", callback_data=with_owner("assistant:radar", owner_id))
    b.button(text="📋 گزارش کامل", callback_data=with_owner("assistant:report", owner_id))
    b.button(text="⏰ کارهای عقب‌مانده", callback_data=with_owner("assistant:reminders", owner_id))
    b.button(text="🧠 ارتقای دستیار", callback_data=with_owner("assistant:upgrade", owner_id))
    b.button(text="✏️ نام", callback_data=with_owner("assistant:edit:name", owner_id))
    b.button(text="🖼️ عکس", callback_data=with_owner("assistant:edit:photo", owner_id))
    b.button(text="⚙️ یادآوری", callback_data=with_owner("assistant:settings", owner_id))
    b.button(text="↩️ بازگشت به منو", callback_data=with_owner("menu:main", owner_id))
    b.adjust(2, 2, 2, 2, 2, 1, 1)
    return b.as_markup()


def live_actions_menu(owner_id):
    """منوی جمع‌وجور زیر گزارش‌های پویا."""
    b = InlineKeyboardBuilder()
    b.button(text="💓 نبض", callback_data=with_owner("assistant:pulse", owner_id))
    b.button(text="🎯 فرصت", callback_data=with_owner("assistant:ops", owner_id))
    b.button(text="⚔️ جنگ", callback_data=with_owner("assistant:war", owner_id))
    b.button(text="🎖️ مأموریت", callback_data=with_owner("assistant:mission", owner_id))
    b.button(text="📡 میدان", callback_data=with_owner("assistant:radar", owner_id))
    b.button(text="🏠 پنل دستیار", callback_data=with_owner("assistant:hub", owner_id))
    b.adjust(3, 2, 1)
    return b.as_markup()


def upgrade_menu(owner_id, level):
    """منوی ارتقایِ دستیار. اگر سطحِ بعدی وجود داشته باشد، دکمه‌ی خرید."""
    b = InlineKeyboardBuilder()
    nxt = next_upgrade(level)
    if nxt is not None:
        b.button(
            text=f"⬆️ ارتقا به «{nxt['name']}» ({nxt['cost']:,}$)",
            callback_data=with_owner("assistant:upgrade:do", owner_id),
        )
    b.button(text="↩️ بازگشت", callback_data=with_owner("assistant:hub", owner_id))
    b.adjust(1)
    return b.as_markup()


def settings_menu(assistant, owner_id):
    """منوی تنظیماتِ یادآوری (روشن/خاموش)."""
    b = InlineKeyboardBuilder()

    def mark(v):
        return "✅" if v else "❌"

    b.button(
        text=f"{mark(assistant.notify_salary)} حقوقِ عقب‌افتاده",
        callback_data=with_owner("assistant:toggle:salary", owner_id),
    )
    b.button(
        text=f"{mark(assistant.notify_production)} کارخانه/تولید",
        callback_data=with_owner("assistant:toggle:production", owner_id),
    )
    b.button(
        text=f"{mark(assistant.notify_income)} درآمدِ عمارت",
        callback_data=with_owner("assistant:toggle:income", owner_id),
    )
    b.button(
        text=f"{mark(assistant.notify_tips)} راهنمای پیشرفت",
        callback_data=with_owner("assistant:toggle:tips", owner_id),
    )
    b.button(text="↩️ بازگشت", callback_data=with_owner("assistant:hub", owner_id))
    b.adjust(1)
    return b.as_markup()


def edit_cancel_menu(owner_id):
    """دکمه‌ی انصراف هنگامِ ویرایشِ نام/عکس."""
    b = InlineKeyboardBuilder()
    b.button(text="✖️ انصراف", callback_data=with_owner("assistant:hub", owner_id))
    b.adjust(1)
    return b.as_markup()


def photo_edit_menu(owner_id, has_photo: bool):
    """منوی ویرایشِ عکسِ دستیار: فقط «حذفِ عکس» (اگر عکسی تنظیم شده).

    🆕 مرحله ۲۹: دکمهِ «✖️ انصراف» حذف شد چون این حالت متنی با واژهِ «انصراف»
    (CANCEL_HINT + handle_cancel_word در assistant.py) پوشش داده می‌شود و وجودِ هم‌زمانی دکمه
    باعثِ سردرگمی می‌شد (دکمه ظاهراً هست ولی کلیک رویش همیشه دوباره مقدار می‌خواست).
    """
    b = InlineKeyboardBuilder()
    if has_photo:
        b.button(text="🗑️ حذفِ عکس", callback_data=with_owner("assistant:photo:delete", owner_id))
        b.adjust(1)
        return b.as_markup()
    return None


def group_menu(owner_id):
    """دکمه‌های شیشه‌ایِ دستیار در گروه."""
    b = InlineKeyboardBuilder()
    b.button(text="📋 گزارشِ روزانه", callback_data=with_owner("assistant:pubreport", owner_id))
    b.button(text="🔐 گزارشِ محرمانه (در ربات)", callback_data=with_owner("assistant:privreport", owner_id))
    b.button(text="↩️ بازگشت به منو", callback_data=with_owner("menu:main", owner_id))
    b.adjust(1)
    return b.as_markup()


def assistants_home_menu(owner_id, has_second: bool):
    b = InlineKeyboardBuilder()
    b.button(text="🤵 دستیار اول", callback_data=with_owner("assistant:hub", owner_id))
    b.button(text=("🧩 دستیار دوم" if has_second else "🔒 دستیار دومِ اشتراکی"), callback_data=with_owner("assistant2:hub", owner_id))
    b.button(text="↩️ بازگشت به منو", callback_data=with_owner("menu:main", owner_id))
    b.adjust(2, 1); return b.as_markup()

def assistant2_menu(owner_id, configured: bool):
    b=InlineKeyboardBuilder()
    b.button(text="✏️ ویرایش نام", callback_data=with_owner("assistant2:name", owner_id))
    b.button(text="💬 تنظیم دستور و جواب", callback_data=with_owner("assistant2:command", owner_id))
    b.button(text="🖼️ ویرایش عکس", callback_data=with_owner("assistant2:photo", owner_id))
    b.button(text="📘 راهنمای پاسخ", callback_data=with_owner("assistant2:help", owner_id))
    b.button(text="↩️ بازگشت", callback_data=with_owner("assistant:home", owner_id))
    b.adjust(2, 1, 1, 1); return b.as_markup()

def assistant2_buy_menu(owner_id):
    b=InlineKeyboardBuilder(); b.button(text="✅ فعال‌سازی دستیار دوم", callback_data=with_owner("assistant2:buy", owner_id)); b.button(text="↩️ بازگشت", callback_data=with_owner("assistant:home", owner_id)); b.adjust(1); return b.as_markup()


def assistant2_chat_menu(owner_id):
    b=InlineKeyboardBuilder()
    b.button(text="🛑 پایان چت با دستیار دوم", callback_data=with_owner("assistant2:end", owner_id))
    b.adjust(1); return b.as_markup()
