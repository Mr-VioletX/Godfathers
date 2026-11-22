# -*- coding: utf-8 -*-
"""v1.7.10.0 — سرویس بازی زنده‌ی فوتبال: شروع، پیشروش زمان‌دار، گزارش زنده، پایان.

۱۰ دقیقهٔ واقعی = ۹۰ دقیقهٔ بازی. تیکر (هر ~۳۰ ثانیه) بازی‌های زنده را جلو می‌برد،
گل‌ها را در دقیقهٔ خودشان آشکار می‌کند و در پایان نتیجه را ثبت/جوایز را می‌دهد.
"""
from __future__ import annotations

import json
import math
import random
from datetime import datetime

from sqlalchemy import select

from app.models.football import FootballClub
from app.models.football_live import FootballLiveMatch

MATCH_REAL_SECONDS = 600   # ۱۰ دقیقهٔ واقعی
GAME_MINUTES = 90


def _game_minute(m: FootballLiveMatch, now: datetime | None = None) -> int:
    now = now or datetime.utcnow()
    elapsed = max(0.0, (now - m.started_at).total_seconds())
    return min(GAME_MINUTES, int(elapsed * GAME_MINUTES / MATCH_REAL_SECONDS))


async def _club_power(session, club_id: int) -> int:
    from app.services import football_service as FS
    club = await session.get(FootballClub, int(club_id))
    if club is None:
        return 1
    cards = await FS.squad(session, club.id)
    return max(1, FS.team_power(session, club, cards))


def _poisson(rng: random.Random, lam: float) -> int:
    L = math.exp(-lam); k = 0; p = 1.0
    while p > L:
        k += 1; p *= rng.random()
    return k - 1


def _gen_events(rng: random.Random, home_power: int, away_power: int, home_cards, away_cards,
                mh: float = 1.0, ma: float = 1.0) -> tuple[list, int, int]:
    """رویدادهای گل (دقیقه + سمت + گلزن) + نتیجهٔ نهایی. mh/ma = ضریب تاکتیک."""
    ratio = home_power / max(1, home_power + away_power)
    xg_h = (0.6 + 2.2 * (ratio ** 1.2)) * mh
    xg_a = (0.6 + 2.2 * ((1 - ratio) ** 1.2)) * ma
    hg = min(6, _poisson(rng, xg_h))
    ag = min(6, _poisson(rng, xg_a))

    def scorers(cards, n):
        attackers = [c for c in cards if c.pos in ("FWD", "MID")] or list(cards)
        return [rng.choice(attackers).name if attackers else "?" for _ in range(n)]

    events = []
    for minute, name in zip(sorted(rng.randint(2, 88) for _ in range(hg)), scorers(home_cards, hg)):
        events.append({"minute": minute, "side": "home", "scorer": name})
    for minute, name in zip(sorted(rng.randint(2, 88) for _ in range(ag)), scorers(away_cards, ag)):
        events.append({"minute": minute, "side": "away", "scorer": name})
    events.sort(key=lambda e: e["minute"])
    return events, hg, ag


async def _match_mod(session, club_id: int, own_power: int, opp_power: int) -> tuple[float, float]:
    """ضریب (گل‌زنیِ خود، گل‌زنیِ حریف) بر اساس تاکتیک؛ اتو ← بر اساس اختلاف قدرت."""
    try:
        from app.services import football_tactics as FT
        row = await FT.get(session, club_id)
        key = row.tactic
        if row.auto_enabled:
            key = "offensive" if own_power < opp_power else "defensive"
        t = FT.TACTICS.get(key, FT.TACTICS["balanced"])
        return float(t["xg_self"]), float(t["xg_opp"])
    except Exception:
        return 1.0, 1.0


