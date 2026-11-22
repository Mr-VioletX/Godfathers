# -*- coding: utf-8 -*-
from aiogram import F,Router
from app.database.engine import async_session
from app.data import dark_world_competitive as C
from app.keyboards.dark_world_competitive_menu import hub
from app.services import dark_world_competitive_service as CS
from app.services.operation_guard import BusyOperation,DuplicateOperation,economic_operation
from app.utils.ui import ensure_owner,safe_answer,safe_show
router=Router(name="dark_world_competitive")
async def show(c):
 async with async_session() as s:season,rows,b,mine,reward=await CS.state(s,c.from_user.id);await s.commit()
 text=f"🏆 <b>رقابت پایان فصل</b>\n\nفصل: {season.title} · {season.status}\nرتبه: {mine.rank if mine else '—'}\nامتیاز: {int(mine.score) if mine else 0:,}\nلیگ: {mine.division_key if mine else 'بدون رتبه'}\nفعالیت معتبر: {int(mine.activity) if mine else 0}/{C.MIN_RANK_ACTIVITY}\n👁️ نگهبان شب: {int(b.current_hp):,}/{int(b.max_hp):,}\n\nامتیاز از چند مسیر مستقل محاسبه می‌شود؛ ثروت یا نفوذ به‌تنهایی کافی نیست."
 claimable=season.status=='completed' and mine and mine.eligible and not reward;await safe_show(c.message,text,hub(c.from_user.id,season.status=='completed',claimable,b.status=='active'));await safe_answer(c)
@router.callback_query(F.data.startswith("dwk:hub"))
async def h(c):
 if await ensure_owner(c):await show(c)
@router.callback_query(F.data.startswith("dwk:board"))
async def board(c):
 if not await ensure_owner(c):return
 async with async_session() as s:season,rows,b,mine,reward=await CS.state(s,c.from_user.id);await s.commit()
 lines=["🏆 <b>جدول چندمحوره</b>",""]+[f"{x.rank}. {C.division(x.score)['icon']} {x.owner_id} — {int(x.score):,} · فعالیت {x.activity}" for x in rows[:15]];await safe_show(c.message,"\n".join(lines),hub(c.from_user.id));await safe_answer(c)
@router.callback_query(F.data.startswith("dwk:me"))
async def me(c):
 if not await ensure_owner(c):return
 async with async_session() as s:season,rows,b,x,reward=await CS.state(s,c.from_user.id);await s.commit()
 if not x:return await safe_answer(c,"هنوز عضو فصل نیستی.",show_alert=True)
 text=f"📊 <b>جزئیات امتیاز</b>\n\nرتبه {x.rank} · {x.division_key} · {int(x.score):,}\nعملیات: {x.activity}\nقاچاق موفق: {x.shipments}\nپول‌شویی موفق: {x.launders}\nبرد شبیخون: {x.raid_wins}\nکار موفق: {x.employment}\nآسیب باس: {x.boss_damage:,}\nنفوذ snapshot: {x.influence_snapshot if hasattr(x,'influence_snapshot') else x.influence:,}\nکمک جناحی: {x.contribution_snapshot if hasattr(x,'contribution_snapshot') else x.contribution:,}"
 await safe_show(c.message,text,hub(c.from_user.id));await safe_answer(c)
@router.callback_query(F.data.startswith("dwk:boss"))
async def boss(c):
 if not await ensure_owner(c):return
 try:
  async with economic_operation(c.from_user.id,f"dwc-boss:{c.id}"):
   async with async_session() as s:ok,msg=await CS.hit_boss(s,c.from_user.id)
 except (BusyOperation,DuplicateOperation):return await safe_answer(c,"ضربه تکراری مسدود شد.",show_alert=True)
 await safe_answer(c,msg[:180],show_alert=not ok)
 if ok:await show(c)
@router.callback_query(F.data.startswith("dwk:economy"))
async def economy(c):
 if not await ensure_owner(c):return
 async with async_session() as s:season=await __import__('app.services.dark_world_seasons_service',fromlist=['ensure']).ensure(s);x=await CS.telemetry(s,season);await s.commit()
 text=f"📈 <b>تله‌متری اقتصاد فصل</b>\n\nپول کثیف تولیدشده: {int(x.dirty_created):,}\nپول پاک‌شده: {int(x.cleaned):,}\nمصادره: {int(x.confiscated):,}\nحجم بازار کاربران: {int(x.market_volume):,}\nضریب جایزه: {int(x.reward_factor_bp)/10000:.3f}\n\nضریب فقط در بازه ۰٫۷۵ تا ۱٫۱۵ حرکت می‌کند تا تنظیم اقتصاد قابل‌کنترل باشد."
 await safe_show(c.message,text,hub(c.from_user.id));await safe_answer(c)
@router.callback_query(F.data.startswith("dwk:claim"))
async def claim(c):
 if not await ensure_owner(c):return
 try:
  async with economic_operation(c.from_user.id,f"dwc-claim:{c.id}"):
   async with async_session() as s:ok,msg=await CS.claim(s,c.from_user.id)
 except (BusyOperation,DuplicateOperation):return await safe_answer(c,"دریافت تکراری مسدود شد.",show_alert=True)
 await safe_answer(c,msg[:180],show_alert=not ok)
 if ok:await show(c)
@router.callback_query(F.data.startswith("dwk:hall"))
async def hall(c):
 if not await ensure_owner(c):return
 async with async_session() as s:rows=await CS.hall(s)
 text="🏛️ <b>تالار افتخار</b>\n\n"+("\n".join(f"{i}. {x.owner_id} — امتیاز {int(x.rating):,} · افتخار {int(x.prestige):,} · بهترین رتبه {x.best_rank or '—'}" for i,x in enumerate(rows,1)) or "هنوز قهرمانی ثبت نشده.");await safe_show(c.message,text,hub(c.from_user.id));await safe_answer(c)
