# -*- coding: utf-8 -*-
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from app.data import dark_world_npcs as N
from app.utils.ui import with_owner

def npc_hub_menu(owner_id:int)->InlineKeyboardMarkup:
 b=InlineKeyboardBuilder();b.button(text="🧩 چیدن تیم",callback_data=with_owner("dwn:team",owner_id));b.button(text="🎭 انتخاب تاکتیک",callback_data=with_owner("dwn:tactics",owner_id));b.button(text="💵 پرداخت حقوق",callback_data=with_owner("dwn:wages",owner_id));b.button(text="🛌 استراحت تیم",callback_data=with_owner("dwn:rest",owner_id));b.button(text="👥 استخدام نیروی تازه",callback_data=with_owner("dw:recruits",owner_id));b.button(text="↩️ دنیای سیاه",callback_data=with_owner("dw:sec:crew",owner_id));b.adjust(2,2,1,1);return b.as_markup()
def team_menu(rows,selected,owner_id):
 b=InlineKeyboardBuilder()
 for row in rows:
  key=row["key"];mark="✅" if key in selected else "▫️";locked=not row["available"]
  b.button(text=f"{'🔒' if locked else mark} {row['name']} · L{row['level']}",callback_data=with_owner("dwn:blocked" if locked else f"dwn:toggle:{key}",owner_id))
  b.button(text=f"🎓 تمرین {row['name']}",callback_data=with_owner(f"dwn:train:{key}",owner_id))
  if row["deserted"]:b.button(text=f"🤝 بازگرداندن {row['name']}",callback_data=with_owner(f"dwn:return:{key}",owner_id))
 b.button(text="↩️ مدیریت NPC",callback_data=with_owner("dwn:hub",owner_id));b.adjust(1);return b.as_markup()
def tactics_menu(current,owner_id):
 b=InlineKeyboardBuilder()
 for key in N.TACTIC_ORDER:
  t=N.TACTICS[key];b.button(text=f"{'✅' if key==current else t['icon']} {t['name']}",callback_data=with_owner(f"dwn:tactic:{key}",owner_id))
 b.button(text="↩️ مدیریت NPC",callback_data=with_owner("dwn:hub",owner_id));b.adjust(1);return b.as_markup()
def back(owner_id):
 b=InlineKeyboardBuilder();b.button(text="↩️ مدیریت NPC",callback_data=with_owner("dwn:hub",owner_id));return b.as_markup()
