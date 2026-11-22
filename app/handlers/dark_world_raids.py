# -*- coding: utf-8 -*-
from aiogram import F,Router
from app.database.engine import async_session
from app.data import dark_world_raids as R
from app.keyboards.dark_world_raids_menu import hub,targets,approaches,defenses,lobby,raid as raid_menu
from app.services import dark_world_raids_service as RS
from app.services.operation_guard import BusyOperation,DuplicateOperation,economic_operation
from app.utils.ui import ensure_owner,safe_answer,safe_show,split_owner
router=Router(name="dark_world_raids")
def base(c):return split_owner(c.data or "")[0]
@router.callback_query(F.data.startswith("dwr:hub"))
async def h(c):
 if await ensure_owner(c):await safe_show(c.message,"⚔️ <b>شبیخون و جنگ اطلاعاتی</b>\n\nهدف را شناسایی کن، روش حمله را با دفاع احتمالی تطبیق بده و از هم‌پیمانان کمک بگیر. هر شبیخون ۱۰ دقیقه برای تشکیل گروه باز می‌ماند.",hub(c.from_user.id));await safe_answer(c)
@router.callback_query(F.data.startswith("dwr:targets"))
async def tg(c):
 if not await ensure_owner(c):return
 async with async_session() as s:rows=await RS.targets(s,c.from_user.id)
 await safe_show(c.message,"🎯 <b>اهداف سطح ۳۵ به بالا</b>\nشناسایی ۸ Intel هزینه دارد و گزارش تا دو ساعت معتبر است.",targets(rows,c.from_user.id));await safe_answer(c)
@router.callback_query(F.data.startswith("dwr:scout:"))
async def scout(c):
 if not await ensure_owner(c):return
 target=int(base(c).split(":")[2])
 try:
  async with economic_operation(c.from_user.id,f"dwr-scout:{c.id}"):
   async with async_session() as s:ok,msg,row=await RS.recon(s,c.from_user.id,target)
 except (BusyOperation,DuplicateOperation):return await safe_answer(c,"شناسایی تکراری مسدود شد.",show_alert=True)
 if not ok:return await safe_answer(c,msg,show_alert=True)
 clue=R.DEFENSES[row.observed_defense]['clue'];await safe_show(c.message,f"🕵️ <b>گزارش هدف</b>\n\n{clue}\n\nگزارش ممکن است به‌خاطر ضدجاسوسی دقیق نباشد. روش حمله را انتخاب کن؛ وثیقه {R.STAKE:,} پول کثیف است.",approaches(target,c.from_user.id));await safe_answer(c)
@router.callback_query(F.data.startswith("dwr:create:"))
async def create(c):
 if not await ensure_owner(c):return
 _,_,target,a=base(c).split(":")
 try:
  async with economic_operation(c.from_user.id,f"dwr-create:{c.id}"):
   async with async_session() as s:ok,msg,row=await RS.create(s,c.from_user.id,int(target),a)
 except (BusyOperation,DuplicateOperation):return await safe_answer(c,"ساخت تکراری مسدود شد.",show_alert=True)
 await safe_answer(c,msg[:180],show_alert=not ok)
 if ok:await safe_show(c.message,msg,raid_menu(row,c.from_user.id,False,False));await safe_answer(c)
@router.callback_query(F.data.startswith("dwr:defenses"))
async def defs(c):
 if await ensure_owner(c):await safe_show(c.message,"🛡️ <b>آرایش دفاعی دائمی</b>\n🎭 طعمه علیه محاصره سیگنال\n🧱 قلعه علیه ضربه برق‌آسا\n🕵️ ضدجاسوسی علیه نفوذ خاموش",defenses(c.from_user.id));await safe_answer(c)
@router.callback_query(F.data.startswith("dwr:def:"))
async def setdef(c):
 if not await ensure_owner(c):return
 key=base(c).split(":")[2]
 async with async_session() as s:ok,msg=await RS.set_defense(s,c.from_user.id,key)
 await safe_answer(c,msg,show_alert=not ok)
 if ok:await h(c)
@router.callback_query(F.data.startswith("dwr:lobby"))
async def lob(c):
 if not await ensure_owner(c):return
 async with async_session() as s:rows=await RS.lobby(s)
 await safe_show(c.message,"🤝 <b>لابی شبیخون‌های باز</b>\nهر بازیکن می‌تواند با هزینه ۵ Intel به یکی از دو سمت بپیوندد؛ هر سمت دو جایگاه پشتیبان دارد.",lobby(rows,c.from_user.id));await safe_answer(c)
@router.callback_query(F.data.startswith("dwr:view:"))
async def view(c):
 if not await ensure_owner(c):return
 rid=int(base(c).split(":")[2])
 async with async_session() as s:x=await RS.get_raid(s,rid);parts=await RS.participants(s,rid)
 if not x:return await safe_answer(c,"نبرد پیدا نشد.",show_alert=True)
 rem=max(0,int((x.lock_at-RS.now()).total_seconds()));text=f"⚔️ <b>شبیخون #{x.id}</b>\n\nمهاجم: {x.attacker_id}\nمدافع: {x.defender_id}\nروش مهاجم: {R.APPROACHES[x.approach_key]['name']}\nپشتیبان حمله: {x.attack_support_count}/2\nپشتیبان دفاع: {x.defense_support_count}/2\nوضعیت: {x.status}\n⏱️ {rem//60+1 if rem else 0} دقیقه تا قفل\n\nآرایش دفاع تا زمان نتیجه پنهان می‌ماند."
 await safe_show(c.message,text,raid_menu(x,c.from_user.id,x.status=='forming' and rem>0,x.status=='forming' and rem==0));await safe_answer(c)
@router.callback_query(F.data.startswith("dwr:join:"))
async def join(c):
 if not await ensure_owner(c):return
 _,_,rid,side=base(c).split(":")
 try:
  async with economic_operation(c.from_user.id,f"dwr-join:{c.id}"):
   async with async_session() as s:ok,msg=await RS.join(s,c.from_user.id,int(rid),side)
 except (BusyOperation,DuplicateOperation):return await safe_answer(c,"پیوستن تکراری مسدود شد.",show_alert=True)
 await safe_answer(c,msg[:180],show_alert=not ok)
 if ok:
  async with async_session() as s:rows=await RS.lobby(s)
  await safe_show(c.message,"✅ به نبرد پیوستی.",lobby(rows,c.from_user.id));await safe_answer(c)
@router.callback_query(F.data.startswith("dwr:resolve:"))
async def resolve(c):
 if not await ensure_owner(c):return
 rid=int(base(c).split(":")[2])
 try:
  async with economic_operation(c.from_user.id,f"dwr-resolve:{rid}"):
   async with async_session() as s:ok,msg,_=await RS.resolve(s,c.from_user.id,rid)
 except (BusyOperation,DuplicateOperation):return await safe_answer(c,"حل تکراری مسدود شد.",show_alert=True)
 await safe_answer(c,msg[:180],show_alert=not ok)
 if ok:await safe_show(c.message,msg,hub(c.from_user.id));await safe_answer(c)
@router.callback_query(F.data.startswith("dwr:mine"))
async def mine(c):
 if not await ensure_owner(c):return
 async with async_session() as s:rows=await RS.mine(s,c.from_user.id)
 lines=["📜 <b>نبردهای من</b>",""]+[f"#{x.id} · {R.APPROACHES[x.approach_key]['name']} · {x.status} · غنیمت {int(x.stolen_amount or 0):,}" for x in rows]
 await safe_show(c.message,"\n".join(lines),hub(c.from_user.id));await safe_answer(c)
