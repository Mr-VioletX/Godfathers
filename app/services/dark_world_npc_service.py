# -*- coding: utf-8 -*-
"""Stage 87.4 — persistent NPC progression, payroll and crew composition."""
from __future__ import annotations
import json,secrets
from datetime import datetime,timedelta
from sqlalchemy import select
from app.data import dark_world_npcs as N
from app.models.dark_world import DarkWorldRecruit,DarkWorldRecruitState,DarkWorldTeam,DarkWorldRecruitEvent
from app.services import dark_world_service as DS

def _now():return datetime.utcnow()
def _loads(v):
 try:
  x=json.loads(v or "[]");return x if isinstance(x,list) else []
 except Exception:return []
def _dumps(v):return json.dumps(v,ensure_ascii=False,separators=(",",":"))
async def _owned(session,uid):return list((await session.execute(select(DarkWorldRecruit).where(DarkWorldRecruit.owner_id==int(uid)).order_by(DarkWorldRecruit.id))).scalars().all())
async def get_team(session,uid,create=True):
 row=await session.get(DarkWorldTeam,int(uid))
 if row is None and create:
  owned=await _owned(session,uid);row=DarkWorldTeam(owner_id=int(uid),member_keys_json=_dumps([r.recruit_key for r in owned[:N.TEAM_SIZE]]),tactic_key="balanced");session.add(row);await session.flush()
 return row
async def _state(session,uid,key,create=True):
 row=(await session.execute(select(DarkWorldRecruitState).where(DarkWorldRecruitState.owner_id==int(uid),DarkWorldRecruitState.recruit_key==str(key)))).scalar_one_or_none()
 if row is None and create:
  row=DarkWorldRecruitState(owner_id=int(uid),recruit_key=str(key),fatigue=0,unpaid_cycles=0,wage_due_at=_now()+timedelta(days=N.WAGE_DAYS));session.add(row);await session.flush()
 return row

def _refresh(recruit,state,now=None):
 now=now or _now()
 if state.training_until and state.training_until<=now:
  if int(recruit.level or 1)<N.MAX_LEVEL:recruit.level=int(recruit.level or 1)+1
  state.training_until=None;state.fatigue=min(N.FATIGUE_MAX,int(state.fatigue or 0)+10)
 if state.rest_until and state.rest_until<=now:
  state.rest_until=None;state.fatigue=max(0,int(state.fatigue or 0)-45)
 if state.injured_until and state.injured_until<=now:state.injured_until=None

