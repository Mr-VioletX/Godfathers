# -*- coding: utf-8 -*-
"""🆕 مرحله ۲۸ — کیبوردهایِ مشترک.

دکمه‌ی «انصراف» برای هر جایی که ربات از کاربر مقدار/متن می‌گیرد.
"""
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.utils.ui import with_owner

CANCEL_CB = "ui:cancel"
CANCEL_TEXT = "✖ انصراف"


def cancel_menu(owner_id: int | None = None, back_to: str | None = None) -> InlineKeyboardMarkup:
    """کیبوردِ تک‌دکمه‌ی انصراف (و در صورتِ دلخواه، بازگشت به یک منو)."""
    b = InlineKeyboardBuilder()
    cb = with_owner(CANCEL_CB, owner_id) if owner_id else CANCEL_CB
    b.button(text=CANCEL_TEXT, callback_data=cb)
    if back_to:
        b.button(text="↩️ بازگشت", callback_data=back_to)
    b.adjust(1)
    return b.as_markup()
