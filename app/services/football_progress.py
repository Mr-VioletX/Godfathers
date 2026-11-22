# -*- coding: utf-8 -*-
"""v1.7.9.4 — سرویس پیشرفت فوتبال (F2): سرمربی، استادیوم، سوشال، کمپ و تمرین + مصدومیت.

منطقِ خالص در app/data/football_progress.py است. وضعیت‌های روزانه/هفتگی در جدولِ
تازه‌ی FootballClubState نگه‌داری می‌شوند تا هیچ مهاجرتِ دستی لازم نباشد.
"""
from __future__ import annotations

import json
import random
from datetime import datetime, timedelta

from sqlalchemy import select

from app.data import football_progress as FP
from app.data import football_players as FCAT
from app.models.football import FootballClub, FootballClubState, FootballPlayerCard
from app.services import football_service as FS


# --------------------------- وضعیتِ باشگاه (جدول تازه) ---------------------------
async def get_state(session, club_id: int) -> FootballClubState:
    st = await session.get(FootballClubState, int(club_id))
    if st is None:
        st = FootballClubState(club_id=int(club_id))
        session.add(st)
        await session.flush()
    return st


def coach_xp_map(state: FootballClubState) -> dict:
    try:
        return {str(k): int(v) for k, v in json.loads(state.coach_xp_json or "{}").items()}
    except Exception:
        return {}


def _tehran_today() -> str:
    try:
        from app.data.news import now_tehran
        return now_tehran().date().isoformat()
    except Exception:
        return datetime.utcnow().date().isoformat()


def _iso_week() -> str:
    y, w, _ = datetime.utcnow().isocalendar()
    return f"{y}-W{w:02d}"


# --------------------------- سرمربی ---------------------------
async def change_style(session, club: FootballClub, state: FootballClubState, player, style: str) -> tuple[bool, str]:
    if style not in FP.COACH_STYLES:
        return False, "سبک نامعتبر."
    if club.coach_style == style:
        return False, "همین سبک از قبل فعال است. ✅"
    this_week = _iso_week()
    free = state.style_change_week != this_week
    if not free:
        cash = int(getattr(player, "cash", 0) or 0)
        if cash < FP.STYLE_CHANGE_COST:
            return False, f"تعویضِ رایگانِ این هفته را استفاده کردی — هزینه: {FP.STYLE_CHANGE_COST:,}$ (موجودی: {cash:,}$)"
        player.cash = cash - FP.STYLE_CHANGE_COST
    club.coach_style = style
    state.style_change_week = this_week
    await session.flush()
    s = FP.COACH_STYLES[style]
    return True, f"✅ سبک به «{s['name']}» تغییر کرد ({s['effect']})." + (" (رایگانِ این هفته)" if free else f" (-{FP.STYLE_CHANGE_COST:,}$)")


async def build_star(session, club: FootballClub, state: FootballClubState, player) -> tuple[bool, str]:
    cur = int(club.coach_stars or 1)
    if cur >= 5:
        return False, "سرمربی در بیشینه‌ی ستاره (۵⭐) است. ✅"
    nxt = cur + 1
    if nxt > FP.STAR_MAX_BUILD:
        return False, "⭐ ستاره‌ی ۵ فقط از فروشگاهِ واقعی قابل خرید است (بخش خریدهای ویژه)."
    cost, req_level = FP.STAR_BUILD[nxt]
    level = int(club.coach_level or 1)
    if level < req_level:
        return False, f"🔒 برای {nxt}⭐ سرمربی باید سطح {req_level} باشد (فعلی: {level})."
    cash = int(getattr(player, "cash", 0) or 0)
    if cash < cost:
        return False, f"موجودی کافی نیست. هزینه: {cost:,}$ (موجودی: {cash:,}$)"
    player.cash = cash - cost
    club.coach_stars = nxt
    await session.flush()
    return True, f"✅ سرمربی به {nxt}⭐ رسید — ضریب قدرت داخل زمین: ×{FP.coach_star_mult(nxt):.2f}"


