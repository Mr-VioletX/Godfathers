# -*- coding: utf-8 -*-
from aiogram import F,Router
from aiogram.types import CallbackQuery
from app.database.engine import async_session
from app.data import dark_world_npcs as N
from app.keyboards.dark_world_npc_menu import npc_hub_menu,team_menu,tactics_menu,back
from app.services import dark_world_npc_service as NS
from app.services.operation_guard import BusyOperation,DuplicateOperation,economic_operation
from app.utils.ui import click_debounce,ensure_owner,safe_answer,safe_show,split_owner
router=Router(name="dark_world_npcs")
def base(cb):return split_owner(cb.data or "")[0]
def text(s):
 a=s["analysis"];lines=["👥 <b>شبکه پیشرفته NPC</b>","<i>سه نفر انتخاب کن؛ کلاس، آمادگی و تاکتیک روی نتیجه واقعی عملیات اثر دارد.</i>","",f"🧩 تیم فعال: <b>{len(s['selected'])}/{N.TEAM_SIZE}</b>",f"🎭 تاکتیک: <b>{a['tactic']['name']}</b>",f"📈 کارایی تیم: <b>{a['effectiveness']*100:.0f}٪</b>",f"🧠 هم‌افزایی تنوع کلاس: +{a['diversity_bonus']*100:.0f}٪",f"🩺 پزشک فعال: {'بله' if a['medic'] else 'خیر'}",""]
 for r in s["rows"]:
  status="آماده" if r["available"] else "غیرفعال";sel="✅" if r["key"] in s["selected"] else "▫️";due=" · حقوق عقب‌افتاده" if r["wage_due"] else ""
  lines.append(f"{sel} <b>{r['display']['class_name']}</b> · L{r['level']} · وفاداری {r['loyalty']} · خستگی {r['fatigue']} · {status}{due}")
 if not s["rows"]:lines.append("هنوز NPC استخدام نکرده‌ای.")
 return "\n".join(lines)
async def show(cb):
 async with async_session() as sess:ok,msg,s=await NS.snapshot(sess,cb.from_user.id);await sess.commit()
 if not ok:await safe_answer(cb,msg,show_alert=True);return
 await safe_show(cb.message,text(s),npc_hub_menu(cb.from_user.id));await safe_answer(cb)
@router.callback_query(F.data.startswith("dwn:hub"))
async def hub(cb):
 if await ensure_owner(cb):await show(cb)
@router.callback_query(F.data.startswith("dwn:team"))
async def team(cb):
 if not await ensure_owner(cb):return
 async with async_session() as sess:ok,msg,s=await NS.snapshot(sess,cb.from_user.id);await sess.commit()
 if not ok:return await safe_answer(cb,msg,show_alert=True)
 await safe_show(cb.message,"🧩 <b>چیدن تیم سه‌نفره</b>\n\nتنوع کلاس هم‌افزایی می‌دهد. نیروی مصدوم، خسته در استراحت، درحال تمرین یا جداشده قابل انتخاب نیست.",team_menu(s["rows"],s["selected"],cb.from_user.id));await safe_answer(cb)
@router.callback_query(F.data.startswith("dwn:tactics"))
async def tactics(cb):
 if not await ensure_owner(cb):return
 async with async_session() as sess:team=await NS.get_team(sess,cb.from_user.id);await sess.commit()
 lines=["🎭 <b>تاکتیک تیم</b>",""]+[f"{v['icon']} <b>{v['name']}</b> — {v['description']}" for v in N.TACTICS.values()]
 await safe_show(cb.message,"\n".join(lines),tactics_menu(team.tactic_key,cb.from_user.id));await safe_answer(cb)
@router.callback_query(F.data.startswith("dwn:toggle:"))
@router.callback_query(F.data.startswith("dwn:tactic:"))
@router.callback_query(F.data.startswith("dwn:train:"))
@router.callback_query(F.data.startswith("dwn:return:"))
@router.callback_query(F.data.startswith("dwn:wages"))
@router.callback_query(F.data.startswith("dwn:rest"))
async def mutate(cb:CallbackQuery):
 if not await ensure_owner(cb):return
 if click_debounce(cb.from_user.id,"dwn_mutate",2.5):await safe_answer(cb,"در حال پردازش است.");return
 parts=base(cb).split(":");op=parts[1];key=parts[2] if len(parts)>2 else ""
 try:
  async with economic_operation(cb.from_user.id,f"dwn-{op}:{cb.id}"):
   async with async_session() as sess:
    if op=="toggle":ok,msg=await NS.toggle_member(sess,cb.from_user.id,key)
    elif op=="tactic":ok,msg=await NS.set_tactic(sess,cb.from_user.id,key)
    elif op=="train":ok,msg=await NS.train(sess,cb.from_user.id,key)
    elif op=="return":ok,msg=await NS.return_deserter(sess,cb.from_user.id,key)
    elif op=="wages":ok,msg=await NS.pay_wages(sess,cb.from_user.id)
    else:ok,msg=await NS.rest_team(sess,cb.from_user.id)
 except (BusyOperation,DuplicateOperation):await safe_answer(cb,"این درخواست قبلاً ثبت شده است.",show_alert=True);return
 await safe_answer(cb,msg[:180],show_alert=not ok)
 if ok:await show(cb)
@router.callback_query(F.data.startswith("dwn:blocked"))
async def blocked(cb):
 if await ensure_owner(cb):await safe_answer(cb,"این نیرو فعلاً آماده نیست.",show_alert=True)
