# -*- coding: utf-8 -*-
"""v1.7.9.9 — سرویس لیگ جمعهٔ رسمی (F4): ثبت‌نام تا پنجشنبه + دوری رفت‌وبرگشت جمعه + جوایز.

جوایز (تأیید امیر): دلار بازی + XP سرمربی + طرفدار. قهرمان بیشترین سهم را می‌گیرد.
"""
from __future__ import annotations

import random
from datetime import datetime

from sqlalchemy import func, select

from app.models.football import FootballClub
from app.models.football_friday import FootballLeagueEntry, FootballLeagueFixture, FootballLeagueSeason

MIN_TEAMS = 4
MAX_TEAMS = 24
# جوایز قهرمان (به‌ازای هر تیمِ شرکت‌کننده)
CHAMPION_CASH_PER_TEAM = 500_000      # دلار بازی
RUNNER_CASH_PER_TEAM = 200_000
CHAMPION_FANS = 5_000
RUNNER_FANS = 2_000


def _iso_week_tehran() -> str:
    try:
        from app.data.news import now_tehran
        d = now_tehran().date()
    except Exception:
        d = datetime.utcnow().date()
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"


def _is_friday_tehran() -> bool:
    try:
        from app.data.news import now_tehran
        return now_tehran().weekday() == 4  # جمعه
    except Exception:
        return datetime.utcnow().weekday() == 4


# --------------------------- فصلِ جاری ---------------------------
async def current_season(session, create: bool = True) -> FootballLeagueSeason | None:
    wk = _iso_week_tehran()
    row = (await session.execute(
        select(FootballLeagueSeason).where(FootballLeagueSeason.week_key == wk)
        .order_by(FootballLeagueSeason.id.desc())
    )).scalars().first()
    if row is None and create:
        row = FootballLeagueSeason(week_key=wk, status="registration")
        session.add(row)
        await session.flush()
    return row


async def latest_completed_season(session, week_key: str | None = None) -> FootballLeagueSeason | None:
    query = select(FootballLeagueSeason).where(FootballLeagueSeason.status == "done")
    if week_key:
        query = query.where(FootballLeagueSeason.week_key == str(week_key))
    return (await session.execute(
        query.order_by(FootballLeagueSeason.id.desc())
    )).scalars().first()


async def is_registered(session, season_id: int, club_id: int) -> bool:
    return (await session.execute(
        select(FootballLeagueEntry.id).where(
            FootballLeagueEntry.season_id == season_id, FootballLeagueEntry.club_id == int(club_id)
        )
    )).scalar_one_or_none() is not None


async def register(session, club: FootballClub) -> tuple[bool, str]:
    """ثبت‌نام در لیگ این هفته — فقط تا پنجشنبه (قبل از شروع جمعه)."""
    season = await current_season(session, create=True)
    if season.status != "registration":
        return False, "ثبت‌نام این هفته بسته شده — لیگ در جریان است."
    if _is_friday_tehran():
        return False, "امروز جمعه است — ثبت‌نام تا پنجشنبه بود. هفته‌ی بعد ثبت‌نام کن."
    cnt = int((await session.execute(
        select(func.count()).select_from(FootballLeagueEntry).where(FootballLeagueEntry.season_id == season.id)
    )).scalar() or 0)
    if cnt >= MAX_TEAMS:
        return False, f"لیگ پر است (حداکثر {MAX_TEAMS} تیم)."
    if await is_registered(session, season.id, club.id):
        return False, "قبلاً در لیگ این هفته ثبت‌نام کرده‌ای."
    session.add(FootballLeagueEntry(season_id=season.id, club_id=club.id, owner_id=int(club.owner_id), club_name=club.name))
    season.team_count = cnt + 1
    await session.flush()
    return True, f"✅ در لیگ جمعهٔ این هفته ثبت‌نام شدی ({cnt+1} تیم). بازی‌ها جمعه انجام می‌شود."


async def entries(session, season_id: int) -> list[FootballLeagueEntry]:
    return list((await session.execute(
        select(FootballLeagueEntry).where(FootballLeagueEntry.season_id == season_id)
    )).scalars().all())


async def record_live_result(session, season_id: int, home_id: int, away_id: int, hg: int, ag: int) -> None:
    """ثبت نتیجهٔ یک بازی زنده در جدول فصل."""
    for cid, gf, ga in ((home_id, hg, ag), (away_id, ag, hg)):
        e = (await session.execute(select(FootballLeagueEntry).where(
            FootballLeagueEntry.season_id == int(season_id), FootballLeagueEntry.club_id == int(cid)
        ))).scalars().first()
        if e is not None:
            await _record(e, gf, ga)
    await session.flush()


