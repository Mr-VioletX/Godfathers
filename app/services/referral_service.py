# -*- coding: utf-8 -*-
"""سیستم لینک دعوت — v1.7.2

رفع‌ها:
  • پارس مطمئن deep-link
  • پاداش و ثبت دعوت حتی وقتی فقط یکی از گزینه‌ها روشن است
  • پیام موفقیت برای دعوت‌کننده و دعوت‌شده
  • پاک‌سازی رکورد دعوت هنگام حذف کامل کاربر
"""
from __future__ import annotations

from datetime import timedelta

from sqlalchemy import delete, func, or_, select

from app.models.player import Player
from app.models.referral import PendingReferral, Referral, ReferralBonusDay
from app.services import admin_service as adm

try:
    from app.data.news import now_tehran
except Exception:  # pragma: no cover
    from datetime import datetime

    def now_tehran():
        return datetime.utcnow()

CASH_ON = "referral_cash_enabled"
CASH_AMOUNT = "referral_cash_amount"
BONUS_ON = "referral_bonus_enabled"
BONUS_PCT = "referral_bonus_pct"


async def _int_setting(session, key: str, default: int = 0) -> int:
    try:
        raw = await adm.get_setting(session, key)
        if raw is None or str(raw).strip() == "":
            return int(default)
        return int(raw)
    except Exception:
        return int(default)


async def get_config(session) -> dict:
    return {
        "cash_on": str(await adm.get_setting(session, CASH_ON) or "0") == "1",
        "cash_amount": await _int_setting(session, CASH_AMOUNT, 0),
        "bonus_on": str(await adm.get_setting(session, BONUS_ON) or "0") == "1",
        "bonus_pct": await _int_setting(session, BONUS_PCT, 0),
    }


async def config(session):
    """سازگاری با کد قدیمی."""
    return await get_config(session)


async def set_config(session, key, value):
    await adm.set_setting(session, key, str(value), commit=False)


async def bonus_pct(session, uid) -> int:
    today = now_tehran().date()
    rows = (
        await session.execute(
            select(ReferralBonusDay.pct).where(
                ReferralBonusDay.referrer_id == int(uid),
                ReferralBonusDay.active_date == today,
            )
        )
    ).scalars().all()
    return sum(int(x or 0) for x in rows)


async def referral_count(session, uid) -> int:
    return int(
        (
            await session.execute(
                select(func.count())
                .select_from(Referral)
                .where(Referral.referrer_id == int(uid))
            )
        ).scalar()
        or 0
    )


async def clear_user_referrals(session, uid: int) -> int:
    """پاک کردن همه‌ی ردپای دعوت این کاربر (دعوت‌کننده یا دعوت‌شده)."""
    uid = int(uid)
    n = 0
    r1 = await session.execute(
        delete(Referral).where(or_(Referral.invited_id == uid, Referral.referrer_id == uid))
    )
    n += int(r1.rowcount or 0)
    r2 = await session.execute(
        delete(ReferralBonusDay).where(
            or_(ReferralBonusDay.invited_id == uid, ReferralBonusDay.referrer_id == uid)
        )
    )
    n += int(r2.rowcount or 0)
    return n


async def reward_new_player(session, referrer_id, invited_id):
    """ثبت دعوت موفق + پاداش.

    خروجی dict یا None اگر دعوت معتبر نباشد.
    """
    if not referrer_id:
        return None
    try:
        rid = int(referrer_id)
        iid = int(invited_id)
    except (TypeError, ValueError):
        return None
    if rid <= 0 or iid <= 0 or rid == iid:
        return None

    if await session.get(Referral, iid):
        return None

    # v1.7.6.2 — PK جدول players فیلد id است نه tg_user_id
    referrer = (await session.execute(select(Player).where(Player.tg_user_id == rid))).scalar_one_or_none()
    invited = (await session.execute(select(Player).where(Player.tg_user_id == iid))).scalar_one_or_none()
    if not referrer or not invited:
        return None

    session.add(Referral(invited_id=iid, referrer_id=rid))
    c = await get_config(session)
    notes: list[str] = []
    cash_given = 0
    bonus_day = None
    bonus_given = 0

    if c["cash_on"] and c["cash_amount"] > 0:
        cash_given = int(c["cash_amount"])
        referrer.cash = int(referrer.cash or 0) + cash_given
        notes.append(f"{cash_given:,}$ نقد")

    if c["bonus_on"] and c["bonus_pct"] > 0:
        day = now_tehran().date()
        while True:
            used = int(
                (
                    await session.execute(
                        select(func.count())
                        .select_from(ReferralBonusDay)
                        .where(
                            ReferralBonusDay.referrer_id == rid,
                            ReferralBonusDay.active_date == day,
                        )
                    )
                ).scalar()
                or 0
            )
            if used < 2:
                break
            day = day + timedelta(days=1)
        bonus_given = int(c["bonus_pct"])
        bonus_day = day
        session.add(
            ReferralBonusDay(
                referrer_id=rid,
                invited_id=iid,
                active_date=day,
                pct=bonus_given,
            )
        )
        notes.append(f"+{bonus_given}٪ بونس درآمد برای {day.strftime('%Y/%m/%d')}")

    return {
        "ok": True,
        "referrer_id": rid,
        "invited_id": iid,
        "referrer_name": str(getattr(referrer, "name", None) or rid),
        "invited_name": str(getattr(invited, "name", None) or iid),
        "notes": notes,
        "cash": cash_given,
        "bonus_pct": bonus_given,
        "bonus_day": bonus_day,
    }


