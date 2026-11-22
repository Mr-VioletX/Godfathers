# -*- coding: utf-8 -*-
"""سرویسِ «اشتراکِ ۴ سطحی» (مرحله ۲۰).

⚠️ سیستمِ فروش/تأیید/پرداخت/رسید (ادمین‌محور) در مرحله ۲۱ اضافه می‌شود.
در این مرحله: زیرساختِ اشتراک (سطوح/مزایا/وضعیت)، تابعِ فعال‌سازیِ آماده‌ی
استفاده‌ی ادمین، تاریخچه‌ی خرید و کدِ پیگیری.
خریدِ مستقیم با پولِ درون‌بازی وجود ندارد؛ فعال‌سازی پس از تأییدِ واقعیِ ادمین.
"""
import random
import string
from datetime import datetime, timedelta

from sqlalchemy import desc, select

from app.models.player import Player
from app.models.subscription import Subscription
from app.models.purchase import PurchaseHistory
from app.data import subscription as S
from app.services import admin_service as adm

# 🆕 مرحله ۲۱.۱ — پیشوندِ کلیدِ تنظیماتِ قیمتِ override‌شده‌یِ هر سطح (فقط ادمینِ اصلی تغییر می‌دهد)
_PRICE_PREFIX = "sub_price_"


# ------------------------- وضعیتِ اشتراک -------------------------
async def get_subscription(session, uid: int) -> Subscription | None:
    return await session.get(Subscription, uid)


async def active_tier(session, uid: int) -> str:
    """سطحِ موثرِ فعلی؛ اگر اشتراک منقضی شده باشد free."""
    sub = await get_subscription(session, uid)
    if sub is None or sub.tier == "free":
        return "free"
    if sub.expires_at is None or sub.expires_at <= datetime.utcnow():
        return "free"
    return sub.tier


async def is_subscribed(session, uid: int) -> bool:
    """آیا کاربر اشتراکِ پولیِ فعال دارد؟ (ملاکِ بازشدنِ لقبِ دلخواه)."""
    return (await active_tier(session, uid)) != "free"


async def days_left(session, uid: int) -> int:
    sub = await get_subscription(session, uid)
    if sub is None or not sub.expires_at:
        return 0
    delta = sub.expires_at - datetime.utcnow()
    return max(0, delta.days)


async def _ensure_row(session, uid: int) -> Subscription:
    sub = await get_subscription(session, uid)
    if sub is None:
        sub = Subscription(tg_user_id=uid, tier="free", expires_at=None)
        session.add(sub)
    return sub


# ------------------------- فعال‌سازی (ادمین‌محور در مرحله ۲۱) -------------------------
async def activate_tier(
    session,
    uid: int,
    tier_key: str,
    days: int | None = None,
    tracking_code: str | None = None,
    commit: bool = True,
) -> tuple[bool, str]:
    """🔑 فعال‌سازیِ اشتراک بدونِ کسرِ پولِ درون‌بازی.

    در مرحله ۲۱ پس از تأییدِ ادمین (و تأییدِ رسید) صدا زده می‌شود.
    اگر tracking_code داده شود، رکوردِ خریدِ متناظر هم active می‌شود.
    """
    tier = S.get_tier(tier_key)
    if tier["key"] == "free":
        return False, "سطحِ رایگان نیازی به فعال‌سازی ندارد."

    days = days or S.SUBSCRIPTION_DAYS
    sub = await _ensure_row(session, uid)
    now = datetime.utcnow()
    extend = timedelta(days=days)

    # هر خریدِ تأییدشده روی اشتراکِ فعال، به انتهای تاریخ فعلی افزوده می‌شود؛
    # حتی اگر سطح درخواست با سطح فعلی متفاوت باشد، روزهای قبلی از بین نمی‌روند.
    active_before = sub.tier != "free" and sub.expires_at and sub.expires_at > now
    previous_tier = sub.tier
    base_expiry = sub.expires_at if active_before else now
    sub.tier = tier["key"]
    sub.expires_at = base_expiry + extend
    if active_before:
        msg = (f"✅ اشتراکِ {S.badge(tier['key'])} فعال شد و {days} روز به پایانِ اشتراکِ فعلی "
               f"اضافه شد (سطح قبلی: {S.badge(previous_tier)}).")
    else:
        msg = f"🎉 اشتراکِ {S.badge(tier['key'])} فعال شد ({days} روز)."
    sub.activated_at = now

    player = (await session.execute(select(Player).where(Player.tg_user_id == uid))).scalar_one_or_none()
    if player is not None and hasattr(player, "is_premium"):
        player.is_premium = True

    if tracking_code:
        rec = await get_purchase_by_code(session, tracking_code)
        if rec is not None and rec.tg_user_id == uid:
            rec.status = "active"
            rec.activated_at = now
            rec.expires_at = sub.expires_at

    if commit:
        await session.commit()
    return True, msg