async def start_match(session, home_club_id: int, away_club_id: int, mode: str = "friendly",
                      season_id: int | None = None, fixture_id: int | None = None,
                      rng: random.Random | None = None) -> FootballLiveMatch:
    """شروع یک بازی زنده — رویدادها از پیش ساخته و ذخیره می‌شوند."""
    from app.services import football_service as FS
    rng = rng or random.Random()
    home = await session.get(FootballClub, int(home_club_id))
    if home is None:
        raise ValueError("home club missing")
    away_name = "⚔️ تیم خیالی"
    away_cards = []
    if away_club_id:
        away = await session.get(FootballClub, int(away_club_id))
        away_name = away.name if away else "?"
        away_cards = await FS.squad(session, int(away_club_id))
    home_cards = await FS.squad(session, int(home_club_id))
    hp = await _club_power(session, home_club_id)
    ap = await _club_power(session, away_club_id) if away_club_id else max(1, int(hp * rng.uniform(0.75, 1.25)))
    # 🆕 v1.8.1.0 — تاکتیک: ضریب گل‌زنی هر تیم (خودکار بر اساس اختلاف قدرت اگر اتو فعال باشد)
    mh, h_opp = await _match_mod(session, home_club_id, hp, ap)
    if away_club_id:
        ma, a_opp = await _match_mod(session, away_club_id, ap, hp)
        mh *= a_opp      # تاکتیک دفاعی مهمان ← گل‌زدهٔ میزبان کمتر
        ma = ma * h_opp  # تاکتیک دفاعی میزبان ← گل‌زدهٔ مهمان کمتر
    else:
        ma = h_opp       # حریف بات: فقط اثر دفاعی میزبان
    events, hg, ag = _gen_events(rng, hp, ap, home_cards, away_cards, mh=mh, ma=ma)
    m = FootballLiveMatch(
        home_club_id=int(home_club_id), away_club_id=int(away_club_id or 0),
        home_name=home.name, away_name=away_name, mode=mode,
        season_id=season_id, fixture_id=fixture_id,
        events_json=json.dumps(events, ensure_ascii=False),
        status="live",
    )
    session.add(m)
    await session.flush()
    return m


def build_report(m: FootballLiveMatch, now: datetime | None = None) -> str:
    """گزارش زندهٔ فعلی (تا دقیقهٔ جاری)."""
    gm = _game_minute(m, now)
    try:
        events = json.loads(m.events_json or "[]")
    except Exception:
        events = []
    shown = events[: int(m.revealed or 0)]
    clock = "⏱️ پایان" if m.status == "done" or gm >= GAME_MINUTES else f"⏱️ دقیقه {gm}′"
    lines = [
        f"⚽ <b>{m.home_name}</b> {m.home_goals}-{m.away_goals} <b>{m.away_name}</b>",
        f"{clock}  |  {_mode_fa(m.mode)}",
        "",
    ]
    if shown:
        for e in shown:
            side = m.home_name if e["side"] == "home" else m.away_name
            lines.append(f"⚽ {e['minute']}′ — {e['scorer']} ({side})")
    else:
        lines.append("هنوز گلی زده نشده...")
    if m.status == "done" or gm >= GAME_MINUTES:
        res = "برد" if m.home_goals > m.away_goals else ("مساوی" if m.home_goals == m.away_goals else "باخت")
        lines += ["", f"🏁 نتیجهٔ نهایی: {m.home_goals}-{m.away_goals} ({res} برای {m.home_name})"]
    return "\n".join(lines)


def _mode_fa(mode: str) -> str:
    return {"friendly": "🤝 دوستانه", "league": "🏆 لیگ جمعه", "ucl": "🌟 لیگ قهرمانان"}.get(mode, mode)


async def tick(session, bot=None) -> None:
    """پیشروش همهٔ بازی‌های زنده: آشکارسازی گل‌ها در دقیقه‌شان + پایان در ۹۰."""
    now = datetime.utcnow()
    live = list((await session.execute(
        select(FootballLiveMatch).where(FootballLiveMatch.status == "live")
    )).scalars().all())
    for m in live:
        gm = _game_minute(m, now)
        try:
            events = json.loads(m.events_json or "[]")
        except Exception:
            events = []
        # آشکارسازی گل‌هایی که دقیقه‌شان رسیده
        rev = int(m.revealed or 0)
        changed = False
        while rev < len(events) and events[rev]["minute"] <= gm:
            e = events[rev]
            if e["side"] == "home":
                m.home_goals = int(m.home_goals or 0) + 1
            else:
                m.away_goals = int(m.away_goals or 0) + 1
            rev += 1
            changed = True
        m.revealed = rev
        # پایان
        if gm >= GAME_MINUTES:
            m.status = "done"
            await _finish(session, m, bot)
            changed = True
        if changed:
            await session.flush()


