# -*- coding: utf-8 -*-
"""سرویسِ اتحادیه — پرس‌وجوی دیتابیسی و محاسبه‌ی قدرت/رنک.

منطقِ خالص در app/data/alliance.py است.
تابعِ same_alliance کلیدیاست: در war.py و spy.py برای منعِ درگیریِ داخلی به کار می‌رود.
"""
from __future__ import annotations

from sqlalchemy import delete, func, select

from app.data import alliance as A
from app.models.alliance import Alliance, AllianceMember
from app.models.alliance_perm import AlliancePermission  # 🆕 مرحله ۳۰
from app.services import war_service


async def get_membership(session, uid: int) -> AllianceMember | None:
    return (await session.execute(
        select(AllianceMember).where(AllianceMember.player_id == uid)
    )).scalar_one_or_none()


async def get_alliance(session, alliance_id: int) -> Alliance | None:
    return await session.get(Alliance, alliance_id)


async def get_alliance_by_tag(session, tag: str) -> Alliance | None:
    return (await session.execute(
        select(Alliance).where(Alliance.tag == A.normalize_tag(tag))
    )).scalar_one_or_none()


async def member_count(session, alliance_id: int) -> int:
    return int((await session.execute(
        select(func.count()).select_from(AllianceMember).where(
            AllianceMember.alliance_id == alliance_id
        )
    )).scalar() or 0)


async def member_ids(session, alliance_id: int) -> list[int]:
    return list((await session.execute(
        select(AllianceMember.player_id).where(AllianceMember.alliance_id == alliance_id)
    )).scalars().all())


async def same_alliance(session, uid1: int, uid2: int) -> bool:
    """آیا دو کاربر در یک اتحادیه‌اند؟ (مبنای منعِ جنگ/جاسوسیِ داخلی)"""
    if uid1 == uid2:
        return False
    m1 = await get_membership(session, uid1)
    if m1 is None:
        return False
    m2 = await get_membership(session, uid2)
    if m2 is None:
        return False
    return m1.alliance_id == m2.alliance_id


async def member_power_sum(session, alliance_id: int) -> int:
    total = 0
    for uid in await member_ids(session, alliance_id):
        total += await war_service.compute_combat_power(session, uid)
    return total


async def alliance_power_value(session, alliance: Alliance) -> int:
    # 🆕 v1.7.9.1 — قدرتِ نظامی = ارتشِ سربازخانه (mil_level قدیمی بازنشسته شد)
    try:
        from app.services import alliance_military_service as AMS
        mil = await AMS.army_power(session, alliance.id)
    except Exception:
        mil = A.mil_power_for_level(alliance.mil_level)
    psum = await member_power_sum(session, alliance.id)
    return A.alliance_power(mil, psum)


async def compute_all_alliances(session):
    """فهرستِ (alliance, power, members) مرتب‌شده‌ی نزولی برای رتبه‌بندیِ سراسری."""
    alliances = (await session.execute(select(Alliance))).scalars().all()
    rows = []
    for al in alliances:
        power = await alliance_power_value(session, al)
        cnt = await member_count(session, al.id)
        rows.append((al, power, cnt))
    rows.sort(key=lambda r: r[1], reverse=True)
    return rows


async def internal_ranking(session, alliance_id: int):
    """اعضای اتحادیه مرتب‌شده بر اساسِ قدرتِ فردی (نزولی)."""
    members = (await session.execute(
        select(AllianceMember).where(AllianceMember.alliance_id == alliance_id)
    )).scalars().all()
    rows = []
    for m in members:
        power = await war_service.compute_combat_power(session, m.player_id)
        rows.append((m, power))
    rows.sort(key=lambda r: r[1], reverse=True)
    return rows


# ---------------------------------------------------------------------------
# 🆕 مرحله ۳۰ — دسترسی‌هایِ معاون
# ---------------------------------------------------------------------------
async def get_permissions(session, alliance_id: int, player_id: int) -> set[str]:
    rows = (await session.execute(
        select(AlliancePermission.perm_key).where(
            AlliancePermission.alliance_id == alliance_id,
            AlliancePermission.player_id == player_id,
        )
    )).scalars().all()
    return {str(r) for r in rows}


async def set_permission(session, alliance_id: int, player_id: int, perm_key: str, enabled: bool) -> bool:
    """دادن یا گرفتنِ یک دسترسی. خروجی: وضعیتِ نهایی."""
    existing = (await session.execute(
        select(AlliancePermission).where(
            AlliancePermission.alliance_id == alliance_id,
            AlliancePermission.player_id == player_id,
            AlliancePermission.perm_key == perm_key,
        )
    )).scalar_one_or_none()
    if enabled and existing is None:
        session.add(AlliancePermission(
            alliance_id=alliance_id, player_id=player_id, perm_key=perm_key
        ))
    elif not enabled and existing is not None:
        await session.delete(existing)
    await session.flush()
    return bool(enabled)


async def toggle_permission(session, alliance_id: int, player_id: int, perm_key: str) -> bool:
    perms = await get_permissions(session, alliance_id, player_id)
    return await set_permission(session, alliance_id, player_id, perm_key, perm_key not in perms)


async def grant_default_permissions(session, alliance_id: int, player_id: int) -> None:
    for key in A.DEFAULT_DEPUTY_PERMS:
        await set_permission(session, alliance_id, player_id, key, True)


async def clear_permissions(session, alliance_id: int, player_id: int) -> None:
    await session.execute(delete(AlliancePermission).where(
        AlliancePermission.alliance_id == alliance_id,
        AlliancePermission.player_id == player_id,
    ))
    await session.flush()


async def has_permission(session, membership, perm_key: str) -> bool:
    """رئیس همیشه همه‌ی دسترسی‌ها را دارد؛ معاون فقط هرچه رئیس داده."""
    if membership is None:
        return False
    if membership.role == A.ROLE_LEADER:
        return True
    if membership.role != A.ROLE_DEPUTY:
        return False
    perms = await get_permissions(session, membership.alliance_id, membership.player_id)
    return perm_key in perms
