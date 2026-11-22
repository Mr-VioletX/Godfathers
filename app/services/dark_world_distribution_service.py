# -*- coding: utf-8 -*-
from __future__ import annotations
import secrets
from datetime import datetime,timedelta
from sqlalchemy import select,func
from app.data import dark_world_distribution as D
from app.models.dark_world import DarkWorldDistributionProfile,DarkWorldDistributionSale,DarkWorldCustomerContact,DarkWorldDistributionLog,DarkWorldCustomRecipe,DarkWorldCustomInventory
from app.services import dark_world_service as DS

def now():return datetime.utcnow()
async def profile(session,uid,district,create=True):
 x=(await session.execute(select(DarkWorldDistributionProfile).where(DarkWorldDistributionProfile.owner_id==int(uid),DarkWorldDistributionProfile.district_key==district))).scalar_one_or_none()
 if x is None and create:x=DarkWorldDistributionProfile(owner_id=int(uid),district_key=district,reputation=0,control_points=0,sales=0,failures=0);session.add(x);await session.flush()
 return x
async def active(session,uid):return (await session.execute(select(DarkWorldDistributionSale).where(DarkWorldDistributionSale.owner_id==int(uid),DarkWorldDistributionSale.status=="active").order_by(DarkWorldDistributionSale.id.desc()))).scalar_one_or_none()
async def inventory(session,uid):return list((await session.execute(select(DarkWorldCustomInventory).where(DarkWorldCustomInventory.owner_id==int(uid),DarkWorldCustomInventory.qty>0))).scalars())
async def start(session,uid,recipe_id,district,channel,screen):
 if district not in D.DISTRICTS or channel not in D.CHANNELS or screen not in D.SCREENS:return False,"طرح توزیع نامعتبر است."
 if await active(session,uid):return False,"یک معامله فعال داری."
 inv=(await session.execute(select(DarkWorldCustomInventory).where(DarkWorldCustomInventory.owner_id==int(uid),DarkWorldCustomInventory.recipe_id==int(recipe_id)))).scalar_one_or_none();recipe=await session.get(DarkWorldCustomRecipe,int(recipe_id));qty=D.CHANNELS[channel]['qty']
 if not inv or not recipe or int(recipe.owner_id)!=int(uid) or int(inv.qty or 0)<qty:return False,"موجودی محصول برای این کانال کافی نیست."
 p=await profile(session,uid,district);from app.services import dark_world_finance_service as FS
 wallet=await FS.account(session,uid);from app.services import dark_world_npc_service as NS
 team=await NS.team_context(session,uid);plan=D.plan(recipe,inv.avg_quality,inv.avg_power,inv.avg_stability,district,channel,screen,p.reputation,wallet.trace,team['effectiveness']);cust_roll=secrets.randbelow(100);customer=D.customer(district,wallet.trace,cust_roll);roll=secrets.randbelow(10_000);out=D.resolve(plan,customer,screen,roll/100);inv.qty=int(inv.qty)-qty;t=now();session.add(DarkWorldDistributionSale(owner_id=int(uid),recipe_id=recipe.id,district_key=district,channel_key=channel,screen_key=screen,customer_key=customer,status="active",qty=qty,chance_bp=int(plan['chance']*100),roll_bp=roll,result_success=out['success'],caught=out['caught'],payout=out['payout'],heat_gain=out['heat'],reputation_delta=out['rep'],started_at=t,ready_at=t+timedelta(seconds=plan['duration'])));await session.commit();return True,"شبکه توزیع فعال شد؛ هویت مشتری و نتیجه در سرور قفل شدند."
async def collect(session,uid):
 x=await active(session,uid)
 if not x:return False,"معامله فعالی نداری."
 if x.ready_at>now():return False,f"هنوز {int((x.ready_at-now()).total_seconds())//60+1} دقیقه مانده."
 from app.services import dark_world_finance_service as FS
 await FS.credit_dirty(session,uid,x.payout,"distribution");wallet=await FS.account(session,uid);wallet.trace=min(100,int(wallet.trace or 0)+(10 if x.caught else 2));dw=await DS.get_profile(session,uid,True);dw.heat=min(100,int(dw.heat or 0)+int(x.heat_gain));p=await profile(session,uid,x.district_key);p.reputation=max(-100,min(100,int(p.reputation or 0)+int(x.reputation_delta)));p.control_points=max(0,int(p.control_points or 0)+(8 if x.result_success else 0));p.sales=int(p.sales or 0)+(1 if x.result_success else 0);p.failures=int(p.failures or 0)+(0 if x.result_success else 1);x.status="completed" if x.result_success else "failed";x.completed_at=now()
 if x.result_success:
  c=(await session.execute(select(DarkWorldCustomerContact).where(DarkWorldCustomerContact.owner_id==int(uid),DarkWorldCustomerContact.district_key==x.district_key,DarkWorldCustomerContact.customer_key==x.customer_key))).scalar_one_or_none()
  if not c:c=DarkWorldCustomerContact(owner_id=int(uid),district_key=x.district_key,customer_key=x.customer_key,trust=0,debt=0,deals=0);session.add(c)
  c.trust=min(100,int(c.trust or 0)+5);c.deals=int(c.deals or 0)+1
 session.add(DarkWorldDistributionLog(owner_id=int(uid),sale_id=x.id,event_key="success" if x.result_success else "caught" if x.caught else "failed",value=int(x.payout)));await session.commit();return True,(("✅ معامله انجام شد." if x.result_success else "🚨 معامله شکست خورد.")+f"\nمشتری: {D.CUSTOMER_NAMES[x.customer_key]}\nدرآمد: {int(x.payout):,}\nHeat: +{x.heat_gain}\nشهرت محله: {p.reputation}")
async def territories(session):
 rows=list((await session.execute(select(DarkWorldDistributionProfile).order_by(DarkWorldDistributionProfile.district_key,DarkWorldDistributionProfile.control_points.desc()))).scalars());return rows
async def mine(session,uid):return list((await session.execute(select(DarkWorldDistributionProfile).where(DarkWorldDistributionProfile.owner_id==int(uid)).order_by(DarkWorldDistributionProfile.control_points.desc()))).scalars())
async def contacts(session,uid):return list((await session.execute(select(DarkWorldCustomerContact).where(DarkWorldCustomerContact.owner_id==int(uid)).order_by(DarkWorldCustomerContact.trust.desc()).limit(20))).scalars())
