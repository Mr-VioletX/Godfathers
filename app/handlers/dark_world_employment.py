# -*- coding: utf-8 -*-
from aiogram import F,Router
from aiogram.types import CallbackQuery
from app.database.engine import async_session
from app.data import dark_world_employment as E
from app.keyboards.dark_world_employment_menu import hub,jobs,payments,publish,list_contracts,detail,plans
from app.services import dark_world_employment_service as ES
from app.services.operation_guard import BusyOperation,DuplicateOperation,economic_operation
from app.utils.ui import click_debounce,ensure_owner,safe_answer,safe_show,split_owner
router=Router(name="dark_world_employment")
def base(cb):return split_owner(cb.data or "")[0]
def hub_text(rep):return f"🤝 <b>بازار کار دنیای سیاه</b>\n<i>کار واقعی بازیکن‌به‌بازیکن؛ بدون رمز، session یا کنترل حساب دیگران.</i>\n\n⭐ اعتماد: <b>{int(rep.trust or 50)}/100</b>\n🧑‍💼 قرارداد کارفرمایی: {int(rep.contracts_as_employer or 0)}\n🧑‍🔧 قرارداد کاری: {int(rep.contracts_as_worker or 0)}\n✅ موفق/ناموفق: {int(rep.successes or 0)}/{int(rep.failures or 0)}\n💵 درآمد کاری: {int(rep.amount_earned or 0):,}\n⚖️ اختلاف‌ها: {int(rep.disputes or 0)}\n\nتمام بودجه پیش از انتشار در escrow قفل و نتیجه فقط از اکشن سرور تسویه می‌شود."
def ctext(c):
 j=E.JOBS[c.job_key];p=E.PAYMENTS[c.payment_key];cond=E.CONDITIONS.get(c.condition_key,{})
 return f"📄 <b>قرارداد #{c.id}</b>\n\n{j['icon']} کار: <b>{j['name']}</b>\n💰 پرداخت: {p['name']}\n📌 وضعیت: <b>{c.status}</b>\n👤 کارفرما: <code>{c.employer_id}</code>\n🧑‍🔧 مجری: <code>{c.worker_id or 'هنوز انتخاب نشده'}</code>\n🎚️ حداقل لول/اعتماد: {c.min_level}/{c.min_trust}\n💵 دستمزد ثابت: {c.fixed_wage:,}\n🏆 پاداش موفقیت: {c.success_bonus:,}\n📊 سهم غنیمت: {c.share_pct}٪\n🔒 کل escrow: {c.escrow_total:,}\n⏳ مهلت: {c.expires_at:%Y-%m-%d %H:%M}\n"+(f"\n🛰️ گزارش میدان: {cond.get('clue','')}" if c.status in ('in_progress','submitted','disputed','completed','failed') else "")
@router.callback_query(F.data.startswith("dwe:hub"))
async def market_hub(cb):
 if not await ensure_owner(cb):return
 async with async_session() as s:r=await ES.rep(s,cb.from_user.id);await s.commit()
 await safe_show(cb.message,hub_text(r),hub(cb.from_user.id));await safe_answer(cb)
@router.callback_query(F.data.startswith("dwe:new"))
async def new(cb):
 if await ensure_owner(cb):await safe_show(cb.message,"➕ <b>نوع کار سرورمحور را انتخاب کن</b>\n\nچهار کار واقعی روی Intel، حمل مالی، Heat یا استحکام مخفیگاه اثر می‌گذارند.",jobs(cb.from_user.id));await safe_answer(cb)
@router.callback_query(F.data.startswith("dwe:job:"))
async def job(cb):
 if not await ensure_owner(cb):return
 k=base(cb).split(":")[2];j=E.job(k)
 if not j:return await safe_answer(cb,"کار نامعتبر است.",show_alert=True)
 await safe_show(cb.message,f"{j['icon']} <b>{j['name']}</b>\n{j['description']}\n\nحداقل لول مجری: {j['min_level']}\nبودجه عملیات: {j['budget']:,}\n\nمدل پرداخت را انتخاب کن.",payments(k,cb.from_user.id));await safe_answer(cb)
