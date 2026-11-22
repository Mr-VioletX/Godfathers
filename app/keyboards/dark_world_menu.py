# -*- coding: utf-8 -*-
"""Inline menus for the Dark World (available in private chat and groups)."""
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.data import dark_world as D
from app.data import dark_world_npcs as N  # extends NPC catalog
from app.utils.ui import with_owner


def hub_menu(owner_id: int, has_active: bool = False, result_ready: bool = False) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    if has_active:
        b.button(text="🎁 نتیجه آماده" if result_ready else "⏳ عملیات فعال", callback_data=with_owner("dw:active", owner_id))
    b.button(text="🎯 مأموریت‌ها و پرونده‌ها", callback_data=with_owner("dw:sec:ops", owner_id))
    b.button(text="👥 نیروها و قراردادها", callback_data=with_owner("dw:sec:crew", owner_id))
    b.button(text="💰 تجارت و اقتصاد", callback_data=with_owner("dw:sec:economy", owner_id))
    b.button(text="⚔️ رقابت و فصل", callback_data=with_owner("dw:sec:competition", owner_id))
    b.button(text="🧪 تولید و توزیع", callback_data=with_owner("dw:sec:production", owner_id))
    b.button(text="📘 راهنمای شروع و قوانین", callback_data=with_owner("dw:sec:guide", owner_id))
    b.button(text="🏠 منوی اصلی", callback_data=with_owner("menu:main", owner_id))
    b.adjust(1,2,2,1,1)
    return b.as_markup()

def _section_footer(b, owner_id):
    b.button(text="◀️ دنیای سیاه", callback_data=with_owner("dw:hub", owner_id))
    b.button(text="🏠 منوی اصلی", callback_data=with_owner("menu:main", owner_id))

def operations_hub_menu(owner_id, has_active=False, result_ready=False):
    b=InlineKeyboardBuilder();b.button(text="🗺️ عملیات سایه",callback_data=with_owner("dw:contracts",owner_id));b.button(text="🎲 پرونده‌های چندشاخه",callback_data=with_owner("dwc:hub",owner_id));b.button(text="🕵️ تعقیب و مخفیگاه",callback_data=with_owner("dwp:hub",owner_id))
    if has_active:b.button(text="🎁 دریافت نتیجه" if result_ready else "⏳ عملیات فعال",callback_data=with_owner("dw:active",owner_id))
    _section_footer(b,owner_id);b.adjust(1,2,1,2);return b.as_markup()
def crew_hub_menu(owner_id):
    b=InlineKeyboardBuilder();b.button(text="👥 استخدام نیرو",callback_data=with_owner("dw:recruits",owner_id));b.button(text="🧩 مدیریت تیم NPC",callback_data=with_owner("dwn:hub",owner_id));b.button(text="🤝 بازار کار کاربران",callback_data=with_owner("dwe:hub",owner_id));_section_footer(b,owner_id);b.adjust(1,2,2);return b.as_markup()
def economy_hub_menu(owner_id):
    b=InlineKeyboardBuilder();b.button(text="🚚 حمل‌ونقل و بازار کاربران",callback_data=with_owner("smg:hub",owner_id));b.button(text="🕶️ پول‌شویی و بازار سیاه",callback_data=with_owner("dwf:hub",owner_id));_section_footer(b,owner_id);b.adjust(1,1,2);return b.as_markup()
def competition_hub_menu(owner_id):
    b=InlineKeyboardBuilder();b.button(text="⚔️ شبیخون و اطلاعات",callback_data=with_owner("dwr:hub",owner_id));b.button(text="🌒 روایت و جناح‌ها",callback_data=with_owner("dws:hub",owner_id));b.button(text="🏆 رقابت پایان فصل",callback_data=with_owner("dwk:hub",owner_id));b.button(text="🎖️ رنک داخلی",callback_data=with_owner("dw:rank",owner_id));_section_footer(b,owner_id);b.adjust(2,2,2);return b.as_markup()
def production_hub_menu(owner_id):
    b=InlineKeyboardBuilder();b.button(text="🧪 مرکز تولید و توزیع",callback_data=with_owner("dwl:hub",owner_id));_section_footer(b,owner_id);b.adjust(1,2);return b.as_markup()
