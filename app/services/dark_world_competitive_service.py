# -*- coding: utf-8 -*-
from __future__ import annotations
import secrets
from datetime import datetime,timedelta
from types import SimpleNamespace
from sqlalchemy import select,func,or_
from app.data import dark_world_competitive as C
from app.models.dark_world import (DarkWorldSeason,DarkWorldFactionMember,DarkWorldSeasonRank,DarkWorldCompetitiveProfile,DarkWorldCompetitiveReward,DarkWorldBalanceSnapshot,DarkWorldWorldBoss,DarkWorldBossHit,DarkWorldShipment,DarkWorldLaunderingJob,DarkWorldRaid,DarkWorldRaidParticipant,DarkWorldEmploymentContract,DarkWorldFinanceLog,DarkWorldMarketTrade)
from app.services import dark_world_service as DS
from app.services import dark_world_seasons_service as SS

def now():return datetime.utcnow()
async def boss(session,season):
 b=(await session.execute(select(DarkWorldWorldBoss).where(DarkWorldWorldBoss.season_id==season.id))).scalar_one_or_none()
 members=(await session.execute(select(func.count()).select_from(DarkWorldFactionMember).where(DarkWorldFactionMember.season_id==season.id))).scalar() or 0
 hp=C.boss_max_hp(members)
 if not b:
  b=DarkWorldWorldBoss(season_id=season.id,name="نگهبان شب",max_hp=hp,current_hp=hp,status="active",created_at=now());session.add(b);await session.flush()
 elif b.status=="active" and hp>int(b.max_hp):
  growth=hp-int(b.max_hp);b.max_hp=hp;b.current_hp=int(b.current_hp)+growth
 return b
async def _count(session,model,*conds):return int((await session.execute(select(func.count()).select_from(model).where(*conds))).scalar() or 0)
async def metrics(session,season,mem):
 uid=int(mem.owner_id);end=season.completed_at or now();start=season.created_at
 shipments=await _count(session,DarkWorldShipment,DarkWorldShipment.owner_id==uid,DarkWorldShipment.started_at>=start,DarkWorldShipment.started_at<=end,DarkWorldShipment.status=="completed")
 launders=await _count(session,DarkWorldLaunderingJob,DarkWorldLaunderingJob.owner_id==uid,DarkWorldLaunderingJob.started_at>=start,DarkWorldLaunderingJob.started_at<=end,DarkWorldLaunderingJob.status=="completed")
 attack_wins=await _count(session,DarkWorldRaid,DarkWorldRaid.attacker_id==uid,DarkWorldRaid.resolved_at>=start,DarkWorldRaid.resolved_at<=end,DarkWorldRaid.status=="attacker_won")
 defense_wins=await _count(session,DarkWorldRaid,DarkWorldRaid.defender_id==uid,DarkWorldRaid.resolved_at>=start,DarkWorldRaid.resolved_at<=end,DarkWorldRaid.status=="defender_won")
 support_wins=int((await session.execute(select(func.count()).select_from(DarkWorldRaidParticipant).join(DarkWorldRaid,DarkWorldRaid.id==DarkWorldRaidParticipant.raid_id).where(DarkWorldRaidParticipant.user_id==uid,DarkWorldRaidParticipant.joined_at>=start,DarkWorldRaid.resolved_at<=end,or_((DarkWorldRaidParticipant.side=="attack")&(DarkWorldRaid.status=="attacker_won"),(DarkWorldRaidParticipant.side=="defense")&(DarkWorldRaid.status=="defender_won"))))).scalar() or 0)
 employment=await _count(session,DarkWorldEmploymentContract,DarkWorldEmploymentContract.worker_id==uid,DarkWorldEmploymentContract.completed_at>=start,DarkWorldEmploymentContract.completed_at<=end,DarkWorldEmploymentContract.status=="completed")
 damage=int((await session.execute(select(func.coalesce(func.sum(DarkWorldBossHit.damage),0)).where(DarkWorldBossHit.season_id==season.id,DarkWorldBossHit.owner_id==uid))).scalar() or 0);p=await DS.get_profile(session,uid,True);raid_wins=attack_wins+defense_wins+support_wins
 s=C.score(influence=p.influence,contribution=mem.contribution,shipments=shipments,launders=launders,raid_wins=raid_wins,employment=employment,boss_damage=damage);return {**s,"influence":int(p.influence or 0),"contribution":int(mem.contribution or 0),"shipments":shipments,"launders":launders,"raid_wins":raid_wins,"employment":employment,"boss_damage":damage}
