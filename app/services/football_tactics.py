# -*- coding: utf-8 -*-
"""v1.8.1.0 — F6: سرویس ترکیب و تاکتیک فوتبال.

تاکتیک بر ضریب گل‌زنی (xG) در بازی‌های زنده اثر می‌گذارد:
- تهاجمی: گل بیشتر می‌زنی ولی بیشتر هم می‌خوری
- دفاعی: کمتر می‌زنی ولی کمتر هم می‌خوری
- متعادل: خنثی
اتو‌تاکتیک: وسط بازی (نیمهٔ دوم) بر اساسِ نتیجه، تاکتیک خودکار عوض می‌شود.
"""
from __future__ import annotations

from sqlalchemy import select

from app.models.football_tactics import FootballTactic

TACTICS = {
    "offensive": {"name": "⚔️ تهاجمی", "xg_self": 1.15, "xg_opp": 1.05},
    "balanced": {"name": "⚖️ متعادل", "xg_self": 1.0, "xg_opp": 1.0},
    "defensive": {"name": "🛡️ دفاعی", "xg_self": 0.92, "xg_opp": 0.85},
}


def tactic_name(key: str) -> str:
    return TACTICS.get(key, TACTICS["balanced"])["name"]


async def get(session, club_id: int) -> FootballTactic:
    row = await session.get(FootballTactic, int(club_id))
    if row is None:
        row = FootballTactic(club_id=int(club_id), tactic="balanced", auto_enabled=False)
        session.add(row)
        await session.flush()
    return row


async def set_tactic(session, club_id: int, tactic: str) -> FootballTactic:
    row = await get(session, club_id)
    if tactic in TACTICS:
        row.tactic = tactic
    await session.flush()
    return row


async def set_auto(session, club_id: int, on: bool) -> FootballTactic:
    row = await get(session, club_id)
    row.auto_enabled = bool(on)
    await session.flush()
    return row


async def modifiers(session, club_id: int) -> tuple[float, float]:
    """(xg_self, xg_opp) برای این باشگاه."""
    row = await get(session, club_id)
    t = TACTICS.get(row.tactic, TACTICS["balanced"])
    return float(t["xg_self"]), float(t["xg_opp"])
