# -*- coding: utf-8 -*-
"""v1.7.9.2 — سرویسِ فوتبال منیجر (مرحله ۷۹ — فاز F1: اسکلت باشگاه + دوستانه).

منطقِ کاتالوگ در app/data/football_players.py است. در F1: ساخت باشگاه، اسکادر اولیه،
قدرت ساده و بازی دوستانه (بدون جایزه — فقط نتیجه + گلزنان، سقف ۵/روز).
"""
from __future__ import annotations

import random
import uuid
from datetime import datetime, timedelta

from sqlalchemy import delete, func, select

from app.data import football_players as FP
from app.models.football import FootballClub, FootballMatch, FootballPlayerCard

CLUB_CREATE_COST = 2_500_000          # دلار بازی (سند A12)
FRIENDLY_DAILY_LIMIT = 5              # سقف دوستانه در روز (سند A12)
NAME_MIN, NAME_MAX = 3, 24

# کلماتِ نامناسب پایه برای فیلتر نام باشگاه
_BAD_WORDS = {"fuck", "shit", "کص", "کیر", "کون", "ننت", "جنده", "کسکش", "حرامی"}


def name_is_valid(raw: str) -> bool:
    name = (raw or "").strip()
    if not (NAME_MIN <= len(name) <= NAME_MAX):
        return False
    low = name.lower()
    return not any(bad in low for bad in _BAD_WORDS)


async def get_club(session, uid: int) -> FootballClub | None:
    return (await session.execute(
        select(FootballClub).where(FootballClub.owner_id == int(uid))
    )).scalar_one_or_none()


async def club_name_taken(session, name: str) -> bool:
    return (await session.execute(
        select(FootballClub.id).where(func.lower(FootballClub.name) == name.strip().lower())
    )).scalar_one_or_none() is not None


async def create_club(session, uid: int, name: str, player) -> tuple[bool, str]:
    """ساخت باشگاه + پکیج شروع (۱۸ بازیکن عادی رایگان)."""
    if player is None:
        return False, "اول /start را بزن تا ثبت‌نام شوی."
    name = (name or "").strip()
    if not name_is_valid(name):
        return False, f"❌ نام نامعتبر است (باید {NAME_MIN} تا {NAME_MAX} کاراکتر و بدون کلمات نامناسب باشد)."
    if await club_name_taken(session, name):
        return False, "❌ این نام قبلاً گرفته شده؛ نام دیگری انتخاب کن."
    if await get_club(session, uid) is not None:
        return False, "تو از قبل باشگاه داری."
    cash = int(getattr(player, "cash", 0) or 0)
    if cash < CLUB_CREATE_COST:
        return False, f"موجودی کافی نیست. هزینه‌ی ساخت باشگاه: {CLUB_CREATE_COST:,}$"
    player.cash = cash - CLUB_CREATE_COST
    club = FootballClub(owner_id=int(uid), name=name)
    session.add(club)
    await session.flush()
    for tpl in FP.starters_pack():
        session.add(FootballPlayerCard(
            club_id=club.id, owner_id=int(uid), template_key=tpl["key"],
            name=tpl["name"], pos=tpl["pos"], tier=tpl["tier"], base_power=tpl["power"],
            tracking_code=uuid.uuid4().hex[:10].upper(), acquired_via="starter",
        ))
    await session.flush()
    return True, club.id


async def squad(session, club_id: int) -> list[FootballPlayerCard]:
    return list((await session.execute(
        select(FootballPlayerCard).where(FootballPlayerCard.club_id == int(club_id))
    )).scalars().all())


# --------------------------- قدرت ---------------------------
def coach_star_mult(stars: int) -> float:
    return 1.0 + 0.05 * max(1, min(5, int(stars)))


def effective_power(card: FootballPlayerCard, club: FootballClub, now: datetime | None = None) -> int:
    now = now or datetime.utcnow()
    if card.injured_until and card.injured_until > now:
        return 0
    base = int(card.base_power or 0) + int(card.training_bonus or 0)
    form = max(90, min(110, int(card.form_pct or 100))) / 100.0
    fatigue_factor = 1.0 - 0.25 * (int(card.fatigue or 0) / 100.0)
    return int(base * form * fatigue_factor * coach_star_mult(club.coach_stars))


def _formation_needs(formation: str) -> dict:
    try:
        d, m, f = (int(x) for x in formation.split("-"))
        return {"DEF": d, "MID": m, "FWD": f}
    except Exception:
        return {"DEF": 4, "MID": 3, "FWD": 3}


def best_eleven(cards: list[FootballPlayerCard], club: FootballClub, now: datetime | None = None) -> list[FootballPlayerCard]:
    """بهترین ۱۱ سالم بر اساس آرایشِ استارتر (۱ GK + نیازهای آرایش؛ کمبود با بهترینِ باقی پر می‌شود)."""
    now = now or datetime.utcnow()
    healthy = [c for c in cards if not (c.injured_until and c.injured_until > now)]
    healthy.sort(key=lambda c: effective_power(c, club, now), reverse=True)
    needs = _formation_needs(club.formation_start)
    picked: list[FootballPlayerCard] = []
    gks = [c for c in healthy if c.pos == "GK"]
    if gks:
        picked.append(gks[0])
    for pos, n in needs.items():
        pool = [c for c in healthy if c.pos == pos and c not in picked]
        picked.extend(pool[:n])
    if len(picked) < 11:
        for c in healthy:
            if c not in picked:
                picked.append(c)
                if len(picked) >= 11:
                    break
    return picked[:11]