async def live_rows(session,season):
 members=list((await session.execute(select(DarkWorldFactionMember).where(DarkWorldFactionMember.season_id==season.id))).scalars());rows=[]
 for m in members:
  x=await metrics(session,season,m);rows.append(SimpleNamespace(owner_id=m.owner_id,faction_key=m.faction_key,rank=0,eligible=x['activity']>=C.MIN_RANK_ACTIVITY,division_key=C.division(x['score'])['name'],**x))
 rows.sort(key=lambda x:(not x.eligible,-x.score,-x.activity,x.owner_id))
 for i,x in enumerate(rows,1):x.rank=i
 return rows
async def telemetry(session,season):
 row=(await session.execute(select(DarkWorldBalanceSnapshot).where(DarkWorldBalanceSnapshot.season_id==season.id))).scalar_one_or_none()
 if row:return row
 start=season.created_at;end=season.completed_at or now();created=int((await session.execute(select(func.coalesce(func.sum(DarkWorldFinanceLog.amount),0)).where(DarkWorldFinanceLog.created_at>=start,DarkWorldFinanceLog.created_at<=end,DarkWorldFinanceLog.event_key.like("dirty:%")))).scalar() or 0);cleaned=int((await session.execute(select(func.coalesce(func.sum(DarkWorldLaunderingJob.clean_cash),0)).where(DarkWorldLaunderingJob.completed_at>=start,DarkWorldLaunderingJob.completed_at<=end))).scalar() or 0);confiscated=int((await session.execute(select(func.coalesce(func.sum(DarkWorldLaunderingJob.confiscated),0)).where(DarkWorldLaunderingJob.completed_at>=start,DarkWorldLaunderingJob.completed_at<=end))).scalar() or 0);market=int((await session.execute(select(func.coalesce(func.sum(DarkWorldMarketTrade.qty*DarkWorldMarketTrade.price_per_unit),0)).where(DarkWorldMarketTrade.created_at>=start,DarkWorldMarketTrade.created_at<=end))).scalar() or 0);factor=C.economy_factor(created,cleaned,confiscated,market)
 if season.status!="completed":return SimpleNamespace(season_id=season.id,dirty_created=created,cleaned=cleaned,confiscated=confiscated,market_volume=market,reward_factor_bp=round(factor*10000),created_at=now())
 row=DarkWorldBalanceSnapshot(season_id=season.id,dirty_created=created,cleaned=cleaned,confiscated=confiscated,market_volume=market,reward_factor_bp=round(factor*10000),created_at=now());session.add(row);await session.flush();return row
async def ensure_rankings(session,season):
 rows=list((await session.execute(select(DarkWorldSeasonRank).where(DarkWorldSeasonRank.season_id==season.id).order_by(DarkWorldSeasonRank.rank))).scalars())
 if rows or season.status!="completed":return rows
 live=await live_rows(session,season)
 for x in live:session.add(DarkWorldSeasonRank(season_id=season.id,owner_id=x.owner_id,faction_key=x.faction_key,rank=x.rank,score=x.score,division_key=x.division_key,eligible=x.eligible,activity=x.activity,shipments=x.shipments,launders=x.launders,raid_wins=x.raid_wins,employment=x.employment,boss_damage=x.boss_damage,influence_snapshot=x.influence,contribution_snapshot=x.contribution))
 await telemetry(session,season);await session.flush();return list((await session.execute(select(DarkWorldSeasonRank).where(DarkWorldSeasonRank.season_id==season.id).order_by(DarkWorldSeasonRank.rank))).scalars())
async def state(session,uid):
 season=await SS.ensure(session);rows=await ensure_rankings(session,season) if season.status=="completed" else await live_rows(session,season);b=await boss(session,season);mine=next((x for x in rows if int(x.owner_id)==int(uid)),None);reward=(await session.execute(select(DarkWorldCompetitiveReward).where(DarkWorldCompetitiveReward.season_id==season.id,DarkWorldCompetitiveReward.owner_id==int(uid)))).scalar_one_or_none();return season,rows,b,mine,reward
