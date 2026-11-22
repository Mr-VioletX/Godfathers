# -*- coding: utf-8 -*-
from aiogram import F,Router
from app.database.engine import async_session
from app.data import dark_world_recipes as R
from app.keyboards.dark_world_recipes_menu import hub,garden,market,market_group,bases,catalysts,signatures,brands,recipes,modes,inventory
from app.services import dark_world_recipes_service as RS
from app.services.operation_guard import BusyOperation,DuplicateOperation,economic_operation
from app.utils.ui import ensure_owner,safe_answer,safe_show,split_owner
router=Router(name="dark_world_recipes")
def base(c):return split_owner(c.data or "")[0]
async def show(c):
 async with async_session() as s:ok,msg,x=await RS.snapshot(s,c.from_user.id)
 if not ok:return await safe_answer(c,msg,show_alert=True)
 a=x['active'];rem=max(0,int((a.ready_at-RS.now()).total_seconds())) if a else 0;ings=' · '.join(f"{R.ingredient(k)['icon']}{v}" for k,v in x['ingredients'].items() if v) or 'خالی'
 text=f"🧬 <b>گلخانه و موتور فرمول‌های داستانی</b>\n<i>۱۲۵ ترکیب کاملاً خیالی؛ بدون ماده یا دستور واقعی.</i>\n\n🌱 قطعه‌ها: {len(x['crops'])}/{R.PLOT_LIMIT}\n🧱 مواد: {ings}\n📓 فرمول‌های کشف‌شده: {len(x['recipes'])}/125\n🎒 محصولات ترکیبی: {sum(int(i.qty) for i in x['inventory'])}\n📈 امضای پرتقاضا: {R.SIGNATURES[R.demand_signature()]['name']}\n⏳ تولید: {('آماده دریافت' if rem<=0 else str(rem//60+1)+' دقیقه مانده') if a else 'نداری'}"
 await safe_show(c.message,text,hub(c.from_user.id,bool(a),bool(a and rem<=0)));await safe_answer(c)
@router.callback_query(F.data.startswith("dwx:hub"))
async def h(c):
 if await ensure_owner(c):await show(c)
@router.callback_query(F.data.startswith("dwx:garden"))
async def gd(c):
 if not await ensure_owner(c):return
 async with async_session() as s:rows=await RS.growing(s,c.from_user.id)
 lines=["🌱 <b>گلخانه مواد داستانی</b>","بذر از بازار سیاه تهیه می‌شود؛ کشت ارزان‌تر از خرید مستقیم است.",""]+[f"قطعه {x.slot_no}: {R.BASES[x.base_key]['name']} · {'آماده' if x.ready_at<=RS.now() else str(int((x.ready_at-RS.now()).total_seconds())//60+1)+' دقیقه'}" for x in rows];await safe_show(c.message,"\n".join(lines),garden(rows,c.from_user.id));await safe_answer(c)
@router.callback_query(F.data.startswith("dwx:plant:"))
async def plant(c):
 if not await ensure_owner(c):return
 key=base(c).split(":")[2]
 async with economic_operation(c.from_user.id,f"dwx-plant:{c.id}"):
  async with async_session() as s:ok,msg=await RS.plant(s,c.from_user.id,key)
 await safe_answer(c,msg,show_alert=not ok)
 if ok:await gd(c)
@router.callback_query(F.data.startswith("dwx:harvest:"))
async def harvest(c):
 if not await ensure_owner(c):return
 pid=int(base(c).split(":")[2])
 async with economic_operation(c.from_user.id,f"dwx-harvest:{c.id}"):
  async with async_session() as s:ok,msg=await RS.harvest(s,c.from_user.id,pid)
 await safe_answer(c,msg,show_alert=not ok)
 if ok:await gd(c)
@router.callback_query(F.data.startswith("dwx:market"))
async def mk(c):
 if await ensure_owner(c):
  parts=base(c).split(":");group=parts[2] if len(parts)>2 else None
  await safe_show(c.message,"🕶️ <b>بازار مواد اولیه خیالی</b>\nیک دسته را انتخاب کن." if not group else "مواد این دسته را انتخاب کن.",market_group(group,c.from_user.id) if group else market(c.from_user.id));await safe_answer(c)
@router.callback_query(F.data.startswith("dwx:buy:"))
async def buy(c):
 if not await ensure_owner(c):return
 parts=base(c).split(":");key=parts[2];group=parts[3] if len(parts)>3 else None
 async with economic_operation(c.from_user.id,f"dwx-buy:{c.id}"):
  async with async_session() as s:ok,msg=await RS.buy(s,c.from_user.id,key)
 await safe_answer(c,msg,show_alert=not ok)
 if ok:await safe_show(c.message,"مواد این دسته را انتخاب کن.",market_group(group,c.from_user.id) if group else market(c.from_user.id))