def team_power(session, club: FootballClub, cards: list[FootballPlayerCard] | None = None) -> int:
    """قدرت ساده F1: جمع قدرت مؤثر بهترین ۱۱ + ضریب سوشال (هر ۲۰M فالوور = +۱٪، سقف ۲۵٪)."""
    if cards is None:
        cards = []
    eleven = best_eleven(cards, club)
    base = sum(effective_power(c, club) for c in eleven)
    social_pct = min(25, int(club.social_followers or 0) // 20_000_000)
    return int(base * (1 + social_pct / 100))


# --------------------------- بازی دوستانه ---------------------------
_BOT_NAMES = ["⚔️ تیم خیالی", "🌪️ تیم طوفان", "🔥 تیم آتش", "🌊 تیم اقیانوس", "⛰️ تیم صخره", "🌙 تیم مهتاب"]


async def friendlies_today(session, uid: int) -> int:
    """تعداد دوستانه‌های امروز (به وقت تهران)."""
    try:
        from app.data.news import now_tehran
        day = now_tehran().date()
    except Exception:
        day = datetime.utcnow().date()
    start = datetime.combine(day, datetime.min.time())
    end = start + timedelta(days=1)
    return int((await session.execute(
        select(func.count()).select_from(FootballMatch).where(
            FootballMatch.home_club_id.in_(
                select(FootballClub.id).where(FootballClub.owner_id == int(uid))
            ),
            FootballMatch.mode == "friendly",
            FootballMatch.created_at >= start,
            FootballMatch.created_at < end,
        )
    )).scalar() or 0)


async def play_friendly(session, uid: int, rng: random.Random | None = None) -> dict | None:
    """بازی دوستانه با حریف بات — بدون جایزه (فقط نتیجه + گلزنان). سند A12 v2."""
    rng = rng or random.Random()
    club = await get_club(session, uid)
    if club is None:
        return None
    cards = await squad(session, club.id)
    if len([c for c in cards if not (c.injured_until and c.injured_until > datetime.utcnow())]) < 11:
        return {"error": "حداقل ۱۱ بازیکن سالم لازم است."}
    my_power = max(1, team_power(session, club, cards))
    bot_power = max(1, int(my_power * rng.uniform(0.75, 1.25)))
    ratio = my_power / (my_power + bot_power)
    xg_me = 0.6 + 2.2 * (ratio ** 1.2)
    xg_bot = 0.6 + 2.2 * ((1 - ratio) ** 1.2)
    my_goals = min(6, _poisson(rng, xg_me))
    bot_goals = min(6, _poisson(rng, xg_bot))
    scorers = _scorers(cards, my_goals, rng)
    bot_name = rng.choice(_BOT_NAMES)
    attendance = min(int(club.stadium_capacity or 12_500), int(int(club.fans or 0) * rng.uniform(0.70, 0.95)))
    report = _friendly_report(club, bot_name, my_goals, bot_goals, scorers, my_power, bot_power, attendance)
    try:
        from app.services import football_league as FLG
        await FLG.update_standing(session, club, my_goals, bot_goals)
    except Exception:
        pass
    session.add(FootballMatch(
        home_club_id=club.id, away_club_id=0,
        home_goals=my_goals, away_goals=bot_goals,
        mode="friendly", report=report,
    ))
    await session.flush()
    return {
        "my_goals": my_goals, "bot_goals": bot_goals, "bot_name": bot_name,
        "scorers": scorers, "report": report,
        "result": "win" if my_goals > bot_goals else ("draw" if my_goals == bot_goals else "loss"),
    }


def _poisson(rng: random.Random, lam: float) -> int:
    import math
    L = math.exp(-lam)
    k, p = 0, 1.0
    while p > L:
        k += 1
        p *= rng.random()
    return k - 1


def _scorers(cards: list[FootballPlayerCard], goals: int, rng: random.Random) -> list[str]:
    if goals <= 0:
        return []
    attackers = [c for c in cards if c.pos in ("FWD", "MID")] or list(cards)
    out = []
    for _ in range(goals):
        c = rng.choice(attackers)
        out.append(f"{c.name} ({rng.randint(3, 90)}′)")
    return out


def _friendly_report(club, bot_name, hg, ag, scorers, my_power, bot_power, attendance) -> str:
    lines = [
        f"⚽ <b>{club.name}</b> {hg}-{ag} {bot_name}",
        f"🏟️ حضور: {attendance:,} / {int(club.stadium_capacity or 0):,}",
        f"⭐ قدرت: {my_power:,} vs {bot_power:,}",
        "",
    ]
    if scorers:
        lines.append("🥅 گلزن‌ها: " + "، ".join(scorers))
    else:
        lines.append("🥅 بدون گل.")
    lines.append("")
    lines.append("🤝 دوستانه — بدون جایزه (فقط نتیجه ثبت می‌شود).")
    return "\n".join(lines)


# --------------------------- ریست فوتبال قدیمی (یک‌بار) ---------------------------
async def reset_old_football_once(session) -> None:
    """ریست کامل فوتبالِ قدیمی (SportsTeam/SportsMatch ورزش football) — فقط یک‌بار.

    باقی ورزش‌ها (بسکتبال/مسابقه‌ای) دست‌نخورده می‌مانند.
    """
    try:
        from app.services import admin_service as adm
        if str(await adm.get_setting(session, "football_reset_v1792_done") or "0") == "1":
            return
        from app.models.sports import SportsTeam, SportsMatch
        await session.execute(delete(SportsMatch).where(SportsMatch.sport == "football"))
        await session.execute(delete(SportsTeam).where(SportsTeam.sport == "football"))
        await adm.set_setting(session, "football_reset_v1792_done", "1", commit=False)
        await session.commit()
    except Exception:
        try:
            await session.rollback()
        except Exception:
            pass
