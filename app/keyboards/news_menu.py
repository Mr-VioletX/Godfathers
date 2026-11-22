# -*- coding: utf-8 -*-
"""کیبوردِ «اخبارِ روزانه» (مرحله ۲۰)."""
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.utils.ui import with_owner


def news_home_menu(owner_id):
    b = InlineKeyboardBuilder()
    b.button(text="🔄 تازه‌ترین اخبار", callback_data=with_owner("news:latest", owner_id))
    b.button(text="📅 خلاصه‌ی امروز", callback_data=with_owner("news:digest", owner_id))
    b.button(text="↩️ بازگشت به منو", callback_data=with_owner("menu:main", owner_id))
    b.adjust(2, 1)
    return b.as_markup()


def news_back_menu(owner_id):
    b = InlineKeyboardBuilder()
    b.button(text="↩️ بازگشت", callback_data=with_owner("menu:news", owner_id))
    b.adjust(1)
    return b.as_markup()


def news_digest_menu(post_id: int, page: int, total: int):
    """ناوبریِ صفحه‌های خلاصه‌ی روزانه — مشترک بین همه (کانال/خصوصی)، بدونِ مالک (v1.7.9.1)."""
    b = InlineKeyboardBuilder()
    if page > 0:
        b.button(text="◀️ قبلی", callback_data=f"news:dg:{post_id}:{page-1}")
    if page < total - 1:
        b.button(text="بعدی ▶️", callback_data=f"news:dg:{post_id}:{page+1}")
    b.adjust(2)
    if page > 0 or page < total - 1:
        return b.as_markup()
    return None
