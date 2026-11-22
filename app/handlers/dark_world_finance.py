# -*- coding: utf-8 -*-
from aiogram import F,Router
from aiogram.types import CallbackQuery
from app.database.engine import async_session
from app.data import dark_world_finance as DF
from app.keyboards.dark_world_finance_menu import hub,amounts,methods,start,rare
from app.services import dark_world_finance_service as FS
from app.services.operation_guard import BusyOperation,DuplicateOperation,economic_operation
from app.utils.ui import ensure_owner,safe_answer,safe_show,split_owner
router=Router(name="dark_world_finance")
def base(c):return split_owner(c.data or "")[0]
async def show(c):
 async with async_session() as s:ok,msg,x=await FS.snapshot(s,c.from_user.id);await s.commit()
 if not ok:return await safe_answer(c,msg,show_alert=True)
 a=x['account'];j=x['active'];rem=max(0,int((j.ready_at-FS.now()).total_seconds())) if j else 0;cl=DF.climate()
 text=f"🕶️ <b>اقتصاد بازار سیاه</b>\n\n🌑 پول کثیف: <b>{int(a.dirty_balance or 0):,}</b>\n💵 مجموع پاک‌شده: {int(a.total_cleaned or 0):,}\n🚨 ردگیری مالی: <b>{int(a.trace or 0)}/100</b>\n📡 وضعیت امروز: <b>{cl['name']}</b>\n<i>{cl['clue']}</i>\n🎯 عملیات: {('آماده دریافت' if rem<=0 else str(rem//60+1)+' دقیقه مانده') if j else 'نداری'}\n\nردگیری هر ساعت یک واحد کم می‌شود. روش سریع‌تر ارزان‌تر است، اما احتمال مصادره و رد بیشتری دارد."
 await safe_show(c.message,text,hub(c.from_user.id,bool(j),bool(j and rem<=0)));await safe_answer(c)
@router.callback_query(F.data.startswith("dwf:hub"))
async def h(c):
 if await ensure_owner(c):await show(c)
@router.callback_query(F.data.startswith("dwf:amounts"))
async def am(c):
 if not await ensure_owner(c):return
 async with async_session() as s:a=await FS.account(s,c.from_user.id);FS.recover(a);await s.commit()
 await safe_show(c.message,"🧼 <b>مقدار پول‌شویی</b>\nمبلغ بزرگ‌تر سود مطلق بیشتری دارد، اما شانس را کم و مصادره را سنگین‌تر می‌کند.",amounts(a.dirty_balance,c.from_user.id));await safe_answer(c)
@router.callback_query(F.data.startswith("dwf:methods:"))
async def ms(c):
 if not await ensure_owner(c):return
 pct=int(base(c).split(":")[2]);await safe_show(c.message,"روش را انتخاب کن:\n🏪 امن و پرکارمزد\n🤝 متعادل\n🕸️ سریع، ارزان و پرریسک",methods(pct,c.from_user.id));await safe_answer(c)
@router.callback_query(F.data.startswith("dwf:prev:"))
async def prev(c):
 if not await ensure_owner(c):return
 _,_,pct,m=base(c).split(":")
 async with async_session() as s:ok,msg,p=await FS.preview(s,c.from_user.id,int(pct),m);await s.commit()
 if not p:return await safe_answer(c,msg,show_alert=True)
 x=DF.METHODS[m];text=f"{x['icon']} <b>{x['name']}</b>\n\nمبلغ: {p['amount']:,}\nپول پاک احتمالی: {p['clean']:,}\nکارمزد: {p['fee_pct']}٪\nشانس: {p['chance']:.2f}٪\nردگیری: +{p['trace_gain']}\nمصادره در شکست: {p['confiscation_pct']}٪\nزمان: {p['duration']//60} دقیقه\n\nوضعیت امروز: {p['climate']['name']}"
 await safe_show(c.message,text,start(pct,m,c.from_user.id) if ok else methods(pct,c.from_user.id));await safe_answer(c,msg if not ok else "")
@router.callback_query(F.data.startswith("dwf:start:"))
async def go(c):
 if not await ensure_owner(c):return
 _,_,pct,m=base(c).split(":")
 try:
  async with economic_operation(c.from_user.id,f"dwf-start:{c.id}"):
   async with async_session() as s:ok,msg=await FS.start(s,c.from_user.id,int(pct),m)
 except (BusyOperation,DuplicateOperation):return await safe_answer(c,"عملیات تکراری مسدود شد.",show_alert=True)
 await safe_answer(c,msg[:180],show_alert=not ok)
 if ok:await show(c)
@router.callback_query(F.data.startswith("dwf:active"))
async def collect(c):
 if not await ensure_owner(c):return
 try:
  async with economic_operation(c.from_user.id,f"dwf-collect:{c.id}"):
   async with async_session() as s:ok,msg=await FS.collect(s,c.from_user.id)
 except (BusyOperation,DuplicateOperation):return await safe_answer(c,"دریافت تکراری مسدود شد.",show_alert=True)
 await safe_answer(c,msg[:180],show_alert=not ok)
 if ok:await safe_show(c.message,msg,hub(c.from_user.id));await safe_answer(c)
 else:await show(c)
@router.callback_query(F.data.startswith("dwf:rare"))
async def rares(c):
 if not await ensure_owner(c):return
 keys=DF.rare_today();text="🕶️ <b>واسطه‌های امروز</b>\n\n"+"\n".join(f"{DF.RARE[k]['icon']} {DF.RARE[k]['name']} — {DF.RARE[k]['price']:,}" for k in keys)
 await safe_show(c.message,text,rare(keys,c.from_user.id));await safe_answer(c)
@router.callback_query(F.data.startswith("dwf:buy:"))
async def buy(c):
 if not await ensure_owner(c):return
 key=base(c).split(":")[2]
 try:
  async with economic_operation(c.from_user.id,f"dwf-buy:{c.id}"):
   async with async_session() as s:ok,msg=await FS.buy_rare(s,c.from_user.id,key)
 except (BusyOperation,DuplicateOperation):return await safe_answer(c,"خرید تکراری مسدود شد.",show_alert=True)
 await safe_answer(c,msg[:180],show_alert=not ok)
 if ok:await show(c)
@router.callback_query(F.data.startswith("dwf:log"))
async def log(c):
 if not await ensure_owner(c):return
 async with async_session() as s:rows=await FS.logs(s,c.from_user.id)
 text="📜 <b>دفتر ردگیری مالی</b>\n\n"+("\n".join(f"#{r.id} · {r.event_key} · {int(r.amount):,} · رد {int(r.trace_delta):+d}" for r in rows) or "هنوز رویدادی ثبت نشده.")
 await safe_show(c.message,text,hub(c.from_user.id));await safe_answer(c)
