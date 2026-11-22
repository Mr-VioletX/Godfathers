# -*- coding: utf-8 -*-
"""🆕 مرحله ۴۶ — موتورِ نبردِ زنده‌ی ۱۵ دقیقه‌ای (کلاسیک و رنکینگ).

قواعدِ تازه:
  • نتیجه با شبیه‌سازیِ واقعیِ سنگ‌کاغذ‌قیچی تعیین می‌شود، نه فقط نسبتِ قدرت.
  • هر دو طرف تلفات می‌دهند؛ لولِ بالاترِ نیرو = تلفاتِ کمتر.
  • پیش از شروع، درصدِ احتمالیِ پیروزی و برآوردِ تلفات نشان داده می‌شود.
  • هر جنگ ۱۵ دقیقه طول می‌کشد و فازها فقط با دکمه‌ی «🔄 بروزرسانی» باز می‌شوند.
  • کلاسیک: غنیمتِ ثابتِ ۵٪ از کلِ ثروت (شاملِ بانک)، روزی یک بار، بدونِ کاپ.
  • رنکینگ: هر ۳ روز یک بار به هر نفر (جزئیاتِ کاپ/لیگ در لایه‌ی رنکینگ).
"""
from __future__ import annotations

import json
import random
from datetime import datetime, timedelta

from sqlalchemy import select

from app.data import battle_report as BR
from app.data import battle_sentences
from app.data import ranks as RK
from app.data import military as M
from app.data import war as W
from app.models.live_battle import LiveBattle
from app.models.player import Player
from app.services import military_service, war_service

BATTLE_SECONDS = BR.BATTLE_MINUTES * 60
CLASSIC_LOOT_PCT = 5
CLASSIC_COOLDOWN_HOURS = 24
RANKED_COOLDOWN_HOURS = 72
WIN_XP = 42
PREDICT_SAMPLES = 15


# --------------------------- کمکی‌ها ---------------------------
async def _player(session, uid: int):
    try:
        from app.handlers.profile import get_player
        return await get_player(session, int(uid))
    except Exception:
        return (await session.execute(select(Player).where(Player.tg_user_id == int(uid)))).scalar_one_or_none()


def _name_of(player, uid: int) -> str:
    return str(getattr(player, "name", None) or uid)


async def bank_balance(session, uid: int) -> int:
    """موجودیِ بانکِ مافیایی (برای محاسبه‌ی کلِ ثروت)."""
    try:
        from app.models.worldbank import BankAccount
        acc = await session.get(BankAccount, int(uid))
        return max(0, int(getattr(acc, "deposit", 0) or 0)) if acc else 0
    except Exception:
        return 0


async def total_wealth(session, uid: int) -> int:
    p = await _player(session, uid)
    cash = int(getattr(p, "cash", 0) or 0) if p else 0
    return max(0, cash) + await bank_balance(session, uid)


