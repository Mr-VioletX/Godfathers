# -*- coding: utf-8 -*-
"""Fictional-only cultivation and combinatorial recipe gameplay."""
from __future__ import annotations
import secrets
from datetime import datetime,timedelta
from sqlalchemy import select
from app.data import dark_world_recipes as R
from app.data import dark_world_laboratory as L
from app.models.dark_world import DarkWorldIngredientInventory,DarkWorldCropPlot,DarkWorldCustomRecipe,DarkWorldCustomBatch,DarkWorldCustomInventory,DarkWorldCustomSale
from app.services import dark_world_service as DS
from app.services import dark_world_laboratory_service as LS

def now():return datetime.utcnow()
async def ingredient_row(session,uid,key,create=False):
 x=(await session.execute(select(DarkWorldIngredientInventory).where(DarkWorldIngredientInventory.owner_id==int(uid),DarkWorldIngredientInventory.ingredient_key==key))).scalar_one_or_none()
 if x is None and create:x=DarkWorldIngredientInventory(owner_id=int(uid),ingredient_key=key,qty=0);session.add(x);await session.flush()
 return x
async def ingredients(session,uid):return {x.ingredient_key:int(x.qty or 0) for x in (await session.execute(select(DarkWorldIngredientInventory).where(DarkWorldIngredientInventory.owner_id==int(uid)))).scalars()}
async def crops(session,uid):return list((await session.execute(select(DarkWorldCropPlot).where(DarkWorldCropPlot.owner_id==int(uid)).order_by(DarkWorldCropPlot.id.desc()).limit(20))).scalars())
async def growing(session,uid):return list((await session.execute(select(DarkWorldCropPlot).where(DarkWorldCropPlot.owner_id==int(uid),DarkWorldCropPlot.status=="growing").order_by(DarkWorldCropPlot.slot_no))).scalars())
async def recipes(session,uid):return list((await session.execute(select(DarkWorldCustomRecipe).where(DarkWorldCustomRecipe.owner_id==int(uid)).order_by(DarkWorldCustomRecipe.id.desc()).limit(30))).scalars())
async def inventory(session,uid):return list((await session.execute(select(DarkWorldCustomInventory).where(DarkWorldCustomInventory.owner_id==int(uid),DarkWorldCustomInventory.qty>0).order_by(DarkWorldCustomInventory.recipe_id))).scalars())
async def active(session,uid):return (await session.execute(select(DarkWorldCustomBatch).where(DarkWorldCustomBatch.owner_id==int(uid),DarkWorldCustomBatch.status=="active").order_by(DarkWorldCustomBatch.id.desc()))).scalar_one_or_none()
async def snapshot(session,uid):
 player=await DS.get_player(session,uid);blocked=DS.access_message(player)
 if blocked:return False,blocked,{}
 return True,"ok",{"ingredients":await ingredients(session,uid),"crops":await growing(session,uid),"recipes":await recipes(session,uid),"inventory":await inventory(session,uid),"active":await active(session,uid),"lab":await LS.lab(session,uid)}
async def buy(session,uid,key):
 item=R.ingredient(key)
 if not item:return False,"جزء داستانی نامعتبر است."
 from app.services import dark_world_finance_service as FS
 wallet=await FS.account(session,uid);cost=R.market_price(key)*R.INGREDIENT_PACK
 if int(wallet.dirty_balance or 0)<cost:return False,f"برای خرید {cost:,} پول کثیف لازم است."
 wallet.dirty_balance=int(wallet.dirty_balance or 0)-cost;row=await ingredient_row(session,uid,key,True);row.qty=int(row.qty or 0)+R.INGREDIENT_PACK;await session.commit();return True,f"{R.INGREDIENT_PACK} واحد {item['name']} از بازار سیاه خریداری شد."
