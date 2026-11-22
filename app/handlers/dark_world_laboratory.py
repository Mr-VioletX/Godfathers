# -*- coding: utf-8 -*-
from aiogram import F,Router
from app.database.engine import async_session
from app.data import dark_world_laboratory as L
from app.keyboards.dark_world_laboratory_menu import hub,core,products,modes,start,materials,upgrades,inventory
from app.services import dark_world_laboratory_service as LS
from app.services.operation_guard import BusyOperation,DuplicateOperation,economic_operation
from app.utils.ui import ensure_owner,safe_answer,safe_show,split_owner
router=Router(name="dark_world_laboratory")
def base(c):return split_owner(c.data or "")[0]
async def show(c):
 async with async_session() as s:ok,msg,x=await LS.snapshot(s,c.from_user.id)
 if not ok:return await safe_answer(c,msg,show_alert=True)
 lab=x['lab'];a=x['active'];remain=max(0,int((a.ready_at-LS.now()).total_seconds())) if a else 0;m=' · '.join(f"{L.MATERIALS[k]['icon']}{v}" for k,v in x['materials'].items() if v) or 'خالی'
 text=f"🧪 <b>آزمایشگاه محصولات داستانی</b>\n<i>تمام محصولات، اجزا و فرایندها کاملاً خیالی و انتزاعی‌اند.</i>\n\nسطح: {lab.level}/10 · وضعیت: {lab.condition}/100\n🧰 تجهیزات {lab.equipment} · ⚡ برق {lab.power}\n🌀 تهویه {lab.ventilation} · 🧯 ایمنی {lab.safety}\n🔷 مواد: {m}\n📦 محصول‌های انبار: {sum(int(p.qty) for p in x['products'])}\n⏳ بچ: {('آماده دریافت' if remain<=0 else str(remain//60+1)+' دقیقه مانده') if a else 'نداری'}"
 await safe_show(c.message,text,hub(c.from_user.id,bool(a),bool(a and remain<=0)));await safe_answer(c)
@router.callback_query(F.data.startswith("dwl:hub"))
async def h(c):
 if await ensure_owner(c):await show(c)
@router.callback_query(F.data.startswith("dwl:core"))
async def core_menu(c):
 if await ensure_owner(c):await safe_show(c.message,"⚗️ <b>تولید استاندارد</b>\nکاتالوگ، چرخه تولید، مواد، ارتقا و انبار.",core(c.from_user.id));await safe_answer(c)
@router.callback_query(F.data.startswith("dwl:catalog"))
async def catalog(c):
 if not await ensure_owner(c):return
 lines=["📚 <b>کاتالوگ محصولات کاملاً داستانی</b>","","هیچ نام، ماده یا دستور واقعی در این سیستم وجود ندارد.",""]+[f"{p['icon']} <b>{p['name']}</b> · {p['family']} · L{p['level']} · قدرت {p['power']} · پایداری {p['stability']} · خطر {p['risk']}" for p in L.PRODUCTS.values()];await safe_show(c.message,"\n".join(lines),hub(c.from_user.id));await safe_answer(c)
@router.callback_query(F.data.startswith("dwl:products"))
async def ps(c):
 if not await ensure_owner(c):return
 async with async_session() as s:x=await LS.lab(s,c.from_user.id)
 page=int(base(c).split(":")[2]) if len(base(c).split(":"))>2 else 0
 await safe_show(c.message,"🧪 محصول را انتخاب کن. سطح‌های بالاتر تنوع، ارزش و ریسک بیشتری دارند.",products(x.level,c.from_user.id,page));await safe_answer(c)
@router.callback_query(F.data.startswith("dwl:modes:"))
async def md(c):
 if not await ensure_owner(c):return
 k=base(c).split(":")[2];await safe_show(c.message,"چرخه ایمن آهسته‌تر است؛ چرخه دقیق کیفیت بالاتر دارد؛ چرخه فشرده سریع‌تر و پرخطرتر است.",modes(k,c.from_user.id));await safe_answer(c)
@router.callback_query(F.data.startswith("dwl:prev:"))
async def prev(c):
 if not await ensure_owner(c):return
 _,_,p,q,m=base(c).split(":")
 async with async_session() as s:ok,msg,x=await LS.preview(s,c.from_user.id,p,int(q),m)
 if not x:return await safe_answer(c,msg,show_alert=True)
 mats=' · '.join(f"{L.MATERIALS[k]['name']}×{v}" for k,v in x['materials'].items());text=f"🧾 <b>{L.PRODUCTS[p]['name']}</b>\n\nحالت: {L.MODES[m]['name']}\nمواد انتزاعی: {mats}\nشانس: {x['chance']:.2f}٪\nخروجی: {x['yield_qty']}\nکیفیت پایه: {x['quality']}\nقدرت پایه: {x['potency']}\nپایداری پایه: {x['stability']}\nزمان: {x['duration']//60+1} دقیقه\nفرسودگی: {x['condition_loss']}"
 await safe_show(c.message,text,start(x,c.from_user.id) if ok else modes(p,c.from_user.id));await safe_answer(c,msg if not ok else "")