async def deactivate(session, uid: int, commit: bool = True) -> None:
    sub = await get_subscription(session, uid)
    if sub is not None:
        sub.tier = "free"
        sub.expires_at = None
    player = (await session.execute(select(Player).where(Player.tg_user_id == uid))).scalar_one_or_none()
    if player is not None and hasattr(player, "is_premium"):
        player.is_premium = False
    if commit:
        await session.commit()


# ------------------------- تاریخچه‌ی خرید + کدِ پیگیری -------------------------
async def _unique_tracking_code(session) -> str:
    for _ in range(12):
        code = S.generate_tracking_code()
        if await get_purchase_by_code(session, code) is None:
            return code
    # بسیار بعید، اما دفاعی: طولانی‌تر کن
    return "SUB-" + "".join(random.choice(string.ascii_uppercase + string.digits) for _ in range(10))


async def create_purchase_request(session, uid: int, tier_key: str, price: int | None = None, commit: bool = True) -> PurchaseHistory:
    """ثبتِ درخواستِ خرید (status=pending) با کدِ پیگیریِ یکتا.

    price: اگر داده شود (قیمتِ مؤثرِ فعلی)، همان ذخیره می‌شود، وگرنه قیمتِ پیش���فرضِ سطح.
    """
    tier = S.get_tier(tier_key)
    code = await _unique_tracking_code(session)
    rec = PurchaseHistory(
        tg_user_id=uid,
        tier=tier["key"],
        tracking_code=code,
        status="pending",
        amount=(price if price is not None else tier["price"]),
        note="درخواستِ خرید — در انتظارِ تأییدِ ادمین",
    )
    session.add(rec)
    if commit:
        await session.commit()
    else:
        await session.flush()
    return rec


async def get_purchases(session, uid: int, limit: int = 10) -> list:
    res = await session.execute(
        select(PurchaseHistory)
        .where(PurchaseHistory.tg_user_id == uid)
        .order_by(desc(PurchaseHistory.created_at))
        .limit(limit)
    )
    return list(res.scalars().all())


async def get_purchase_by_code(session, code: str) -> PurchaseHistory | None:
    res = await session.execute(
        select(PurchaseHistory).where(PurchaseHistory.tracking_code == code)
    )
    return res.scalar_one_or_none()


# ------------------------- 🆕 مرحله ۲۱.۱ — قیمت‌گذاریِ مؤثر (override توسطِ ادمینِ اصلی) -------------------------
async def effective_price(session, tier_key: str) -> int:
    """قیمتِ مؤثرِ فعلیِ یک سطح؛ اگر ادمینِ اصلی override کرده باشد همان، وگرنه قیمتِ پیش‌فرضِ سطح."""
    val = await adm.get_setting(session, _PRICE_PREFIX + tier_key)
    if val is not None:
        try:
            return int(val)
        except (TypeError, ValueError):
            pass
    return S.get_tier(tier_key)["price"]


async def set_price_override(session, tier_key: str, price: int, commit: bool = True) -> None:
    """🆕 تنظیمِ قیمتِ override‌شده‌یِ یک سطح (فقط ادمینِ اصلی این را صدا می‌زند)."""
    await adm.set_setting(session, _PRICE_PREFIX + tier_key, str(int(price)), commit=commit)


