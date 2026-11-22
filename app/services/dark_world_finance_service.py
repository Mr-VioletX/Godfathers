# -*- coding: utf-8 -*-
"""Stage 87.7 — persistent dirty money, laundering, seizure and rare brokers."""
from __future__ import annotations
import secrets
from datetime import datetime,timedelta
from sqlalchemy import select
from app.data import dark_world as D
from app.data import dark_world_finance as F
from app.models.dark_world import DarkWorldFinance,DarkWorldLaunderingJob,DarkWorldRareInventory,DarkWorldFinanceLog
from app.services import dark_world_service as DS

def now():return datetime.utcnow()
async def account(session,uid,create=True):
 a=await session.get(DarkWorldFinance,int(uid))
 if a is None and create:a=DarkWorldFinance(owner_id=int(uid),dirty_balance=0,trace=0,last_trace_at=now());session.add(a);await session.flush()
 return a
def recover(a):
 n=now();steps=int(max(0,(n-(a.last_trace_at or n)).total_seconds())//F.TRACE_DECAY_SECONDS)
 if steps:a.trace=max(0,int(a.trace or 0)-steps);a.last_trace_at=n if a.trace<=0 else (a.last_trace_at+timedelta(seconds=steps*F.TRACE_DECAY_SECONDS))
async def active(session,uid):return (await session.execute(select(DarkWorldLaunderingJob).where(DarkWorldLaunderingJob.owner_id==int(uid),DarkWorldLaunderingJob.status=="active").order_by(DarkWorldLaunderingJob.id.desc()))).scalar_one_or_none()
async def rare_map(session,uid):return {r.item_key:int(r.qty or 0) for r in (await session.execute(select(DarkWorldRareInventory).where(DarkWorldRareInventory.owner_id==int(uid)))).scalars()}
async def snapshot(session,uid):
 player=await DS.get_player(session,uid);blocked=DS.access_message(player)
 if blocked:return False,blocked,{}
 a=await account(session,uid);recover(a);job=await active(session,uid);items=await rare_map(session,uid);profile=await DS.get_profile(session,uid,True)
 return True,"ok",{"player":player,"account":a,"active":job,"items":items,"profile":profile}
async def credit_dirty(session,uid,amount,source="smuggling"):
 a=await account(session,uid);value=max(0,int(amount));a.dirty_balance=min(F.DIRTY_MAX,int(a.dirty_balance or 0)+value);a.total_dirty_earned=int(a.total_dirty_earned or 0)+value;session.add(DarkWorldFinanceLog(owner_id=int(uid),event_key=f"dirty:{source}",amount=value,trace_delta=0));return value
async def debit_dirty(session,uid,amount,source="expense"):
 a=await account(session,uid);value=max(0,int(amount))
 if int(a.dirty_balance or 0)<value:return False
 a.dirty_balance=int(a.dirty_balance or 0)-value;session.add(DarkWorldFinanceLog(owner_id=int(uid),event_key=f"debit:{source}",amount=-value,trace_delta=0));return True
async def preview(session,uid,pct,method):
 ok,msg,s=await snapshot(session,uid)
 if not ok:return False,msg,{}
 if s["active"]:return False,"یک عملیات پول‌شویی فعال داری.",{}
 balance=int(s["account"].dirty_balance or 0);amount=balance*max(1,min(100,int(pct)))//100;items=s["items"]
 plan=F.plan(amount,method,int(s["account"].trace or 0),int(s["profile"].influence or 0),items.get("cipher_key",0)>0,items.get("ghost_pass",0)>0,items.get("zero_ledger",0)>0)
 if not plan:return False,"مبلغ یا روش نامعتبر است.",{}
 from app.services import dark_world_seasons_service as SES
 mods=await SES.modifiers(session,uid);plan["chance"]=max(10,min(96,float(plan["chance"])+mods["finance"]));plan["season_finance_bonus"]=mods["finance"]
 m=F.method(method)
 if int(s["profile"].influence or 0)<int(m["min_influence"]):return False,f"برای این روش {m['min_influence']:,} نفوذ لازم است.",plan
 return True,"ok",plan
async def start(session,uid,pct,method):
 ready,msg,p=await preview(session,uid,pct,method)
 if not ready:return False,msg
 a=await account(session,uid);items=await rare_map(session,uid);a.dirty_balance=int(a.dirty_balance or 0)-int(p["amount"]);roll=secrets.randbelow(10_000);out=F.resolve(p,roll/100);t=now()
 session.add(DarkWorldLaunderingJob(owner_id=int(uid),method_key=method,status="active",dirty_amount=int(p["amount"]),chance_bp=int(round(p["chance"]*100)),roll_bp=roll,result_success=out["success"],clean_cash=out["clean"],dirty_refund=out["dirty_refund"],confiscated=out["confiscated"],trace_gain=out["trace"],started_at=t,ready_at=t+timedelta(seconds=int(p["duration"]))))
 for key in ("cipher_key","ghost_pass"):
  if items.get(key,0)>0:
   row=(await session.execute(select(DarkWorldRareInventory).where(DarkWorldRareInventory.owner_id==int(uid),DarkWorldRareInventory.item_key==key))).scalar_one();row.qty=max(0,int(row.qty or 0)-1)
 await session.commit();return True,"عملیات مالی آغاز شد؛ نتیجه مخفی و پایدار ثبت شد."
async def collect(session,uid):
 job=await active(session,uid)
 if not job:return False,"عملیات مالی فعالی نداری."
 remain=max(0,int((job.ready_at-now()).total_seconds()))
 if remain:return False,f"هنوز {remain//60+1} دقیقه مانده."
 player=await DS.get_player(session,uid);a=await account(session,uid);player.cash=int(player.cash or 0)+int(job.clean_cash or 0);a.dirty_balance=int(a.dirty_balance or 0)+int(job.dirty_refund or 0);a.trace=min(100,int(a.trace or 0)+int(job.trace_gain or 0));a.total_cleaned=int(a.total_cleaned or 0)+int(job.clean_cash or 0);a.total_confiscated=int(a.total_confiscated or 0)+int(job.confiscated or 0);job.status="completed" if job.result_success else "failed";job.completed_at=now()
 seized=0
 if not job.result_success and int(a.trace)>=70:
  from app.models.dark_world import DarkWorldSmugglingInventory
  rows=list((await session.execute(select(DarkWorldSmugglingInventory).where(DarkWorldSmugglingInventory.owner_id==int(uid),DarkWorldSmugglingInventory.qty>0))).scalars())
  for row in rows:
   cut=max(0,int(row.qty or 0)//5);row.qty=int(row.qty or 0)-cut;seized+=cut
 session.add(DarkWorldFinanceLog(owner_id=int(uid),event_key="launder_success" if job.result_success else "launder_failed",amount=int(job.clean_cash or job.confiscated or 0),trace_delta=int(job.trace_gain or 0)));await session.commit()
 return True,(("✅ پول پاک تحویل شد." if job.result_success else "❌ بخشی از سرمایه مصادره شد.")+f"\n💵 پول پاک: +{int(job.clean_cash or 0):,}\n🌑 پول کثیف برگشتی: {int(job.dirty_refund or 0):,}\n🚨 ردگیری: +{int(job.trace_gain or 0)} → {int(a.trace)}/100"+(f"\n📦 کالای مصادره‌شده: {seized} واحد" if seized else ""))
async def buy_rare(session,uid,key):
 item=F.RARE.get(key)
 if not item:return False,"کالای کمیاب نامعتبر است."
 if key not in F.rare_today():return False,"این کالا امروز در شبکه واسطه‌ها موجود نیست."
 a=await account(session,uid)
 if int(a.dirty_balance or 0)<int(item["price"]):return False,"پول کثیف کافی نداری."
 a.dirty_balance=int(a.dirty_balance or 0)-int(item["price"]);row=(await session.execute(select(DarkWorldRareInventory).where(DarkWorldRareInventory.owner_id==int(uid),DarkWorldRareInventory.item_key==key))).scalar_one_or_none()
 if row:row.qty=int(row.qty or 0)+1
 else:session.add(DarkWorldRareInventory(owner_id=int(uid),item_key=key,qty=1))
 session.add(DarkWorldFinanceLog(owner_id=int(uid),event_key=f"rare:{key}",amount=int(item["price"]),trace_delta=2));a.trace=min(100,int(a.trace or 0)+2);await session.commit();return True,f"{item['icon']} {item['name']} خریداری شد."
async def logs(session,uid):return list((await session.execute(select(DarkWorldFinanceLog).where(DarkWorldFinanceLog.owner_id==int(uid)).order_by(DarkWorldFinanceLog.id.desc()).limit(12))).scalars())
