# -*- coding: utf-8 -*-
"""Owner-bound menus for Stage 87.3 pursuit and hideout."""
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from app.data import dark_world_pursuit as P
from app.utils.ui import with_owner


def pursuit_menu(owner_id: int, has_threat: bool, can_recon: bool, in_prison: bool = False) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    if in_prison:
        b.button(text="🗺️ طرح فرار", callback_data=with_owner("dwp:escape", owner_id))
    else:
        if has_threat and can_recon:
            b.button(text="🔎 جمع‌آوری سرنخ (۱ اطلاعات)", callback_data=with_owner("dwp:recon", owner_id))
        if has_threat:
            b.button(text="♟️ انتخاب ضدنقشه", callback_data=with_owner("dwp:plans", owner_id))
        b.button(text="🏚️ ارتقای مخفیگاه", callback_data=with_owner("dwp:upgrade", owner_id))
        b.button(text="🎭 خرید هویت جعلی", callback_data=with_owner("dwp:buyid", owner_id))
    b.button(text="🔄 بروزرسانی وضعیت", callback_data=with_owner("dwp:hub", owner_id))
    b.button(text="↩️ دنیای سیاه", callback_data=with_owner("dw:sec:ops", owner_id))
    b.adjust(1)
    return b.as_markup()


def plans_menu(owner_id: int, chances: dict[str, dict], forged_ids: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for key in P.ACTION_ORDER:
        action = P.ACTIONS[key]
        info = chances.get(key) or {}
        locked = key == "disguise" and forged_ids <= 0
        label = f"{'🔒' if locked else action['icon']} {action['name']} · {float(info.get('chance', 0)):.0f}٪"
        data = "dwp:noid" if locked else f"dwp:plan:{key}"
        b.button(text=label, callback_data=with_owner(data, owner_id))
    b.button(text="↩️ پرونده تعقیب", callback_data=with_owner("dwp:hub", owner_id))
    b.adjust(1)
    return b.as_markup()


def confirm_plan_menu(action_key: str, owner_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="✅ اجرای ضدنقشه", callback_data=with_owner(f"dwp:do:{action_key}", owner_id))
    b.button(text="↩️ تغییر تصمیم", callback_data=with_owner("dwp:plans", owner_id))
    b.adjust(1)
    return b.as_markup()


def escape_menu(owner_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="🗝️ تونل خدماتی · امن‌تر/پرهزینه", callback_data=with_owner("dwp:break:tunnel", owner_id))
    b.button(text="📄 جعل حکم آزادی · فکری/اطلاعاتی", callback_data=with_owner("dwp:break:papers", owner_id))
    b.button(text="💥 شورش کنترل‌شده · پرریسک", callback_data=with_owner("dwp:break:riot", owner_id))
    b.button(text="↩️ وضعیت", callback_data=with_owner("dwp:hub", owner_id))
    b.adjust(1)
    return b.as_markup()