async def coach_gain_xp(session, club: FootballClub, xp: int) -> None:
    """اعطای XP به سبکِ فعلیِ سرمربی (در بردهای رسمی — سیم‌کشی در F4)."""
    state = await get_state(session, club.id)
    m = coach_xp_map(state)
    style = club.coach_style
    m[style] = m.get(style, 0) + int(xp)
    state.coach_xp_json = json.dumps(m)
    # ارتقای سطح سرمربی از XP فعلی سبک (ساده: جمع XP سبک فعلی به سطح نگاشت می‌شود)
    level = int(club.coach_level or 1)
    while level < FP.COACH_LEVEL_MAX and m[style] >= _xp_for_level(level):
        level += 1
    club.coach_level = level
    await session.flush()


def _xp_for_level(level: int) -> int:
    """XP تجمیعی لازم برای رسیدن به سطحِ n (از سطح ۱)."""
    total = 0
    for lv in range(1, int(level)):
        total += FP.coach_xp_needed(lv)
    return total


# --------------------------- استادیوم ---------------------------
async def upgrade_stadium(session, club: FootballClub, player) -> tuple[bool, str]:
    level = int(club.stadium_level or 0)
    if level >= FP.STADIUM_MAX_LEVEL:
        return False, "استادیوم در بیشینه‌ی ظرفیت است (۱۲۵٬۰۰۰). ✅"
    cost = FP.stadium_upgrade_cost(level)
    cash = int(getattr(player, "cash", 0) or 0)
    if cash < cost:
        return False, f"موجودی کافی نیست. هزینه: {cost:,}$ (موجودی: {cash:,}$)"
    player.cash = cash - cost
    club.stadium_level = level + 1
    club.stadium_capacity = FP.stadium_capacity(level + 1)
    await session.flush()
    display_level = FP.stadium_display_level(club.stadium_level)
    return True, (f"✅ استادیوم به سطح {display_level} ارتقا یافت — ظرفیت: {club.stadium_capacity:,} "
                  f"(بلیت: {FP.TICKET_PRICE_BY_LEVEL[club.stadium_level]}$)")


async def expected_attendance(session, club: FootballClub) -> int:
    """برآورد حضور: min(ظرفیت, طرفدار × ضریب پرشدگی)."""
    cap = int(club.stadium_capacity or FP.STADIUM_LEVELS[0][0])
    fans = int(club.fans or 0)
    fill = 0.70 + min(0.35, FP.social_power_pct(int(club.social_followers or 0)) / 100.0 * 5)
    return min(cap, int(fans * fill))


# --------------------------- سوشال ---------------------------
async def social_post(session, club: FootballClub, state: FootballClubState, player, rng: random.Random | None = None) -> tuple[bool, str]:
    today = _tehran_today()
    if state.social_date != today:
        state.social_date = today
        state.social_count = 0
    if int(state.social_count or 0) >= FP.SOCIAL_POSTS_PER_DAY:
        return False, f"📱 سهمیه‌ی امروز ({FP.SOCIAL_POSTS_PER_DAY} پست) پر شد — فردا دوباره."
    rng = rng or random.Random()
    gain = FP.roll_fans_gain(rng)
    followers_gain = gain * FP.FOLLOWERS_PER_FAN
    club.fans = int(club.fans or 0) + gain
    club.social_followers = int(club.social_followers or 0) + followers_gain
    state.social_count = int(state.social_count or 0) + 1
    # مایلستون‌ها
    try:
        claimed = json.loads(state.milestones_json or "[]")
    except Exception:
        claimed = []
    new_rewards = []
    for threshold, reward, label in FP.SOCIAL_MILESTONES:
        if int(club.social_followers) >= threshold and threshold not in claimed:
            claimed.append(threshold)
            player.cash = int(getattr(player, "cash", 0) or 0) + reward
            new_rewards.append(f"{label}: +{reward:,}$")
    state.milestones_json = json.dumps(claimed)
    await session.flush()
    lines = [
        f"📱 پست منتشر شد! ({int(state.social_count)}/{FP.SOCIAL_POSTS_PER_DAY} امروز)",
        f"👥 +{gain:,} طرفدار جدید (مجموع: {int(club.fans):,})",
        f"📈 +{followers_gain:,} فالوور سوشال (مجموع: {int(club.social_followers):,})",
        f"⭐ بونوس پاور از سوشال: +{FP.social_power_pct(int(club.social_followers))}٪",
    ]
    if new_rewards:
        lines.append("")
        lines.extend("🏆 " + r for r in new_rewards)
    return True, "\n".join(lines)


