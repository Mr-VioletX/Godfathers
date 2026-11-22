# app/handlers/spy.py
"""سیستمِ جاسوسی (مرحله ۱۳).

مدیریتِ جاسوس‌ها فقط داخلِ PVِ ربات انجام می‌شود. اعزام، ارتقا،
پرداختِ غرامت و دیدنِ گزارش‌ها اینجا است.
"""
from datetime import datetime, timedelta

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select

from app.data.espionage import (
    MAX_SPIES,
    MAX_SPY_LEVEL,
    STATUS_LABELS,
    hire_cost,
    mission_seconds,
    ransom_cost,
    spy_stat_block,
    upgrade_cost,
)
from app.database.engine import async_session
from app.handlers.profile import get_player
from app.keyboards.spy_menu import (
    back_only_menu,
    deploy_targets_menu,
    spy_detail_menu,
    spy_home_menu,
)
from app.models.contact import Contact
from app.models.spy import Spy
from app.states import SpyStates
from app.utils.ui import CANCEL_HINT, ensure_owner, handle_cancel_word, safe_show, split_owner
from app.services import alliance_service, spy_service

# 🆕 مرحله ۴۶ — نمایشِ همه‌ی زمان‌هایِ جاسوسی به وقتِ تهران (نه UTC)
from app.data import news as _news_tz


def _teh(dt) -> str:
    """یک datetimeِ UTC را به رشته‌ی تاریخ/ساعتِ تهران تبدیل می‌کند."""
    if dt is None:
        return "-"
    try:
        return _news_tz.now_tehran(dt).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return dt.strftime("%Y-%m-%d %H:%M")


router = Router()

SPY_ONLY_BOT = "🕵️ بخشِ جاسوسی فقط داخلِ خودِ ربات در دسترس است."


def _is_private(chat_type: str) -> bool:
    return chat_type == "private"


async def _load_spies(session, owner_id: int):
    return (await session.execute(
        select(Spy).where(Spy.owner_id == owner_id).order_by(Spy.slot)
    )).scalars().all()


async def _get_spy(session, owner_id: int, slot: int):
    return (await session.execute(
        select(Spy).where(Spy.owner_id == owner_id, Spy.slot == slot)
    )).scalar_one_or_none()


def _home_text(spies: list) -> str:
    lines = ["🕵️ <b>شبکهٔ جاسوسی</b>", ""]
    if not spies:
        lines.append("هنوز جاسوسی استخدام نکرده‌ای.")
    else:
        for s in spies:
            tgt = f" → هدف: <code>{s.target_id}</code>" if s.target_id else ""
            lines.append(f"• جاسوس #{s.slot} — Lv{s.level} — {STATUS_LABELS.get(s.status, s.status)}{tgt}")
    lines.append("")
    lines.append(f"می‌توانی تا {MAX_SPIES} جاسوس استخدام کنی — هر جاسوس تا سطح {MAX_SPY_LEVEL} قابلِ ارتقاست.")
    return "\n".join(lines)


async def _detail_text(session, spy: Spy) -> str:
    reduction = await spy_service.owner_capture_reduction(session, spy.owner_id)
    lines = [
        f"🕵️ <b>جاسوس #{spy.slot}</b> — سطح {spy.level}",
        f"وضعیت: {STATUS_LABELS.get(spy.status, spy.status)}",
        "",
        spy_stat_block(spy.slot, spy.level, reduction),
    ]
    if spy.status == "active" and spy.target_id:
        lines.append(f"\n🎯 هدف: <code>{spy.target_id}</code>")
        if spy.next_report_at:
            lines.append(f"⏳ گزارشِ بعدی: {_teh(spy.next_report_at)} (به وقتِ تهران)")
    if spy.status == "captured" and spy.captured_at:
        deadline = spy.captured_at + timedelta(hours=48)
        lines.append(f"\n🔒 مهلتِ پرداختِ غرامت تا: {_teh(deadline)} (UTC)")
    return "\n".join(lines)


async def _show_home(message: Message, owner_id: int) -> None:
    async with async_session() as session:
        spies = await _load_spies(session, owner_id)
    await safe_show(message, _home_text(spies), spy_home_menu(spies, owner_id))


async def _show_detail(message: Message, owner_id: int, slot: int, note: str = "") -> None:
    async with async_session() as session:
        spy = await _get_spy(session, owner_id, slot)
        if spy is None:
            await safe_show(message, "❌ این جاسوس پیدا نشد.", back_only_menu(owner_id))
            return
        text = await _detail_text(session, spy)
    if note:
        text = f"{note}\n\n{text}"
    await safe_show(message, text, spy_detail_menu(spy, owner_id))


# ---------- ورودی‌ها ----------
@router.message(F.text == "جاسوسی")
async def summon_spy(message: Message) -> None:
    if not _is_private(message.chat.type):
        await message.reply(SPY_ONLY_BOT)
        return
    async with async_session() as session:
        player = await get_player(session, message.from_user.id)
    if not player:
        await message.reply("اول در چت خصوصی ربات /start را بزن.")
        return
    await _show_home(message, message.from_user.id)


