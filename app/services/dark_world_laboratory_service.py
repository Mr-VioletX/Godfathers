# -*- coding: utf-8 -*-
"""Fictional, abstract lab management only; contains no real-world production instructions."""
from __future__ import annotations
import secrets
from datetime import datetime,timedelta
from sqlalchemy import select
from app.data import dark_world as D
from app.data import dark_world_laboratory as L
from app.models.dark_world import DarkWorldLab,DarkWorldLabMaterial,DarkWorldProductInventory,DarkWorldProductionBatch,DarkWorldLabLog
from app.services import dark_world_service as DS

def now():return datetime.utcnow()
async def lab(session,uid,create=True):
 x=await session.get(DarkWorldLab,int(uid))
 if x is None and create:x=DarkWorldLab(owner_id=int(uid),level=1,equipment=1,power=1,ventilation=1,safety=1,condition=100);session.add(x);await session.flush()
 return x
async def material(session,uid,key,create=False):
 x=(await session.execute(select(DarkWorldLabMaterial).where(DarkWorldLabMaterial.owner_id==int(uid),DarkWorldLabMaterial.material_key==key))).scalar_one_or_none()
 if x is None and create:x=DarkWorldLabMaterial(owner_id=int(uid),material_key=key,qty=0);session.add(x);await session.flush()
 return x
async def materials(session,uid):return {x.material_key:int(x.qty or 0) for x in (await session.execute(select(DarkWorldLabMaterial).where(DarkWorldLabMaterial.owner_id==int(uid)))).scalars()}
async def products(session,uid):return list((await session.execute(select(DarkWorldProductInventory).where(DarkWorldProductInventory.owner_id==int(uid),DarkWorldProductInventory.qty>0).order_by(DarkWorldProductInventory.product_key))).scalars())
async def active(session,uid):return (await session.execute(select(DarkWorldProductionBatch).where(DarkWorldProductionBatch.owner_id==int(uid),DarkWorldProductionBatch.status=="active").order_by(DarkWorldProductionBatch.id.desc()))).scalar_one_or_none()
async def snapshot(session,uid):
 player=await DS.get_player(session,uid);blocked=DS.access_message(player)
 if blocked:return False,blocked,{}
 x=await lab(session,uid);m=await materials(session,uid);p=await products(session,uid);a=await active(session,uid);return True,"ok",{"player":player,"lab":x,"materials":m,"products":p,"active":a}
async def buy_material(session,uid,key):
 item=L.MATERIALS.get(key)
 if not item:return False,"ماده داستانی نامعتبر است."
 ok,msg,s=await snapshot(session,uid)
 if not ok:return False,msg
 from app.services import dark_world_finance_service as FS
 wallet=await FS.account(session,uid);cost=int(item['price'])
 if int(wallet.dirty_balance or 0)<cost:return False,"پول کثیف کافی نداری."
 wallet.dirty_balance=int(wallet.dirty_balance or 0)-cost;row=await material(session,uid,key,True);row.qty=int(row.qty or 0)+L.MATERIAL_PACK_QTY;session.add(DarkWorldLabLog(owner_id=int(uid),event_key=f"material:{key}",value=cost));await session.commit();return True,f"{L.MATERIAL_PACK_QTY} واحد {item['name']} خریداری شد."
