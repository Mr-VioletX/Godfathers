# app/keyboards/contacts_menu.py
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.utils.ui import with_owner


def contacts_menu(contacts: list, owner_id: int) -> InlineKeyboardMarkup:
    """لیستِ اشخاصِ اضافه‌شده با دکمهٔ حذف برای هرکدام + بازگشت."""
    b = InlineKeyboardBuilder()
    b.button(text="➕ افزودن دستی مخاطب", callback_data=with_owner("contact:addmanual", owner_id))
    for c in contacts[:25]:
        title = c.display_name or (f"@{c.username}" if c.username else str(c.contact_id))
        b.button(
            text=f"🗑️ {title}",
            callback_data=with_owner(f"contact:del:{c.contact_id}", owner_id),
        )
    b.button(text="↩️ بازگشت به منو", callback_data=with_owner("menu:main", owner_id))
    b.adjust(1)
    return b.as_markup()


def contacts_back_menu(owner_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="↩️ بازگشت به منو", callback_data=with_owner("menu:main", owner_id))
    b.adjust(1)
    return b.as_markup()
