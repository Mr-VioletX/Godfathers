# -*- coding: utf-8 -*-
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from app.data import dark_world_smuggling as S
from app.utils.ui import with_owner

def hub(owner,active=False,ready=False):
 b=InlineKeyboardBuilder();b.button(text="📦 خرید مستقیم کالا",callback_data=with_owner("smg:stock",owner));b.button(text="🚚 آماده‌سازی محموله",callback_data=with_owner("smg:goods",owner))
 if active:b.button(text="🎁 دریافت نتیجه" if ready else "⏳ محموله فعال",callback_data=with_owner("smg:active",owner))
 b.button(text="🏚️ ارتقای انبار",callback_data=with_owner("smg:upgrade",owner));b.button(text="🤝 بازار کاربران",callback_data=with_owner("smg:market",owner));b.button(text="◀️ تجارت و اقتصاد",callback_data=with_owner("dw:sec:economy",owner));b.adjust(2,1,2,1);return b.as_markup()
def stock(owner,mode="buy"):
 b=InlineKeyboardBuilder()
 for k in S.GOOD_ORDER:b.button(text=f"{S.GOODS[k]['icon']} {S.GOODS[k]['name']} ×1",callback_data=with_owner(f"smg:buy:{k}:1",owner))
 b.button(text="◀️ حمل‌ونقل",callback_data=with_owner("smg:hub",owner));b.adjust(2,2,2,1);return b.as_markup()
def goods(inv,owner):
 b=InlineKeyboardBuilder()
 for k in S.GOOD_ORDER:
  q=int(inv.get(k,0));b.button(text=f"{S.GOODS[k]['icon']} {S.GOODS[k]['name']} ×{q}",callback_data=with_owner(f"smg:qty:{k}",owner) if q else with_owner("smg:none",owner))
 b.button(text="◀️ حمل‌ونقل",callback_data=with_owner("smg:hub",owner));b.adjust(1);return b.as_markup()
def qty(g,available,owner):
 b=InlineKeyboardBuilder()
 for q in (1,5,10,20):
  if q<=available:b.button(text=f"{q} واحد",callback_data=with_owner(f"smg:pack:{g}:{q}",owner))
 b.button(text="◀️ انتخاب کالا",callback_data=with_owner("smg:goods",owner));b.adjust(2,2,1);return b.as_markup()
def packs(g,q,owner):
 b=InlineKeyboardBuilder()
 for k in S.PACK_ORDER:b.button(text=f"{S.PACKS[k]['icon']} {S.PACKS[k]['name']}",callback_data=with_owner(f"smg:route:{g}:{q}:{k}",owner))
 b.button(text="◀️ انتخاب مقدار",callback_data=with_owner(f"smg:qty:{g}",owner));b.adjust(1);return b.as_markup()
def routes(g,q,p,owner):
 b=InlineKeyboardBuilder()
 for k in S.ROUTE_ORDER:b.button(text=f"{S.ROUTES[k]['icon']} {S.ROUTES[k]['name']}",callback_data=with_owner(f"smg:dest:{g}:{q}:{p}:{k}",owner))
 b.button(text="◀️ انتخاب بسته‌بندی",callback_data=with_owner(f"smg:pack:{g}:{q}",owner));b.adjust(1);return b.as_markup()
def dests(g,q,p,r,owner):
 b=InlineKeyboardBuilder()
 for k in S.DEST_ORDER:b.button(text=f"{S.DESTINATIONS[k]['icon']} {S.DESTINATIONS[k]['name']}",callback_data=with_owner(f"smg:prev:{g}:{q}:{p}:{r}:{k}",owner))
 b.button(text="◀️ انتخاب مسیر",callback_data=with_owner(f"smg:route:{g}:{q}:{p}",owner));b.adjust(1);return b.as_markup()
def start(plan,owner):
 b=InlineKeyboardBuilder();x=plan;b.button(text="▶️ ارسال و ثبت نتیجه",callback_data=with_owner(f"smg:start:{x['good_key']}:{x['qty']}:{x['pack_key']}:{x['route_key']}:{x['dest_key']}",owner));b.button(text="◀️ تغییر محموله",callback_data=with_owner("smg:goods",owner));b.adjust(1);return b.as_markup()
def market(owner):
 b=InlineKeyboardBuilder();b.button(text="🛒 خرید از کاربران",callback_data=with_owner("smg:offers",owner));b.button(text="➕ ثبت عرضه",callback_data=with_owner("smg:sellgoods",owner));b.button(text="📊 عرضه و تقاضا",callback_data=with_owner("smg:pulse",owner));b.button(text="◀️ حمل‌ونقل",callback_data=with_owner("smg:hub",owner));b.adjust(2,1,1);return b.as_markup()
def offers(rows,owner):
 b=InlineKeyboardBuilder()
 for o in rows:b.button(text=f"#{o.id} · {S.GOODS[o.good_key]['name']} · {o.price_per_unit:,}",callback_data=with_owner(f"smg:take:{o.id}:1",owner))
 b.button(text="◀️ بازار کاربران",callback_data=with_owner("smg:market",owner));b.adjust(1);return b.as_markup()
def sellgoods(inv,owner):
 b=InlineKeyboardBuilder()
 for k in S.GOOD_ORDER:
  if inv.get(k,0):
   b.button(text=f"{S.GOODS[k]['icon']} عرضه ۱ از {inv[k]}",callback_data=with_owner(f"smg:list:{k}:1:fair",owner))
   if inv.get(k,0)>=5:b.button(text=f"عرضه ۵ از {S.GOODS[k]['name']}",callback_data=with_owner(f"smg:list:{k}:5:fair",owner))
 b.button(text="◀️ بازار کاربران",callback_data=with_owner("smg:market",owner));b.adjust(1);return b.as_markup()
