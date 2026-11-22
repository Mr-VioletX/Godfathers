# -*- coding: utf-8 -*-
"""Stage 87.5 — atomic user-to-user contracts, escrow, execution and trust."""
from __future__ import annotations
import secrets
from datetime import datetime,timedelta
from sqlalchemy import select,update,func,or_
from app.data import dark_world as D
from app.data import dark_world_employment as E
from app.models.dark_world import DarkWorldEmploymentContract,DarkWorldEmploymentLog,DarkWorldEmploymentReputation
from app.models.player import Player
from app.services import dark_world_service as DS

def now():return datetime.utcnow()
async def rep(session,uid,create=True):
 r=await session.get(DarkWorldEmploymentReputation,int(uid))
 if r is None and create:r=DarkWorldEmploymentReputation(owner_id=int(uid),trust=50);session.add(r);await session.flush()
 return r
async def get_contract(session,cid):return await session.get(DarkWorldEmploymentContract,int(cid))
async def _player(session,uid):return (await session.execute(select(Player).where(Player.tg_user_id==int(uid)))).scalar_one_or_none()
def _age_ok(p):return bool(p and p.created_at and p.created_at<=now()-timedelta(hours=E.ACCOUNT_AGE_HOURS))
async def sweep(session):
 rows=list((await session.execute(select(DarkWorldEmploymentContract).where(DarkWorldEmploymentContract.status.in_(("open","accepted")),DarkWorldEmploymentContract.expires_at<=now()))).scalars())
 for c in rows:
  employer=await _player(session,c.employer_id);worker=await _player(session,c.worker_id) if c.worker_id else None;total=int(c.escrow_total or 0)
  compensation=round(int(c.fixed_wage or 0)*.05) if c.status=="accepted" and worker else 0
  if worker:worker.cash=int(worker.cash or 0)+compensation
  if employer:employer.cash=int(employer.cash or 0)+max(0,total-compensation)
  c.status="expired";c.completed_at=now();session.add(DarkWorldEmploymentLog(contract_id=c.id,actor_id=0,event_key="expired",amount=total))
 return len(rows)
async def create_contract(session,uid,job_key,payment_key):
 player=await _player(session,uid);blocked=DS.access_message(player)
 if blocked:return False,blocked,None
 if not _age_ok(player):return False,"حساب باید حداقل ۲۴ ساعت قدمت داشته باشد.",None
 j=E.job(job_key);pack=E.package(job_key,payment_key)
 if not j or not pack:return False,"نوع کار یا پرداخت نامعتبر است.",None
 since=now()-timedelta(hours=24)
 posted=(await session.execute(select(func.count()).select_from(DarkWorldEmploymentContract).where(DarkWorldEmploymentContract.employer_id==int(uid),DarkWorldEmploymentContract.created_at>=since))).scalar() or 0
 escrowed=(await session.execute(select(func.coalesce(func.sum(DarkWorldEmploymentContract.escrow_total),0)).where(DarkWorldEmploymentContract.employer_id==int(uid),DarkWorldEmploymentContract.created_at>=since))).scalar() or 0
 if posted>=E.DAILY_POST_LIMIT:return False,"سقف تعداد قرارداد روزانه پر شده است.",None
 if int(escrowed)+pack["escrow_total"]>E.DAILY_ESCROW_LIMIT:return False,"سقف مبلغ escrow روزانه رد می‌شود.",None
 if int(player.cash or 0)<pack["escrow_total"]:return False,f"برای escrow به {pack['escrow_total']:,} پول نیاز داری.",None
 condition=secrets.choice(E.CONDITION_ORDER);player.cash=int(player.cash or 0)-pack["escrow_total"]
 c=DarkWorldEmploymentContract(employer_id=int(uid),beneficiary_id=int(uid),job_key=job_key,payment_key=payment_key,status="open",condition_key=condition,min_level=int(j["min_level"]),min_trust=35,fixed_wage=pack["fixed_wage"],success_bonus=pack["success_bonus"],share_pct=pack["share_pct"],operation_budget=pack["operation_budget"],escrow_total=pack["escrow_total"],expires_at=now()+timedelta(hours=E.CONTRACT_TTL_HOURS))
 session.add(c);await session.flush();session.add(DarkWorldEmploymentLog(contract_id=c.id,actor_id=int(uid),event_key="published",amount=pack["escrow_total"]));await session.commit();return True,"قرارداد منتشر و کل بودجه در escrow قفل شد.",c
