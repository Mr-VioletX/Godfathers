# -*- coding: utf-8 -*-
from aiogram import F,Router
from aiogram.types import CallbackQuery
from app.database.engine import async_session
from app.data import dark_world_smuggling as S
from app.keyboards.dark_world_smuggling_menu import hub,stock,goods,qty,packs,routes,dests,start,market,offers,sellgoods
from app.services import dark_world_smuggling_service as SS
from app.services.operation_guard import BusyOperation,DuplicateOperation,economic_operation
from app.utils.ui import click_debounce,ensure_owner,safe_answer,safe_show,split_owner
router=Router(name="dark_world_smuggling")
def base(c):return split_owner(c.data or "")[0]
async def show_hub(c):
 async with async_session() as s:ok,msg,x=await SS.snapshot(s,c.from_user.id);await s.commit()
 if not ok:return await safe_answer(c,msg,show_alert=True)
 a=x['active'];remain=max(0,int((a.ready_at-SS.now()).total_seconds())) if a else 0;inv=" · ".join(f"{S.GOODS[k]['icon']}{q}" for k,q in x['inventory'].items() if q) or "خالی"
 text=f"🚚 <b>زنجیره قاچاق</b>\n<i>خرید، انبار، بسته‌بندی، مسیر و مقصد؛ بازار کاربران کاملاً اختیاری است.</i>\n\n🏚️ انبار: سطح {x['profile'].warehouse_level} · {x['used']}/{x['capacity']}\n📦 موجودی: {inv}\n🚨 Heat: {int(x['dark'].heat or 0)}/100\n📈 مقصد داغ امروز: {S.DESTINATIONS[S.demand_destination()]['name']}\n🎯 محموله: {('آماده دریافت' if remain<=0 else str(remain//60+1)+' دقیقه مانده') if a else 'نداری'}"
 await safe_show(c.message,text,hub(c.from_user.id,bool(a),bool(a and remain<=0)));await safe_answer(c)
@router.callback_query(F.data.startswith("smg:hub"))
async def h(c):
 if await ensure_owner(c):await show_hub(c)
@router.callback_query(F.data.startswith("smg:stock"))
async def st(c):
 if await ensure_owner(c):await safe_show(c.message,"📦 <b>خرید مستقیم از تأمین‌کننده سیستم</b>\n\nاین مسیر همیشه فعال است؛ استفاده از بازار کاربران اجباری نیست.",stock(c.from_user.id));await safe_answer(c)
@router.callback_query(F.data.startswith("smg:buy:"))
async def buy(c):
 if not await ensure_owner(c):return
 _,_,g,q=base(c).split(":")
 try:
  async with economic_operation(c.from_user.id,f"smg-buy:{c.id}"):
   async with async_session() as s:ok,msg=await SS.buy_system(s,c.from_user.id,g,int(q))
 except (BusyOperation,DuplicateOperation):return await safe_answer(c,"خرید تکراری مسدود شد.",show_alert=True)
 await safe_answer(c,msg[:180],show_alert=not ok)
 if ok:await show_hub(c)
@router.callback_query(F.data.startswith("smg:goods"))
async def gs(c):
 if not await ensure_owner(c):return
 async with async_session() as s:i=await SS.inventory(s,c.from_user.id)
 await safe_show(c.message,"🚚 <b>کالای محموله را انتخاب کن</b>",goods(i,c.from_user.id));await safe_answer(c)
@router.callback_query(F.data.startswith("smg:qty:"))
async def qs(c):
 if not await ensure_owner(c):return
 g=base(c).split(":")[2]
 async with async_session() as s:i=await SS.inventory(s,c.from_user.id)
 await safe_show(c.message,"تعداد محموله را انتخاب کن.",qty(g,int(i.get(g,0)),c.from_user.id));await safe_answer(c)
@router.callback_query(F.data.startswith("smg:pack:"))
async def pk(c):
 if not await ensure_owner(c):return
 _,_,g,q=base(c).split(":");await safe_show(c.message,"📦 بسته‌بندی روی ظرفیت، شانس، کیفیت و Heat اثر دارد.",packs(g,q,c.from_user.id));await safe_answer(c)
@router.callback_query(F.data.startswith("smg:route:"))
async def rt(c):
 if not await ensure_owner(c):return
 _,_,g,q,p=base(c).split(":");await safe_show(c.message,"🗺️ مسیر امن سود کمتر دارد؛ شاهراه قرمز سریع‌تر و پردرآمدتر اما خطرناک‌تر است.",routes(g,q,p,c.from_user.id));await safe_answer(c)
@router.callback_query(F.data.startswith("smg:dest:"))
async def ds(c):
 if not await ensure_owner(c):return
 _,_,g,q,p,r=base(c).split(":");await safe_show(c.message,"🌍 مقصد را با نوع کالا و مقصد داغ امروز مقایسه کن.",dests(g,q,p,r,c.from_user.id));await safe_answer(c)
@router.callback_query(F.data.startswith("smg:prev:"))
async def prev(c):
 if not await ensure_owner(c):return
 _,_,g,q,p,r,d=base(c).split(":")
 async with async_session() as s:ok,msg,x=await SS.preview(s,c.from_user.id,g,int(q),p,r,d);await s.commit()
 if not x:return await safe_answer(c,msg,show_alert=True)
 text=f"🧾 <b>طرح محموله</b>\n\nکالا: {S.GOODS[g]['name']} ×{q}\nبسته‌بندی: {S.PACKS[p]['name']}\nمسیر: {S.ROUTES[r]['name']}\nمقصد: {S.DESTINATIONS[d]['name']}\n🎲 شانس: {x['chance']:.2f}٪\n💵 فروش موفق: {x['payout']:,}\n💳 بسته‌بندی: {x['pack_cost']:,}\n🚨 Heat: +{x['heat']}\n⏱️ زمان: {x['duration']//60} دقیقه"
 await safe_show(c.message,text,start(x,c.from_user.id) if ok else goods({},c.from_user.id));await safe_answer(c,msg if not ok else "")