async def effective_tiers(session) -> list:
    """فهرستِ همه‌یِ سطوح (به ترتیبِ رتبه) با قیمتِ مؤثر (override‌شده در صورتِ وجود)."""
    result = []
    for key in S.TIER_ORDER:
        tier = dict(S.get_tier(key))
        tier["price"] = await effective_price(session, key)
        result.append(tier)
    return result


async def effective_paid_tiers(session) -> list:
    """فهرستِ سطوحِ پولی با قیمتِ مؤثر (override‌شده در صورتِ وجود)."""
    return [t for t in await effective_tiers(session) if t["price"] > 0 or S.get_tier(t["key"])["price"] > 0]


# ------------------------- 🆕 مرحله ۲۱.۱ — رسید + مدیریتِ درخواست‌ها توسطِ ادمین -------------------------
async def attach_receipt(session, tracking_code: str, file_id: str, file_type: str, commit: bool = True) -> PurchaseHistory | None:
    """الحاق‌کردنِ رسید/مسندِ پرداخت که کاربر پس از درخواست می‌فرستد."""
    rec = await get_purchase_by_code(session, tracking_code)
    if rec is None:
        return None
    rec.receipt_file_id = file_id
    rec.receipt_type = file_type
    if commit:
        await session.commit()
    return rec


async def get_payment_method(session) -> str:
    val = await adm.get_setting(session, "sub_payment_method")
    return (val or "").strip()


async def set_payment_method(session, text: str, commit: bool = True) -> None:
    await adm.set_setting(session, "sub_payment_method", (text or "").strip()[:500], commit=commit)


async def mark_approved_for_payment(session, tracking_code: str, admin_id: int, commit: bool = True):
    rec = await get_purchase_by_code(session, tracking_code)
    if rec is None:
        return False, "⚠ کد پیدا نشد.", None
    if rec.status not in ("pending", "awaiting_payment"):
        return False, f"⚠ وضعیت فعلی: {rec.status}", rec
    # 🐞 v1.7.6.3 — قبلاً دقیقاً همین‌جا کلِ گردشِ کار قفل می‌شد: اگر «روشِ
    #   پرداخت» در پنل تنظیم نشده بود، تأییدِ اولیه با خطا برمی‌گشت؛ پس هیچ
    #   ردیفی هرگز به وضعیت awaiting_payment نمی‌رسید و فهرستِ «در انتطار
    #   پرداخت» همیشه خالی دیده می‌شد — کاربر خیال می‌کرد بخش خراب است.
    #   حالا با متنِ پیش‌فرض ادامه می‌دهیم و فقط به ادمین هشدار می‌دهیم.
    pay = await get_payment_method(session)
    warn = ""
    if not pay:
        pay = "روشِ پرداخت هنوز توسطِ ادمین تنظیم نشده است."
        warn = "\n⚠ روشِ پرداخت تنطیم نشده — از «💳 روش پرداخت» تنطیمش کن."
    rec.status = "awaiting_payment"
    if hasattr(rec, 'approved_for_pay'):
        rec.approved_for_pay = 1
    if hasattr(rec, 'payment_info'):
        rec.payment_info = pay
    rec.handled_by = admin_id
    rec.note = "تأیید اولیه — منتظر پرداخت و ارسال رسید"
    if commit:
        await session.commit()
    return True, "✅ درخواست برای پرداخت کاربر آزاد شد." + warn, rec


async def get_user_awaiting_payment(session, uid: int, limit: int = 10) -> list:
    res = await session.execute(
        select(PurchaseHistory)
        .where(PurchaseHistory.tg_user_id == int(uid), PurchaseHistory.status == "awaiting_payment")
        .order_by(desc(PurchaseHistory.created_at))
        .limit(limit)
    )
    return list(res.scalars().all())


async def get_awaiting_payment_all(session, limit: int = 20) -> list:
    res = await session.execute(
        select(PurchaseHistory)
        .where(PurchaseHistory.status == "awaiting_payment")
        .order_by(PurchaseHistory.created_at.asc())
        .limit(limit)
    )
    return list(res.scalars().all())