def guide_hub_menu(owner_id):
    b=InlineKeyboardBuilder();b.button(text="🚀 راهنمای کامل؛ از اینجا شروع کن",callback_data=with_owner("dw:guide:0",owner_id));b.button(text="📜 قوانین و لول ۶۰",callback_data=with_owner("dw:rules",owner_id));b.button(text="📖 پرونده روایی",callback_data=with_owner("dw:story",owner_id));_section_footer(b,owner_id);b.adjust(1,2,2);return b.as_markup()
def guide_page_menu(owner_id,page,total):
    b=InlineKeyboardBuilder()
    if total>1:
        b.button(text="◀️ قبلی",callback_data=with_owner(f"dw:guide:{(page-1)%total}",owner_id));b.button(text=f"{page+1}/{total}",callback_data=with_owner("dw:guide:none",owner_id));b.button(text="بعدی ▶️",callback_data=with_owner(f"dw:guide:{(page+1)%total}",owner_id))
    b.button(text="◀️ فهرست راهنما",callback_data=with_owner("dw:sec:guide",owner_id));b.button(text="🏠 منوی اصلی",callback_data=with_owner("menu:main",owner_id));b.adjust(3,2);return b.as_markup()

def contracts_menu(influence: int, owner_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    points = max(0, int(influence or 0))
    for key in D.CONTRACT_ORDER:
        contract = D.CONTRACTS[key]
        required = int(contract["required_influence"])
        if points >= required:
            text = f"{contract['icon']} {contract['name']} · سختی {contract['difficulty']}"
            data = f"dw:contract:{key}"
        else:
            text = f"🔒 {contract['name']} · {required:,} نفوذ"
            data = "dw:locked"
        b.button(text=text, callback_data=with_owner(data, owner_id))
    b.button(text="↩️ بازگشت", callback_data=with_owner("dw:hub", owner_id))
    b.adjust(1)
    return b.as_markup()


def approaches_menu(contract_key: str, owner_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for key in D.APPROACH_ORDER:
        approach = D.APPROACHES[key]
        b.button(
            text=f"{approach['icon']} {approach['name']}",
            callback_data=with_owner(f"dw:preview:{contract_key}:{key}", owner_id),
        )
    b.button(text="↩️ قراردادها", callback_data=with_owner("dw:contracts", owner_id))
    b.adjust(1)
    return b.as_markup()


def preview_menu(contract_key: str, approach_key: str, owner_id: int, can_start: bool) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    if can_start:
        b.button(
            text="▶️ آغاز عملیات و ثبت مخفی نتیجه",
            callback_data=with_owner(f"dw:start:{contract_key}:{approach_key}", owner_id),
        )
    b.button(text="🎭 تغییر روش", callback_data=with_owner(f"dw:contract:{contract_key}", owner_id))
    b.button(text="↩️ قراردادها", callback_data=with_owner("dw:contracts", owner_id))
    b.adjust(1)
    return b.as_markup()


def active_menu(owner_id: int, ready: bool) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    if ready:
        b.button(text="🎁 دریافت نتیجه", callback_data=with_owner("dw:collect", owner_id))
    else:
        b.button(text="🔄 بروزرسانی زمان", callback_data=with_owner("dw:active", owner_id))
    b.button(text="↩️ هاب دنیای سیاه", callback_data=with_owner("dw:hub", owner_id))
    b.adjust(1)
    return b.as_markup()


def recruits_menu(owned_keys, influence: int, owner_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    owned = set(owned_keys or ())
    points = max(0, int(influence or 0))
    for key in D.RECRUIT_ORDER:
        recruit = D.RECRUITS[key]
        required = int(recruit["required_influence"])
        if key in owned:
            text, data = f"✅ {recruit['name']} · استخدام‌شده", "dw:owned"
        elif points < required:
            text, data = f"🔒 {recruit['name']} · {required:,} نفوذ", "dw:locked"
        else:
            text = f"{recruit['icon']} {recruit['name']} · {int(recruit['cost']):,}"
            data = f"dw:hire:{key}"
        b.button(text=text, callback_data=with_owner(data, owner_id))
    b.button(text="🤝 طرح استخدام کاربران", callback_data=with_owner("dw:userhire", owner_id))
    b.button(text="↩️ هاب دنیای سیاه", callback_data=with_owner("dw:hub", owner_id))
    b.adjust(1)
    return b.as_markup()


def back_to_hub(owner_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="↩️ هاب دنیای سیاه", callback_data=with_owner("dw:hub", owner_id))
    b.button(text="🏠 منوی اصلی", callback_data=with_owner("menu:main", owner_id))
    b.adjust(1)
    return b.as_markup()
