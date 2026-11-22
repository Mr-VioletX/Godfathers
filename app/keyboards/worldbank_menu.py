# -*- coding: utf-8 -*-
"""کیبوردهای مرحله ۱۹.۲ — بانکِ مافیایی. پیشوندِ کالبک: wb:"""
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.utils.ui import with_owner


def wb_back_menu(owner_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="↩️ بازگشت به بانک", callback_data=with_owner("wb:hub", owner_id))
    b.adjust(1)
    return b.as_markup()


def wb_home_menu(owner_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="💰 ثروتِ خالصِ من", callback_data=with_owner("wb:networth", owner_id))
    b.button(text="🏦 سپرده‌گذاری", callback_data=with_owner("wb:deposit", owner_id))
    b.button(text="🏧 برداشت", callback_data=with_owner("wb:withdraw", owner_id))
    b.button(text="🔐 گاوصندوق", callback_data=with_owner("wb:safebox", owner_id))
    b.button(text="🏦 دریافتِ وام", callback_data=with_owner("wb:loan", owner_id))
    b.button(text="✅ تسویه‌ی وام", callback_data=with_owner("wb:repay", owner_id))
    b.button(text="🏆 ثروتمندانِ جهان", callback_data=with_owner("wb:rich:0", owner_id))
    b.button(text="↩️ بازگشت به منو", callback_data=with_owner("menu:main", owner_id))
    b.adjust(2)
    return b.as_markup()


def rich_menu(owner_id: int, page: int, total: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    if page > 0:
        b.button(text="◀️ قبلی", callback_data=with_owner(f"wb:rich:{page-1}", owner_id))
    if page < total - 1:
        b.button(text="بعدی ▶️", callback_data=with_owner(f"wb:rich:{page+1}", owner_id))
    b.button(text="↩️ بازگشت", callback_data=with_owner("wb:hub", owner_id))
    b.adjust(2)
    return b.as_markup()


def wb_safebox_menu(owner_id: int, has_box: bool = False) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="⬆️ ارتقا گاوصندوق", callback_data=with_owner("wb:sb:up", owner_id))
    if has_box:
        b.button(text="📥 واریز به گاوصندوق", callback_data=with_owner("wb:sb:in", owner_id))
        b.button(text="📤 برداشت از گاوصندوق", callback_data=with_owner("wb:sb:out", owner_id))
    b.button(text="↩️ بازگشت به بانک", callback_data=with_owner("wb:hub", owner_id))
    b.adjust(1)
    return b.as_markup()

