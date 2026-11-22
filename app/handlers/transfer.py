# -*- coding: utf-8 -*-
"""مرحله ۱۶ — انتقالِ دارایی بینِ کاربران (کارمزد ۲٪ + سقفِ روزانه).

روشِ استفاده: در گروه، روی پیامِ گیرنده «ریپلای» کن و بنویس: «انتقال <مبلغ>».
"""
import re
from datetime import datetime

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import func, select

from app.database.engine import async_session
from app.data.market import PRODUCTS
from app.data import warehouse as WH
from app.models.contact import Contact
from app.models.player import Player
from app.models.transfer import AssetTransfer, sent_today
from app.models.warehouse import MainWarehouse, WarehouseStock
from app.states import TransferStates
from app.utils.ui import CANCEL_HINT, ensure_owner, handle_cancel_word, safe_edit, safe_show, split_owner, with_owner

router = Router()

TRANSFER_FEE_PCT = 0.02
RESOURCE_TRANSFER_FEE_PCT = 0.05   # 🆕 کارمزدِ انتقالِ منابع (کالا)

_AMOUNT_RE = re.compile(r"^\s*انتقال\s+([0-9۰-۹,٫،]+)\s*$")
_RESOURCE_RE = re.compile(r"^\s*انتقال\s+منابع\s+(\S+)\s+([0-9۰-۹,٫،]+)\s*$")

_FA_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")


def _day_start(now: datetime) -> datetime:
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


def _parse_amount(raw: str) -> int | None:
    raw = (raw or "").translate(_FA_DIGITS).replace(",", "").replace("٫", "").replace("،", "")
    if not raw.isdigit():
        return None
    return int(raw)


def _find_product(token: str):
    """کالا را با کد یا نامِ فارسی پیدا می‌کند."""
    token = (token or "").strip()
    if token in PRODUCTS:
        return token, PRODUCTS[token]
    for k, p in PRODUCTS.items():
        name = (p.get("name") or "").strip()
        if token == name or (name and token in name):
            return k, p
    return None, None


# ---------- 🆕 v11 — منوی انتخابیِ واقعی (منبع→مقدار→کاربر)، علاوه بر دستورِ متنی قدیمی ----------
async def _resolve_transfer_target(session, owner_id: int, raw: str) -> tuple[int | None, str | None]:
    """(target_id, error) — از روی آیدیِ عددی یا یوزرنیم (ابتدا در مخاطبین، سپس در جدولِ بازیکنان)."""
    raw = (raw or "").strip()
    if not raw:
        return None, "ورودی خالی است. آیدی عددی یا @یوزرنیم را بفرست."
    target_id: int | None = None
    if raw.lstrip("-").isdigit():
        target_id = int(raw)
    else:
        uname = raw.lstrip("@").lower()
        c = (await session.execute(
            select(Contact).where(
                Contact.owner_id == owner_id,
                func.lower(Contact.username) == uname,
            )
        )).scalar_one_or_none()
        if c:
            target_id = c.contact_id
        else:
            p = (await session.execute(
                select(Player).where(func.lower(Player.username) == uname)
            )).scalar_one_or_none()
            if p:
                target_id = p.tg_user_id
    if target_id is None:
        return None, "کاربری پیدا نشد. آیدیِ عددی یا یوزرنیمِ دقیق را بفرست."
    if target_id == owner_id:
        return None, "SELF"
    receiver = (await session.execute(
        select(Player).where(Player.tg_user_id == target_id)
    )).scalar_one_or_none()
    if receiver is None:
        return None, "گیرنده هنوز در بازی ثبت‌نام نکرده است (باید /start زده باشد)."
    return target_id, None


