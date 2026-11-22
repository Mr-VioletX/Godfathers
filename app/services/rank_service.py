# -*- coding: utf-8 -*-
"""🆕 مرحله ۴۶ (بچ ۳) — سرویسِ رنکینگ: کاپ، لیگ، نردبانِ کلی و پنجره‌ی حمله.

وظایف:
  • نگهداریِ ردیفِ rank_states هر بازیکن.
  • ساختِ «رتبه‌بندیِ کلی» (مرتب بر اساسِ کاپ، سپس قدرت).
  • محدودکردنِ حمله به ±۵۰ نفرِ اطراف در همین نردبان.
  • اعمالِ کاپ/لیگ/سپر پس از هر نبردِ رنکینگ.
  • رتبه‌بندیِ جزئیِ هر ۶ لیگ (قابلِ پیمایش).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import select

from app.data import ranks as RK
from app.models.player import Player
from app.models.rank import RankState

PAGE_SIZE = 10


@dataclass
class LadderEntry:
    uid: int
    name: str
    cups: int
    power: int
    league: int


# --------------------------- ردیفِ وضعیت ---------------------------
async def get_state(session, uid: int) -> RankState:
    st = await session.get(RankState, int(uid))
    if st is None:
        st = RankState(owner_id=int(uid), cups=0, best_cups=0, league=0, best_league=0)
        session.add(st)
        await session.flush()
    return st


def is_shielded(state: RankState | None, now: datetime | None = None) -> bool:
    now = now or datetime.utcnow()
    return bool(state and state.shield_until and state.shield_until > now)


def shield_left_min(state: RankState | None, now: datetime | None = None) -> int:
    now = now or datetime.utcnow()
    if not is_shielded(state, now):
        return 0
    return max(1, int((state.shield_until - now).total_seconds() // 60))


# --------------------------- نردبانِ کلی ---------------------------
async def _power_map(session) -> dict[int, int]:
    """قدرتِ همه‌ی بازیکن‌ها در یک پاس (از لایه‌ی رتبه‌بندیِ دسته‌ای)."""
    try:
        from app.services import ranking as R
        data = await R.compute_all(session)
        mp = {int(e.tg_user_id): int(e.value) for e in data.get("power", [])}
        if mp:
            return mp
    except Exception:
        pass
    # fallback: قدرت رزمی مستقیم (اگر ranking به‌خاطر بانک/اسکیما fail شد)
    try:
        from app.services import war_service as WS
        players = (await session.execute(select(Player))).scalars().all()
        out: dict[int, int] = {}
        for p in players:
            uid = int(p.tg_user_id)
            try:
                out[uid] = int(await WS.compute_combat_power(session, uid))
            except Exception:
                out[uid] = max(1, int(getattr(p, "level", 1) or 1))
        return out
    except Exception:
        return {}


async def ladder(session) -> list[LadderEntry]:
    """رتبه‌بندیِ کلی: کاپ ↓ ، سپس قدرت ↓ ، سپس شناسه."""
    players = (await session.execute(select(Player))).scalars().all()
    if not players:
        return []
    states = {
        s.owner_id: s
        for s in (await session.execute(select(RankState))).scalars().all()
    }
    powers = await _power_map(session)
    out: list[LadderEntry] = []
    for p in players:
        uid = int(p.tg_user_id)
        st = states.get(uid)
        cups = int(getattr(st, "cups", 0) or 0)
        out.append(LadderEntry(
            uid=uid,
            name=(p.name or "بی‌نام"),
            cups=cups,
            power=int(powers.get(uid, 0)),
            league=RK.league_index(cups),
        ))
    out.sort(key=lambda e: (-e.cups, -e.power, e.uid))
    return out


def index_of(entries: list[LadderEntry], uid: int) -> int:
    for i, e in enumerate(entries):
        if e.uid == int(uid):
            return i
    return -1


def page_slice(entries: list, page: int, per: int = PAGE_SIZE) -> tuple[list, int, int]:
    total = max(1, (len(entries) + per - 1) // per)
    page = max(0, min(int(page), total - 1))
    start = page * per
    return entries[start:start + per], page, total


def league_entries(entries: list[LadderEntry], league_idx: int) -> list[LadderEntry]:
    return [e for e in entries if e.league == int(league_idx)]


# --------------------------- پنجره‌ی حمله (±۵۰) ---------------------------
async def window_targets(session, uid: int) -> tuple[list[LadderEntry], int, int]:
    """(فهرستِ اهدافِ مجاز، رتبه‌ی خودم، کلِ بازیکن‌ها).

    حمله فقط به ۵۰ نفرِ بالا و ۵۰ نفرِ پایینِ خود در رتبه‌بندیِ کلی مجاز است
    (جنگِ بین‌رنکی ممکن است — لیگِ حریف مهم نیست).
    """
    entries = await ladder(session)
    my_idx = index_of(entries, uid)
    if my_idx < 0:
        return [], -1, len(entries)
    lo, hi = RK.window_bounds(my_idx, len(entries))
    window = [e for i, e in enumerate(entries[lo:hi + 1], start=lo) if e.uid != int(uid)]
    return window, my_idx, len(entries)


async def can_attack(session, attacker_id: int, defender_id: int) -> tuple[bool, str]:
    """فقط قاعده‌های رنکینگ (پنجره‌ی ±۵۰ و سپرِ لیگ) را بررسی می‌کند."""
    entries = await ladder(session)
    my_idx = index_of(entries, attacker_id)
    t_idx = index_of(entries, defender_id)
    if my_idx < 0:
        return False, "اول /start را بزن."
    if t_idx < 0:
        return False, "این کاربر در رتبه‌بندی نیست."
    if not RK.in_window(my_idx, t_idx, len(entries)):
        return False, (
            f"🚫 فقط به ±{RK.ATTACK_WINDOW} نفرِ اطرافِ خودت در رتبه‌بندیِ کلی می‌توانی حمله کنی.\n"
            f"رتبه‌ی تو: {my_idx + 1} | رتبه‌ی هدف: {t_idx + 1}"
        )
    st = await session.get(RankState, int(defender_id))
    if is_shielded(st):
        mins = shield_left_min(st)
        hrs, m = divmod(mins, 60)
        return False, f"🛡️ این بازیکن تازه واردِ لیگِ جدید شده و سپر دارد ({hrs}س {m}د)."
    return True, ""


# --------------------------- اعمالِ نتیجه ---------------------------
async def apply_result(
    session,
    attacker_id: int,
    defender_id: int,
    attacker_won: bool,
    att_power: int,
    def_power: int,
    now: datetime | None = None,
) -> dict:
    """کاپ، لیگ، سپر و آمارِ دو طرف را پس از یک نبردِ رنکینگ به‌روز می‌کند."""
    now = now or datetime.utcnow()
    gain = RK.cup_reward(att_power, def_power)
    penalty = RK.cup_penalty(att_power, def_power)

    att = await get_state(session, attacker_id)
    dfn = await get_state(session, defender_id)

    att_before, def_before = int(att.cups or 0), int(dfn.cups or 0)
    att_league_before = RK.league_index(att_before)
    def_league_before = RK.league_index(def_before)

    if attacker_won:
        att.cups = RK.apply_cups(att_before, +gain)
        dfn.cups = RK.apply_cups(def_before, -penalty)
        att.wins = int(att.wins or 0) + 1
        dfn.defenses_lost = int(dfn.defenses_lost or 0) + 1
    else:
        att.cups = RK.apply_cups(att_before, -penalty)
        dfn.cups = RK.apply_cups(def_before, +gain)
        att.losses = int(att.losses or 0) + 1
        dfn.defenses_won = int(dfn.defenses_won or 0) + 1

    att.last_ranked_at = now

    out = {
        "gain": gain,
        "penalty": penalty,
        "att_cups": int(att.cups),
        "def_cups": int(dfn.cups),
        "att_delta": int(att.cups) - att_before,
        "def_delta": int(dfn.cups) - def_before,
        "att_promoted": False,
        "def_promoted": False,
        "att_demoted": False,
        "def_demoted": False,
        "att_league": RK.league_name(int(att.cups)),
        "def_league": RK.league_name(int(dfn.cups)),
    }

    for state, before_league, key in (
        (att, att_league_before, "att"),
        (dfn, def_league_before, "def"),
    ):
        after_league = RK.league_index(int(state.cups))
        state.league = after_league
        state.best_cups = max(int(state.best_cups or 0), int(state.cups))
        state.best_league = max(int(state.best_league or 0), after_league)
        if after_league > before_league:
            # ورود به لیگِ تازه → سپرِ ۱ روزه
            state.shield_until = now + timedelta(hours=RK.NEW_LEAGUE_SHIELD_HOURS)
            out[f"{key}_promoted"] = True
        elif after_league < before_league:
            out[f"{key}_demoted"] = True
    await session.flush()
    return out


# --------------------------- متن‌ها ---------------------------
def result_lines(res: dict, *, for_attacker: bool) -> list[str]:
    key = "att" if for_attacker else "def"
    delta = int(res.get(f"{key}_delta", 0))
    cups = int(res.get(f"{key}_cups", 0))
    sign = "+" if delta > 0 else ""
    lines = [f"🏅 کاپ: <b>{sign}{delta}</b> ← مجموع: <b>{cups:,}</b> ({res.get(f'{key}_league', '')})"]
    if res.get(f"{key}_promoted"):
        lines.append("🎉 به لیگِ بالاتر صعود کردی — ۲۴ ساعت سپرِ دفاعی داری.")
    if res.get(f"{key}_demoted"):
        lines.append("📉 از لیگ سقوط کردی.")
    return lines


async def status_text(session, uid: int) -> str:
    """خلاصه‌ی وضعیتِ رنکینگِ یک بازیکن."""
    st = await get_state(session, uid)
    entries = await ladder(session)
    idx = index_of(entries, uid)
    cups = int(st.cups or 0)
    lines = [
        "🏅 <b>وضعیتِ رنکینگ</b>",
        "",
        f"🏆 کاپ: <b>{cups:,}</b> ({RK.league_name(cups)})",
        f"📈 بهترین کاپ: {int(st.best_cups or 0):,}",
    ]
    if idx >= 0:
        lines.append(f"📍 رتبه‌ی کلی: <b>{idx + 1}</b> از {len(entries)}")
    gap = RK.next_league_gap(cups)
    if gap:
        lines.append(f"⬆️ تا لیگِ بعدی: {gap:,} کاپ")
    lines.append(f"⚔️ برد/باختِ حمله: {int(st.wins or 0)} / {int(st.losses or 0)}")
    lines.append(f"🛡️ دفاعِ موفق/ناموفق: {int(st.defenses_won or 0)} / {int(st.defenses_lost or 0)}")
    if is_shielded(st):
        mins = shield_left_min(st)
        hrs, m = divmod(mins, 60)
        lines.append(f"🛡️ سپرِ لیگِ تازه: {hrs} ساعت و {m} دقیقه‌ی دیگر"
    )
    return "\n".join(lines)
