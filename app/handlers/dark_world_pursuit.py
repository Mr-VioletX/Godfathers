# -*- coding: utf-8 -*-
"""Stage 87.3 — strategic pursuit, hideout and prison handlers."""
from aiogram import F,Router
from aiogram.types import CallbackQuery
from app.database.engine import async_session
from app.data import dark_world_pursuit as P
from app.keyboards.dark_world_pursuit_menu import pursuit_menu,plans_menu,confirm_plan_menu,escape_menu
from app.services import dark_world_pursuit_service as PS
from app.services.operation_guard import BusyOperation,DuplicateOperation,economic_operation
from app.utils.ui import click_debounce,ensure_owner,safe_answer,safe_show,split_owner
router=Router(name="dark_world_pursuit")

def _base(cb):return split_owner(cb.data or "")[0]

def hub_text(state):
 p,h=state["profile"],state["hideout"]; remain=int(state["prison_remaining"]); band=P.heat_band(int(p.heat or 0)); clues=state["clues"]
 lines=["🕵️ <b>تعقیب و مخفیگاه</b>","<i>تهدید پنهان است؛ سرنخ بخر، الگو را تشخیص بده و ضدنقشه درست را انتخاب کن.</i>","",f"🚨 Heat: <b>{int(p.heat or 0)}/100 — {band['name']}</b>",band["description"],f"🏚️ مخفیگاه: <b>سطح {int(h.level)} · {P.hideout(h.level)['name']}</b>",f"🧱 استحکام: <b>{int(h.integrity or 0)}/100</b>",f"🎭 هویت جعلی: <b>{int(h.forged_ids or 0)}/{P.FORGED_ID_MAX}</b>"]
 if remain:
  lines += ["",f"⛓️ زندان ویژه: <b>{remain//60+1} دقیقه مانده</b>","می‌توانی صبر کنی یا یکی از نقشه‌های فرار با هزینه و ریسک متفاوت را اجرا کنی."]
 elif h.threat_key:
  lines += ["", "⚠️ <b>یک تهدید فعال است، اما نوع آن عمداً مخفی مانده.</b>",f"🔎 سرنخ‌های جمع‌شده: <b>{len(clues)}/{P.MAX_CLUES}</b>"]
  for i,c in enumerate(clues,1):lines.append(f"{i}. {c}")
  lines += ["","یکی از سه سرنخ می‌تواند رد گم‌کن باشد؛ با مقایسه نشانه‌ها تصمیم بگیر."]
 else: lines += ["","✅ فعلاً تعقیب فعالی نداری. با بالا رفتن Heat، تهدید جدید به‌صورت پویا شکل می‌گیرد."]
 return "\n".join(lines)

def plans_text(state):
 lines=["♟️ <b>اتاق ضدنقشه</b>","","نوع تهدید نمایش داده نمی‌شود. درصدها برآورد شبکه تو هستند، نه پاسخ قطعی؛ سرنخ‌ها را تفسیر کن.",""]
 for key in P.ACTION_ORDER:
  a=P.ACTIONS[key]; info=state["chances"].get(key,{})
  lines.append(f"{a['icon']} <b>{a['name']}</b> — برآورد {float(info.get('chance',0)):.0f}٪\n   {a['description']}\n   هزینه: {int(a.get('cash',0)):,} پول · {int(a.get('energy',0))} انرژی · {int(a.get('intel',0))} اطلاعات")
 return "\n".join(lines)

@router.callback_query(F.data.startswith("dwp:hub"))
async def pursuit_hub(cb:CallbackQuery):
 if not await ensure_owner(cb):return
 async with async_session() as s:
  ok,msg,state=await PS.snapshot(s,cb.from_user.id); await s.commit()
 if not ok:await safe_answer(cb,msg,show_alert=True);return
 h=state["hideout"]; await safe_show(cb.message,hub_text(state),pursuit_menu(cb.from_user.id,bool(h.threat_key),len(state["clues"])<P.MAX_CLUES,bool(state["prison_remaining"])));await safe_answer(cb)

@router.callback_query(F.data.startswith("dwp:recon"))
async def recon(cb):
 if not await ensure_owner(cb):return
 if click_debounce(cb.from_user.id,"dwp_recon",2.5):await safe_answer(cb,"در حال پردازش است.");return
 try:
  async with economic_operation(cb.from_user.id,f"dwp-recon:{cb.id}"):
   async with async_session() as s:ok,msg=await PS.recon(s,cb.from_user.id)
 except (BusyOperation,DuplicateOperation):await safe_answer(cb,"این شناسایی قبلاً ثبت شده است.",show_alert=True);return
 await safe_answer(cb,msg[:180],show_alert=not ok)
 if ok: await pursuit_hub(cb)

@router.callback_query(F.data.startswith("dwp:plans"))
async def plans(cb):
 if not await ensure_owner(cb):return
 async with async_session() as s:ok,msg,state=await PS.snapshot(s,cb.from_user.id);await s.commit()
 if not ok or not state["hideout"].threat_key:await safe_answer(cb,msg if not ok else "تهدید فعالی نداری.",show_alert=True);return
 await safe_show(cb.message,plans_text(state),plans_menu(cb.from_user.id,state["chances"],int(state["hideout"].forged_ids or 0)));await safe_answer(cb)

