# -*- coding: utf-8 -*-
"""Stage 87.8 — multiplayer raid forming, support and atomic resolution."""
from __future__ import annotations
import secrets
from datetime import datetime,timedelta
from types import SimpleNamespace
from sqlalchemy import select,update,func,or_
from app.data import dark_world as D
from app.data import dark_world_raids as R
from app.models.player import Player
from app.models.dark_world import DarkWorldRaidDefense,DarkWorldRecon,DarkWorldRaid,DarkWorldRaidParticipant,DarkWorldRaidLog
from app.services import dark_world_service as DS

def now():return datetime.utcnow()
async def defense(session,uid,create=True):
 row=await session.get(DarkWorldRaidDefense,int(uid))
 if row is None and create:row=DarkWorldRaidDefense(owner_id=int(uid),doctrine_key="fortify");session.add(row);await session.flush()
 return row
async def set_defense(session,uid,key):
 if key not in R.DEFENSES:return False,"آرایش نامعتبر است."
 p=await DS.get_player(session,uid);blocked=DS.access_message(p)
 if blocked:return False,blocked
 row=await defense(session,uid);row.doctrine_key=key;row.updated_at=now();await session.commit();return True,f"آرایش {R.DEFENSES[key]['name']} فعال شد."
async def targets(session,uid):return list((await session.execute(select(Player).where(Player.tg_user_id!=int(uid),Player.level>=D.ACCESS_LEVEL).order_by(Player.level.desc(),Player.id.desc()).limit(12))).scalars())
async def recon(session,uid,target_id):
 if int(uid)==int(target_id):return False,"نمی‌توانی خودت را شناسایی کنی.",None
 attacker=await DS.get_player(session,uid);target=await DS.get_player(session,target_id)
 if not target or int(target.level or 0)<D.ACCESS_LEVEL:return False,"هدف معتبر نیست.",None
 ap=await DS.get_profile(session,uid,True);DS.apply_recovery(ap)
 if int(ap.intel or 0)<R.RECON_INTEL_COST:return False,f"برای شناسایی {R.RECON_INTEL_COST} Intel لازم است.",None
 ap.intel=int(ap.intel or 0)-R.RECON_INTEL_COST;actual=(await defense(session,target_id)).doctrine_key
 from app.services import dark_world_seasons_service as SES
 mods=await SES.modifiers(session,uid);truth=secrets.randbelow(100)<min(95,60+int(ap.intel or 0)//5+mods["recon"]);observed=actual if truth else next(k for k in R.DEFENSE_ORDER if k!=actual)
 row=(await session.execute(select(DarkWorldRecon).where(DarkWorldRecon.attacker_id==int(uid),DarkWorldRecon.target_id==int(target_id)))).scalar_one_or_none();exp=now()+timedelta(hours=R.RECON_TTL_HOURS)
 if row:row.observed_defense=observed;row.truthful=truth;row.expires_at=exp;row.created_at=now()
 else:row=DarkWorldRecon(attacker_id=int(uid),target_id=int(target_id),observed_defense=observed,truthful=truth,expires_at=exp);session.add(row)
 await session.commit();return True,"گزارش شناسایی آماده شد.",row
async def create(session,uid,target_id,approach):
 if approach not in R.APPROACHES or int(uid)==int(target_id):return False,"طرح حمله نامعتبر است.",None
 attacker=await DS.get_player(session,uid);target=await DS.get_player(session,target_id);blocked=DS.access_message(attacker)
 if blocked:return False,blocked,None
 if not target or int(target.level or 0)<D.ACCESS_LEVEL:return False,"هدف به دنیای سیاه دسترسی ندارد.",None
 rec=(await session.execute(select(DarkWorldRecon).where(DarkWorldRecon.attacker_id==int(uid),DarkWorldRecon.target_id==int(target_id),DarkWorldRecon.expires_at>now()).order_by(DarkWorldRecon.id.desc()))).scalar_one_or_none()
 if not rec:return False,"ابتدا گزارش شناسایی تازه بگیر.",None
 since=now()-timedelta(hours=24);daily=(await session.execute(select(func.count()).select_from(DarkWorldRaid).where(DarkWorldRaid.attacker_id==int(uid),DarkWorldRaid.created_at>=since))).scalar() or 0
 if daily>=R.DAILY_RAID_LIMIT:return False,"سقف سه شبیخون در ۲۴ ساعت پر شده است.",None
 pair_since=now()-timedelta(hours=R.PAIR_COOLDOWN_HOURS);pair=(await session.execute(select(func.count()).select_from(DarkWorldRaid).where(DarkWorldRaid.attacker_id==int(uid),DarkWorldRaid.defender_id==int(target_id),DarkWorldRaid.created_at>=pair_since))).scalar() or 0
 if pair:return False,"این هدف هنوز در کول‌داون شبیخون است.",None
 from app.services import dark_world_finance_service as FS
 wallet=await FS.account(session,uid)
 if int(wallet.dirty_balance or 0)<R.STAKE:return False,f"برای وثیقه حمله {R.STAKE:,} پول کثیف لازم است.",None
 wallet.dirty_balance=int(wallet.dirty_balance or 0)-R.STAKE;doctrine=(await defense(session,target_id)).doctrine_key;t=now();raid=DarkWorldRaid(attacker_id=int(uid),defender_id=int(target_id),approach_key=approach,defense_key=doctrine,status="forming",stake=R.STAKE,recon_truthful=bool(rec.truthful),attack_support_count=0,defense_support_count=0,created_at=t,lock_at=t+timedelta(seconds=R.FORMING_SECONDS));session.add(raid);await session.flush();session.add(DarkWorldRaidLog(raid_id=raid.id,actor_id=int(uid),event_key="created",side="attack",amount=R.STAKE));await session.commit();return True,f"شبیخون #{raid.id} ساخته شد؛ ۱۰ دقیقه برای پیوستن هم‌پیمانان.",raid
async def lobby(session):
 rows=list((await session.execute(select(DarkWorldRaid).where(DarkWorldRaid.status=="forming").order_by(DarkWorldRaid.created_at.desc()).limit(15))).scalars());out=[]
 for x in rows:
  a=await DS.get_player(session,x.attacker_id);d=await DS.get_player(session,x.defender_id);x.attacker_name=a.name if a else str(x.attacker_id);x.defender_name=d.name if d else str(x.defender_id);out.append(x)
 return out
async def get_raid(session,rid):return await session.get(DarkWorldRaid,int(rid))
async def participants(session,rid):return list((await session.execute(select(DarkWorldRaidParticipant).where(DarkWorldRaidParticipant.raid_id==int(rid)))).scalars())
async def join(session,uid,rid,side):
 if side not in ("attack","defense"):return False,"سمت نامعتبر است."
 raid=await get_raid(session,rid)
 if not raid or raid.status!="forming" or raid.lock_at<=now():return False,"مهلت پیوستن تمام شده است."
 if int(uid) in (int(raid.attacker_id),int(raid.defender_id)):return False,"فرماندهان اصلی نمی‌توانند دوباره به نبرد بپیوندند."
 player=await DS.get_player(session,uid);blocked=DS.access_message(player)
 if blocked:return False,blocked
 exists=(await session.execute(select(DarkWorldRaidParticipant).where(DarkWorldRaidParticipant.raid_id==int(rid),DarkWorldRaidParticipant.user_id==int(uid)))).scalar_one_or_none()
 if exists:return False,"قبلاً در این نبرد عضو شده‌ای."
 p=await DS.get_profile(session,uid,True);DS.apply_recovery(p)
 if int(p.intel or 0)<R.SUPPORT_INTEL_COST:return False,f"برای پشتیبانی {R.SUPPORT_INTEL_COST} Intel لازم است."
 col=DarkWorldRaid.attack_support_count if side=="attack" else DarkWorldRaid.defense_support_count
 result=await session.execute(update(DarkWorldRaid).where(DarkWorldRaid.id==int(rid),DarkWorldRaid.status=="forming",DarkWorldRaid.lock_at>now(),col<R.MAX_SUPPORTERS_PER_SIDE).values({col:col+1}))
 if result.rowcount!=1:await session.rollback();return False,"ظرفیت این سمت پر شده یا مهلت تمام شده است."
 p.intel=int(p.intel or 0)-R.SUPPORT_INTEL_COST;session.add(DarkWorldRaidParticipant(raid_id=int(rid),user_id=int(uid),side=side,intel_spent=R.SUPPORT_INTEL_COST));session.add(DarkWorldRaidLog(raid_id=int(rid),actor_id=int(uid),event_key="joined",side=side,amount=0));await session.commit();return True,"به نبرد پیوستی؛ نتیجه پس از قفل‌شدن مشخص می‌شود."
async def resolve(session,uid,rid):
 raid=await get_raid(session,rid)
 if not raid or raid.status!="forming":return False,"این نبرد قابل حل نیست.",raid
 if raid.lock_at>now():return False,f"هنوز {int((raid.lock_at-now()).total_seconds())//60+1} دقیقه تا قفل نبرد مانده.",raid
 result=await session.execute(update(DarkWorldRaid).where(DarkWorldRaid.id==int(rid),DarkWorldRaid.status=="forming",DarkWorldRaid.lock_at<=now()).values(status="resolving"))
 if result.rowcount!=1:await session.rollback();return False,"حل هم‌زمان توسط درخواست دیگری انجام شد.",raid
 aplayer=await DS.get_player(session,raid.attacker_id);dplayer=await DS.get_player(session,raid.defender_id);ap=await DS.get_profile(session,raid.attacker_id,True);dp=await DS.get_profile(session,raid.defender_id,True)
 from app.services import dark_world_pursuit_service as PS
 from app.services import dark_world_npc_service as NS
 from app.services import dark_world_finance_service as FS
 hide=await PS.get_hideout(session,raid.defender_id,True);at=await NS.team_context(session,raid.attacker_id);dt=await NS.team_context(session,raid.defender_id)
 ch=R.chance(raid.approach_key,raid.defense_key,attacker_level=aplayer.level,defender_level=dplayer.level,attacker_influence=ap.influence,defender_influence=dp.influence,hideout_level=hide.level,hideout_integrity=hide.integrity,attack_team=at['effectiveness'],defense_team=dt['effectiveness'],attack_support=raid.attack_support_count,defense_support=raid.defense_support_count,recon_truth=raid.recon_truthful)
 from app.services import dark_world_seasons_service as SES
 am=await SES.modifiers(session,raid.attacker_id);dm=await SES.modifiers(session,raid.defender_id);ch=max(8,min(92,ch+am["raid"]-dm["raid"]))
 roll=secrets.randbelow(10_000);target_wallet=await FS.account(session,raid.defender_id);out=R.resolve(ch,roll/100,raid.stake,target_wallet.dirty_balance);members=await participants(session,rid);attackers=[x for x in members if x.side=="attack"];defenders=[x for x in members if x.side=="defense"]
 attacker_wallet=await FS.account(session,raid.attacker_id);defender_wallet=target_wallet
 if out['success']:
  target_wallet.dirty_balance=max(0,int(target_wallet.dirty_balance or 0)-out['stolen']);support_pool=round(out['stolen']*.20) if attackers else 0;attacker_wallet.dirty_balance=int(attacker_wallet.dirty_balance or 0)+out['stake_refund']+out['stolen']-support_pool
  for x in attackers:(await FS.account(session,x.user_id)).dirty_balance+=support_pool//len(attackers)
  hide.integrity=max(0,int(hide.integrity or 0)-(18 if raid.approach_key=='assault' else 10));ap.influence=int(ap.influence or 0)+12;dp.influence=max(0,int(dp.influence or 0)-6)
 else:
  support_pool=round(out['defense_pool']*.30) if defenders else 0;defender_wallet.dirty_balance=int(defender_wallet.dirty_balance or 0)+out['defense_pool']-support_pool
  for x in defenders:(await FS.account(session,x.user_id)).dirty_balance+=support_pool//len(defenders)
  ap.influence=max(0,int(ap.influence or 0)-8);dp.influence=int(dp.influence or 0)+8
 ap.heat=min(100,int(ap.heat or 0)+R.APPROACHES[raid.approach_key]['heat']+(6 if not out['success'] else 0));raid.status="attacker_won" if out['success'] else "defender_won";raid.chance_bp=int(round(ch*100));raid.roll_bp=roll;raid.stolen_amount=out['stolen'];raid.resolved_at=now();session.add(DarkWorldRaidLog(raid_id=raid.id,actor_id=int(uid),event_key=raid.status,side="system",amount=out['stolen'] or out['defense_pool']));await NS.apply_mission_wear(session,raid.attacker_id,4,bool(out['success']));await NS.apply_mission_wear(session,raid.defender_id,3,not bool(out['success']));await session.commit();return True,("⚔️ مهاجم پیروز شد." if out['success'] else "🛡️ مدافع حمله را دفع کرد.")+f"\n🎲 شانس {ch:.2f}٪ · رول {roll/100:.2f}\n🌑 غنیمت: {out['stolen']:,}",raid
async def mine(session,uid):return list((await session.execute(select(DarkWorldRaid).where(or_(DarkWorldRaid.attacker_id==int(uid),DarkWorldRaid.defender_id==int(uid))).order_by(DarkWorldRaid.id.desc()).limit(15))).scalars())
