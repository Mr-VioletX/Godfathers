# -*- coding: utf-8 -*-
"""مرحله ۱۹.۲ — بانکِ مافیایی: ثروتِ خالص، سپرده، وام و ثروتمندان.

پیشوندِ کالبک: wb:  —  فقط داخلِ PV.
کلمه‌ی فرمان: «بانک» / «بانک مافیایی» → منو.
"""
from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select

from app.data import worldbank as WB
from app.database.engine import async_session
from app.handlers.profile import get_player
from app.keyboards.worldbank_menu import rich_menu, wb_back_menu, wb_home_menu, wb_safebox_menu
from app.models.player import Player
from app.services import worldbank_service as WBS
from app.states import BankStates
from app.utils.ui import CANCEL_HINT, ensure_owner, handle_cancel_word, safe_show, split_owner, safe_answer

router = Router(name="worldbank")

BANK_ONLY_BOT = "🏦 بخشِ بانکِ مافیایی فقط داخلِ خودِ ربات در دسترس است."


def _is_private(chat_type: str) -> bool:
    return chat_type == "private"


def _parse_amount(text: str) -> int | None:
    raw = (text or "").strip().replace(",", "").replace("٬", "")
    if raw.isdigit():
        return int(raw)
    return None


async def _home_text(session, uid: int) -> str:
    acc = await WBS.get_account(session, uid)
    nw = await WBS.compute_net_worth(session, uid)
    tier, rate = WB.tier_for(nw["net_worth"])
    loan_due = WBS.loan_balance(acc)
    lines = [
        "🏦 <b>بانکِ مافیایی</b>",
        "",
        f"🏅 رده‌ی بانکی: <b>{tier}</b> (سودِ روزانه {int(rate*100)}٪)",
        f"💰 ثروتِ خالص: <b>{nw['net_worth']:,}$</b>",
        f"🏦 سپرده: {acc.deposit:,}$",
    ]
    try:
        sb = await WBS.safebox_info(session, uid)
        lines.append(
            f"🔐 گاوصندوق Lv{int(sb.get('level') or 0)}: "
            f"{int(sb.get('balance') or 0):,}$ / {int(sb.get('capacity') or 0):,}$"
        )
    except Exception:
        pass
    lines.append("")
    lines.append("🛡 <b>امنیت در برابر جنگ/جاسوسی:</b>")
    lines.append(f"• {WB.get_war_safe_pct()}٪ سپرده (+ کل موجودی گاوصندوق) امن است")
    lines.append(f"• غارت فقط از <b>نقد + {WB.get_war_lootable_pct()}٪ سپرده آزاد</b>")
    lines.append("• غنیمت پیروز: <b>۱۴٪</b> (قوی→ضعیف) تا <b>۴۲٪</b> (ضعیف→قوی)")
    if loan_due > 0:
        lines.append(f"🔴 بدهیِ وام: {loan_due:,}$")
    return "\n".join(lines)


async def _show_home(message: Message, uid: int) -> None:
    try:
        async with async_session() as session:
            text = await _home_text(session, uid)
            await session.commit()
    except Exception:
        text = (
            "🏦 <b>بانکِ مافیایی</b>\n\n"
            "⚠ بارگذاری حساب با خطا روبه‌رو شد. یک‌بار /start بزن و دوباره تلاش کن."
        )
    await safe_show(message, text, wb_home_menu(uid))



@router.message(F.text.in_({"بانک", "🏦 بانک", "بانک مافیایی", "بانکِ مافیایی", "بانک جهانی", "بانکِ جهانی"}))
async def summon_bank(message: Message) -> None:
    if not _is_private(message.chat.type):
        await message.reply(BANK_ONLY_BOT)
        return
    async with async_session() as session:
        player = await get_player(session, message.from_user.id)
    if not player:
        await message.reply("اول در چتِ خصوصیِ ربات /start را بزن.")
        return
    if int(player.level or 1) < WB.WORLDBANK_UNLOCK_LEVEL:
        await message.reply(f"🔒 بانکِ مافیایی از سطحِ {WB.WORLDBANK_UNLOCK_LEVEL} باز می‌شود.")
        return
    await _show_home(message, message.from_user.id)