async def market(session,uid):
 await sweep(session);return list((await session.execute(select(DarkWorldEmploymentContract).where(DarkWorldEmploymentContract.status=="open",DarkWorldEmploymentContract.employer_id!=int(uid),DarkWorldEmploymentContract.expires_at>now()).order_by(DarkWorldEmploymentContract.created_at.desc()).limit(E.MARKET_LIMIT))).scalars())
async def mine(session,uid):
 await sweep(session);return list((await session.execute(select(DarkWorldEmploymentContract).where(or_(DarkWorldEmploymentContract.employer_id==int(uid),DarkWorldEmploymentContract.worker_id==int(uid))).order_by(DarkWorldEmploymentContract.created_at.desc()).limit(20))).scalars())
async def accept(session,uid,cid):
 worker=await _player(session,uid);blocked=DS.access_message(worker)
 if blocked:return False,blocked
 if not _age_ok(worker):return False,"حساب باید حداقل ۲۴ ساعت قدمت داشته باشد."
 c=await get_contract(session,cid)
 if not c or c.status!="open":return False,"این قرارداد دیگر باز نیست."
 if int(c.employer_id)==int(uid):return False,"استخدام خودت ممنوع است."
 r=await rep(session,uid)
 if int(worker.level or 1)<int(c.min_level):return False,f"حداقل لول این کار {c.min_level} است."
 if int(r.trust or 0)<int(c.min_trust):return False,f"حداقل اعتماد این کار {c.min_trust} است."
 since=now()-timedelta(hours=24);pairs=(await session.execute(select(func.count()).select_from(DarkWorldEmploymentContract).where(DarkWorldEmploymentContract.employer_id==c.employer_id,DarkWorldEmploymentContract.worker_id==int(uid),DarkWorldEmploymentContract.accepted_at>=since))).scalar() or 0
 if pairs>=E.PAIR_DAILY_LIMIT:return False,"سقف قرارداد روزانه میان این دو حساب پر شده است."
 result=await session.execute(update(DarkWorldEmploymentContract).where(DarkWorldEmploymentContract.id==int(cid),DarkWorldEmploymentContract.status=="open").values(status="accepted",worker_id=int(uid),accepted_at=now()))
 if result.rowcount!=1:await session.rollback();return False,"کاربر دیگری زودتر قرارداد را پذیرفت."
 session.add(DarkWorldEmploymentLog(contract_id=int(cid),actor_id=int(uid),event_key="accepted",amount=0));await session.commit();return True,"قرارداد با موفقیت پذیرفته شد."
async def start(session,uid,cid):
 c=await get_contract(session,cid)
 if not c or c.status!="accepted" or int(c.worker_id or 0)!=int(uid):return False,"امکان شروع این قرارداد را نداری."
 c.status="in_progress";c.started_at=now();session.add(DarkWorldEmploymentLog(contract_id=c.id,actor_id=int(uid),event_key="started",amount=0));await session.commit();return True,"کار آغاز شد؛ گزارش میدان را بخوان و روش اجرا را انتخاب کن."
async def execution_preview(session,uid,cid):
 c=await get_contract(session,cid);worker=await _player(session,uid)
 if not c or c.status!="in_progress" or int(c.worker_id or 0)!=int(uid):return False,"قرارداد در وضعیت اجرا نیست.",{}
 wr=await rep(session,uid);profile=await DS.get_profile(session,uid,create=True)
 from app.services import dark_world_npc_service as NS
 team=await NS.team_context(session,uid);chances={k:E.execution_chance(c.job_key,c.condition_key,k,level=int(worker.level or 1),trust=int(wr.trust or 50),heat=int(profile.heat or 0),team_effectiveness=team["effectiveness"],team_tactic=team["tactic"]) for k in E.APPROACH_ORDER}
 return True,"ok",{"contract":c,"worker":worker,"reputation":wr,"profile":profile,"team":team,"chances":chances,"condition":E.CONDITIONS[c.condition_key]}
async def execute(session,uid,cid,approach_key):
 ok,msg,p=await execution_preview(session,uid,cid)
 if not ok:return False,msg,{}
 c=p["contract"];a=E.approach(approach_key);info=p["chances"].get(approach_key)
 if not a or not info:return False,"روش اجرا نامعتبر است.",{}
 roll=secrets.randbelow(10_000);success=roll<int(round(info["chance"]*100));j=E.job(c.job_key)
 loot=round(int(c.operation_budget)*float(j["loot_mult"])*float(a["loot_mult"])*(1 if success else .10));effect=int(j["effect_success"] if success else j["effect_fail"])
 c.status="submitted";c.execution_approach=approach_key;c.result_success=success;c.result_loot=max(0,loot);c.result_effect=effect;c.execution_chance_bp=int(round(info["chance"]*100));c.execution_roll_bp=roll;c.submitted_at=now()
 profile=p["profile"];profile.heat=min(100,int(profile.heat or 0)+int(a["heat"])+(0 if success else 8))
 from app.services import dark_world_npc_service as NS
 team_note=await NS.apply_mission_wear(session,uid,2 if c.job_key in ("intel_scout","shadow_courier") else 3,success)
 session.add(DarkWorldEmploymentLog(contract_id=c.id,actor_id=int(uid),event_key="submitted_success" if success else "submitted_fail",amount=loot));await session.commit();return True,"نتیجه سرور ثبت و برای تسویه آماده شد.",{"success":success,"loot":loot,"effect":effect,"chance":info["chance"],"roll":roll/100,"team_note":team_note}