# ---------- 🆕 دکمه‌ی «💸 انتقال» در منوی شیشه‌ای اصلی ----------
# 🐞 رفعِ باگ: قبلاً این راهنما با callback.answer(show_alert=True) نشان داده می‌شد،
# ولی متنش (۲۳۹ کاراکتر) از سقفِ ۲۰۰ کاراکتریِ تلگرام برای پاپ‌آپِ کال‌بک بیشتر بود؛
# تلگرام این درخواست را رد می‌کرد (TelegramBadRequest) و کل هندلر با خطا متوقف
# می‌شد — یعنی از دیدِ کاربر، دکمه‌ی «💸 انتقال» کاملاً بی‌پاسخ می‌ماند و هیچ منویی
# باز نمی‌شد. الان به‌جای پاپ‌آپ، یک پیامِ واقعیِ منو (مثلِ بقیه‌ی بخش‌ها) با دکمه‌ی
# بازگشت نمایش داده می‌شود که هیچ محدودیتِ طول ندارد.
TRANSFER_INFO_TEXT = (
    "💸 <b>انتقالِ پول:</b>\nدر گروه روی پیامِ گیرنده ریپلای کن و بنویس:\n<code>انتقال &lt;مبلغ&gt;</code>\n\n"
    "📦 <b>انتقالِ منابع (کالا):</b>\nدر گروه روی پیامِ گیرنده ریپلای کن و بنویس:\n<code>انتقال منابع &lt;نامِ کالا&gt; &lt;مقدار&gt;</code>\n\n"
    f"🧾 کارمزدِ پول: {int(TRANSFER_FEE_PCT * 100)}٪\n"
    f"🧾 کارمزدِ منابع: {int(RESOURCE_TRANSFER_FEE_PCT * 100)}٪"
)


def _transfer_info_menu(owner_id: int):
    b = InlineKeyboardBuilder()
    b.button(text="💵 انتقالِ پول (منو)", callback_data=with_owner("transfer:cashmenu", owner_id))
    b.button(text="📦 انتقالِ کالا (منو)", callback_data=with_owner("transfer:resmenu", owner_id))
    b.button(text="🏠 بازگشت به منوی اصلی", callback_data=with_owner("menu:main", owner_id))
    b.adjust(1)
    return b.as_markup()


@router.callback_query(F.data.startswith("transfer:info"))
async def transfer_info(callback: CallbackQuery) -> None:
    """راهنمای دو دستورِ متنی + دو دکمه‌ی منوی واقعی برای انتقالِ پول/کالا (🆕 v11)."""
    if not await ensure_owner(callback):
        return
    await safe_show(callback.message, TRANSFER_INFO_TEXT, _transfer_info_menu(callback.from_user.id))
    await callback.answer()


# ---------- 🆕 v11 — منوی انتقالِ پول ----------
@router.callback_query(F.data.startswith("transfer:cashmenu"))
async def transfer_cash_menu_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not await ensure_owner(callback):
        return
    await state.set_state(TransferStates.cash_amount)
    await safe_edit(
        callback.message,
        "💵 <b>انتقالِ پول</b>\nچه مبلغی می‌خوای بفرستی؟ (فقط عدد) ۲٪ کارمزد کسر می‌شود." + CANCEL_HINT,
    )
    await callback.answer()


@router.message(TransferStates.cash_amount)
async def transfer_cash_amount_msg(message: Message, state: FSMContext) -> None:
    if await handle_cancel_word(message, state):
        return
    amount = _parse_amount(message.text or "")
    if not amount or amount <= 0:
        await message.reply("❗ مبلغ نامعتبر است. یک عددِ مثبت بفرست (مثلاً 5000) یا برای انصراف بنویس: انصراف")
        return
    async with async_session() as session:
        sender = await session.scalar(select(Player).where(Player.tg_user_id == message.from_user.id))
        if sender is None:
            await state.clear()
            await message.reply("اول در چت خصوصی ربات /start را بزن.")
            return
        if int(sender.cash or 0) < amount:
            await message.reply(f"💸 موجودی کافی نداری. موجودی: {sender.cash:,}$\nیک مبلغِ دیگر بفرست یا برای انصراف بنویس: انصراف")
            return
    await state.update_data(amount=amount)
    await state.set_state(TransferStates.cash_target)
    await message.reply(
        "👤 حالا آیدیِ عددی یا یوزرنیمِ گیرنده را بفرست (مثلاً <code>123456789</code> یا <code>@username</code>)." + CANCEL_HINT,
    )