async def upgrade(session,uid,key):
 if key not in L.UPGRADES:return False,"بخش نامعتبر است."
 x=await lab(session,uid);current=int(getattr(x,key) or 1)
 if current>=L.LAB_MAX_LEVEL:return False,"این بخش در بالاترین سطح است."
 from app.services import dark_world_finance_service as FS
 wallet=await FS.account(session,uid);cost=L.upgrade_cost(current)
 if int(wallet.dirty_balance or 0)<cost:return False,f"برای ارتقا {cost:,} پول کثیف لازم است."
 wallet.dirty_balance=int(wallet.dirty_balance or 0)-cost;setattr(x,key,current+1);x.level=min(L.LAB_MAX_LEVEL,1+sum(max(0,int(getattr(x,k))-1) for k in L.UPGRADES)//2);session.add(DarkWorldLabLog(owner_id=int(uid),event_key=f"upgrade:{key}",value=cost));await session.commit();return True,f"{L.UPGRADES[key]['name']} به سطح {current+1} رسید؛ سطح آزمایشگاه {x.level}."
async def repair(session,uid):
 x=await lab(session,uid);missing=100-int(x.condition or 0)
 if missing<=0:return False,"آزمایشگاه سالم است."
 from app.services import dark_world_finance_service as FS
 wallet=await FS.account(session,uid);cost=missing*4_000_000
 if int(wallet.dirty_balance or 0)<cost:return False,f"هزینه تعمیر {cost:,} است."
 wallet.dirty_balance=int(wallet.dirty_balance or 0)-cost;x.condition=100;session.add(DarkWorldLabLog(owner_id=int(uid),event_key="repair",value=cost));await session.commit();return True,"آزمایشگاه کاملاً تعمیر شد."
async def preview(session,uid,product,qty,mode):
 ok,msg,s=await snapshot(session,uid)
 if not ok:return False,msg,{}
 if s['active']:return False,"یک بچ فعال داری.",{}
 p=L.PRODUCTS.get(product)
 if not p or int(s['lab'].level)<int(p['level']):return False,"سطح آزمایشگاه برای این محصول کافی نیست.",{}
 if int(s['lab'].condition or 0)<20:return False,"شرایط آزمایشگاه بحرانی است؛ ابتدا تعمیر کن.",{}
 plan=L.plan(product,qty,mode,s['lab'])
 if int(plan.get('qty',0))>L.capacity(s['lab'].level,s['lab'].equipment):return False,"ظرفیت این چرخه کافی نیست.",plan
 for k,v in plan.get('materials',{}).items():
  if int(s['materials'].get(k,0))<v:return False,f"موجودی {L.MATERIALS[k]['name']} کافی نیست.",plan
 return True,"ok",plan
async def start(session,uid,product,qty,mode):
 ready,msg,p=await preview(session,uid,product,qty,mode)
 if not ready:return False,msg
 for k,v in p['materials'].items():(await material(session,uid,k)).qty-=v
 rolls=[secrets.randbelow(10_000),secrets.randbelow(101),secrets.randbelow(101),secrets.randbelow(101)];out=L.resolve(p,rolls[0]/100,*rolls[1:]);t=now();session.add(DarkWorldProductionBatch(owner_id=int(uid),product_key=product,mode_key=mode,input_qty=int(p['qty']),status="active",chance_bp=int(round(p['chance']*100)),roll_bp=rolls[0],result_success=out['success'],result_qty=out['yield_qty'],result_quality=out['quality'],result_potency=out['potency'],result_stability=out['stability'],accident=out['accident'],condition_loss=out['condition_loss'],started_at=t,ready_at=t+timedelta(seconds=p['duration'])));await session.commit();return True,"چرخه آغاز شد؛ تمام نتیجه‌ها اکنون مخفی و پایدار ثبت شدند."
async def collect(session,uid):
 b=await active(session,uid)
 if not b:return False,"بچ فعالی نداری."
 remain=max(0,int((b.ready_at-now()).total_seconds()))
 if remain:return False,f"هنوز {remain//60+1} دقیقه مانده."
 x=await lab(session,uid);x.condition=max(0,int(x.condition or 0)-int(b.condition_loss or 0));profile=await DS.get_profile(session,uid,True);profile.heat=min(100,int(profile.heat or 0)+(12 if b.accident else 3));b.status="completed" if b.result_success else "failed";b.completed_at=now()
 if b.result_success:
  row=(await session.execute(select(DarkWorldProductInventory).where(DarkWorldProductInventory.owner_id==int(uid),DarkWorldProductInventory.product_key==b.product_key))).scalar_one_or_none();q=int(b.result_qty);old=int(row.qty or 0) if row else 0
  if not row:row=DarkWorldProductInventory(owner_id=int(uid),product_key=b.product_key,qty=0,avg_quality=0,avg_potency=0,avg_stability=0);session.add(row)
  total=old+q;row.avg_quality=round((int(row.avg_quality or 0)*old+int(b.result_quality)*q)/total);row.avg_potency=round((int(row.avg_potency or 0)*old+int(b.result_potency)*q)/total);row.avg_stability=round((int(row.avg_stability or 0)*old+int(b.result_stability)*q)/total);row.qty=total
 session.add(DarkWorldLabLog(owner_id=int(uid),event_key="batch_success" if b.result_success else "batch_accident",value=int(b.result_qty or 0)));await session.commit();return True,((f"✅ {b.result_qty} واحد {L.PRODUCTS[b.product_key]['name']} ساخته شد.\nکیفیت {b.result_quality} · قدرت {b.result_potency} · پایداری {b.result_stability}" if b.result_success else "⚠️ چرخه شکست خورد و آزمایشگاه آسیب دید.")+f"\nوضعیت آزمایشگاه: {x.condition}/100")
async def sell(session,uid,key):
 row=(await session.execute(select(DarkWorldProductInventory).where(DarkWorldProductInventory.owner_id==int(uid),DarkWorldProductInventory.product_key==key,DarkWorldProductInventory.qty>0))).scalar_one_or_none()
 if not row:return False,"این محصول را نداری."
 value=L.broker_value(key,row.avg_quality,row.avg_potency,row.avg_stability);row.qty=int(row.qty)-1
 from app.services import dark_world_finance_service as FS
 await FS.credit_dirty(session,uid,value,"fictional_product");session.add(DarkWorldLabLog(owner_id=int(uid),event_key=f"broker:{key}",value=value));await session.commit();return True,f"یک واحد به واسطه داستانی فروخته شد: {value:,} پول کثیف."