async def plant(session,uid,key):
 item=R.BASES.get(key)
 if not item:return False,"بذر داستانی نامعتبر است."
 rows=await growing(session,uid)
 if len(rows)>=R.PLOT_LIMIT:return False,"هر سه قطعه گلخانه پر هستند."
 from app.services import dark_world_finance_service as FS
 wallet=await FS.account(session,uid)
 if int(wallet.dirty_balance or 0)<int(item['seed']):return False,"پول کثیف کافی برای بذر بازار سیاه نداری."
 used={int(x.slot_no) for x in rows};slot=next(i for i in range(1,R.PLOT_LIMIT+1) if i not in used);wallet.dirty_balance=int(wallet.dirty_balance or 0)-int(item['seed']);t=now();session.add(DarkWorldCropPlot(owner_id=int(uid),slot_no=slot,base_key=key,status="growing",yield_qty=int(item['yield']),planted_at=t,ready_at=t+timedelta(seconds=int(item['grow']))));await session.commit();return True,f"{item['name']} در قطعه {slot} کاشته شد؛ برداشت حدود {item['grow']//60} دقیقه دیگر."
async def harvest(session,uid,plot_id):
 x=await session.get(DarkWorldCropPlot,int(plot_id))
 if not x or int(x.owner_id)!=int(uid) or x.status!="growing":return False,"قطعه قابل برداشت نیست."
 if x.ready_at>now():return False,f"هنوز {int((x.ready_at-now()).total_seconds())//60+1} دقیقه مانده."
 row=await ingredient_row(session,uid,x.base_key,True);row.qty=int(row.qty or 0)+int(x.yield_qty);x.status="harvested";x.harvested_at=now();await session.commit();return True,f"{x.yield_qty} واحد {R.BASES[x.base_key]['name']} برداشت شد."
async def discover(session,uid,base,cat,sig,brand):
 if base not in R.BASES or cat not in R.CATALYSTS or sig not in R.SIGNATURES or brand not in R.BRANDS:return False,"ترکیب نامعتبر است.",None
 spec=R.formula(base,cat,sig,brand);old=(await session.execute(select(DarkWorldCustomRecipe).where(DarkWorldCustomRecipe.owner_id==int(uid),DarkWorldCustomRecipe.fingerprint==spec['fingerprint']))).scalar_one_or_none()
 if old:return False,"این فرمول را قبلاً کشف کرده‌ای.",old
 inv=await ingredients(session,uid)
 for k in (base,cat,sig):
  if int(inv.get(k,0))<1:return False,f"برای آزمایش یک واحد {R.ingredient(k)['name']} لازم است.",None
 lab=await LS.lab(session,uid)
 if int(lab.level)<int(spec['required_level']):return False,f"این ترکیب به آزمایشگاه سطح {spec['required_level']} نیاز دارد.",None
 for k in (base,cat,sig):(await ingredient_row(session,uid,k)).qty-=1
 row=DarkWorldCustomRecipe(owner_id=int(uid),fingerprint=spec['fingerprint'],base_key=base,catalyst_key=cat,signature_key=sig,brand_key=brand,custom_name=spec['name'],quality=spec['quality'],power=spec['power'],stability=spec['stability'],risk=spec['risk'],value=spec['value'],required_level=spec['required_level']);session.add(row);await session.flush();await session.commit();return True,f"فرمول #{row.id} کشف شد: {row.custom_name}",row