async def settle(session,uid,cid):
 c=await get_contract(session,cid)
 if not c or c.status!="submitted" or int(uid) not in (int(c.employer_id),int(c.worker_id or 0)):return False,"این قرارداد آماده تسویه نیست.",{}
 result=await session.execute(update(DarkWorldEmploymentContract).where(DarkWorldEmploymentContract.id==int(cid),DarkWorldEmploymentContract.status=="submitted").values(status="settling"))
 if result.rowcount!=1:await session.rollback();return False,"تسویه قبلاً انجام شده است.",{}
 employer=await _player(session,c.employer_id);worker=await _player(session,c.worker_id);beneficiary=await _player(session,c.beneficiary_id)
 pay=E.settlement(c.fixed_wage,c.success_bonus,c.share_pct,c.operation_budget,c.result_loot,bool(c.result_success));worker.cash=int(worker.cash or 0)+pay["worker"];employer.cash=int(employer.cash or 0)+pay["employer"]
 bp=await DS.get_profile(session,c.beneficiary_id,create=True)
 if c.job_key=="intel_scout":bp.intel=max(0,int(bp.intel or 0)+int(c.result_effect))
 elif c.job_key=="signal_breach":bp.heat=max(0,min(100,int(bp.heat or 0)+int(c.result_effect)))
 elif c.job_key=="safehouse_guard":
  from app.services import dark_world_pursuit_service as PS
  h=await PS.get_hideout(session,c.beneficiary_id,create=True);h.integrity=max(0,min(100,int(h.integrity or 0)+int(c.result_effect)))
 er=await rep(session,c.employer_id);wr=await rep(session,c.worker_id);er.contracts_as_employer=int(er.contracts_as_employer or 0)+1;er.amount_paid=int(er.amount_paid or 0)+pay["worker"];wr.contracts_as_worker=int(wr.contracts_as_worker or 0)+1;wr.amount_earned=int(wr.amount_earned or 0)+pay["worker"]
 if c.result_success:wr.successes=int(wr.successes or 0)+1;wr.trust=min(100,int(wr.trust or 50)+3);er.trust=min(100,int(er.trust or 50)+1)
 else:wr.failures=int(wr.failures or 0)+1;wr.trust=max(0,int(wr.trust or 50)-2)
 c.status="completed" if c.result_success else "failed";c.worker_payout=pay["worker"];c.employer_refund=pay["employer"];c.completed_at=now();session.add(DarkWorldEmploymentLog(contract_id=c.id,actor_id=int(uid),event_key="settled",amount=pay["worker"]));await session.commit();return True,"تسویه اتمیک انجام شد.",pay
async def cancel(session,uid,cid):
 c=await get_contract(session,cid)
 if not c or int(c.employer_id)!=int(uid) or c.status!="open":return False,"فقط قرارداد باز خودت قابل لغو است."
 p=await _player(session,uid);p.cash=int(p.cash or 0)+int(c.escrow_total or 0);c.status="cancelled";c.completed_at=now();session.add(DarkWorldEmploymentLog(contract_id=c.id,actor_id=int(uid),event_key="cancelled",amount=int(c.escrow_total or 0)));await session.commit();return True,"قرارداد لغو و کل escrow بازپرداخت شد."
async def dispute(session,uid,cid):
 c=await get_contract(session,cid)
 if not c or c.status!="submitted" or int(uid) not in (int(c.employer_id),int(c.worker_id or 0)):return False,"امکان ثبت اختلاف نیست."
 c.status="disputed";c.disputed_by=int(uid);c.disputed_at=now();rr=await rep(session,uid);rr.disputes=int(rr.disputes or 0)+1;session.add(DarkWorldEmploymentLog(contract_id=c.id,actor_id=int(uid),event_key="disputed",amount=0));await session.commit();return True,"منابع قفل ماند و اختلاف با ارجاع به لاگ سرور ثبت شد."
