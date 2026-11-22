# -*- coding: utf-8 -*-
"""v1.8.2.8 — elite UCL fed exclusively by the previous Friday League.

The top eight in the latest completed Friday League are automatically invited.
There is no open registration path and no unrelated club can enter.
"""
from __future__ import annotations

import asyncio as _asyncio
from datetime import datetime

from sqlalchemy import func, select

from app.data import football_competitions as FC
from app.database.engine import async_session as _async_session
from app.models.football import FootballClub
from app.models.football_ucl import FootballUclEntry, FootballUclFixture, FootballUclSeason

MIN_TEAMS = FC.UCL_QUALIFIER_LIMIT
MAX_TEAMS = FC.UCL_QUALIFIER_LIMIT
GROUP_SIZE = 4
UCL_CHAMPION_CASH = 5_000_000
UCL_CHAMPION_FANS = 20_000


def _is_monday_tehran() -> bool:
    try:
        from app.data.news import now_tehran
        return now_tehran().weekday() == 0
    except Exception:
        return datetime.utcnow().weekday() == 0


async def _source_season(session, week_key: str | None = None):
    from app.services import football_friday as FFRI
    return await FFRI.latest_completed_season(session, week_key=week_key)


async def _source_table(session, source) -> list:
    if source is None:
        return []
    from app.services import football_friday as FFRI
    return await FFRI.standings(session, source.id)


async def _seed_qualifiers(session, season: FootballUclSeason, source) -> int:
    """Insert exactly the top-eight Friday teams; idempotent for retry safety."""
    table = await _source_table(session, source)
    qualifiers = FC.select_ucl_qualifiers(table)
    if not qualifiers:
        season.status = "cancelled"
        season.team_count = 0
        await session.flush()
        return 0

    existing = {
        int(row.club_id): row
        for row in (await session.execute(
            select(FootballUclEntry).where(FootballUclEntry.season_id == season.id)
        )).scalars().all()
    }
    for qualified in qualifiers:
        if int(qualified.club_id) in existing:
            continue
        session.add(FootballUclEntry(
            season_id=season.id,
            club_id=int(qualified.club_id),
            owner_id=int(qualified.owner_id),
            club_name=qualified.club_name,
        ))
    season.team_count = len(qualifiers)
    await session.flush()
    return len(qualifiers)


async def current_season(session, create: bool = True) -> FootballUclSeason | None:
    """Return the UCL edition bound to the latest completed Friday League."""
    source = await _source_season(session)
    if source is None:
        return None
    period_key = FC.ucl_period_key(source.week_key)
    row = (await session.execute(
        select(FootballUclSeason)
        .where(FootballUclSeason.period_key == period_key)
        .order_by(FootballUclSeason.id.desc())
    )).scalars().first()
    if row is None and create:
        row = FootballUclSeason(period_key=period_key, status="registration")
        session.add(row)
        await session.flush()
    if row is not None and create and row.status == "registration":
        await _seed_qualifiers(session, row, source)
    return row


async def qualification_status(
    session, club_id: int, season: FootballUclSeason | None = None
) -> dict[str, object]:
    """Return the club's authoritative rank/scope for the UCL screen."""
    source_week = FC.source_week_from_ucl_period(season.period_key) if season else None
    source = await _source_season(session, week_key=source_week)
    if source is None:
        return {
            "eligible": False, "rank": None, "source_week": None,
            "source_team_count": 0, "reason": "هنوز لیگ جمعهٔ تکمیل‌شده‌ای وجود ندارد.",
        }
    table = await _source_table(session, source)
    rank = next((index for index, row in enumerate(table, 1) if int(row.club_id) == int(club_id)), None)
    eligible = FC.is_ucl_rank_eligible(rank, len(table))
    if len(table) < FC.UCL_MIN_SOURCE_TEAMS:
        reason = f"لیگ جمعهٔ {source.week_key} فقط {len(table)} تیم داشت؛ حداقل ۸ تیم لازم است."
    elif rank is None:
        reason = f"باشگاه در لیگ جمعهٔ {source.week_key} شرکت نکرده است."
    elif eligible:
        reason = f"رتبهٔ {rank} لیگ جمعهٔ {source.week_key}؛ سهمیهٔ خودکار UCL."
    else:
        reason = f"رتبهٔ {rank} لیگ جمعهٔ {source.week_key}؛ فقط رتبه‌های ۱ تا ۸ صعود می‌کنند."
    return {
        "eligible": eligible,
        "rank": rank,
        "source_week": source.week_key,
        "source_team_count": len(table),
        "reason": reason,
    }


