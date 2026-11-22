# -*- coding: utf-8 -*-
"""v1.7.9.6 — سرویس آمار لیگ فوتبال: به‌روزرسانی جدول پس از هر مسابقه + جدول مرتب."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from app.models.football import FootballClub
from app.models.football_standing import FootballStanding


def _iso_week() -> str:
    y, w, _ = datetime.utcnow().isocalendar()
    return f"{y}-W{w:02d}"


async def get_or_create(session, club: FootballClub) -> FootballStanding:
    row = await session.get(FootballStanding, int(club.id))
    if row is None:
        row = FootballStanding(club_id=int(club.id), owner_id=int(club.owner_id), club_name=club.name)
        session.add(row)
        await session.flush()
    return row


async def update_standing(session, club: FootballClub, gf: int, ga: int) -> None:
    """پس از هر مسابقه: بازی/برد/مساوی/باخت + گل + امتیاز (۳/۱/۰) + امتیاز هفتگی."""
    row = await get_or_create(session, club)
    # ریست هفتگی تنبل
    wk = _iso_week()
    if row.week_key != wk:
        row.week_key = wk
        row.weekly_points = 0
    row.club_name = club.name
    row.owner_id = int(club.owner_id)
    row.played = int(row.played or 0) + 1
    row.goals_for = int(row.goals_for or 0) + int(gf)
    row.goals_against = int(row.goals_against or 0) + int(ga)
    if gf > ga:
        row.wins = int(row.wins or 0) + 1
        pts = 3
    elif gf == ga:
        row.draws = int(row.draws or 0) + 1
        pts = 1
    else:
        row.losses = int(row.losses or 0) + 1
        pts = 0
    row.points = int(row.points or 0) + pts
    row.weekly_points = int(row.weekly_points or 0) + pts
    await session.flush()


def goal_diff(row: FootballStanding) -> int:
    return int(row.goals_for or 0) - int(row.goals_against or 0)


async def league_table(session, limit: int = 30) -> list[FootballStanding]:
    """جدول مرتب مثل جدول واقعی: امتیاز ← تفاضل گل ← گل‌زده."""
    rows = list((await session.execute(select(FootballStanding))).scalars().all())
    rows.sort(key=lambda r: (int(r.points or 0), goal_diff(r), int(r.goals_for or 0)), reverse=True)
    return rows[:limit]