async def start(session,uid,recipe_id,mode):
 if mode not in L.MODES:return False,"چرخه نامعتبر است."
 if await active(session,uid):return False,"یک تولید ترکیبی فعال داری."
 recipe=await session.get(DarkWorldCustomRecipe,int(recipe_id));lab=await LS.lab(session,uid)
 if not recipe or int(recipe.owner_id)!=int(uid):return False,"فرمول متعلق به تو نیست."
 if int(lab.level)<int(recipe.required_level) or int(lab.condition)<20:return False,"سطح یا وضعیت آزمایشگاه کافی نیست."
 inv=await ingredients(session,uid)
 for k in (recipe.base_key,recipe.catalyst_key,recipe.signature_key):
  if int(inv.get(k,0))<2:return False,f"برای تولید دو واحد {R.ingredient(k)['name']} لازم است."
 for k in (recipe.base_key,recipe.catalyst_key,recipe.signature_key):(await ingredient_row(session,uid,k)).qty-=2
 p=R.production(recipe,mode,lab);rolls=[secrets.randbelow(10_000),secrets.randbelow(101),secrets.randbelow(101),secrets.randbelow(101)];out=R.resolve(p,rolls[0]/100,*rolls[1:]);t=now();session.add(DarkWorldCustomBatch(owner_id=int(uid),recipe_id=recipe.id,mode_key=mode,status="active",chance_bp=int(round(p['chance']*100)),roll_bp=rolls[0],result_success=out['success'],result_qty=out['qty'],result_quality=out['quality'],result_power=out['power'],result_stability=out['stability'],condition_loss=out['condition_loss'],started_at=t,ready_at=t+timedelta(seconds=p['duration'])));await session.commit();return True,"تولید فرمول آغاز شد؛ نتیجه اکنون مخفی و پایدار است."
async def collect(session,uid):
 b=await active(session,uid)
 if not b:return False,"تولید فعالی نداری."
 if b.ready_at>now():return False,f"هنوز {int((b.ready_at-now()).total_seconds())//60+1} دقیقه مانده."
 lab=await LS.lab(session,uid);lab.condition=max(0,int(lab.condition)-int(b.condition_loss));profile=await DS.get_profile(session,uid,True);profile.heat=min(100,int(profile.heat or 0)+(4 if b.result_success else 14));b.status="completed" if b.result_success else "failed";b.completed_at=now()
 if b.result_success:
  row=(await session.execute(select(DarkWorldCustomInventory).where(DarkWorldCustomInventory.owner_id==int(uid),DarkWorldCustomInventory.recipe_id==b.recipe_id))).scalar_one_or_none();old=int(row.qty or 0) if row else 0;q=int(b.result_qty)
  if not row:row=DarkWorldCustomInventory(owner_id=int(uid),recipe_id=b.recipe_id,qty=0,avg_quality=0,avg_power=0,avg_stability=0);session.add(row)
  total=old+q;row.avg_quality=round((int(row.avg_quality or 0)*old+int(b.result_quality)*q)/total);row.avg_power=round((int(row.avg_power or 0)*old+int(b.result_power)*q)/total);row.avg_stability=round((int(row.avg_stability or 0)*old+int(b.result_stability)*q)/total);row.qty=total
 await session.commit();return True,(f"✅ {b.result_qty} واحد محصول ترکیبی آماده شد؛ کیفیت {b.result_quality} · قدرت {b.result_power} · پایداری {b.result_stability}." if b.result_success else "⚠️ تولید شکست خورد؛ مواد مصرف و آزمایشگاه آسیب دید.")
async def sell(session,uid,recipe_id):
 row=(await session.execute(select(DarkWorldCustomInventory).where(DarkWorldCustomInventory.owner_id==int(uid),DarkWorldCustomInventory.recipe_id==int(recipe_id),DarkWorldCustomInventory.qty>0))).scalar_one_or_none();recipe=await session.get(DarkWorldCustomRecipe,int(recipe_id))
 if not row or not recipe or int(recipe.owner_id)!=int(uid):return False,"محصول قابل فروش نیست."
 value=R.sale_value(recipe,row.avg_quality,row.avg_power,row.avg_stability);bonus=recipe.signature_key==R.demand_signature();row.qty=int(row.qty)-1
 from app.services import dark_world_finance_service as FS
 await FS.credit_dirty(session,uid,value,"custom_product");session.add(DarkWorldCustomSale(owner_id=int(uid),recipe_id=recipe.id,qty=1,unit_value=value,demand_bonus=bonus));await session.commit();return True,f"فروش انجام شد: {value:,} پول کثیف"+(" · امضای پرتقاضای امروز" if bonus else "")