@router.message(TransferStates.cash_target)
async def transfer_cash_target_msg(message: Message, state: FSMContext) -> None:
    if await handle_cancel_word(message, state):
        return
    data = await state.get_data()
    amount = int(data.get("amount") or 0)
    if amount <= 0:
        await state.clear()
        await message.reply("❌ مشکلی پیش آمد؛ دوباره از اول شروع کن.")
        return
    sender_id = message.from_user.id
    async with async_session() as session:
        receiver_id, err = await _resolve_transfer_target(session, sender_id, message.text or "")
        if err == "SELF":
            await message.reply("به خودت نمی‌توانی پول بفرستی. یک آیدی/یوزرنیمِ دیگر بفرست یا برای انصراف بنویس: انصراف")
            return
        if err:
            await message.reply(f"❌ {err}")
            return
        sender = await session.scalar(select(Player).where(Player.tg_user_id == sender_id))
        receiver = await session.scalar(select(Player).where(Player.tg_user_id == receiver_id))
        if sender is None or receiver is None:
            await state.clear()
            await message.reply("❌ خطای غیرمنتظره؛ دوباره از اول شروع کن.")
            return
        if int(sender.cash or 0) < amount:
            await state.clear()
            await message.reply(f"💸 موجودی کافی نداری. موجودی: {sender.cash:,}$")
            return
        fee = int(round(amount * TRANSFER_FEE_PCT))
        received = amount - fee
        sender.cash = int(sender.cash) - amount
        receiver.cash = int(receiver.cash or 0) + received
        session.add(AssetTransfer(
            from_user_id=sender_id, to_user_id=receiver_id,
            kind="cash", amount=amount, fee=fee, received=received,
        ))
        await session.commit()
        s_cash = sender.cash
        r_name = receiver.name
    await state.clear()
    await message.reply(
        "✅ <b>انتقال انجام شد!</b>\n"
        f"➡️ به {r_name}: <b>{received:,}$</b>\n"
        f"🧾 کارمزد (۲٪): {fee:,}$\n"
        f"💵 موجودیِ تو: {s_cash:,}$"
    )


# ---------- 🆕 v11 — منوی انتقالِ کالا (منبع→مقدار→کاربر) ----------
async def _sender_stocks(session, tg_user_id: int):
    """لیستِ (key, product, qty) برای کالاهایی که موجودیِ بیش از صفر دارند."""
    wh = await session.scalar(select(MainWarehouse).where(MainWarehouse.tg_user_id == tg_user_id))
    if wh is None:
        return None, []
    rows = (await session.execute(
        select(WarehouseStock).where(WarehouseStock.warehouse_id == wh.id, WarehouseStock.qty > 0)
    )).scalars().all()
    out = []
    for r in rows:
        product = PRODUCTS.get(r.product_key)
        if product:
            out.append((r.product_key, product, r.qty))
    return wh, out


def _resource_pick_menu(stocks, owner_id: int):
    b = InlineKeyboardBuilder()
    for key, product, qty in stocks:
        b.button(
            text=f"{product['name']} — {qty:,} واحد",
            callback_data=with_owner(f"transfer:respick:{key}", owner_id),
        )
    b.button(text="↩️ بازگشت", callback_data=with_owner("transfer:info", owner_id))
    b.adjust(1)
    return b.as_markup()


