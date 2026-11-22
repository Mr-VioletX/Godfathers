# -*- coding: utf-8 -*-
from aiogram.utils.keyboard import InlineKeyboardBuilder
from app.data import dark_world_recipes as R
from app.data import dark_world_laboratory as L
from app.utils.ui import with_owner
PAGE=6
def hub(owner,active=False,ready=False):
 b=InlineKeyboardBuilder();b.button(text="🌱 گلخانه",callback_data=with_owner("dwx:garden",owner));b.button(text="🕶️ بازار مواد اولیه",callback_data=with_owner("dwx:market",owner));b.button(text="🧩 کشف فرمول",callback_data=with_owner("dwx:bases",owner));b.button(text="📓 فرمول‌های من",callback_data=with_owner("dwx:recipes:0",owner));b.button(text="🎒 محصولات ترکیبی",callback_data=with_owner("dwx:inventory",owner))
 if active:b.button(text="🎁 دریافت تولید" if ready else "⏳ تولید فعال",callback_data=with_owner("dwx:active",owner))
 b.button(text="◀️ مرکز تولید",callback_data=with_owner("dwl:hub",owner));b.adjust(2,2,1,1,1);return b.as_markup()
def garden(rows,owner):
 b=InlineKeyboardBuilder()
 for k,x in R.BASES.items():b.button(text=f"{x['icon']} کاشت {x['name']}",callback_data=with_owner(f"dwx:plant:{k}",owner))
 for x in rows:
  if x.status=='growing':b.button(text=f"🌾 برداشت قطعه #{x.slot_no}",callback_data=with_owner(f"dwx:harvest:{x.id}",owner))
 b.button(text="◀️ فرمول‌سازی",callback_data=with_owner("dwx:hub",owner));b.adjust(1);return b.as_markup()
def market(owner):
 b=InlineKeyboardBuilder();b.button(text="🌱 پایه‌ها",callback_data=with_owner("dwx:market:bases",owner));b.button(text="⚗️ عامل‌ها",callback_data=with_owner("dwx:market:catalysts",owner));b.button(text="✨ امضاها",callback_data=with_owner("dwx:market:signatures",owner));b.button(text="◀️ فرمول‌سازی",callback_data=with_owner("dwx:hub",owner));b.adjust(1);return b.as_markup()
def market_group(group,owner):
 seq={'bases':R.BASE_ORDER,'catalysts':R.CATALYST_ORDER,'signatures':R.SIGNATURE_ORDER}[group];b=InlineKeyboardBuilder()
 for k in seq:
  x=R.ingredient(k);b.button(text=f"{x['icon']} {x['name']} ×۵",callback_data=with_owner(f"dwx:buy:{k}:{group}",owner))
 b.button(text="◀️ دسته‌های بازار",callback_data=with_owner("dwx:market",owner));b.adjust(1);return b.as_markup()
def bases(owner):
 b=InlineKeyboardBuilder()
 for k,x in R.BASES.items():b.button(text=f"{x['icon']} {x['name']}",callback_data=with_owner(f"dwx:cats:{k}",owner))
 b.button(text="◀️ فرمول‌سازی",callback_data=with_owner("dwx:hub",owner));b.adjust(1);return b.as_markup()
def catalysts(base,owner):
 b=InlineKeyboardBuilder()
 for k,x in R.CATALYSTS.items():b.button(text=f"{x['icon']} {x['name']}",callback_data=with_owner(f"dwx:sigs:{base}:{k}",owner))
 b.button(text="◀️ انتخاب پایه",callback_data=with_owner("dwx:bases",owner));b.adjust(1);return b.as_markup()
def signatures(base,cat,owner):
 b=InlineKeyboardBuilder()
 for k,x in R.SIGNATURES.items():b.button(text=f"{x['icon']} {x['name']}",callback_data=with_owner(f"dwx:brands:{base}:{cat}:{k}",owner))
 b.button(text="◀️ انتخاب عامل",callback_data=with_owner(f"dwx:cats:{base}",owner));b.adjust(1);return b.as_markup()
def brands(base,cat,sig,owner):
 b=InlineKeyboardBuilder()
 for k,x in R.BRANDS.items():b.button(text=x['name'],callback_data=with_owner(f"dwx:discover:{base}:{cat}:{sig}:{k}",owner))
 b.button(text="◀️ انتخاب امضا",callback_data=with_owner(f"dwx:sigs:{base}:{cat}",owner));b.adjust(1);return b.as_markup()
def recipes(rows,owner,page=0):
 pages=max(1,(len(rows)+PAGE-1)//PAGE);page=max(0,min(int(page),pages-1));b=InlineKeyboardBuilder()
 for x in rows[page*PAGE:(page+1)*PAGE]:b.button(text=f"🧬 #{x.id} {x.custom_name}",callback_data=with_owner(f"dwx:modes:{x.id}",owner))
 if pages>1:b.button(text="◀️ قبلی",callback_data=with_owner(f"dwx:recipes:{(page-1)%pages}",owner));b.button(text=f"{page+1}/{pages}",callback_data=with_owner("dwx:none",owner));b.button(text="بعدی ▶️",callback_data=with_owner(f"dwx:recipes:{(page+1)%pages}",owner))
 b.button(text="◀️ فرمول‌سازی",callback_data=with_owner("dwx:hub",owner));b.adjust(1);return b.as_markup()
def modes(recipe_id,owner):
 b=InlineKeyboardBuilder()
 for k,x in L.MODES.items():b.button(text=f"{x['icon']} {x['name']}",callback_data=with_owner(f"dwx:start:{recipe_id}:{k}",owner))
 b.button(text="◀️ فرمول‌های من",callback_data=with_owner("dwx:recipes:0",owner));b.adjust(1);return b.as_markup()
def inventory(rows,owner):
 b=InlineKeyboardBuilder()
 for x in rows:b.button(text=f"💰 فروش ۱ فرمول #{x.recipe_id}",callback_data=with_owner(f"dwx:sell:{x.recipe_id}",owner))
 b.button(text="◀️ فرمول‌سازی",callback_data=with_owner("dwx:hub",owner));b.adjust(1);return b.as_markup()
