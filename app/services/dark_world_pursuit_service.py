# -*- coding: utf-8 -*-
"""Stage 87.3 — persistent strategic pursuit engine."""
from __future__ import annotations
import json, secrets
from datetime import datetime, timedelta
from sqlalchemy import select
from app.data import dark_world as D
from app.data import dark_world_pursuit as P
from app.models.dark_world import DarkWorldHideout, DarkWorldPursuitLog
from app.services import dark_world_service as DS


def _now(): return datetime.utcnow()

def _loads(value, default):
    try:
        obj=json.loads(value or "")
        return obj if isinstance(obj,type(default)) else default
    except Exception: return default

def _dumps(value): return json.dumps(value,ensure_ascii=False,separators=(",",":"))

async def get_hideout(session,uid:int,create:bool=False):
    row=await session.get(DarkWorldHideout,int(uid))
    if row is None and create:
        row=DarkWorldHideout(owner_id=int(uid),level=1,integrity=100,forged_ids=0,clues_json="[]")
        session.add(row); await session.flush()
    return row

def prison_remaining(row,now=None):
    return max(0,int((row.prison_until-(now or _now())).total_seconds())) if row and row.prison_until else 0

def clue_list(row): return _loads(row.clues_json,[])

def _clear_threat(row):
    row.threat_key=None; row.threat_expires_at=None; row.clue_order_json="[]"; row.clues_json="[]"; row.threat_roll_bp=0

def _new_threat(row,heat:int):
    # Heat changes weighting: raids become more common, but the actual pick remains hidden and persisted.
    pool=["paper_trail","camera_net","tactical_raid"]
    if heat>=70: pool += ["tactical_raid","camera_net"]
    elif heat>=55: pool += ["camera_net"]
    key=secrets.choice(pool); row.threat_key=key; row.threat_expires_at=_now()+timedelta(hours=P.THREAT_TTL_HOURS)
    true=list(P.THREATS[key]["clues"])
    other=secrets.choice([k for k in P.THREAT_ORDER if k!=key])
    # Two reliable clues and one plausible false lead; order is frozen in DB.
    clues=[true[0],true[1],secrets.choice(P.THREATS[other]["clues"])]
    secrets.SystemRandom().shuffle(clues); row.clue_order_json=_dumps(clues); row.clues_json="[]"
    row.threat_roll_bp=secrets.randbelow(10_000)

def ensure_threat(row,heat:int):
    now=_now()
    if row.threat_key and row.threat_expires_at and row.threat_expires_at<=now:
        _clear_threat(row)
    if P.threat_required(heat) and not row.threat_key:
        _new_threat(row,heat)
    return row.threat_key

async def snapshot(session,uid:int):
    player=await DS.get_player(session,uid); blocked=DS.access_message(player)
    if blocked:return False,blocked,{}
    profile=await DS.get_profile(session,uid,create=True); DS.apply_recovery(profile)
    row=await get_hideout(session,uid,create=True)
    if row.prison_until and row.prison_until<=_now(): row.prison_until=None
    ensure_threat(row,int(profile.heat or 0))
    clues=clue_list(row); from app.services import dark_world_npc_service as NPS; recruits=(await NPS.team_context(session,uid))["keys"]
    chances={}
    if row.threat_key:
        for action in P.ACTION_ORDER:
            chances[action]=P.action_chance(row.threat_key,action,heat=int(profile.heat or 0),hideout_level=int(row.level),clue_count=len(clues),has_fixer="fixer" in recruits)
    return True,"ok",{"player":player,"profile":profile,"hideout":row,"clues":clues,"chances":chances,"prison_remaining":prison_remaining(row)}

async def recon(session,uid:int):
    ok,msg,state=await snapshot(session,uid)
    if not ok:return False,msg
    profile,row=state["profile"],state["hideout"]
    if not row.threat_key:return False,"در حال حاضر تهدید فعالی برای شناسایی وجود ندارد."
    clues=clue_list(row); order=_loads(row.clue_order_json,[])
    if len(clues)>=min(P.MAX_CLUES,len(order)):return False,"همه سرنخ‌های موجود جمع‌آوری شده‌اند؛ حالا باید تصمیم بگیری."
    if int(profile.intel or 0)<P.RECON_INTEL_COST:return False,"برای شناسایی حداقل ۱ اطلاعات لازم است."
    profile.intel=int(profile.intel or 0)-P.RECON_INTEL_COST; clues.append(order[len(clues)]); row.clues_json=_dumps(clues)
    await session.commit(); return True,f"🔎 سرنخ تازه: {clues[-1]}"

async def upgrade_hideout(session,uid:int):
    ok,msg,state=await snapshot(session,uid)
    if not ok:return False,msg
    player,profile,row=state["player"],state["profile"],state["hideout"]
    level=int(row.level or 1)
    if level>=5:return False,"مخفیگاه به بالاترین سطح رسیده است."
    spec=P.hideout(level); cost=int(spec["upgrade_cost"]); need=int(spec["influence"])
    if int(profile.influence or 0)<need:return False,f"برای ارتقا {need:,} نفوذ لازم است."
    if int(player.cash or 0)<cost:return False,f"هزینه ارتقا {cost:,} است و پول کافی نداری."
    player.cash=int(player.cash or 0)-cost; row.level=level+1; row.integrity=100
    await session.commit(); return True,f"✅ مخفیگاه به سطح {row.level} — {P.hideout(row.level)['name']} ارتقا یافت."