@router.callback_query(F.data.startswith("transfer:resmenu"))
async def transfer_res_menu_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not await ensure_owner(callback):
        return
    async with async_session() as session:
        wh, stocks = await _sender_stocks(session, callback.from_user.id)
    if wh is None:
        await callback.answer("🏢 تو هنوز انبارِ اصلی نساخته‌ای.", show_alert=True)
        return
    if not stocks:
        await callback.answer("📦 انبارِ اصلیت خالی است — اول کالایی تولید کن.", show_alert=True)
        return
    await safe_edit(
        callback.message,
        "📦 <b>انتقالِ کالا</b>\nیکی از کالاهایِ انبارِ اصلیت را انتخاب کن:",
        _resource_pick_menu(stocks, callback.from_user.id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("transfer:respick:"))
async def transfer_res_pick(callback: CallbackQuery, state: FSMContext) -> None:
    if not await ensure_owner(callback):
        return
    base, _owner = split_owner(callback.data)
    key = base.split(":", 2)[2]
    product = PRODUCTS.get(key)
    if not product:
        await callback.answer("❌ این کالا شناخته نشد.", show_alert=True)
        return
    async with async_session() as session:
        wh, stocks = await _sender_stocks(session, callback.from_user.id)
    have = next((qty for k, _p, qty in stocks if k == key), 0)
    if have <= 0:
        await callback.answer("📦 موجودی این کالا صفر شده.", show_alert=True)
        return
    await state.update_data(res_key=key)
    await state.set_state(TransferStates.resource_amount)
    await safe_edit(
        callback.message,
        f"📦 <b>{product['name']}</b>\nموجودی: <b>{have:,}</b> واحد\nچه مقداری می‌خوای بفرستی؟" + CANCEL_HINT,
    )
    await callback.answer()


@router.message(TransferStates.resource_amount)
async def transfer_res_amount_msg(message: Message, state: FSMContext) -> None:
    if await handle_cancel_word(message, state):
        return
    data = await state.get_data()
    key = data.get("res_key")
    product = PRODUCTS.get(key)
    if not key or not product:
        await state.clear()
        await message.reply("❌ مشکلی پیش آمد؛ دوباره از اول شروع کن.")
        return
    amount = _parse_amount(message.text or "")
    if not amount or amount <= 0:
        await message.reply("❗ مقدار نامعتبر است. یک عددِ مثبت بفرست یا برای انصراف بنویس: انصراف")
        return
    async with async_session() as session:
        wh, stocks = await _sender_stocks(session, message.from_user.id)
    have = next((qty for k, _p, qty in stocks if k == key), 0)
    if amount > have:
        await message.reply(f"📦 موجودی کافی نیست. موجودی: {have:,} واحد. یک مقدارِ دیگر بفرست یا برای انصراف بنویس: انصراف")
        return
    await state.update_data(res_amount=amount)
    await state.set_state(TransferStates.resource_target)
    await message.reply(
        "👤 حالا آیدیِ عددی یا یوزرنیمِ گیرنده را بفرست (مثلاً <code>123456789</code> یا <code>@username</code>)." + CANCEL_HINT,
    )


@router.message(TransferStates.resource_target)
async def transfer_res_target_msg(message: Message, state: FSMContext) -> None:
    if await handle_cancel_word(message, state):
        return
    data = await state.get_data()
    key = data.get("res_key")
    amount = int(data.get("res_amount") or 0)
    product = PRODUCTS.get(key)
    if not key or not product or amount <= 0:
        await state.clear()
        await message.reply("❌ مشکلی پیش آمد؛ دوباره از اول شروع کن.")
        return
    sender_id = message.from_user.id
    async with async_session() as session:
        receiver_id, err = await _resolve_transfer_target(session, sender_id, message.text or "")
        if err == "SELF":
            await message.reply("به خودت نمی‌توانی جنس بفرستی. یک آیدی/یوزرنیمِ دیگر بفرست یا برای انصراف بنویس: انصر����ف")
            return
        if err:
            await message.reply(f"❌ {err}")
            return
        sender_wh = await session.scalar(select(MainWarehouse).where(MainWarehouse.tg_user_id == sender_id))
        receiver_wh = await session.scalar(select(MainWarehouse).where(MainWarehouse.tg_user_id == receiver_id))
        if sender_wh is None:
            await state.clear()
            await message.reply("❌ انبارِ اصلی نداری.")
            return
        if receiver_wh is None:
            await message.reply("❌ گیرنده هنوز انبارِ اصلی نساخته. یک آیدی/یوزرنیمِ دیگر بفرست یا برای انصراف بنویس: انصراف")
            return
        sender_stock = await session.scalar(select(WarehouseStock).where(
            WarehouseStock.warehouse_id == sender_wh.id, WarehouseStock.product_key == key,
        ))
        if sender_stock is None or sender_stock.qty < amount:
            await state.clear()
            await message.reply(f"📦 موجودی کافی نیست. دوباره از اول شروع کن.")
            return
        fee = int(round(amount * RESOURCE_TRANSFER_FEE_PCT))
        received = max(0, amount - fee)
        # بچ ۵: انتقالِ کالا اتمیک است؛ اگر مقصد جا نداشته باشد، هیچ واحدی از مبدأ کم نمی‌شود.
        receiver_rows = (await session.execute(select(WarehouseStock).where(
            WarehouseStock.warehouse_id == receiver_wh.id
        ))).scalars().all()
        receiver_used = sum(int(row.qty or 0) for row in receiver_rows)
        receiver_room = max(0, WH.warehouse_volume(receiver_wh.level) - receiver_used)
        if received > receiver_room:
            await message.reply(
                f"🏢 انبارِ گیرنده فقط برای {receiver_room:,} واحد جا دارد؛ انتقال انجام نشد و موجودیِ تو دست‌نخورده است."
            )
            return
        sender_stock.qty -= amount
        receiver_stock = await session.scalar(select(WarehouseStock).where(
            WarehouseStock.warehouse_id == receiver_wh.id, WarehouseStock.product_key == key,
        ))
        if receiver_stock is None:
            receiver_stock = WarehouseStock(warehouse_id=receiver_wh.id, product_key=key, qty=0)
            session.add(receiver_stock)
        receiver_stock.qty = (receiver_stock.qty or 0) + received
        await session.commit()
        s_left = sender_stock.qty
        receiver_player = await session.scalar(select(Player).where(Player.tg_user_id == receiver_id))
        r_name = receiver_player.name if receiver_player else str(receiver_id)
    await state.clear()
    await message.reply(
        "✅ <b>انتقالِ کالا انجام شد!</b>\n"
        f"➡️ به {r_name}: <b>{received:,}</b> {product['name']}\n"
        f"🧾 کارمزد (۵٪): {fee:,}\n"
        f"📦 موجودیِ باقی‌مانده: {s_left:,}"
    )


@router.message(F.text.regexp(r"^\s*انتقال\s+[0-9۰-۹,٫،]+\s*$"))
async def transfer_cmd(message: Message) -> None:
    m = _AMOUNT_RE.match(message.text or "")
    if not m:
        return
    amount = _parse_amount(m.group(1))
    if not amount or amount <= 0:
        await message.reply("مبلغِ نامعتبر. مثال: «انتقال 5000» (با ریپلای روی پیامِ گیرنده).")
        return
    if message.chat.type == "private":
        await message.reply("💸 انتقال باید در گروه و با ریپلای روی پیامِ گیرنده انجام شود.")
        return
    if not message.reply_to_message or not message.reply_to_message.from_user:
        await message.reply("↩️ روی پیامِ کسی که می‌خواهی پول بفرستی «ریپلای» کن و بنویس: انتقال <مبلغ>")
        return
    target = message.reply_to_message.from_user
    if target.is_bot:
        await message.reply("به ربات نمی‌شود پول فرستاد.")
        return
    sender_id = message.from_user.id
    receiver_id = target.id
    if sender_id == receiver_id:
        await message.reply("به خودت نمی‌توانی پول بفرستی.")
        return

    async with async_session() as session:
        sender = await session.scalar(select(Player).where(Player.tg_user_id == sender_id))
        receiver = await session.scalar(select(Player).where(Player.tg_user_id == receiver_id))
        if sender is None:
            await message.reply("اول در چت خصوصی ربات /start را بزن.")
            return
        if receiver is None:
            await message.reply("گیرنده هنوز در بازی ثبت‌نام نکرده است.")
            return
        if int(sender.cash or 0) < amount:
            await message.reply(f"💸 موجودی کافی نداری. موجودی: {sender.cash:,}$")
            return
        fee = int(round(amount * TRANSFER_FEE_PCT))
        received = amount - fee
        sender.cash = int(sender.cash) - amount
        receiver.cash = int(receiver.cash or 0) + received
        session.add(AssetTransfer(
            from_user_id=sender_id, to_user_id=receiver_id,
            kind="cash", amount=amount, fee=fee, received=received,
        ))
        await session.commit()
        s_cash = sender.cash

    await message.reply(
        "✅ <b>انتقال انجام شد!</b>\n"
        f"➡️ به {target.full_name}: <b>{received:,}$</b>\n"
        f"🧾 کارمزد (۲٪): {fee:,}$\n"
        f"💵 موجودیِ تو: {s_cash:,}$"
    )


# ---------- 🆕 انتقالِ منابع (کالا) بینِ کاربران ----------
@router.message(F.text.regexp(r"^\s*انتقال\s+منابع\s+\S+\s+[0-9۰-۹,٫،]+\s*$"))
async def transfer_resource_cmd(message: Message) -> None:
    m = _RESOURCE_RE.match(message.text or "")
    if not m:
        return
    token, raw_amount = m.group(1), m.group(2)
    amount = _parse_amount(raw_amount)
    if not amount or amount <= 0:
        await message.reply("مقدارِ نامعتبر. مثال: «انتقال منابع فلزات 50» (با ریپلای روی پیامِ گیرنده).")
        return
    if message.chat.type == "private":
        await message.reply("📦 انتقالِ منابع باید در گروه و با ریپلای روی پیامِ گیرنده انجام شود.")
        return
    if not message.reply_to_message or not message.reply_to_message.from_user:
        await message.reply("↩️ روی پیامِ کسی که می‌خواهی جنس بفرستی «ریپلای» کن و بنویس: انتقال منابع <نامِ کالا> <مقدار>")
        return
    target = message.reply_to_message.from_user
    if target.is_bot:
        await message.reply("به ربات نمی‌شود جنس فرستاد.")
        return
    sender_id = message.from_user.id
    receiver_id = target.id
    if sender_id == receiver_id:
        await message.reply("به خودت نمی‌توانی جنس بفرستی.")
        return
    key, product = _find_product(token)
    if not key:
        await message.reply(f"❗ کالای «{token}» شناخته نشد. نام یا کدِ دقیقِ محصول را بنویس.")
        return

    async with async_session() as session:
        sender = await session.scalar(select(Player).where(Player.tg_user_id == sender_id))
        receiver = await session.scalar(select(Player).where(Player.tg_user_id == receiver_id))
        if sender is None:
            await message.reply("اول در چت خصوصی ربات /start را بزن.")
            return
        if receiver is None:
            await message.reply("گیرنده هنوز در بازی ثبت‌نام نکرده است.")
            return
        s_wh = await session.scalar(select(MainWarehouse).where(MainWarehouse.tg_user_id == sender_id))
        if s_wh is None:
            await message.reply("🏢 تو هنوز انبارِ اصلی نساخته‌ای.")
            return
        r_wh = await session.scalar(select(MainWarehouse).where(MainWarehouse.tg_user_id == receiver_id))
        if r_wh is None:
            await message.reply("🏢 گیرنده هنوز انبارِ اصلی نساخته است.")
            return
        s_stock = await session.scalar(
            select(WarehouseStock).where(
                WarehouseStock.warehouse_id == s_wh.id,
                WarehouseStock.product_key == key,
            )
        )
        have = s_stock.qty if s_stock else 0
        if not s_stock or have < amount:
            await message.reply(f"📦 موجودیِ کافی نداری. موجودیِ {product['name']}: {have:,}")
            return
        fee_units = int(round(amount * RESOURCE_TRANSFER_FEE_PCT))
        received_units = amount - fee_units
        r_stock = await session.scalar(
            select(WarehouseStock).where(
                WarehouseStock.warehouse_id == r_wh.id,
                WarehouseStock.product_key == key,
            )
        )
        s_stock.qty = have - amount
        if r_stock is None:
            r_stock = WarehouseStock(warehouse_id=r_wh.id, product_key=key, qty=0)
            session.add(r_stock)
        r_stock.qty = (r_stock.qty or 0) + received_units
        session.add(AssetTransfer(
            from_user_id=sender_id, to_user_id=receiver_id,
            kind=f"resource:{key}", amount=amount, fee=fee_units, received=received_units,
        ))
        await session.commit()
        s_left = s_stock.qty

    await message.reply(
        "✅ <b>انتقالِ منابع انجام شد!</b>\n"
        f"📦 {product['name']}\n"
        f"➡️ به {target.full_name}: <b>{received_units:,}</b> واحد\n"
        f"🧾 کارمزد (۵٪): {fee_units:,} واحد\n"
        f"📦 موجودیِ باقی‌مانده‌ی تو: {s_left:,}"
    )