@router.callback_query(F.data.startswith("menu:worldbank") | F.data.startswith("wb:hub"))
async def open_bank(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    if not _is_private(callback.message.chat.type):
        await safe_answer(callback, BANK_ONLY_BOT, show_alert=True)
        return
    async with async_session() as session:
        player = await get_player(session, callback.from_user.id)
    if player and int(player.level or 1) < WB.WORLDBANK_UNLOCK_LEVEL:
        await safe_answer(callback, f"🔒 از سطحِ {WB.WORLDBANK_UNLOCK_LEVEL} باز می‌شود.", show_alert=True)
        return
    await _show_home(callback.message, callback.from_user.id)
    await safe_answer(callback)


# --------------------------- ثروتِ خالص ---------------------------
@router.callback_query(F.data.startswith("wb:networth"))
async def show_networth(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    uid = callback.from_user.id
    async with async_session() as session:
        nw = await WBS.compute_net_worth(session, uid)
    tier, rate = WB.tier_for(nw["net_worth"])
    nxt = WB.next_tier(nw["net_worth"])
    lines = [
        "💰 <b>ثروتِ خالصِ تو</b>",
        "",
        f"💵 نقدینگی: {nw['cash']:,}$",
        f"📈 درآمدِ روزانه: {nw['daily_income']:,}$",
        f"🏙️ ارزشِ شهرها: {nw['city_value']:,}$",
        f"🏳️ ارزشِ کشورها: {nw['country_value']:,}$",
        "—" * 8,
        f"🧾 ثروتِ خالصِ کل: <b>{nw['net_worth']:,}$</b>",
        f"🏅 رده: {tier}",
    ]
    if nxt:
        lines.append(f"🔼 تا رده‌ی بعدی: {nxt[1]} ({nxt[0] - nw['net_worth']:,}$)")
    await safe_show(callback.message, "\n".join(lines), wb_back_menu(uid))
    await safe_answer(callback)


# --------------------------- سپرده / برداشت ---------------------------
@router.callback_query(F.data.startswith("wb:deposit"))
async def deposit_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not await ensure_owner(callback):
        return
    await state.set_state(BankStates.depositing)
    await callback.message.answer(
        "🏦 چقدر می‌خواهی سپرده‌گذاری کنی؟ مبلغ را بفرست." + CANCEL_HINT,
    )
    await safe_answer(callback)


@router.message(BankStates.depositing)
async def deposit_do(message: Message, state: FSMContext) -> None:
    if await handle_cancel_word(message, state):
        return
    await state.clear()
    amount = _parse_amount(message.text or "")
    if amount is None:
        await message.reply("مبلغِ معتبر بفرست (فقط عدد).")
        return
    uid = message.from_user.id
    async with async_session() as session:
        ok, msg = await WBS.deposit(session, uid, amount)
        if ok:
            await session.commit()
    await message.reply(msg)
    if ok:
        await _show_home(message, uid)


@router.callback_query(F.data.startswith("wb:withdraw"))
async def withdraw_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not await ensure_owner(callback):
        return
    await state.set_state(BankStates.withdrawing)
    await callback.message.answer(
        "🏧 چقدر برداشت می‌کنی؟ مبلغ را بفرست." + CANCEL_HINT,
    )
    await safe_answer(callback)


@router.message(BankStates.withdrawing)
async def withdraw_do(message: Message, state: FSMContext) -> None:
    if await handle_cancel_word(message, state):
        return
    await state.clear()
    amount = _parse_amount(message.text or "")
    if amount is None:
        await message.reply("مبلغِ معتبر بفرست (فقط عدد).")
        return
    uid = message.from_user.id
    async with async_session() as session:
        ok, msg = await WBS.withdraw(session, uid, amount)
        if ok:
            await session.commit()
    await message.reply(msg)
    if ok:
        await _show_home(message, uid)


# --------------------------- وام ---------------------------
@router.callback_query(F.data.startswith("wb:loan"))
async def loan_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not await ensure_owner(callback):
        return
    uid = callback.from_user.id
    async with async_session() as session:
        acc = await WBS.get_account(session, uid)
        net = await WBS.net_worth_value(session, uid)
    cap = WB.max_loan(net, int(acc.loan_principal))
    if int(acc.loan_principal) > 0:
        await safe_answer(callback, "اول وامِ قبلی را تسویه کن.", show_alert=True)
        return
    await state.set_state(BankStates.borrowing)
    await callback.message.answer(
        f"🏦 سقفِ وامِ تو {cap:,}$ است. مبلغِ وام را بفرست." + CANCEL_HINT,
    )
    await safe_answer(callback)


@router.message(BankStates.borrowing)
async def loan_do(message: Message, state: FSMContext) -> None:
    if await handle_cancel_word(message, state):
        return
    await state.clear()
    amount = _parse_amount(message.text or "")
    if amount is None:
        await message.reply("مبلغِ معتبر بفرست (فقط عدد).")
        return
    uid = message.from_user.id
    async with async_session() as session:
        ok, msg = await WBS.take_loan(session, uid, amount)
        if ok:
            await session.commit()
    await message.reply(msg)
    if ok:
        await _show_home(message, uid)


@router.callback_query(F.data.startswith("wb:repay"))
async def repay(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    uid = callback.from_user.id
    async with async_session() as session:
        ok, msg = await WBS.repay_loan(session, uid)
        if ok:
            await session.commit()
    await safe_answer(callback, msg, show_alert=True)
    if ok:
        await _show_home(callback.message, uid)


# --------------------------- ثروتمندانِ جهان ---------------------------
@router.callback_query(F.data.startswith("wb:rich:"))
async def show_rich(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    base, _ = split_owner(callback.data)
    try:
        page = int(base.split(":")[2])
    except (IndexError, ValueError):
        page = 0
    uid = callback.from_user.id
    async with async_session() as session:
        players = (await session.execute(select(Player))).scalars().all()
        scored = []
        for p in players:
            net = await WBS.net_worth_value(session, p.tg_user_id)
            scored.append((p, net))
    scored.sort(key=lambda x: x[1], reverse=True)
    per = 10
    total = max(1, (len(scored) + per - 1) // per)
    page = max(0, min(page, total - 1))
    chunk = scored[page * per:(page + 1) * per]
    lines = ["🏆 <b>ثروتمندانِ جهان</b>", ""]
    for i, (p, net) in enumerate(chunk, start=page * per + 1):
        medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(i, f"{i}.")
        nm = p.name if p.name else str(p.tg_user_id)
        tier, _ = WB.tier_for(net)
        lines.append(f"{medal} {nm} — {net:,}$ ({tier})")
    if not chunk:
        lines.append("— هنوز بازیکنی نیست —")
    await safe_show(callback.message, "\n".join(lines), rich_menu(uid, page, total))
    await safe_answer(callback)


# --------------------------- گاوصندوق v1.7.7.6 ---------------------------
@router.callback_query(F.data.startswith("wb:safebox"))
async def safebox_home(callback: CallbackQuery, state: FSMContext) -> None:
    if not await ensure_owner(callback):
        return
    uid = callback.from_user.id
    await state.clear()
    async with async_session() as session:
        info = await WBS.safebox_info(session, uid)
        await session.commit()
    lv = int(info["level"])
    mx = int(info["max_level"])
    bal = int(info["balance"])
    cap = int(info["capacity"])
    dep = int(info["deposit"])
    loot_dep = int(info["lootable_deposit"])
    lines = [
        "🔐 <b>گاوصندوق بانک مافیایی</b>",
        "",
        "بدون سود — فقط <b>امنیت</b> پول در برابر غارت جنگ و جاسوسی.",
        "",
        f"سطح: <b>{lv}</b> / {mx}",
        f"موجودی امن: <b>{bal:,}$</b>",
        f"ظرفیت: <b>{cap:,}$</b>",
        f"سپرده کل بانک: {dep:,}$",
        f"سپرده غارت‌پذیر ({WB.get_war_lootable_pct()}٪ آزاد): {loot_dep:,}$",
        "",
    ]
    if lv < mx:
        nc = int(info["next_cost"])
        ncap = int(info["next_capacity"])
        lines.append(f"⬆️ ارتقا به Lv{lv + 1}: <b>{nc:,}$</b>")
        lines.append(f"📦 ظرفیت بعدی: {ncap:,}$")
    else:
        lines.append("✅ گاوصندوق در سقف سطح است.")
    lines.append("")
    lines.append("نکته: پول گاوصندوق از <b>سپرده</b> تأمین می‌شود (اول سپرده بگذار، بعد به گاوصندوق ببر).")
    text = "\n".join(lines)
    await safe_show(callback.message, text, wb_safebox_menu(uid, has_box=lv > 0))
    await safe_answer(callback)

@router.callback_query(F.data.startswith("wb:sb:up"))
async def safebox_up(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    uid = callback.from_user.id
    async with async_session() as session:
        ok, msg = await WBS.upgrade_safebox(session, uid)
        info = await WBS.safebox_info(session, uid)
        await session.commit()
    lv = int(info["level"])
    await safe_answer(callback, "✅ ارتقا انجام شد" if ok else msg, show_alert=True)
    cap = int(info["capacity"])
    bal = int(info["balance"])
    text = (
        "🔐 <b>گاوصندوق</b>\n\n"
        + str(msg) + "\n\n"
        + f"سطح: <b>{lv}</b> | ظرفیت: <b>{cap:,}$</b>\n"
        + f"موجودی امن: <b>{bal:,}$</b>"
    )
    await safe_show(callback.message, text, wb_safebox_menu(uid, has_box=lv > 0))

@router.callback_query(F.data.startswith("wb:sb:in") | F.data.startswith("wb:sb:out"))
async def safebox_move_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not await ensure_owner(callback):
        return
    uid = callback.from_user.id
    base, _ = split_owner(callback.data)
    mode = "in" if ":in" in base else "out"
    await state.set_state(BankStates.safebox_wait_amount)
    await state.update_data(sb_mode=mode)
    tip = "واریز به گاوصندوق (از سپرده)" if mode == "in" else "برداشت از گاوصندوق (به سپرده)"
    text = "🔐 <b>" + tip + "</b>\n\nمبلغ را به عدد بفرست." + CANCEL_HINT
    await safe_show(callback.message, text, wb_back_menu(uid))
    await safe_answer(callback)

@router.message(StateFilter(BankStates.safebox_wait_amount))
async def safebox_move_amount(message: Message, state: FSMContext) -> None:
    if message.chat.type != "private":
        return
    if await handle_cancel_word(message, state):
        return
    amount = _parse_amount(message.text or "")
    if amount is None or amount <= 0:
        await message.reply("⚠ مبلغ معتبر بفرست.")
        return
    data = await state.get_data()
    mode = data.get("sb_mode") or "in"
    uid = message.from_user.id
    async with async_session() as session:
        if mode == "in":
            ok, msg = await WBS.move_to_safebox(session, uid, amount)
        else:
            ok, msg = await WBS.move_from_safebox(session, uid, amount)
        await session.commit()
    await state.clear()
    await message.reply(msg)
    await _show_home(message, uid)