async def _finish(session, m: FootballLiveMatch, bot) -> None:
    """ثبت نتیجه در جدول/لیگ + اطلاع به دو طرف."""
    try:
        from app.services import football_league as FLG
        home = await session.get(FootballClub, int(m.home_club_id))
        if home:
            await FLG.update_standing(session, home, m.home_goals, m.away_goals)
        if m.away_club_id:
            away = await session.get(FootballClub, int(m.away_club_id))
            if away:
                await FLG.update_standing(session, away, m.away_goals, m.home_goals)
    except Exception:
        pass
    # 🆕 به‌روزرسانی جدول فصل (لیگ جمعه/UCL) بر اساس نتیجهٔ این بازی زنده
    if m.season_id and m.mode in ("league", "ucl"):
        try:
            if m.mode == "ucl":
                from app.services import football_ucl as FUCL
                await FUCL.record_live_result(session, int(m.season_id), int(m.home_club_id), int(m.away_club_id), int(m.home_goals), int(m.away_goals))
            else:
                from app.services import football_friday as FFRI
                await FFRI.record_live_result(session, int(m.season_id), int(m.home_club_id), int(m.away_club_id), int(m.home_goals), int(m.away_goals))
        except Exception:
            pass
    # اگر متعلق به فیکسچر لیگ/UCL است → مدلِ درست را علامت بزن.
    if m.fixture_id:
        try:
            if m.mode == "ucl":
                from app.models.football_ucl import FootballUclFixture as FixtureModel
            else:
                from app.models.football_friday import FootballLeagueFixture as FixtureModel
            fx = await session.get(FixtureModel, int(m.fixture_id))
            if fx is not None:
                fx.home_goals, fx.away_goals, fx.played = m.home_goals, m.away_goals, True
        except Exception:
            pass
    try:
        if m.mode == "friendly":
            from app.models.football import FootballMatch
            session.add(FootballMatch(home_club_id=int(m.home_club_id), away_club_id=0,
                                      home_goals=int(m.home_goals), away_goals=int(m.away_goals),
                                      mode="friendly", report=build_report(m)))
            await session.flush()
    except Exception:
        pass
    if bot is not None:
        for cid in (m.home_club_id, m.away_club_id):
            if not cid:
                continue
            try:
                club = await session.get(FootballClub, int(cid))
                if club:
                    await bot.send_message(int(club.owner_id), "🏁 بازی تمام شد:\n" + build_report(m))
            except Exception:
                pass


async def live_matches(session, mode: str | None = None) -> list[FootballLiveMatch]:
    q = select(FootballLiveMatch).where(FootballLiveMatch.status == "live")
    if mode:
        q = q.where(FootballLiveMatch.mode == mode)
    return list((await session.execute(q.order_by(FootballLiveMatch.id.desc()))).scalars().all())


async def my_live_match(session, uid: int) -> FootballLiveMatch | None:
    """بازی زنده‌ای که باشگاهِ این کاربر در آن است."""
    club = (await session.execute(select(FootballClub).where(FootballClub.owner_id == int(uid)))).scalar_one_or_none()
    if club is None:
        return None
    return (await session.execute(
        select(FootballLiveMatch).where(
            FootballLiveMatch.status == "live",
            (FootballLiveMatch.home_club_id == club.id) | (FootballLiveMatch.away_club_id == club.id),
        ).order_by(FootballLiveMatch.id.desc())
    )).scalars().first()


# --------------------------- حلقهٔ زمان‌بند ---------------------------
import asyncio as _asyncio
from app.database.engine import async_session as _async_session


async def live_loop(bot) -> None:
    """هر ۳۰ ثانیه بازی‌های زنده را جلو می‌برد."""
    while True:
        try:
            async with _async_session() as session:
                await tick(session, bot)
                await session.commit()
        except Exception:
            pass
        await _asyncio.sleep(30)


async def live_friendlies_today(session, uid: int) -> int:
    """تعداد بازی‌های زندهٔ دوستانهٔ امروز (به وقت تهران) برای سقف روزانه."""
    from datetime import timedelta
    try:
        from app.data.news import now_tehran
        day = now_tehran().date()
    except Exception:
        day = datetime.utcnow().date()
    start = datetime.combine(day, datetime.min.time())
    end = start + timedelta(days=1)
    club = (await session.execute(select(FootballClub).where(FootballClub.owner_id == int(uid)))).scalar_one_or_none()
    if club is None:
        return 0
    return int((await session.execute(
        select(__import__("sqlalchemy").func.count()).select_from(FootballLiveMatch).where(
            FootballLiveMatch.home_club_id == club.id,
            FootballLiveMatch.mode == "friendly",
            FootballLiveMatch.created_at >= start,
            FootballLiveMatch.created_at < end,
        )
    )).scalar() or 0)
