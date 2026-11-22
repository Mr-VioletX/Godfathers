# -*- coding: utf-8 -*-
from aiogram import F,Router
from app.database.engine import async_session
from app.data import dark_world_distribution as D
from app.keyboards.dark_world_distribution_menu import hub,products,districts,channels,screens
from app.services import dark_world_distribution_service as DS
from app.services import dark_world_recipes_service as RS
from app.services.operation_guard import economic_operation
from app.utils.ui import ensure_owner,safe_answer,safe_show,split_owner
router=Router(name="dark_world_distribution")
def base(c):return split_owner(c.data or "")[0]
async def show(c):
 async with async_session() as s:a=await DS.active(s,c.from_user.id);rows=await DS.mine(s,c.from_user.id)
 rem=max(0,int((a.ready_at-DS.now()).total_seconds())) if a else 0;text="🚚 <b>شبکه توزیع داستانی</b>\n\nکانال، محله و روش بررسی مشتری روی حجم، قیمت، Heat و خطر مأمور مخفی اثر دارند.\n\n"+"\n".join(f"{D.DISTRICTS[x.district_key]['icon']} {D.DISTRICTS[x.district_key]['name']}: شهرت {x.reputation} · کنترل {x.control_points}" for x in rows)+(f"\n⏳ معامله: {'آماده' if rem<=0 else str(rem//60+1)+' دقیقه'}" if a else "")
 await safe_show(c.message,text,hub(c.from_user.id,bool(a),bool(a and rem<=0)));await safe_answer(c)
@router.callback_query(F.data.startswith("dwd:hub"))
async def h(c):
 if await ensure_owner(c):await show(c)
@router.callback_query(F.data.startswith("dwd:products"))
async def ps(c):
 if not await ensure_owner(c):return
 async with async_session() as s:rows=await DS.inventory(s,c.from_user.id);forms={x.id:x.custom_name for x in await RS.recipes(s,c.from_user.id)}
 page=int(base(c).split(":")[2]) if len(base(c).split(":"))>2 else 0
 await safe_show(c.message,"🛍️ محصول ترکیبی را انتخاب کن.",products(rows,forms,c.from_user.id,page));await safe_answer(c)
@router.callback_query(F.data.startswith("dwd:districts:"))
async def ds(c):
 if not await ensure_owner(c):return
 rid=base(c).split(":")[2];await safe_show(c.message,"🗺️ محله را براساس ثروت، سلیقه و شدت بازرسی انتخاب کن.",districts(rid,c.from_user.id));await safe_answer(c)
@router.callback_query(F.data.startswith("dwd:channels:"))
async def ch(c):
 if not await ensure_owner(c):return
 _,_,rid,d=base(c).split(":");await safe_show(c.message,"کانال مستقیم سود بیشتر و خطر بالاتر دارد؛ عمده‌فروش حجم بالا و حاشیه کمتر.",channels(rid,d,c.from_user.id));await safe_answer(c)
@router.callback_query(F.data.startswith("dwd:screens:"))
async def sc(c):
 if not await ensure_owner(c):return
 _,_,rid,d,k=base(c).split(":");await safe_show(c.message,"روش بررسی مشتری را انتخاب کن؛ سرعت بیشتر می‌تواند مأمور مخفی را پنهان کند.",screens(rid,d,k,c.from_user.id));await safe_answer(c)
@router.callback_query(F.data.startswith("dwd:start:"))
async def start(c):
 if not await ensure_owner(c):return
 _,_,rid,d,k,s=base(c).split(":")
 async with economic_operation(c.from_user.id,f"dwd-start:{c.id}"):
  async with async_session() as db:ok,msg=await DS.start(db,c.from_user.id,int(rid),d,k,s)
 await safe_answer(c,msg[:180],show_alert=not ok)
 if ok:await show(c)
@router.callback_query(F.data.startswith("dwd:active"))
async def collect(c):
 if not await ensure_owner(c):return
 async with economic_operation(c.from_user.id,f"dwd-collect:{c.id}"):
  async with async_session() as s:ok,msg=await DS.collect(s,c.from_user.id)
 await safe_answer(c,msg[:180],show_alert=not ok)
 if ok:await safe_show(c.message,msg,hub(c.from_user.id));await safe_answer(c)
 else:await show(c)
@router.callback_query(F.data.startswith("dwd:territory"))
async def territory(c):
 if not await ensure_owner(c):return
 async with async_session() as s:rows=await DS.territories(s)
 leaders={}
 for x in rows:leaders.setdefault(x.district_key,x)
 text="🗺️ <b>رهبران منطقه‌ای</b>\n\n"+"\n".join(f"{D.DISTRICTS[k]['icon']} {D.DISTRICTS[k]['name']}: {leaders[k].owner_id} · {leaders[k].control_points}" if k in leaders else f"{D.DISTRICTS[k]['icon']} {D.DISTRICTS[k]['name']}: آزاد" for k in D.DISTRICT_ORDER);await safe_show(c.message,text,hub(c.from_user.id));await safe_answer(c)
@router.callback_query(F.data.startswith("dwd:contacts"))
async def contacts(c):
 if not await ensure_owner(c):return
 async with async_session() as s:rows=await DS.contacts(s,c.from_user.id)
 text="👥 <b>شبکه مشتریان</b>\n\n"+("\n".join(f"{D.DISTRICTS[x.district_key]['name']} · {D.CUSTOMER_NAMES[x.customer_key]} · اعتماد {x.trust} · معامله {x.deals}" for x in rows) or "هنوز مشتری پایداری نداری.");await safe_show(c.message,text,hub(c.from_user.id));await safe_answer(c)

@router.callback_query(F.data.startswith("dwd:none"))
async def none(c):
 if await ensure_owner(c):await safe_answer(c)