@router.callback_query(F.data.startswith("menu:spy") | F.data.startswith("spy:hub"))
async def open_spy(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    if not _is_private(callback.message.chat.type):
        await callback.answer(SPY_ONLY_BOT, show_alert=True)
        return
    await _show_home(callback.message, callback.from_user.id)
    await callback.answer()


# ---------- استخدام ----------
@router.callback_query(F.data.startswith("spy:hire"))
async def hire_spy(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    owner_id = callback.from_user.id
    async with async_session() as session:
        spies = await _load_spies(session, owner_id)
        if len(spies) >= MAX_SPIES:
            await callback.answer("ظرفیتِ جاسوس‌ها پر است.", show_alert=True)
            return
        next_slot = len(spies) + 1
        cost = hire_cost(next_slot)
        player = await get_player(session, owner_id)
        if player is None:
            await callback.answer("اول /start را بزن.", show_alert=True)
            return
        if player.cash < cost:
            await callback.answer(f"پولت کافی نیست. هزینه: {cost:,}$", show_alert=True)
            return
        player.cash -= cost
        from app.data import leveling as _lv
        _xp_res = {}
        try:   # XP for hiring a spy
            _xp_res = await _lv.grant_xp(session, player, max(5, cost // 1000), source="spy_hire")
        except Exception:
            pass
        session.add(Spy(owner_id=owner_id, slot=next_slot, level=1, status="idle"))
        await session.commit()
    await _show_home(callback.message, owner_id)
    await callback.answer(f"✅ جاسوس #{next_slot} استخدام شد." + _lv.xp_note(_xp_res))


# ---------- بازکردنِ جاسوس ----------
@router.callback_query(F.data.startswith("spy:open:"))
async def open_detail(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    base, owner_id = split_owner(callback.data)
    slot = int(base.split(":")[2])
    await _show_detail(callback.message, callback.from_user.id, slot)
    await callback.answer()


# ---------- ارتقا ----------
@router.callback_query(F.data.startswith("spy:upmax:"))
async def upgrade_max(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    await callback.answer("این جاسوس به سقفِ سطح رسیده ✅", show_alert=True)


@router.callback_query(F.data.startswith("spy:up:"))
async def upgrade_spy(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    base, owner_id = split_owner(callback.data)
    slot = int(base.split(":")[2])
    async with async_session() as session:
        spy = await _get_spy(session, callback.from_user.id, slot)
        if spy is None:
            await callback.answer("جاسوس پیدا نشد.", show_alert=True)
            return
        if spy.level >= MAX_SPY_LEVEL:
            await callback.answer("به سقفِ سطح رسیده.", show_alert=True)
            return
        cost = upgrade_cost(spy.level)
        player = await get_player(session, callback.from_user.id)
        if player is None or player.cash < cost:
            await callback.answer(f"پولت کافی نیست. هزینه: {cost:,}$", show_alert=True)
            return
        player.cash -= cost
        spy.level += 1
        from app.data import leveling as _lv
        _xp_res = {}
        try:   # XP for spy upgrades
            _xp_res = await _lv.grant_xp(session, player, (20 + 10 * spy.level) // 2, source="spy_upgrade")
        except Exception:
            pass
        await session.commit()
    await _show_detail(callback.message, callback.from_user.id, slot, note="⬆️ ارتقا انجام شد." + _lv.xp_note(_xp_res))
    await callback.answer()


# ---------- اطلاعاتِ آخرین گزارش ----------
@router.callback_query(F.data.startswith("spy:info:"))
async def spy_info(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    base, owner_id = split_owner(callback.data)
    slot = int(base.split(":")[2])
    async with async_session() as session:
        spy = await _get_spy(session, callback.from_user.id, slot)
    if spy is None or not spy.last_intel:
        await callback.answer("هنوز گزارشی ثبت نشده. صبر کن تا چرخهٔ بعدی.", show_alert=True)
        return
    await safe_show(callback.message, spy.last_intel, spy_detail_menu(spy, callback.from_user.id))
    await callback.answer()


# ---------- اعزام: انتخابِ هدف ----------
@router.callback_query(F.data.startswith("spy:deploy:"))
async def choose_target(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    base, owner_id = split_owner(callback.data)
    slot = int(base.split(":")[2])
    async with async_session() as session:
        spy = await _get_spy(session, callback.from_user.id, slot)
        if spy is None or spy.status != "idle":
            await callback.answer("این جاسوس آمادهٔ اعزام نیست.", show_alert=True)
            return
        contacts = (await session.execute(
            select(Contact).where(Contact.owner_id == callback.from_user.id).order_by(Contact.added_at.desc())
        )).scalars().all()
    await safe_show(
        callback.message,
        "🎯 <b>هدف را انتخاب کن</b>\nاز مخاطبین انتخاب کن یا آیدی/یوزرنیم را دستی وارد کن.",
        deploy_targets_menu(contacts, slot, callback.from_user.id),
    )
    await callback.answer()


async def _deploy(session, owner_id: int, slot: int, target_id: int) -> tuple[bool, str]:
    """(ok, message) — جاسوس را رویِ هدف اعزام می‌کند."""
    spy = await _get_spy(session, owner_id, slot)
    if spy is None or spy.status != "idle":
        return False, "این جاسوس آمادهٔ اعزام نیست."
    # هر هدف فقط یک جاسوسِ فعال از همین کاربر
    dup = (await session.execute(
        select(Spy).where(
            Spy.owner_id == owner_id,
            Spy.target_id == target_id,
            Spy.status == "active",
        )
    )).scalar_one_or_none()
    if dup is not None:
        return False, "رویِ این هدف الان یک جاسوسِ فعال داری."
    if await alliance_service.same_alliance(session, owner_id, target_id):
        return False, "🤝 این بازیکن هم‌اتحادیه‌ی توست؛ نمی‌توانی برایش جاسوس بفرستی."
    now = datetime.utcnow()
    spy.status = "active"
    spy.target_id = target_id
    spy.deployed_at = now
    spy.next_report_at = now + timedelta(seconds=mission_seconds(spy.level))
    spy.captured_at = None
    await session.commit()
    return True, "📤 جاسوس اعزام شد. اولین گزارش پس از پایانِ چرخه می‌رسد."


@router.callback_query(F.data.startswith("spy:target:"))
async def deploy_to_contact(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    base, owner_id = split_owner(callback.data)
    parts = base.split(":")   # spy:target:<slot>:<target_id>
    slot = int(parts[2])
    target_id = int(parts[3])
    async with async_session() as session:
        if target_id == callback.from_user.id:
            await callback.answer("نمی‌توانی رویِ خودت جاسوس بفرستی!", show_alert=True)
            return
        ok, msg = await _deploy(session, callback.from_user.id, slot, target_id)
    if not ok:
        await callback.answer(msg, show_alert=True)
        return
    await _show_detail(callback.message, callback.from_user.id, slot, note=msg)
    await callback.answer()


@router.callback_query(F.data.startswith("spy:manual:"))
async def manual_target(callback: CallbackQuery, state: FSMContext) -> None:
    if not await ensure_owner(callback):
        return
    base, owner_id = split_owner(callback.data)
    slot = int(base.split(":")[2])
    await state.set_state(SpyStates.entering_target)
    await state.update_data(spy_slot=slot)
    await callback.message.answer(
        "⌨️ آیدیِ عددی یا یوزرنیمِ هدف را بفرست (مثلاً <code>123456789</code> یا <code>@username</code>)." + CANCEL_HINT,
    )
    await callback.answer()


@router.message(SpyStates.entering_target)
async def receive_manual_target(message: Message, state: FSMContext) -> None:
    if await handle_cancel_word(message, state):
        return
    data = await state.get_data()
    slot = data.get("spy_slot")
    await state.clear()
    if slot is None:
        await message.reply("دوباره از منوی جاسوسی تلاش کن.")
        return
    async with async_session() as session:
        target_id, err = await spy_service.resolve_target(session, message.from_user.id, message.text or "")
        if err:
            await message.reply(f"❌ {err}")
            return
        ok, msg = await _deploy(session, message.from_user.id, int(slot), target_id)
    await message.reply(msg if ok else f"❌ {msg}")
    if ok:
        await _show_home(message, message.from_user.id)


# ---------- فراخوانی ----------
@router.callback_query(F.data.startswith("spy:recall:"))
async def recall_spy(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    base, owner_id = split_owner(callback.data)
    slot = int(base.split(":")[2])
    async with async_session() as session:
        spy = await _get_spy(session, callback.from_user.id, slot)
        if spy is None or spy.status != "active":
            await callback.answer("این جاسوس در مأموریت نیست.", show_alert=True)
            return
        spy.status = "idle"
        spy.target_id = None
        spy.next_report_at = None
        await session.commit()
    await _show_detail(callback.message, callback.from_user.id, slot, note="🔙 جاسوس به پایگاه بازگشت.")
    await callback.answer()


# ---------- پرداختِ غرامت ----------
@router.callback_query(F.data.startswith("spy:ransom:"))
async def pay_ransom(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    base, owner_id = split_owner(callback.data)
    slot = int(base.split(":")[2])
    async with async_session() as session:
        spy = await _get_spy(session, callback.from_user.id, slot)
        if spy is None or spy.status != "captured":
            await callback.answer("این جاسوس دستگیر نیست.", show_alert=True)
            return
        cost = ransom_cost(slot, spy.level)
        player = await get_player(session, callback.from_user.id)
        if player is None or player.cash < cost:
            await callback.answer(f"پولت کافی نیست. غرامت: {cost:,}$", show_alert=True)
            return
        player.cash -= cost
        spy.status = "idle"
        spy.captured_at = None
        spy.target_id = None
        spy.next_report_at = None
        await session.commit()
    await _show_detail(callback.message, callback.from_user.id, slot, note="💵 غرامت پرداخت شد؛ جاسوس آزاد شد.")
    await callback.answer()
