# -*- coding: utf-8 -*-
from aiogram import F,Router
from app.database.engine import async_session
from app.data import dark_world_empire as E
from app.keyboards.dark_world_empire_menu import hub,builds,facilities,facility,rivals,responses,inspections
from app.services import dark_world_empire_service as S
from app.services.operation_guard import economic_operation
from app.utils.ui import ensure_owner,safe_answer,safe_show,split_owner
router=Router(name="dark_world_empire")
def raw(c):return split_owner(c.data or "")[0]
async def show(c):
 async with async_session() as s:p,fs,cap,stealth=await S.empire_stats(s,c.from_user.id);x=await S.active_inspection(s,c.from_user.id)
 ready=bool(x and x.status=='active' and x.ready_at<=S.now());text=f"🏰 <b>امپراتوری تولید</b>\n\nمراکز: {len(fs)}/5\nظرفیت شبکه: {cap}\nپنهان‌کاری: {stealth}\nقدرت برند: {p.brand_power}\nبرد برابر رقبا: {p.rival_wins}\nعبور از بازرسی: {p.inspection_wins}"+("\n\n🚨 هشدار بازرسی فعال است." if x and x.status=='warning' else "")
 await safe_show(c.message,text,hub(c.from_user.id,bool(x),ready));await safe_answer(c)
@router.callback_query(F.data.startswith("dwi:hub"))
async def h(c):
 if await ensure_owner(c):await show(c)
@router.callback_query(F.data.startswith("dwi:build"))
async def b(c):
 if await ensure_owner(c):await safe_show(c.message,"🏗️ مرکز بزرگ‌تر ظرفیت بیشتر اما ریسک و هزینه نگهداری بالاتری دارد.",builds(c.from_user.id));await safe_answer(c)
@router.callback_query(F.data.startswith("dwi:buy:"))
async def buy(c):
 if not await ensure_owner(c):return
 key=raw(c).split(":")[2]
 async with economic_operation(c.from_user.id,f"dwe-buy:{c.id}"):
  async with async_session() as s:ok,msg=await S.buy(s,c.from_user.id,key)
 await safe_answer(c,msg,show_alert=not ok)
 if ok:await show(c)
@router.callback_query(F.data.startswith("dwi:facilities"))
async def fs(c):
 if not await ensure_owner(c):return
 async with async_session() as s:rows=await S.facilities(s,c.from_user.id)
 await safe_show(c.message,"🏭 مرکز موردنظر را برای ارتقا انتخاب کن.",facilities(rows,c.from_user.id));await safe_answer(c)
@router.callback_query(F.data.startswith("dwi:facility:"))
async def fd(c):
 if not await ensure_owner(c):return
 fid=int(raw(c).split(":")[2])
 async with async_session() as s:x=await s.get(__import__('app.models.dark_world',fromlist=['DarkWorldFacility']).DarkWorldFacility,fid)
 if not x or x.owner_id!=c.from_user.id:return await safe_answer(c,"مرکز پیدا نشد.",show_alert=True)
 await safe_show(c.message,f"🏭 وضعیت {x.condition}%\nخط {x.capacity_level} · سایه {x.stealth_level} · مقاومت {x.resilience_level} · تحقیق {x.research_level}",facility(x,c.from_user.id));await safe_answer(c)
@router.callback_query(F.data.startswith("dwi:upgrade:"))
async def up(c):
 if not await ensure_owner(c):return
 _,_,fid,key=raw(c).split(":")
 async with economic_operation(c.from_user.id,f"dwe-up:{c.id}"):
  async with async_session() as s:ok,msg=await S.upgrade(s,c.from_user.id,int(fid),key)
 await safe_answer(c,msg,show_alert=not ok)
 if ok:await show(c)
@router.callback_query(F.data.startswith("dwi:rivals"))
async def rv(c):
 if await ensure_owner(c):await safe_show(c.message,"⚔️ رقیب پویا را انتخاب کن. پاسخ‌ها هزینه و اثر متفاوت دارند.",rivals(c.from_user.id));await safe_answer(c)
@router.callback_query(F.data.startswith("dwi:responses:"))
async def rs(c):
 if not await ensure_owner(c):return
 rival=raw(c).split(":")[2];await safe_show(c.message,"پاسخ استراتژیک را انتخاب کن.",responses(rival,c.from_user.id));await safe_answer(c)
@router.callback_query(F.data.startswith("dwi:rival:"))
async def fight(c):
 if not await ensure_owner(c):return
 _,_,r,a=raw(c).split(":")
 async with economic_operation(c.from_user.id,f"dwe-rival:{c.id}"):
  async with async_session() as s:ok,msg=await S.fight_rival(s,c.from_user.id,r,a)
 await safe_answer(c,msg,show_alert=not ok)
 if ok:await show(c)
@router.callback_query(F.data.startswith("dwi:inspection"))
async def ins(c):
 if not await ensure_owner(c):return
 async with async_session() as s:x=await S.active_inspection(s,c.from_user.id)
 if not x:return await safe_answer(c,"بازرسی فعالی نداری.",show_alert=True)
 if x.status=='warning':await safe_show(c.message,f"🚨 ریسک برآوردی: {x.risk_bp/100:.0f}%\nواکنش را انتخاب کن.",inspections(c.from_user.id));return await safe_answer(c)
 async with economic_operation(c.from_user.id,f"dwe-inspect:{c.id}"):
  async with async_session() as s:ok,msg=await S.resolve_inspection(s,c.from_user.id)
 await safe_answer(c,msg,show_alert=not ok)
 if ok:await show(c)
@router.callback_query(F.data.startswith("dwi:prepare:"))
async def prep(c):
 if not await ensure_owner(c):return
 key=raw(c).split(":")[2]
 async with economic_operation(c.from_user.id,f"dwe-prep:{c.id}"):
  async with async_session() as s:ok,msg=await S.prepare_inspection(s,c.from_user.id,key)
 await safe_answer(c,msg,show_alert=not ok)
 if ok:await show(c)
@router.callback_query(F.data.startswith("dwi:stats"))
async def stats(c):
 if await ensure_owner(c):await show(c)
