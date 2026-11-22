# -*- coding: utf-8 -*-
"""موتورِ ارزیابی و اعطای القاب (مرحله ۱۱).

جریانِ کلی:
  1) هر سیستمی (جنگ/جاسوسی/شهر/...) فقط شمارنده‌ی PlayerStats را زیاد،
     سپس evaluate_titles(session, tg_user_id) را صدا می‌زند.
  2) evaluate_titles تمامِ القابِ خودکار (auto_titles) را می‌سنجد، فیلترِ جنسیت،
     قفلِ تک/یونیک (TitleClaim) را اعمال می‌کند و القابِ جدید را بی‌سروصدا می‌دهد.
  3) القابِ رویدادی (special) با grant_title(...) از دلِ کدِ رویداد داده می‌شوند.

این فایل فقط به titles.py (دیتا + منطقِ شرط) و مدل‌ها وابسته است.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.data import titles as T
from app.models.title import PlayerStats, PlayerTitle, TitleClaim, TitleProfile, TitleApproval, TitleApproval


@dataclass
class StatsView:
    """نمایِ مسطحِ آمار که به meets_requirement داده می‌شود."""
    # از PlayerStats پر می‌شود + چند فیلدِ مشتق از Player
    capital: int = 0
    level: int = 0
    gender: Optional[str] = None


async def _get_or_create_stats(session: AsyncSession, uid: int) -> PlayerStats:
    st = await session.get(PlayerStats, uid)
    if st is None:
        st = PlayerStats(tg_user_id=uid)
        session.add(st)
        await session.flush()
    return st


async def _get_or_create_profile(session: AsyncSession, uid: int) -> TitleProfile:
    pr = await session.get(TitleProfile, uid)
    if pr is None:
        pr = TitleProfile(tg_user_id=uid)
        session.add(pr)
        await session.flush()
    return pr


async def gather_stats(session: AsyncSession, uid: int) -> dict:
    """تمامِ شمارنده‌ها را کنارِ capital/level/gender (از جدولِ بازیکن) جمع می‌کند."""
    st = await _get_or_create_stats(session, uid)
    data = {c.name: getattr(st, c.name) for c in PlayerStats.__table__.columns}

    capital, level, gender = 0, 0, None
    try:
        # از جدولِ بازیکن مشتق می‌کنیم (در صورتِ موجود بودن).
        from app.models.player import Player  # type: ignore

        pl = await session.scalar(select(Player).where(Player.tg_user_id == uid))
        if pl is not None:
            capital = int(getattr(pl, "cash", 0) or 0)
            level = int(getattr(pl, "level", 0) or 0)
            gender = getattr(pl, "gender", None)
    except Exception:
        # اگر مدلِ Player متفاوت بود، فقط آمارِ داخلی ملاک می‌شود.
        pass

    data["capital"] = capital
    data["level"] = level
    data["gender"] = gender
    # 🆕 v1.7.8.19 — active_days از تاریخِ ساختِ اکانت محاسبه می‌شود (شرطِ جاودانه/کرونوس)
    try:
        created = getattr(pl, "created_at", None) if pl is not None else None
        if created is not None:
            from datetime import datetime as _dt
            data["active_days"] = max(0, (_dt.utcnow() - created).days)
    except Exception:
        pass
    return data


async def player_gender(session: AsyncSession, uid: int) -> Optional[str]:
    """جنسیتِ فعلیِ بازیکن را از جدولِ Player می‌خواند (یا None)."""
    try:
        from app.models.player import Player  # type: ignore

        pl = await session.scalar(select(Player).where(Player.tg_user_id == uid))
        return getattr(pl, "gender", None) if pl else None
    except Exception:
        return None


async def _already_has(session: AsyncSession, uid: int, key: str) -> bool:
    q = select(PlayerTitle.id).where(
        PlayerTitle.tg_user_id == uid, PlayerTitle.title_key == key
    )
    return (await session.scalar(q)) is not None


async def _claim_owner(session: AsyncSession, key: str) -> Optional[int]:
    c = await session.get(TitleClaim, key)
    return c.tg_user_id if c else None


async def _award(session: AsyncSession, uid: int, key: str, *, unique: bool) -> bool:
    """ثبتِ یک لقب برای بازیکن. اگر تک/یونیک باشد، قفلِ first-claim می‌گیرد."""
    if await _already_has(session, uid, key):
        return False
    if unique:
        owner = await _claim_owner(session, key)
        if owner is not None and owner != uid:
            return False  # قبلاً توسطِ دیگری قفل شده
        if owner is None:
            session.add(TitleClaim(title_key=key, tg_user_id=uid))
    session.add(PlayerTitle(tg_user_id=uid, title_key=key))
    await session.flush()
    return True


async def _request_approval(session: AsyncSession, uid: int, key: str, source: str='auto') -> bool:
    if await _already_has(session, uid, key): return False
    exists=await session.scalar(select(TitleApproval.id).where(TitleApproval.tg_user_id==uid, TitleApproval.title_key==key, TitleApproval.status=='pending'))
    if exists is not None: return False
    session.add(TitleApproval(tg_user_id=uid,title_key=key,source=source,status='pending'))
    await session.flush(); return True


async def evaluate_titles(session: AsyncSession, uid: int) -> list[dict]:
    """همه‌ی القابِ خودکار را می‌سنجد و مواردِ جدید را می‌دهد.

    خروجی: فهرستِ dict القابِ تازه‌کسب‌شده (برای پیامِ تبریک).
    """
    # بچ ۵: قبل از شروع فصل هیچ لقب آماری داده نمی‌شود و بعد از آن نیز
    # هر مورد ابتدا وارد صفِ تأیید ادمین اصلی خواهد شد.
    from app.services import title_season
    if not await title_season.season_is_live(session):
        return []
    stats = await gather_stats(session, uid)
    gender = stats.get("gender")
    queued: list[dict] = []
    for t in T.auto_titles():
        if t.get("unique") or not T.gender_ok(t, gender) or not T.meets_requirement(t, stats):
            continue
        if not await _already_has(session, uid, t["key"]) and await title_season.queue(session, uid, t["key"]):
            queued.append(t)
    return queued


async def grant_title(session: AsyncSession, uid: int, key: str) -> bool:
    """اعطای دستیِ یک لقبِ رویدادی/ویژه (special) از دلِ کدِ رویداد.

    مثال: پس از پایانِ فصل → grant_title(s, winner_id, "server_legend").
    """
    t = T.get_title(key)
    if t is None:
        return False
    return await _request_approval(session, uid, key, source="event")


async def revoke_unique_from_others(session: AsyncSession, uid: int, key: str) -> None:
    """برای القابِ پویا (مانندِ قدرتمندترین بازیکن): انتقالِ قفل به دارنده‌ی جدید."""
    c = await session.get(TitleClaim, key)
    if c is None:
        session.add(TitleClaim(title_key=key, tg_user_id=uid))
    elif c.tg_user_id != uid:
        c.tg_user_id = uid
    await session.flush()


async def list_player_titles(session: AsyncSession, uid: int) -> list[dict]:
    """فهرستِ القابِ کسب‌شده‌ی بازیکن (همراه با دیتای لقب)."""
    q = (
        select(PlayerTitle.title_key)
        .where(PlayerTitle.tg_user_id == uid)
        .order_by(PlayerTitle.granted_at.desc())
    )
    keys = list((await session.scalars(q)).all())
    out = []
    for k in keys:
        t = T.get_title(k)
        if t:
            out.append(t)
    return out


# ---------------------------------------------------------------------------
# اشتراک و لقبِ فعال
# ---------------------------------------------------------------------------
async def set_active_title(session: AsyncSession, uid: int, key: str) -> tuple[bool, str]:
    """لقبِ فعال را روی یکی از القابِ کسب‌شده تنظیم می‌کند."""
    if not await _already_has(session, uid, key):
        return False, "این لقب را هنوز کسب نکرده‌ای."
    t = T.get_title(key)
    if t is not None and T.is_gender_locked(t):
        gender = await player_gender(session, uid)
        if not T.gender_ok(t, gender):
            return False, "این لقب جنسیتی است و با جنسیتِ فعلیِ تو سازگار نیست."
    pr = await _get_or_create_profile(session, uid)
    pr.active_kind = "earned"
    pr.active_title_key = key
    await session.flush()
    t = T.get_title(key)
    return True, (t["name"] if t else key)


async def clear_active_title(session: AsyncSession, uid: int) -> None:
    pr = await _get_or_create_profile(session, uid)
    pr.active_kind = None
    pr.active_title_key = None
    await session.flush()


async def display_title(session: AsyncSession, uid: int) -> Optional[str]:
    """متنِ لقبی که باید کنارِ نامِ بازیکن نشان داده شود (یا None)."""
    pr = await session.get(TitleProfile, uid)
    if pr is None or pr.active_kind is None:
        return None
    if pr.active_kind == "custom":
        if pr.custom_title and (pr.subscription_active() or await _is_admin_uid(session, uid)):
            return pr.custom_title
        return None  # اشتراک منقضی شده — لقبِ سفارشی غیرفعال
    if pr.active_kind == "earned" and pr.active_title_key:
        t = T.get_title(pr.active_title_key)
        if not t:
            return None
        if T.is_gender_locked(t):
            gender = await player_gender(session, uid)
            if not T.gender_ok(t, gender):
                return None  # لقبِ جنسیتیِ غیرفعال تا بازگشتِ جنسیت
        return t["name"]
    return None


async def buy_subscription(session: AsyncSession, uid: int) -> tuple[bool, str]:
    """خرید/تمدیدِ اشتراک، برداشتِ هزینه از موجودیِ بازیکن."""
    from datetime import datetime, timedelta

    try:
        from app.models.player import Player  # type: ignore

        pl = await session.scalar(select(Player).where(Player.tg_user_id == uid))
    except Exception:
        pl = None

    if pl is None:
        return False, "ابتدا باید پروفایلت را بسازی (/start)."
    if int(getattr(pl, "cash", 0) or 0) < T.SUBSCRIPTION_COST:
        return False, (
            f"موجودیِ کافی نداری. هزینه‌ی اشتراک: {T.SUBSCRIPTION_COST:,} دلار."
        )

    pl.cash = int(pl.cash) - T.SUBSCRIPTION_COST
    pr = await _get_or_create_profile(session, uid)
    base = pr.sub_expires_at if pr.subscription_active() else datetime.utcnow()
    pr.sub_expires_at = base + timedelta(days=T.SUBSCRIPTION_DAYS)
    from app.data import leveling as _lv
    _xp_res = {}
    try:   # XP for buying the custom-title subscription
        _xp_res = await _lv.grant_xp(session, pl, 150, source="titles_subscription")
    except Exception:
        pass
    await session.flush()
    return True, (
        f"اشتراک فعال شد! تا تاریخِ {pr.sub_expires_at:%Y-%m-%d} می‌توانی لقبِ دلخواهت را تنظیم کنی."
    )


async def _is_admin_uid(session: AsyncSession, uid: int) -> bool:
    """آیا این کاربر یک ادمینِ فعال است؟ (بازکردنِ لقبِ دلخواه بدونِ اشتراک — مرحله ۲۱)."""
    try:
        from app.services import admin_service
        return await admin_service.is_admin(session, uid)
    except Exception:
        return False


async def set_custom_title(session: AsyncSession, uid: int, raw: str, force: bool = False) -> tuple[bool, str]:
    """تنظیمِ لقبِ سفارشی. مجاز اگر: force (اقدامِ ادمین) یا اشتراکِ فعال یا خودِ کاربر ادمین باشد."""
    pr = await _get_or_create_profile(session, uid)
    if not force and not pr.subscription_active() and not await _is_admin_uid(session, uid):
        return False, "برای لقبِ سفارشی باید اشتراکِ فعال داشته باشی."

    ok, result = T.validate_custom_title(raw)
    if not ok:
        return False, result  # result = دلیلِ رد

    pr.custom_title = result  # result = متنِ پاک‌شده
    pr.active_kind = "custom"
    pr.active_title_key = None
    await session.flush()
    return True, result


# ---------------------------------------------------------------------------
# اثرِ القاب، تغییرِ جنسیت و اعطای ادمین
# ---------------------------------------------------------------------------
async def aggregate_effects(session: AsyncSession, uid: int) -> dict:
    """جمعِ پاداشِ همه‌ی القابِ کسب‌شده.
    اثرِ مثبتِ هر لقب دائمی است؛ اما القابِ جنسیتیِ ناسازگار با جنسیتِ فعلی
    موقتاً حساب نمی‌شوند (تا کاربر جنسیتش را بازگرداند).
    خروجی: {"bonuses": {...}, "counted": [key...], "disabled": [key...]}.
    """
    gender = await player_gender(session, uid)
    owned = await list_player_titles(session, uid)
    total: dict[str, int] = {}
    counted, disabled = [], []
    for t in owned:
        if T.is_gender_locked(t) and not T.gender_ok(t, gender):
            disabled.append(t["key"])
            continue
        counted.append(t["key"])
        for k, v in (t.get("bonus") or {}).items():
            total[k] = total.get(k, 0) + int(v)
    return {"bonuses": total, "counted": counted, "disabled": disabled}


async def on_gender_change(session: AsyncSession, uid: int, new_gender: str) -> dict:
    """باید پس از تغییرِ جنسیتِ بازیکن صدا زده شود.
    اگر لقبِ فعالِ پروفایل جنسیتی و ناسازگار شد، آن را با یک لقبِ رندوم از
    سخت‌ترین/کمیاب‌ترین القابِ سازگارِ کاربر جایگزین می‌کند.
    خروجی: {"changed": bool, "old": name|None, "new": name|None}.
    """
    pr = await session.get(TitleProfile, uid)
    if pr is None or pr.active_kind != "earned" or not pr.active_title_key:
        return {"changed": False, "old": None, "new": None}
    active = T.get_title(pr.active_title_key)
    if active is None:
        return {"changed": False, "old": None, "new": None}
    if not T.is_gender_locked(active) or T.gender_ok(active, new_gender):
        return {"changed": False, "old": active["name"], "new": active["name"]}
    owned = await list_player_titles(session, uid)
    keys = [t["key"] for t in owned]
    replacement = T.rarest_key(keys, gender=new_gender)
    old_name = active["name"]
    if replacement:
        pr.active_kind = "earned"
        pr.active_title_key = replacement
        await session.flush()
        rep = T.get_title(replacement)
        return {"changed": True, "old": old_name, "new": rep["name"] if rep else None}
    pr.active_kind = None
    pr.active_title_key = None
    await session.flush()
    return {"changed": True, "old": old_name, "new": None}


async def admin_grant_title(
    session: AsyncSession, target_uid: int, key: str, *, reassign_unique: bool = True
) -> tuple[bool, str]:
    """اعطای دستیِ لقب توسطِ ادمین؛ حتی القابِ تک/یونیک را می‌دهد.
    برای القابِ تک، در صورتِ reassign_unique قفل و دارنده به کاربرِ هدف منتقل می‌شود.
    """
    t = T.get_title(key)
    if t is None:
        return False, "کلیدِ لقب نامعتبر است."
    if t["unique"] and reassign_unique:
        # حذفِ لقب از دارندگانِ قبلی (به‌جز هدف) برای حفظِ تک‌بودن
        others = await session.scalars(
            select(PlayerTitle).where(
                PlayerTitle.title_key == key, PlayerTitle.tg_user_id != target_uid
            )
        )
        other_rows = others.all()
        # ⚡ مرحله ۲۸ (سرعت): پروفایل‌ها در یک کؤری
        other_uids = [row.tg_user_id for row in other_rows]
        other_profiles = {}
        if other_uids:
            other_profiles = {
                pr.tg_user_id: pr
                for pr in (await session.execute(
                    select(TitleProfile).where(TitleProfile.tg_user_id.in_(other_uids))
                )).scalars().all()
            }
        for row in other_rows:
            await session.delete(row)
            opr = other_profiles.get(row.tg_user_id)
            if opr and opr.active_title_key == key:
                opr.active_kind = None
                opr.active_title_key = None
        await revoke_unique_from_others(session, target_uid, key)
        await session.flush()
    ok = await _award(session, target_uid, key, unique=False)
    if not ok:
        return False, "کاربر از قبل این لقب را دارد."
    return True, t["name"]


async def admin_revoke_title(session: AsyncSession, target_uid: int, key: str) -> bool:
    """حذفِ یک لقب از کاربر توسطِ ادمین (و آزادسازیِ قفلِ یونیک)."""
    row = await session.scalar(
        select(PlayerTitle).where(
            PlayerTitle.tg_user_id == target_uid, PlayerTitle.title_key == key
        )
    )
    if row is None:
        return False
    await session.delete(row)
    pr = await session.get(TitleProfile, target_uid)
    if pr and pr.active_title_key == key:
        pr.active_kind = None
        pr.active_title_key = None
    claim = await session.get(TitleClaim, key)
    if claim and claim.tg_user_id == target_uid:
        await session.delete(claim)
    await session.flush()
    return True


async def pending_approvals(session, limit: int = 30):
    return (await session.execute(select(TitleApproval).where(TitleApproval.status == "pending").order_by(TitleApproval.requested_at).limit(limit))).scalars().all()

async def approve_title(session, approval_id: int, reviewer_id: int) -> tuple[bool, str, int | None]:
    from datetime import datetime
    row = await session.get(TitleApproval, approval_id)
    if row is None or row.status != "pending": return False, "درخواست معتبر نیست یا قبلاً بررسی شده است.", None
    ok, msg = await admin_grant_title(session, row.tg_user_id, row.title_key)
    row.status = "approved" if ok else "rejected"; row.reviewed_at = datetime.utcnow(); row.reviewed_by = reviewer_id
    await session.flush(); return ok, msg, row.tg_user_id

async def reject_title(session, approval_id: int, reviewer_id: int) -> bool:
    from datetime import datetime
    row=await session.get(TitleApproval, approval_id)
    if row is None or row.status != "pending": return False
    row.status="rejected"; row.reviewed_at=datetime.utcnow(); row.reviewed_by=reviewer_id; await session.flush(); return True