@router.callback_query(F.data.startswith("dwl:start:"))
async def go(c):
 if not await ensure_owner(c):return
 _,_,p,q,m=base(c).split(":")
 try:
  async with economic_operation(c.from_user.id,f"dwl-start:{c.id}"):
   async with async_session() as s:ok,msg=await LS.start(s,c.from_user.id,p,int(q),m)
 except (BusyOperation,DuplicateOperation):return await safe_answer(c,"شروع تکراری مسدود شد.",show_alert=True)
 await safe_answer(c,msg[:180],show_alert=not ok)
 if ok:await show(c)
@router.callback_query(F.data.startswith("dwl:active"))
async def collect(c):
 if not await ensure_owner(c):return
 try:
  async with economic_operation(c.from_user.id,f"dwl-collect:{c.id}"):
   async with async_session() as s:ok,msg=await LS.collect(s,c.from_user.id)
 except (BusyOperation,DuplicateOperation):return await safe_answer(c,"دریافت تکراری مسدود شد.",show_alert=True)
 await safe_answer(c,msg[:180],show_alert=not ok)
 if ok:await safe_show(c.message,msg,hub(c.from_user.id));await safe_answer(c)
 else:await show(c)
@router.callback_query(F.data.startswith("dwl:materials"))
async def mats(c):
 if await ensure_owner(c):await safe_show(c.message,"🧱 <b>اجزای خیالی A/B/C/D</b>\nاین‌ها فقط توکن‌های بازی‌اند و هیچ معادل واقعی ندارند.",materials(c.from_user.id));await safe_answer(c)
@router.callback_query(F.data.startswith("dwl:mat:"))
async def mat(c):
 if not await ensure_owner(c):return
 key=base(c).split(":")[2]
 async with economic_operation(c.from_user.id,f"dwl-mat:{c.id}"):
  async with async_session() as s:ok,msg=await LS.buy_material(s,c.from_user.id,key)
 await safe_answer(c,msg,show_alert=not ok)
 if ok:await mats(c)
@router.callback_query(F.data.startswith("dwl:upgrades"))
async def ups(c):
 if await ensure_owner(c):await safe_show(c.message,"🔧 هر بخش روی کیفیت، قدرت، پایداری، شانس، ظرفیت یا خطر اثر متفاوت دارد.",upgrades(c.from_user.id));await safe_answer(c)
@router.callback_query(F.data.startswith("dwl:up:"))
async def up(c):
 if not await ensure_owner(c):return
 key=base(c).split(":")[2]
 async with economic_operation(c.from_user.id,f"dwl-up:{c.id}"):
  async with async_session() as s:ok,msg=await LS.upgrade(s,c.from_user.id,key)
 await safe_answer(c,msg,show_alert=not ok)
 if ok:await ups(c)
@router.callback_query(F.data.startswith("dwl:repair"))
async def repair(c):
 if not await ensure_owner(c):return
 async with economic_operation(c.from_user.id,f"dwl-repair:{c.id}"):
  async with async_session() as s:ok,msg=await LS.repair(s,c.from_user.id)
 await safe_answer(c,msg,show_alert=not ok)
 if ok:await ups(c)
@router.callback_query(F.data.startswith("dwl:inventory"))
async def inv(c):
 if not await ensure_owner(c):return
 async with async_session() as s:rows=await LS.products(s,c.from_user.id)
 lines=["🎒 <b>محصولات داستانی</b>",""]+[f"{L.PRODUCTS[x.product_key]['icon']} {L.PRODUCTS[x.product_key]['name']} ×{x.qty} · کیفیت {x.avg_quality} · قدرت {x.avg_potency} · پایداری {x.avg_stability}" for x in rows];await safe_show(c.message,"\n".join(lines),inventory(rows,c.from_user.id));await safe_answer(c)
@router.callback_query(F.data.startswith("dwl:sell:"))
async def sell(c):
 if not await ensure_owner(c):return
 key=base(c).split(":")[2]
 async with economic_operation(c.from_user.id,f"dwl-sell:{c.id}"):
  async with async_session() as s:ok,msg=await LS.sell(s,c.from_user.id,key)
 await safe_answer(c,msg,show_alert=not ok)
 if ok:await inv(c)
@router.callback_query(F.data.startswith("dwl:locked"))
async def locked(c):
 if await ensure_owner(c):await safe_answer(c,"سطح آزمایشگاه کافی نیست.",show_alert=True)

@router.callback_query(F.data.startswith("dwl:none"))
async def none(c):
 if await ensure_owner(c):await safe_answer(c)