async def finalize_after_receipt(session, tracking_code: str, admin_id: int, days: int | None = None, commit: bool = True):
    rec = await get_purchase_by_code(session, tracking_code)
    if rec is None:
        return False, "⚠ کد پیدا نشد.", None
    if rec.status not in ("awaiting_payment", "pending"):
        return False, f"⚠ وضعیت فعلی: {rec.status}", rec
    if not rec.receipt_file_id:
        return False, "⚠ هنوز رسیدی ثبت نشده.", rec
    ok, msg = await activate_tier(session, rec.tg_user_id, rec.tier, days=days, tracking_code=tracking_code, commit=False)
    if ok:
        rec.handled_by = admin_id
        rec.note = "فعال‌سازی پس از تأیید رسید"
    if commit:
        await session.commit()
    return ok, msg, rec


async def get_receipts_pending(session, limit: int = 20) -> list:
    """🆕 v1.7.6.3 — هر درخواستی که کاربر برایش رسید فرستاده و هنوز تکلیفش روشن نیست.

    چرا لازم بود: attach_receipt وضعیتِ ردیف را عوض نمی‌کند، پس اگر کاربری
    رسید را در حالتِ pending می‌فرستاد، نه در فهرستِ «در انتطار پرداخت»
    (فقط awaiting_payment) دیده می‌شد و نه جای دیگری — رسید عملاً گم می‌شد.
    قدیمی‌ترین اول تا نوبت رعایت شود.
    """
    res = await session.execute(
        select(PurchaseHistory)
        .where(
            PurchaseHistory.receipt_file_id.isnot(None),
            PurchaseHistory.status.in_(("pending", "awaiting_payment")),
        )
        .order_by(PurchaseHistory.created_at.asc())
        .limit(limit)
    )
    return list(res.scalars().all())


async def get_pending_requests(session, limit: int = 15) -> list:
    """درخواست‌هایِ درِ انتظارِ تأیید (همه‌یِ کاربران) برایِ پنلِ ادمین."""
    res = await session.execute(
        select(PurchaseHistory)
        .where(PurchaseHistory.status == "pending")
        .order_by(PurchaseHistory.created_at.asc())
        .limit(limit)
    )
    return list(res.scalars().all())


async def get_recent_purchases(session, limit: int = 20) -> list:
    """🆕 تاریخچه‌ی کاملِ خریدها (همه‌ی کاربران) برایِ نمایشِ ادمین."""
    res = await session.execute(
        select(PurchaseHistory).order_by(desc(PurchaseHistory.created_at)).limit(limit)
    )
    return list(res.scalars().all())


async def approve_request(session, tracking_code: str, admin_id: int, days: int | None = None, commit: bool = True):
    """🆕 تأییدِ یک درخواستِ درِ انتظار: فعال‌سازیِ اشتراک برایِ کاربرِ همان درخواست.

    این جدا از دسترسیِ ویژه‌ی «فعال‌سازیِ اشتراک» (adm:sub:on) است که بدونِ نیاز به
    دارا بودنِ یک درخواست، هر سطحی را برای هر کاربری فعال می‌کند.
    """
    rec = await get_purchase_by_code(session, tracking_code)
    if rec is None:
        return False, "⚠ کدِ پیگیری پیدا نشد.", None
    # 🐞 v1.7.6.3 — قبلاً فقط pending قابلِ تأیید بود؛ پس هر درخواستی که یک بار
    #   تأییدِ اولیه گرفته بود (awaiting_payment) دیگر قابلِ تأیید نبود.
    if rec.status not in ("pending", "awaiting_payment"):
        return False, f"⚠ این درخواست پیش‌تر پردازش شده (وضعیت: {rec.status}).", rec
    ok, msg = await activate_tier(session, rec.tg_user_id, rec.tier, days=days, tracking_code=tracking_code, commit=False)
    if ok:
        rec.handled_by = admin_id
    if commit:
        await session.commit()
    return ok, msg, rec