@router.callback_query(F.data.startswith("dwe:preview:"))
async def preview(cb):
 if not await ensure_owner(cb):return
 _,_,jobk,pay=base(cb).split(":");j=E.job(jobk);p=E.payment(pay);pack=E.package(jobk,pay)
 if not pack:return await safe_answer(cb,"انتخاب نامعتبر است.",show_alert=True)
 text=f"🧾 <b>پیش‌فاکتور قرارداد</b>\n\nکار: {j['name']}\nپرداخت: {p['name']}\nدستمزد ثابت: {pack['fixed_wage']:,}\nپاداش موفقیت: {pack['success_bonus']:,}\nسهم غنیمت: {pack['share_pct']}٪\nبودجه عملیات: {pack['operation_budget']:,}\n🔒 escrow کل: <b>{pack['escrow_total']:,}</b>\nمهلت پذیرش و اجرا: {E.CONTRACT_TTL_HOURS} ساعت\n\nپس از انتشار هیچ عددی یک‌طرفه تغییر نمی‌کند."
 await safe_show(cb.message,text,publish(jobk,pay,cb.from_user.id));await safe_answer(cb)
@router.callback_query(F.data.startswith("dwe:publish:"))
async def create(cb):
 if not await ensure_owner(cb):return
 if click_debounce(cb.from_user.id,"dwe_publish",3):return await safe_answer(cb,"در حال پردازش است.")
 _,_,jobk,pay=base(cb).split(":")
 try:
  async with economic_operation(cb.from_user.id,f"dwe-publish:{cb.id}"):
   async with async_session() as s:ok,msg,c=await ES.create_contract(s,cb.from_user.id,jobk,pay)
 except (BusyOperation,DuplicateOperation):return await safe_answer(cb,"این انتشار قبلاً ثبت شده است.",show_alert=True)
 if not ok:return await safe_answer(cb,msg[:180],show_alert=True)
 await safe_show(cb.message,f"✅ {msg}\nشماره قرارداد: <b>#{c.id}</b>",hub(cb.from_user.id));await safe_answer(cb,"منتشر شد")
@router.callback_query(F.data.startswith("dwe:market"))
async def browse(cb):
 if not await ensure_owner(cb):return
 async with async_session() as s:rows=await ES.market(s,cb.from_user.id);await s.commit()
 text="🛒 <b>قراردادهای باز</b>\n\n"+("\n".join(f"#{c.id} · {E.JOBS[c.job_key]['name']} · ثابت {c.fixed_wage:,} · سهم {c.share_pct}٪" for c in rows) or "قرارداد بازی وجود ندارد.")
 await safe_show(cb.message,text,list_contracts(rows,cb.from_user.id,True));await safe_answer(cb)
@router.callback_query(F.data.startswith("dwe:mine"))
async def mine(cb):
 if not await ensure_owner(cb):return
 async with async_session() as s:rows=await ES.mine(s,cb.from_user.id);await s.commit()
 await safe_show(cb.message,"📂 <b>قراردادهای من</b>\n\n"+("\n".join(f"#{c.id} · {E.JOBS[c.job_key]['name']} · {c.status}" for c in rows) or "هنوز قراردادی نداری."),list_contracts(rows,cb.from_user.id));await safe_answer(cb)
@router.callback_query(F.data.startswith("dwe:view:"))
async def view(cb):
 if not await ensure_owner(cb):return
 cid=int(base(cb).split(":")[2])
 async with async_session() as s:c=await ES.get_contract(s,cid)
 if not c or cb.from_user.id not in (c.employer_id,c.worker_id) and c.status!="open":return await safe_answer(cb,"دسترسی نداری.",show_alert=True)
 await safe_show(cb.message,ctext(c),detail(c,cb.from_user.id,cb.from_user.id));await safe_answer(cb)
