# -*- coding: utf-8 -*-
from aiogram.utils.keyboard import InlineKeyboardBuilder
from app.data import dark_world_seasons as S
from app.utils.ui import with_owner
def hub(owner,member=False,completed=False,claimable=False):
 b=InlineKeyboardBuilder()
 if not member:b.button(text="🏴 انتخاب جناح",callback_data=with_owner("dws:factions",owner))
 if member and not completed:b.button(text="🗳️ تصمیم جمعی",callback_data=with_owner("dws:choices",owner));b.button(text="📦 کمک به جناح",callback_data=with_owner("dws:contrib",owner))
 b.button(text="🏆 جدول جناح‌ها",callback_data=with_owner("dws:board",owner))
 if claimable:b.button(text="🎁 دریافت پاداش فصل",callback_data=with_owner("dws:claim",owner))
 b.button(text="↩️ دنیای سیاه",callback_data=with_owner("dw:sec:competition",owner));b.adjust(2,2,1);return b.as_markup()
def factions(owner):
 b=InlineKeyboardBuilder()
 for k in S.FACTION_ORDER:b.button(text=f"{S.FACTIONS[k]['icon']} {S.FACTIONS[k]['name']}",callback_data=with_owner(f"dws:join:{k}",owner))
 b.button(text="↩️ فصل",callback_data=with_owner("dws:hub",owner));b.adjust(1);return b.as_markup()
def choices(chapter,owner):
 b=InlineKeyboardBuilder()
 for k,v in chapter['choices'].items():b.button(text=f"🗳️ {v['name']}",callback_data=with_owner(f"dws:vote:{k}",owner))
 b.button(text="↩️ فصل",callback_data=with_owner("dws:hub",owner));b.adjust(1);return b.as_markup()
def contribute(owner):
 b=InlineKeyboardBuilder();b.button(text="🧠 کمک ۱۰ Intel",callback_data=with_owner("dws:give:intel",owner));b.button(text="🌑 کمک ۵۰M پول کثیف",callback_data=with_owner("dws:give:dirty",owner));b.button(text="↩️ فصل",callback_data=with_owner("dws:hub",owner));b.adjust(1);return b.as_markup()
