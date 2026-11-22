# -*- coding: utf-8 -*-
"""کیبوردهایِ سیستمِ ورزشی (مرحله ۱۴).

callback ها (سپس with_owner شناسه‌ی صاحب را می‌چسباند):
  sport:hub                     — هابِ اصلی
  sport:open:<sport>            — بازکردنِ یک ورزش
  sport:create:<sport>          — ساختِ تیم/برند
  sport:play:<sport>            — اجرای مسابقه
  sport:up:<sport>:<what>       — ارتقا (stadium/coach/player/tire/brand/tech/driver/track)
  sport:budget:<sport>         — تزریقِ بودجه
  sport:brand:<sport>          — منوی برندسازی
  sport:rn:<sport>:<field>      — تغییرِ نامِ یک فیلد
  sport:league:<sport>         — جدولِ لیگ
  sport:events                  — ایونتِ هفته
"""
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.data import sports as S
from app.utils.ui import with_owner


def _btn(text: str, data: str, owner_id: int) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=with_owner(data, owner_id))


def sports_hub(owner_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for sport in S.ALL_SPORTS:
        b.button(text=S.SPORT_LABEL[sport], callback_data=with_owner(f"sport:open:{sport}", owner_id))
    b.button(text="📅 ایونت‌ها و نتایج", callback_data=with_owner("sport:events", owner_id))
    b.button(text="🏠 بازگشت به منو", callback_data=with_owner("menu:main", owner_id))
    b.adjust(2, 2, 1, 1)
    return b.as_markup()


def create_menu(owner_id: int, sport: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    label = "🆕 ساختِ برند" if sport in S.RACING_SPORTS else "🆕 ساختِ تیم"
    b.row(_btn(label, f"sport:create:{sport}", owner_id))
    b.row(_btn("🏆 جدولِ لیگ", f"sport:league:{sport}", owner_id))
    b.row(_btn("◀️ بازگشت", "sport:hub", owner_id))
    return b.as_markup()


def team_manage_menu(owner_id: int, sport: str) -> InlineKeyboardMarkup:
    """مدیریتِ تیمِ فوتبال/بسکتبال."""
    b = InlineKeyboardBuilder()
    b.row(_btn("🏟️ ارتقای استادیوم", f"sport:up:{sport}:stadium", owner_id),
          _btn("🧑‍🏫 ارتقای کادرِ فنی", f"sport:up:{sport}:coach", owner_id))
    b.row(_btn("⭐ خریدِ بازیکنِ ستاره", f"sport:up:{sport}:player", owner_id))
    b.row(_btn("💰 تزریقِ بودجه", f"sport:budget:{sport}", owner_id),
          _btn("🎨 برندسازی", f"sport:brand:{sport}", owner_id))
    b.row(_btn("🤝 مسابقهِ دوستانه", f"sport:play:{sport}", owner_id))
    b.row(_btn("🏆 ثبت‌نامِ لیگ", f"sport:regleague:{sport}", owner_id),
          _btn("📊 جدولِ لیگ", f"sport:league:{sport}", owner_id))
    b.row(_btn("◀️ بازگشت", "sport:hub", owner_id))
    return b.as_markup()


def brand_manage_menu(owner_id: int, sport: str) -> InlineKeyboardMarkup:
    """مدیریتِ برندِ F1/موتور."""
    b = InlineKeyboardBuilder()
    b.row(_btn("🚗 ارتقای برند", f"sport:up:{sport}:brand", owner_id),
          _btn("🛩️ کارخانه‌ی لاستیک", f"sport:up:{sport}:tire", owner_id))
    b.row(_btn("🔧 تیمِ فنی", f"sport:up:{sport}:tech", owner_id),
          _btn("🏁 استخدام/ارتقای راننده", f"sport:up:{sport}:driver", owner_id))
    b.row(_btn("🏟️ ساختِ پیست", f"sport:up:{sport}:track", owner_id),
          _btn("🎨 برندسازی", f"sport:brand:{sport}", owner_id))
    b.row(_btn("🏎️ مسابقه", f"sport:play:{sport}", owner_id),
          _btn("🏆 جدول", f"sport:league:{sport}", owner_id))
    b.row(_btn("◀️ بازگشت", "sport:hub", owner_id))
    return b.as_markup()


def branding_menu(owner_id: int, sport: str) -> InlineKeyboardMarkup:
    """منوی نام‌گذاری/شخصی‌سازی."""
    b = InlineKeyboardBuilder()
    if sport in S.TEAM_SPORTS:
        b.row(_btn("✏️ نامِ باشگاه", f"sport:rn:{sport}:name", owner_id))
        b.row(_btn("🎨 رنگِ پیراهن", f"sport:rn:{sport}:color", owner_id),
              _btn("💬 شعار", f"sport:rn:{sport}:slogan", owner_id))
        b.row(_btn("🏟️ نامِ استادیوم", f"sport:rn:{sport}:stadium", owner_id))
    else:
        b.row(_btn("✏️ نامِ برند", f"sport:rn:{sport}:name", owner_id))
        b.row(_btn("🎨 رنگِ ماشین", f"sport:rn:{sport}:color", owner_id),
              _btn("🏎️ نامِ تیمِ مسابقه", f"sport:rn:{sport}:raceteam", owner_id))
        b.row(_btn("🏟️ نامِ پیست", f"sport:rn:{sport}:track", owner_id))
    b.row(_btn("◀️ بازگشت", f"sport:open:{sport}", owner_id))
    return b.as_markup()


def after_match_menu(owner_id: int, sport: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(_btn("🔁 مسابقه‌ی دیگر", f"sport:play:{sport}", owner_id))
    b.row(_btn("🏆 جدولِ لیگ", f"sport:league:{sport}", owner_id),
          _btn("◀️ مدیریت", f"sport:open:{sport}", owner_id))
    return b.as_markup()


def back_menu(owner_id: int, sport: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(_btn("◀️ بازگشت", f"sport:open:{sport}", owner_id))
    return b.as_markup()


def events_menu(owner_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(_btn("◀️ بازگشت", "sport:hub", owner_id))
    return b.as_markup()
