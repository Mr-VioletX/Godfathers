# -*- coding: utf-8 -*-
"""کیبوردهای سیستمِ القاب (مرحله ۱۱).

همه‌ی دکمه‌های inline با with_owner(...) بسته می‌شوند تا فقط صاحبِ منو بتواند
رویِ آن‌ها بزند (هم‌راستا با مرحله‌ی ۱۰).
"""
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.utils.ui import with_owner


def titles_home_kb(owner_id: int, sub_active: bool) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(
            text="🏷 القابِ من", callback_data=with_owner("titles:mine", owner_id)
        )
    )
    b.row(
        InlineKeyboardButton(
            text="⭐ تنظیمِ لقبِ فعال",
            callback_data=with_owner("titles:choose", owner_id),
        )
    )
    sub_text = "👑 مدیریتِ اشتراک" if sub_active else "👑 خریدِ اشتراک (لقبِ دلخواه)"
    b.row(
        InlineKeyboardButton(
            text=sub_text, callback_data=with_owner("titles:sub", owner_id)
        )
    )
    b.row(
        InlineKeyboardButton(
            text="🏠 بازگشت به منو", callback_data=with_owner("menu:main", owner_id)
        )
    )
    return b.as_markup()


def choose_active_kb(owner_id: int, titles: list[dict]) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for t in titles[:40]:
        b.row(
            InlineKeyboardButton(
                text=f"{t['name']}",
                callback_data=with_owner(f"titles:set:{t['key']}", owner_id),
            )
        )
    b.row(
        InlineKeyboardButton(
            text="🗑 حذف لقب",
            callback_data=with_owner("titles:clear", owner_id),
        )
    )
    b.row(
        InlineKeyboardButton(
            text="❌ انصراف", callback_data=with_owner("titles:home", owner_id)
        )
    )
    return b.as_markup()


def subscription_kb(owner_id: int, sub_active: bool) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    if sub_active:
        b.row(
            InlineKeyboardButton(
                text="✍ نوشتن/تغییرِ لقبِ دلخواه",
                callback_data=with_owner("titles:custom", owner_id),
            )
        )
        b.row(
            InlineKeyboardButton(
                text="♻ تمدیدِ اشتراک",
                callback_data=with_owner("titles:sub:buy", owner_id),
            )
        )
    else:
        b.row(
            InlineKeyboardButton(
                text="💳 خریدِ اشتراک",
                callback_data=with_owner("titles:sub:buy", owner_id),
            )
        )
    b.row(
        InlineKeyboardButton(
            text="↩️ بازگشت", callback_data=with_owner("titles:home", owner_id)
        )
    )
    return b.as_markup()


def back_kb(owner_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(
            text="↩️ بازگشت", callback_data=with_owner("titles:home", owner_id)
        )
    )
    return b.as_markup()
