# -*- coding: utf-8 -*-
from aiogram.utils.keyboard import InlineKeyboardBuilder
from app.data import dark_world_empire as E
from app.utils.ui import with_owner
def hub(owner,inspection=False,ready=False):
 b=InlineKeyboardBuilder();b.button(text="🏗️ ساخت مرکز",callback_data=with_owner("dwi:build",owner));b.button(text="🏭 مراکز من",callback_data=with_owner("dwi:facilities",owner));b.button(text="⚔️ رقبا",callback_data=with_owner("dwi:rivals",owner));b.button(text="📊 توان امپراتوری",callback_data=with_owner("dwi:stats",owner))
 if inspection:b.button(text="🚨 نتیجه بازرسی" if ready else "⏳ بازرسی فعال",callback_data=with_owner("dwi:inspection",owner))
 b.button(text="↩️ آزمایشگاه",callback_data=with_owner("dwl:hub",owner));b.adjust(2,2,1,1);return b.as_markup()
def builds(owner):
 b=InlineKeyboardBuilder()
 for k,x in E.FACILITIES.items():b.button(text=f"{x['icon']} {x['name']} · {x['cost']:,}",callback_data=with_owner(f"dwi:buy:{k}",owner))
 b.button(text="◀️ امپراتوری",callback_data=with_owner("dwi:hub",owner));b.adjust(1);return b.as_markup()
def facilities(rows,owner):
 b=InlineKeyboardBuilder()
 for x in rows:b.button(text=f"{E.FACILITIES[x.facility_key]['icon']} {E.FACILITIES[x.facility_key]['name']} #{x.id}",callback_data=with_owner(f"dwi:facility:{x.id}",owner))
 b.button(text="◀️ امپراتوری",callback_data=with_owner("dwi:hub",owner));b.adjust(1);return b.as_markup()
def facility(row,owner):
 b=InlineKeyboardBuilder()
 for k,x in E.UPGRADES.items():b.button(text=f"{x['icon']} {x['name']}",callback_data=with_owner(f"dwi:upgrade:{row.id}:{k}",owner))
 b.button(text="◀️ مراکز",callback_data=with_owner("dwi:facilities",owner));b.adjust(2,2,1);return b.as_markup()
def rivals(owner):
 b=InlineKeyboardBuilder()
 for k,x in E.RIVALS.items():b.button(text=f"{x['icon']} {x['name']}",callback_data=with_owner(f"dwi:responses:{k}",owner))
 b.button(text="◀️ امپراتوری",callback_data=with_owner("dwi:hub",owner));b.adjust(1);return b.as_markup()
def responses(rival,owner):
 b=InlineKeyboardBuilder()
 for k,x in E.RESPONSES.items():b.button(text=f"{x['icon']} {x['name']}",callback_data=with_owner(f"dwi:rival:{rival}:{k}",owner))
 b.button(text="◀️ رقبا",callback_data=with_owner("dwi:rivals",owner));b.adjust(1);return b.as_markup()
def inspections(owner):
 b=InlineKeyboardBuilder()
 for k,x in E.INSPECTION_CHOICES.items():b.button(text=f"{x['icon']} {x['name']}",callback_data=with_owner(f"dwi:prepare:{k}",owner))
 b.button(text="◀️ امپراتوری",callback_data=with_owner("dwi:hub",owner));b.adjust(1);return b.as_markup()