async def hit_boss(session,uid):
 season=await SS.ensure(session)
 if season.status!="active":return False,"این فصل پایان یافته است."
 mem=await SS.member(session,uid,season.id)
 if not mem:return False,"ابتدا عضو یکی از جناح‌ها شو."
 b=await boss(session,season)
 if b.status!="active" or int(b.current_hp)<=0:return False,"نگهبان شب شکست خورده است."
 last=(await session.execute(select(DarkWorldBossHit).where(DarkWorldBossHit.season_id==season.id,DarkWorldBossHit.owner_id==int(uid)).order_by(DarkWorldBossHit.id.desc()).limit(1))).scalar_one_or_none()
 if last and last.created_at>now()-timedelta(seconds=C.BOSS_HIT_COOLDOWN_SECONDS):return False,"ضربه بعدی هنوز آماده نیست."
 p=await DS.get_profile(session,uid,True);DS.apply_recovery(p)
 if int(p.energy or 0)<C.BOSS_ENERGY_COST:return False,"انرژی کافی نداری."
 from app.services import dark_world_npc_service as NS
 team=await NS.team_context(session,uid);roll=secrets.randbelow(100);damage=min(int(b.current_hp),C.boss_damage((await DS.get_player(session,uid)).level,team['effectiveness'],roll));p.energy=int(p.energy or 0)-C.BOSS_ENERGY_COST;b.current_hp=max(0,int(b.current_hp)-damage);session.add(DarkWorldBossHit(season_id=season.id,boss_id=b.id,owner_id=int(uid),damage=damage,roll=roll,created_at=now()))
 if b.current_hp<=0:b.status="defeated";b.defeated_at=now()
 await session.commit();return True,f"👁️ {damage:,} آسیب وارد شد؛ جان باقی‌مانده {int(b.current_hp):,}/{int(b.max_hp):,}."
async def claim(session,uid):
 season=await SS.ensure(session)
 if season.status!="completed":return False,"رتبه‌بندی نهایی هنوز بسته نشده است."
 rows=await ensure_rankings(session,season);mine=next((x for x in rows if int(x.owner_id)==int(uid)),None)
 if not mine or not mine.eligible:return False,f"حداقل {C.MIN_RANK_ACTIVITY} فعالیت رقابتی لازم است."
 exists=(await session.execute(select(DarkWorldCompetitiveReward).where(DarkWorldCompetitiveReward.season_id==season.id,DarkWorldCompetitiveReward.owner_id==int(uid)))).scalar_one_or_none()
 if exists:return False,"جایزه رقابتی را قبلاً گرفته‌ای."
 tele=await telemetry(session,season);eligible=sum(1 for x in rows if x.eligible);r=C.reward(mine.rank,eligible,int(tele.reward_factor_bp)/10000);from app.services import dark_world_finance_service as FS
 await FS.credit_dirty(session,uid,r['dirty'],"competitive");p=await DS.get_profile(session,uid,True);p.intel=min(999,int(p.intel or 0)+r['intel']);cp=await session.get(DarkWorldCompetitiveProfile,int(uid))
 if not cp:cp=DarkWorldCompetitiveProfile(owner_id=int(uid),rating=0,prestige=0,seasons=0);session.add(cp)
 cp.rating=round(int(cp.rating or 0)*.90)+r['prestige'];cp.prestige=int(cp.prestige or 0)+r['prestige'];cp.seasons=int(cp.seasons or 0)+1;cp.best_rank=mine.rank if not cp.best_rank else min(int(cp.best_rank),mine.rank);cp.last_title=r['title'];session.add(DarkWorldCompetitiveReward(season_id=season.id,owner_id=int(uid),rank=mine.rank,dirty_reward=r['dirty'],intel_reward=r['intel'],prestige_reward=r['prestige'],title_key=r['title'],claimed_at=now()));await session.commit();return True,f"🎁 رتبه {mine.rank}: {r['dirty']:,} پول کثیف، {r['intel']} Intel و {r['prestige']} اعتبار رقابتی."
async def hall(session):return list((await session.execute(select(DarkWorldCompetitiveProfile).order_by(DarkWorldCompetitiveProfile.rating.desc(),DarkWorldCompetitiveProfile.best_rank).limit(15))).scalars())
