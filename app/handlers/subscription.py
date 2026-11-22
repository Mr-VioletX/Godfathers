# -*- coding: utf-8 -*-
"""هندلرِ «اشتراکِ ویژه (۴ سطحی)» (مرحله ۲۰).

⚠️ سیستمِ فروش/تأیید/پرداخت/رسید (ادمین‌محور) در مرحله ۲۱ اضافه می‌شود.
در این مرحله: نمایشِ سطوح/مزایا/وضعیت، ثبتِ «درخواستِ خرید» با کدِ پیگیری،
تاریخچه‌ی خرید و جزئیاتِ فعال‌سازی/پایان/روزهای باقی‌مانده.
"""
from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.config import MAIN_ADMIN_ID
from app.database.engine import async_session
from app.data import subscription as S
from app.services import admin_service as adm
from app.services import subscription_service as subs
from app.keyboards.subscription_menu import receipt_ask_kb, sub_home_menu, sub_view_menu, sub_history_menu, paylist_menu, pay_detail_menu
from app.keyboards.main_menu import BTN_SUBSCRIPTION, WORD_SUBSCRIPTION
from app.states import SubStates
from app.utils.ui import ensure_owner, safe_edit

router = Router()

_STATUS_FA = {
    "pending": "⏳ در انتظارِ تأیید",
    "awaiting_payment": "💳 تأییدشده — منتظر پرداخت",
    "active": "✅ فعال‌شده",
    "failed": "❌ ناموفق",
    "canceled": "🚫 لغو‌شده",
    "expired": "⌛ منقضی",
}


async def _home_text(session, uid: int) -> str:
    lines = ["💎 <b>اشتراکِ ویژه‌ی بازی</b>", await subs.status_text(session, uid)]
    # اگر اشتراکِ فعال دارد، جزئیاتِ فعال‌سازی/پایان/باقی‌مانده را نشان بده
    act = await subs.activation_text(session, uid)
    if act:
        lines += ["", act]
    lines += ["", "چهار سطحِ اشتراک در دسترس است:"]
    # 🆕 مرحله ۲۱.۱ — قیمتِ مؤثر (اگر ادمینِ اصلی override کرده باشد)
    for tier in await subs.effective_tiers(session):
        if tier["price"] > 0:
            lines.append(f"{tier['emoji']} <b>{tier['name']}</b> — {tier['price']:,}$ / {S.SUBSCRIPTION_DAYS} روز")
        else:
            lines.append(f"{tier['emoji']} <b>{tier['name']}</b> — پیش‌فرض")
    lines += [
        "",
        "برای دیدنِ مزایای هر سطح روی آن بزن.",
        "📣 اعلامِ آنلاین برای همهٔ اشتراک‌های فعال فقط وقتی باز است که یک لقبِ فعال هم داشته باشی.",
        "🤖 دستیار دوم فقط در اشتراک طلایی فعال است.",
        "ℹ️ خرید و پرداخت از طریقِ درخواست و تأییدِ ادمین انجام می‌شود؛ تأییدِ خرید جدید، روزهای آن را به پایانِ اشتراک فعال اضافه می‌کند.",
    ]
    return "\n".join(lines)


async def _tier_text(session, tier_key: str) -> str:
    tier = S.get_tier(tier_key)
    price = await subs.effective_price(session, tier_key)
    lines = [
        f"{tier['emoji']} <b>اشتراکِ {tier['name']}</b>",
        f"💰 قیمت: <b>{price:,}</b> دلار / {S.SUBSCRIPTION_DAYS} روز",
        "",
        "✨ مزایا:",
    ]
    lines += [f"• {p}" for p in tier["perks"]]
    lines += ["", "ℹ️ تمدید یا خرید مجددِ تأییدشده، مدتِ اشتراک را به پایانِ اشتراک فعال اضافه می‌کند."]
    return "\n".join(lines)


