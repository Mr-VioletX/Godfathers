# -*- coding: utf-8 -*-
"""فصلِ بازطراحی‌شده‌ی القابِ بچ ۵."""
from __future__ import annotations
import json
from datetime import datetime, timedelta
from sqlalchemy import delete, select
from app.models.player import Player
from app.models.title import PlayerStats, PlayerTitle, TitleClaim, TitleProfile, TitleSeason, TitleApproval, TitleWeekBaseline

CASH_CAP = 10_000_000_000
START_DELAY = timedelta(days=7)

async def bootstrap(session):
    season = await session.get(TitleSeason, 1)
    if season is None:
        season = TitleSeason(id=1, starts_at=datetime.utcnow() + START_DELAY, migration_done=False)
        session.add(season); await session.flush()
    if not season.migration_done:
        # حذف قطعی تمام لقب‌های کسب‌شده/یونیکِ قدیمی؛ لقب سفارشیِ اشتراکی باقی می‌ماند.
        await session.execute(delete(PlayerTitle)); await session.execute(delete(TitleClaim)); await session.execute(delete(TitleApproval))
        profiles = (await session.execute(select(TitleProfile))).scalars().all()
        for pr in profiles:
            pr.active_title_key = None
            pr.active_kind = "custom" if pr.custom_title and pr.subscription_active() else None
        players = (await session.execute(select(Player))).scalars().all()
        for player in players:
            if int(player.cash or 0) > CASH_CAP: player.cash = CASH_CAP
        season.migration_done = True
        await session.flush()
    return season

async def season_is_live(session) -> bool:
    season = await bootstrap(session)
    return bool(season.active and datetime.utcnow() >= season.starts_at)

async def queue(session, uid:int, key:str, source="auto") -> bool:
    pending = await session.scalar(select(TitleApproval.id).where(TitleApproval.tg_user_id==uid, TitleApproval.title_key==key, TitleApproval.status=="pending"))
    if pending: return False
    session.add(TitleApproval(tg_user_id=uid, title_key=key, source=source)); await session.flush(); return True

async def begin_week(session):
    season = await bootstrap(session); now=datetime.utcnow()
    if season.unique_week_started_at and now - season.unique_week_started_at < timedelta(days=7): return season.unique_week_started_at
    season.unique_week_started_at = now
    await session.execute(delete(TitleWeekBaseline))
    rows=(await session.execute(select(PlayerStats))).scalars().all()
    for st in rows:
        data={c.name:int(getattr(st,c.name) or 0) for c in PlayerStats.__table__.columns if c.name not in {"tg_user_id","updated_at","created_at"}}
        session.add(TitleWeekBaseline(tg_user_id=st.tg_user_id, week_started_at=now, stats_json=json.dumps(data)))
    await session.flush(); return now

async def weekly_unique_candidates(session, titles):
    # تنها پس از کامل‌شدن هفته؛ هر لقبِ تک به نفرِ دارای بزرگ‌ترین پیشرفتِ شرطش پیشنهاد می‌شود.
    season=await bootstrap(session); now=datetime.utcnow()
    if not season.unique_week_started_at: await begin_week(session); return []
    if now-season.unique_week_started_at < timedelta(days=7): return []
    baselines={x.tg_user_id:json.loads(x.stats_json or "{}") for x in (await session.execute(select(TitleWeekBaseline))).scalars().all()}
    stats=(await session.execute(select(PlayerStats))).scalars().all(); out=[]
    for title in titles:
        if not title.get("unique") or not title.get("stat"): continue
        stat=title["stat"]; ranked=[]
        for st in stats:
            val=int(getattr(st,stat,0) or 0); delta=val-int(baselines.get(st.tg_user_id,{}).get(stat,0) or 0)
            if delta>0 and val>=int(title.get("value") or 0): ranked.append((delta, val, st.tg_user_id))
        if ranked:
            ranked.sort(reverse=True); out.append((ranked[0][2], title["key"]))
    await begin_week(session); return out
