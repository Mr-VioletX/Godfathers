# -*- coding: utf-8 -*-
"""مرحله ۲۷ — سرویسِ رویدادهایِ بونس (XP Bonus / Money Bonus).

وضعیتِ رویدادها در جدولِ `admin_settings` (key/value) ذخیره می‌شود؛ پس هیچ مایگریشنِ
جدیدی لازم نیست و ریستارتِ ربات/پسنجر رویدادِ فعال را پاک نمی‌کند.

در هر ریکوئست مقدارها از کَشِ درون‌حافطه (`app.data.events.BONUS`) خوانده می‌شوند؛ کَش هر ۶۰
ثانیه (یا فوری پس از تغییرِ ادمین) تازه می‌شود تا روی هاستِ چندپروسه‌ای هم همه‌ی پروسه‌ها
همِ وضعیت باشند.
"""
from __future__ import annotations

from datetime import datetime

from app.data import events as E
from app.database.engine import async_session
from app.services.admin_service import get_setting, set_setting

# کلیدهایِ تنطیمات
SETTING_XP_ACTIVE = "event_xp_active"
SETTING_XP_MULT = "event_xp_mult"
SETTING_XP_UNTIL = "event_xp_until"
SETTING_MONEY_ACTIVE = "event_money_active"
SETTING_MONEY_MULT = "event_money_mult"
SETTING_MONEY_UNTIL = "event_money_until"
SETTING_TITLE = "event_title"

# مدتِ اعتبارِ کَش (ثانیه)
CACHE_TTL = 60.0
_last_load: datetime | None = None


def _parse_dt(val: str | None) -> datetime | None:
    if not val:
        return None
    try:
        return datetime.fromisoformat(val)
    except (TypeError, ValueError):
        return None


def _parse_float(val: str | None, default: float = 1.0) -> float:
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


async def load_bonus(session) -> E.BonusState:
    """وضعیت را از دیتابیس می‌خواند و کَشِ سراسری را پر می‌کند."""
    global _last_load
    st = E.BONUS
    st.xp_active = (await get_setting(session, SETTING_XP_ACTIVE)) == "1"
    st.xp_mult = _parse_float(await get_setting(session, SETTING_XP_MULT))
    st.xp_until = _parse_dt(await get_setting(session, SETTING_XP_UNTIL))
    st.money_active = (await get_setting(session, SETTING_MONEY_ACTIVE)) == "1"
    st.money_mult = _parse_float(await get_setting(session, SETTING_MONEY_MULT))
    st.money_until = _parse_dt(await get_setting(session, SETTING_MONEY_UNTIL))
    st.title = (await get_setting(session, SETTING_TITLE)) or ""
    # v1.7.6.6 — مهلت گذشته: اثر را بردار و در DB هم خاموش کن
    expired = st.expire_if_needed()
    if expired:
        if E.KIND_XP in expired:
            await set_setting(session, SETTING_XP_ACTIVE, "0", commit=False)
        if E.KIND_MONEY in expired:
            await set_setting(session, SETTING_MONEY_ACTIVE, "0", commit=False)
        # اگر هر دو خاموش‌اند عنوان رویداد را هم پاک کن
        if not st.xp_active and not st.money_active:
            st.title = ""
            await set_setting(session, SETTING_TITLE, None, commit=False)
        try:
            await session.commit()
        except Exception:
            try:
                await session.rollback()
            except Exception:
                pass
    _last_load = datetime.utcnow()
    return st


async def refresh_if_stale(force: bool = False) -> E.BonusState:
    """اگر کَش کهنه شده باشد، تازه‌اش می‌کند.

    force=True همیشه از DB می‌خواند (برای دزدی/درآمد حیاتی).
    حتی در حالت کَش تازه، expire_if_needed را اجرا می‌کند تا مهلت همان لحظه اعمال شود.
    """
    # همیشه اول انقضای زمانی روی کَش فعلی
    try:
        E.BONUS.expire_if_needed()
    except Exception:
        pass
    if (not force) and _last_load is not None and (datetime.utcnow() - _last_load).total_seconds() < CACHE_TTL:
        # اگر منقضی شده ولی هنوز در DB فعال است، force-load کن
        if E.BONUS.xp_active or E.BONUS.money_active:
            # ممکن است until گذشته باشد و expire_if_needed خاموش کرده — DB را هم sync کن
            if (E.BONUS.xp_until and datetime.utcnow() >= E.BONUS.xp_until) or (
                E.BONUS.money_until and datetime.utcnow() >= E.BONUS.money_until
            ):
                force = True
            else:
                return E.BONUS
        else:
            return E.BONUS
    try:
        async with async_session() as session:
            return await load_bonus(session)
    except Exception:
        return E.BONUS


async def set_bonus(
    session,
    kind: str,
    active: bool,
    mult: float | None = None,
    hours: int | None = None,
    commit: bool = True,
) -> E.BonusState:
    """فعال/غیرفعال‌کردنِ یک رویداد + تعیینِ ضریب و مدت."""
    if kind not in E.KINDS:
        raise ValueError("unknown bonus kind")
    until = E.until_from_hours(int(hours or 0)) if active else None
    if kind == E.KIND_XP:
        keys = (SETTING_XP_ACTIVE, SETTING_XP_MULT, SETTING_XP_UNTIL)
    else:
        keys = (SETTING_MONEY_ACTIVE, SETTING_MONEY_MULT, SETTING_MONEY_UNTIL)
    await set_setting(session, keys[0], ("1" if active else "0"), commit=False)
    if mult is not None:
        await set_setting(session, keys[1], str(float(mult)), commit=False)
    await set_setting(session, keys[2], (until.isoformat() if until else None), commit=False)
    if commit:
        await session.commit()
    return await load_bonus(session)


async def set_title(session, title: str | None, commit: bool = True) -> E.BonusState:
    await set_setting(session, SETTING_TITLE, (title or "").strip()[:64] or None, commit=commit)
    return await load_bonus(session)


async def clear_all(session, commit: bool = True) -> E.BonusState:
    """خاموش‌کردنِ همه‌ی رویدادها (پایانِ اونت)."""
    for key in (SETTING_XP_ACTIVE, SETTING_MONEY_ACTIVE):
        await set_setting(session, key, "0", commit=False)
    for key in (SETTING_XP_UNTIL, SETTING_MONEY_UNTIL, SETTING_TITLE):
        await set_setting(session, key, None, commit=False)
    if commit:
        await session.commit()
    return await load_bonus(session)