def inviter_success_text(result: dict) -> str:
    notes = result.get("notes") or []
    if notes:
        reward_line = "🎁 پاداش: " + " | ".join(notes)
    else:
        reward_line = (
            "🎁 پاداش نقدی/بونس فعلاً توسط ادمین خاموش است، ولی دعوت ثبت شد."
        )
    return (
        f"🎉 دعوتت موفق شد!\n"
        f"👤 <b>{result.get('invited_name')}</b> با لینک تو وارد بازی شد.\n"
        f"{reward_line}"
    )


def invitee_success_text(result: dict) -> str:
    return (
        f"🤝 دعوت موفق!\n"
        f"تو با لینک دعوتِ <b>{result.get('referrer_name')}</b> وارد بازی شدی.\n"
        f"به دنیای گادفادر خوش آمدی 🎩"
    )



def parse_referral_payload(text, self_id) -> int | None:
    """استخراج امن ref_XXXX از متن /start — نسخه‌ی خالصِ مشترک (v1.7.9).

    بدون وابستگی به aiogram؛ برای میدلور جوین اجباری و تست‌ها.
    """
    raw = (text or "").strip()
    if not raw:
        return None
    candidates: list[str] = []
    parts = raw.split()
    if len(parts) >= 2:
        candidates.append(parts[-1].strip())
    candidates.append(raw)
    for item in candidates:
        if not item:
            continue
        token = item
        if "start=" in token:
            token = token.split("start=", 1)[1]
        token = token.split("&", 1)[0].strip()
        if token.startswith("ref_"):
            token = token[4:]
        try:
            cand = int(token)
        except ValueError:
            continue
        if cand > 0 and cand != int(self_id):
            return cand
    return None


async def stash_pending(session, tg_user_id, referrer_id, commit: bool = True) -> None:
    """ذخیره‌ی پایدارِ دعوتِ در انتظار؛ آخرین لینک جایگزینِ قبلی می‌شود (v1.7.9)."""
    try:
        uid = int(tg_user_id)
        rid = int(referrer_id)
    except (TypeError, ValueError):
        return
    if uid <= 0 or rid <= 0 or uid == rid:
        return
    row = await session.get(PendingReferral, uid)
    if row is None:
        session.add(PendingReferral(tg_user_id=uid, referrer_id=rid))
    else:
        row.referrer_id = rid
    if commit:
        await session.commit()


async def peek_pending(session, tg_user_id) -> int | None:
    """خواندنِ دعوتِ در انتظار بدون پاک کردن (v1.7.9)."""
    try:
        uid = int(tg_user_id)
    except (TypeError, ValueError):
        return None
    row = await session.get(PendingReferral, uid)
    return int(row.referrer_id) if row is not None else None


async def pop_pending(session, tg_user_id, commit: bool = True) -> int | None:
    """خواندن و پاک کردنِ دعوتِ در انتظار — مصرفِ یک‌باره (v1.7.9)."""
    rid = await peek_pending(session, tg_user_id)
    if rid is None:
        return None
    try:
        await session.execute(
            delete(PendingReferral).where(PendingReferral.tg_user_id == int(tg_user_id))
        )
        if commit:
            await session.commit()
    except Exception:
        pass
    return rid