async def lootable_pool(session, uid: int) -> dict:
    """v1.7.7.6 — ثروت قابل‌غارت = نقد + ۵۰٪ سپرده (منهای گاوصندوق امن)."""
    try:
        from app.services import worldbank_service as WBS
        return await WBS.lootable_wealth_of(session, uid)
    except Exception:
        p = await _player(session, uid)
        cash = int(getattr(p, "cash", 0) or 0) if p else 0
        dep = await bank_balance(session, uid)
        return {
            "cash": cash,
            "deposit": dep,
            "safebox": 0,
            "lootable_deposit": int(dep * 30 // 100),
            "lootable_total": cash + int(dep * 30 // 100),
            "protected_deposit": int(dep * 70 // 100),
        }


def _avg_level(stacks) -> float:
    tot = sum(int(c) for _k, c, _lv in stacks)
    if tot <= 0:
        return 0.0
    return sum(int(c) * int(lv) for _k, c, lv in stacks) / tot


# --------------------------- پیش‌بینی پیش از جنگ ---------------------------
def _finalize_losses(result: dict, att_stacks, def_stacks, att_power: int, def_power: int) -> tuple[dict, dict, bool]:
    """🆕 v1.7.3 — همان مسیر تلفات نهایی برای preview و نبرد واقعی."""
    attacker_won = bool((result or {}).get("attacker_won", True))
    att_losses = _mitigate(
        (result or {}).get("att_losses", {}),
        _avg_level(att_stacks),
        won=attacker_won,
        own_power=att_power,
        enemy_power=def_power,
        own_stacks=att_stacks,
    )
    def_losses = _mitigate(
        (result or {}).get("def_losses", {}),
        _avg_level(def_stacks),
        won=not attacker_won,
        own_power=def_power,
        enemy_power=att_power,
        own_stacks=def_stacks,
    )
    return att_losses, def_losses, attacker_won


async def preview(session, attacker_id: int, defender_id: int) -> dict:
    att_stacks = await military_service.army_stacks(session, attacker_id)
    def_stacks = await military_service.army_stacks(session, defender_id)
    att_power = await war_service.compute_combat_power(session, attacker_id)
    def_power = await war_service.compute_combat_power(session, defender_id)

    # 🆕 v1.7.3 — برآورد دقیقاً از همان مسیر mitigate/finalize عبور می‌کند
    # تا عدد اعلامی با تلفات واقعی یکی باشد (قبلاً preview خام بود و واقعی mitigate می‌شد).
    seed = (int(attacker_id) + int(defender_id)) % 99991
    samples = max(1, int(PREDICT_SAMPLES))
    wins = 0
    al, dl = [], []
    for i in range(samples):
        rng = random.Random((int(seed) * 7919) + i)
        if def_stacks:
            res = M.simulate_battle(att_stacks, def_stacks, rng)
        else:
            res = M.simulate_battle(att_stacks, [], rng)
        att_l, def_l, won = _finalize_losses(res, att_stacks, def_stacks, att_power, def_power)
        wins += 1 if won else 0
        al.append(sum(int(v) for v in att_l.values()))
        dl.append(sum(int(v) for v in def_l.values()))
    if not al:
        al, dl = [0], [0]
    win_prob = wins / float(len(al))
    # کمی اثر قدرت کلی برای نمایش احتمال
    p_power = W.win_probability(att_power, def_power)
    win_prob = 0.65 * float(win_prob) + 0.35 * float(p_power)
    win_prob = max(0.03, min(0.97, win_prob))
    return {
        "att_power": int(att_power),
        "def_power": int(def_power),
        "win_prob": win_prob,
        "win_pct": int(round(win_prob * 100)),
        "att_loss_min": int(min(al)),
        "att_loss_max": int(max(al)),
        "def_loss_min": int(min(dl)),
        "def_loss_max": int(max(dl)),
        "att_units": sum(int(c) for _k, c, _l in att_stacks),
        "def_units": sum(int(c) for _k, c, _l in def_stacks),
        "weakness": M.army_weakness(att_stacks),
    }


def preview_text(pre: dict) -> str:
    lines = [
        f"💥 قدرتِ تو: {pre['att_power']:,}",
        f"🛡️ قدرتِ حریف: {pre['def_power']:,}",
        f"🎯 احتمالِ پیروزی: <b>≈{pre['win_pct']}٪</b>",
        f"🩸 برآوردِ تلفاتِ تو: {pre['att_loss_min']:,} تا {pre['att_loss_max']:,} واحد",
        f"🩸 برآوردِ تلفاتِ حریف: {pre['def_loss_min']:,} تا {pre['def_loss_max']:,} واحد",
    ]
    if pre.get("weakness"):
        lines.append(f"⚠️ {pre['weakness']}")
    return "\n".join(lines)


# --------------------------- کول‌داون ---------------------------
def cooldown_hours(mode: str) -> int:
    return RANKED_COOLDOWN_HOURS if mode == "ranked" else CLASSIC_COOLDOWN_HOURS


async def cooldown_left_min(session, attacker_id: int, defender_id: int, mode: str, now: datetime | None = None) -> int:
    now = now or datetime.utcnow()
    hrs = cooldown_hours(mode)
    since = now - timedelta(hours=hrs)
    q = select(LiveBattle).where(
        LiveBattle.attacker_id == int(attacker_id),
        LiveBattle.defender_id == int(defender_id),
        LiveBattle.mode == mode,
        LiveBattle.started_at >= since,
    ).order_by(LiveBattle.started_at.desc())
    row = (await session.execute(q)).scalars().first()
    if row is None:
        return 0
    left = (row.started_at + timedelta(hours=hrs)) - now
    return max(0, int(left.total_seconds() // 60))


async def running_battle(session, uid: int, now: datetime | None = None) -> LiveBattle | None:
    """نبردِ درحال‌اجرایی که این کاربر مهاجمِ آن است."""
    q = select(LiveBattle).where(
        LiveBattle.attacker_id == int(uid),
        LiveBattle.finalized == 0,
    ).order_by(LiveBattle.started_at.desc())
    return (await session.execute(q)).scalars().first()


async def last_battle(session, uid: int) -> LiveBattle | None:
    """🆕 مرحله ۷۰ — آخرین نبردِ این کاربر، چه مهاجم باشد چه مدافع.

    اولویت با نبردِ درجریان است؛ اگر نبود، تازه‌ترین نبردِ تمام‌شده.
    با این تابع، کاربری که پیامِ گزارش را بسته/رد کرده می‌تواند دوباره بازش کند.
    """
    mine = (LiveBattle.attacker_id == int(uid)) | (LiveBattle.defender_id == int(uid))
    running = (await session.execute(
        select(LiveBattle).where(mine, LiveBattle.finalized == 0)
        .order_by(LiveBattle.started_at.desc())
    )).scalars().first()
    if running is not None:
        return running
    return (await session.execute(
        select(LiveBattle).where(mine).order_by(LiveBattle.started_at.desc())
    )).scalars().first()


# --------------------------- شروعِ نبرد ---------------------------
async def start(session, attacker_id: int, defender_id: int, mode: str = "classic") -> tuple[bool, object]:
    now = datetime.utcnow()
    attacker = await _player(session, attacker_id)
    defender = await _player(session, defender_id)
    if attacker is None:
        return False, "اول /start را بزن."
    if defender is None:
        return False, "این کاربر هنوز در بازی نیست."

    busy = await running_battle(session, attacker_id, now)
    if busy is not None and busy.ends_at > now:
        return False, "⚔️ یک نبردِ درحال‌اجرا داری؛ اول همان را تمام کن."

    cd = await cooldown_left_min(session, attacker_id, defender_id, mode, now)
    if cd:
        hrs, mins = divmod(cd, 60)
        return False, f"⏳ تا حمله‌ی بعدی به این بازیکن {hrs} ساعت و {mins} دقیقه مانده."

    att_stacks = await military_service.army_stacks(session, attacker_id)
    if not att_stacks:
        return False, "🤡 بدونِ ارتش که نمی‌شود جنگید! اول از بخشِ نظامی نیرو بساز."
    def_stacks = await military_service.army_stacks(session, defender_id)

    pre = await preview(session, attacker_id, defender_id)
    rng = random.Random(int(now.timestamp()) ^ (int(attacker_id) << 3) ^ int(defender_id))
    # 🆕 v1.7.4 — شبیه‌سازی ترکیب + هم‌راستایی برنده با احتمال اعلام‌شده
    if def_stacks:
        result = M.simulate_battle(att_stacks, def_stacks, rng)
    else:
        result = M.simulate_battle(att_stacks, [], rng)
    # در نبرد هم‌رده، برنده را با win_prob اعلامی ترکیب می‌کنیم تا با پیش‌نمایش نخواند
    ap = max(1, int(pre.get("att_power") or 1))
    dp = max(1, int(pre.get("def_power") or 1))
    field_ratio = max(ap, dp) / max(1.0, float(min(ap, dp)))
    sim_won = bool(result.get("attacker_won", True))
    if def_stacks and field_ratio < 1.5:
        # 60٪ شبیه‌سازی ترکیب + 40٪ شانس قدرت/پیش‌نمایش
        p = 0.60 * (1.0 if sim_won else 0.0) + 0.40 * float(pre.get("win_prob") or 0.5)
        attacker_won = rng.random() < max(0.05, min(0.95, p))
        result = dict(result)
        result["attacker_won"] = bool(attacker_won)
    att_losses, def_losses, attacker_won = _finalize_losses(
        result, att_stacks, def_stacks, pre["att_power"], pre["def_power"]
    )

    att_name = _name_of(attacker, attacker_id)
    def_name = _name_of(defender, defender_id)
    phases = battle_sentences.make_battle_phases(att_name, def_name, att_stacks, def_stacks, {"att_losses": att_losses, "def_losses": def_losses, "attacker_won": attacker_won}, seed=int(now.timestamp()) % 100003)

    row = LiveBattle(
        attacker_id=int(attacker_id),
        defender_id=int(defender_id),
        mode=mode,
        started_at=now,
        ends_at=now + timedelta(seconds=BATTLE_SECONDS),
        plan_json=json.dumps({
            "att_name": att_name,
            "def_name": def_name,
            "att_power": pre["att_power"],
            "def_power": pre["def_power"],
            "win_pct": pre["win_pct"],
            "attacker_won": bool(attacker_won),
            "att_losses": att_losses,
            "def_losses": def_losses,
            "phases": phases,
        }, ensure_ascii=False),
        finalized=0,
        notified=0,
    )
    session.add(row)
    await session.flush()
    return True, row


def _mitigate(
    losses: dict,
    avg_level: float,
    *,
    won: bool,
    own_power: int = 1,
    enemy_power: int = 1,
    own_stacks=None,
) -> dict:
    """v1.7.7.8 — جدول تلفات بازتنظیم‌شده با سخت‌کپ ۲۵٪ (قبلاً ۴۰٪).

    مقیاس نسبت به جدول طراحی قدیمی: ×(۲۵/۴۰)=۰٫۶۲۵
      واحد برنده: هم‌رده ۱۰٪ … قوی→ضعیف ~۳–۴٪
      واحد بازنده: هم‌رده ۱۵٪ … قوی→ضعیف سخت‌کپ ۲۵٪
      قدرت برنده: سخت‌کپ ~۱۲٫۵٪ | بازنده هم‌رده ~۱۷٫۵٪ | بازنده ضعیف ۲۵٪
      سقف پشتهٔ هر نوع نیرو: ۲۵/۳۵/۴۵ (جدول ۴)
    """
    from app.data import military as MD

    q = W.quality_mitigation(avg_level)
    op = max(1, int(own_power))
    ep = max(1, int(enemy_power))
    dominance = op / (op + ep)  # سهم قدرت خودت از کل نبرد
    # نسبت قوی‌تر/ضعیف‌تر از دید کل میدان (همیشه >=1)
    stronger = max(op, ep)
    weaker = min(op, ep)
    field_ratio = stronger / max(1.0, float(weaker))
    # نسبت قدرت خودت به دشمن
    power_ratio = op / max(1.0, float(ep))

    # --- ضریب نرم اولیه ---
    if won:
        outcome_mult = 1.0
        if field_ratio < 1.35:
            # هم‌رده: برنده هم آسیب واقعی می‌بیند ولی له نمی‌شود
            outcome_mult *= 0.85
        elif field_ratio < 2.0:
            outcome_mult *= 0.65
        elif field_ratio < 3.0:
            outcome_mult *= 0.40
        else:
            outcome_mult *= max(0.10, 0.55 / field_ratio)
    else:
        outcome_mult = 1.05
        if field_ratio < 1.35:
            # هم‌رده: بازنده آسیب بیشتر از برنده، نه نابودی ارتش
            outcome_mult *= 0.70
        elif field_ratio < 2.0:
            outcome_mult *= 0.85
        elif dominance >= 0.55:
            # بازنده‌ی نسبتاً قوی (upset)
            outcome_mult *= 0.75

    mult = q * outcome_mult
    stock: dict[str, int] = {}
    levels: dict[str, int] = {}
    total_stock = 0
    for k, c, lv in (own_stacks or []):
        stock[k] = stock.get(k, 0) + int(c or 0)
        levels[k] = max(levels.get(k, 0), int(lv or 0))
        total_stock += int(c or 0)

    # --- سقف کسری واحد بر اساس نزدیکی قدرت ---
    if total_stock <= 0:
        return {}

    # v1.7.7.8 — کل جدول برنده/بازنده با مقیاس ۲۵/۴۰ نسبت به طراحی ۴۰٪
    # جدول کاربردی قدیمی → جدید (واحد):
    #   هم‌رده: برنده ۱۶→۱۰ | بازنده ۲۴→۱۵
    #   کمی برتر: برنده ۱۴→۹ | بازنده ۲۸→۱۷٫۵
    #   متوسط: برنده ۱۰→۶ | بازنده ۳۴→۲۱
    #   قوی→ضعیف: برنده ~۴–۶→~۲٫۵–۴ | بازنده ۴۰→۲۵
    if won:
        if field_ratio < 1.25:
            max_frac = 0.10   # هم‌رده (قبلاً ۱۶٪)
        elif field_ratio < 1.50:
            max_frac = 0.09   # کمی برتر (قبلاً ۱۴٪)
        elif field_ratio < 2.00:
            max_frac = 0.06   # برتری متوسط (قبلاً ۱۰٪)
        elif field_ratio < 3.00:
            max_frac = 0.04   # (قبلاً ~۶٪)
        elif field_ratio < 5.00:
            max_frac = 0.022  # (قبلاً ~۳٫۵٪)
        elif field_ratio < 10.0:
            max_frac = 0.012  # (قبلاً ~۲٪)
        else:
            max_frac = 0.008  # (قبلاً ~۱٫۲٪)
    else:
        if field_ratio < 1.25:
            max_frac = 0.15   # هم‌رده (قبلاً ۲۴٪)
        elif field_ratio < 1.50:
            max_frac = 0.175  # کمی برتر (قبلاً ۲۸٪)
        elif field_ratio < 2.00:
            max_frac = 0.21   # برتری متوسط (قبلاً ۳۴٪)
        else:
            max_frac = 0.25   # قوی→ضعیف — سخت‌کپ ۲۵٪ (قبلاً ۴۰٪)

    # سقف قدرت ارتش (جدول بخش ۲ طراحی، مقیاس‌شده)
    #   برنده: سخت‌کپ ۲۰٪ → ۱۲٫۵٪ | فرمول تقریبی min(۱۲٪، فشار+۶) → min(۷٫۵٪، …)
    #   بازنده هم‌رده: ۲۸٪ → ۱۷٫۵٪
    #   بازنده ضعیف: ۴۰٪ → ۲۵٪
    if won:
        max_power_frac = min(0.125, max_frac + 0.04)
    else:
        if field_ratio < 1.5:
            max_power_frac = min(0.175, max_frac + 0.05)
        else:
            max_power_frac = min(0.25, max_frac + 0.03)
        max_power_frac = min(0.25, max_power_frac)  # سخت‌کپ نهایی ۲۵٪

    # mitigate معمولی
    raw_out: dict = {}
    for k, v in (losses or {}).items():
        n = int(round(max(0, int(v)) * mult))
        cap = stock.get(k)
        if cap is not None:
            # سقف هر پشته (جدول ۴): هم‌رده ۲۵٪ | متوسط ۳۵٪ | شدید ۴۵٪
            per_stack_cap = 0.25 if field_ratio < 1.25 else (0.35 if field_ratio < 2.0 else 0.45)
            n = min(n, max(0, int(cap * per_stack_cap)))
            if int(v) > 0 and cap > 0 and n == 0 and not won:
                n = 1
        if n > 0:
            raw_out[k] = n

    def _total_power_lost(loss_map: dict) -> int:
        s = 0
        for k, n in loss_map.items():
            s += int(MD.unit_power(k, int(n), int(levels.get(k, 0))))
        return s

    def _scale_to_cap(loss_map: dict, unit_cap: int, power_cap: int) -> dict:
        if not loss_map:
            return {}
        out = dict(loss_map)
        # چند دور scale تا هر دو سقف رعایت شود
        for _ in range(4):
            tu = sum(out.values())
            tp = _total_power_lost(out)
            scale_u = (unit_cap / tu) if (tu > unit_cap) else 1.0
            scale_p = (power_cap / tp) if (tp > power_cap) else 1.0
            scale = min(scale_u, scale_p)
            if scale >= 0.999:
                break
            nxt = {}
            for k, n in out.items():
                nn = int(round(n * scale))
                if nn > 0:
                    nxt[k] = min(nn, stock.get(k, nn))
            if not nxt and unit_cap >= 1.0 and stock:
                kmax = max(stock.keys(), key=lambda x: stock[x])
                nxt[kmax] = min(1, stock[kmax])
            out = nxt
        # v1.7.8.0 exact cap trim — گِردکردن می‌تواند یک‌دو واحد از سقف رد شود
        hard = int(unit_cap)
        guard = 0
        while out and sum(out.values()) > hard and guard < 100000:
            kbig = max(out.keys(), key=lambda x: out[x])
            out[kbig] -= 1
            if out[kbig] <= 0:
                del out[kbig]
            guard += 1
        return out

    # v1.7.8.0 casualty cap fix — سقف را اعشاری نگه می‌داریم؛ int() آن را صفر می‌کرد
    unit_cap = max(0.0, float(total_stock) * max_frac)
    start_power = sum(int(MD.unit_power(k, c, levels.get(k, 0))) for k, c in stock.items()) or 1
    power_cap = max(0.0, float(start_power) * max_power_frac)
    raw_out = _scale_to_cap(raw_out, unit_cap, power_cap)
    if not won and not raw_out and unit_cap >= 1.0 and (losses or {}):
        # بازنده دست‌کم یک واحد از دست می‌دهد، حتی با ارتشِ خیلی کوچک
        _kmax = max(stock.keys(), key=lambda x: stock[x])
        raw_out = {_kmax: 1}
    return raw_out


# --------------------------- رندرِ گزارش ---------------------------
def plan_of(row: LiveBattle) -> dict:
    try:
        return json.loads(row.plan_json or "{}")
    except Exception:
        return {}


def phases_unlocked(row: LiveBattle, now: datetime | None = None) -> int:
    now = now or datetime.utcnow()
    elapsed = (now - row.started_at).total_seconds()
    n = 0
    for i in range(BR.PHASE_COUNT):
        if elapsed >= BR.phase_unlock_seconds(i):
            n = i + 1
    return n


def is_over(row: LiveBattle, now: datetime | None = None) -> bool:
    return (now or datetime.utcnow()) >= row.ends_at


def render(row: LiveBattle, now: datetime | None = None) -> str:
    now = now or datetime.utcnow()
    plan = plan_of(row)
    mode_label = "🏅 رنکینگ" if row.mode == "ranked" else "🔥 کلاسیک"
    head = [
        f"⚔️ <b>میدانِ نبرد</b> — {mode_label}",
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
        tail.append(plan.get("final_attacker", "🏁 نبرد تمام شد."))
    elif is_over(row, now):
        tail.append("")
        tail.append("🏁 جنگ تمام شد — برای دیدنِ گزارشِ نهایی دکمه‌ی بروزرسانی را بزن.")
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
            tail.append(f"🕒 عملیاتِ بعدی تا {BR.fmt_remaining(int(nxt))} دیگر — دکمه‌ی «🔄 بروزرسانی» را بزن.")
        tail.append(f"⏳ پایانِ جنگ تا {BR.fmt_remaining(left)} دیگر.")
    if not body:
        body = ["🔭 نیروها در حالِ استقرارند…"]
    return "\n".join(head + ["\n\n".join(body)] + tail)


def render_for(row: LiveBattle, uid: int, now: datetime | None = None) -> str:
    """🆕 مرحله ۷۰ — همان گزارش، اما از دیدِ کاربرِ خواسته‌شده (مهاجم یا مدافع)."""
    if int(row.attacker_id) == int(uid):
        return render(row, now)
    now = now or datetime.utcnow()
    plan = plan_of(row)
    mode_label = "🏅 رنکینگ" if row.mode == "ranked" else "🔥 کلاسیک"
    head = [
        f"🛡️ <b>دفاع از قلمرو</b> — {mode_label}",
        f"{plan.get('att_name', 'مهاجم')} ⚔️ {plan.get('def_name', 'مدافع')}",
        f"💥 {int(plan.get('att_power', 0)):,} — 🛡️ {int(plan.get('def_power', 0)):,}",
        "➖➖➖",
        "",
    ]
    n = phases_unlocked(row, now)
    body = list((plan.get("phases") or [])[:n]) or ["🔭 نیروها در حالِ استقرارند…"]
    tail: list[str] = [""]
    if row.finalized:
        tail.append(plan.get("final_defender", "🏁 نبرد تمام شد."))
    elif is_over(row, now):
        tail.append("🏁 جنگ تمام شد — برای دیدنِ گزارشِ نهایی دکمه‌ی بروزرسانی را بزن.")
    else:
        left = int((row.ends_at - now).total_seconds())
        tail.append(f"⏳ پایانِ جنگ تا {BR.fmt_remaining(left)} دیگر.")
    return "\n".join(head + ["\n\n".join(body)] + tail)


# --------------------------- پایان و اعمالِ نتیجه ---------------------------
async def finalize(session, row: LiveBattle, now: datetime | None = None) -> dict:
    """تلفات، غنیمت، XP و گزارشِ نهایی را اعمال می‌کند (فقط یک بار)."""
    now = now or datetime.utcnow()
    plan = plan_of(row)
    if row.finalized:
        return {"attacker": plan.get("final_attacker", ""), "defender": plan.get("final_defender", ""), "already": True}

    attacker_won = bool(plan.get("attacker_won"))
    att_losses = {k: int(v) for k, v in (plan.get("att_losses") or {}).items()}
    def_losses = {k: int(v) for k, v in (plan.get("def_losses") or {}).items()}

    await military_service.apply_losses(session, row.attacker_id, att_losses)
    await military_service.apply_losses(session, row.defender_id, def_losses)

    attacker = await _player(session, row.attacker_id)
    defender = await _player(session, row.defender_id)

    att_power = int(plan.get("att_power", 0))
    def_power = int(plan.get("def_power", 0))
    ranked = str(row.mode) == "ranked"

    amount = 0
    looted_bank = 0
    loot_pct = 0
    if attacker_won and defender is not None and attacker is not None:
        pool = await lootable_pool(session, row.defender_id)
        lootable = max(0, int(pool.get("lootable_total") or 0))
        cash = max(0, int(pool.get("cash") or 0))
        loot_pct = int(RK.loot_percent_by_power(att_power, def_power))
        # غنیمت = ۱۴..۴۲٪ از (نقد + ۵۰٪ سپرده غیرگاوصندوق)
        if ranked:
            gross = RK.ranked_loot(cash, lootable, att_power, def_power)
        else:
            gross = RK.classic_loot(lootable, cash, pct=loot_pct, att_power=att_power, def_power=def_power)
            _lm = float(plan.get("loot_mult") or 1.0)
            if _lm < 1:
                gross = int(gross * _lm)
        amount = max(0, min(int(lootable), int(gross)))
        take_cash = min(cash, amount)
        defender.cash = max(0, cash - take_cash)
        need_bank = amount - take_cash
        if need_bank > 0:
            # فقط از بخش غارت‌پذیر سپرده (نه گاوصندوق / نه ۵۰٪ امن)
            looted_bank = await _withdraw_lootable_bank(session, row.defender_id, need_bank)
            amount = take_cash + looted_bank
        attacker.cash = int(getattr(attacker, "cash", 0) or 0) + amount
        plan["loot_pct"] = loot_pct
        plan["lootable_pool"] = lootable

    xp_gain = 0
    if attacker_won:
        xp_gain = RK.win_xp(att_power, def_power)
        await _grant_xp(session, row.attacker_id, xp_gain)

    # 🆕 بچ ۳ — کاپ/لیگ فقط در حالتِ رنکینگ
    rank_res = None
    if ranked:
        try:
            from app.services import rank_service
            rank_res = await rank_service.apply_result(
                session, row.attacker_id, row.defender_id, bool(attacker_won),
                att_power, def_power,
            )
        except Exception:
            rank_res = None

    att_lines = [
        BR.result_banner(attacker_won),
        "",
        f"🎯 هدف: {plan.get('def_name', row.defender_id)}",
        f"🩸 تلفاتِ تو: {military_service.losses_text(att_losses)}",
        f"🩸 تلفاتِ حریف: {military_service.losses_text(def_losses)}",
    ]
    if attacker_won:
        loot_note = f"{int(plan.get('loot_pct') or loot_pct)}٪ از ثروت قابل‌غارت (نقد+۵۰٪ سپرده)"
        att_lines.append(f"💰 غنیمت: <b>{amount:,}$</b> ({loot_note})")
        if looted_bank:
            att_lines.append(f"🏦 از سپرده‌ی بانکیِ هدف: <b>{looted_bank:,}$</b>")
        if amount <= 0:
            att_lines.append("🕳️ هدف واقعاً هیچ دارایی‌ای برای غارت نداشت.")
        att_lines.append(f"⭐ تجربه: +{xp_gain} XP")
    else:
        att_lines.append("💸 غنیمتی در کار نیست — حمله‌ات دفع شد.")
        att_lines.append("⭐ بازنده XP نمی‌گیرد.")
    if rank_res:
        try:
            from app.services import rank_service as _RS
            att_lines += _RS.result_lines(rank_res, for_attacker=True)
        except Exception:
            pass

    def_lines = [
        "🛡️ <b>به قلمروی‌ات حمله شد!</b>",
        "",
        f"⚔️ مهاجم: {plan.get('att_name', row.attacker_id)}",
        ("💀 دفاع شکست خورد." if attacker_won else "🏆 حمله را دفع کردی!"),
        f"🩸 تلفاتِ تو: {military_service.losses_text(def_losses)}",
        f"🩸 ��لفاتِ مهاجم: {military_service.losses_text(att_losses)}",
    ]
    if attacker_won and amount:
        def_lines.append(f"💸 غارت‌شده: <b>{amount:,}$</b>")
        if looted_bank:
            def_lines.append(f"🏦 از سپرده‌ی بانکیِ تو: <b>{looted_bank:,}$</b>")
    if rank_res:
        try:
            from app.services import rank_service as _RS
            def_lines += _RS.result_lines(rank_res, for_attacker=False)
        except Exception:
            pass

    # 🆕 v1.7.6.3 — بیمارستانِ دستی:
    #   در پایانِ هر نبرد برای هر طرف یک «ردیفِ مجروحان» با مهلتِ
    #   ۲۴ ساعتهٔ مستقل ساخته می‌شود. دیگر هیچ درمانِ خودکاری در کار
    #   نیست؛ کاربر باید خودش به بیمارستان برود و هزینهٔ همان ردیف را
    #   بپردازد. اگر در چند جنگ شرکت داشته، چند ردیفِ جداگانه با
    #   زمان‌های متفاوت خواهد داشت. پس از ۲۴ ساعت نیروها می‌میرند.
    try:
        from app.services import hospital_service as _HS

        _att_ward = await _HS.create_ward(
            session, row.attacker_id, att_losses,
            battle_id=int(row.id), mode=str(row.mode or "classic"),
            opponent_name=str(plan.get("def_name") or row.defender_id),
            now=now,
        )
        _def_ward = await _HS.create_ward(
            session, row.defender_id, def_losses,
            battle_id=int(row.id), mode=str(row.mode or "classic"),
            opponent_name=str(plan.get("att_name") or row.attacker_id),
            now=now,
        )
        plan["ward_attacker"] = int(_att_ward.id) if _att_ward is not None else 0
        plan["ward_defender"] = int(_def_ward.id) if _def_ward is not None else 0
        _att_notice = _HS.battle_end_notice(_att_ward).lstrip("\n")
        _def_notice = _HS.battle_end_notice(_def_ward).lstrip("\n")
        if _att_notice:
            att_lines.append("")
            att_lines.append(_att_notice)
        if _def_notice:
            def_lines.append("")
            def_lines.append(_def_notice)
    except Exception:
        pass

    plan["final_attacker"] = "\n".join(att_lines)
    plan["final_defender"] = "\n".join(def_lines)
    plan["loot"] = amount
    row.plan_json = json.dumps(plan, ensure_ascii=False)
    row.finalized = 1

    # 🆕 v1.7.5 — ثبت خبر جنگ تا بخش اخبار/دستیار خالی نماند
    try:
        from app.services import news_service

        att_n = plan.get("att_name") or row.attacker_id
        def_n = plan.get("def_name") or row.defender_id
        mode_fa = "رنکینگ" if ranked else "کلاسیک"
        al = sum(int(v or 0) for v in att_losses.values())
        dl = sum(int(v or 0) for v in def_losses.values())
        if attacker_won:
            # 🆕 v1.7.9.1 — مبلغِ غنیمت در اخبار اعلام نمی‌شود
            txt = (
                f"[{mode_fa}] {att_n} بر {def_n} پیروز شد "
                f"(قدرت {att_power:,} vs {def_power:,} | تلفات {al}/{dl})"
            )
        else:
            txt = (
                f"[{mode_fa}] {def_n} حملهٔ {att_n} را دفع کرد "
                f"(قدرت {att_power:,} vs {def_power:,} | تلفات {al}/{dl})"
            )
        imp = 3 if (att_power + def_power) >= 100_000 or amount >= 50_000_000 else 2
        await news_service.add_news(
            session,
            category="war",
            text=txt,
            importance=imp,
            actor_id=row.attacker_id,
            commit=False,
        )
    except Exception:
        pass

    await session.commit()
    return {"attacker": plan["final_attacker"], "defender": plan["final_defender"], "already": False}


def _scaled_xp(att_power: int, def_power: int) -> int:
    """۴۲ XP برای پیروزی — متناسب با قوی‌تر/ضعیف‌تر بودنِ حریف."""
    a = max(1, int(att_power))
    d = max(1, int(def_power))
    ratio = d / a
    if ratio >= 1.3:
        return WIN_XP
    if ratio <= 0.7:
        return max(14, int(WIN_XP / 3))
    return int(round(14 + (WIN_XP - 14) * ((ratio - 0.7) / 0.6)))


async def _withdraw_bank(session, uid: int, amount: int) -> int:
    """🆕 مرحله ۷۰ — برداشتِ اجباریِ غنیمت از سپرده‌ی بانکِ مافیایی.

    خروجی: مقدارِ واقعیِ برداشت‌شده (ممکن است کمتر از درخواست باشد).
    """
    if int(amount) <= 0:
        return 0
    try:
        from app.models.worldbank import BankAccount
        acc = await session.get(BankAccount, int(uid))
        if acc is None:
            return 0
        have = max(0, int(getattr(acc, "deposit", 0) or 0))
        take = min(have, int(amount))
        acc.deposit = have - take
        return int(take)
    except Exception:
        return 0


async def _withdraw_lootable_bank(session, uid: int, amount: int) -> int:
    """v1.7.7.9 — برداشتِ غنیمت فقط از بخشِ غارت‌پذیرِ سپرده.

    این تابع صدا زده می‌شد ولی هرگز تعریف نشده بود؛ نتیجه NameError
    درِ میانهٔ نهایی‌سازیِ نبرد بود. دو قاعده را رعایت می‌کند:

      • ۵۰٪ سپرده در جنگ امن است (DEPOSIT_WAR_SAFE_PCT)
      • موجودیِ گاوصندوق اصلاً در معرضِ غارت قرار نمی‌گیرد

    پس سقفِ برداشت = ۵۰٪ × (سپرده − گاوصندوق)، دقیقاً همان عددی که
    lootable_pool() به مهاجم وعده داده است.

    خروجی: مقدارِ واقعیِ برداشت‌شده (ممکن است کمتر از درخواست باشد).
    """
    if int(amount) <= 0:
        return 0
    try:
        from app.data import worldbank as WB
        from app.models.worldbank import BankAccount
        acc = await session.get(BankAccount, int(uid))
        if acc is None:
            return 0
        dep = max(0, int(getattr(acc, "deposit", 0) or 0))
        if dep <= 0:
            return 0
        safe_box = max(0, min(dep, int(getattr(acc, "safebox_balance", 0) or 0)))
        exposed = int(WB.lootable_bank_deposit(dep, safe_box))
        take = max(0, min(exposed, int(amount)))
        if take <= 0:
            return 0
        acc.deposit = dep - take
        return int(take)
    except Exception:
        return 0


async def _grant_xp(session, uid: int, amount: int) -> None:
    if amount <= 0:
        return
    try:
        from app.services.leveling import add_xp
        await add_xp(session, uid, amount, source="war")
        return
    except Exception:
        pass
    try:
        p = await _player(session, uid)
        if p is not None:
            p.xp = int(getattr(p, "xp", 0) or 0) + int(amount)
    except Exception:
        pass


# --------------------------- v1.7.6 آتش‌بس + بیمارستان ---------------------------
async def ceasefire(session, battle_id: int, uid: int, now=None) -> tuple[bool, str, LiveBattle | None]:
    """آتش‌بس تا قبل از باز شدن اعلامیه/فاز سوم (index=2). تلفات تا همان فاز اعمال می‌شود."""
    now = now or datetime.utcnow()
    row = await session.get(LiveBattle, int(battle_id))
    if row is None:
        return False, "نبرد پیدا نشد.", None
    if int(uid) not in (int(row.attacker_id), int(row.defender_id)):
        return False, "این نبرد مال تو نیست.", None
    if row.finalized:
        return False, "این نبرد تمام شده.", None
    plan = plan_of(row)
    if plan.get("ceased"):
        return False, "آتش‌بس قبلاً زده شده.", None
    unlocked = phases_unlocked(row, now)
    # فازها 1-based در unlocked؛ آتش‌بس فقط قبل از فاز ۳
    if unlocked >= 3:
        return False, "⏳ اعلامیه سوم باز شده؛ دیگر نمی‌توانی آتش‌بس بزنی.", None
    # تلفات نسبی بر اساس فازهای باز شده (۱ یا ۲)
    frac = 0.35 if unlocked <= 1 else 0.65
    att_full = {k: int(v) for k, v in (plan.get("att_losses") or {}).items()}
    def_full = {k: int(v) for k, v in (plan.get("def_losses") or {}).items()}
    att_cut = {k: max(0, int(round(v * frac))) for k, v in att_full.items() if int(round(v * frac)) > 0}
    def_cut = {k: max(0, int(round(v * frac))) for k, v in def_full.items() if int(round(v * frac)) > 0}
    plan["att_losses"] = att_cut
    plan["def_losses"] = def_cut
    plan["ceased"] = True
    plan["cease_by"] = int(uid)
    plan["cease_phase"] = int(unlocked)
    # نتیجه را بی‌طرف/نیمه‌کاره: برنده قبلی حفظ می‌شود ولی غنیمت کاهش
    plan["loot_mult"] = 0.4 if unlocked <= 1 else 0.7
    row.plan_json = json.dumps(plan, ensure_ascii=False)
    row.ends_at = now  # فوراً قابل finalize
    await session.flush()
    return True, f"🕊️ آتش‌بس ثبت شد (پس از اعلامیه {max(1, unlocked)}). با بروزرسانی نتیجه نهایی را ببین.", row


def personnel_losses_only(losses: dict) -> dict:
    """فقط نیروهای انسانی (cat=soldier) — نه سلاح/وسیله."""
    from app.data import military as MD
    out = {}
    for k, n in (losses or {}).items():
        u = MD.get_unit(k) or {}
        if u.get("cat") in {"soldier", "weapon", "tank", "fighter", "bomber"} and int(n or 0) > 0:
            out[k] = int(n)
    return out


async def hospital_heal(session, uid: int, battle_id: int | None = None) -> tuple[bool, str]:
    """⚠️ منسوخ از v1.7.6.3 — درمانِ خودکار حذف شد.

    رفتارِ قدیم (باگ): همین که کاربر دکمه را می‌زد، ۴۰–۸۰٪ تلفاتِ
    «آخرین» جنگ فوراً و خودکار درمان می‌شد. نه پیامِ پایانِ جنگی بود،
    نه مهلتی، و اگر کاربر در چند جنگ شرکت می‌کرد فقط جنگِ آخر حساب
    می‌شد و مجروحانِ جنگ‌های دیگر برای همیشه گم می‌شدند.

    حالا در پایانِ هر نبرد یک «ردیفِ مجروحان» جداگانه با مهلتِ ۲۴ ساعته
    ساخته می‌شود (app/services/hospital_service.py) و کاربر باید خودش ردیف را
    باز کند و هزینه‌اش را بپردازد.

    این تابع فقط برای سازگاری با دکمه‌های قدیمیِ باقی‌مانده در چت‌ها نگه
    داشته شده؛ هرگز درمان نمی‌کند (همیشه ok=False) و خروجی‌اش در یک
    alert نشان داده می‌شود، پس عمداً بدونِ تگِ HTML است.
    """
    from app.services import hospital_service as _HS

    try:
        wards = await _HS.list_wards(session, uid)
    except Exception:
        wards = []
    if not wards:
        return False, (
            "🏥 بیمارستان / تعمیر\n\n"
            "الان هیچ نیروی مجروحی نداری.\n"
            "بعد از هر نبرد، مجروحانِ همان نبرد یک ردیفِ جداگانه می‌گیرند."
        )
    total_units = sum(int(w.unit_count or 0) for w in wards)
    total_cost = sum(int(w.cost or 0) for w in wards)
    return False, (
        "🏥 بیمارستان / تعمیر\n\n"
        f"{len(wards)} ردیفِ مجروحان داری "
        f"({total_units:,} واحد — {total_cost:,}$).\n"
        f"هر ردیف {_HS.HEAL_DEADLINE_HOURS} ساعت مهلت دارد؛ بعد از آن نیروها می‌میرند.\n\n"
        "برو به: 🎖️ نظامی ← 🏥 بیمارستان / تعمیر"
    )