@router.callback_query(F.data.startswith("dwx:bases"))
async def bs(c):
 if await ensure_owner(c):await safe_show(c.message,"🧩 پایه خیالی فرمول را انتخاب کن.",bases(c.from_user.id));await safe_answer(c)
@router.callback_query(F.data.startswith("dwx:cats:"))
async def cats(c):
 if not await ensure_owner(c):return
 b=base(c).split(":")[2];await safe_show(c.message,"عامل خیالی دوم را انتخاب کن.",catalysts(b,c.from_user.id));await safe_answer(c)
@router.callback_query(F.data.startswith("dwx:sigs:"))
async def sigs(c):
 if not await ensure_owner(c):return
 _,_,b,k=base(c).split(":");await safe_show(c.message,"امضای خیالی سوم را انتخاب کن.",signatures(b,k,c.from_user.id));await safe_answer(c)
@router.callback_query(F.data.startswith("dwx:brands:"))
async def br(c):
 if not await ensure_owner(c):return
 _,_,b,k,s=base(c).split(":");await safe_show(c.message,"سبک نام‌گذاری محصول را انتخاب کن.",brands(b,k,s,c.from_user.id));await safe_answer(c)
@router.callback_query(F.data.startswith("dwx:discover:"))
async def discover(c):
 if not await ensure_owner(c):return
 _,_,b,k,s,n=base(c).split(":")
 async with economic_operation(c.from_user.id,f"dwx-discover:{c.id}"):
  async with async_session() as db:ok,msg,row=await RS.discover(db,c.from_user.id,b,k,s,n)
 await safe_answer(c,msg[:180],show_alert=not ok)
 if ok:await show(c)
@router.callback_query(F.data.startswith("dwx:recipes"))
async def rc(c):
 if not await ensure_owner(c):return
 async with async_session() as s:rows=await RS.recipes(s,c.from_user.id)
 page=int(base(c).split(":")[2]) if len(base(c).split(":"))>2 else 0
 await safe_show(c.message,"📓 <b>فرمول‌های کشف‌شده</b>\nهر فرمول از سه جزء خیالی ساخته شده و ویژگی‌های منحصربه‌فرد دارد.",recipes(rows,c.from_user.id,page));await safe_answer(c)
@router.callback_query(F.data.startswith("dwx:modes:"))
async def mode(c):
 if not await ensure_owner(c):return
 rid=int(base(c).split(":")[2]);await safe_show(c.message,"چرخه تولید را انتخاب کن؛ هر بار دو واحد از هر جزء مصرف می‌شود.",modes(rid,c.from_user.id));await safe_answer(c)
@router.callback_query(F.data.startswith("dwx:start:"))
async def start(c):
 if not await ensure_owner(c):return
 _,_,rid,m=base(c).split(":")
 async with economic_operation(c.from_user.id,f"dwx-start:{c.id}"):
  async with async_session() as s:ok,msg=await RS.start(s,c.from_user.id,int(rid),m)
 await safe_answer(c,msg[:180],show_alert=not ok)
 if ok:await show(c)
@router.callback_query(F.data.startswith("dwx:active"))
async def collect(c):
 if not await ensure_owner(c):return
 async with economic_operation(c.from_user.id,f"dwx-collect:{c.id}"):
  async with async_session() as s:ok,msg=await RS.collect(s,c.from_user.id)
 await safe_answer(c,msg[:180],show_alert=not ok)
 if ok:await safe_show(c.message,msg,hub(c.from_user.id));await safe_answer(c)
 else:await show(c)
@router.callback_query(F.data.startswith("dwx:inventory"))
async def inv(c):
 if not await ensure_owner(c):return
 async with async_session() as s:rows=await RS.inventory(s,c.from_user.id);forms={r.id:r for r in await RS.recipes(s,c.from_user.id)}
 lines=["🎒 <b>محصولات ترکیبی</b>",""]+[f"{forms[x.recipe_id].custom_name} ×{x.qty} · کیفیت {x.avg_quality} · قدرت {x.avg_power} · پایداری {x.avg_stability}" for x in rows if x.recipe_id in forms];await safe_show(c.message,"\n".join(lines),inventory(rows,c.from_user.id));await safe_answer(c)
@router.callback_query(F.data.startswith("dwx:sell:"))
async def sell(c):
 if not await ensure_owner(c):return
 rid=int(base(c).split(":")[2])
 async with economic_operation(c.from_user.id,f"dwx-sell:{c.id}"):
  async with async_session() as s:ok,msg=await RS.sell(s,c.from_user.id,rid)
 await safe_answer(c,msg,show_alert=not ok)
 if ok:await inv(c)

@router.callback_query(F.data.startswith("dwx:none"))
async def none(c):
 if await ensure_owner(c):await safe_answer(c)
