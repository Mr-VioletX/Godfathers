# -*- coding: utf-8 -*-
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from app.data import dark_world_finance as F
from app.utils.ui import with_owner
def hub(owner,active=False,ready=False):
 b=InlineKeyboardBuilder();b.button(text="🧼 پول‌شویی",callback_data=with_owner("dwf:amounts",owner));
 if active:b.button(text="🎁 دریافت نتیجه" if ready else "⏳ عملیات مالی فعال",callback_data=with_owner("dwf:active",owner))
 b.button(text="🕶️ کالاهای کمیاب",callback_data=with_owner("dwf:rare",owner));b.button(text="📜 دفتر ردگیری",callback_data=with_owner("dwf:log",owner));b.button(text="↩️ دنیای سیاه",callback_data=with_owner("dw:sec:economy",owner));b.adjust(2,2,1);return b.as_markup()
def amounts(balance,owner):
 b=InlineKeyboardBuilder()
 for pct in (10,25,50,100):
  amount=max(0,int(balance)*pct//100)
  if amount>=F.LAUNDER_MIN:b.button(text=f"{pct}٪ · {amount:,}",callback_data=with_owner(f"dwf:methods:{pct}",owner))
 b.button(text="↩️ بازار سیاه",callback_data=with_owner("dwf:hub",owner));b.adjust(2,2,1);return b.as_markup()
def methods(pct,owner):
 b=InlineKeyboardBuilder()
 for k in F.METHOD_ORDER:b.button(text=f"{F.METHODS[k]['icon']} {F.METHODS[k]['name']}",callback_data=with_owner(f"dwf:prev:{pct}:{k}",owner))
 b.button(text="↩️ مبلغ",callback_data=with_owner("dwf:amounts",owner));b.adjust(1);return b.as_markup()
def start(pct,m,owner):
 b=InlineKeyboardBuilder();b.button(text="▶️ شروع و ثبت مخفی نتیجه",callback_data=with_owner(f"dwf:start:{pct}:{m}",owner));b.button(text="↩️ تغییر روش",callback_data=with_owner(f"dwf:methods:{pct}",owner));b.adjust(1);return b.as_markup()
def rare(keys,owner):
 b=InlineKeyboardBuilder()
 for k in keys:b.button(text=f"{F.RARE[k]['icon']} {F.RARE[k]['name']}",callback_data=with_owner(f"dwf:buy:{k}",owner))
 b.button(text="↩️ بازار سیاه",callback_data=with_owner("dwf:hub",owner));b.adjust(1);return b.as_markup()