def _available(state):return not bool(state.deserted or state.training_until or state.rest_until or state.injured_until)
async def snapshot(session,uid):
 player=await DS.get_player(session,uid);blocked=DS.access_message(player)
 if blocked:return False,blocked,{}
 profile=await DS.get_profile(session,uid,create=True);owned=await _owned(session,uid);team=await get_team(session,uid)
 rows=[]
 for rec in owned:
  st=await _state(session,uid,rec.recruit_key);_refresh(rec,st);meta=N.npc(rec.recruit_key) or {"class_name":"نیرو","description":""}
  overdue=max(0,1+int((_now()-st.wage_due_at).total_seconds()//(N.WAGE_DAYS*86400))) if st.wage_due_at and st.wage_due_at<=_now() else 0
  st.unpaid_cycles=max(int(st.unpaid_cycles or 0),overdue)
  rows.append({"key":str(rec.recruit_key),"name":meta.get("class_name",rec.recruit_key),"display":meta,"level":int(rec.level or 1),"loyalty":int(rec.loyalty or 0),"effective_loyalty":max(0,int(rec.loyalty or 0)-st.unpaid_cycles*10),"missions":int(rec.missions or 0),"fatigue":int(st.fatigue or 0),"unpaid":int(st.unpaid_cycles or 0),"wage_due":bool(st.wage_due_at and st.wage_due_at<=_now()),"injured_until":st.injured_until,"training_until":st.training_until,"rest_until":st.rest_until,"deserted":bool(st.deserted),"available":_available(st),"state":st,"recruit":rec})
 selected=[k for k in _loads(team.member_keys_json) if any(r["key"]==k for r in rows)][:N.TEAM_SIZE];team.member_keys_json=_dumps(selected)
 members=[dict(r,loyalty=r["effective_loyalty"],available=r["available"] and r["key"] in selected) for r in rows if r["key"] in selected]
 analysis=N.team_analysis(members,team.tactic_key)
 return True,"ok",{"player":player,"profile":profile,"team":team,"rows":rows,"selected":selected,"members":members,"analysis":analysis}
async def team_context(session,uid):
 ok,_,s=await snapshot(session,uid)
 if not ok:return {"keys":set(),"effectiveness":0.0,"tactic":"balanced","members":[]}
 return {"keys":{m["key"] for m in s["members"] if m["available"]},"effectiveness":s["analysis"]["effectiveness"],"tactic":str(s["team"].tactic_key or "balanced"),"members":s["members"],"analysis":s["analysis"]}
async def toggle_member(session,uid,key):
 ok,msg,s=await snapshot(session,uid)
 if not ok:return False,msg
 row=next((r for r in s["rows"] if r["key"]==key),None)
 if not row:return False,"این نیرو را استخدام نکرده‌ای."
 if not row["available"]:return False,"این نیرو اکنون مصدوم، در تمرین، در استراحت یا جداشده است."
 selected=list(s["selected"])
 if key in selected:selected.remove(key)
 else:
  if len(selected)>=N.TEAM_SIZE:return False,"تیم فقط سه جای فعال دارد؛ ابتدا یک نفر را خارج کن."
  selected.append(key)
 s["team"].member_keys_json=_dumps(selected);await session.commit();return True,"ترکیب تیم بروزرسانی شد."
async def set_tactic(session,uid,key):
 if key not in N.TACTICS:return False,"تاکتیک نامعتبر است."
 team=await get_team(session,uid);team.tactic_key=key;await session.commit();return True,f"تاکتیک «{N.TACTICS[key]['name']}» فعال شد."
async def train(session,uid,key):
 ok,msg,s=await snapshot(session,uid)
 if not ok:return False,msg
 row=next((r for r in s["rows"] if r["key"]==key),None)
 if not row:return False,"نیرو پیدا نشد."
 if not row["available"]:return False,"نیرو اکنون آماده تمرین نیست."
 if row["level"]>=N.MAX_LEVEL:return False,"این نیرو به بالاترین لول رسیده است."
 cost=N.training_cost(key,row["level"])
 if int(s["player"].cash or 0)<cost:return False,f"هزینه تمرین {cost:,} است."
 s["player"].cash=int(s["player"].cash or 0)-cost;row["state"].training_until=_now()+timedelta(hours=N.TRAINING_HOURS)
 session.add(DarkWorldRecruitEvent(owner_id=int(uid),recruit_key=key,event_key="training",value=cost));await session.commit();return True,f"🎓 تمرین آغاز شد؛ {N.TRAINING_HOURS} ساعت دیگر لول نیرو افزایش می‌یابد."
async def pay_wages(session,uid):
 ok,msg,s=await snapshot(session,uid)
 if not ok:return False,msg
 due=[r for r in s["rows"] if r["wage_due"]]
 if not due:return False,"هنوز حقوق هیچ نیرویی سررسید نشده است."
 total=sum(N.salary(r["key"],r["level"]) for r in due)
 if int(s["player"].cash or 0)<total:return False,f"جمع حقوق {total:,} است و موجودی کافی نیست."
 s["player"].cash=int(s["player"].cash or 0)-total
 for r in due:
  r["state"].wage_due_at=_now()+timedelta(days=N.WAGE_DAYS);r["state"].unpaid_cycles=0;r["recruit"].loyalty=min(100,int(r["recruit"].loyalty or 0)+8)
 session.add(DarkWorldRecruitEvent(owner_id=int(uid),recruit_key="team",event_key="wages",value=total));await session.commit();return True,f"💵 حقوق {len(due)} نیرو به مبلغ {total:,} پرداخت شد؛ وفاداری افزایش یافت."
async def rest_team(session,uid):
 ok,msg,s=await snapshot(session,uid)
 if not ok:return False,msg
 targets=[m for m in s["members"] if m["available"] and m["fatigue"]>=15]
 if not targets:return False,"عضو خسته و آماده‌ای در تیم فعال نیست."
 for r in targets:r["state"].rest_until=_now()+timedelta(hours=N.REST_HOURS)
 await session.commit();return True,f"🛌 {len(targets)} عضو تیم برای {N.REST_HOURS} ساعت استراحت کردند؛ در این مدت قابل استفاده نیستند."
async def return_deserter(session,uid,key):
 ok,msg,s=await snapshot(session,uid)
 if not ok:return False,msg
 r=next((x for x in s["rows"] if x["key"]==key and x["deserted"]),None)
 if not r:return False,"این نیرو شبکه را ترک نکرده است."
 cost=N.salary(key,r["level"])*3
 if int(s["player"].cash or 0)<cost:return False,f"برای بازگرداندن نیرو {cost:,} لازم است."
 s["player"].cash=int(s["player"].cash or 0)-cost;r["state"].deserted=False;r["state"].unpaid_cycles=0;r["recruit"].loyalty=45;r["state"].wage_due_at=_now()+timedelta(days=N.WAGE_DAYS)
 await session.commit();return True,"🤝 نیرو با قرارداد تازه برگشت؛ وفاداری روی ۴۵ تنظیم شد."
async def apply_mission_wear(session,uid,difficulty:int,success:bool):
 ctx=await team_context(session,uid);events=[];mult=ctx.get("analysis",{}).get("fatigue_mult",1.0)
 for m in ctx["members"]:
  if not m["available"]:continue
  rec,st=m["recruit"],m["state"];gain=max(3,round((5+int(difficulty)*4)*mult));st.fatigue=min(100,int(st.fatigue or 0)+gain);rec.missions=int(rec.missions or 0)+1
  rec.loyalty=max(0,min(100,int(rec.loyalty or 0)+(1 if success else -3)-int(st.unpaid_cycles or 0)*2))
  injury=max(1,int((N.npc(m["key"])["risk"]*100+int(difficulty)*2)*(0.55 if ctx.get("analysis",{}).get("medic") else 1.0)*(1.2 if not success else 1.0)))
  if secrets.randbelow(100)<injury:st.injured_until=_now()+timedelta(hours=N.INJURY_HOURS);events.append(f"🩹 {N.npc(m['key'])['class_name']} مصدوم شد")
  betray=N.betrayal_chance(rec.loyalty,st.unpaid_cycles,N.npc(m["key"])["risk"])
  if secrets.randbelow(10_000)<int(betray*100):st.deserted=True;events.append(f"⚠️ {N.npc(m['key'])['class_name']} به‌دلیل وفاداری پایین شبکه را ترک کرد")
 return ("\n"+"\n".join(events)) if events else ""
