# -*- coding: utf-8 -*-
from aiogram.utils.keyboard import InlineKeyboardBuilder
from app.data import dark_world_raids as R
from app.utils.ui import with_owner
def hub(owner):
 b=InlineKeyboardBuilder();b.button(text="🎯 شناسایی هدف",callback_data=with_owner("dwr:targets",owner));b.button(text="🛡️ آرایش دفاعی",callback_data=with_owner("dwr:defenses",owner));b.button(text="🤝 لابی شبیخون",callback_data=with_owner("dwr:lobby",owner));b.button(text="📜 نبردهای من",callback_data=with_owner("dwr:mine",owner));b.button(text="↩️ دنیای سیاه",callback_data=with_owner("dw:sec:competition",owner));b.adjust(2,2,1);return b.as_markup()
def targets(rows,owner):
 b=InlineKeyboardBuilder()
 for p in rows:b.button(text=f"🎯 {p.name or p.tg_user_id} · Lv.{p.level}",callback_data=with_owner(f"dwr:scout:{p.tg_user_id}",owner))
 b.button(text="↩️ شبیخون",callback_data=with_owner("dwr:hub",owner));b.adjust(1);return b.as_markup()
def approaches(target,owner):
 b=InlineKeyboardBuilder()
 for k in R.APPROACH_ORDER:b.button(text=f"{R.APPROACHES[k]['icon']} {R.APPROACHES[k]['name']}",callback_data=with_owner(f"dwr:create:{target}:{k}",owner))
 b.button(text="↩️ اهداف",callback_data=with_owner("dwr:targets",owner));b.adjust(1);return b.as_markup()
def defenses(owner):
 b=InlineKeyboardBuilder()
 for k in R.DEFENSE_ORDER:b.button(text=f"{R.DEFENSES[k]['icon']} {R.DEFENSES[k]['name']}",callback_data=with_owner(f"dwr:def:{k}",owner))
 b.button(text="↩️ شبیخون",callback_data=with_owner("dwr:hub",owner));b.adjust(1);return b.as_markup()
def lobby(rows,owner):
 b=InlineKeyboardBuilder()
 for x in rows:b.button(text=f"#{x.id} · {x.attacker_name} ← {x.defender_name}",callback_data=with_owner(f"dwr:view:{x.id}",owner))
 b.button(text="↩️ شبیخون",callback_data=with_owner("dwr:hub",owner));b.adjust(1);return b.as_markup()
def raid(raid,owner,can_join=True,can_resolve=False):
 b=InlineKeyboardBuilder()
 if can_join:b.button(text="⚔️ کمک به حمله",callback_data=with_owner(f"dwr:join:{raid.id}:attack",owner));b.button(text="🛡️ کمک به دفاع",callback_data=with_owner(f"dwr:join:{raid.id}:defense",owner))
 if can_resolve:b.button(text="🎲 قفل و حل نبرد",callback_data=with_owner(f"dwr:resolve:{raid.id}",owner))
 b.button(text="↩️ لابی",callback_data=with_owner("dwr:lobby",owner));b.adjust(2,1,1);return b.as_markup()
