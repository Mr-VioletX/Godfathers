# -*- coding: utf-8 -*-
from __future__ import annotations
import secrets
from datetime import datetime,timedelta
from sqlalchemy import select,func
from app.data import dark_world_empire as E
from app.models.dark_world import DarkWorldEmpireProfile,DarkWorldFacility,DarkWorldRivalConflict,DarkWorldInspection,DarkWorldEmpireLog,DarkWorldCustomInventory
from app.services import dark_world_service as DS

def now():return datetime.utcnow()
async def profile(s,uid):
 x=await s.get(DarkWorldEmpireProfile,int(uid))
 if not x:x=DarkWorldEmpireProfile(owner_id=int(uid),research_points=0,brand_power=0,rival_wins=0,inspection_wins=0,total_capacity=0);s.add(x);await s.flush()
 return x
async def facilities(s,uid):return list((await s.execute(select(DarkWorldFacility).where(DarkWorldFacility.owner_id==int(uid),DarkWorldFacility.status=="active").order_by(DarkWorldFacility.id))).scalars())
async def buy(s,uid,key):
 if key not in E.FACILITIES:return False,"مرکز نامعتبر است."
 fs=await facilities(s,uid)
 if len(fs)>=5:return False,"سقف پنج مرکز فعال است."
 from app.services import dark_world_finance_service as F
 if not await F.debit_dirty(s,uid,E.FACILITIES[key]['cost'],"facility_build"):return False,"پول کثیف کافی نیست."
 s.add(DarkWorldFacility(owner_id=int(uid),facility_key=key,status="active",capacity_level=0,stealth_level=0,resilience_level=0,research_level=0,condition=100,created_at=now()));p=await profile(s,uid);p.total_capacity=E.empire_capacity(fs)+E.FACILITIES[key]['capacity'];await s.commit();return True,"مرکز تولید داستانی ساخته شد."
async def upgrade(s,uid,fid,key):
 if key not in E.UPGRADES:return False,"ارتقای نامعتبر است."
 x=await s.get(DarkWorldFacility,int(fid))
 if not x or int(x.owner_id)!=int(uid) or x.status!='active':return False,"مرکز پیدا نشد."
 col=key+'_level';lv=int(getattr(x,col) or 0)
 if lv>=5:return False,"این شاخه به سقف رسیده است."
 cost=E.upgrade_cost(lv,key);from app.services import dark_world_finance_service as F
 if not await F.debit_dirty(s,uid,cost,"facility_upgrade"):return False,"پول کثیف کافی نیست."
 setattr(x,col,lv+1);p=await profile(s,uid);p.total_capacity=E.empire_capacity(await facilities(s,uid));p.research_points+=2 if key=='research' else 0;await s.commit();return True,"ارتقا انجام شد."
async def empire_stats(s,uid):
 fs=await facilities(s,uid);p=await profile(s,uid);return p,fs,E.empire_capacity(fs),E.empire_stealth(fs)
async def fight_rival(s,uid,rival,response):
 if rival not in E.RIVALS or response not in E.RESPONSES:return False,"انتخاب نامعتبر است."
 p,fs,cap,stealth=await empire_stats(s,uid)
 if not fs:return False,"اول یک مرکز تولید بساز."
 from app.services import dark_world_finance_service as F
 if not await F.debit_dirty(s,uid,E.RESPONSES[response]['cost'],"rival_response"):return False,"پول کثیف کافی نیست."
 roll=secrets.randbelow(10_000)/100;out=E.rival_plan(rival,response,cap+stealth+p.brand_power,roll);p.rival_wins+=1 if out['success'] else 0;p.brand_power=max(0,int(p.brand_power)+(4 if out['success'] else -3));dw=await DS.get_profile(s,uid,True);dw.heat=min(100,int(dw.heat or 0)+out['heat']);s.add(DarkWorldRivalConflict(owner_id=int(uid),rival_key=rival,response_key=response,result_success=out['success'],chance_bp=int(out['chance']*100),roll_bp=int(roll*100),control_delta=out['control_delta'],reward=out['reward'],created_at=now()))
 if out['success']:await F.credit_dirty(s,uid,out['reward'],"rival_win")
 await maybe_schedule_inspection(s,uid);await s.commit();return True,("رقیب عقب نشست." if out['success'] else "رقیب دست بالا را گرفت.")
