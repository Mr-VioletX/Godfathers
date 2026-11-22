# -*- coding: utf-8 -*-
"""سرویسِ سیستمِ ورزشی (مرحله ۱۴).

وظایف:
  • ساختِ تیم/برند و برداشتِ پول (پیش‌نیازها + هزینه)
  • محاسبه‌ی قدرت (از روی شهرِ فعالِ بازیکن برای FanSupport)
  • شبیه‌سازیِ مسابقه (Upset + کارت‌های رویداد) + ثبتِ تاریخچه + جایزه
  • جدولِ لیگ + اعلانِ قهرمانِ روزانه
  • ایونتِ هفته
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.data import sports as S
from app.models.mafia_city import MafiaBuilding, MafiaCity  # 🆕 بچ ۴ — شهرسازِ جدید
from app.models.player import Player
from app.models.sports import RacingBrand, SportsMatch, SportsTeam


# ---------------------------------------------------------------------------
# کمکی‌ها
# ---------------------------------------------------------------------------
async def get_player(session: AsyncSession, uid: int) -> Player | None:
    return await session.scalar(select(Player).where(Player.tg_user_id == uid))


async def get_team(session: AsyncSession, uid: int, sport: str) -> SportsTeam | None:
    return await session.scalar(
        select(SportsTeam).where(
            SportsTeam.tg_user_id == uid, SportsTeam.sport == sport
        )
    )


async def get_brand(session: AsyncSession, uid: int, sport: str) -> RacingBrand | None:
    return await session.scalar(
        select(RacingBrand).where(
            RacingBrand.tg_user_id == uid, RacingBrand.sport == sport
        )
    )


async def list_teams(session: AsyncSession, uid: int) -> list[SportsTeam]:
    rows = await session.execute(
        select(SportsTeam).where(SportsTeam.tg_user_id == uid).order_by(SportsTeam.id)
    )
    return list(rows.scalars().all())


async def list_brands(session: AsyncSession, uid: int) -> list[RacingBrand]:
    rows = await session.execute(
        select(RacingBrand).where(RacingBrand.tg_user_id == uid).order_by(RacingBrand.id)
    )
    return list(rows.scalars().all())


async def _active_city(session: AsyncSession, uid: int) -> MafiaCity | None:
    """شهرِ بازیکن (برای FanSupport/تحصیلات). 🆕 بچ ۴: تک‌شهری."""
    return await session.scalar(
        select(MafiaCity).where(MafiaCity.tg_user_id == uid)
    )


async def team_fan_context(session: AsyncSession, uid: int) -> tuple[int, int]:
    """(رضایت، جمعیت) شهرِ فعال را برمی‌گرداند (یا پیش‌فرض)."""
    city = await _active_city(session, uid)
    if city is None:
        return 50, 20_000   # پیش‌فرضِ تیمِ بی‌شهر
    return int(city.satisfaction or 50), int(city.population or 0)


async def _avg_education(session: AsyncSession, uid: int) -> float:
    """سطحِ مدرسه/دانشگاهِ شهر (برای CarQuality). 🆕 بچ ۴: شهرسازِ جدید."""
    city = await _active_city(session, uid)
    if city is None:
        return 0.0
    rows = (await session.execute(
        select(MafiaBuilding).where(
            MafiaBuilding.city_id == city.id,
            MafiaBuilding.btype == "school",
        )
    )).scalars().all()
    if not rows:
        return 0.0
    return float(sum(int(b.qty or 0) for b in rows))


# ---------------------------------------------------------------------------
# محاسبه‌ی قدرت
# ---------------------------------------------------------------------------
async def compute_team_power(session: AsyncSession, team: SportsTeam) -> float:
    satisfaction, population = await team_fan_context(session, team.tg_user_id)
    return S.team_power(
        avg_player_lvl=team.avg_player_level,
        coach_lvl=team.coach_level,
        stadium_lvl=team.stadium_level,
        satisfaction=satisfaction,
        population=population,
        budget=team.budget,
    )


async def compute_brand_power(session: AsyncSession, brand: RacingBrand) -> float:
    edu = await _avg_education(session, brand.tg_user_id)
    return S.racing_power(
        driver_skill=brand.driver_skill,
        brand_level=brand.brand_level,
        tire_level=brand.tire_level,
        tech_level=brand.tech_level,
        avg_education_level=edu,
    )


# ---------------------------------------------------------------------------
# ایونتِ هفته
# ---------------------------------------------------------------------------
def current_event(now: datetime | None = None) -> dict:
    now = now or datetime.utcnow()
    return S.event_for_day(now)


# ---------------------------------------------------------------------------
# 🆕 پچ — محدودیتِ روزانه‌ی مسابقه (هر ورزش/هر بازیکن، به‌وقتِ تهران)
# ---------------------------------------------------------------------------
def _tehran_day_bounds_utc(now_utc: datetime | None = None) -> tuple[datetime, datetime]:
    """(شروع, پایان) روزِ جاری به‌وقتِ تهران، بازگردانده‌شده به UTCِ ساده (بدونِ tzinfo)."""
    from app.data import news as N

    now_utc = now_utc or datetime.utcnow()
    teh = N.now_tehran(now_utc)
    start_teh = teh.replace(hour=0, minute=0, second=0, microsecond=0)
    end_teh = start_teh + timedelta(days=1)
    if N.TEHRAN is not None:
        start_utc = N.TEHRAN.localize(start_teh).astimezone(timezone.utc).replace(tzinfo=None)
        end_utc = N.TEHRAN.localize(end_teh).astimezone(timezone.utc).replace(tzinfo=None)
    else:
        start_utc = start_teh - N.TEHRAN_OFFSET
        end_utc = end_teh - N.TEHRAN_OFFSET
    return start_utc, end_utc


async def matches_played_today(session: AsyncSession, uid: int, sport: str) -> int:
    """چند مسابقه از این ورزش، امروز (به‌وقتِ تهران) توسطِ این بازیکن بازی شده."""
    start_utc, end_utc = _tehran_day_bounds_utc()
    count = await session.scalar(
        select(func.count()).select_from(SportsMatch).where(
            SportsMatch.tg_user_id == uid,
            SportsMatch.sport == sport,
            SportsMatch.played_at >= start_utc,
            SportsMatch.played_at < end_utc,
        )
    )
    return int(count or 0)


async def seconds_until_daily_reset(now_utc: datetime | None = None) -> int:
    """ثانیه‌های باقی‌مانده تا نیمه‌شبِ بعدی به‌وقتِ تهران (ریست‌شدنِ سهمیه‌ی مسابقه)."""
    now_utc = now_utc or datetime.utcnow()
    _, end_utc = _tehran_day_bounds_utc(now_utc)
    return max(1, int((end_utc - now_utc).total_seconds()))


# ---------------------------------------------------------------------------
# شبیه‌سازیِ مسابقه‌ی تیمی (فوتبال/بسکتبال)
# ---------------------------------------------------------------------------
_STAR_NAMES = [
    "رونالدو", "مسی", "زیدان", "مارادونا", "نیمار",
    "لواندوفسکی", "مباپه", "حاجی‌صفی", "علی کریمی", "جوردن",
]


async def _make_bot_opponent(sport: str, base_power: float, rng: random.Random) -> tuple[str, float]:
    """حریفِ رباتی با قدرتِ نزدیک به تیمِ بازیکن (برای وقتی حریفِ واقعی نیست)."""
    names = {
        S.FOOTBALL: ["بارسلونا", "رئال", "میلان", "لیورپول", "پرسپولیس", "استقلال"],
        S.BASKETBALL: ["لیکرز", "بولز", "وریورز", "سلتیکس"],
        S.F1: ["فراری", "مرسدس", "ردبول", "مکلارن"],
        S.MOTO: ["دوکاتی", "یاماها", "هوندا", "ک‌تی‌ام"],
    }.get(sport, ["حریف"])
    name = rng.choice(names)
    # قدرتِ حریف ۸۰٪ تا ۱۲۰٪ قدرتِ بازیکن (متوازن)
    op = base_power * rng.uniform(0.8, 1.2)
    return name, max(1.0, round(op, 2))


async def play_team_match(
    session: AsyncSession, uid: int, sport: str, rng: random.Random | None = None
) -> dict | None:
    """یک مسابقه‌ی لیگ برای تیمِ فوتبال/بسکتبالِ بازیکن اجرا می‌کند."""
    rng = rng or random.Random()
    team = await get_team(session, uid, sport)
    if team is None:
        return None

    power_a = await compute_team_power(session, team)

    # حریف: یک تیمِ واقعیِ دیگر در همین ورزش یا حریفِ ربات
    others = (await session.execute(
        select(SportsTeam).where(
            SportsTeam.sport == sport, SportsTeam.tg_user_id != uid
        )
    )).scalars().all()
    opponent = rng.choice(others) if others else None

    if opponent is not None:
        power_b = await compute_team_power(session, opponent)
        team_b_name = opponent.name
        opp_uid = opponent.tg_user_id
        opp_sat, _ = await team_fan_context(session, opponent.tg_user_id)
    else:
        team_b_name, power_b = await _make_bot_opponent(sport, power_a, rng)
        opp_uid = None
        opp_sat = 50

    host_sat, _ = await team_fan_context(session, uid)
    ctx = S.MatchContext(host_is_a=True, host_satisfaction=host_sat)
    res = S.simulate_match(sport, power_a, power_b, ctx, rng)

    # جایزه + آمارِ لیگ
    event = current_event()
    if res.winner == "A":
        rkey, team.wins = "win", team.wins + 1
        team.points += S.WIN_POINTS
    elif res.winner == "draw":
        rkey, team.draws = "draw", team.draws + 1
        team.points += S.DRAW_POINTS
    else:
        rkey, team.losses = "loss", team.losses + 1

    prize = S.match_prize(sport, rkey)
    team.goals_for += res.score_a
    team.goals_against += res.score_b

    star = rng.choice(_STAR_NAMES) if res.score_a > 0 else None

    player = await get_player(session, uid)
    if player and prize:
        player.cash = int(player.cash or 0) + prize

    match = SportsMatch(
        tg_user_id=uid, sport=sport,
        team_a_name=team.name, team_b_name=team_b_name,
        opponent_user_id=opp_uid,
        score_a=res.score_a, score_b=res.score_b,
        result=res.winner, events=",".join(res.events) or None,
        prize=prize, star_player=star,
    )
    session.add(match)
    await session.commit()

    return {
        "team": team, "team_b_name": team_b_name,
        "power_a": power_a, "power_b": power_b,
        "result": res, "prize": prize, "star": star, "event": event,
    }


async def play_race(
    session: AsyncSession, uid: int, sport: str, rng: random.Random | None = None
) -> dict | None:
    """یک مسابقه‌ی F1/موتور برای برندِ بازیکن اجرا می‌کند."""
    rng = rng or random.Random()
    brand = await get_brand(session, uid, sport)
    if brand is None:
        return None

    power_a = await compute_brand_power(session, brand)
    others = (await session.execute(
        select(RacingBrand).where(
            RacingBrand.sport == sport, RacingBrand.tg_user_id != uid
        )
    )).scalars().all()
    opponent = rng.choice(others) if others else None
    if opponent is not None:
        power_b = await compute_brand_power(session, opponent)
        team_b_name = opponent.race_team_name or opponent.name
        opp_uid = opponent.tg_user_id
    else:
        team_b_name, power_b = await _make_bot_opponent(sport, power_a, rng)
        opp_uid = None

    ctx = S.MatchContext(host_is_a=True, host_satisfaction=50,
                         a_tech_bonus=brand.tech_level * 1.0)
    res = S.simulate_match(sport, power_a, power_b, ctx, rng)

    event = current_event()
    if res.winner == "A":
        rkey, brand.wins = "win", brand.wins + 1
        brand.points += S.WIN_POINTS
    elif res.winner == "draw":
        rkey = "draw"
        brand.points += S.DRAW_POINTS
    else:
        rkey, brand.losses = "loss", brand.losses + 1

    prize = S.match_prize(sport, rkey)
    player = await get_player(session, uid)
    if player and prize:
        player.cash = int(player.cash or 0) + prize

    match = SportsMatch(
        tg_user_id=uid, sport=sport,
        team_a_name=brand.race_team_name or brand.name, team_b_name=team_b_name,
        opponent_user_id=opp_uid,
        score_a=0, score_b=0,
        result=res.winner, events=",".join(res.events) or None,
        prize=prize, star_player=None,
    )
    session.add(match)
    await session.commit()

    return {
        "brand": brand, "team_b_name": team_b_name,
        "power_a": power_a, "power_b": power_b,
        "result": res, "prize": prize, "event": event,
    }


# ---------------------------------------------------------------------------
# جدولِ لیگ (رتبه‌بندیِ تیم‌های یک ورزش)
# ---------------------------------------------------------------------------
async def league_table(session: AsyncSession, sport: str, limit: int = 20) -> list[dict]:
    if sport in S.TEAM_SPORTS:
        rows = (await session.execute(
            select(SportsTeam).where(SportsTeam.sport == sport)
        )).scalars().all()
        table = [{
            "uid": t.tg_user_id, "name": t.name, "points": t.points,
            "wins": t.wins, "draws": t.draws, "losses": t.losses,
            "gd": t.goals_for - t.goals_against,
        } for t in rows]
        table.sort(key=lambda r: (r["points"], r["gd"]), reverse=True)
    else:
        rows = (await session.execute(
            select(RacingBrand).where(RacingBrand.sport == sport)
        )).scalars().all()
        table = [{
            "uid": b.tg_user_id, "name": b.race_team_name or b.name,
            "points": b.points, "wins": b.wins, "draws": 0, "losses": b.losses,
            "gd": 0,
        } for b in rows]
        table.sort(key=lambda r: r["points"], reverse=True)
    return table[:limit]


# ---------------------------------------------------------------------------
# ۵) نتایجِ مسابقاتِ اخیر (نمایش on-demand در بخشِ ایونت‌ها؛ بدونِ ارسالِ خودکار)
# ---------------------------------------------------------------------------
async def build_daily_announcement(session: AsyncSession, now: datetime | None = None) -> str | None:
    """متنِ اعلانِ روزانه را از مسابقاتِ ۲۴ ساعتِ اخیر می‌سازد (یا None)."""
    now = now or datetime.utcnow()
    since = now - timedelta(hours=24)
    rows = (await session.execute(
        select(SportsMatch).where(SportsMatch.played_at >= since).order_by(SportsMatch.id.desc())
    )).scalars().all()
    if not rows:
        return None

    def _pick(sport: str):
        for m in rows:
            if m.sport == sport and m.result == "A":
                return m
        for m in rows:
            if m.sport == sport:
                return m
        return None

    lines = ["🏆 <b>نتایجِ مسابقاتِ امروز</b> 🏆", ""]
    fb = _pick(S.FOOTBALL)
    if fb:
        star = f" (گلِ طلایی توسطِ {fb.star_player})" if fb.star_player else ""
        lines.append(f"⚽ <b>فوتبال:</b> {fb.team_a_name} {fb.score_a}-{fb.score_b} {fb.team_b_name}{star}")
    bk = _pick(S.BASKETBALL)
    if bk:
        lines.append(f"🏀 <b>بسکتبال:</b> {bk.team_a_name} {bk.score_a}-{bk.score_b} {bk.team_b_name}")
    f1 = _pick(S.F1)
    if f1:
        w = f1.team_a_name if f1.result == "A" else f1.team_b_name
        lines.append(f"🏎️ <b>فرمول یک:</b> {w} در جایگاهِ اول ایستاد. 🏁")
    mt = _pick(S.MOTO)
    if mt:
        w = mt.team_a_name if mt.result == "A" else mt.team_b_name
        lines.append(f"🏍️ <b>موتورسواری:</b> {w} قهرمانِ پیست شد.")

    total_prize = sum(int(m.prize or 0) for m in rows)
    lines.append("")
    lines.append(f"💰 <b>جوایز:</b> مجموعاً {total_prize:,}$ به حسابِ برندگان واریز شد. جدولِ رنکینگ به‌روز شد.")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# لیگِ حذفیِ هفتگی (ثبت‌نام + اجرای خودکار)
# ---------------------------------------------------------------------------
async def league_registered_count(session: AsyncSession, sport: str) -> int:
    rows = (await session.execute(
        select(SportsTeam).where(SportsTeam.sport == sport, SportsTeam.in_league == True)  # noqa: E712
    )).scalars().all()
    return len(rows)


async def league_registration_status(session: AsyncSession, uid: int, sport: str) -> bool:
    team = await get_team(session, uid, sport)
    return bool(team and team.in_league)


async def register_for_league(session: AsyncSession, uid: int, sport: str) -> tuple[bool, str]:
    """ثبت‌نامِ تیمِ بازیکن برای لیگِ حذفیِ هفتهِ جاری/بعدی همین رشته.
    اگر تیم همین‌الان در یک لیگِ درحالِ اجرا باشد هم‌می‌تواند برای هفتهِ بعد ثبت‌نام کند
    (چون in_league بعد از هر اجرای هفتگی ریست می‌شود)."""
    if sport not in S.TEAM_SPORTS:
        return False, "⚠️ لیگِ حذفی فقط برای فوتبال/بسکتبال فعال است."
    team = await get_team(session, uid, sport)
    if team is None:
        return False, "⚠️ اول باید تیم بسازی."
    if team.in_league:
        return False, "✅ تو قبلاً برای لیگِ این هفته ثبت‌نام کرده‌ای."
    player = await get_player(session, uid)
    if player is None or int(player.cash or 0) < S.LEAGUE_ENTRY_FEE:
        return False, f"⚠️ برای ثبت‌نام به {S.LEAGUE_ENTRY_FEE:,}$ نیاز داری."
    player.cash = int(player.cash or 0) - S.LEAGUE_ENTRY_FEE
    team.in_league = True
    await session.commit()
    return True, f"🏆 ثبت‌نام شد! {S.LEAGUE_ENTRY_FEE:,}$ کسر شد. منتظرِ زمانِ شروعِ لیگِ حذفی باش (هفته‌ی جمعه، ظهر)."


async def _settle_pair_result(
    session: AsyncSession, sport: str, team_a: SportsTeam, team_b_name: str,
    opp_uid: int | None, res, rng: random.Random,
) -> tuple[int, str]:
    """آمارِ تیمِ A را برای نتیجهِ رس به‌روز می‌کند و جایزه می‌دهد. نتیجه را برمی‌گرداند: (پرایز, "A"/"B")."""
    if res.winner == "A":
        team_a.wins += 1
        team_a.points += S.WIN_POINTS
        rkey = "win"
    elif res.winner == "draw":
        team_a.draws += 1
        team_a.points += S.DRAW_POINTS
        rkey = "draw"
    else:
        team_a.losses += 1
        rkey = "loss"
    team_a.goals_for += res.score_a
    team_a.goals_against += res.score_b
    prize = S.match_prize(sport, rkey)
    player = await get_player(session, team_a.tg_user_id)
    if player and prize:
        player.cash = int(player.cash or 0) + prize
    session.add(SportsMatch(
        tg_user_id=team_a.tg_user_id, sport=sport,
        team_a_name=team_a.name, team_b_name=team_b_name,
        opponent_user_id=opp_uid,
        score_a=res.score_a, score_b=res.score_b,
        result=res.winner, events=",".join(res.events) or None,
        prize=prize, star_player=(rng.choice(_STAR_NAMES) if res.score_a > 0 else None),
    ))
    return prize, res.winner


async def _resolve_bracket_pair(
    session: AsyncSession, sport: str, team_a: SportsTeam, team_b: SportsTeam,
    rng: random.Random,
) -> SportsTeam:
    """یک مسابقهِ حذفی بینِ دو تیمِ واقعی را اجرا می‌کند (تا ۳ بار تلاش درصورتِ مساوی
    چون حذفی نمی‌تواند مساوی بماند؛ درنهایت تیمِ قوی‌تر برنده اعلام می‌شود) و برنده را برمی‌گرداند."""
    power_a = await compute_team_power(session, team_a)
    power_b = await compute_team_power(session, team_b)
    host_sat, _ = await team_fan_context(session, team_a.tg_user_id)
    ctx = S.MatchContext(host_is_a=True, host_satisfaction=host_sat)
    winner_team = None
    for _ in range(3):
        res = S.simulate_match(sport, power_a, power_b, ctx, rng)
        await _settle_pair_result(session, sport, team_a, team_b.name, team_b.tg_user_id, res, rng)
        flipped = S.MatchResult(
            winner=("B" if res.winner == "A" else "A" if res.winner == "B" else "draw"),
            score_a=res.score_b, score_b=res.score_a,
            power_a=res.power_b, power_b=res.power_a,
            final_a=res.final_b, final_b=res.final_a,
            events=res.events,
        )
        await _settle_pair_result(session, sport, team_b, team_a.name, team_a.tg_user_id, flipped, rng)
        if res.winner == "A":
            winner_team = team_a
            break
        if res.winner == "B":
            winner_team = team_b
            break
    if winner_team is None:
        winner_team = team_a if power_a >= power_b else team_b
    return winner_team


async def _resolve_bracket_bot_match(
    session: AsyncSession, sport: str, team: SportsTeam, rng: random.Random,
) -> bool:
    """برای تیمِ فرد (بدون حریف)، یک مسابقه با حریفِ رباتی اجرا می‌کند. برد = صعود."""
    power_a = await compute_team_power(session, team)
    opp_name, power_b = await _make_bot_opponent(sport, power_a, rng)
    host_sat, _ = await team_fan_context(session, team.tg_user_id)
    ctx = S.MatchContext(host_is_a=True, host_satisfaction=host_sat)
    res = S.simulate_match(sport, power_a, power_b, ctx, rng)
    await _settle_pair_result(session, sport, team, opp_name, None, res, rng)
    return res.winner == "A"


async def run_weekly_league(session: AsyncSession, sport: str, rng: random.Random | None = None) -> dict:
    """تورنمنتِ حذفیِ هفتگی را برای یک رشته اجرا می‌کند: تیم‌های ثبت‌نام‌شده را جفت
    می‌کند، درصورتِ فردبودن، یک تیم را برای دو مسابقهِ رباتی می‌فرستد، بقیه را دوتایی می‌کند، قهرمان را
    جایزه می‌دهد و ثبت‌نام‌ها را برای هفتهِ بعد ریست می‌کند. اگر کمتر از ۲ تیم ثبت‌نام کرده باشد، چیزی اجرا
    نمی‌شود و ثبت‌نامِ آن تک تیم (اگر باشد) برای هفتهِ بعد نگه داشته می‌شود."""
    rng = rng or random.Random()
    if sport not in S.TEAM_SPORTS:
        return {"status": "invalid_sport", "participants": 0}
    teams = (await session.execute(
        select(SportsTeam).where(SportsTeam.sport == sport, SportsTeam.in_league == True)  # noqa: E712
    )).scalars().all()
    participants = len(teams)
    if participants < 2:
        return {"status": "not_enough", "participants": participants}

    alive = list(teams)
    rng.shuffle(alive)
    rounds = 0
    while len(alive) > 1:
        rounds += 1
        next_round: list[SportsTeam] = []
        pool = list(alive)
        double_team = None
        if len(pool) % 2 == 1:
            idx = rng.randrange(len(pool))
            double_team = pool.pop(idx)
        for i in range(0, len(pool), 2):
            team_a, team_b = pool[i], pool[i + 1]
            winner = await _resolve_bracket_pair(session, sport, team_a, team_b, rng)
            next_round.append(winner)
        if double_team is not None:
            leg1 = await _resolve_bracket_bot_match(session, sport, double_team, rng)
            leg2 = await _resolve_bracket_bot_match(session, sport, double_team, rng)
            if leg1 and leg2:
                next_round.append(double_team)
        alive = next_round

    for t in teams:
        t.in_league = False

    champion = None
    if alive:
        champ_team = alive[0]
        player = await get_player(session, champ_team.tg_user_id)
        if player:
            player.cash = int(player.cash or 0) + S.LEAGUE_CHAMPION_PRIZE
        champ_team.points += S.LEAGUE_CHAMPION_BONUS_POINTS
        champion = {"uid": champ_team.tg_user_id, "name": champ_team.name}

    await session.commit()
    return {
        "status": "done", "participants": participants, "rounds": rounds,
        "champion": champion,
    }
