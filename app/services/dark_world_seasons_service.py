# -*- coding: utf-8 -*-
"""Stage 87.9 — lazy, restart-safe collective narrative seasons."""
from __future__ import annotations
from datetime import datetime,timedelta
from sqlalchemy import select,func
from app.data import dark_world_seasons as S
from app.models.dark_world import DarkWorldSeason,DarkWorldFactionMember,DarkWorldSeasonVote,DarkWorldFactionScore,DarkWorldSeasonLog
from app.services import dark_world_service as DS

def now():return datetime.utcnow()
async def _new(session,number):
 t=now();x=DarkWorldSeason(season_no=int(number),title=f"شب بی‌تاج #{number}",status="active",chapter_index=0,chapter_ends_at=t+timedelta(hours=S.SEASON_HOURS_PER_CHAPTER),market_bias=0,finance_bias=0,raid_bias=0,created_at=t);session.add(x);await session.flush()
 for k in S.FACTION_ORDER:session.add(DarkWorldFactionScore(season_id=x.id,faction_key=k,points=0))
 await session.flush();return x
async def ensure(session):
 x=(await session.execute(select(DarkWorldSeason).where(DarkWorldSeason.status=="active").order_by(DarkWorldSeason.id.desc()))).scalar_one_or_none()
 if not x:
  last=(await session.execute(select(DarkWorldSeason).order_by(DarkWorldSeason.id.desc()).limit(1))).scalar_one_or_none()
  if last and last.status=="completed" and last.completed_at and last.completed_at>now()-timedelta(hours=24):return last
  x=await _new(session,1 if not last else int(last.season_no)+1)
 await advance(session,x);return x
async def advance(session,x):
 while x.status=="active" and x.chapter_ends_at<=now():
  votes=list((await session.execute(select(DarkWorldSeasonVote).where(DarkWorldSeasonVote.season_id==x.id,DarkWorldSeasonVote.chapter_index==x.chapter_index))).scalars());chapter=S.chapter(x.chapter_index);tally={k:0 for k in chapter['choices']}
  for v in votes:tally[v.choice_key]=tally.get(v.choice_key,0)+int(v.weight or 1)
  winner=max(tally,key=lambda k:(tally[k],-list(chapter['choices']).index(k)));effect=chapter['choices'][winner];m=S.apply_choice(x.market_bias,x.finance_bias,x.raid_bias,effect);x.market_bias=m['market_pct'];x.finance_bias=m['finance'];x.raid_bias=m['raid'];x.last_choice_key=winner;session.add(DarkWorldSeasonLog(season_id=x.id,chapter_index=x.chapter_index,event_key="chapter_resolved",detail_key=winner,value=tally[winner]));x.chapter_index+=1
  if x.chapter_index>=S.CHAPTER_COUNT:
   x.status="completed";x.completed_at=now();scores=await board(session,x.id);x.winning_faction=scores[0].faction_key if scores else S.FACTION_ORDER[0];break
  x.chapter_ends_at=x.chapter_ends_at+timedelta(hours=S.SEASON_HOURS_PER_CHAPTER)
 await session.flush()
async def member(session,uid,season_id):return (await session.execute(select(DarkWorldFactionMember).where(DarkWorldFactionMember.owner_id==int(uid),DarkWorldFactionMember.season_id==int(season_id)))).scalar_one_or_none()
async def join(session,uid,key):
 if key not in S.FACTIONS:return False,"جناح نامعتبر است."
 player=await DS.get_player(session,uid);blocked=DS.access_message(player)
 if blocked:return False,blocked
 season=await ensure(session)
 if season.status!="active":return False,"این فصل پایان یافته است."
 if await member(session,uid,season.id):return False,"در این فصل قبلاً جناح انتخاب کرده‌ای."
 session.add(DarkWorldFactionMember(owner_id=int(uid),season_id=season.id,faction_key=key,contribution=0,reward_claimed=False,joined_at=now()));await session.commit();return True,f"به {S.FACTIONS[key]['name']} پیوستی؛ جناح تا پایان فصل قفل است."