@router.callback_query(F.data.startswith("smg:start:"))
async def go(c):
 if not await ensure_owner(c):return
 _,_,g,q,p,r,d=base(c).split(":")
 try:
  async with economic_operation(c.from_user.id,f"smg-start:{c.id}"):
   async with async_session() as s:ok,msg=await SS.start_shipment(s,c.from_user.id,g,int(q),p,r,d)
 except (BusyOperation,DuplicateOperation):return await safe_answer(c,"ارسال تکراری مسدود شد.",show_alert=True)
 await safe_answer(c,msg[:180],show_alert=not ok)
 if ok:await show_hub(c)
@router.callback_query(F.data.startswith("smg:active"))
async def active(c):
 if not await ensure_owner(c):return
 try:
  async with economic_operation(c.from_user.id,f"smg-collect:{c.id}"):
   async with async_session() as s:ok,msg=await SS.collect(s,c.from_user.id)
 except (BusyOperation,DuplicateOperation):return await safe_answer(c,"دریافت تکراری مسدود شد.",show_alert=True)
 await safe_answer(c,msg[:180],show_alert=not ok)
 if ok:await safe_show(c.message,msg,hub(c.from_user.id));await safe_answer(c)
 else:await show_hub(c)
@router.callback_query(F.data.startswith("smg:upgrade"))
async def up(c):
 if not await ensure_owner(c):return
 try:
  async with economic_operation(c.from_user.id,f"smg-upgrade:{c.id}"):
   async with async_session() as s:ok,msg=await SS.upgrade(s,c.from_user.id)
 except (BusyOperation,DuplicateOperation):return await safe_answer(c,"ارتقای تکراری مسدود شد.",show_alert=True)
 await safe_answer(c,msg[:180],show_alert=not ok)
 if ok:await show_hub(c)
@router.callback_query(F.data.startswith("smg:market"))
async def mk(c):
 if await ensure_owner(c):await safe_show(c.message,"🤝 <b>بازار کمکی کاربران</b>\n\nاختیاری است؛ می‌توانی کالا را مستقیم از سیستم بخری. قیمت مرجع از عرضه فعال و معاملات ۲۴ ساعت اخیر محاسبه می‌شود.",market(c.from_user.id));await safe_answer(c)
@router.callback_query(F.data.startswith("smg:pulse"))
async def pulse(c):
 if not await ensure_owner(c):return
 async with async_session() as s:x=await SS.pulse(s);await s.commit()
 lines=["📊 <b>نبض عرضه و تقاضا</b>",""]+[f"{S.GOODS[k]['icon']} {S.GOODS[k]['name']}: {v['label']} · عرضه {v['supply']} · تقاضا {v['demand']} · مرجع {v['reference']:,}" for k,v in x.items()]
 await safe_show(c.message,"\n".join(lines),market(c.from_user.id));await safe_answer(c)
@router.callback_query(F.data.startswith("smg:offers"))
async def ofs(c):
 if not await ensure_owner(c):return
 async with async_session() as s:x=await SS.offers(s,c.from_user.id);await s.commit()
 await safe_show(c.message,"🛒 <b>عرضه‌های کاربران</b>\nهر دکمه یک واحد می‌خرد؛ کارمزد ۲٪ از فروشنده کم می‌شود.",offers(x,c.from_user.id));await safe_answer(c)
@router.callback_query(F.data.startswith("smg:sellgoods"))
async def sg(c):
 if not await ensure_owner(c):return
 async with async_session() as s:i=await SS.inventory(s,c.from_user.id)
 await safe_show(c.message,"➕ <b>عرضه کالا</b>\nقیمت منصفانه لحظه ثبت از نبض بازار محاسبه می‌شود.",sellgoods(i,c.from_user.id));await safe_answer(c)
@router.callback_query(F.data.startswith("smg:list:"))
async def li(c):
 if not await ensure_owner(c):return
 _,_,g,q,t=base(c).split(":")
 try:
  async with economic_operation(c.from_user.id,f"smg-list:{c.id}"):
   async with async_session() as s:ok,msg,_=await SS.list_offer(s,c.from_user.id,g,int(q),t)
 except (BusyOperation,DuplicateOperation):return await safe_answer(c,"عرضه تکراری مسدود شد.",show_alert=True)
 await safe_answer(c,msg[:180],show_alert=not ok)
 if ok:await mk(c)
@router.callback_query(F.data.startswith("smg:take:"))
async def take(c):
 if not await ensure_owner(c):return
 _,_,oid,q=base(c).split(":")
 try:
  async with economic_operation(c.from_user.id,f"smg-take:{c.id}"):
   async with async_session() as s:ok,msg=await SS.buy_offer(s,c.from_user.id,int(oid),int(q))
 except (BusyOperation,DuplicateOperation):return await safe_answer(c,"معامله تکراری مسدود شد.",show_alert=True)
 await safe_answer(c,msg[:180],show_alert=not ok)
 if ok:await ofs(c)
@router.callback_query(F.data.startswith("smg:none"))
async def none(c):
 if await ensure_owner(c):await safe_answer(c,"موجودی کافی نیست.",show_alert=True)
