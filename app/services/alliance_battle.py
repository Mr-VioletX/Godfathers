# -*- coding: utf-8 -*-
"""v1.7.9.1 — موتورِ نبردِ زنده‌ی اتحادیه (دقیقاً مثل جنگِ کلاسیک/رنکینگ).

- نبردِ ۱۵ دقیقه‌ایِ فازدار با شبیه‌سازیِ سنگ‌کاغذقیچی روی ارتشِ سربازخانه
- آتش‌بس تا پیش از فازِ سوم (تلفاتِ مقیاس‌شده + کاهشِ غنیمت) — مثل جنگِ عادی
- غنیمت ۱۴–۴۲٪ از صندوقِ بازنده → نیمی صندوقِ برنده + نیمی مساوی بین اعضای برنده
- باختِ مهاجم → غرامت ۱۰–۴۰٪ از صندوقِ مهاجم (همین‌طور نصف/نصف برای مدافع)
- XP و کاپ با همان فرمول‌های جنگِ عادی؛ کاپ در رنکینگِ جدای اتحادیه‌ها
- سپر ۲۴ ساعته برای بازنده + حمله‌ی تکراری روی همان هدف: ۳ روز یک‌بار (رنکینگ‌مانند) — اصلاحِ قواعد
"""
from __future__ import annotations

import json
import random
from datetime import datetime, timedelta

from sqlalchemy import select

from app.data import alliance as A
from app.data import alliance_military as AM
from app.data import battle_report as BR
from app.data import battle_sentences
from app.data import military as M
from app.data import ranks as RK
from app.data import war as W
from app.models.alliance import Alliance, AllianceWar
from app.models.alliance_war import AllianceBattle, AllianceRankRow, AllianceWarState
from app.services import alliance_military_service as AMS
from app.services import alliance_service

BATTLE_SECONDS = BR.BATTLE_MINUTES * 60
PREDICT_SAMPLES = 15

# قواعدِ فعلیِ سپر/کول‌داون (تأیید امیر): سپر ۲۴ ساعت پس از باخت؛ حمله‌ی تکراری ۳ روز یک‌بار
ALLIANCE_SHIELD_HOURS = 24
PAIR_LOCK_DAYS = 3


# --------------------------- وضعیتِ جنگی ---------------------------
async def get_or_create_war_state(session, alliance_id: int) -> AllianceWarState:
    st = await session.get(AllianceWarState, int(alliance_id))
    if st is None:
        st = AllianceWarState(alliance_id=int(alliance_id))
        session.add(st)
        await session.flush()
    return st


def is_shielded(state: AllianceWarState | None, now: datetime | None = None) -> bool:
    now = now or datetime.utcnow()
    return bool(state and state.shield_until and state.shield_until > now)


def shield_days_left(state: AllianceWarState | None, now: datetime | None = None) -> int:
    now = now or datetime.utcnow()
    if not (state and state.shield_until and state.shield_until > now):
        return 0
    return max(1, (state.shield_until - now).days + 1)