async def _notify_admins_new_request(bot, session, rec, tier: dict) -> None:
    """🆕 مرحله ۲۱.۱ — اطلاع‌رسانیِ درخواستِ خریدِ جدید به ادمینِ اصلی و/یا ادمینِ فروش."""
    current_status = await subs.status_text(session, rec.tg_user_id)
    active_details = await subs.activation_text(session, rec.tg_user_id)
    lines = [
        "📩 <b>درخواستِ خریدِ جدید</b>",
        f"{tier['emoji']} سطحِ درخواستی: <b>{tier['name']}</b> — {rec.amount:,}$",
        f"👤 کاربر: <code>{rec.tg_user_id}</code>",
        f"🧩 کدِ پیگیری: <code>{rec.tracking_code}</code>",
        "",
        "<b>اشتراکِ فعلی کاربر:</b>",
        current_status,
        *( [active_details] if active_details else [] ),
        "",
        "برای بررسی/تأیید، در ادمین‌مود → بخشِ «💎 اشتراک‌ها» → «📥 درخواست‌هایِ خرید» برو.",
    ]
    text = "\n".join(lines)
    sales_id = await adm.get_sales_admin_id(session)
    notify_main = await adm.main_notify_on_purchase(session)
    recipients = set()
    if sales_id:
        recipients.add(sales_id)
    if notify_main and MAIN_ADMIN_ID:
        recipients.add(MAIN_ADMIN_ID)
    if not recipients and MAIN_ADMIN_ID:
        recipients.add(MAIN_ADMIN_ID)  # 🆕 ایمنی: هیچ‌کس تعیین نشده، درخواست بی‌جواب نماند
    for rid in recipients:
        try:
            await bot.send_message(rid, text)
        except Exception:
            pass


# ---------- ورودی‌ها ----------
# 🔄 مرحله ۲۱.۱ — تطبیقِ دقیق به‌جای جستجویِ زیررشته؛ فقط "vip" به‌صورت case-insensitive باقی می‌ماند.
SUB_WORDS = {BTN_SUBSCRIPTION, WORD_SUBSCRIPTION, "اشتراکِ ویژه"}


# 🆕 مرحله ۳۱ — فیلترِ async به‌جای lambda (جلوگیری از ساختِ نخِ تازه به ازای هر پیام)
async def _is_sub_word(message: Message) -> bool:
    t = message.text
    if not t:
        return False
    t = t.strip()
    return t in SUB_WORDS or t.lower() == "vip"


@router.message(StateFilter(None), _is_sub_word)
async def subscription_button(message: Message):
    async with async_session() as session:
        text = await _home_text(session, message.from_user.id)
        tiers = await subs.effective_tiers(session)
    await message.answer(text, reply_markup=sub_home_menu(message.from_user.id, tiers))


@router.callback_query(F.data.startswith("menu:sub"))
async def sub_menu_cb(callback: CallbackQuery):
    if not await ensure_owner(callback):
        return
    async with async_session() as session:
        text = await _home_text(session, callback.from_user.id)
        tiers = await subs.effective_tiers(session)
    await safe_edit(callback.message, text, sub_home_menu(callback.from_user.id, tiers))
    await callback.answer()


@router.callback_query(F.data.startswith("sub:view:"))
async def sub_view_cb(callback: CallbackQuery):
    if not await ensure_owner(callback):
        return
    parts = callback.data.split(":")
    tier_key = parts[2] if len(parts) > 2 else "free"
    async with async_session() as session:
        text = await _tier_text(session, tier_key)
    await safe_edit(callback.message, text, sub_view_menu(callback.from_user.id, tier_key))
    await callback.answer()


@router.callback_query(F.data.startswith("sub:request:"))
async def sub_request_cb(callback: CallbackQuery, state: FSMContext):
    if not await ensure_owner(callback):
        return
    parts = callback.data.split(":")
    tier_key = parts[2] if len(parts) > 2 else "free"
    tier = S.get_tier(tier_key)
    if tier["key"] == "free":
        await callback.answer("سطحِ رایگان نیازی به خرید ندارد.", show_alert=True)
        return
    async with async_session() as session:
        price = await subs.effective_price(session, tier_key)
        rec = await subs.create_purchase_request(session, callback.from_user.id, tier_key, price=price)
        code = rec.tracking_code
        await _notify_admins_new_request(callback.bot, session, rec, tier)
    text = "\n".join([
        "📝 <b>درخواستِ خرید ثبت شد</b>",
        f"{tier['emoji']} سطح: <b>{tier['name']}</b> — {price:,}$",
        f"🧩 کدِ پیگیری: <code>{code}</code>",
        "",
        "این کد را نگه دار؛ با آن می‌توانی خرید و خطاهای احتمالی‌اش را پیگیری کنی.",
        "ℹ️ تأییدِ پرداخت و فعال‌سازی توسطِ ادمین انجام می‌شود.",
        "اگر اکنون اشتراک فعال داشته باشی، روزهای خریدِ تأییدشده به پایانِ اشتراک فعلی‌ات اضافه می‌شود.",
        "",
        "🧾 اگر همین الان رسید/مسندِ پرداخت را داری، همین‌جا (عکس یا فایل) بفرست، وگرنه رد کن.",
    ])
    await state.set_state(SubStates.awaiting_receipt)
    await state.update_data(tracking_code=code)
    await safe_edit(callback.message, text, receipt_ask_kb(callback.from_user.id))
    await callback.answer("کدِ پیگیری صادر شد ✅")


