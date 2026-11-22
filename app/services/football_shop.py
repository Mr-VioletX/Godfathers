# -*- coding: utf-8 -*-
"""v1.7.9.5 — فروشگاه سرمربی ۵⭐ (پول واقعی) با تأیید ادمین + قیمت قابل‌تنظیم.

الگوی خرید مثل اشتراک: درخواست → تأیید اولیه ادمین (منتظر پرداخت) → کاربر رسید می‌فرستد
→ ادمین رسید را تأیید می‌کند → سرمربی روی باشگاه اعمال می‌شود (۵⭐ + نام). سرمربی‌ها غیرتک‌اند.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select

from app.data import football_coaches as FC
from app.models.football import FootballClub, FootballCoachPurchase

STATUS_PENDING = "pending"              # درخواست ثبت شد — منتظر تأیید اولیه ادمین
STATUS_AWAITING = "awaiting_payment"    # تأیید اولیه — منتظر پرداخت و رسید
STATUS_RECEIPT = "receipt_sent"         # رسید ارسال شد — منتظر تأیید نهایی ادمین
STATUS_DONE = "done"                    # تأیید شد — سرمربی اعمال شد
STATUS_REJECTED = "rejected"


# --------------------------- قیمت (override ادمین) ---------------------------
async def effective_price(session, coach_key: str) -> int:
    """قیمت مؤثر = override ادمین یا قیمت پیش‌فرض کاتالوگ."""
    coach = FC.get(coach_key)
    if coach is None:
        return 0
    try:
        from app.services import admin_service as adm
        raw = await adm.get_setting(session, f"coach_price:{coach_key}")
        if raw is not None and str(raw).isdigit():
            return int(raw)
    except Exception:
        pass
    return int(coach["price"])


async def set_price_override(session, coach_key: str, price: int) -> None:
    from app.services import admin_service as adm
    await adm.set_setting(session, f"coach_price:{coach_key}", str(int(price)), commit=False)
    await session.flush()


# --------------------------- درخواست خرید ---------------------------
async def request_purchase(session, uid: int, coach_key: str) -> tuple[bool, str, FootballCoachPurchase | None]:
    coach = FC.get(coach_key)
    if coach is None:
        return False, "سرمربی نامعتبر.", None
    price = await effective_price(session, coach_key)
    code = uuid.uuid4().hex[:10].upper()
    rec = FootballCoachPurchase(
        owner_id=int(uid), coach_key=coach_key, coach_name=coach["name"],
        price=price, tracking_code=code, status=STATUS_PENDING,
    )
    session.add(rec)
    await session.flush()
    return True, code, rec


async def get_purchase(session, code: str) -> FootballCoachPurchase | None:
    return (await session.execute(
        select(FootballCoachPurchase).where(FootballCoachPurchase.tracking_code == code)
    )).scalar_one_or_none()


async def pending_requests(session, status: str = STATUS_PENDING) -> list[FootballCoachPurchase]:
    return list((await session.execute(
        select(FootballCoachPurchase).where(FootballCoachPurchase.status == status)
        .order_by(FootballCoachPurchase.created_at.asc())
    )).scalars().all())


async def set_status(session, rec: FootballCoachPurchase, status: str, admin_id: int | None = None) -> None:
    rec.status = status
    if admin_id is not None:
        rec.decided_by = int(admin_id)
    rec.decided_at = datetime.utcnow()
    await session.flush()


async def attach_receipt(session, code: str, file_id: str) -> FootballCoachPurchase | None:
    rec = await get_purchase(session, code)
    if rec is None:
        return None
    rec.receipt_file_id = file_id
    rec.status = STATUS_RECEIPT
    await session.flush()
    return rec


# --------------------------- اعمال سرمربی روی باشگاه ---------------------------
async def apply_coach(session, rec: FootballCoachPurchase) -> tuple[bool, str]:
    """بعد از تأیید نهایی: سرمربی ۵⭐ + نام روی باشگاهِ خریدار اعمال می‌شود."""
    club = (await session.execute(
        select(FootballClub).where(FootballClub.owner_id == int(rec.owner_id))
    )).scalar_one_or_none()
    if club is None:
        return False, "خریدار باشگاهی ندارد."
    club.coach_stars = 5   # ۵⭐ فقط از فروشگاه واقعی
    rec.status = STATUS_DONE
    rec.decided_at = datetime.utcnow()
    await session.flush()
    return True, club.name


async def active_coach_name(session, uid: int) -> str | None:
    """نام سرمربیِ فعال = آخرین خریدِ تأییدشده (done)."""
    rec = (await session.execute(
        select(FootballCoachPurchase)
        .where(FootballCoachPurchase.owner_id == int(uid), FootballCoachPurchase.status == STATUS_DONE)
        .order_by(FootballCoachPurchase.decided_at.desc())
    )).scalars().first()
    return rec.coach_name if rec else None


async def my_purchases(session, uid: int, limit: int = 10) -> list:
    return list((await session.execute(
        select(FootballCoachPurchase).where(FootballCoachPurchase.owner_id == int(uid))
        .order_by(FootballCoachPurchase.created_at.desc()).limit(limit)
    )).scalars().all())
