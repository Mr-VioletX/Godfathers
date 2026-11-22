# -*- coding: utf-8 -*-
from aiogram.utils.keyboard import InlineKeyboardBuilder
from app.data import dark_world_distribution as D
from app.utils.ui import with_owner
PAGE=6
def hub(owner,active=False,ready=False):
 b=InlineKeyboardBuilder();b.button(text="🛍️ انتخاب محصول",callback_data=with_owner("dwd:products:0",owner));b.button(text="🗺️ قلمروها",callback_data=with_owner("dwd:territory",owner));b.button(text="👥 مشتریان",callback_data=with_owner("dwd:contacts",owner))
 if active:b.button(text="🎁 نتیجه معامله" if ready else "⏳ معامله فعال",callback_data=with_owner("dwd:active",owner))
 b.button(text="◀️ مرکز تولید",callback_data=with_owner("dwl:hub",owner));b.adjust(2,1,1,1);return b.as_markup()
def products(rows,names,owner,page=0):
 pages=max(1,(len(rows)+PAGE-1)//PAGE);page=max(0,min(int(page),pages-1));b=InlineKeyboardBuilder()
 for x in rows[page*PAGE:(page+1)*PAGE]:b.button(text=f"🧬 {names.get(x.recipe_id,'فرمول')} ×{x.qty}",callback_data=with_owner(f"dwd:districts:{x.recipe_id}",owner))
 if pages>1:b.button(text="◀️ قبلی",callback_data=with_owner(f"dwd:products:{(page-1)%pages}",owner));b.button(text=f"{page+1}/{pages}",callback_data=with_owner("dwd:none",owner));b.button(text="بعدی ▶️",callback_data=with_owner(f"dwd:products:{(page+1)%pages}",owner))
 b.button(text="◀️ شبکه توزیع",callback_data=with_owner("dwd:hub",owner));b.adjust(1);return b.as_markup()
def districts(recipe_id,owner):
 b=InlineKeyboardBuilder()
 for k,x in D.DISTRICTS.items():b.button(text=f"{x['icon']} {x['name']}",callback_data=with_owner(f"dwd:channels:{recipe_id}:{k}",owner))
 b.button(text="◀️ محصولات",callback_data=with_owner("dwd:products:0",owner));b.adjust(1);return b.as_markup()
def channels(recipe_id,district,owner):
 b=InlineKeyboardBuilder()
 for k,x in D.CHANNELS.items():b.button(text=f"{x['icon']} {x['name']} ×{x['qty']}",callback_data=with_owner(f"dwd:screens:{recipe_id}:{district}:{k}",owner))
 b.button(text="◀️ انتخاب محله",callback_data=with_owner(f"dwd:districts:{recipe_id}",owner));b.adjust(1);return b.as_markup()
def screens(recipe_id,district,channel,owner):
 b=InlineKeyboardBuilder()
 for k,x in D.SCREENS.items():b.button(text=f"{x['icon']} {x['name']}",callback_data=with_owner(f"dwd:start:{recipe_id}:{district}:{channel}:{k}",owner))
 b.button(text="◀️ انتخاب کانال",callback_data=with_owner(f"dwd:channels:{recipe_id}:{district}",owner));b.adjust(1);return b.as_markup()