async def _notify_admins_receipt(message, code: str, kind: str) -> None:
    """🆕 v1.7.6.3 — خبردادن به ادمین‌ها از رسیدِ تازه.

    باگِ قدیم: فقط ارسالِ «عکس» به ادمینِ اصلی خبر می‌داد و ارسالِ
    «فایل/سند» به هیچ‌کس خبر نمی‌داد؛ پس رسیدهای فایلی بی‌صدا در
    دیتابیس می‌ماندند و کاربر معطل می‌ماند. حالا هر دو حالت هم به
    ادمینِ اصلی و هم به ادمینِ فروش خبر می‌دهند.
    """
    kind_fa = "🖼 عکس" if kind == "photo" else "📄 فایل"
    text = (
        "🧾 <b>رسیدِ تازه برای اشتراک</b>\n"
        f"👤 <code>{message.from_user.id}</code>\n"
        f"🧩 <code>{code}</code>\n"
        f"نوع: {kind_fa}\n\n"
        "ادمین‌مود → اشتراک‌ها → «🧾 رسیدهای ارسال‌شده»"
    )
    targets = []
    try:
        from app.config import MAIN_ADMIN_ID
        if MAIN_ADMIN_ID:
            targets.append(int(MAIN_ADMIN_ID))
    except Exception:
        pass
    try:
        from app.services import admin_service as _adm
        async with async_session() as session:
            sales = await _adm.get_sales_admin_id(session)
        if sales:
            targets.append(int(sales))
    except Exception:
        pass
    for target in dict.fromkeys(targets):
        try:
            await message.bot.send_message(target, text)
        except Exception:
            pass


@router.message(StateFilter(SubStates.awaiting_receipt), F.photo)
async def sub_receipt_photo(message: Message, state: FSMContext):
    data = await state.get_data()
    code = data.get("tracking_code")
    await state.clear()
    if not code:
        return
    file_id = message.photo[-1].file_id
    async with async_session() as session:
        await subs.attach_receipt(session, code, file_id, "photo")
    await message.answer(
        "✅ رسید ثبت شد. ادمین آن را بررسی و در صورت تأیید، اشتراک را فعال می‌کند.",
        reply_markup=sub_history_menu(message.from_user.id),
    )
    await _notify_admins_receipt(message, code, "photo")


@router.message(StateFilter(SubStates.awaiting_receipt), F.document)
async def sub_receipt_document(message: Message, state: FSMContext):
    data = await state.get_data()
    code = data.get("tracking_code")
    await state.clear()
    if not code:
        return
    file_id = message.document.file_id
    async with async_session() as session:
        await subs.attach_receipt(session, code, file_id, "document")
    await message.answer(
        "✅ رسید ثبت شد. با کدِ پیگیری‌ات می‌توانی وضعیتش را دنبال کنی.",
        reply_markup=sub_history_menu(message.from_user.id),
    )
    await _notify_admins_receipt(message, code, "document")