async def standings(session, season_id: int) -> list[FootballLeagueEntry]:
    rows = await entries(session, season_id)
    rows.sort(key=lambda r: (
        -int(r.points or 0),
        -(int(r.goals_for or 0) - int(r.goals_against or 0)),
        -int(r.goals_for or 0),
        int(r.club_id),
    ))
    return rows


# --------------------------- تولید فیکسچر (دوری رفت‌وبرگشت) ---------------------------
def _round_robin(club_ids: list[int]) -> list[tuple[int, int, int]]:
    """(round_no, home, away) — هر تیم با هر تیم ۲ بار (رفت و برگشت). الگوریتم دایره‌ای."""
    teams = list(club_ids)
    if len(teams) % 2 == 1:
        teams.append(-1)  # استراحت
    n = len(teams)
    fixtures: list[tuple[int, int, int]] = []
    rounds = n - 1
    arr = teams[:]
    rnd = 0
    for _ in range(rounds):
        rnd += 1
        for i in range(n // 2):
            home, away = arr[i], arr[n - 1 - i]
            if home != -1 and away != -1:
                fixtures.append((rnd, home, away))
        arr = [arr[0]] + [arr[-1]] + arr[1:-1]
    # برگشت (خانه/مهمان برعکس)
    back = [(rnd + rounds, a, h) for (rnd, h, a) in fixtures]
    return fixtures + back


async def generate_fixtures(session, season: FootballLeagueSeason) -> int:
    ent = await entries(session, season.id)
    ids = [int(e.club_id) for e in ent]
    if len(ids) < MIN_TEAMS:
        return 0
    names = {int(e.club_id): e.club_name for e in ent}
    # سیدبندی ساده بر اساس ثبت (۳ سبد) — برای تعادل فیکسچر
    random.Random(season.id).shuffle(ids)
    for rnd, home, away in _round_robin(ids):
        session.add(FootballLeagueFixture(
            season_id=season.id, round_no=rnd, home_club_id=home, away_club_id=away,
            home_name=names.get(home, "?"), away_name=names.get(away, "?"),
        ))
    season.status = "fixtures"
    await session.flush()
    return len(ids)


# --------------------------- شبیه‌سازی بازی ---------------------------
def _sim_goals(rng: random.Random, power_a: int, power_b: int) -> tuple[int, int]:
    ratio = power_a / max(1, power_a + power_b)
    import math
    def pois(lam):
        L = math.exp(-lam); k = 0; p = 1.0
        while p > L:
            k += 1; p *= rng.random()
        return k - 1
    xg_a = 0.6 + 2.2 * (ratio ** 1.2)
    xg_b = 0.6 + 2.2 * ((1 - ratio) ** 1.2)
    return min(6, pois(xg_a)), min(6, pois(xg_b))


async def _club_power(session, club_id: int) -> int:
    from app.services import football_service as FS
    club = await session.get(FootballClub, int(club_id))
    if club is None:
        return 1
    cards = await FS.squad(session, club.id)
    return max(1, FS.team_power(session, club, cards))


async def _record(entry: FootballLeagueEntry, gf: int, ga: int) -> None:
    entry.played = int(entry.played or 0) + 1
    entry.goals_for = int(entry.goals_for or 0) + gf
    entry.goals_against = int(entry.goals_against or 0) + ga
    if gf > ga:
        entry.wins = int(entry.wins or 0) + 1; entry.points = int(entry.points or 0) + 3
    elif gf == ga:
        entry.draws = int(entry.draws or 0) + 1; entry.points = int(entry.points or 0) + 1
    else:
        entry.losses = int(entry.losses or 0) + 1


async def run_league(session, bot=None) -> tuple[bool, str]:
    """اجرای لیگ جمعه: تولید فیکسچر (اگر نشده) + شبیه‌سازی همهٔ بازی‌ها + جوایز."""
    season = await current_season(session, create=False)
    if season is None:
        return False, "لیگی برای این هفته نیست."
    if season.status == "done":
        return False, "لیگ این هفته قبلاً برگزار شده."
    if season.status == "registration":
        n = await generate_fixtures(session, season)
        if n < MIN_TEAMS:
            return False, f"تیم‌های کافی ثبت‌نام نکردند ({n}/{MIN_TEAMS}) — لیگ این هفته لغو شد."
    ent = {int(e.club_id): e for e in await entries(session, season.id)}
    fixtures = list((await session.execute(
        select(FootballLeagueFixture).where(
            FootballLeagueFixture.season_id == season.id, FootballLeagueFixture.played == False
        )
    )).scalars().all())
    rng = random.Random(season.id * 7919)
    powers = {}
    for cid in ent:
        powers[cid] = await _club_power(session, cid)
    for fx in fixtures:
        hg, ag = _sim_goals(rng, powers.get(fx.home_club_id, 1), powers.get(fx.away_club_id, 1))
        fx.home_goals, fx.away_goals, fx.played = hg, ag, True
        await _record(ent[fx.home_club_id], hg, ag)
        await _record(ent[fx.away_club_id], ag, hg)
        # XP سرمربی برای برد رسمی + به‌روزرسانی جدول دائمی
        try:
            from app.services import football_league as FLG
            home_club = await session.get(FootballClub, int(fx.home_club_id))
            away_club = await session.get(FootballClub, int(fx.away_club_id))
            if home_club:
                await FLG.update_standing(session, home_club, hg, ag)
            if away_club:
                await FLG.update_standing(session, away_club, ag, hg)
        except Exception:
            pass
    await session.flush()
    # قهرمان + جوایز
    table = await standings(session, season.id)
    if table:
        champ = table[0]
        season.champion_club_id = champ.club_id
        season.status = "done"
        n = len(table)
        await _award(session, champ, CHAMPION_CASH_PER_TEAM * n, CHAMPION_FANS, coach_xp=10, title="🏆 قهرمان لیگ")
        if n > 1:
            await _award(session, table[1], RUNNER_CASH_PER_TEAM * n, RUNNER_FANS, coach_xp=5, title="🥈 نایب‌قهرمان")
        await session.flush()
        if bot is not None:
            await _announce_champion(bot, champ, n)
        return True, f"✅ لیگ جمعه تمام شد — قهرمان: {champ.club_name} ({int(champ.points)} امتیاز)"
    season.status = "done"
    await session.flush()
    return False, "لیگ بدون نتیجه بسته شد."


async def _award(session, entry: FootballLeagueEntry, cash: int, fans: int, coach_xp: int, title: str) -> None:
    from app.handlers.profile import get_player   # 🐞 v1.8.1.6 — ماژول profile_service وجود نداشت؛ جوایز قهرمان هرگز پرداخت نمی‌شد
    club = await session.get(FootballClub, int(entry.club_id))
    if club is None:
        return
    player = await get_player(session, int(entry.owner_id))
    if player is not None:
        player.cash = int(getattr(player, "cash", 0) or 0) + int(cash)
    club.fans = int(club.fans or 0) + int(fans)
    club.coach_level = min(100, int(club.coach_level or 1) + max(1, coach_xp // 3))
    await session.flush()


async def _announce_champion(bot, champ: FootballLeagueEntry, n: int) -> None:
    try:
        await bot.send_message(int(champ.owner_id), f"🏆 تبریک! باشگاهِ «{champ.club_name}» قهرمان لیگ جمعه شد ({int(champ.points)} امتیاز از {n} تیم). جایزه: دلار بازی + XP سرمربی + طرفدار")
    except Exception:
        pass


async def my_season_status(session, club_id: int) -> FootballLeagueEntry | None:
    season = await current_season(session, create=False)
    if season is None:
        return None
    return (await session.execute(
        select(FootballLeagueEntry).where(
            FootballLeagueEntry.season_id == season.id, FootballLeagueEntry.club_id == int(club_id)
        )
    )).scalars().first()


# --------------------------- تیک جمعه (زمان‌بند) ---------------------------
async def friday_tick(session, bot) -> None:
    """اگر جمعه است و لیگ این هفته هنوز برگزار نشده → اجرا می‌شود."""
    try:
        if not _is_friday_tehran():
            return
        season = await current_season(session, create=False)
        if season is None or season.status == "done":
            return
        await run_league(session, bot)
    except Exception:
        pass


import asyncio as _asyncio
from app.database.engine import async_session as _async_session


async def friday_loop(bot) -> None:
    """هر ۵ دقیقه چک می‌کند؛ اگر جمعه است و لیگ برگزار نشده → اجرا می‌شود."""
    while True:
        try:
            async with _async_session() as session:
                await friday_tick(session, bot)
                await session.commit()
        except Exception:
            pass
        await _asyncio.sleep(300)
