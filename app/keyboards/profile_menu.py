from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.utils.ui import with_owner


def profile_menu(owner_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✏️ تغییر نام", callback_data=with_owner("profile:edit_name", owner_id))
    builder.button(text="🏷 القاب", callback_data=with_owner("titles:home", owner_id))
    builder.button(text="⚧ تغییر جنسیت", callback_data=with_owner("profile:edit_gender", owner_id))
    builder.button(text="🖼️ تغییر عکس", callback_data=with_owner("profile:edit_photo", owner_id))
    builder.button(text="🔒 حریم خصوصی", callback_data=with_owner("profile:privacy", owner_id))
    builder.button(text="📣 اعلام آنلاین", callback_data=with_owner("profile:announce", owner_id))
    builder.button(text="🔗 لینک دعوت من", callback_data=with_owner("profile:referral", owner_id))
    builder.button(text="↩️ بازگشت به منو", callback_data=with_owner("menu:main", owner_id))
    builder.adjust(2)
    return builder.as_markup()


def profile_back_menu(owner_id: int) -> InlineKeyboardMarkup:
    """کیبوردِ کوتاهِ پروفایل در گروه: فقط دکمه‌ی «بازگشت به منو»."""
    builder = InlineKeyboardBuilder()
    builder.button(text="↩️ بازگشت به منو", callback_data=with_owner("menu:main", owner_id))
    return builder.as_markup()


def edit_cancel_menu(owner_id: int) -> InlineKeyboardMarkup:
    """دکمه‌ی «انصراف» هنگامِ تغییرِ نام (و مواردِ مشابه)."""
    builder = InlineKeyboardBuilder()
    builder.button(text="✖️ انصراف", callback_data=with_owner("profile:cancel", owner_id))
    builder.adjust(1)
    return builder.as_markup()


def photo_edit_menu(owner_id: int, has_photo: bool) -> InlineKeyboardMarkup | None:
    """منوی ویرایشِ عکسِ پروفایل: فقط «حذفِ عکس» (اگر عکسی هست).

    🆕 مرحله ۲۹: دکمهِ «✖️ انصراف» حذف شد؛ این حالت الان با واژهِ متنی
    «انصراف» پوشش داده می‌شود.
    """
    builder = InlineKeyboardBuilder()
    if has_photo:
        builder.button(text="🗑️ حذفِ عکس", callback_data=with_owner("profile:photo_delete", owner_id))
        builder.adjust(1)
        return builder.as_markup()
    return None


def gender_inline_menu(owner_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="👔 The Don (مرد)", callback_data=with_owner("setgender:male", owner_id))
    builder.button(text="👗 La Donna (زن)", callback_data=with_owner("setgender:female", owner_id))
    builder.button(text="↩️ بازگشت", callback_data=with_owner("profile:back", owner_id))
    builder.adjust(2)
    return builder.as_markup()