@router.callback_query(F.data.startswith("sub:receipt:skip"))
async def sub_receipt_skip_cb(callback: CallbackQuery, state: FSMContext):
    if not await ensure_owner(callback):
        return
    await state.clear()
    await safe_edit(
        callback.message,
        "باشه. هر وقت رسیددار شدی با کدِ پیگیری می‌توانی توسطِ ادمین بررسی شوی.",
        sub_history_menu(callback.from_user.id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("sub:history"))
async def sub_history_cb(callback: CallbackQuery):
    if not await ensure_owner(callback):
        return
    async with async_session() as session:
        rows = await subs.get_purchases(session, callback.from_user.id, limit=10)
    if not rows:
        text = "📜 <b>تاریخچه‌ی خرید</b>\n\nهنوز خریدی ثبت نشده است."
    else:
        lines = ["📜 <b>تاریخچه‌ی خرید</b>", ""]
        for r in rows:
            tier = S.get_tier(r.tier)
            status = _STATUS_FA.get(r.status, r.status)
            date = r.created_at.strftime("%Y/%m/%d") if r.created_at else "—"
            lines.append(
                f"{tier['emoji']} {tier['name']} — {status}\n"
                f"🧩 <code>{r.tracking_code}</code> • 📅 {date}"
            )
        text = "\n".join(lines)
    await safe_edit(callback.message, text, sub_history_menu(callback.from_user.id))
    await callback.answer()


# ---------- v1.7.6 درخواست‌های تأییدشده و پرداخت ----------
@router.callback_query(F.data.startswith("sub:paylist"))
async def sub_paylist_cb(callback: CallbackQuery):
    if not await ensure_owner(callback):
        return
    uid = callback.from_user.id
    async with async_session() as session:
        rows = await subs.get_user_awaiting_payment(session, uid)
    if not rows:
        text = (
            "💳 <b>درخواست‌های تأییدشده و پرداخت</b>\n\n"
            "فعلاً موردی نیست.\n"
            "وقتی ادمین درخواستت را تأیید اولیه کند، اینجا روش پرداخت و ارسال رسید ظاهر می‌شود."
        )
    else:
        lines = ["💳 <b>درخواست‌های تأییدشده و پرداخت</b>", ""]
        for r in rows:
            tier = S.get_tier(r.tier)
            lines.append(
                f"{tier['emoji']} {tier['name']} — {r.amount:,}$\n"
                f"🧩 <code>{r.tracking_code}</code>"
            )
        text = "\n\n".join(lines)
    await safe_edit(callback.message, text, paylist_menu(uid, rows))
    await callback.answer()


@router.callback_query(F.data.startswith("sub:pay:") & ~F.data.startswith("sub:paylist"))
async def sub_pay_detail_cb(callback: CallbackQuery):
    if not await ensure_owner(callback):
        return
    code = callback.data.split(":")[2].split("@")[0] if "@" in callback.data else callback.data.split(":")[2]
    # strip owner suffix if present via split_owner
    from app.utils.ui import split_owner
    base, _ = split_owner(callback.data)
    code = base.split("sub:pay:", 1)[1]
    uid = callback.from_user.id
    async with async_session() as session:
        rec = await subs.get_purchase_by_code(session, code)
        if rec is None or int(rec.tg_user_id) != uid:
            await callback.answer("پیدا نشد", show_alert=True); return
        tier = S.get_tier(rec.tier)
        pay = rec.payment_info or (await subs.get_payment_method(session)) or "—"
    text = "\n".join([
        "💳 <b>پرداخت اشتراک</b>",
        f"{tier['emoji']} {tier['name']} — {rec.amount:,}$",
        f"🧩 کد: <code>{rec.tracking_code}</code>",
        "",
        "📌 <b>روش پرداخت:</b>",
        f"<code>{pay}</code>",
        "",
        "۱) مبلغ را واریز کن",
        "۲) دکمه‌ی «ارسال رسید» را بزن و عکس/فایل رسید را بفرست",
        "۳) ادمین رسید را می‌بیند و اشتراک را فعال می‌کند",
    ])
    await safe_edit(callback.message, text, pay_detail_menu(uid, rec.tracking_code))
    await callback.answer()


@router.callback_query(F.data.startswith("sub:sendrec:"))
async def sub_sendrec_cb(callback: CallbackQuery, state: FSMContext):
    if not await ensure_owner(callback):
        return
    from app.utils.ui import split_owner
    base, _ = split_owner(callback.data)
    code = base.split("sub:sendrec:", 1)[1]
    await state.set_state(SubStates.awaiting_receipt)
    await state.update_data(tracking_code=code)
    await safe_edit(
        callback.message,
        f"🧾 رسید پرداخت برای <code>{code}</code> را همین‌جا (عکس یا فایل) بفرست.",
        receipt_ask_kb(callback.from_user.id),
    )
    await callback.answer()
