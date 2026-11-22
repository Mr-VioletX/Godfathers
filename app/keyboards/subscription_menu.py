# -*- coding: utf-8 -*-
"""کیبوردِ «اشتراکِ ویژه (۴ سطحی)» (مرحله ۲۰)."""
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.utils.ui import with_owner
from app.data import subscription as S


def sub_home_menu(owner_id, tiers=None):
    """صفحه‌ی اصلیِ اشتراک: دکمه برای دیدنِ جزئیاتِ هر سطح + تاریخچه‌ی خرید.

    tiers: 🆕 فهرستِ اختیاریِ سطوح (معمولاً effective_tiers با قیمتِ override‌شده)؛ اگر None، از S.paid_tiers() استفاده می‌شود.
    """
    b = InlineKeyboardBuilder()
    for tier in (tiers if tiers is not None else S.paid_tiers()):
        b.button(
            text=f"{tier['emoji']} {tier['name']} — {tier['price']:,}$",
            callback_data=with_owner(f"sub:view:{tier['key']}", owner_id),
        )
    b.button(text="💳 درخواست‌های تأییدشده و پرداخت", callback_data=with_owner("sub:paylist", owner_id))
    b.button(text="📜 تاریخچه‌ی خرید", callback_data=with_owner("sub:history", owner_id))
    b.button(text="↩️ بازگشت به منو", callback_data=with_owner("menu:main", owner_id))
    b.adjust(1)
    return b.as_markup()


def receipt_ask_kb(owner_id):
    """🆕 پس از ثبتِ درخواست: درخواستِ اختیاریِ رسید (یا رد/فعلاً‌ندارم)."""
    b = InlineKeyboardBuilder()
    b.button(text="⏭️ فعلاً رسید ندارم", callback_data=with_owner("sub:receipt:skip", owner_id))
    b.button(text="📜 تاریخچه‌ی خرید", callback_data=with_owner("sub:history", owner_id))
    b.adjust(1)
    return b.as_markup()


def sub_view_menu(owner_id, tier_key):
    """زیرِ نمایِ جزئیاتِ یک سطح + دکمه‌ی درخواستِ خریدِ همان سطح."""
    b = InlineKeyboardBuilder()
    b.button(
        text="🛒 درخواستِ خریدِ این سطح",
        callback_data=with_owner(f"sub:request:{tier_key}", owner_id),
    )
    b.button(text="📜 تاریخچه‌ی خرید", callback_data=with_owner("sub:history", owner_id))
    b.button(text="↩️ بازگشت", callback_data=with_owner("menu:sub", owner_id))
    b.adjust(1)
    return b.as_markup()


def sub_history_menu(owner_id):
    b = InlineKeyboardBuilder()
    b.button(text="↩️ بازگشت", callback_data=with_owner("menu:sub", owner_id))
    b.adjust(1)
    return b.as_markup()


def paylist_menu(owner_id, rows):
    b = InlineKeyboardBuilder()
    for r in rows:
        b.button(
            text=f"💳 پرداخت {r.tracking_code}",
            callback_data=with_owner(f"sub:pay:{r.tracking_code}", owner_id),
        )
    b.button(text="↩️ بازگشت", callback_data=with_owner("menu:sub", owner_id))
    b.adjust(1)
    return b.as_markup()


def pay_detail_menu(owner_id, code):
    b = InlineKeyboardBuilder()
    b.button(text="🧾 ارسال رسید", callback_data=with_owner(f"sub:sendrec:{code}", owner_id))
    b.button(text="↩️ بازگشت", callback_data=with_owner("sub:paylist", owner_id))
    b.adjust(1)
    return b.as_markup()
