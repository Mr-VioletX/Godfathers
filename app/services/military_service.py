# -*- coding: utf-8 -*-
"""سرویسِ نظامی — پرس‌وجوی دیتابیسی، خرید/ارتقا/آموزش و نبرد.

منطقِ خالص در app/data/military.py است.
❗ این ماژول نباید war_service را import کند (تا حلقه‌ی وارداتی پیش نیاید)؛
برعکس، war_service به‌صورتِ تنبل (lazy) قدرتِ ارتش را از این‌جا می‌گیرد.
"""
from __future__ import annotations

import random
import heapq
from datetime import datetime, timedelta

from sqlalchemy import select

from app.data import military as M
from app.data import war as W
from app.models.military import MilitaryTrainingQueue, MilitaryUnit, MilitaryUpgradeQueue, MilitaryBarracks
from app.models.player import Player


async def get_units(session, uid: int) -> list[MilitaryUnit]:
    # ارتقاهای زمان‌دارِ آماده‌شده قبل از نمایش یا محاسبهٔ قدرت اعمال می‌شوند.
    await settle_upgrades(session, uid)
    res = await session.execute(select(MilitaryUnit).where(MilitaryUnit.owner_id == uid))
    return list(res.scalars().all())


async def get_unit_row(session, uid: int, unit_key: str) -> MilitaryUnit | None:
    res = await session.execute(
        select(MilitaryUnit).where(
            MilitaryUnit.owner_id == uid, MilitaryUnit.unit_key == unit_key
        )
    )
    return res.scalar_one_or_none()


def _stacks(units: list[MilitaryUnit]) -> list[tuple[str, int, int]]:
    out = []
    for u in units:
        if u.count > 0 and M.get_unit(u.unit_key):
            out.append((u.unit_key, int(u.count), int(u.upgrade_level)))
    return out


async def army_stacks(session, uid: int) -> list[tuple[str, int, int]]:
    return _stacks(await get_units(session, uid))


async def army_power(session, uid: int) -> int:
    return M.army_power(await army_stacks(session, uid))


async def has_any_army(session, uid: int) -> bool:
    return bool(await army_stacks(session, uid))



MAX_CONCURRENT_TRAINING = 10

async def schedule_training_queues(session, uid: int) -> None:
    """فقط ۱۰ صف تایمر فعال هستند؛ باقی صف‌ها زمان شروع آینده می‌گیرند."""
    now = datetime.utcnow()
    rows = list((await session.execute(
        select(MilitaryTrainingQueue).where(MilitaryTrainingQueue.owner_id == uid)
        .order_by(MilitaryTrainingQueue.started_at, MilitaryTrainingQueue.id)
    )).scalars().all())
    # اگر داده‌های قدیمی بیش از سقف تایمر فعال داشته باشند، فقط ده تای اول فعال می‌مانند.
    started = [q for q in rows if (q.started_at or now) <= now < q.ready_at]
    active = started[:MAX_CONCURRENT_TRAINING]
    active_ids = {q.id for q in active}
    waiting = [q for q in rows if q.id not in active_ids]
    lanes = [now] * (MAX_CONCURRENT_TRAINING - len(active)) + [q.ready_at for q in active]
    heapq.heapify(lanes)
    for q in waiting:
        # صف غیر فعال از ابتدا و با زمان کامل خودش شروع می‌شود.
        # 🐞 مرحله ۶۷ — زمان همیشه از روی نرخ‌ِ ثابت‌ِ هر واحد حساب می‌شود.
        duration = max(1, M.train_seconds_per_unit(q.unit_key) * max(1, int(q.qty or 1)))
        start = max(now, heapq.heappop(lanes))
        q.started_at = start
        q.ready_at = start + timedelta(seconds=duration)
        heapq.heappush(lanes, q.ready_at)
    await session.flush()