async def register(session, club: FootballClub) -> tuple[bool, str]:
    """Compatibility endpoint: enforce rank and recover a missing seeded entry."""
    season = await current_season(session, create=True)
    if season is None:
        return False, "هنوز لیگ جمعهٔ تکمیل‌شده‌ای برای تعیین سهمیه وجود ندارد."
    status = await qualification_status(session, club.id, season=season)
    if not status["eligible"]:
        return False, str(status["reason"])
    if season.status != "registration":
        return False, "فهرست سهمیه‌های این دوره بسته شده است."
    exists = (await session.execute(select(FootballUclEntry.id).where(
        FootballUclEntry.season_id == season.id,
        FootballUclEntry.club_id == club.id,
    ))).scalar_one_or_none()
    if exists:
        return False, "سهمیهٔ تو قبلاً به‌صورت خودکار از جدول لیگ جمعه ثبت شده است."
    session.add(FootballUclEntry(
        season_id=season.id,
        club_id=club.id,
        owner_id=int(club.owner_id),
        club_name=club.name,
    ))
    season.team_count = min(MAX_TEAMS, int(season.team_count or 0) + 1)
    await session.flush()
    return True, "✅ سهمیهٔ کسب‌شده از لیگ جمعه بازیابی و ثبت شد."


async def entries(session, season_id: int) -> list[FootballUclEntry]:
    return list((await session.execute(
        select(FootballUclEntry).where(FootballUclEntry.season_id == season_id)
    )).scalars().all())


async def draw_groups(session, season: FootballUclSeason) -> int:
    ent = await entries(session, season.id)
    if len(ent) != MIN_TEAMS:
        return 0

    # Seed by Friday rank and snake across two four-team groups.
    source_week = FC.source_week_from_ucl_period(season.period_key)
    source = await _source_season(session, week_key=source_week)
    source_table = await _source_table(session, source)
    source_rank = {int(row.club_id): rank for rank, row in enumerate(source_table, 1)}
    ent.sort(key=lambda row: source_rank.get(int(row.club_id), 999))
    group_numbers = FC.seeded_group_numbers(len(ent), GROUP_SIZE)
    for entry, group_no in zip(ent, group_numbers):
        entry.group_no = group_no

    from app.services.football_friday import _round_robin
    groups: dict[int, list] = {}
    for entry in ent:
        groups.setdefault(entry.group_no, []).append(entry)
    for group_no, members in groups.items():
        ids = [int(member.club_id) for member in members]
        names = {int(member.club_id): member.club_name for member in members}
        for _round, home, away in _round_robin(ids):
            session.add(FootballUclFixture(
                season_id=season.id,
                stage="group",
                home_club_id=home,
                away_club_id=away,
                home_name=names.get(home, "?"),
                away_name=names.get(away, "?"),
            ))
    season.status = "groups"
    await session.flush()
    return len(ent)


def _rec(entry: FootballUclEntry, goals_for: int, goals_against: int) -> None:
    entry.played = int(entry.played or 0) + 1
    entry.goals_for = int(entry.goals_for or 0) + goals_for
    entry.goals_against = int(entry.goals_against or 0) + goals_against
    if goals_for > goals_against:
        entry.wins = int(entry.wins or 0) + 1
        entry.points = int(entry.points or 0) + 3
    elif goals_for == goals_against:
        entry.draws = int(entry.draws or 0) + 1
        entry.points = int(entry.points or 0) + 1
    else:
        entry.losses = int(entry.losses or 0) + 1


async def group_table(session, season_id: int, group_no: int) -> list[FootballUclEntry]:
    rows = list((await session.execute(select(FootballUclEntry).where(
        FootballUclEntry.season_id == season_id,
        FootballUclEntry.group_no == group_no,
    ))).scalars().all())
    rows.sort(key=lambda row: (
        -int(row.points or 0),
        -(int(row.goals_for or 0) - int(row.goals_against or 0)),
        -int(row.goals_for or 0),
        int(row.club_id),
    ))
    return rows


