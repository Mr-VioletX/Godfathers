# -*- coding: utf-8 -*-
from aiogram.utils.keyboard import InlineKeyboardBuilder
from app.data import dark_world_laboratory as L
from app.utils.ui import with_owner
PAGE=6
def hub(owner,active=False,ready=False):
 b=InlineKeyboardBuilder();b.button(text="⚗️ تولید استاندارد",callback_data=with_owner("dwl:core",owner));b.button(text="🧬 فرمول‌سازی و گلخانه",callback_data=with_owner("dwx:hub",owner));b.button(text="🚚 مشتریان و توزیع",callback_data=with_owner("dwd:hub",owner));b.button(text="🏰 امپراتوری تولید",callback_data=with_owner("dwi:hub",owner))
 if active:b.button(text="🎁 دریافت بچ" if ready else "⏳ بچ فعال",callback_data=with_owner("dwl:active",owner))
 b.button(text="◀️ تولید و توزیع",callback_data=with_owner("dw:sec:production",owner));b.button(text="🏠 منوی اصلی",callback_data=with_owner("menu:main",owner));b.adjust(2,2,1,2);return b.as_markup()
def core(owner):
 b=InlineKeyboardBuilder();b.button(text="📚 کاتالوگ",callback_data=with_owner("dwl:catalog",owner));b.button(text="🧪 شروع چرخه",callback_data=with_owner("dwl:products:0",owner));b.button(text="🧱 مواد A/B/C/D",callback_data=with_owner("dwl:materials",owner));b.button(text="🔧 ارتقا و تعمیر",callback_data=with_owner("dwl:upgrades",owner));b.button(text="🎒 انبار و فروش",callback_data=with_owner("dwl:inventory",owner));b.button(text="◀️ مرکز تولید",callback_data=with_owner("dwl:hub",owner));b.adjust(2,2,1,1);return b.as_markup()
def products(level,owner,page=0):
 keys=list(L.PRODUCT_ORDER);pages=max(1,(len(keys)+PAGE-1)//PAGE);page=max(0,min(int(page),pages-1));b=InlineKeyboardBuilder()
 for k in keys[page*PAGE:(page+1)*PAGE]:
  x=L.PRODUCTS[k];b.button(text=f"{x['icon']} {x['name']} · L{x['level']}",callback_data=with_owner(f"dwl:modes:{k}",owner) if x['level']<=level else with_owner("dwl:locked",owner))
 if pages>1:b.button(text="◀️ قبلی",callback_data=with_owner(f"dwl:products:{(page-1)%pages}",owner));b.button(text=f"{page+1}/{pages}",callback_data=with_owner("dwl:none",owner));b.button(text="بعدی ▶️",callback_data=with_owner(f"dwl:products:{(page+1)%pages}",owner))
 b.button(text="◀️ تولید استاندارد",callback_data=with_owner("dwl:core",owner));b.adjust(1,1,1,1);return b.as_markup()
def modes(product,owner):
 b=InlineKeyboardBuilder()
 for k in L.MODE_ORDER:b.button(text=f"{L.MODES[k]['icon']} {L.MODES[k]['name']}",callback_data=with_owner(f"dwl:prev:{product}:1:{k}",owner))
 b.button(text="◀️ محصولات",callback_data=with_owner("dwl:products:0",owner));b.adjust(1);return b.as_markup()
def start(plan,owner):
 b=InlineKeyboardBuilder();b.button(text="▶️ شروع و ثبت نتیجه",callback_data=with_owner(f"dwl:start:{plan['product_key']}:{plan['qty']}:{plan['mode_key']}",owner));b.button(text="◀️ تغییر چرخه",callback_data=with_owner(f"dwl:modes:{plan['product_key']}",owner));b.adjust(1);return b.as_markup()
def materials(owner):
 b=InlineKeyboardBuilder()
 for k,x in L.MATERIALS.items():b.button(text=f"{x['icon']} خرید ۱۰ {x['name']}",callback_data=with_owner(f"dwl:mat:{k}",owner))
 b.button(text="◀️ تولید استاندارد",callback_data=with_owner("dwl:core",owner));b.adjust(2,2,1);return b.as_markup()
def upgrades(owner):
 b=InlineKeyboardBuilder()
 for k,x in L.UPGRADES.items():b.button(text=f"{x['icon']} {x['name']}",callback_data=with_owner(f"dwl:up:{k}",owner))
 b.button(text="🛠️ تعمیر کامل",callback_data=with_owner("dwl:repair",owner));b.button(text="◀️ تولید استاندارد",callback_data=with_owner("dwl:core",owner));b.adjust(2,2,1,1);return b.as_markup()
def inventory(rows,owner):
 b=InlineKeyboardBuilder()
 for x in rows:b.button(text=f"💰 فروش ۱ {L.PRODUCTS[x.product_key]['name']}",callback_data=with_owner(f"dwl:sell:{x.product_key}",owner))
 b.button(text="◀️ تولید استاندارد",callback_data=with_owner("dwl:core",owner));b.adjust(1);return b.as_markup()
