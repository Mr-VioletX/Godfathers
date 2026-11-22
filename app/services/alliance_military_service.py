# -*- coding: utf-8 -*-
"""v1.7.9.1 — سرویسِ ارتشِ اتحادیه: سربازخانه، تولیدِ اسکادرانی (دستی/خودکار)،
ارتقاها (۳۰×، فقط از صندوق)، بیمارستان و کسرِ اشتراکِ عضویت.

منطقِ خالص در app/data/alliance_military.py است؛ این ماژول فقط پرس‌وجو و اعمال است.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta

from sqlalchemy import select

from app.data import alliance as A
from app.data import alliance_military as AM
from app.models.alliance import Alliance, AllianceMember
from app.models.alliance_war import (
    AllianceBarracks,
    AllianceFeeState,
    AllianceTrainQueue,
    AllianceUnitStack,
    AllianceWard,
)

WARD_HOURS = 24          # مهلتِ درمانِ مجروحان (مثل بیمارستانِ عادی)


# --------------------------- سربازخانه و پشته‌ها ---------------------------
async def get_or_create_barracks(session, alliance_id: int) -> AllianceBarracks:
    row = await session.get(AllianceBarracks, int(alliance_id))
    if row is None:
        row = AllianceBarracks(alliance_id=int(alliance_id), level=1)
        session.add(row)
        await session.flush()
    return row


async def stacks(session, alliance_id: int) -> list[tuple[str, int, int]]:
    """[(unit_key, count, level)] — فقط پشته‌های غیرخالی."""
    rows = (await session.execute(
        select(AllianceUnitStack).where(AllianceUnitStack.alliance_id == int(alliance_id))
    )).scalars().all()
    return [(r.unit_key, int(r.count or 0), int(r.level or 0)) for r in rows if int(r.count or 0) > 0]


async def stack_counts(session, alliance_id: int) -> dict:
    return {k: c for k, c, _lv in await stacks(session, alliance_id)}


async def army_power(session, alliance_id: int) -> int:
    return AM.stacks_power(await stacks(session, alliance_id))


async def _stack_row(session, alliance_id: int, unit_key: str) -> AllianceUnitStack | None:
    return (await session.execute(
        select(AllianceUnitStack).where(
            AllianceUnitStack.alliance_id == int(alliance_id),
            AllianceUnitStack.unit_key == unit_key,
        )
    )).scalar_one_or_none()


async def _add_units(session, alliance_id: int, unit_key: str, units: int) -> None:
    row = await _stack_row(session, alliance_id, unit_key)
    if row is None:
        row = AllianceUnitStack(alliance_id=int(alliance_id), unit_key=unit_key, count=0, level=0)
        session.add(row)
        await session.flush()
    row.count = int(row.count or 0) + int(units)


# --------------------------- صفِ تولید ---------------------------
async def pending_training(session, alliance_id: int) -> list:
    return list((await session.execute(
        select(AllianceTrainQueue)
        .where(AllianceTrainQueue.alliance_id == int(alliance_id))
        .order_by(AllianceTrainQueue.ready_at.asc())
    )).scalars().all())


async def queued_counts(session, alliance_id: int) -> dict:
    out: dict[str, int] = {}
    for row in await pending_training(session, alliance_id):
        out[row.unit_key] = out.get(row.unit_key, 0) + int(row.units or 0)
    return out


async def settle_training(session, alliance_id: int, now: datetime | None = None) -> int:
    """ردیف‌های آماده‌ی صف را به پشته منتقل می‌کند. خروجی: تعدادِ واحدهای اضافه‌شده."""
    now = now or datetime.utcnow()
    ready = [r for r in await pending_training(session, alliance_id) if r.ready_at <= now]
    done = 0
    for row in ready:
        await _add_units(session, alliance_id, row.unit_key, int(row.units or 0))
        done += int(row.units or 0)
        await session.delete(row)
    if ready:
        await session.flush()
    return done


async def capacity_free(session, alliance_id: int) -> int:
    b = await get_or_create_barracks(session, alliance_id)
    cap = AM.barracks_capacity(b.level)
    used = sum(c for _k, c, _lv in await stacks(session, alliance_id))
    queued = sum(int(r.units or 0) for r in await pending_training(session, alliance_id))
    return max(0, cap - used - queued)


# --------------------------- خرید و ارتقا (فقط از صندوق) ---------------------------
async def buy_squadron(session, alliance: Alliance, unit_key: str, squads: int = 1) -> tuple[bool, str]:
    u = AM.get_unit(unit_key)
    if u is None:
        return False, "واحدِ نامعتبر."
    squads = max(1, int(squads))
    b = await get_or_create_barracks(session, alliance.id)
    if b.level < int(u["unlock_barracks"]):
        return False, f"🔒 این واحد به سربازخانه‌ی سطح {u['unlock_barracks']} نیاز دارد (فعلی: {b.level})."
    cost = AM.squad_cost(unit_key, squads)
    if int(alliance.treasury or 0) < cost:
        return False, f"صندوق کافی نیست. هزینه: {cost:,}$"
    free = await capacity_free(session, alliance.id)
    units = squads * int(u["squad"])
    if units > free:
        return False, f"ظرفیتِ سربازخانه کافی نیست (خالی: {free:,} — موردنیاز: {units:,})."
    alliance.treasury = int(alliance.treasury or 0) - cost
    ready_at = datetime.utcnow() + timedelta(seconds=AM.train_seconds(unit_key, squads))
    session.add(AllianceTrainQueue(
        alliance_id=int(alliance.id), unit_key=unit_key,
        squads=squads, units=units, ready_at=ready_at,
    ))
    await session.flush()
    mins = max(1, int((ready_at - datetime.utcnow()).total_seconds() // 60))
    h, m = divmod(mins, 60)
    when = f"{h} ساعت و {m} دقیقه" if h else f"{m} دقیقه"
    return True, f"✅ {squads} اسکادران {u['name']} ({units:,} نیرو) در صفِ تولید است — آماده تا {when} دیگر. هزینه: {cost:,}$ از صندوق."


async def upgrade_unit(session, alliance: Alliance, unit_key: str) -> tuple[bool, str]:
    u = AM.get_unit(unit_key)
    if u is None:
        return False, "واحدِ نامعتبر."
    row = await _stack_row(session, alliance.id, unit_key)
    if row is None or int(row.count or 0) <= 0:
        return False, "اول از این واحد بساز، بعد ارتقا بده."
    level = int(row.level or 0)
    if level >= AM.MAX_UNIT_LEVEL:
        return False, "این واحد در بیشینه‌ی سطح است. ✅"
    cost = AM.unit_upgrade_cost(unit_key, level)
    if int(alliance.treasury or 0) < cost:
        return False, f"صندوق کافی نیست. هزینه: {cost:,}$"
    alliance.treasury = int(alliance.treasury or 0) - cost
    row.level = level + 1
    await session.flush()
    return True, f"✅ {u['name']} به سطح {row.level} رسید (+۱۵٪ قدرت هر سطح). هزینه: {cost:,}$ از صندوق."


async def upgrade_barracks(session, alliance: Alliance) -> tuple[bool, str]:
    b = await get_or_create_barracks(session, alliance.id)
    if b.level >= AM.BARRACKS_MAX_LEVEL:
        return False, "سربازخانه در بیشینه‌ی سطح است. ✅"
    cost = AM.barracks_upgrade_cost(b.level)
    if int(alliance.treasury or 0) < cost:
        return False, f"صندوق کافی نیست. هزینه: {cost:,}$"
    alliance.treasury = int(alliance.treasury or 0) - cost
    b.level += 1
    await session.flush()
    return True, (
        f"✅ سربازخانه به سطح {b.level} رسید — ظرفیت: {AM.barracks_capacity(b.level):,} نیرو. "
        f"هزینه: {cost:,}$ از صندوق."
    )


# --------------------------- تلفات و بیمارستان ---------------------------
async def apply_losses(session, alliance_id: int, losses_base: dict) -> None:
    """تلفات با کلیدهای جنگِ عادی می‌آید؛ به کلیدهای اتحادیه ترجمه و کسر می‌شود."""
    losses = AM.to_alliance_losses(losses_base)
    for key, n in losses.items():
        row = await _stack_row(session, alliance_id, key)
        if row is None:
            continue
        row.count = max(0, int(row.count or 0) - int(n))
    await session.flush()


def losses_text(losses_base: dict) -> str:
    losses = AM.to_alliance_losses(losses_base)
    parts = []
    for key, n in losses.items():
        u = AM.get_unit(key)
        parts.append(f"{(u['name'] if u else key)} ×{int(n):,}")
    return "، ".join(parts) if parts else "بدونِ تلفات"


async def create_ward(session, alliance_id: int, losses_base: dict, battle_id: int | None,
                      opponent_name: str | None, now: datetime | None = None) -> AllianceWard | None:
    """۴۰–۸۰٪ از تلفاتِ پیاده/تسلیحات به‌عنوانِ مجروح ثبت می‌شود (منطقِ بیمارستانِ عادی)."""
    from app.services import hospital_service as HS
    units_base = HS.wounded_from_losses(losses_base)
    if not units_base:
        return None
    units = AM.to_alliance_losses(units_base)
    cost = 0
    for key, n in units.items():
        u = AM.get_unit(key)
        if u:
            cost += int(u["cost"]) * int(n) * int(HS.HEAL_COST_PCT) // 100
    now = now or datetime.utcnow()
    ward = AllianceWard(
        alliance_id=int(alliance_id), battle_id=int(battle_id) if battle_id else None,
        opponent_name=(str(opponent_name)[:64] if opponent_name else None),
        units_json=json.dumps(units, ensure_ascii=False),
        unit_count=int(sum(units.values())),
        cost=int(cost), status="wounded",
        expires_at=now + timedelta(hours=WARD_HOURS),
    )
    session.add(ward)
    await session.flush()
    return ward


def ward_units(ward: AllianceWard) -> dict:
    try:
        return {str(k): int(v) for k, v in json.loads(ward.units_json or "{}").items()}
    except Exception:
        return {}


async def _expire_old_wards(session, alliance_id: int, now: datetime) -> None:
    rows = (await session.execute(
        select(AllianceWard).where(
            AllianceWard.alliance_id == int(alliance_id),
            AllianceWard.status == "wounded",
            AllianceWard.expires_at <= now,
        )
    )).scalars().all()
    for r in rows:
        r.status = "dead"   # مهلت تمام شد — نیروها مردند
    if rows:
        await session.flush()


async def active_wards(session, alliance_id: int, now: datetime | None = None) -> list:
    now = now or datetime.utcnow()
    await _expire_old_wards(session, alliance_id, now)
    return list((await session.execute(
        select(AllianceWard).where(
            AllianceWard.alliance_id == int(alliance_id),
            AllianceWard.status == "wounded",
            AllianceWard.expires_at > now,
        ).order_by(AllianceWard.expires_at.asc())
    )).scalars().all())


async def healable_counts(session, alliance_id: int, now: datetime | None = None) -> dict:
    out: dict[str, int] = {}
    for ward in await active_wards(session, alliance_id, now):
        for k, n in ward_units(ward).items():
            out[k] = out.get(k, 0) + int(n)
    return out


async def heal_ward(session, alliance: Alliance, ward_id: int, now: datetime | None = None) -> tuple[bool, str]:
    now = now or datetime.utcnow()
    ward = await session.get(AllianceWard, int(ward_id))
    if ward is None or int(ward.alliance_id) != int(alliance.id):
        return False, "ردیفِ مجروحان پیدا نشد."
    if ward.status != "wounded":
        return False, "این ردیف قبلاً رسیدگی شده."
    if ward.expires_at <= now:
        ward.status = "dead"
        await session.flush()
        return False, "⏰ مهلتِ درمان تمام شده بود؛ نیروها از دست رفتند."
    cost = int(ward.cost or 0)
    if int(alliance.treasury or 0) < cost:
        return False, f"صندوق کافی نیست. هزینه‌ی درمان: {cost:,}$"
    alliance.treasury = int(alliance.treasury or 0) - cost
    for key, n in ward_units(ward).items():
        await _add_units(session, alliance.id, key, n)
    ward.status = "healed"
    await session.flush()
    return True, f"✅ {int(ward.unit_count or 0):,} نیرو به ارتش برگشتند. هزینه: {cost:,}$ از صندوق."


# --------------------------- صندوق: واریز و امتیازِ مشارکت ---------------------------
async def deposit(session, alliance: Alliance, member: AllianceMember, player, amount: int) -> tuple[bool, str]:
    """واریز از جیبِ عضو به صندوق — جدا از هزینه‌ی اشتراک؛ امتیازِ مشارکت (contributed) ثبت می‌شود."""
    amount = int(amount)
    if amount <= 0:
        return False, "مبلغ باید مثبت باشد."
    cash = int(getattr(player, "cash", 0) or 0)
    if cash < amount:
        return False, f"موجودی کافی نیست. (نقد: {cash:,}$)"
    player.cash = cash - amount
    alliance.treasury = int(alliance.treasury or 0) + amount
    member.contributed = int(member.contributed or 0) + amount
    await session.flush()
    return True, (
        f"✅ {amount:,}$ به صندوقِ اتحادیه واریز شد.\n"
        f"🎖️ مجموعِ مشارکتِ تو: {int(member.contributed or 0):,}$"
    )


# --------------------------- تولیدِ خودکارِ روزانه ---------------------------
def auto_minimums(barracks: AllianceBarracks) -> dict:
    try:
        raw = json.loads(barracks.auto_min_json or "{}")
        return {str(k): max(0, int(v)) for k, v in raw.items() if AM.get_unit(str(k))}
    except Exception:
        return {}


async def set_auto_minimum(session, alliance_id: int, unit_key: str, value: int) -> None:
    b = await get_or_create_barracks(session, alliance_id)
    mins = auto_minimums(b)
    mins[unit_key] = max(0, int(value))
    b.auto_min_json = json.dumps(mins, ensure_ascii=False)
    await session.flush()


async def auto_produce_alliance(session, alliance: Alliance, now: datetime | None = None) -> dict:
    """اجرای روزانه‌ی تولیدِ خودکار برای یک اتحادیه (با نگهبانِ تاریخِ تهران).

    منطق (تأییدشده): اول نیروهای قابل‌درمانِ بیمارستان به حداقل حساب می‌شوند،
    بعد ظرفیتِ خالی و خزانه چک می‌شود و تا حداقل ساخته می‌شود؛ نیروی مرده‌شده
    در بیمارستان در healable نیست و کمبودش دوباره ساخته می‌شود.
    """
    try:
        from app.data.news import now_tehran
    except Exception:
        now_tehran = None
    now = now or datetime.utcnow()
    b = await get_or_create_barracks(session, alliance.id)
    if not int(b.auto_enabled or 0):
        return {"built": 0}
    today = (now_tehran().date() if now_tehran else now.date())
    if b.last_auto_at is not None:
        last_day = b.last_auto_at.date()
        if last_day >= today:
            return {"built": 0}
    await settle_training(session, alliance.id, now)
    mins = auto_minimums(b)
    if not mins:
        b.last_auto_at = now
        await session.flush()
        return {"built": 0}
    alive = await stack_counts(session, alliance.id)
    queued = await queued_counts(session, alliance.id)
    healable = await healable_counts(session, alliance.id, now)
    free = await capacity_free(session, alliance.id)
    plan = AM.auto_build_plan(alive, healable, queued, free, mins, int(alliance.treasury or 0))
    built_units = 0
    spent = 0
    lines = []
    for key, squads, cost in plan:
        u = AM.get_unit(key)
        alliance.treasury = int(alliance.treasury or 0) - cost
        ready_at = now + timedelta(seconds=AM.train_seconds(key, squads))
        session.add(AllianceTrainQueue(
            alliance_id=int(alliance.id), unit_key=key,
            squads=squads, units=squads * int(u["squad"]), ready_at=ready_at,
        ))
        built_units += squads * int(u["squad"])
        spent += cost
        lines.append(f"{u['name']} ×{squads} اسکادران")
    b.last_auto_at = now
    await session.flush()
    return {"built": built_units, "spent": spent, "lines": lines}


# --------------------------- کسرِ اشتراکِ عضویت ---------------------------
async def charge_membership_fee(session, alliance: Alliance, now: datetime | None = None) -> dict:
    """کسرِ sub_pct٪ از درآمدِ اعضا هر sub_days روز → صندوق + پیامِ اطلاع به هر عضو.

    (قبلاً این کسر هیچ‌جا اجرا نمی‌شد — v1.7.9.1 اضافه شد.)
    خروجی: {"charged": مبلغ کل, "members": n, "notify": [ (uid, amount) ]}
    """
    now = now or datetime.utcnow()
    state = await session.get(AllianceFeeState, int(alliance.id))
    if state is None:
        state = AllianceFeeState(alliance_id=int(alliance.id), last_charge_at=now)
        session.add(state)
        await session.flush()
        return {"charged": 0, "members": 0, "notify": []}   # نوبتِ اول: فقط ثبتِ مبنا
    days = max(1, int(alliance.sub_days or 1))
    if state.last_charge_at and now - state.last_charge_at < timedelta(days=days):
        return {"charged": 0, "members": 0, "notify": []}
    pct = max(A.SUB_PCT_MIN, min(A.SUB_PCT_MAX, int(alliance.sub_pct or 0)))
    from app.services import alliance_service, war_service
    from app.handlers.profile import get_player
    total = 0
    notified: list[tuple[int, int]] = []
    for uid in await alliance_service.member_ids(session, alliance.id):
        try:
            income = await war_service.daily_income(session, uid)
        except Exception:
            income = 0
        fee = int(max(0, income) * pct / 100) * days
        if fee <= 0:
            continue
        player = await get_player(session, uid)
        if player is None:
            continue
        cash = int(getattr(player, "cash", 0) or 0)
        take = min(cash, fee)
        if take <= 0:
            continue
        player.cash = cash - take
        total += take
        notified.append((int(uid), int(take)))
    state.last_charge_at = now
    alliance.treasury = int(alliance.treasury or 0) + total
    await session.flush()
    return {"charged": total, "members": len(notified), "notify": notified}


# --------------------------- 🆕 v1.8.2.0 — نمایش/لغوِ صفِ تولید ---------------------------
async def queue_items(session, alliance_id: int) -> list[dict]:
    """همه‌ی بچ‌های در صف (مرتب بر اساسِ نزدیک‌ترین آماده‌شدن) برای منوی صف.

    خروجی: [{id, unit_key, name, squads, units, remaining}]
    """
    now = datetime.utcnow()
    out: list[dict] = []
    for r in await pending_training(session, alliance_id):
        u = AM.get_unit(r.unit_key)
        out.append({
            "id": int(r.id),
            "unit_key": r.unit_key,
            "name": (u["name"] if u else r.unit_key),
            "squads": int(r.squads or 0),
            "units": int(r.units or 0),
            "remaining": max(0, int((r.ready_at - now).total_seconds())),
        })
    return out


async def cancel_training(session, alliance: Alliance, queue_id: int) -> tuple[bool, str]:
    """لغوِ یک بچِ صف و بازگشتِ کاملِ هزینه به صندوق (مثلِ cancel_inactive_trainingِ
    بخشِ نظامی، ولی بازپرداخت به صندوقِ اتحادیه چون پول از همانجا رفته).

    نکته: جدولِ صف، هزینه‌ی پرداخت‌شده را نگه نمی‌دارد؛ بازپرداخت با فرمولِ فعلیِ
    squad_cost محاسبه می‌شود (همان رویکردِ سازگاریِ صف‌های قدیمی در بخشِ نظامی).
    """
    row = await session.get(AllianceTrainQueue, int(queue_id))
    if row is None or int(row.alliance_id) != int(alliance.id):
        return False, "❌ این صف پیدا نشد (شاید همین حالا تمام شده)."
    u = AM.get_unit(row.unit_key)
    name = (u["name"] if u else row.unit_key)
    squads = max(1, int(row.squads or 1))
    units = int(row.units or 0)
    refund = AM.squad_cost(row.unit_key, squads)
    alliance.treasury = int(alliance.treasury or 0) + refund
    await session.delete(row)
    await session.flush()
    return True, f"✅ صفِ {name} — {squads} اسکادران ({units:,} نیرو) لغو شد و {refund:,}$ به صندوق برگشت."


# --------------------------- 🆕 v1.8.2.1 — تکمیل فوری همهٔ صف‌ها (ادمین) ---------------------------
async def admin_force_settle_all(session) -> tuple[int, int]:
    """همهٔ ردیف‌های صفِ تولیدِ همهٔ اتحادیه‌ها را فوری تسویه می‌کند. خروجی: (تعداد اتحادیه‌ها, تعداد واحدها)."""
    from sqlalchemy import select as _sel
    far = datetime.utcnow() + timedelta(days=3650)  # آیندهٔ دور ← همه آماده
    aids = (await session.execute(_sel(AllianceTrainQueue.alliance_id).distinct())).scalars().all()
    total = 0
    for aid in aids:
        total += await settle_training(session, int(aid), now=far)
    return len(aids), total