# --------------------------- کمپ و تمرین ---------------------------
async def build_camp(session, club: FootballClub, player) -> tuple[bool, str]:
    camps = int(club.training_camps or 0)
    if camps >= FP.CAMP_MAX:
        return False, "هر ۳ کمپ ساخته شده‌اند. ✅"
    cost = FP.CAMP_COSTS[camps]
    cash = int(getattr(player, "cash", 0) or 0)
    if cash < cost:
        return False, f"موجودی کافی نیست. هزینه‌ی کمپ {camps+1}: {cost:,}$ (موجودی: {cash:,}$)"
    player.cash = cash - cost
    club.training_camps = camps + 1
    await session.flush()
    return True, f"✅ کمپ {club.training_camps} ساخته شد — اثر هر جلسه‌ی تمرین حالا +{FP.camp_power_per_session(club.training_camps)} پاور است."


async def train_session(session, club: FootballClub, state: FootballClubState, rng: random.Random | None = None) -> tuple[bool, str]:
    """یک جلسه تمرین: پاور به بازیکنان سالم (با بازده نزولی) + رول مصدومیت + خستگی."""
    camps = int(club.training_camps or 0)
    if camps <= 0:
        return False, "اول کمپ تمرینی بساز (کمپ ۱ ← ۴M$)."
    today = _tehran_today()
    if state.train_date != today:
        state.train_date = today
        state.train_count = 0
    session_idx = int(state.train_count or 0) + 1
    if session_idx > FP.TRAIN_SESSIONS_PER_DAY:
        return False, f"🏋️ سهمیه‌ی امروز ({FP.TRAIN_SESSIONS_PER_DAY} جلسه) پر شد — فردا دوباره."
    rng = rng or random.Random()
    now = datetime.utcnow()
    gain_per = FP.camp_power_per_session(camps)
    cards = await FS.squad(session, club.id)
    # کاهش تنبل خستگی از آخرین فعالیت
    trained_cards = []
    injured_new = []
    for c in cards:
        # مصدوم‌ها تمرین نمی‌کنند
        if c.injured_until and c.injured_until > now:
            continue
        cur_fatigue = int(c.fatigue or 0)
        tired = cur_fatigue > FP.FATIGUE_TIRED_THRESHOLD
        eff_gain = gain_per // 2 if tired else gain_per
        if eff_gain <= 0:
            eff_gain = 0
        applied = FP.diminishing_gain(int(c.training_bonus or 0), eff_gain)
        c.training_bonus = int(c.training_bonus or 0) + applied
        c.fatigue = FP.fatigue_after(cur_fatigue)
        trained_cards.append(c)

    trained = len(trained_cards)
    average_fatigue = (
        sum(int(c.fatigue or 0) for c in trained_cards) / trained if trained else 0.0
    )
    raw_team_risk = FP.team_injury_chance(average_fatigue, session_idx, club.coach_style)

    # Protect the last healthy goalkeeper, then roll ONCE for the whole team.
    healthy_gks = sum(1 for c in trained_cards if c.pos == "GK")
    candidates = [c for c in trained_cards if c.pos != "GK" or healthy_gks > 1]
    team_risk = raw_team_risk if trained > FP.INJURY_HEALTHY_FLOOR and candidates else 0.0
    if team_risk > 0:
        picked = FP.roll_team_injury_index(
            [int(c.fatigue or 0) for c in candidates],
            team_risk,
            rng,
            healthy_roster_size=trained,
        )
        if picked is not None:
            card = candidates[picked]
            days = FP.injury_days(rng)
            card.injured_until = now + timedelta(days=days)
            injured_new.append((card.name, days))
    state.train_count = session_idx
    await session.flush()
    lines = [
        f"🏋️ جلسه‌ی {session_idx}/{FP.TRAIN_SESSIONS_PER_DAY} انجام شد (کمپ ×{camps} ← +{gain_per} پاور پایه)",
        f"💪 {trained} بازیکن سالم تمرین کردند.",
        (f"🩺 ریسک تیمی مصدومیت: {team_risk:.2f}٪ — معادل "
         f"{FP.player_equivalent_injury_chance(team_risk, trained):.3f}٪ برای هر بازیکن"),
    ]
    if injured_new:
        lines.append("⚠️ مصدومیت: " + "، ".join(f"{n} ({d} روز)" for n, d in injured_new))
    else:
        lines.append("✅ این جلسه بدون مصدومیت تمام شد.")
    return True, "\n".join(lines)
