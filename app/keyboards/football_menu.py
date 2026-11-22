# -*- coding: utf-8 -*-
"""v1.7.9.2 — کیبوردهای فوتبال منیجر (مرحله ۷۹ — فاز F1). پیشوند کالبک: fb:"""
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.utils.ui import with_owner


def football_no_club_menu(owner_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="🏟️ ساخت باشگاه", callback_data=with_owner("fb:create", owner_id))
    b.button(text="📖 راهنمای فوتبال", callback_data=with_owner("fb:guide", owner_id))
    b.button(text="◀️ بازگشت", callback_data=with_owner("sport:hub", owner_id))
    b.adjust(1)
    return b.as_markup()


def football_hub_menu(owner_id: int) -> InlineKeyboardMarkup:
    """هاب باشگاه — خوشه‌ای و دوسطونه (v1.8.1.5): جزئیات در ۴ زیرمنو."""
    b = InlineKeyboardBuilder()
    b.button(text="🤝 بازی دوستانه", callback_data=with_owner("fb:play", owner_id))
    b.button(text="🎮 بازی زنده", callback_data=with_owner("fb:live", owner_id))
    b.button(text="📜 آخرین نتایج", callback_data=with_owner("fb:results", owner_id))
    b.button(text="📖 راهنما", callback_data=with_owner("fb:guide", owner_id))
    b.button(text="👥 تیم و تاکتیک", callback_data=with_owner("fb:sec:team", owner_id))
    b.button(text="🏟️ باشگاه و هوادار", callback_data=with_owner("fb:sec:club", owner_id))
    b.button(text="🛒 بازار و فروشگاه", callback_data=with_owner("fb:sec:shop", owner_id))
    b.button(text="🏆 رقابت‌ها", callback_data=with_owner("fb:sec:comp", owner_id))
    b.button(text="◀️ بازگشت به ورزش", callback_data=with_owner("sport:hub", owner_id))
    b.adjust(2, 2, 1, 1, 1, 1, 1)
    return b.as_markup()


def football_sec_team_menu(owner_id: int) -> InlineKeyboardMarkup:
    """👥 تیم و تاکتیک."""
    b = InlineKeyboardBuilder()
    b.button(text="🧑‍💼 بازیکن‌ها و نیمکت", callback_data=with_owner("fb:squad:0", owner_id))
    b.button(text="👤 ترکیب و تاکتیک", callback_data=with_owner("fb:tactics", owner_id))
    b.button(text="🧠 سرمربی", callback_data=with_owner("fb:coach", owner_id))
    b.button(text="🏋️ تمرین و کمپ", callback_data=with_owner("fb:train", owner_id))
    b.button(text="⚽ بازگشت به باشگاه", callback_data=with_owner("fb:hub", owner_id))
    b.adjust(1)
    return b.as_markup()


def football_sec_club_menu(owner_id: int) -> InlineKeyboardMarkup:
    """🏟️ باشگاه و هوادار."""
    b = InlineKeyboardBuilder()
    b.button(text="🏟️ استادیوم و هوادار", callback_data=with_owner("fb:stadium", owner_id))
    b.button(text="📱 سوشال مدیا", callback_data=with_owner("fb:social", owner_id))
    b.button(text="⚽ بازگشت به باشگاه", callback_data=with_owner("fb:hub", owner_id))
    b.adjust(1)
    return b.as_markup()


def football_sec_shop_menu(owner_id: int) -> InlineKeyboardMarkup:
    """🛒 بازار و فروشگاه."""
    b = InlineKeyboardBuilder()
    b.button(text="🛒 بازار نقل‌وانتقال", callback_data=with_owner("fb:market", owner_id))
    b.button(text="🧑‍✈️ فروشگاه سرمربی ۵⭐", callback_data=with_owner("fb:coachshop:0", owner_id))
    b.button(text="⚽ بازگشت به باشگاه", callback_data=with_owner("fb:hub", owner_id))
    b.adjust(1)
    return b.as_markup()


def football_sec_comp_menu(owner_id: int) -> InlineKeyboardMarkup:
    """🏆 رقابت‌ها — لیگ و UCL."""
    b = InlineKeyboardBuilder()
    b.button(text="🏆 لیگ و جدول", callback_data=with_owner("fb:league:0", owner_id))
    b.button(text="🗓️ لیگ جمعه (رسمی)", callback_data=with_owner("fb:friday", owner_id))
    b.button(text="🌟 لیگ قهرمانان (دوشنبه)", callback_data=with_owner("fb:ucl", owner_id))
    b.button(text="⚽ بازگشت به باشگاه", callback_data=with_owner("fb:hub", owner_id))
    b.adjust(1)
    return b.as_markup()


def football_back_menu(owner_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="⚽ بازگشت به باشگاه", callback_data=with_owner("fb:hub", owner_id))
    b.adjust(1)
    return b.as_markup()


def football_coach_menu(owner_id: int, current_style: str) -> InlineKeyboardMarkup:
    from app.data.football_progress import COACH_STYLES, STYLE_ORDER
    b = InlineKeyboardBuilder()
    for key in STYLE_ORDER:
        s = COACH_STYLES[key]
        mark = "✅ " if key == current_style else ""
        b.button(text=f"{mark}{s['name']}", callback_data=with_owner(f"fb:coach:style:{key}", owner_id))
    b.button(text="⭐ ساخت ستاره بعدی", callback_data=with_owner("fb:coach:star", owner_id))
    b.button(text="⚽ بازگشت به باشگاه", callback_data=with_owner("fb:hub", owner_id))
    b.adjust(2, 2, 1, 1)
    return b.as_markup()


def football_stadium_menu(owner_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="⬆️ ارتقای استادیوم", callback_data=with_owner("fb:stadium:up", owner_id))
    b.button(text="⚽ بازگشت به باشگاه", callback_data=with_owner("fb:hub", owner_id))
    b.adjust(1)
    return b.as_markup()


def football_social_menu(owner_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="📤 بارگذاری پست (عکس)", callback_data=with_owner("fb:social:post", owner_id))
    b.button(text="⚽ بازگشت به باشگاه", callback_data=with_owner("fb:hub", owner_id))
    b.adjust(1)
    return b.as_markup()


def football_training_menu(owner_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="🏗️ ساخت کمپ بعدی", callback_data=with_owner("fb:train:camp", owner_id))
    b.button(text="▶️ انجام جلسه تمرین", callback_data=with_owner("fb:train:go", owner_id))
    b.button(text="⚽ بازگشت به باشگاه", callback_data=with_owner("fb:hub", owner_id))
    b.adjust(1)
    return b.as_markup()
