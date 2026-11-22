import json
from datetime import datetime,timedelta
from sqlalchemy import select, func
from app.models.activity import PlayerActivityLog
from app.models.player import Player
async def log_activity(session, player=None, *, tg_user_id=None, action_key='event', title='فعالیت', amount=0, before_value=None, after_value=None, meta=None, commit=False):
    rec=PlayerActivityLog(player_id=getattr(player,'id',None), tg_user_id=getattr(player,'tg_user_id',tg_user_id), action_key=action_key,title=title,amount=int(amount or 0),before_value=before_value,after_value=after_value,meta=json.dumps(meta or {},ensure_ascii=False) if meta is not None else None)
    session.add(rec)
    if commit: await session.commit()
    return rec
def since_24h(): return datetime.utcnow()-timedelta(hours=24)
async def top_recent_players(session, limit=20):
    rows=(await session.execute(select(PlayerActivityLog.tg_user_id,func.count(PlayerActivityLog.id),func.sum(PlayerActivityLog.amount)).where(PlayerActivityLog.created_at>=since_24h()).group_by(PlayerActivityLog.tg_user_id).order_by(func.count(PlayerActivityLog.id).desc()).limit(limit))).all()
    out=[]
    for tg,cnt,sm in rows:
        if tg is None: continue
        p=(await session.execute(select(Player).where(Player.tg_user_id==tg))).scalar_one_or_none(); out.append((tg, getattr(p,'name','—') if p else '—', cnt or 0, sm or 0))
    return out
async def recent_for_user(session,tg_user_id:int,limit=30):
    return (await session.execute(select(PlayerActivityLog).where(PlayerActivityLog.tg_user_id==tg_user_id,PlayerActivityLog.created_at>=since_24h()).order_by(PlayerActivityLog.created_at.desc()).limit(limit))).scalars().all()
