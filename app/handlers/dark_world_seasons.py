# -*- coding: utf-8 -*-
from aiogram import F,Router
from app.database.engine import async_session
from app.data import dark_world_seasons as S
from app.keyboards.dark_world_seasons_menu import hub,factions,choices,contribute
from app.services import dark_world_seasons_service as SS
from app.services.operation_guard import BusyOperation,DuplicateOperation,economic_operation
from app.utils.ui import ensure_owner,safe_answer,safe_show,split_owner
router=Router(name="dark_world_seasons")
def base(c):return split_owner(c.data or "")[0]
async def show(c):
 async with async_session() as s:season,mem,scores=await SS.state(s,c.from_user.id);await s.commit()
 done=season.status=="completed";chapter=S.chapter(min(season.chapter_index,S.CHAPTER_COUNT-1));remain=max(0,int((season.chapter_ends_at-SS.now()).total_seconds())) if not done else 0;f=S.FACTIONS.get(mem.faction_key) if mem else None
 text=f"🌒 <b>{season.title}</b>\n\nوضعیت: {'پایان‌یافته' if done else 'فصل '+str(season.chapter_index+1)+' از ۴'}\n📖 {chapter['title']}: {chapter['story']}\n⏱️ {remain//3600} ساعت و {(remain%3600)//60} دقیقه\n🏴 جناح: {f['icon']+' '+f['name'] if f else 'انتخاب نشده'}\n📦 کمک شخصی: {int(mem.contribution or 0) if mem else 0}\n\n🌍 اثرهای جمعی فعلی:\n📈 بازار {int(season.market_bias or 0):+d}٪ · 🧼 پول‌شویی {int(season.finance_bias or 0):+d} · ⚔️ شبیخون {int(season.raid_bias or 0):+d}"+(f"\n🏆 جناح پیروز: {S.FACTIONS[season.winning_faction]['name']}" if done and season.winning_faction else "")
 await safe_show(c.message,text,hub(c.from_user.id,bool(mem),done,bool(done and mem and not mem.reward_claimed)));await safe_answer(c)
@router.callback_query(F.data.startswith("dws:hub"))
async def h(c):
 if await ensure_owner(c):await show(c)
@router.callback_query(F.data.startswith("dws:factions"))
async def fs(c):
 if await ensure_owner(c):await safe_show(c.message,"🏴 <b>انتخاب جناح فصل</b>\nاین انتخاب تا پایان فصل قفل است و هر جناح مزیت متفاوتی دارد.\n\n"+"\n".join(f"{v['icon']} {v['name']}: {v['perk']}" for v in S.FACTIONS.values()),factions(c.from_user.id));await safe_answer(c)
@router.callback_query(F.data.startswith("dws:join:"))
async def join(c):
 if not await ensure_owner(c):return
 key=base(c).split(":")[2]
 async with async_session() as s:ok,msg=await SS.join(s,c.from_user.id,key)
 await safe_answer(c,msg,show_alert=not ok)
 if ok:await show(c)
@router.callback_query(F.data.startswith("dws:choices"))
async def ch(c):
 if not await ensure_owner(c):return
 async with async_session() as s:season=await SS.ensure(s);await s.commit()
 x=S.chapter(season.chapter_index);text=f"🗳️ <b>{x['title']}</b>\n\n{x['story']}\n\n"+"\n".join(f"• {v['name']}: {v['effect']}" for v in x['choices'].values())
 await safe_show(c.message,text,choices(x,c.from_user.id));await safe_answer(c)
@router.callback_query(F.data.startswith("dws:vote:"))
async def vote(c):
 if not await ensure_owner(c):return
 key=base(c).split(":")[2]
 try:
  async with economic_operation(c.from_user.id,f"dws-vote:{c.id}"):
   async with async_session() as s:ok,msg=await SS.vote(s,c.from_user.id,key)
 except (BusyOperation,DuplicateOperation):return await safe_answer(c,"رأی تکراری مسدود شد.",show_alert=True)
 await safe_answer(c,msg,show_alert=not ok)
 if ok:await show(c)
@router.callback_query(F.data.startswith("dws:contrib"))
async def co(c):
 if await ensure_owner(c):await safe_show(c.message,"📦 <b>کمک به جناح</b>\nIntel امتیاز کمتر اما هزینه اقتصادی ندارد؛ پول کثیف امتیاز بیشتری می‌دهد.",contribute(c.from_user.id));await safe_answer(c)
@router.callback_query(F.data.startswith("dws:give:"))
async def give(c):
 if not await ensure_owner(c):return
 kind=base(c).split(":")[2]
 try:
  async with economic_operation(c.from_user.id,f"dws-give:{c.id}"):
   async with async_session() as s:ok,msg=await SS.contribute(s,c.from_user.id,kind)
 except (BusyOperation,DuplicateOperation):return await safe_answer(c,"کمک تکراری مسدود شد.",show_alert=True)
 await safe_answer(c,msg,show_alert=not ok)
 if ok:await show(c)
@router.callback_query(F.data.startswith("dws:board"))
async def board(c):
 if not await ensure_owner(c):return
 async with async_session() as s:season=await SS.ensure(s);rows=await SS.board(s,season.id);await s.commit()
 text="🏆 <b>جدول جناح‌ها</b>\n\n"+"\n".join(f"{i}. {S.FACTIONS[x.faction_key]['icon']} {S.FACTIONS[x.faction_key]['name']} — {int(x.points):,}" for i,x in enumerate(rows,1));await safe_show(c.message,text,hub(c.from_user.id));await safe_answer(c)
@router.callback_query(F.data.startswith("dws:claim"))
async def claim(c):
 if not await ensure_owner(c):return
 try:
  async with economic_operation(c.from_user.id,f"dws-claim:{c.id}"):
   async with async_session() as s:ok,msg=await SS.claim(s,c.from_user.id)
 except (BusyOperation,DuplicateOperation):return await safe_answer(c,"دریافت تکراری مسدود شد.",show_alert=True)
 await safe_answer(c,msg,show_alert=not ok)
 if ok:await show(c)