# --------------------------- صفِ پرورشِ نیرو (مرحله ۴۵) ---------------------------
async def settle_training(session, uid: int, *, commit: bool = True) -> int:
    """🆕 مرحله ۴۶ — تحویلِ تک‌تکِ نیروها.

    قبلاً کلِ بچ فقط پس از آماده‌شدنِ آخرین واحد تحویل می‌شد؛ حالا هر واحد
    به‌محضِ ساخته‌شدن به ارتش اضافه می‌شود (تحویلِ پیوسته).
    """
    now = datetime.utcnow()
    res = await session.execute(
        select(MilitaryTrainingQueue).where(MilitaryTrainingQueue.owner_id == uid)
    )
    rows = list(res.scalars().all())
    if not rows:
        return 0
    total = 0
    # ظرفیت و نیروهای موجود فقط یک بار خوانده می‌شوند؛ قبلاً برای هر صف چندین
    # پرس‌وجوی تکراری اجرا می‌شد و صفحهٔ صف با تعداد زیاد کند می‌شد.
    _b, _mx, _levels, capacity = await barracks_status(session, uid)
    current_total = sum(int(u.count or 0) for u in await get_units(session, uid))
    for r in rows:
        qty = max(0, int(r.qty or 0))
        if qty <= 0:
            await session.delete(r)
            continue
        started = r.started_at or now
        # 🐞 مرحله ۶۷ — ریشهٔ باگ‌ِ «۹۰۲ کماندو = ۱۰۵ ساعت ولی ۸۴۰۰ تا = ۲۰ ساعت»:
        # per_unit قبلاً از تقسیم‌ِ span بر qty درمی‌آمد؛ چون qty با هر تحویل کوچک می‌شد
        # و ready_at بازنویسی می‌شد، نرخ در هر محاسبه تغییر می‌کرد و زمان‌ِ کل می‌پرید.
        # حالا نرخ همیشه از جدول‌ِ قطعی‌ِ هر نیرو خوانده می‌شود و هرگز دریفت نمی‌کند.
        per_unit = float(M.train_seconds_per_unit(r.unit_key))
        elapsed = (now - started).total_seconds()
        if per_unit <= 0:
            ready_n = qty if now >= r.ready_at else 0
        else:
            ready_n = int(elapsed // per_unit)
        ready_n = max(0, min(qty, ready_n))
        # تحویل نیرو هرگز از ظرفیت سربازخانه عبور نمی‌کند. در صورت پر بودن،
        # تایمر صف متوقف می‌شود تا کاربر ظرفیت را ارتقا دهد یا صف را لغو کند.
        free = max(0, capacity - current_total)
        if free <= 0:
            r.started_at = now
            r.ready_at = now + timedelta(seconds=max(1, int(per_unit * qty)))
            continue
        ready_n = min(ready_n, free)
        if ready_n <= 0:
            continue
        row = await get_unit_row(session, uid, r.unit_key)
        if row is None:
            row = MilitaryUnit(owner_id=uid, unit_key=r.unit_key, count=ready_n, upgrade_level=0)
            session.add(row)
        else:
            row.count = int(row.count) + ready_n
        total += ready_n
        current_total += ready_n
        remaining = qty - ready_n
        if remaining <= 0:
            await session.delete(r)
        else:
            r.qty = remaining
            r.started_at = started + timedelta(seconds=per_unit * ready_n)
    await session.flush()
    await schedule_training_queues(session, uid)
    if commit:
        await session.commit()
    return total

async def pending_training(session, uid: int) -> list[dict]:
    """همه صف‌ها با تفکیک فعال/غیرفعال؛ فقط فعال‌ها زمان‌سنج دارند."""
    now = datetime.utcnow()
    rows = list((await session.execute(
        select(MilitaryTrainingQueue).where(MilitaryTrainingQueue.owner_id == uid)
        .order_by(MilitaryTrainingQueue.started_at, MilitaryTrainingQueue.id)
    )).scalars().all())
    # یک بار خواندن ظرفیت/ارتش به جای اجرای N+1 query برای هر ردیف ��ف.
    _b, _mx, _levels, capacity = await barracks_status(session, uid)
    current_total = sum(int(x.count or 0) for x in await get_units(session, uid))
    out: list[dict] = []
    for r in rows:
        active = (r.started_at or now) <= now < r.ready_at
        blocked = active and current_total >= capacity
        u = M.get_unit(r.unit_key)
        out.append({
            "id": r.id, "unit_key": r.unit_key,
            "name": u["name"] if u else r.unit_key,
            "qty": int(r.qty),
            "active": active,
            "blocked": blocked,
            "remaining": max(0, int((r.ready_at - now).total_seconds())) if active else 0,
            "starts_in": max(0, int(((r.started_at or now) - now).total_seconds())) if not active else 0,
        })
    return out

async def cancel_inactive_training(session, uid: int, queue_id: int) -> tuple[bool, str]:
    row = (await session.execute(select(MilitaryTrainingQueue).where(
        MilitaryTrainingQueue.id == queue_id, MilitaryTrainingQueue.owner_id == uid
    ))).scalar_one_or_none()
    if row is None:
        return False, "❌ این صف پیدا نشد."
    # صف فعال هم قابل لغو است؛ هزینه پرداخت‌شده به‌صورت کامل بازگردانده می‌شود.
    name = (M.get_unit(row.unit_key) or {}).get("name", row.unit_key)
    qty = int(row.qty or 0)
    player = (await session.execute(select(Player).where(Player.tg_user_id == uid))).scalar_one_or_none()
    if player is None:
        return False, "❌ کاربر پیدا نشد."
    # صف‌های جدید قیمت واقعی پرداخت‌شده را دارند؛ برای صف‌های قدیمی، قیمت همان لول فعلی برگردانده می‌شود.
    original_qty = max(int(row.original_qty or 0), qty)
    refund = int((int(row.paid_cost or 0) * qty) / original_qty) if original_qty else int(row.paid_cost or 0)
    if refund <= 0:
        unit_row = await get_unit_row(session, uid, row.unit_key)
        refund = M.buy_cost(row.unit_key, int(unit_row.upgrade_level) if unit_row else 0) * qty
    player.cash = int(player.cash or 0) + refund
    await session.delete(row)
    await session.flush()
    await schedule_training_queues(session, uid)
    return True, f"✅ صف {name} ×{qty:,} لغو شد و {refund:,}$ به حسابت برگشت."


# --------------------------- خرید ---------------------------
async def buy_unit(session, uid: int, unit_key: str, qty: int) -> tuple[bool, str]:
    """خریدِ qty واحد از یک نوع. قیمتِ هر واحد به سطحِ ارتقای فعلیِ آن نوع بستگی دارد."""
    unit = M.get_unit(unit_key)
    if not unit:
        return False, "❌ این نیرو وجود ندارد."
    qty = max(1, int(qty))
    player = (await session.execute(select(Player).where(Player.tg_user_id == uid))).scalar_one_or_none()
    if player is None:
        return False, "اول /start را بزن."
    if int(player.level or 1) < unit["unlock"]:
        return False, f"🔒 این نیرو از سطحِ {unit['unlock']} باز می‌شود."
    row = await get_unit_row(session, uid, unit_key)
    level = int(row.upgrade_level) if row else 0
    unit_price = M.buy_cost(unit_key, level)
    total = unit_price * qty
    if int(player.cash or 0) < total:
        return False, f"💸 پولت کافی نیست. هزینه: {M.fmt_money(total)}$ (هر واحد {M.fmt_money(unit_price)}$)"
    # ظرفیت سربازخانه، هم نیروهای فعال و هم نیروهای در حال پرورش را پوشش می‌دهد.
    barracks, max_cap, levels, capacity = await barracks_status(session, uid)
    active_total = sum(int(u.count or 0) for u in await get_units(session, uid))
    queued_total = sum(int(q.qty or 0) for q in (await session.execute(select(MilitaryTrainingQueue).where(MilitaryTrainingQueue.owner_id == uid))).scalars().all())
    if active_total + queued_total + qty > capacity:
        return False, f"🪖 ظرفیت سربازخانه کافی نیست: {active_total + queued_total:,}/{capacity:,}. ابتدا سربازخانه را ارتقا بده."
    player.cash = int(player.cash or 0) - total
    await settle_training(session, uid, commit=False)
    secs = M.train_seconds(unit_key, qty)
    now=datetime.utcnow()
    queued_start = now + timedelta(days=3650)
    queue=MilitaryTrainingQueue(owner_id=uid, unit_key=unit_key, qty=qty, paid_cost=total, original_qty=qty, started_at=queued_start, ready_at=queued_start+timedelta(seconds=secs))
    session.add(queue); await session.flush()
    await schedule_training_queues(session, uid)
    starts_in=max(0, int((queue.started_at-now).total_seconds()))
    try:   # Stage 27: XP for buying military units
        from app.data import leveling as _lv

        _lv.add_xp(player, min(250, max(5, total // 10_000)), source="military_buy")
    except Exception:
        pass
    await session.flush()
    return True, (
        f"✅ {qty} واحد {unit['name']} به صفِ پرورش رفت — هزینه: {total:,}$\n"
        f"⏳ زمان پرورش: {M.fmt_eta(secs)} (هر واحد: {M.fmt_eta(M.train_seconds(unit_key, 1))})\n"
        + (f"🕒 شروع صف پس از {M.fmt_eta(starts_in)} دیگر.\n" if starts_in else "🟢 این صف هم‌اکنون فعال است.\n")
        + "🏗️ حداکثر ۱۰ صف هم‌زمان فعال است؛ صف‌های بعدی در بخش غیرفعال می‌مانند و خودکار جای صف تمام‌شده را می‌گیرند."
    )


async def settle_upgrades(session, uid: int) -> int:
    now=datetime.utcnow()
    rows=(await session.execute(select(MilitaryUpgradeQueue).where(MilitaryUpgradeQueue.owner_id==uid, MilitaryUpgradeQueue.ready_at<=now))).scalars().all()
    done=0
    for q in rows:
        row=await get_unit_row(session, uid, q.unit_key)
        if row: row.upgrade_level=max(int(row.upgrade_level or 0), int(q.target_level))
        await session.delete(q); done+=1
    if done:
        await session.flush()
        await session.commit()
    return done

# --------------------------- ارتقا/آموزش ---------------------------
async def upgrade_unit(session, uid: int, unit_key: str) -> tuple[bool, str]:
    """یک سطح ارتقا/آموزشِ یک نوع؛ روی همه‌ی واحدهای موجودِ آن نوع اثر می‌گذارد."""
    unit = M.get_unit(unit_key)
    if not unit:
        return False, "❌ این نیرو وجود ندارد."
    row = await get_unit_row(session, uid, unit_key)
    if row is None or int(row.count) <= 0:
        return False, "اول حداقل یک واحد از این نوع بخر."
    if not M.can_upgrade(int(row.upgrade_level)):
        return False, "⚡ این نوع به سقفِ ارتقا رسیده است."
    player = (await session.execute(select(Player).where(Player.tg_user_id == uid))).scalar_one_or_none()
    if player is None:
        return False, "اول /start را بزن."
    cost = M.upgrade_cost(unit_key, int(row.upgrade_level), int(row.count))
    if int(player.cash or 0) < cost:
        return False, f"💸 پولت کافی نیست. هزینه‌ی ارتقا: {cost:,}$"
    player.cash = int(player.cash or 0) - cost
    target_level = int(row.upgrade_level) + 1
    existing=(await session.execute(select(MilitaryUpgradeQueue).where(MilitaryUpgradeQueue.owner_id==uid, MilitaryUpgradeQueue.unit_key==unit_key))).scalar_one_or_none()
    if existing:
        return False, "⏳ ارتقای این نیرو هنوز در صف است."
    seconds=M.upgrade_seconds(unit_key, int(row.count), target_level)
    session.add(MilitaryUpgradeQueue(owner_id=uid, unit_key=unit_key, target_level=target_level, started_at=datetime.utcnow(), ready_at=datetime.utcnow()+timedelta(seconds=seconds)))
    # Stage 27: give XP for military unit upgrades (XP from everywhere)
    try:
        from app.data import leveling as _lv

        _lv.add_xp(player, (20 + 10 * target_level) // 2, source="military_upgrade")
    except Exception:
        pass
    await session.flush()
    return True, (
        f"⏳ ارتقای {unit['name']} به سطح {target_level} شروع شد — همه‌ی {int(row.count)} واحد پس از اتمام قوی‌تر می‌شوند.\n"
        f"⏱ زمان ارتقا (ثابت برای این نوع/لول، مستقل از تعداد): {M.fmt_eta(seconds)}"
    )


# --------------------------- نبرد ---------------------------
def simulate(att_stacks, def_stacks, rng: random.Random | None = None) -> dict:
    return M.simulate_battle(att_stacks, def_stacks, rng)


async def apply_losses(session, uid: int, losses: dict) -> None:
    """تلفات را از ارتشِ یک بازیکن کم می‌کند."""
    if not losses:
        return
    for key, lost in losses.items():
        row = await get_unit_row(session, uid, key)
        if row is not None:
            row.count = max(0, int(row.count) - int(lost))
    await session.flush()


async def battle_between(session, att_id: int, def_id: int, rng: random.Random | None = None) -> dict:
    """نبردِ کاملِ دو ارتش را شبیه‌سازی و تلفات را در دیتابیس اعمال می‌کند."""
    att = await army_stacks(session, att_id)
    dfn = await army_stacks(session, def_id)
    result = M.simulate_battle(att, dfn, rng)
    await apply_losses(session, att_id, result.get("att_losses", {}))
    await apply_losses(session, def_id, result.get("def_losses", {}))
    return result


def army_summary_lines(units: list[MilitaryUnit]) -> list[str]:
    """خطوطِ خواندنی برای نمایشِ ارتش (دسته‌بندی‌شده)."""
    by_key = {u.unit_key: u for u in units if u.count > 0}
    lines: list[str] = []
    for cat in M.CATEGORY_ORDER:
        keys = [k for k in M.units_in_category(cat) if k in by_key]
        if not keys:
            continue
        lines.append(f"\n<b>{M.CATEGORY_LABELS[cat]}</b>")
        for k in keys:
            u = by_key[k]
            unit = M.get_unit(k)
            pw = M.unit_power(k, int(u.count), int(u.upgrade_level))
            lvl = f" ⚙️لول{u.upgrade_level}" if u.upgrade_level else ""
            lines.append(f"  • {unit['name']}: {u.count}عدد{lvl} — 💥{pw:,}")
    return lines


async def apply_ratio_losses(session, uid: int, ratio: float, *, min_loss: int = 1) -> dict:
    """کم‌کردن درصدیِ منطقی از نیروهای نظامی کاربر. خروجی: {unit_key: lost}.
    ratio مثل 0.03 یعنی ۳٪. اگر کاربر نیرو داشته باشد، حداقل از یک پشته ۱ واحد کم می‌شود.
    """
    ratio = max(0.0, min(0.95, float(ratio or 0)))
    rows = await get_units(session, uid)
    losses: dict[str, int] = {}
    candidates = [r for r in rows if int(r.count or 0) > 0 and M.get_unit(r.unit_key)]
    if not candidates or ratio <= 0:
        return losses
    for row in candidates:
        cnt = int(row.count or 0)
        lost = int(cnt * ratio)
        if lost <= 0 and cnt >= 1 and ratio >= 0.01:
            lost = 1
        lost = max(0, min(cnt, lost))
        if lost:
            row.count = cnt - lost
            losses[row.unit_key] = losses.get(row.unit_key, 0) + lost
    if not losses and min_loss > 0:
        row = max(candidates, key=lambda r: int(r.count or 0))
        row.count = max(0, int(row.count or 0) - min_loss)
        losses[row.unit_key] = min_loss
    await session.flush()
    return losses


async def apply_scaled_losses(
    session,
    uid: int,
    own_power: int,
    enemy_power: int,
    *,
    won: bool,
    intensity: float,
    min_loss: int = 0,
) -> dict:
    """تلفاتِ منطقی را بر اساسِ نسبتِ قدرت حساب و از ارتشِ کاربر کم می‌کند.

    برخلافِ apply_ratio_losses (که درصدِ ثابت از کلِ ارتش می‌گرفت و با ارتشِ بزرگ
    فاجعه می‌شد)، این‌جا کلِ تلفات از W.combat_losses می‌آید که به نسبتِ قدرتِ
    خودت/حریف و قدرتِ حریف گره خورده و سقفِ مطلق دارد؛ سپس متناسب بین پشته‌ها پخش می‌شود.
    خروجی: {unit_key: lost}.
    """
    rows = await get_units(session, uid)
    candidates = [r for r in rows if int(r.count or 0) > 0 and M.get_unit(r.unit_key)]
    total_troops = sum(int(r.count or 0) for r in candidates)
    if not candidates or total_troops <= 0:
        return {}

    total_loss = W.combat_losses(
        total_troops, own_power, enemy_power, won=won, base_intensity=intensity
    )
    # 🆕 کیفیتِ ارتش: میانگینِ سطحِ ارتقا (وزنی به تعدادِ هر پشته) تلفات را کم می‌کند
    weighted_levels = sum(
        int(r.count or 0) * int(getattr(r, "upgrade_level", 0) or 0) for r in candidates
    )
    avg_level = (weighted_levels / total_troops) if total_troops else 0.0
    total_loss = int(round(total_loss * W.quality_mitigation(avg_level)))
    if min_loss > 0:
        total_loss = max(total_loss, min(int(min_loss), total_troops))
    total_loss = max(0, min(total_troops, int(total_loss)))
    if total_loss <= 0:
        return {}

    # تخصیصِ متناسبِ تلفات بین پشته‌ها (به تناسبِ تعدادِ هر پشته)
    alloc: dict[str, int] = {}
    for row in candidates:
        cnt = int(row.count or 0)
        alloc[row.unit_key] = min(cnt, int(total_loss * cnt / total_troops))
    remaining = total_loss - sum(alloc.values())
    # پخشِ باقی‌مانده‌ی گِردکردن روی پشته‌هایی که هنوز ظرفیت دارند (بزرگ‌به‌کوچک)
    order = sorted(candidates, key=lambda r: int(r.count or 0), reverse=True)
    while remaining > 0:
        progressed = False
        for row in order:
            cnt = int(row.count or 0)
            if alloc[row.unit_key] < cnt:
                alloc[row.unit_key] += 1
                remaining -= 1
                progressed = True
                if remaining <= 0:
                    break
        if not progressed:
            break

    losses: dict[str, int] = {}
    for row in candidates:
        take = int(alloc.get(row.unit_key, 0))
        if take > 0:
            row.count = int(row.count or 0) - take
            losses[row.unit_key] = take
    await session.flush()
    return losses


def losses_text(losses: dict) -> str:
    if not losses:
        return "بدون تلفات نظامی"
    parts = []
    for key, n in losses.items():
        unit = M.get_unit(key) or {}
        parts.append(f"{unit.get('name', key)} ×{int(n)}")
    return "، ".join(parts)


async def get_barracks(session, uid: int) -> MilitaryBarracks:
    row=await session.get(MilitaryBarracks, uid)
    if row is None:
        row=MilitaryBarracks(owner_id=uid, level=1); session.add(row); await session.flush()
    return row
async def barracks_max_capacity(session) -> int:
    from app.models.admin import GameNumberSetting
    row=await session.get(GameNumberSetting, "military.barracks_max_capacity")
    try: return max(M.BARRACKS_DEFAULT_MAX_CAPACITY, int(float(row.value))) if row and row.value else M.BARRACKS_DEFAULT_MAX_CAPACITY
    except Exception: return M.BARRACKS_DEFAULT_MAX_CAPACITY
async def barracks_status(session, uid: int) -> tuple[MilitaryBarracks,int,int,int]:
    b=await get_barracks(session,uid)
    if b.upgrading_until and b.upgrading_until <= datetime.utcnow():
        b.level += 1; b.upgrading_until = None; await session.flush()
    mx=await barracks_max_capacity(session); levels=M.barracks_levels(mx)
    return b,mx,levels,M.barracks_capacity(b.level,mx)
async def start_barracks_upgrade(session, uid: int) -> tuple[bool, str]:
    b, mx, levels, cap = await barracks_status(session, uid)
    now = datetime.utcnow()
    if b.upgrading_until and b.upgrading_until > now:
        return False, "ارتقای سربازخانه هنوز در جریان است."
    if b.level >= levels:
        return False, "سربازخانه به سقف ظرفیت رسیده است."
    p = (await session.execute(select(Player).where(Player.tg_user_id == uid))).scalar_one_or_none()
    cost = M.barracks_upgrade_cost(b.level, mx)
    if p is None:
        return False, "کاربر پیدا نشد."
    if int(p.cash or 0) < cost:
        return False, f"پول کافی نداری؛ هزینه: {M.fmt_money(cost)}$"
    p.cash = int(p.cash or 0) - cost
    b.upgrading_until = now + timedelta(days=1)
    await session.flush()
    await session.commit()
    return True, "ارتقای سربازخانه آغاز شد؛ تا ۲۴ ساعت دیگر آماده می‌شود."


async def add_units_bulk(session, uid: int, units: dict) -> None:
    """v1.7.6 — افزودن تعداد به یگان‌های موجود (بیمارستان).

    🐞 v1.7.6.3 — رفعِ باگ: نامِ ستون‌ها اشتباه بود. مدلِ MilitaryUnit
    ستون‌های «count» و «upgrade_level» دارد؛ «qty» و «level» مالِ جدولِ
    دیگری (MilitaryTrainingQueue) است. پس ساختِ ردیفِ تازه با TypeError و
    به‌روزرسانیِ ردیفِ موجود با AttributeError شکست می‌خورد و نیروهای
    درمان‌شدهٔ بیمارستان هرگز به ارتش برنمی‌گشتند (پول کم می‌شد،
    نیرو اضافه نمی‌شد). select و MilitaryUnit هم در سراسرِ ماژول import
    شده‌اند، پس importِ داخلِ تابع حذف شد (همان الگویی که در
    battle_live باعثِ UnboundLocalError شده بود).
    """
    for key, qty in (units or {}).items():
        q = max(0, int(qty or 0))
        if q <= 0:
            continue
        row = (await session.execute(
            select(MilitaryUnit).where(MilitaryUnit.owner_id == int(uid), MilitaryUnit.unit_key == str(key))
        )).scalar_one_or_none()
        if row is None:
            session.add(MilitaryUnit(owner_id=int(uid), unit_key=str(key), count=q, upgrade_level=0))
        else:
            row.count = int(row.count or 0) + q
    await session.flush()