async def simple_mutation(cb,op):
 cid=int(base(cb).split(":")[2])
 try:
  async with economic_operation(cb.from_user.id,f"dwe-{op}:{cb.id}"):
   async with async_session() as s:ok,msg=await getattr(ES,op)(s,cb.from_user.id,cid)
 except (BusyOperation,DuplicateOperation):return await safe_answer(cb,"درخواست تکراری یا هم‌زمان مسدود شد.",show_alert=True)
 await safe_answer(cb,msg[:180],show_alert=not ok)
 if ok:await mine(cb)
@router.callback_query(F.data.startswith("dwe:accept:"))
async def accept(cb):
 if await ensure_owner(cb):await simple_mutation(cb,"accept")
@router.callback_query(F.data.startswith("dwe:start:"))
async def start(cb):
 if await ensure_owner(cb):await simple_mutation(cb,"start")
@router.callback_query(F.data.startswith("dwe:cancel:"))
async def cancel(cb):
 if await ensure_owner(cb):await simple_mutation(cb,"cancel")
@router.callback_query(F.data.startswith("dwe:dispute:"))
async def dispute(cb):
 if await ensure_owner(cb):await simple_mutation(cb,"dispute")
@router.callback_query(F.data.startswith("dwe:plans:"))
async def run_plans(cb):
 if not await ensure_owner(cb):return
 cid=int(base(cb).split(":")[2])
 async with async_session() as s:ok,msg,p=await ES.execution_preview(s,cb.from_user.id,cid);await s.commit()
 if not ok:return await safe_answer(cb,msg,show_alert=True)
 lines=["♟️ <b>انتخاب روش اجرا</b>","",f"🛰️ گزارش میدان: {p['condition']['clue']}","","هر روش سود، Heat و سازگاری متفاوت دارد:"]
 for k in E.APPROACH_ORDER:lines.append(f"{E.APPROACHES[k]['icon']} {E.APPROACHES[k]['name']} — برآورد {p['chances'][k]['chance']:.1f}٪")
 await safe_show(cb.message,"\n".join(lines),plans(p['contract'],p['chances'],cb.from_user.id));await safe_answer(cb)
@router.callback_query(F.data.startswith("dwe:do:"))
async def execute(cb):
 if not await ensure_owner(cb):return
 _,_,cid,approach=base(cb).split(":")
 try:
  async with economic_operation(cb.from_user.id,f"dwe-execute:{cb.id}"):
   async with async_session() as s:ok,msg,p=await ES.execute(s,cb.from_user.id,int(cid),approach)
 except (BusyOperation,DuplicateOperation):return await safe_answer(cb,"اجرای تکراری مسدود شد.",show_alert=True)
 if not ok:return await safe_answer(cb,msg,show_alert=True)
 text=("✅ <b>کار موفق شد.</b>" if p['success'] else "❌ <b>کار ناموفق بود.</b>")+f"\n\nغنیمت ثبت‌شده: {p['loot']:,}\nاثر مأموریت: {p['effect']:+d}\nشانس: {p['chance']:.2f}٪ · رول {p['roll']:.2f}"+(p.get('team_note') or '')
 await safe_show(cb.message,text,hub(cb.from_user.id));await safe_answer(cb,"برای تسویه آماده شد")
@router.callback_query(F.data.startswith("dwe:settle:"))
async def settle(cb):
 if not await ensure_owner(cb):return
 cid=int(base(cb).split(":")[2])
 try:
  async with economic_operation(cb.from_user.id,f"dwe-settle:{cb.id}"):
   async with async_session() as s:ok,msg,p=await ES.settle(s,cb.from_user.id,cid)
 except (BusyOperation,DuplicateOperation):return await safe_answer(cb,"تسویه تکراری مسدود شد.",show_alert=True)
 if not ok:return await safe_answer(cb,msg,show_alert=True)
 await safe_show(cb.message,f"💳 <b>تسویه کامل شد</b>\n\nپرداخت کارگر: {p['worker']:,}\nبازگشت/سهم کارفرما: {p['employer']:,}\nسهم غنیمت کارگر: {p['worker_share']:,}",hub(cb.from_user.id));await safe_answer(cb,"تسویه شد")
@router.callback_query(F.data.startswith("dwe:rep"))
async def reputation(cb):
 if await ensure_owner(cb):await market_hub(cb)
