# -*- coding: utf-8 -*-
"""کیبوردهای جنگ شخصی، رنکینگ و اتحادیه."""
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.data import war as W
from app.utils.ui import add_pager, paginate, with_owner


def back_only_menu(owner_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="↩️ بازگشت به منو", callback_data=with_owner("menu:main", owner_id))
    b.adjust(1)
    return b.as_markup()


def war_back_menu(owner_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="↩️ بازگشت به جنگ", callback_data=with_owner("war:hub", owner_id))
    b.adjust(1)
    return b.as_markup()


def war_home_menu(owner_id: int) -> InlineKeyboardMarkup:
    """خانه‌ی جنگ: رنکینگ، کلاسیک، اتحادیه و وضعیت."""
    b = InlineKeyboardBuilder()
    # 🆕 مرحله ۴۶ (بچ ۳) — سه نوعِ جنگ: رنکینگ، کلاسیک، اتحادیه
    b.button(text="🏅 جنگِ رنکینگ", callback_data=with_owner("war:ranked", owner_id))
    b.button(text="🔥 جنگِ کلاسیک", callback_data=with_owner("war:attack", owner_id))
    b.button(text="🛡️ جنگِ اتحادیه", callback_data=with_owner("all:war", owner_id))
    b.button(text="🏆 وضعیتِ رنکینگ", callback_data=with_owner("war:rstatus", owner_id))
    # 🆕 مرحله ۷۰ — بازآوردنِ گزارشِ نبرد پس از بستن/ردکردنِ پیام (مهاجم یا مدافع)
    b.button(text="📜 گزارشِ آخرین نبرد", callback_data=with_owner("war:report", owner_id))
    b.button(text="🛡️ وضعیتِ جنگی", callback_data=with_owner("war:status", owner_id))
    b.button(text="↩️ بازگشت به منو", callback_data=with_owner("menu:main", owner_id))
    b.adjust(1)
    return b.as_markup()


def attack_targets_menu(contacts: list, owner_id: int) -> InlineKeyboardMarkup:
    """انتخابِ هدف: از مخاطبین یا واردکردنِ دستیِ آیدی/یوزرنیم."""
    b = InlineKeyboardBuilder()
    for c in contacts[:20]:
        title = c.display_name or (f"@{c.username}" if c.username else str(c.contact_id))
        b.button(text=f"🎯 {title}", callback_data=with_owner(f"war:target:{c.contact_id}", owner_id))
    b.button(text="⌨️ واردکردنِ آیدی/یوزرنیم", callback_data=with_owner("war:manual", owner_id))
    b.button(text="↩️ بازگشت به جنگ", callback_data=with_owner("war:hub", owner_id))
    b.adjust(1)
    return b.as_markup()


def confirm_attack_menu(target_id: int, owner_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="⚔️ حمله!", callback_data=with_owner(f"war:strike:{target_id}", owner_id))
    b.button(text="↩️ انصراف", callback_data=with_owner("war:attack", owner_id))
    b.adjust(1)
    return b.as_markup()


# --------------------------- 🆕 مرحله ۴۶ — نبردِ زنده ---------------------------
def battle_live_menu(battle_id: int, owner_id: int, finished: bool = False, can_cease: bool = False) -> InlineKeyboardMarkup:
    """دکمه‌ی بروزرسانی + آتش‌بس.

    v1.7.6.3 - دکمه «🏥 بیمارستان» به درخواستِ کاربر از گزارشِ آخرین
    نبرد حذف شد؛ درمان/تعمیر فقط از مسیرِ
    «نطامی ← 🏥 بیمارستان / تعمیر» انجام می‌شود.
    """
    b = InlineKeyboardBuilder()
    if not finished:
        b.button(text="🔄 بروزرسانی گزارش", callback_data=with_owner(f"war:live:{battle_id}", owner_id))
        if can_cease:
            b.button(text="🕊️ آتش‌بس", callback_data=with_owner(f"war:cease:{battle_id}", owner_id))
    else:
        b.button(text="📜 گزارشِ آخرین نبرد", callback_data=with_owner("war:report", owner_id))
    b.button(text="↩️ بازگشت به جنگ", callback_data=with_owner("war:hub", owner_id))
    b.adjust(1)
    return b.as_markup()


# --------------------------- 🆕 مرحله ۴۶ (بچ ۳) — جنگِ رنکینگ ---------------------------
def ranked_targets_menu(entries, owner_id: int, page: int = 0, pages: int = 1):
    """فهرستِ اهدافِ مجاز (±۵۰ نفرِ اطراف در رتبه‌بندیِ کلی)."""
    b = InlineKeyboardBuilder()
    for e in entries:
        b.button(
            text=f"🎯 {e.name} — 🏆{e.cups:,} | 💥{e.power:,}",
            callback_data=with_owner(f"war:rtarget:{e.uid}", owner_id),
        )
    if page > 0:
        b.button(text="◀️ قبلی", callback_data=with_owner(f"war:rpage:{page - 1}", owner_id))
    if page < pages - 1:
        b.button(text=f"بعدی ▶️ ({page + 2}/{pages})", callback_data=with_owner(f"war:rpage:{page + 1}", owner_id))
    b.button(text="🏆 وضعیتِ رنکینگ", callback_data=with_owner("war:rstatus", owner_id))
    b.button(text="↩️ بازگشت به جنگ", callback_data=with_owner("war:hub", owner_id))
    b.adjust(1)
    return b.as_markup()


def ranked_confirm_menu(target_id: int, owner_id: int):
    b = InlineKeyboardBuilder()
    b.button(text="🏅 حمله‌ی رنکینگ!", callback_data=with_owner(f"war:rstrike:{target_id}", owner_id))
    b.button(text="↩️ انصراف", callback_data=with_owner("war:ranked", owner_id))
    b.adjust(1)
    return b.as_markup()