async def active_inspection(s,uid):return (await s.execute(select(DarkWorldInspection).where(DarkWorldInspection.owner_id==int(uid),DarkWorldInspection.status.in_(("warning","active"))).order_by(DarkWorldInspection.id.desc()))).scalar_one_or_none()
async def maybe_schedule_inspection(s,uid):
 if await active_inspection(s,uid):return None
 fs=await facilities(s,uid)
 if not fs:return None
 from app.services import dark_world_finance_service as F
 w=await F.account(s,uid);dw=await DS.get_profile(s,uid,True);risk=E.inspection_risk(dw.heat,w.trace,fs)
 if secrets.randbelow(100)>=risk:return None
 x=DarkWorldInspection(owner_id=int(uid),status="warning",risk_bp=int(risk*100),choice_key=None,chance_bp=0,roll_bp=0,result_success=False,condition_loss=0,confiscated_qty=0,warned_at=now(),ready_at=None,resolved_at=None);s.add(x);await s.flush();return x
async def prepare_inspection(s,uid,choice):
 if choice not in E.INSPECTION_CHOICES:return False,"واکنش نامعتبر است."
 x=await active_inspection(s,uid)
 if not x or x.status!='warning':return False,"هشدار فعالی وجود ندارد."
 from app.services import dark_world_finance_service as F
 if not await F.debit_dirty(s,uid,E.INSPECTION_CHOICES[choice]['cost'],"inspection_prepare"):return False,"پول کثیف کافی نیست."
 fs=await facilities(s,uid);res=sum(int(z.resilience_level or 0) for z in fs);roll=secrets.randbelow(10_000)/100;out=E.inspection_result(x.risk_bp/100,choice,res,roll);x.choice_key=choice;x.chance_bp=int(out['chance']*100);x.roll_bp=int(roll*100);x.result_success=out['success'];x.condition_loss=out['condition_loss'];x.status='active';x.ready_at=now()+timedelta(minutes=20);await s.commit();return True,"واکنش ثبت شد و نتیجه در سرور قفل شد."
async def resolve_inspection(s,uid):
 x=await active_inspection(s,uid)
 if not x:return False,"بازرسی فعالی نداری."
 if x.status=='warning':return False,"ابتدا واکنش انتخاب کن."
 if x.ready_at>now():return False,"بازرسی هنوز تمام نشده است."
 fs=await facilities(s,uid);dw=await DS.get_profile(s,uid,True);p=await profile(s,uid)
 if x.result_success:dw.heat=max(0,int(dw.heat or 0)-18);p.inspection_wins+=1
 else:
  for z in fs:z.condition=max(1,int(z.condition)-int(x.condition_loss))
  inv=list((await s.execute(select(DarkWorldCustomInventory).where(DarkWorldCustomInventory.owner_id==int(uid),DarkWorldCustomInventory.qty>0))).scalars());taken=0
  for z in inv:q=max(0,int(z.qty)*18//100);z.qty-=q;taken+=q
  x.confiscated_qty=taken;dw.heat=min(100,int(dw.heat or 0)+12)
 x.status='resolved';x.resolved_at=now();s.add(DarkWorldEmpireLog(owner_id=int(uid),event_key='inspection_pass' if x.result_success else 'inspection_fail',value=int(x.confiscated_qty)));await s.commit();return True,("بازرسی بدون خسارت رد شد." if x.result_success else f"بازرسی شکست خورد؛ {x.confiscated_qty} واحد خیالی ضبط شد.")