async def record_live_result(
    session, season_id: int, home_id: int, away_id: int, home_goals: int, away_goals: int
) -> None:
    for club_id, goals_for, goals_against in (
        (home_id, home_goals, away_goals),
        (away_id, away_goals, home_goals),
    ):
        entry = (await session.execute(select(FootballUclEntry).where(
            FootballUclEntry.season_id == int(season_id),
            FootballUclEntry.club_id == int(club_id),
        ))).scalars().first()
        if entry is not None:
            _rec(entry, goals_for, goals_against)
    await session.flush()


async def advance_ucl(session, bot=None) -> None:
    """On Monday draw the earned top-eight places, then advance live fixtures."""
    season = await current_season(session, create=True)
    if season is None or season.status in ("done", "cancelled"):
        return
    from app.models.football_live import FootballLiveMatch
    from app.services import football_live as FLIVE

    if season.status == "registration":
        if not _is_monday_tehran():
            return
        number = await draw_groups(session, season)
        if number != MIN_TEAMS:
            season.status = "cancelled"
            await session.flush()
            return

    live_count = int((await session.execute(select(func.count()).select_from(FootballLiveMatch).where(
        FootballLiveMatch.season_id == season.id,
        FootballLiveMatch.status == "live",
        FootballLiveMatch.mode == "ucl",
    ))).scalar() or 0)
    if live_count > 0:
        return
    todo = list((await session.execute(select(FootballUclFixture).where(
        FootballUclFixture.season_id == season.id,
        FootballUclFixture.played == False,
    ))).scalars().all())
    if todo:
        live_map = {
            int(match.fixture_id)
            for match in (await session.execute(
                select(FootballLiveMatch).where(FootballLiveMatch.mode == "ucl")
            )).scalars().all()
            if match.fixture_id
        }
        started = 0
        for fixture in todo:
            if fixture.id in live_map:
                continue
            await FLIVE.start_match(
                session,
                fixture.home_club_id,
                fixture.away_club_id,
                mode="ucl",
                season_id=season.id,
                fixture_id=fixture.id,
            )
            started += 1
            if started >= 8:
                break
        await session.flush()
        return
    await _advance_stage(session, season, bot)


async def _advance_stage(session, season: FootballUclSeason, bot) -> None:
    ent = await entries(session, season.id)
    groups = sorted({entry.group_no for entry in ent})
    qualifiers = []
    for group_no in groups:
        qualifiers.extend((await group_table(session, season.id, group_no))[:2])
    for qualified in qualifiers:
        qualified.advanced = True
    qualifiers.sort(key=lambda row: (
        -int(row.points or 0),
        -(int(row.goals_for or 0) - int(row.goals_against or 0)),
        int(row.club_id),
    ))
    if qualifiers:
        champion = qualifiers[0]
        season.champion_club_id = champion.club_id
        await _award(session, champion)
        await session.flush()
        if bot is not None:
            try:
                await bot.send_message(
                    int(champion.owner_id),
                    f"🌟 تبریک! باشگاه «{champion.club_name}» قهرمان لیگ قهرمانان شد! "
                    f"جایزه: {UCL_CHAMPION_CASH:,}$ + {UCL_CHAMPION_FANS:,} طرفدار",
                )
            except Exception:
                pass
    season.status = "done"
    await session.flush()


async def _award(session, entry: FootballUclEntry) -> None:
    from app.handlers.profile import get_player
    club = await session.get(FootballClub, int(entry.club_id))
    if club is None:
        return
    player = await get_player(session, int(entry.owner_id))
    if player is not None:
        player.cash = int(getattr(player, "cash", 0) or 0) + UCL_CHAMPION_CASH
    club.fans = int(club.fans or 0) + UCL_CHAMPION_FANS
    club.coach_level = min(100, int(club.coach_level or 1) + 4)
    await session.flush()


async def my_status(session, club_id: int) -> FootballUclEntry | None:
    season = await current_season(session, create=False)
    if season is None:
        return None
    return (await session.execute(select(FootballUclEntry).where(
        FootballUclEntry.season_id == season.id,
        FootballUclEntry.club_id == int(club_id),
    ))).scalars().first()


async def ucl_loop(bot) -> None:
    while True:
        try:
            async with _async_session() as session:
                await advance_ucl(session, bot)
                await session.commit()
        except Exception:
            pass
        await _asyncio.sleep(300)