async def vote(session,uid,choice):
 season=await ensure(session)
 if season.status!="active":return False,"رأی‌گیری فصل بسته شده است."
 chapter=S.chapter(season.chapter_index)
 if choice not in chapter['choices']:return False,"انتخاب نامعتبر است."
 mem=await member(session,uid,season.id)
 if not mem:return False,"ابتدا یک جناح انتخاب کن."
 p=await DS.get_profile(session,uid,True);weight=S.vote_weight(p.influence);row=(await session.execute(select(DarkWorldSeasonVote).where(DarkWorldSeasonVote.season_id==season.id,DarkWorldSeasonVote.chapter_index==season.chapter_index,DarkWorldSeasonVote.owner_id==int(uid)))).scalar_one_or_none()
 if row:row.choice_key=choice;row.weight=weight
 else:session.add(DarkWorldSeasonVote(season_id=season.id,chapter_index=season.chapter_index,owner_id=int(uid),faction_key=mem.faction_key,choice_key=choice,weight=weight))
 score=(await session.execute(select(DarkWorldFactionScore).where(DarkWorldFactionScore.season_id==season.id,DarkWorldFactionScore.faction_key==mem.faction_key))).scalar_one();score.points=int(score.points or 0)+weight;await session.commit();return True,f"رأی ثبت شد؛ وزن رأی براساس نفوذ: {weight}."
async def contribute(session,uid,kind):
 season=await ensure(session);mem=await member(session,uid,season.id)
 if season.status!="active" or not mem:return False,"برای کمک باید عضو جناح فعال باشی."
 p=await DS.get_profile(session,uid,True)
 if kind=="intel":
  if int(p.intel or 0)<S.INTEL_CONTRIBUTION:return False,"Intel کافی نداری."
  p.intel=int(p.intel or 0)-S.INTEL_CONTRIBUTION;points=20
 elif kind=="dirty":
  from app.services import dark_world_finance_service as FS
  a=await FS.account(session,uid)
  if int(a.dirty_balance or 0)<S.DIRTY_CONTRIBUTION:return False,"پول کثیف کافی نداری."
  a.dirty_balance=int(a.dirty_balance or 0)-S.DIRTY_CONTRIBUTION;points=30
 else:return False,"نوع کمک نامعتبر است."
 mem.contribution=int(mem.contribution or 0)+points;score=(await session.execute(select(DarkWorldFactionScore).where(DarkWorldFactionScore.season_id==season.id,DarkWorldFactionScore.faction_key==mem.faction_key))).scalar_one();score.points=int(score.points or 0)+points;session.add(DarkWorldSeasonLog(season_id=season.id,chapter_index=season.chapter_index,event_key="contribution",detail_key=kind,value=points));await session.commit();return True,f"کمک ثبت شد؛ {points} امتیاز جناحی."
async def board(session,season_id):return list((await session.execute(select(DarkWorldFactionScore).where(DarkWorldFactionScore.season_id==int(season_id)).order_by(DarkWorldFactionScore.points.desc(),DarkWorldFactionScore.faction_key))).scalars())
async def state(session,uid):
 season=await ensure(session);mem=await member(session,uid,season.id);scores=await board(session,season.id);return season,mem,scores
async def modifiers(session,uid):
 season=await ensure(session);mem=await member(session,uid,season.id);f=S.FACTIONS.get(mem.faction_key,{}) if mem else {}
 return {"market_pct":int(season.market_bias or 0)+int(f.get('market_pct',0)),"finance":int(season.finance_bias or 0)+int(f.get('finance',0)),"raid":int(season.raid_bias or 0)+int(f.get('raid',0)),"recon":int(f.get('recon',0))}
async def claim(session,uid):
 season=await ensure(session);mem=await member(session,uid,season.id)
 if season.status!="completed" or not mem:return False,"پاداشی برای دریافت وجود ندارد."
 if mem.reward_claimed:return False,"پاداش فصل را قبلاً گرفته‌ای."
 winner=mem.faction_key==season.winning_faction;dirty=250_000_000 if winner else 50_000_000;intel=20 if winner else 5
 from app.services import dark_world_finance_service as FS
 await FS.credit_dirty(session,uid,dirty,"season");p=await DS.get_profile(session,uid,True);p.intel=min(999,int(p.intel or 0)+intel);mem.reward_claimed=True;await session.commit();return True,f"پاداش فصل: {dirty:,} پول کثیف و {intel} Intel."