def attack_cooldown_left_min(state: AllianceWarState | None, now: datetime | None = None) -> int:
    now = now or datetime.utcnow()
    if not (state and state.last_attack_at):
        return 0
    ready_at = state.last_attack_at + timedelta(hours=W.ATTACK_COOLDOWN_HOURS)
    if ready_at <= now:
        return 0
    return max(1, int((ready_at - now).total_seconds() // 60))


async def pair_loot_lock_left_days(session, attacker_id: int, defender_id: int, now: datetime | None = None) -> int:
    """قفلِ غنیمتِ جفت‌بازی: تا LOOT_DAYS پس از آخرین پیروزیِ مهاجم بر همین هدف."""
    now = now or datetime.utcnow()
    row = (await session.execute(
        select(AllianceBattle).where(
            AllianceBattle.attacker_id == int(attacker_id),
            AllianceBattle.defender_id == int(defender_id),
            AllianceBattle.loot_until.is_not(None),
            AllianceBattle.loot_until > now,
        ).order_by(AllianceBattle.id.desc())
    )).scalars().first()
    if row is None or not row.loot_until:
        return 0
    return max(1, (row.loot_until - now).days + 1)


async def running_battle_for(session, alliance_id: int, now: datetime | None = None) -> AllianceBattle | None:
    now = now or datetime.utcnow()
    mine = (AllianceBattle.attacker_id == int(alliance_id)) | (AllianceBattle.defender_id == int(alliance_id))
    return (await session.execute(
        select(AllianceBattle).where(mine, AllianceBattle.finalized == 0)
        .order_by(AllianceBattle.started_at.desc())
    )).scalars().first()


async def last_battle_for(session, alliance_id: int) -> AllianceBattle | None:
    mine = (AllianceBattle.attacker_id == int(alliance_id)) | (AllianceBattle.defender_id == int(alliance_id))
    return (await session.execute(
        select(AllianceBattle).where(mine).order_by(AllianceBattle.started_at.desc())
    )).scalars().first()


# --------------------------- قدرت و پیش‌بینی ---------------------------
async def battle_power(session, alliance: Alliance) -> int:
    """قدرتِ جنگیِ اتحادیه = قدرتِ ارتشِ سربازخانه (نیروهای جدا از بخشِ نظامیِ شخصی)."""
    return max(1, await AMS.army_power(session, alliance.id))


async def preview(session, attacker_id: int, defender_id: int) -> dict:
    att_stacks = await AMS.stacks(session, attacker_id)
    def_stacks = await AMS.stacks(session, defender_id)
    att_power = await AMS.army_power(session, attacker_id)
    def_power = await AMS.army_power(session, defender_id)
    att_base = AM.to_base_stacks(att_stacks)
    def_base = AM.to_base_stacks(def_stacks)

    seed = (int(attacker_id) * 7919 + int(defender_id)) % 99991
    wins = 0
    al, dl = [], []
    from app.services import battle_live as BL
    for i in range(max(1, PREDICT_SAMPLES)):
        rng = random.Random((seed * 7919) + i)
        res = M.simulate_battle(att_base, def_base, rng)
        att_l, def_l, won = BL._finalize_losses(res, att_base, def_base, max(1, att_power), max(1, def_power))
        wins += 1 if won else 0
        al.append(sum(int(v) for v in att_l.values()))
        dl.append(sum(int(v) for v in def_l.values()))
    if not al:
        al, dl = [0], [0]
    win_prob = wins / float(len(al))
    p_power = W.win_probability(max(1, att_power), max(1, def_power))
    win_prob = 0.65 * float(win_prob) + 0.35 * float(p_power)
    win_prob = max(0.03, min(0.97, win_prob))
    return {
        "att_power": int(att_power), "def_power": int(def_power),
        "win_prob": win_prob, "win_pct": int(round(win_prob * 100)),
        "att_loss_min": int(min(al)), "att_loss_max": int(max(al)),
        "def_loss_min": int(min(dl)), "def_loss_max": int(max(dl)),
        "att_units": sum(int(c) for _k, c, _l in att_stacks),
        "def_units": sum(int(c) for _k, c, _l in def_stacks),
    }


def preview_text(pre: dict, att_name: str, def_name: str) -> str:
    return "\n".join([
        f"⚔️ <b>{att_name}</b> ← → <b>{def_name}</b>",
        f"💥 قدرتِ ارتشِ شما: {pre['att_power']:,}",
        f"🛡️ قدرتِ ارتشِ حریف: {pre['def_power']:,}",
        f"🎯 احتمالِ پیروزی: <b>≈{pre['win_pct']}٪</b>",
        f"🩸 برآوردِ تلفاتِ شما: {pre['att_loss_min']:,} تا {pre['att_loss_max']:,} نیرو",
        f"🩸 برآوردِ تلفاتِ حریف: {pre['def_loss_min']:,} تا {pre['def_loss_max']:,} نیرو",
    ])


# --------------------------- شروعِ نبرد ---------------------------
async def start(session, attacker_id: int, defender_id: int, now: datetime | None = None) -> tuple[bool, object]:
    now = now or datetime.utcnow()
    attacker = await alliance_service.get_alliance(session, int(attacker_id))
    defender = await alliance_service.get_alliance(session, int(defender_id))
    if attacker is None or defender is None:
        return False, "یکی از اتحادیه‌ها دیگر وجود ندارد."
    if attacker.id == defender.id:
        return False, "هدفِ نامعتبر."

    busy = await running_battle_for(session, attacker.id, now)
    if busy is not None and busy.ends_at > now:
        return False, "⚔️ اتحادیه‌ی شما همین حالا یک نبردِ درحال‌اجرا دارد؛ اول همان را تمام کنید."

    att_state = await get_or_create_war_state(session, attacker.id)

    # قفلِ جفتی: حمله‌ی تکراری به همان اتحادیه فقط یک‌بار در ۳ روز (رنکینگ‌مانند)
    lock_days = await pair_loot_lock_left_days(session, attacker.id, defender.id, now)
    if lock_days:
        return False, f"🔒 حمله‌ی تکراری: تا {lock_days} روز دیگر می‌توانید دوباره به این اتحادیه حمله کنید."

    def_state = await get_or_create_war_state(session, defender.id)
    if is_shielded(def_state, now):
        return False, f"🛡️ این اتحادیه سپر دارد؛ تا {shield_days_left(def_state, now)} روز دیگر مصون است."

    att_stacks = await AMS.stacks(session, attacker.id)
    if not att_stacks:
        return False, "🤡 سربازخانه‌ی شما خالی است! اول از بخشِ سربازخانه نیرو بسازید."
    def_stacks = await AMS.stacks(session, defender.id)

    pre = await preview(session, attacker.id, defender.id)
    att_base = AM.to_base_stacks(att_stacks)
    def_base = AM.to_base_stacks(def_stacks)
    rng = random.Random(int(now.timestamp()) ^ (int(attacker.id) << 3) ^ int(defender.id))
    result = M.simulate_battle(att_base, def_base, rng)
    # هم‌راستایی برنده با احتمالِ اعلامی در نبردِ هم‌رده (مثل جنگِ عادی)
    ap = max(1, int(pre.get("att_power") or 1))
    dp = max(1, int(pre.get("def_power") or 1))
    field_ratio = max(ap, dp) / max(1.0, float(min(ap, dp)))
    sim_won = bool(result.get("attacker_won", True))
    if def_base and field_ratio < 1.5:
        p = 0.60 * (1.0 if sim_won else 0.0) + 0.40 * float(pre.get("win_prob") or 0.5)
        attacker_won = rng.random() < max(0.05, min(0.95, p))
        result = dict(result)
        result["attacker_won"] = bool(attacker_won)
    from app.services import battle_live as BL
    att_losses, def_losses, attacker_won = BL._finalize_losses(result, att_base, def_base, ap, dp)

    phases = battle_sentences.make_battle_phases(
        attacker.name, defender.name, att_base, def_base,
        {"att_losses": att_losses, "def_losses": def_losses, "attacker_won": attacker_won},
        seed=int(now.timestamp()) % 100003,
    )
    row = AllianceBattle(
        attacker_id=int(attacker.id), defender_id=int(defender.id), mode="alliance",
        started_at=now, ends_at=now + timedelta(seconds=BATTLE_SECONDS),
        plan_json=json.dumps({
            "att_name": attacker.name, "def_name": defender.name,
            "att_power": ap, "def_power": dp, "win_pct": pre["win_pct"],
            "attacker_won": bool(attacker_won),
            "att_losses": att_losses, "def_losses": def_losses,
            "phases": phases,
        }, ensure_ascii=False),
        finalized=0, notified=0,
    )
    session.add(row)
    att_state.last_attack_at = now
    await session.flush()
    return True, row


# --------------------------- رندرِ گزارش ---------------------------
def plan_of(row: AllianceBattle) -> dict:
    try:
        return json.loads(row.plan_json or "{}")
    except Exception:
        return {}


def phases_unlocked(row: AllianceBattle, now: datetime | None = None) -> int:
    now = now or datetime.utcnow()
    elapsed = (now - row.started_at).total_seconds()
    n = 0
    for i in range(BR.PHASE_COUNT):
        if elapsed >= BR.phase_unlock_seconds(i):
            n = i + 1
    return n


def is_over(row: AllianceBattle, now: datetime | None = None) -> bool:
    return (now or datetime.utcnow()) >= row.ends_at


def render(row: AllianceBattle, now: datetime | None = None) -> str:
    now = now or datetime.utcnow()
    plan = plan_of(row)
    head = [
        "⚔️ <b>نبردِ اتحادیه‌ها</b> — 🤝",
        f"{plan.get('att_name', 'مهاجم')} ⚔️ {plan.get('def_name', 'مدافع')}",
        f"💥 {int(plan.get('att_power', 0)):,} — 🛡️ {int(plan.get('def_power', 0)):,}",
        f"🎯 احتمالِ پیروزیِ اعلام‌شده: ≈{int(plan.get('win_pct', 0))}٪",
        "➖➖➖",
        "",
    ]
    phases = plan.get("phases", [])
    n = phases_unlocked(row, now)
    body = list(phases[:n])
    tail: list[str] = []
    if row.finalized:
        tail.append("")
        tail.append(plan.get("final_text", "🏁 نبرد تمام شد."))
    elif is_over(row, now):
        tail.append("")
        tail.append("🏁 جنگ تمام شد — برای دیدنِ گزارشِ نهایی «🔄 بروزرسانی» را بزن.")
    else:
        left = int((row.ends_at - now).total_seconds())
        nxt = None
        elapsed = (now - row.started_at).total_seconds()
        for i in range(BR.PHASE_COUNT):
            if elapsed < BR.phase_unlock_seconds(i):
                nxt = BR.phase_unlock_seconds(i) - elapsed
                break
        tail.append("")
        if nxt is not None:
            tail.append(f"🕒 عملیاتِ بعدی تا {BR.fmt_remaining(int(nxt))} دیگر — «🔄 بروزرسانی» را بزن.")
        tail.append(f"⏳ پایانِ جنگ تا {BR.fmt_remaining(left)} دیگر.")
    if not body:
        body = ["🔭 ارتش‌های دو اتحادیه در حالِ استقرارند…"]
    return "\n".join(head + ["\n\n".join(body)] + tail)


# --------------------------- آتش‌بس (مثل جنگِ عادی) ---------------------------
async def ceasefire(session, battle_id: int, alliance_id: int, now: datetime | None = None) -> tuple[bool, str, AllianceBattle | None]:
    """آتش‌بس تا قبل از باز شدنِ فازِ سوم؛ تلفاتِ همان فازها اعمال و غنیمت کاهش می‌یابد."""
    now = now or datetime.utcnow()
    row = await session.get(AllianceBattle, int(battle_id))
    if row is None:
        return False, "نبرد پیدا نشد.", None
    if int(alliance_id) not in (int(row.attacker_id), int(row.defender_id)):
        return False, "این نبرد مالِ اتحادیه‌ی تو نیست.", None
    if row.finalized:
        return False, "این نبرد تمام شده.", None
    plan = plan_of(row)
    if plan.get("ceased"):
        return False, "آتش‌بس قبلاً ثبت شده.", None
    unlocked = phases_unlocked(row, now)
    if unlocked >= 3:
        return False, "⏳ فازِ سوم باز شده؛ دیگر آتش‌بس ممکن نیست.", None
    frac = 0.35 if unlocked <= 1 else 0.65
    att_full = {k: int(v) for k, v in (plan.get("att_losses") or {}).items()}
    def_full = {k: int(v) for k, v in (plan.get("def_losses") or {}).items()}
    plan["att_losses"] = {k: v for k, v in ((k, int(round(v * frac))) for k, v in att_full.items()) if v > 0}
    plan["def_losses"] = {k: v for k, v in ((k, int(round(v * frac))) for k, v in def_full.items()) if v > 0}
    plan["ceased"] = True
    plan["cease_phase"] = int(unlocked)
    plan["loot_mult"] = 0.4 if unlocked <= 1 else 0.7
    row.plan_json = json.dumps(plan, ensure_ascii=False)
    row.ends_at = now
    await session.flush()
    return True, f"🕊️ آتش‌بس ثبت شد (پس از فازِ {max(1, unlocked)}). با بروزرسانی نتیجه را ببین.", row


# --------------------------- پایان و اعمالِ نتیجه ---------------------------
async def _rank_row(session, alliance_id: int) -> AllianceRankRow:
    row = await session.get(AllianceRankRow, int(alliance_id))
    if row is None:
        row = AllianceRankRow(alliance_id=int(alliance_id), cups=0, wins=0, losses=0)
        session.add(row)
        await session.flush()
    return row


async def _split_to_winner(session, winner: Alliance, amount: int) -> int:
    """نیمی به صندوقِ برنده + نیمی مساوی بین اعضای برنده. خروجی: سهمِ هر عضو."""
    half = int(amount) // 2
    winner.treasury = int(winner.treasury or 0) + half
    rest = int(amount) - half
    member_ids = await alliance_service.member_ids(session, winner.id)
    share = (rest // len(member_ids)) if member_ids else 0
    if share > 0:
        from app.handlers.profile import get_player
        for uid in member_ids:
            try:
                p = await get_player(session, uid)
                if p is not None:
                    p.cash = int(getattr(p, "cash", 0) or 0) + share
            except Exception:
                continue
    return share


async def _grant_winner_xp(session, winner: Alliance, xp: int) -> None:
    if xp <= 0:
        return
    from app.data import leveling as _lv
    from app.handlers.profile import get_player
    for uid in await alliance_service.member_ids(session, winner.id):
        try:
            p = await get_player(session, uid)
            if p is not None:
                await _lv.grant_xp(session, p, xp, source="alliance_war")
        except Exception:
            continue


async def finalize(session, row: AllianceBattle, now: datetime | None = None) -> dict:
    """تلفات، غنیمت/غرامت از صندوق، XP، کاپ، سپر/قفل و خبر — فقط یک‌بار."""
    now = now or datetime.utcnow()
    plan = plan_of(row)
    if row.finalized:
        return {"text": plan.get("final_text", ""), "already": True}

    attacker = await alliance_service.get_alliance(session, row.attacker_id)
    defender = await alliance_service.get_alliance(session, row.defender_id)
    if attacker is None or defender is None:
        row.finalized = 1
        await session.flush()
        return {"text": "یکی از اتحادیه‌ها دیگر وجود ندارد.", "already": False}

    attacker_won = bool(plan.get("attacker_won"))
    att_losses = {k: int(v) for k, v in (plan.get("att_losses") or {}).items()}
    def_losses = {k: int(v) for k, v in (plan.get("def_losses") or {}).items()}
    await AMS.apply_losses(session, attacker.id, att_losses)
    await AMS.apply_losses(session, defender.id, def_losses)

    att_power = int(plan.get("att_power", 0))
    def_power = int(plan.get("def_power", 0))
    ceased = bool(plan.get("ceased"))
    loot_mult = float(plan.get("loot_mult") or 1.0)

    winner = attacker if attacker_won else defender
    loser = defender if attacker_won else attacker

    amount = 0
    loot_pct = 0
    member_share = 0
    if attacker_won:
        loot_pct = int(RK.loot_percent_by_power(att_power, def_power))
        gross = min(int(defender.treasury or 0), int(int(defender.treasury or 0) * loot_pct / 100))
        amount = int(gross * min(1.0, loot_mult))
        if amount > 0:
            defender.treasury = int(defender.treasury or 0) - amount
            member_share = await _split_to_winner(session, attacker, amount)
    else:
        loot_pct = int(W.penalty_percent(att_power, def_power))
        gross = min(int(attacker.treasury or 0), int(int(attacker.treasury or 0) * loot_pct / 100))
        amount = int(gross * min(1.0, loot_mult))
        if amount > 0:
            attacker.treasury = int(attacker.treasury or 0) - amount
            member_share = await _split_to_winner(session, defender, amount)

    # XP و کاپ (همان فرمول‌های جنگِ عادی)
    xp_gain = 0
    if not ceased:
        xp_gain = RK.win_xp(att_power, def_power)
        await _grant_winner_xp(session, winner, xp_gain)
        wr = await _rank_row(session, winner.id)
        lr = await _rank_row(session, loser.id)
        wr.cups = int(wr.cups or 0) + RK.cup_reward(att_power, def_power)
        wr.wins = int(wr.wins or 0) + 1
        lr.cups = max(0, int(lr.cups or 0) - RK.cup_penalty(att_power, def_power))
        lr.losses = int(lr.losses or 0) + 1

    # سپر و قفلِ غنیمت (همون منطق جنگِ عادی)
    loser_state = await get_or_create_war_state(session, loser.id)
    loser_state.shield_until = now + timedelta(hours=ALLIANCE_SHIELD_HOURS)  # سپر ۲۴ ساعته پس از باخت
    row.loot_until = now + timedelta(days=PAIR_LOCK_DAYS)  # حمله‌ی تکراری: ۳ روز یک‌بار

    # تاریخچه
    session.add(AllianceWar(
        attacker_id=attacker.id, defender_id=defender.id,
        winner_id=winner.id, loser_id=loser.id, amount=amount,
        attacker_won=1 if attacker_won else 0,
    ))

    # بیمارستان برای هر دو طرف
    try:
        await AMS.create_ward(session, attacker.id, att_losses, battle_id=int(row.id),
                              opponent_name=defender.name, now=now)
        await AMS.create_ward(session, defender.id, def_losses, battle_id=int(row.id),
                              opponent_name=attacker.name, now=now)
    except Exception:
        pass

    # خبر (بدونِ مبلغِ غنیمت — v1.7.9.1)
    try:
        from app.services import news_service
        al = sum(int(v or 0) for v in att_losses.values())
        dl = sum(int(v or 0) for v in def_losses.values())
        if ceased:
            txt = f"[اتحادیه] 🕊️ آتش‌بس بین {attacker.name} و {defender.name} پس از فازِ {int(plan.get('cease_phase') or 1)} برقرار شد (تلفات {al}/{dl})"
        elif attacker_won:
            txt = f"[اتحادیه] {attacker.name} بر {defender.name} پیروز شد (قدرت {att_power:,} vs {def_power:,} | تلفات {al}/{dl})"
        else:
            txt = f"[اتحادیه] {defender.name} حمله‌ی {attacker.name} را دفع کرد (قدرت {att_power:,} vs {def_power:,} | تلفات {al}/{dl})"
        imp = 3 if (att_power + def_power) >= 100_000 else 2
        await news_service.add_news(session, category="war", text=txt, importance=imp, commit=False)
    except Exception:
        pass

    # متنِ نهایی
    lines = [
        BR.result_banner(attacker_won) if not ceased else "🕊️ <b>آتش‌بس برقرار شد</b>",
        "",
        f"⚔️ {attacker.name} vs {defender.name}",
        f"🩸 تلفاتِ {attacker.name}: {AMS.losses_text(att_losses)}",
        f"🩸 تلفاتِ {defender.name}: {AMS.losses_text(def_losses)}",
    ]
    if amount > 0:
        lines.append(f"💰 مبلغِ جابه‌جاشده از صندوقِ {loser.name}: <b>{amount:,}$</b>")
        lines.append(f"🏦 نیمی به صندوقِ {winner.name} رفت")
        if member_share > 0:
            lines.append(f"👥 سهمِ هر عضوِ {winner.name}: <b>{member_share:,}$</b>")
    else:
        lines.append("🕳️ صندوقِ بازنده چیزی برای جابه‌جایی نداشت.")
    if xp_gain:
        lines.append(f"⭐ هر عضوِ {winner.name}: +{xp_gain} XP")
    if not ceased:
        lines.append(f"🏆 کاپ: {winner.name} +{RK.cup_reward(att_power, def_power)} / {loser.name} −{RK.cup_penalty(att_power, def_power)}")
    lines.append(f"🛡️ {loser.name} به مدتِ {ALLIANCE_SHIELD_HOURS} ساعت سپر گرفت.")
    plan["final_text"] = "\n".join(lines)
    plan["loot"] = amount
    row.plan_json = json.dumps(plan, ensure_ascii=False)
    row.finalized = 1
    await session.commit()
    return {"text": plan["final_text"], "already": False}


async def sweep_finalize_finished(session, now: datetime | None = None) -> int:
    """نبردهای تمام‌شده‌ی نهایی‌نشده را نهایی می‌کند (برای تیکر/کرون)."""
    now = now or datetime.utcnow()
    rows = (await session.execute(
        select(AllianceBattle).where(AllianceBattle.finalized == 0, AllianceBattle.ends_at <= now)
    )).scalars().all()
    n = 0
    for row in rows:
        try:
            await finalize(session, row, now)
            n += 1
        except Exception:
            continue
    return n