async def buy_forged_id(session,uid:int):
    ok,msg,state=await snapshot(session,uid)
    if not ok:return False,msg
    player,row=state["player"],state["hideout"]
    if int(row.forged_ids or 0)>=P.FORGED_ID_MAX:return False,"حداکثر سه هویت جعلی می‌توانی نگه داری."
    if int(player.cash or 0)<P.FORGED_ID_COST:return False,f"قیمت هویت جعلی {P.FORGED_ID_COST:,} است."
    player.cash=int(player.cash or 0)-P.FORGED_ID_COST; row.forged_ids=int(row.forged_ids or 0)+1
    await session.commit(); return True,f"🎭 هویت جعلی ساخته شد؛ موجودی {row.forged_ids}/{P.FORGED_ID_MAX}."

async def execute_plan(session,uid:int,action_key:str):
    ok,msg,state=await snapshot(session,uid)
    if not ok:return False,msg,{}
    player,profile,row=state["player"],state["profile"],state["hideout"]
    action=P.get_action(action_key)
    if not action or not row.threat_key:return False,"نقشه یا تهدید معتبر نیست.",{}
    if prison_remaining(row):return False,"در زندان هستی؛ ابتدا نقشه فرار را انتخاب کن.",{}
    cash=int(action.get("cash",0)); energy=int(action.get("energy",0)); intel=int(action.get("intel",0)); ids=int(action.get("forged_id",0))
    if int(player.cash or 0)<cash:return False,f"برای این نقشه {cash:,} پول لازم است.",{}
    if int(profile.energy or 0)<energy:return False,f"برای این نقشه {energy} انرژی لازم است.",{}
    if int(profile.intel or 0)<intel:return False,f"برای این نقشه {intel} اطلاعات لازم است.",{}
    if int(row.forged_ids or 0)<ids:return False,"هویت جعلی نداری.",{}
    player.cash=int(player.cash or 0)-cash; profile.energy=int(profile.energy or 0)-energy; profile.intel=int(profile.intel or 0)-intel; row.forged_ids=int(row.forged_ids or 0)-ids
    threat_key=str(row.threat_key); clues=clue_list(row); from app.services import dark_world_npc_service as NPS; recruits=(await NPS.team_context(session,uid))["keys"]
    roll=int(row.threat_roll_bp)/100
    result=P.resolve_action(threat_key,action_key,roll,heat=int(profile.heat or 0),hideout_level=int(row.level),clue_count=len(clues),has_fixer="fixer" in recruits)
    profile.heat=int(P.clamp(int(profile.heat or 0)+int(result["heat_delta"]),0,D.HEAT_MAX)); row.integrity=int(P.clamp(int(row.integrity or 100)+int(result["integrity_delta"]),0,100))
    if result["success"]: row.evaded_count=int(row.evaded_count or 0)+1
    else: row.failed_evades=int(row.failed_evades or 0)+1
    if result["jailed"]: row.prison_until=_now()+timedelta(minutes=P.PRISON_MINUTES); row.prison_mode=threat_key; profile.heat=max(70,int(profile.heat or 0))
    session.add(DarkWorldPursuitLog(owner_id=int(uid),threat_key=threat_key,action_key=action_key,clue_count=len(clues),success=bool(result["success"]),chance_bp=int(round(result["chance"]*100)),roll_bp=int(round(roll*100)),heat_delta=int(result["heat_delta"]),jailed=bool(result["jailed"])))
    _clear_threat(row)
    await session.commit()
    return True,"ok",{"result":result,"threat":P.THREATS[threat_key],"action":action,"heat":int(profile.heat),"integrity":int(row.integrity),"roll":roll}

ESCAPES={
 "tunnel":{"name":"تونل خدماتی","cash":140_000_000,"intel":0,"chance":78,"heat_success":-18,"heat_fail":4},
 "papers":{"name":"جعل حکم آزادی","cash":45_000_000,"intel":4,"chance":68,"heat_success":-24,"heat_fail":8},
 "riot":{"name":"شورش کنترل‌شده","cash":0,"intel":0,"chance":48,"heat_success":-30,"heat_fail":15},
}
async def escape_prison(session,uid:int,strategy:str):
    ok,msg,state=await snapshot(session,uid)
    if not ok:return False,msg,{}
    player,profile,row=state["player"],state["profile"],state["hideout"]
    if not prison_remaining(row):return False,"زندان فعالی نداری.",{}
    plan=ESCAPES.get(strategy)
    if not plan:return False,"نقشه فرار نامعتبر است.",{}
    if int(player.cash or 0)<plan["cash"]:return False,f"برای این نقشه {plan['cash']:,} پول لازم است.",{}
    if int(profile.intel or 0)<plan["intel"]:return False,f"برای این نقشه {plan['intel']} اطلاعات لازم است.",{}
    player.cash=int(player.cash or 0)-plan["cash"]; profile.intel=int(profile.intel or 0)-plan["intel"]
    chance=P.clamp(plan["chance"]+(int(row.level)-1)*3-max(0,int(profile.heat)-80)*.2,15,92); roll=secrets.randbelow(10_000)/100; success=roll<chance
    delta=plan["heat_success"] if success else plan["heat_fail"]; profile.heat=int(P.clamp(int(profile.heat)+delta,0,100))
    if success: row.prison_until=None; row.prison_mode=None
    else: row.prison_until=(row.prison_until or _now())+timedelta(minutes=10)
    session.add(DarkWorldPursuitLog(owner_id=int(uid),threat_key=str(row.prison_mode or "prison"),action_key=f"escape:{strategy}",clue_count=0,success=success,chance_bp=int(round(chance*100)),roll_bp=int(round(roll*100)),heat_delta=int(delta),jailed=not success))
    await session.commit(); return True,"ok",{"success":success,"plan":plan,"chance":chance,"roll":roll,"heat":int(profile.heat),"remaining":prison_remaining(row)}