@router.callback_query(F.data.startswith("dwp:plan:"))
async def plan_detail(cb):
 if not await ensure_owner(cb):return
 key=_base(cb).split(":")[2];a=P.get_action(key)
 if not a:await safe_answer(cb,"نقشه نامعتبر است.",show_alert=True);return
 async with async_session() as s:ok,msg,state=await PS.snapshot(s,cb.from_user.id);await s.commit()
 if not ok:return await safe_answer(cb,msg,show_alert=True)
 info=state["chances"].get(key,{})
 text=f"{a['icon']} <b>{a['name']}</b>\n\n{a['description']}\n\n🎲 برآورد شبکه: <b>{float(info.get('chance',0)):.2f}٪</b>\n💵 پول: {int(a.get('cash',0)):,}\n⚡ انرژی: {int(a.get('energy',0))}\n👁️ اطلاعات: {int(a.get('intel',0))}\n\n⚠️ تطبیق نقشه با تهدید مهم‌تر از درصد خام است؛ نتیجه و هزینه قابل بازگشت نیست."
 await safe_show(cb.message,text,confirm_plan_menu(key,cb.from_user.id));await safe_answer(cb)

@router.callback_query(F.data.startswith("dwp:do:"))
async def do_plan(cb):
 if not await ensure_owner(cb):return
 if click_debounce(cb.from_user.id,"dwp_plan",3):await safe_answer(cb,"در حال پردازش است.");return
 key=_base(cb).split(":")[2]
 try:
  async with economic_operation(cb.from_user.id,f"dwp-plan:{cb.id}"):
   async with async_session() as s:ok,msg,payload=await PS.execute_plan(s,cb.from_user.id,key)
 except (BusyOperation,DuplicateOperation):await safe_answer(cb,"این ضدنقشه قبلاً اجرا شده است.",show_alert=True);return
 if not ok:await safe_answer(cb,msg[:180],show_alert=True);return
 r=payload["result"];icon="✅" if r["success"] else "❌"; verdict="تهدید خنثی شد" if r["success"] else ("دستگیر شدی" if r["jailed"] else "ضدنقشه شکست خورد")
 text=f"{icon} <b>{verdict}</b>\n\nتهدید واقعی: {payload['threat']['icon']} <b>{payload['threat']['name']}</b>\nنقشه تو: {payload['action']['icon']} {payload['action']['name']}\nتطبیق تخصصی: {'بله' if r['is_counter'] else 'خیر'}\n🎲 شانس ثبت‌شده: {r['chance']:.2f}٪ · رول {payload['roll']:.2f}\n🚨 Heat جدید: <b>{payload['heat']}/100</b>\n🧱 استحکام: {payload['integrity']}/100"
 await safe_show(cb.message,text,pursuit_menu(cb.from_user.id,False,False,bool(r["jailed"])));await safe_answer(cb,"نتیجه ثبت شد")

@router.callback_query(F.data.startswith("dwp:upgrade"))
@router.callback_query(F.data.startswith("dwp:buyid"))
async def purchase(cb):
 if not await ensure_owner(cb):return
 op="upgrade" if _base(cb).startswith("dwp:upgrade") else "buyid"
 if click_debounce(cb.from_user.id,f"dwp_{op}",3):await safe_answer(cb,"در حال پردازش است.");return
 try:
  async with economic_operation(cb.from_user.id,f"dwp-{op}:{cb.id}"):
   async with async_session() as s:ok,msg=await (PS.upgrade_hideout(s,cb.from_user.id) if op=="upgrade" else PS.buy_forged_id(s,cb.from_user.id))
 except (BusyOperation,DuplicateOperation):await safe_answer(cb,"این خرید قبلاً ثبت شده است.",show_alert=True);return
 await safe_answer(cb,msg[:180],show_alert=not ok)
 if ok:await pursuit_hub(cb)

@router.callback_query(F.data.startswith("dwp:escape"))
async def escape_hub(cb):
 if not await ensure_owner(cb):return
 text="🗺️ <b>سه راه خروج</b>\n\n🗝️ تونل: ۱۴۰م پول، شانس بالا، کاهش Heat متوسط\n📄 جعل حکم: ۴۵م + ۴ اطلاعات، کاهش Heat خوب\n💥 شورش: رایگان، شانس کم و شکست بسیار پرهزینه\n\nانتخاب به منابع و تحمل ریسک تو بستگی دارد."
 await safe_show(cb.message,text,escape_menu(cb.from_user.id));await safe_answer(cb)

@router.callback_query(F.data.startswith("dwp:break:"))
async def break_out(cb):
 if not await ensure_owner(cb):return
 key=_base(cb).split(":")[2]
 try:
  async with economic_operation(cb.from_user.id,f"dwp-break:{cb.id}"):
   async with async_session() as s:ok,msg,p=await PS.escape_prison(s,cb.from_user.id,key)
 except (BusyOperation,DuplicateOperation):await safe_answer(cb,"این نقشه قبلاً اجرا شده است.",show_alert=True);return
 if not ok:await safe_answer(cb,msg,show_alert=True);return
 text=("✅ <b>فرار موفق شد.</b>" if p["success"] else "❌ <b>فرار شکست خورد؛ ۱۰ دقیقه به حکم اضافه شد.</b>")+f"\n\nنقشه: {p['plan']['name']}\nشانس: {p['chance']:.2f}٪ · رول {p['roll']:.2f}\nHeat: {p['heat']}/100"
 await safe_show(cb.message,text,pursuit_menu(cb.from_user.id,False,False,not p["success"]));await safe_answer(cb,"نتیجه ثبت شد")

@router.callback_query(F.data.startswith("dwp:noid"))
async def no_id(cb):
 if await ensure_owner(cb):await safe_answer(cb,"اول یک هویت جعلی بخر.",show_alert=True)