async def reject_request(session, tracking_code: str, admin_id: int, note: str | None = None, commit: bool = True):
    """🆕 ردِ یک درخواستِ درِ انتظار (مثلاً رسید/پرداخت نامعتبر)."""
    rec = await get_purchase_by_code(session, tracking_code)
    if rec is None:
        return False, "⚠ کدِ پیگیری پیدا نشد.", None
    # 🐞 v1.7.6.3 — ریشهٔ باگِ «🚫 رد کار نمی‌کند»: در فهرستِ «در انتطار
    #   پرداخت» دکمهٔ رد برای ردیف‌های awaiting_payment نشان داده می‌شد، اما
    #   این گارد فقط pending را قبول می‌کرد — پس دکمه همیشه با خطا برمی‌گشت.
    if rec.status not in ("pending", "awaiting_payment"):
        return False, f"⚠ این درخواست پیش‌تر پردازش شده (وضعیت: {rec.status}).", rec
    rec.status = "canceled"
    rec.handled_by = admin_id
    if note:
        rec.note = note
    if commit:
        await session.commit()
    return True, "🚫 درخواست رد شد.", rec


# ------------------------- مزایا/اثرات -------------------------
def tier_perks(tier_key: str) -> list:
    return list(S.get_tier(tier_key)["perks"])


async def income_bonus_pct(session, uid: int) -> int:
    return S.income_bonus_pct(await active_tier(session, uid))


async def discount_pct(session, uid: int) -> int:
    return S.discount_pct(await active_tier(session, uid))


async def bank_bonus_pct(session, uid: int) -> int:
    """بونس سود بانکی اشتراک (٪) — v1.7.8.3."""
    try:
        return int(S.bank_bonus_pct(await active_tier(session, uid)) or 0)
    except Exception:
        return 0


async def has_news_priority(session, uid: int) -> bool:
    return S.has_news_priority(await active_tier(session, uid))


# ------------------------- متونِ نمایش -------------------------
def _fmt(dt: datetime | None) -> str:
    return dt.strftime("%Y/%m/%d %H:%M") if dt else "—"


async def status_text(session, uid: int) -> str:
    key = await active_tier(session, uid)
    tier = S.get_tier(key)
    if key == "free":
        return "⚪ اشتراکِ فعلی: <b>رایگان</b>"
    left = await days_left(session, uid)
    parts = [f"{tier['emoji']} اشتراکِ فعلی: <b>{tier['name']}</b> — {left} روز باقی مانده"]
    if int(tier.get("income_pct") or 0):
        parts.append(f"💎 بونس درآمد فعال: <b>+{tier['income_pct']}٪</b>")
    if int(tier.get("discount_pct") or 0):
        parts.append(f"🏷 تخفیف خرید فعال: <b>−{tier['discount_pct']}٪</b>")
    if int(tier.get("xp_bonus_pct") or 0):
        parts.append(f"✨ بونس XP فعال: <b>+{tier['xp_bonus_pct']}٪</b>")
    return '\n'.join(parts)


async def activation_text(session, uid: int) -> str | None:
    """جزئیاتِ فعال‌سازی/پایان/روزهای باقی‌مانده؛ None اگر اشتراکِ فعال ندارد."""
    sub = await get_subscription(session, uid)
    if sub is None or (await active_tier(session, uid)) == "free":
        return None
    tier = S.get_tier(sub.tier)
    now = datetime.utcnow()
    left = max(0, (sub.expires_at - now).days) if sub.expires_at else 0
    expired = sub.expires_at is not None and sub.expires_at <= now
    lines = [
        f"{tier['emoji']} <b>اشتراکِ {tier['name']}</b>",
        f"🟢 لحظه‌ی فعال‌سازی: <code>{_fmt(sub.activated_at)}</code>",
        f"🔴 پایانِ اشتراک: <code>{_fmt(sub.expires_at)}</code>",
    ]
    if expired:
        lines.append("⏳ وضعیت: <b>منقضی شده</b>")
    else:
        lines.append(f"⏳ روزهای باقی‌مانده: <b>{left}</b> روز")
    return "\n".join(lines)
