# -*- coding: utf-8 -*-
"""برندسازی — مرحله ۱۹.۱ + \U0001f195 بازنگاریِ کاملِ مرحله ۲۸.

پیشوندِ کالبک: brd:  —  فقط داخلِ PV.

\U0001f195 مرحله ۲۸:
  • ۵ شرکتِ یکتا: \U0001f697 ماشین‌سازی | ⌚ ساعت‌سازی | \U0001f48e جواهرات | \U0001f454 لباس | \U0001f3a1 هولدینگ
  • هر شرکت فقط یک‌بار قابلِ خرید است
  • تولیدِ درصدی از حجمِ خالیِ انبار (پله‌ی ۱۰٪)
  • نمودارِ قیمتِ مستقل برای محصولاتِ برند
  • هولدینگ: اول هتل → سپس ایرلاین/مجتمع/سرگرمی/رسانه
  • نام‌گذاری و تغییرِ نامِ برند، شرکت‌ها، هولدینگ و واحدهایش
"""
import json
from datetime import datetime, timedelta

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select

from app.data import branding as B
from app.data import brands as BR
from app.data.market import heal_price
from app.database.engine import async_session
from app.handlers.profile import get_player
from app.keyboards.branding_menu import (
    brand_back_menu,
    brand_chart_back_menu,
    brand_create_menu,
    brand_home_menu,
    brand_prices_menu,
    campaigns_menu,
    companies_menu,
    company_menu,
    company_prices_menu,
    expand_menu,
    holding_buy_menu,
    holding_menu,
    holding_unit_menu,
    company_queue_menu,
    percent_menu,
    product_menu,
    queue_percent_menu,
)
from app.models.branding import (
    Brand,
    BrandCompany,
    BrandProduct,
    BrandQueueItem,
    HoldingUnit,
)
from app.models.market import MarketPrice
from app.models.player import Player  # 🆕 مرحله ۳۰ — نامِ مالکِ برند
from app.models.warehouse import MainWarehouse, WarehouseStock
from app.data import warehouse as WH
from app.services import branding_service as BS
from app.states import BrandStates
from app.utils.ui import CANCEL_HINT, ensure_owner, handle_cancel_word, safe_show, split_owner, safe_answer

router = Router(name="branding")

BRAND_ONLY_BOT = "🏷️ بخشِ برندسازی فقط داخلِ خودِ ربات در دسترس است."
# 🆕 مرحله ۳۰ — بخشِ برند در گروه هم فعال شد؛ فقط مراحلی که نیاز به
# نوشتنِ متن (نام‌گذاری/تغییرِ نام) دارند به چتِ خصوصی منتقل می‌شوند.
BRAND_NAMING_ONLY_BOT = (
    "✏️ نام‌گذاری و تغییرِ نام فقط داخلِ خودِ ربات انجام می‌شود (تا پیام‌هایِ گروه قاطی نشوند)."
)
HOLDING_MAX_OFFLINE_HOURS = getattr(BR, "HOLDING_MAX_OFFLINE_HOURS", 24)


def _is_private(chat_type: str) -> bool:
    return chat_type == "private"


def _parts(callback: CallbackQuery):
    """بخش‌های کالبک بدونِ شناسه‌ی مالک."""
    base, _ = split_owner(callback.data)
    return base.split(":")


def _int(value, default=0):
    try:
        return int(value)
    except Exception:
        return default


# ===========================================================================
# خانه‌ی برند
# ===========================================================================
async def _companies(session, uid: int) -> dict:
    rows = (await session.execute(
        select(BrandCompany).where(BrandCompany.owner_id == uid)
    )).scalars().all()
    return {r.company_key: r for r in rows}


async def _company_products(session, company_id: int):
    return (await session.execute(
        select(BrandProduct).where(BrandProduct.company_id == company_id).order_by(BrandProduct.id)
    )).scalars().all()


# 🆕 انبارِ اصلی — انتقالِ محصولاتِ برند به همان انباری که کارخانه‌ها ازش استفاده می‌کنند
async def _user_warehouse(session, uid: int):
    res = await session.execute(select(MainWarehouse).where(MainWarehouse.tg_user_id == uid))
    return res.scalar_one_or_none()


async def _warehouse_rows(session, warehouse_id: int):
    res = await session.execute(select(WarehouseStock).where(WarehouseStock.warehouse_id == warehouse_id))
    return list(res.scalars().all())


async def _wh_add(session, wh, product_key: str, qty: int) -> int:
    """افزودن به انبارِ اصلی با رعایتِ حجم، تعدادِ انجام‌شده را برمی‌گرداند."""
    rows = await _warehouse_rows(session, wh.id)
    total = sum(int(r.qty or 0) for r in rows)
    room = max(0, WH.warehouse_volume(wh.level) - total)
    moved = min(int(qty or 0), room)
    if moved <= 0:
        return 0
    row = next((r for r in rows if r.product_key == product_key), None)
    if row is None:
        session.add(WarehouseStock(warehouse_id=wh.id, product_key=product_key, qty=moved))
    else:
        row.qty = int(row.qty or 0) + moved
    return moved


async def _holding_units(session, uid: int) -> dict:
    rows = (await session.execute(
        select(HoldingUnit).where(HoldingUnit.owner_id == uid)
    )).scalars().all()
    return {r.unit_key: r for r in rows}


def _tracks(unit) -> dict:
    try:
        data = json.loads(unit.tracks or "{}")
        return {k: int(v or 0) for k, v in data.items()}
    except Exception:
        return {}


async def _home_text(session, uid: int, brand) -> str:
    if brand is None:
        return (
            "🏷️ <b>برندسازی</b>\n\n"
            "با ساختنِ برند، هویتِ تجاری‌ات را می‌سازی.\n"
            "• تبلیغ کن تا شهرت بگیری.\n"
            "• بعد از ثبتِ برند، ۵ شرکتِ لوکس برایت باز می‌شود:\n"
            "   \U0001f697 ماشین‌سازی ، ⌚ ساعت‌سازی ، \U0001f48e جواهرات ، \U0001f454 لباس ، \U0001f3a1 هولدینگِ تفریحی"
        )
    tier = B.tier_for(int(brand.reputation))
    nxt = B.next_tier(int(brand.reputation))
    nxt_line = (
        f"🔼 تا رده‌ی بعدی: {nxt[1]} ({nxt[0] - int(brand.reputation):,} شهرت)"
        if nxt else "🏅 بالاترین رده!"
    )
    owned = await _companies(session, uid)
    units = await _holding_units(session, uid)
    hold_income = BR.holding_total_income([(u.unit_key, _tracks(u)) for u in units.values()])
    lines = [
        f"🏷️ <b>{brand.name}</b>",
        f"🎖️ سطحِ برند: {brand.level}/{B.MAX_BRAND_LEVEL}",
        f"⭐ شهرت: {brand.reputation:,}",
        f"🏷️ رده: {tier}",
        nxt_line,
        await BS.brand_bonus_hint(session, int(getattr(brand, "reputation", 0) or 0)),
        "",
        f"🏢 شرکت‌های خریداری‌شده: <b>{len(owned)}</b> از {len(BR.COMPANY_ORDER)}",
    ]
    if units:
        lines.append(f"🎡 واحدهای هولدینگ: <b>{len(units)}</b> — درآمد: <b>{hold_income:,}</b>$/ساعت"
    )
    return "\n".join(lines)


async def _show_home(message: Message, uid: int) -> None:
    async with async_session() as session:
        brand = await BS.get_brand(session, uid)
        text = await _home_text(session, uid, brand)
    if brand is None:
        await safe_show(message, text, brand_create_menu(uid))
    else:
        await safe_show(message, text, brand_home_menu(uid, int(brand.level)))


@router.message(F.text.in_({"برند", "🏷️ برند", "برندسازی"}))
async def summon_brand(message: Message) -> None:
    # 🆕 مرحله ۳۰ — در گروه هم کار می‌کند
    async with async_session() as session:
        player = await get_player(session, message.from_user.id)
    if not player:
        await message.reply("اول در چتِ خصوصیِ ربات /start را بزن.")
        return
    if int(player.level or 1) < B.BRAND_UNLOCK_LEVEL:
        await message.reply(f"🔒 برندسازی از سطحِ {B.BRAND_UNLOCK_LEVEL} باز می‌شود.")
        return
    await _show_home(message, message.from_user.id)


@router.callback_query(F.data.startswith("menu:branding") | F.data.startswith("brd:hub"))
async def open_brand(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    # 🆕 مرحله ۳۰ — دکمهٔ برند در گروه هم پاسخ می‌دهد
    await _show_home(callback.message, callback.from_user.id)
    await safe_answer(callback)


# --------------------------- ثبتِ برند ---------------------------
@router.callback_query(F.data.startswith("brd:create"))
async def create_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not await ensure_owner(callback):
        return
    uid = callback.from_user.id
    async with async_session() as session:
        brand = await BS.get_brand(session, uid)
        player = await get_player(session, uid)
    if brand is not None:
        await safe_answer(callback, "تو قبلاً برند داری.", show_alert=True)
        return
    if player is None or int(player.level or 1) < B.BRAND_UNLOCK_LEVEL:
        await safe_answer(callback, f"🔒 از سطحِ {B.BRAND_UNLOCK_LEVEL} باز می‌شود.", show_alert=True)
        return
    if int(player.cash or 0) < B.BRAND_FOUND_COST:
        await safe_answer(callback, f"پولت کافی نیست. هزینه: {B.BRAND_FOUND_COST:,}$", show_alert=True)
        return
    if not _is_private(callback.message.chat.type):
        await safe_answer(callback, BRAND_NAMING_ONLY_BOT, show_alert=True)
        return
    await state.set_state(BrandStates.creating_name)
    await callback.message.answer(
        "🏷️ نامِ برندت را بفرست (حداکثر ۴۸ کاراکتر)." + CANCEL_HINT,
    )
    await safe_answer(callback)


@router.message(BrandStates.creating_name)
async def create_name(message: Message, state: FSMContext) -> None:
    if await handle_cancel_word(message, state):
        return
    await state.clear()
    uid = message.from_user.id
    async with async_session() as session:
        ok, msg = await BS.create_brand(session, uid, message.text or "")
        if ok:
            await session.commit()
    await message.reply(msg)
    if ok:
        await _show_home(message, uid)


# --------------------------- ارتقا / کمپین / رتبه ---------------------------
@router.callback_query(F.data.startswith("brd:upg"))
async def upgrade(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    uid = callback.from_user.id
    async with async_session() as session:
        ok, msg = await BS.upgrade_brand(session, uid)
        if ok:
            await session.commit()
    await safe_answer(callback, msg, show_alert=True)
    if ok:
        await _show_home(callback.message, uid)


@router.callback_query(F.data.startswith("brd:camp") & ~F.data.startswith("brd:campgo"))
async def show_campaigns(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    uid = callback.from_user.id
    async with async_session() as session:
        brand = await BS.get_brand(session, uid)
    if brand is None:
        await safe_answer(callback, "اول یک برند بساز.", show_alert=True)
        return
    await safe_show(callback.message, "📣 یک کمپینِ تبلیغاتی انتخاب کن:", campaigns_menu(uid))
    await safe_answer(callback)


@router.callback_query(F.data.startswith("brd:campgo:"))
async def run_campaign(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    key = _parts(callback)[2]
    uid = callback.from_user.id
    async with async_session() as session:
        ok, msg = await BS.run_campaign(session, uid, key)
        if ok:
            await session.commit()
    await safe_answer(callback, "✅ انجام شد!" if ok else msg, show_alert=True)
    if ok:
        await safe_show(callback.message, msg, brand_back_menu(uid))


@router.callback_query(F.data.startswith("brd:rank"))
async def show_rank(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    uid = callback.from_user.id
    async with async_session() as session:
        brands = (await session.execute(
            select(Brand).order_by(Brand.reputation.desc()).limit(10)
        )).scalars().all()
        # 🆕 مرحله ۳۰ — نامِ مالک کنارِ نامِ برند (قبلاً ایموجیِ خراب = علامتِ سوال بود)
        owner_names: dict[int, str] = {}
        if brands:
            _rows = (await session.execute(
                select(Player.tg_user_id, Player.name).where(
                    Player.tg_user_id.in_([int(getattr(b, "owner_id")) for b in brands])
                )
            )).all()
            owner_names = {int(r[0]): (r[1] or "بی‌نام") for r in _rows}
        lines = ["🏆 <b>رتبه‌بندیِ برندها</b>", ""]
        for i, br in enumerate(brands, start=1):
            medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(i, f"{i}.")
            owner = owner_names.get(int(getattr(br, "owner_id")), "بی‌نام")
            lines.append(f"{medal} <b>{br.name}</b> — 👤 متعلق به: {owner}")
            lines.append(
                f"      🏅 اعتبار: {br.reputation:,} — {B.tier_for(int(br.reputation))}"
            )
        if not brands:
            lines.append("— هنوز برندی ثبت نشده —")
    await safe_show(callback.message, "\n".join(lines), brand_back_menu(uid))
    await safe_answer(callback)


# ===========================================================================
# \U0001f195 قیمتِ محصولاتِ برند (موتورِ مستقل)
# ===========================================================================
async def _brand_price(session, product_key: str) -> MarketPrice:
    now = datetime.utcnow()
    mp = await session.get(MarketPrice, product_key)
    if mp is None:
        price = BR.brand_initial_price(product_key)
        mp = MarketPrice(
            product_key=product_key,
            price=price,
            history=json.dumps([price]),
            updated_at=now,
        )
        session.add(mp)
        await session.commit()
        return mp
    ticks = BR.brand_ticks_elapsed(mp.updated_at, now)
    history = json.loads(mp.history or "[]")
    # v1.7.8.15: هماهنگ‌سازیِ فوریِ قیمتِ ذخیره‌شده با بازه‌ی فعلیِ کد.
    price, history, healed = heal_price(product_key, mp.price, history, BR.BRAND_HISTORY_LEN)
    if ticks > 0:
        price, history = BR.brand_advance_price(product_key, price, history, ticks)
    if healed or ticks > 0:
        mp.price = price
        mp.history = json.dumps(history)
        if ticks > 0:
            mp.updated_at = now
        await session.commit()
    return mp


@router.callback_query(F.data.startswith("brd:prices") | F.data.startswith("brd:pricesp:"))
async def brand_prices(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    uid = callback.from_user.id
    parts = _parts(callback)
    page = _int(parts[2], 0) if len(parts) > 2 else 0
    lines = [
        "📈 <b>نمودارِ قیمتِ محصولاتِ برند</b>",
        "",
        "قیمتِ این کالاهای لوکس مستقل از کارخانه‌های عادی حرکت می‌کند.",
        "یک شرکت را انتخاب کن تا محصولاتِ همان شرکت را ببینی:",
    ]
    await safe_show(callback.message, "\n".join(lines), brand_prices_menu(uid, page))
    await safe_answer(callback)


@router.callback_query(F.data.startswith("brd:pc:") | F.data.startswith("brd:pcp:"))
async def company_prices(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    uid = callback.from_user.id
    parts = _parts(callback)
    ckey = parts[2]
    page = _int(parts[3], 0) if len(parts) > 3 else 0
    lines = [f"📈 <b>قیمتِ محصولاتِ {BR.company_name(ckey)}</b>", ""]
    async with async_session() as session:
        for key in BR.company_products(ckey):
            p = BR.get_brand_product(key) or {"name": key}
            mp = await _brand_price(session, key)
            hist = json.loads(mp.history or "[]")
            lines.append(
                f"{p['name']} — <b>{mp.price:,.0f}</b>$ {BR.brand_price_arrow(hist)}"
            )
            lines.append(f"   {BR.brand_sparkline(hist[-12:])}")
    await safe_show(callback.message, "\n".join(lines), company_prices_menu(ckey, uid, page))
    await safe_answer(callback)


@router.callback_query(F.data.startswith("brd:chart:"))
async def brand_chart(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    uid = callback.from_user.id
    key = _parts(callback)[2]
    p = BR.get_brand_product(key)
    if not p:
        await safe_answer(callback, "محصولِ نامعتبر.", show_alert=True)
        return
    ckey = BR.company_of_product(key)
    async with async_session() as session:
        mp = await _brand_price(session, key)
        hist = json.loads(mp.history or "[]")
        # 🐞 v1.7.8.14 — این‌جا unit_raw_cost بدون speed_level صدا زده می‌شد،
        # پس همیشه هزینه‌ی سطحِ سرعتِ ۱ را نشان می‌داد؛ در حالی که هنگامِ
        # تولید (خطوط ۷۰۹ / ۷۲۱ / ۷۵۸ / ۱۵۱۱) هزینه با speed_level کسر می‌شود.
        # نتیجه: عددِ نمایش کمتر از عددی بود که از حساب کم می‌شد.
        spd = int(await session.scalar(
            select(BrandCompany.speed_level).where(
                BrandCompany.owner_id == uid,
                BrandCompany.company_key == ckey,
            )
        ) or 1)
    unit_cost = BR.unit_raw_cost(key, spd)
    cost_line = f"🧾 هزینه‌ی موادِ هر واحد: {unit_cost:,}$"
    if spd > 1:
        cost_line += f"  <i>(سرعتِ سطح {spd} ← +{2 * (spd - 1)}٪)</i>"
    lines = [
        f"📈 <b>{p['name']}</b>",
        f"🏢 تولیدکننده: {BR.company_name(ckey)}",
        "",
        f"💵 قیمتِ امروز: <b>{mp.price:,.0f}</b>$ {BR.brand_price_arrow(hist)}",
        f"📊 روندِ ۲۴ ساعت: {BR.brand_sparkline(hist)}",
        f"🔽 کمترین: {p['min']:,}$   🔼 بیشترین: {p['max']:,}$",
        cost_line,
        f"⏱️ زمانِ تولیدِ پایه: {p['produce_hours']} ساعت",
        f"🏷️ سطحِ محصول: {p['tier']}",
    ]
    await safe_show(callback.message, "\n".join(lines), brand_chart_back_menu(key, uid))
    await safe_answer(callback)


# ===========================================================================
# \U0001f195 شرکت‌ها
# ===========================================================================
async def _render_companies(session, message: Message, uid: int, page: int = 0) -> None:
    player = await get_player(session, uid)
    owned = await _companies(session, uid)
    lines = [
        "🏢 <b>شرکت‌های برند</b>",
        f"💵 موجودی: <b>{int(player.cash or 0):,}</b> دلار",
        "",
        "در کلِ بازی <b>۵</b> شرکت وجود دارد و هر کدام <b>فقط یک‌بار</b> قابلِ خرید است.",
        "",
    ]
    for key in BR.COMPANY_ORDER:
        info = BR.COMPANIES[key]
        co = owned.get(key)
        if co is None:
            lines.append(f"➕ {info['name']} — {info['cost']:,}$")
            lines.append(f"   {info['desc']}")
            continue
        if key == BR.HOLDING_KEY:
            units = await _holding_units(session, uid)
            income = BR.holding_total_income([(u.unit_key, _tracks(u)) for u in units.values()])
            lines.append(f"✅ {co.title or info['name']} — 🎡 {len(units)} واحد | 💰 {income:,}$/ساعت")
        else:
            bps = await _company_products(session, co.id)
            stock = sum(int(x.stock or 0) for x in bps)
            producing = sum(len(_busy_slots(x)) for x in bps)   # 🆕 v1.7.8.18
            lines.append(
                f"✅ {co.title or info['name']} — 🏗️ {len(bps)} محصول | ⚙️ {producing} خط در حالِ تولید | 📦 {stock:,}"
            )
    await safe_show(message, "\n".join(lines), companies_menu(owned, uid, page))


@router.callback_query(F.data.startswith("brd:cos") | F.data.startswith("brd:cosp:"))
async def companies_home(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    uid = callback.from_user.id
    parts = _parts(callback)
    page = _int(parts[2], 0) if len(parts) > 2 else 0
    async with async_session() as session:
        brand = await BS.get_brand(session, uid)
        if brand is None:
            await safe_answer(callback, "اول یک برند بساز.", show_alert=True)
            return
        await _render_companies(session, callback.message, uid, page)
    await safe_answer(callback)


@router.callback_query(F.data.startswith("brd:new:"))
async def buy_company(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    uid = callback.from_user.id
    ckey = _parts(callback)[2]
    info = BR.get_company(ckey)
    if not info:
        await safe_answer(callback, "شرکتِ نامعتبر.", show_alert=True)
        return
    async with async_session() as session:
        brand = await BS.get_brand(session, uid)
        if brand is None:
            await safe_answer(callback, "اول یک برند بساز.", show_alert=True)
            return
        owned = await _companies(session, uid)
        if ckey in owned:
            await safe_answer(callback, "❗ این شرکت یکتاست و قبلاً خریده‌ای.", show_alert=True)
            return
        player = await get_player(session, uid)
        cost = int(info["cost"])
        if player is None or int(player.cash or 0) < cost:
            await safe_answer(callback, f"💸 پولت کافی نیست. هزینه: {cost:,}$", show_alert=True)
            return
        player.cash = int(player.cash or 0) - cost
        co = BrandCompany(
            owner_id=uid,
            company_key=ckey,
            title=info["default_name"],
            level=1,
        )
        session.add(co)
        await session.flush()
        if ckey == BR.HOLDING_KEY:
            # هتل واحدِ پایه است و با خریدِ هولدینگ باز می‌شود
            session.add(HoldingUnit(
                owner_id=uid,
                unit_key="hotel",
                title=BR.HOLDING_UNITS["hotel"]["default_name"],
                tracks="{}",
                last_collected_at=datetime.utcnow(),
            ))
            msg = "🎡 هولدینگ خریداری شد! 🏨 هتل برایت باز شد."
        else:
            first = BR.company_products(ckey)[0]
            session.add(BrandProduct(company_id=co.id, product_key=first, percent=50))
            msg = f"🎉 {info['name']} تأسیس شد!"
        from app.data import leveling as _lv
        _xp_res = {}
        try:   # XP for buying a brand company
            _xp_res = await _lv.grant_xp(session, player, min(250, max(10, cost // 6000)), source="brand_company_buy")
            msg = msg + _lv.xp_note(_xp_res)
        except Exception:
            pass
        await session.commit()
    await safe_answer(callback, msg, show_alert=True)
    async with async_session() as session:
        if ckey == BR.HOLDING_KEY:
            await _render_holding(session, callback.message, uid)
        else:
            await _render_companies(session, callback.message, uid)


# ---------- 🆕 v1.7.8.18 — هر محصول دو خطِ تولیدِ مستقل دارد ----------
_SLOT_SUFFIX = ("", "2")


def _slots_count() -> int:
    try:
        return max(1, min(len(_SLOT_SUFFIX), int(getattr(BR, "LINES_PER_PRODUCT", 2) or 2)))
    except Exception:
        return 2


def _sg(bp, slot, field, default=None):
    return getattr(bp, f"{field}{_SLOT_SUFFIX[slot]}", default)


def _ss(bp, slot, field, value) -> None:
    setattr(bp, f"{field}{_SLOT_SUFFIX[slot]}", value)


def _slot_busy(bp, slot) -> bool:
    return str(_sg(bp, slot, "status", "") or "") == "producing"


def _busy_slots(bp):
    return [s for s in range(_slots_count()) if _slot_busy(bp, s)]


def _free_slots(bp):
    return [s for s in range(_slots_count()) if not _slot_busy(bp, s)]


def _free_slot(bp):
    free = _free_slots(bp)
    return free[0] if free else None


def _slot_clear(bp, slot) -> None:
    _ss(bp, slot, "status", "idle")
    _ss(bp, slot, "pending_units", 0)
    _ss(bp, slot, "started_at", None)


def _slot_start(bp, slot, units, pct) -> None:
    _ss(bp, slot, "status", "producing")
    _ss(bp, slot, "percent", BR.normalize_percent(pct))
    _ss(bp, slot, "pending_units", int(units))
    _ss(bp, slot, "started_at", datetime.utcnow())


def _slot_units(bp, slot, company=None) -> int:
    if not _slot_busy(bp, slot):
        return 0
    return int(_sg(bp, slot, "pending_units", 0) or 0)


def _slot_ready(bp, slot, speed_level) -> bool:
    if not _slot_busy(bp, slot):
        return False
    started = _sg(bp, slot, "started_at", None)
    if started is None:
        return False
    hrs = BR.effective_produce_hours(bp.product_key, speed_level)
    return datetime.utcnow() >= started + timedelta(hours=hrs)


def _ready_slots(bp, speed_level):
    return [s for s in _busy_slots(bp) if _slot_ready(bp, s, speed_level)]


def _slot_mins_left(bp, slot, speed_level):
    started = _sg(bp, slot, "started_at", None)
    if started is None:
        return None
    hrs = BR.effective_produce_hours(bp.product_key, speed_level)
    return max(0, int((started + timedelta(hours=hrs) - datetime.utcnow()).total_seconds() // 60))


def _fmt_mins(mins) -> str:
    h, m = divmod(int(mins or 0), 60)
    return f"{h}س {m}د" if h else f"{m}د"


def _slot_remaining(bp, slot, speed_level) -> str:
    return _fmt_mins(_slot_mins_left(bp, slot, speed_level) or 0)


def _pending_units(bp, company=None) -> int:
    return sum(_slot_units(bp, s, company) for s in range(_slots_count()))


def _bp_lines_text(bp, company) -> str:
    """خلاصهٔ وضعیتِ خطوطِ یک محصول برایِ لیستِ شرکت."""
    parts, free = [], 0
    for s in range(_slots_count()):
        if not _slot_busy(bp, s):
            free += 1
        elif _slot_ready(bp, s, company.speed_level):
            parts.append(f"✅ خطِ {s + 1}: آماده ({_slot_units(bp, s, company):,})")
        else:
            parts.append(
                f"⏳ خطِ {s + 1}: {_slot_remaining(bp, s, company.speed_level)}"
                f" ({_slot_units(bp, s, company):,})"
            )
    if free:
        parts.append(f"⚪ {free} خطِ آزاد")
    return " | ".join(parts)


def _lines_block_msg(bp) -> str:
    return chr(10).join([
        "🧵 همهٔ خطوطِ تولیدِ این محصول مشغول است!",
        "",
        f"هر محصول {_slots_count()} خطِ تولیدِ مستقل دارد.",
        "صبر کن تا یکی آزاد شود، یا سفارش را به «🧾 صفِ ساخت» بفرست.",
    ])


def _bp_ready(bp, speed_level) -> bool:
    return bool(_ready_slots(bp, speed_level))


def _bp_remaining(bp, speed_level) -> str:
    best = None
    for s in _busy_slots(bp):
        mins = _slot_mins_left(bp, s, speed_level)
        if mins is None:
            continue
        best = mins if best is None else min(best, mins)
    return _fmt_mins(best or 0)


def _reserved_units(rows) -> int:
    """🆕 v1.7.8.16 - واحدهایی که تولیدِ در جریان از انبار رزرو کرده."""
    return sum(_pending_units(x) for x in rows)


def _p_cap(bp) -> int:
    """🆕 v1.7.8.17 — ظرفیتِ انبارِ اختصاصیِ همین محصول."""
    return BR.product_capacity(getattr(bp, "capacity_level", 1) or 1)


def _p_used(bp, reserve: bool = True) -> int:
    used = int(getattr(bp, "stock", 0) or 0)
    if reserve:
        used += _pending_units(bp)   # 🆕 v1.7.8.18 — جمعِ هر دو خط
    return used


def _bp_room(bp, reserve: bool = True) -> int:
    """🆕 v1.7.8.17 — حجمِ خالیِ انبارِ *خودِ محصول* (نه کلِ شرکت)."""
    return max(0, _p_cap(bp) - _p_used(bp, reserve))


def _room_block_msg(bp) -> str:
    """🆕 v1.7.8.17 — پیامِ دقیق وقتی انبارِ همین محصول جا ندارد."""
    cap = _p_cap(bp)
    stock = int(getattr(bp, "stock", 0) or 0)
    pend = _pending_units(bp)   # 🆕 v1.7.8.18 — جمعِ هر دو خط
    if pend > 0:
        return chr(10).join([
            "⏳ انبارِ این محصول جا ندارد!",
            "",
            f"📦 {stock + pend:,}/{cap:,} واحد ({pend:,} واحد در حالِ تولید)",
            "",
            "جمع‌آوری‌اش کن و بفروش، یا به «🧾 صفِ ساخت» بفرست.",
        ])
    return chr(10).join([
        "📦 انبارِ این محصول پر است!",
        "",
        f"📦 {stock:,}/{cap:,} واحد",
        "",
        "بفروش، منتقل کن، انبارش را ارتقا بده، یا به «🧾 صفِ ساخت» بفرست.",
    ])


def _company_block_msg(company, bps) -> str:
    """🆕 v1.7.8.17 — پیامِ کلی وقتی هیچ‌کدام از انبارهایِ محصولات جا ندارند."""
    cap = BR.company_total_capacity(bps)
    stock = sum(int(getattr(x, "stock", 0) or 0) for x in bps)
    reserved = _reserved_units(bps)
    if reserved > 0:
        return chr(10).join([
            "⏳ جا برای تولیدِ تازه نیست!",
            "",
            f"📦 انبارِ شرکت: {stock + reserved:,}/{cap:,} واحد",
            f"🏭 {reserved:,} واحد در حالِ تولید است و جا را گرفته.",
            "",
            "جمع‌آوری کن و بفروش، یا سفارش‌ها را به «🧾 صفِ ساخت» بسپار.",
        ])
    return chr(10).join([
        "📦 انبارِ همه‌ی محصولات پر است!",
        "",
        f"📦 انبارِ شرکت: {stock:,}/{cap:,} واحد",
        "",
        "بفروش یا به انبارِ اصلی منتقل کن، یا انبارِ محصولات را ارتقا بده.",
    ])


def _free_room(company, bps, reserve: bool = False) -> int:
    """حجمِ خالیِ کلِ شرکت = جمعِ حجمِ خالیِ انبارِ محصولاتش.

    🆕 v1.7.8.17 — فقط برایِ نمایشِ کلی. گیتِ تولید از `_bp_room` استفاده
    می‌کند، چون هر محصول انبارِ جداگانهٔ خودش را دارد.
    """
    return sum(_bp_room(x, reserve) for x in bps)


# ---------- 🆕 v1.7.8.17 — صفِ ساختِ شرکتِ برند ----------
async def _queue_rows(session, company_id: int):
    """همه‌ی سفارش‌هایِ صفِ یک شرکت، به‌ترتیبِ ثبت."""
    res = await session.execute(
        select(BrandQueueItem)
        .where(BrandQueueItem.company_id == company_id)
        .order_by(BrandQueueItem.id)
    )
    return list(res.scalars().all())


async def _queue_for_bp(session, bp_id: int):
    res = await session.execute(
        select(BrandQueueItem)
        .where(BrandQueueItem.bp_id == bp_id)
        .order_by(BrandQueueItem.id)
    )
    return list(res.scalars().all())


async def _try_start_queue(session, company, bps=None):
    """هر جا در انبار جا باز شود، سفارش‌هایِ صف را جلو می‌بَرد.

    پولِ مواد هنگامِ ثبت در صف کسر شده؛ اینجا دوباره پول گرفته
    نمی‌شود. commit بر عهدهٔ صدازننده است.
    """
    items = await _queue_rows(session, company.id)
    if not items:
        return 0, 0
    if bps is None:
        bps = await _company_products(session, company.id)
    by_id = {bp.id: bp for bp in bps}
    started, units_total = 0, 0
    for it in items:
        bp = by_id.get(int(getattr(it, "bp_id", 0) or 0))
        want = max(0, int(getattr(it, "units", 0) or 0))
        if bp is None or want <= 0:
            await session.delete(it)
            continue
        # 🆕 v1.7.8.18 — هر محصول دو خطِ مستقل دارد
        slot = _free_slot(bp)
        if slot is None:
            continue
        room = _bp_room(bp)
        if room <= 0:
            continue
        take = min(want, room)
        _slot_start(bp, slot, take,
                    getattr(it, "percent", None) or getattr(BR, "START_ALL_PERCENT", 100))
        started += 1
        units_total += take
        if take >= want:
            await session.delete(it)
        else:
            paid = max(0, int(getattr(it, "paid_cost", 0) or 0))
            it.paid_cost = max(0, paid - (paid * take) // want)
            it.units = want - take
    return started, units_total


def _company_costs(company, bps):
    ckey = company.company_key
    unlocked = len(bps)
    max_prod = len(BR.company_products(ckey))
    line_max = min(BR.MAX_TRACK_LEVEL, max_prod)
    costs = {
        "expand": BR.expansion_upgrade_cost(unlocked) if unlocked < max_prod else None,
        # 🆕 v1.7.8.17 — انبارِ شرکت دیگر مستقیم ارتقا نمی‌شود؛ از صفحهٔ هر محصول.
        "cap": None,
        "spd": BR.speed_upgrade_cost(company.speed_level) if company.speed_level < BR.MAX_TRACK_LEVEL else None,
        "line": BR.line_upgrade_cost(company.line_level) if company.line_level < line_max else None,
    }
    return costs, unlocked < max_prod


async def _render_company(session, message: Message, uid: int, company, page: int = 0) -> None:
    player = await get_player(session, uid)
    bps = await _company_products(session, company.id)
    info = BR.get_company(company.company_key) or {"name": company.company_key}
    # 🆕 v1.7.8.17 — ظرفیتِ شرکت = جمعِ انبارِ محصولاتش
    cap = BR.company_total_capacity(bps)
    stock = sum(int(x.stock or 0) for x in bps)
    reserved = _reserved_units(bps)  # 🆕 v1.7.8.16 — تولیدِ در جریان هم جا می‌گیرد
    producing = sum(len(_busy_slots(x)) for x in bps)   # 🆕 v1.7.8.18
    total_lines = len(bps) * _slots_count()
    max_prod = len(BR.company_products(company.company_key))
    ready_map = {}
    lines = [
        f"🏢 <b>{company.title or info['name']}</b>",
        f"💵 موجودی: <b>{int(player.cash or 0):,}</b> دلار",
        "",
        f"📦 انبارِ شرکت: <b>{stock + reserved:,}</b>/{cap:,} واحد (جمعِ انبارِ {len(bps)} محصول)"
        + (
            chr(10) + f"   ├ 💰 قابلِ فروش: <b>{stock:,}</b> واحد"
            + chr(10) + f"   └ 🏭 در حالِ تولید: <b>{reserved:,}</b> واحد (هنوز قابلِ فروش نیست)"
            if reserved else ""
        ),
        f"🔳 حجمِ خالی: <b>{max(0, cap - stock - reserved):,}</b> واحد",
        f"⚡ سرعت: سطح {company.speed_level} (زمانِ تولید ×{BR.speed_factor(company.speed_level):.2f})",
        f"🧵 خطِ تولیدِ همزمان: {producing}/{total_lines} ({_slots_count()} خط برایِ هر محصول)",
        f"🏗️ محصولاتِ بازشده: {len(bps)}/{max_prod}",
        "",
        "<b>محصولات:</b>",
    ]
    for bp in bps:
        p = BR.get_brand_product(bp.product_key) or {"name": bp.product_key}
        # 🆕 v1.7.8.18 — وضعیتِ هر دو خط
        ready_map[bp.id] = _bp_ready(bp, company.speed_level)
        st = _bp_lines_text(bp, company)
        extra = f" | 📦 {int(bp.stock or 0):,}/{_p_cap(bp):,}"   # 🆕 v1.7.8.17
        lines.append(f"• {p['name']} — {st}{extra}")
    costs, can_expand = _company_costs(company, bps)
    qn = len(await _queue_rows(session, company.id))   # 🆕 v1.7.8.17
    await safe_show(
        message,
        "\n".join(lines),
        company_menu(company, bps, ready_map, can_expand, costs, uid, page, queue_count=qn),
    )


async def _get_company(session, uid: int, cid: int):
    co = await session.get(BrandCompany, cid)
    if co is None or int(co.owner_id) != int(uid):
        return None
    return co


@router.callback_query(F.data.startswith("brd:co:") | F.data.startswith("brd:copg:"))
async def company_home(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    uid = callback.from_user.id
    parts = _parts(callback)
    cid = _int(parts[2], 0)
    page = _int(parts[3], 0) if len(parts) > 3 else 0
    async with async_session() as session:
        co = await _get_company(session, uid, cid)
        if co is None:
            await safe_answer(callback, "شرکت پیدا نشد.", show_alert=True)
            return
        await _render_company(session, callback.message, uid, co, page)
    await safe_answer(callback)


async def _render_product(session, message: Message, uid: int, company, bp) -> None:
    player = await get_player(session, uid)
    p = BR.get_brand_product(bp.product_key) or {"name": bp.product_key, "min": 0, "max": 0}
    mp = await _brand_price(session, bp.product_key)
    hist = json.loads(mp.history or "[]")
    brand = await BS.get_brand(session, uid)
    mult = 1.0 + ((await BS.reputation_bonus_pct(session, int(getattr(brand,'reputation',0) or 0))) / 100.0 if brand else 0.0)
    bps = await _company_products(session, company.id)
    # 🆕 v1.7.8.17 — جا فقط در انبارِ خودِ همین محصول
    room = _bp_room(bp)
    p_cap = _p_cap(bp)
    p_lvl = int(getattr(bp, "capacity_level", 1) or 1)
    cap_cost = (BR.product_capacity_upgrade_cost(p_lvl)
                if p_lvl < BR.PRODUCT_CAP_MAX_LEVEL else None)
    qrows = await _queue_for_bp(session, bp.id)
    unit_cost = BR.unit_raw_cost(bp.product_key, company.speed_level)
    hrs = BR.effective_produce_hours(bp.product_key, company.speed_level)
    unit_price = mp.price * mult
    ready = _bp_ready(bp, company.speed_level)
    lines = [
        f"{p['name']} — {company.title or BR.company_name(company.company_key)}",
        f"💵 موجودی: <b>{int(player.cash or 0):,}</b> دلار",
        "",
        f"📈 قیمتِ بازار: <b>{mp.price:,.0f}</b>$ {BR.brand_price_arrow(hist)}",
        f"🏷️ با بونوسِ برند: <b>{unit_price:,.0f}</b>$ / واحد",
        f"🧾 هزینه‌ی موادِ هر واحد: <b>{unit_cost:,}</b>$",
        f"📦 انبارِ این محصول: <b>{int(bp.stock or 0):,}</b>/{p_cap:,} واحد "
        f"(سطح {p_lvl}/{BR.PRODUCT_CAP_MAX_LEVEL}) — ≈ {int(int(bp.stock or 0) * unit_price):,}$"
        + (f"{chr(10)}   └ 🏭 در حالِ تولید: <b>{_pending_units(bp):,}</b> واحد"
           " (جا گرفته، هنوز قابلِ فروش نیست)" if _busy_slots(bp) else ""),
        f"🔳 حجمِ خالیِ انبارِ این محصول: <b>{room:,}</b> واحد"
        + (f"{chr(10)}🧾 صفِ ساخت: <b>{len(qrows)}</b> سفارش "
           f"({sum(int(q.units or 0) for q in qrows):,} واحد منتظر)" if qrows else ""),
        f"📊 روندِ قیمت: {BR.brand_sparkline(hist[-12:])}",
        "",
    ]
    # 🆕 v1.7.8.18 — وضعیتِ خط‌به‌خط (هر محصول دو خطِ مستقل دارد)
    can_start = _free_slot(bp) is not None
    lines.append(f"🧵 خطوطِ این محصول ({_slots_count()} خط):")
    for _s in range(_slots_count()):
        if not _slot_busy(bp, _s):
            lines.append(f"   • خطِ {_s + 1}: ⚪ بی‌کار — آمادهٔ شروع")
        elif _slot_ready(bp, _s, company.speed_level):
            lines.append(
                f"   • خطِ {_s + 1}: ✅ {_slot_units(bp, _s, company):,} واحد آماده است!"
            )
        else:
            lines.append(
                f"   • خطِ {_s + 1}: ⏳ {_slot_units(bp, _s, company):,} واحد — "
                f"{_slot_remaining(bp, _s, company.speed_level)} مانده"
            )
    lines.append(f"⏱️ هر دوره‌ی تولید: {hrs:.1f} ساعت.")
    if can_start and room > 0:
        lines.append(
            "▶️ تا حدِ جایِ خالیِ انبارِ این محصول می‌توانی تولیدِ تازه شروع کنی"
            "، حتی وقتی خطِ دیگر مشغول است."
        )
    wh = await _user_warehouse(session, uid)
    await safe_show(message, "\n".join(lines), product_menu(
        company.id, bp, ready, uid, wh is not None,
        cap_cost=cap_cost, cap_level=p_lvl, queue_count=len(qrows),
        can_start=can_start, busy=bool(_busy_slots(bp)),
    ))


async def _get_bp(session, company_id: int, product_key: str):
    return (await session.execute(
        select(BrandProduct).where(
            BrandProduct.company_id == company_id,
            BrandProduct.product_key == product_key,
        )
    )).scalar_one_or_none()


@router.callback_query(F.data.startswith("brd:cp:"))
async def product_home(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    uid = callback.from_user.id
    parts = _parts(callback)
    cid, pkey = _int(parts[2], 0), parts[3]
    async with async_session() as session:
        co = await _get_company(session, uid, cid)
        if co is None:
            await safe_answer(callback, "شرکت پیدا نشد.", show_alert=True)
            return
        bp = await _get_bp(session, cid, pkey)
        if bp is None:
            await safe_answer(callback, "این محصول هنوز باز نشده.", show_alert=True)
            return
        await _render_product(session, callback.message, uid, co, bp)
    await safe_answer(callback)


@router.callback_query(F.data.startswith("brd:cpct:"))
async def product_percent(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    uid = callback.from_user.id
    parts = _parts(callback)
    cid, pkey = _int(parts[2], 0), parts[3]
    async with async_session() as session:
        co = await _get_company(session, uid, cid)
        if co is None:
            await safe_answer(callback, "شرکت پیدا نشد.", show_alert=True)
            return
        bps = await _company_products(session, cid)
        bp = next((x for x in bps if x.product_key == pkey), None)
        if bp is None:
            await safe_answer(callback, "محصول پیدا نشد.", show_alert=True)
            return
        room = _bp_room(bp)   # 🆕 v1.7.8.17 — انبارِ خودِ محصول
        if room <= 0:
            await safe_answer(callback, _room_block_msg(bp), show_alert=True)
            return
        p_cap = _p_cap(bp)
        unit_cost = BR.unit_raw_cost(pkey, co.speed_level)
    p = BR.get_brand_product(pkey) or {"name": pkey}
    lines = [
        f"🎛️ <b>درصدِ تولیدِ {p['name']}</b>",
        "",
        f"🔳 حجمِ خالیِ انبارِ این محصول: <b>{room:,}</b>/{p_cap:,} واحد",
        f"🧾 هزینه‌ی موادِ هر واحد: <b>{unit_cost:,}</b>$",
        "",
        "هر دکمه = درصدی از حجمِ خالیِ انبارِ همین محصول:",
    ]
    for pct in BR.PERCENT_STEPS:
        units = BR.units_for_percent(room, pct)
        lines.append(f"• {pct}٪ ← {units:,} واحد ({BR.raw_cost_for_units(pkey, units, co.speed_level):,}$)")
    await safe_show(callback.message, "\n".join(lines), percent_menu(cid, pkey, uid))
    await safe_answer(callback)


@router.callback_query(F.data.startswith("brd:cstart:"))
async def product_start(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    uid = callback.from_user.id
    parts = _parts(callback)
    cid, pkey, pct = _int(parts[2], 0), parts[3], _int(parts[4], 50)
    async with async_session() as session:
        co = await _get_company(session, uid, cid)
        if co is None:
            await safe_answer(callback, "شرکت پیدا نشد.", show_alert=True)
            return
        bps = await _company_products(session, cid)
        bp = next((x for x in bps if x.product_key == pkey), None)
        if bp is None:
            await safe_answer(callback, "محصول پیدا نشد.", show_alert=True)
            return
        # 🆕 v1.7.8.18 — فقط کافیست یکی از دو خطِ خودِ محصول آزاد باشد
        slot = _free_slot(bp)
        if slot is None:
            await safe_answer(callback, _lines_block_msg(bp), show_alert=True)
            return
        room = _bp_room(bp)   # 🆕 v1.7.8.17 — انبارِ خودِ محصول
        if room <= 0:
            await safe_answer(callback, _room_block_msg(bp), show_alert=True)
            return
        units = BR.units_for_percent(room, pct)
        cost = BR.raw_cost_for_units(pkey, units, co.speed_level)
        player = await get_player(session, uid)
        if player is None or int(player.cash or 0) < cost:
            await safe_answer(callback, f"💸 پولت کافی نیست. هزینه‌ی مواد: {cost:,}$", show_alert=True)
            return
        player.cash = int(player.cash or 0) - cost
        _slot_start(bp, slot, units, pct)   # 🆕 v1.7.8.18
        await session.commit()
        await safe_answer(
            callback,
            f"▶️ خطِ {slot + 1}: تولیدِ {units:,} واحد ({pct}٪) شروع شد — مواد: {cost:,}$",
            show_alert=True,
        )
        co = await _get_company(session, uid, cid)
        bp = await _get_bp(session, cid, pkey)
        await _render_product(session, callback.message, uid, co, bp)


@router.callback_query(F.data.startswith("brd:cstartall:"))
async def product_start_all(callback: CallbackQuery) -> None:
    """شروعِ همه‌ی خطوطِ بی‌کار با درصدِ ذخیره‌شده‌ی هر محصول."""
    if not await ensure_owner(callback):
        return
    uid = callback.from_user.id
    cid = _int(_parts(callback)[2], 0)
    async with async_session() as session:
        co = await _get_company(session, uid, cid)
        if co is None:
            await safe_answer(callback, "شرکت پیدا نشد.", show_alert=True)
            return
        bps = await _company_products(session, cid)
        player = await get_player(session, uid)
        # 🆕 v1.7.8.18 — «شروعِ همه» همیشه ۱۰��٪ حجمِ خالیِ هر محصول را می‌سازد
        pct_all = int(getattr(BR, "START_ALL_PERCENT", 100) or 100)
        started, spent, no_cash = 0, 0, False
        # 🆕 v1.7.8.17 — هر محصول از انبارِ خودش سهم می‌گیرد
        _qrows = await _queue_rows(session, cid)
        if not _qrows and _free_room(co, bps, reserve=True) <= 0:
            await safe_answer(callback, _company_block_msg(co, bps), show_alert=True)
            return
        for bp in bps:
            # هر محصول دو خطِ مستقل دارد؛ تا جایی که انبار جا دارد پر می‌شوند
            for _ in range(_slots_count()):
                slot = _free_slot(bp)
                if slot is None:
                    break
                room = _bp_room(bp)
                if room <= 0:
                    break
                units = BR.units_for_percent(room, pct_all)
                if units <= 0:
                    break
                cost = BR.raw_cost_for_units(bp.product_key, units, co.speed_level)
                if int(player.cash or 0) < cost:
                    no_cash = True
                    break
                player.cash = int(player.cash or 0) - cost
                _slot_start(bp, slot, units, pct_all)
                started += 1
                spent += cost
        # 🆕 v1.7.8.17 — «شروعِ همه» صفِ ساخت را هم جلو می‌بَرد
        q_started, q_units = await _try_start_queue(session, co, bps)
        if started or q_started:
            await session.commit()
        if started or q_started:
            _m = f"▶️ {started} خط با ۱۰۰٪ حجمِ خالی شروع شد — مواد: {spent:,}$"
            if q_started:
                _m += chr(10) + f"🧾 {q_started} سفارش از صف شروع شد ({q_units:,} واحد)."
            if no_cash:
                _m += chr(10) + "💸 برایِ باقیِ خط‌ها پولِ مواد کم بود."
        elif no_cash:
            _m = "💸 پولِ مواد کافی نبود."
        else:
            _m = "خطِ بی‌کاری برای شروع نبود، یا انبارِ محصولات جا نداشت."
        await safe_answer(callback, _m, show_alert=True)
        co = await _get_company(session, uid, cid)
        await _render_company(session, callback.message, uid, co)


@router.callback_query(F.data.startswith("brd:ccol:"))
async def product_collect(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    uid = callback.from_user.id
    parts = _parts(callback)
    cid, pkey = _int(parts[2], 0), parts[3]
    async with async_session() as session:
        co = await _get_company(session, uid, cid)
        if co is None:
            await safe_answer(callback, "شرکت پیدا نشد.", show_alert=True)
            return
        bps = await _company_products(session, cid)
        bp = next((x for x in bps if x.product_key == pkey), None)
        if bp is None or not _busy_slots(bp):
            await safe_answer(callback, "تولیدی در جریان نیست.", show_alert=True)
            return
        _rs = _ready_slots(bp, co.speed_level)   # 🆕 v1.7.8.18
        if not _rs:
            await safe_answer(callback, f"⏳ هنوز آماده نیست — {_bp_remaining(bp, co.speed_level)} مانده.", show_alert=True)
            return
        room = _bp_room(bp, reserve=False)   # 🆕 v1.7.8.17
        units, leftover = 0, 0
        # v1.7.6.1 — مثل کارخانه: فقط به اندازه فضا؛ باقی‌مانده نگه داشته شود
        for _s in _rs:
            _u = _slot_units(bp, _s, co)
            _add = max(0, min(_u, room))
            bp.stock = int(bp.stock or 0) + _add
            room -= _add
            units += _add
            _left = max(0, _u - _add)
            if _left > 0:
                _ss(bp, _s, "pending_units", _left)   # started_at دست نمی‌خورد
                leftover += _left
            else:
                _slot_clear(bp, _s)
        await _try_start_queue(session, co, bps)   # 🆕 v1.7.8.17
        await session.commit()
        if leftover > 0:
            msg = (
                f"📥 {units:,} واحد به انبار برند رفت." + '\n' +
                f"⚠️ {leftover:,} واحد جا نبود و نگه داشته شد — ا��بار را خالی/منتقل کن و دوباره جمع‌آوری بزن."
            )
        else:
            msg = f"📥 {units:,} واحد به انبار برند رفت."
        await safe_answer(callback, msg, show_alert=True)
        co = await _get_company(session, uid, cid)
        bp = await _get_bp(session, cid, pkey)
        await _render_product(session, callback.message, uid, co, bp)


@router.callback_query(F.data.startswith("brd:ccolall:"))
async def product_collect_all(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    uid = callback.from_user.id
    cid = _int(_parts(callback)[2], 0)
    async with async_session() as session:
        co = await _get_company(session, uid, cid)
        if co is None:
            await safe_answer(callback, "شرکت پیدا نشد.", show_alert=True)
            return
        bps = await _company_products(session, cid)
        total = 0
        leftover_total = 0
        for bp in bps:
            # 🆕 v1.7.8.18 — هر دو خطِ هر محصول
            room = _bp_room(bp, reserve=False)   # 🆕 v1.7.8.17
            for _s in _ready_slots(bp, co.speed_level):
                _u = _slot_units(bp, _s, co)
                _add = max(0, min(_u, room))
                bp.stock = int(bp.stock or 0) + _add
                room -= _add
                total += _add
                _left = max(0, _u - _add)
                if _left > 0:
                    _ss(bp, _s, "pending_units", _left)
                    leftover_total += _left
                else:
                    _slot_clear(bp, _s)
        # 🆕 v1.7.8.17 — پس از جمع‌آوری، صفِ ساخت خودکار جلو می‌رود
        q_started, q_units = await _try_start_queue(session, co, bps)
        if total or leftover_total or q_started:
            await session.commit()
        if not total and not leftover_total:
            msg = "محصولِ آماده‌ای نبود."
        elif leftover_total:
            msg = (
                f"📥 درمجموع {total:,} واحد جمع‌آوری شد." + '\n' +
                f"⚠️ {leftover_total:,} واحد جا نبود و نگه داشته شد — دوباره جمع‌آوری کن."
            )
        else:
            msg = f"📥 درمجموع {total:,} واحد جمع‌آوری شد."
        if q_started:
            msg += chr(10) + f"🧾 {q_started} سفارش از صف شروع شد ({q_units:,} واحد)."
        await safe_answer(callback, msg, show_alert=True)
        co = await _get_company(session, uid, cid)
        await _render_company(session, callback.message, uid, co)


@router.callback_query(F.data.startswith("brd:csell:"))
async def product_sell(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    uid = callback.from_user.id
    parts = _parts(callback)
    cid, pkey = _int(parts[2], 0), parts[3]
    async with async_session() as session:
        co = await _get_company(session, uid, cid)
        if co is None:
            await safe_answer(callback, "شرکت پیدا نشد.", show_alert=True)
            return
        bp = await _get_bp(session, cid, pkey)
        if bp is None or not int(bp.stock or 0):
            await safe_answer(callback, "انبارِ این محصول خالی است.", show_alert=True)
            return
        mp = await _brand_price(session, pkey)
        brand = await BS.get_brand(session, uid)
        mult = 1.0 + ((await BS.reputation_bonus_pct(session, int(getattr(brand,'reputation',0) or 0))) / 100.0 if brand else 0.0)
        units = int(bp.stock or 0)
        base_gain = int(units * mp.price * mult)
        player = await get_player(session, uid)
        from app.services.bonus_breakdown import income_breakdown, append_note
        br = await income_breakdown(session, uid, base_gain)
        gain = int(br["total"])
        player.cash = int(player.cash or 0) + gain
        bp.stock = 0
        await _try_start_queue(session, co)   # 🆕 v1.7.8.17
        await session.commit()
        await safe_answer(callback, append_note(f"💰 {units:,} واحد فروخته شد: +{gain:,}$", br.get("note") or ""), show_alert=True)
        co = await _get_company(session, uid, cid)
        bp = await _get_bp(session, cid, pkey)
        await _render_product(session, callback.message, uid, co, bp)


@router.callback_query(F.data.startswith("brd:ctomain:"))
async def product_to_main(callback: CallbackQuery) -> None:
    """🆕 انتقالِ موجودیِ انبارِ یک محصولِ برند به انبارِ اصلی."""
    if not await ensure_owner(callback):
        return
    uid = callback.from_user.id
    parts = _parts(callback)
    cid, pkey = _int(parts[2], 0), parts[3]
    async with async_session() as session:
        co = await _get_company(session, uid, cid)
        if co is None:
            await safe_answer(callback, "شرکت پیدا نشد.", show_alert=True)
            return
        bp = await _get_bp(session, cid, pkey)
        if bp is None or not int(bp.stock or 0):
            await safe_answer(callback, "انبارِ این محصول خالی اس��.", show_alert=True)
            return
        wh = await _user_warehouse(session, uid)
        if wh is None:
            await safe_answer(callback, "⛔ اول «🏢 انبارِ اصلی» را از بخشِ بازار بساز.", show_alert=True)
            return
        moved = await _wh_add(session, wh, pkey, int(bp.stock or 0))
        if moved <= 0:
            await safe_answer(callback, "🏢 انبارِ اصلی پر است! ارتقا بده یا بفروش.", show_alert=True)
            return
        bp.stock = int(bp.stock or 0) - moved
        await _try_start_queue(session, co)   # 🆕 v1.7.8.17
        await session.commit()
        await safe_answer(callback, f"🏢 {moved:,} واحد به انبارِ اصلی منتقل شد.", show_alert=True)
        co = await _get_company(session, uid, cid)
        bp = await _get_bp(session, cid, pkey)
        await _render_product(session, callback.message, uid, co, bp)


@router.callback_query(F.data.startswith("brd:ctomainall:"))
async def company_to_main_all(callback: CallbackQuery) -> None:
    """🆕 انتقالِ یکجای موجودیِ همه‌ی محصولاتِ یک شرکت به انبارِ اصلی."""
    if not await ensure_owner(callback):
        return
    uid = callback.from_user.id
    cid = _int(_parts(callback)[2], 0)
    async with async_session() as session:
        co = await _get_company(session, uid, cid)
        if co is None:
            await safe_answer(callback, "شرکت پیدا نشد.", show_alert=True)
            return
        wh = await _user_warehouse(session, uid)
        if wh is None:
            await safe_answer(callback, "⛔ اول «🏢 انبارِ اصلی» را از بخشِ بازار بساز.", show_alert=True)
            return
        bps = await _company_products(session, cid)
        moved_total = 0
        for bp in bps:
            if not int(bp.stock or 0):
                continue
            moved = await _wh_add(session, wh, bp.product_key, int(bp.stock or 0))
            bp.stock = int(bp.stock or 0) - moved
            moved_total += moved
            if moved == 0:
                break
        # 🆕 v1.7.8.17 — خالی‌شدنِ انبار یعنی صف می‌تواند شروع کند
        q_started, q_units = await _try_start_queue(session, co, bps)
        if moved_total or q_started:
            await session.commit()
        co = await _get_company(session, uid, cid)
        await _render_company(session, callback.message, uid, co)
    if moved_total:
        await safe_answer(callback, f"🏢 {moved_total:,} واحد به انبارِ اصلی منتقل شد.", show_alert=True)
    else:
        await safe_answer(callback, "🏢 انبارِ اصلی جا ندارد یا موجودی صفر است.", show_alert=True)


@router.callback_query(F.data.startswith("brd:cexpand:") | F.data.startswith("brd:cexpandp:"))
async def company_expand(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    uid = callback.from_user.id
    parts = _parts(callback)
    cid = _int(parts[2], 0)
    page = _int(parts[3], 0) if len(parts) > 3 else 0
    async with async_session() as session:
        co = await _get_company(session, uid, cid)
        if co is None:
            await safe_answer(callback, "شرکت پیدا نشد.", show_alert=True)
            return
        bps = await _company_products(session, cid)
        have = {x.product_key for x in bps}
        remaining = [k for k in BR.company_products(co.company_key) if k not in have]
        if not remaining:
            await safe_answer(callback, "🎉 ه��ه‌ی محصولاتِ این شرکت باز شده.", show_alert=True)
            return
        cost = BR.expansion_upgrade_cost(len(bps))
        lines = [
            "🏗️ <b>بازکردنِ محصولِ جدید</b>",
            f"💰 هزینه: <b>{cost:,}</b>$",
            "",
        ]
        for k in remaining:
            p = BR.get_brand_product(k)
            lines.append(f"• {p['name']} — سطح {p['tier']} | قیمتِ پایه {p['base']:,}$")
        await safe_show(callback.message, "\n".join(lines), expand_menu(cid, remaining, uid, page))
    await safe_answer(callback)


@router.callback_query(F.data.startswith("brd:caddp:"))
async def company_add_product(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    uid = callback.from_user.id
    parts = _parts(callback)
    cid, pkey = _int(parts[2], 0), parts[3]
    async with async_session() as session:
        co = await _get_company(session, uid, cid)
        if co is None:
            await safe_answer(callback, "شرکت پیدا نشد.", show_alert=True)
            return
        bps = await _company_products(session, cid)
        if any(x.product_key == pkey for x in bps):
            await safe_answer(callback, "این محصول قبلاً باز شده.", show_alert=True)
            return
        if pkey not in BR.company_products(co.company_key):
            await safe_answer(callback, "این محصول مالِ این شرکت نیست.", show_alert=True)
            return
        cost = BR.expansion_upgrade_cost(len(bps))
        player = await get_player(session, uid)
        if player is None or int(player.cash or 0) < cost:
            await safe_answer(callback, f"💸 پولت کافی نیست. هزینه: {cost:,}$", show_alert=True)
            return
        player.cash = int(player.cash or 0) - cost
        co.expansion_level = len(bps) + 1
        from app.data import leveling as _lv
        _xp_res = {}
        try:   # XP for expanding a brand company's product line
            _xp_res = await _lv.grant_xp(session, player, min(150, max(8, cost // 6000)), source="brand_company_expand")
        except Exception:
            pass
        session.add(BrandProduct(company_id=cid, product_key=pkey, percent=50))
        await session.commit()
        p = BR.get_brand_product(pkey)
        await safe_answer(callback, f"🏗️ {p['name']} باز شد!", show_alert=True)
        co = await _get_company(session, uid, cid)
        await _render_company(session, callback.message, uid, co)


@router.callback_query(F.data.startswith("brd:cup:"))
async def company_upgrade(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    uid = callback.from_user.id
    parts = _parts(callback)
    track, cid = parts[2], _int(parts[3], 0)
    async with async_session() as session:
        co = await _get_company(session, uid, cid)
        if co is None:
            await safe_answer(callback, "شرکت پیدا نشد.", show_alert=True)
            return
        bps = await _company_products(session, cid)
        max_prod = len(BR.company_products(co.company_key))
        if track == "cap":
            # 🆕 v1.7.8.17 — ظرفیتِ شرکت دیگر مستقیم ارتقا نمی‌شود
            await safe_answer(
                callback,
                "📦 انبارِ شرکت دیگر مستقیم ارتقا نمی‌شود — ظرف��تش جمعِ انبارِ م��صولاتش است."
                " از صفحهٔ هر محصول، انبارِ همان محصول را ارتقا بده.",
                show_alert=True,
            )
            return
        elif track == "spd":
            if co.speed_level >= BR.MAX_TRACK_LEVEL:
                await safe_answer(callback, "⚡ سرعت به س��حِ نهایی رسیده.", show_alert=True)
                return
            cost, label = BR.speed_upgrade_cost(co.speed_level), "⚡ سرعت"
        elif track == "line":
            if co.line_level >= min(BR.MAX_TRACK_LEVEL, max_prod):
                await safe_answer(callback, "🧵 خطِ تولید به سطحِ نهایی رسیده.", show_alert=True)
                return
            cost, label = BR.line_upgrade_cost(co.line_level), "🧵 خطِ تولید"
        else:
            await safe_answer(callback, "مسیرِ نامعتبر.", show_alert=True)
            return
        player = await get_player(session, uid)
        if player is None or int(player.cash or 0) < cost:
            await safe_answer(callback, f"💸 پولت کافی نیست. هزینه: {cost:,}$", show_alert=True)
            return
        player.cash = int(player.cash or 0) - cost
        if track == "cap":
            co.capacity_level = int(co.capacity_level or 1) + 1
            new_lv = co.capacity_level
        elif track == "spd":
            co.speed_level = int(co.speed_level or 1) + 1
            new_lv = co.speed_level
        else:
            co.line_level = int(co.line_level or 1) + 1
            new_lv = co.line_level
        from app.data import leveling as _lv
        _xp_res = {}
        try:   # XP for company track upgrades
            _xp_res = await _lv.grant_xp(session, player, (20 + 10 * int(new_lv)) // 2, source="brand_company_upgrade")
        except Exception:
            pass
        await session.commit()
        await safe_answer(callback, f"⬆️ {label} به سطح {new_lv} رسید.", show_alert=True)
        co = await _get_company(session, uid, cid)
        await _render_company(session, callback.message, uid, co)


# ===========================================================================
# 🆕 v1.7.8.17 — ارتقایِ انبارِ محصول + صفِ ساختِ شرکت
# ===========================================================================
@router.callback_query(F.data.startswith("brd:pcap:"))
async def product_capacity_upgrade(callback: CallbackQuery) -> None:
    """ارتقایِ انبارِ اختصاصیِ یک محصولِ برند (حداکثر ۱۰ سطح)."""
    if not await ensure_owner(callback):
        return
    uid = callback.from_user.id
    parts = _parts(callback)
    cid, pkey = _int(parts[2], 0), parts[3]
    async with async_session() as session:
        co = await _get_company(session, uid, cid)
        if co is None:
            await safe_answer(callback, "شرکت پیدا نشد.", show_alert=True)
            return
        bp = await _get_bp(session, cid, pkey)
        if bp is None:
            await safe_answer(callback, "محصول پیدا نشد.", show_alert=True)
            return
        lvl = int(getattr(bp, "capacity_level", 1) or 1)
        if lvl >= BR.PRODUCT_CAP_MAX_LEVEL:
            await safe_answer(
                callback,
                f"📦 انبارِ این محصول در بالاترین سطح است ({BR.PRODUCT_CAP_MAX:,} واحد).",
                show_alert=True,
            )
            return
        cost = BR.product_capacity_upgrade_cost(lvl)
        player = await get_player(session, uid)
        if player is None or int(player.cash or 0) < cost:
            await safe_answer(callback, f"💸 پولت کافی نیست. هزینه: {cost:,}$", show_alert=True)
            return
        player.cash = int(player.cash or 0) - cost
        bp.capacity_level = lvl + 1
        new_cap = BR.product_capacity(bp.capacity_level)
        from app.data import leveling as _lv
        _xp_res = {}
        try:   # XP for upgrading a brand product warehouse
            _xp_res = await _lv.grant_xp(session, player, (20 + 10 * (lvl + 1)) // 2, source="brand_company_upgrade")
        except Exception:
            pass
        # جایِ تازه یعنی صف می‌تواند شروع کند
        await _try_start_queue(session, co)
        await session.commit()
        await safe_answer(
            callback,
            f"⬆️ انبارِ این محصول سطح {lvl + 1} شد — ظرفیت: {new_cap:,} واحد.",
            show_alert=True,
        )
        co = await _get_company(session, uid, cid)
        bp = await _get_bp(session, cid, pkey)
        await _render_product(session, callback.message, uid, co, bp)


@router.callback_query(F.data.startswith("brd:cqpct:"))
async def company_queue_percent(callback: CallbackQuery) -> None:
    """انتخابِ حجمِ سفارشی که به صفِ ساخت می‌رود."""
    if not await ensure_owner(callback):
        return
    uid = callback.from_user.id
    parts = _parts(callback)
    cid, pkey = _int(parts[2], 0), parts[3]
    async with async_session() as session:
        co = await _get_company(session, uid, cid)
        if co is None:
            await safe_answer(callback, "شرکت پیدا نشد.", show_alert=True)
            return
        bp = await _get_bp(session, cid, pkey)
        if bp is None:
            await safe_answer(callback, "محصول پیدا نشد.", show_alert=True)
            return
        player = await get_player(session, uid)
        cap = _p_cap(bp)
        unit_cost = BR.unit_raw_cost(pkey, co.speed_level)
        qrows = await _queue_for_bp(session, bp.id)
        p = BR.get_brand_product(pkey) or {"name": pkey}
        lines = [
            f"🧾 <b>صفِ ساخت — {p['name']}</b>",
            f"💵 موجودی: <b>{int(player.cash or 0):,}</b> دلار",
            "",
            f"📦 انبارِ این محصول: <b>{int(bp.stock or 0):,}</b>/{cap:,} واحد",
            f"🔳 حجمِ خالی: <b>{_bp_room(bp):,}</b> واحد",
            f"🧾 سفارش‌هایِ این محصول در صف: <b>{len(qrows)}</b>",
            f"🧾 هزینه‌ی موادِ هر واحد: <b>{unit_cost:,}</b>$",
            "",
            "هر دکمه = درصدی از <b>کلِ ظرفیتِ انبارِ این محصول</b>:",
        ]
        for pct in BR.PERCENT_STEPS:
            units = max(1, BR.units_for_percent(cap, pct))
            lines.append(
                f"• {pct}٪ ← {units:,} واحد ({BR.raw_cost_for_units(pkey, units, co.speed_level):,}$)"
            )
        lines.append("")
        lines.append(
            "💡 پولِ مواد همین حالا کسر می‌شود؛ با حذفِ سفارش <b>کامل</b> برمی‌گردد."
        )
        lines.append(
            "به‌محضِ خالی‌شدنِ انبار (فروش یا انتقال به انبارِ اصلی) خودکار شروع می‌شود."
        )
        await safe_show(callback.message, "\n".join(lines), queue_percent_menu(cid, pkey, uid))
    await safe_answer(callback)


@router.callback_query(F.data.startswith("brd:cqadd:"))
async def company_queue_add(callback: CallbackQuery) -> None:
    """ثبتِ یک سفارش در صفِ ساخ�� (پولِ مواد همین جا کسر می‌شود)."""
    if not await ensure_owner(callback):
        return
    uid = callback.from_user.id
    parts = _parts(callback)
    cid, pkey, pct = _int(parts[2], 0), parts[3], _int(parts[4], 50)
    async with async_session() as session:
        co = await _get_company(session, uid, cid)
        if co is None:
            await safe_answer(callback, "شرکت پیدا نشد.", show_alert=True)
            return
        bp = await _get_bp(session, cid, pkey)
        if bp is None:
            await safe_answer(callback, "محصول پیدا نشد.", show_alert=True)
            return
        rows = await _queue_rows(session, cid)
        if len(rows) >= BR.QUEUE_MAX:
            await safe_answer(
                callback,
                f"🧾 صفِ ساخت پر است ({BR.QUEUE_MAX} سفارش). اول بخشی از صف را خالی کن.",
                show_alert=True,
            )
            return
        pct = BR.normalize_percent(pct)
        units = max(1, BR.units_for_percent(_p_cap(bp), pct))
        cost = BR.raw_cost_for_units(pkey, units, co.speed_level)
        player = await get_player(session, uid)
        if player is None or int(player.cash or 0) < cost:
            await safe_answer(
                callback,
                f"💸 برای {units:,} واحد، {cost:,}$ موادِ اولیه لازم است! درصدِ کمتری انتخاب کن.",
                show_alert=True,
            )
            return
        player.cash = int(player.cash or 0) - cost
        session.add(BrandQueueItem(
            company_id=cid,
            bp_id=bp.id,
            product_key=pkey,
            units=units,
            percent=pct,
            paid_cost=cost,
        ))
        await session.flush()
        started, q_units = await _try_start_queue(session, co)
        await session.commit()
        if started:
            msg = f"🧾 {units:,} واحد ثبت شد و {q_units:,} واحدش فوری شروع شد — مواد: {cost:,}$"
        else:
            msg = (
                f"🧾 {units:,} واحد به صفِ ساخت رفت — مواد: {cost:,}$."
                + chr(10) + "به‌محضِ بازشدنِ جا خودکار شروع می‌شود."
            )
        await safe_answer(callback, msg, show_alert=True)
        co = await _get_company(session, uid, cid)
        bp = await _get_bp(session, cid, pkey)
        await _render_product(session, callback.message, uid, co, bp)


async def _render_queue(session, message: Message, uid: int, company, page: int = 0) -> None:
    """رندرِ صفحهٔ صفِ ساختِ یک شرکت."""
    player = await get_player(session, uid)
    items = await _queue_rows(session, company.id)
    bps = await _company_products(session, company.id)
    by_id = {bp.id: bp for bp in bps}
    info = BR.get_company(company.company_key) or {"name": company.company_key}
    lines = [
        f"🧾 <b>صفِ ساخت — {company.title or info['name']}</b>",
        f"💵 موجودی: <b>{int(player.cash or 0):,}</b> دلار",
        "",
    ]
    if not items:
        lines.append("صف خالی است.")
        lines.append("")
        lines.append(
            "اگر انبارِ محصولی پر بود، از صفحهٔ همان محصول «🧾 افزودن به صفِ ساخت» را بزن."
        )
        lines.append("سفارش‌ها به‌محضِ خالی‌شدنِ انبار خودکار شروع می‌شوند.")
    else:
        total = sum(int(getattr(it, "units", 0) or 0) for it in items)
        held = sum(max(0, int(getattr(it, "paid_cost", 0) or 0)) for it in items)
        lines.append(f"📋 {len(items)} سفارش | مجموعاً <b>{total:,}</b> واحد منتظر")
        lines.append(f"🧾 موادِ پرداخت‌شده: <b>{held:,}</b>$")
        lines.append("")
        for i, it in enumerate(items, 1):
            p = BR.get_brand_product(it.product_key) or {"name": it.product_key}
            bp = by_id.get(int(getattr(it, "bp_id", 0) or 0))
            if bp is None:
                st = "⚠️ محصول حذف شده"
            elif _free_slot(bp) is None:
                st = f"⏳ هر {_slots_count()} خطِ این محصول مشغول است"
            elif _bp_room(bp) > 0:
                st = "▶️ آمادهٔ شروع"
            else:
                st = "⏸️ منتظرِ خالی‌شدنِ انبار"
            lines.append(f"{i}. {p['name']} — {int(getattr(it, 'units', 0) or 0):,} واحد | {st}")
        lines.append("")
        lines.append("💡 با حذفِ سفارش، پولِ موادِ آن <b>کامل</b> برمی‌گردد.")
    await safe_show(message, "\n".join(lines), company_queue_menu(company.id, items, uid, page))


@router.callback_query(F.data.startswith("brd:cq:") | F.data.startswith("brd:cqpg:"))
async def company_queue_home(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    uid = callback.from_user.id
    parts = _parts(callback)
    cid = _int(parts[2], 0)
    page = _int(parts[3], 0) if len(parts) > 3 else 0
    async with async_session() as session:
        co = await _get_company(session, uid, cid)
        if co is None:
            await safe_answer(callback, "شرکت پیدا نشد.", show_alert=True)
            return
        await _render_queue(session, callback.message, uid, co, page)
    await safe_answer(callback)


@router.callback_query(F.data.startswith("brd:cqrun:"))
async def company_queue_run(callback: CallbackQuery) -> None:
    """شروعِ دستیِ هر چه از صف که الان جا دارد."""
    if not await ensure_owner(callback):
        return
    uid = callback.from_user.id
    cid = _int(_parts(callback)[2], 0)
    async with async_session() as session:
        co = await _get_company(session, uid, cid)
        if co is None:
            await safe_answer(callback, "شرکت پیدا نشد.", show_alert=True)
            return
        started, units = await _try_start_queue(session, co)
        if started:
            await session.commit()
            await safe_answer(
                callback,
                f"▶️ {started} سفارش از صف شروع شد ({units:,} واحد).",
                show_alert=True,
            )
        else:
            await safe_answer(
                callback,
                "هنوز جا یا خطِ آزاد نیست. به‌محضِ خالی‌شدنِ انبار، صف خودکار جلو می‌رود.",
                show_alert=True,
            )
        co = await _get_company(session, uid, cid)
        await _render_queue(session, callback.message, uid, co)


@router.callback_query(F.data.startswith("brd:cqdel:"))
async def company_queue_del(callback: CallbackQuery) -> None:
    """حذفِ یک سفارش از صف با بازپرداختِ کاملِ مواد."""
    if not await ensure_owner(callback):
        return
    uid = callback.from_user.id
    item_id = _int(_parts(callback)[2], 0)
    async with async_session() as session:
        it = await session.get(BrandQueueItem, item_id)
        if it is None:
            await safe_answer(callback, "سفارش پیدا نشد.", show_alert=True)
            return
        co = await _get_company(session, uid, int(it.company_id))
        if co is None:
            await safe_answer(callback, "شرکت پیدا نشد.", show_alert=True)
            return
        refund = max(0, int(getattr(it, "paid_cost", 0) or 0))
        player = await get_player(session, uid)
        if player is not None:
            player.cash = int(player.cash or 0) + refund
        await session.delete(it)
        await session.commit()
        await safe_answer(
            callback,
            f"🗑️ سفارش حذف شد — {refund:,}$ بازپرداخت شد.",
            show_alert=True,
        )
        co = await _get_company(session, uid, int(co.id))
        await _render_queue(session, callback.message, uid, co)


@router.callback_query(F.data.startswith("brd:cqclr:"))
async def company_queue_clear(callback: CallbackQuery) -> None:
    """خالی‌کردنِ کلِ صف با بازپرداختِ کامل."""
    if not await ensure_owner(callback):
        return
    uid = callback.from_user.id
    cid = _int(_parts(callback)[2], 0)
    async with async_session() as session:
        co = await _get_company(session, uid, cid)
        if co is None:
            await safe_answer(callback, "شرکت پیدا نشد.", show_alert=True)
            return
        items = await _queue_rows(session, cid)
        n = len(items)
        refund = sum(max(0, int(getattr(it, "paid_cost", 0) or 0)) for it in items)
        for it in items:
            await session.delete(it)
        if n:
            player = await get_player(session, uid)
            if player is not None:
                player.cash = int(player.cash or 0) + refund
            await session.commit()
            await safe_answer(
                callback,
                f"🗑️ {n} سفارش حذف شد — {refund:,}$ بازپرداخت شد.",
                show_alert=True,
            )
        else:
            await safe_answer(callback, "صف از قبل خالی بود.", show_alert=True)
        co = await _get_company(session, uid, cid)
        await _render_queue(session, callback.message, uid, co)


# ===========================================================================
# \U0001f195 هولدینگِ تفریحی
# ===========================================================================
async def _render_holding(session, message: Message, uid: int, page: int = 0) -> None:
    player = await get_player(session, uid)
    owned = await _companies(session, uid)
    if BR.HOLDING_KEY not in owned:
        info = BR.COMPANIES[BR.HOLDING_KEY]
        text = "\n".join([
            "🎡 <b>هولدینگِ تفریحی</b>",
            f"💵 موجودی: <b>{int(player.cash or 0):,}</b> دلار",
            "",
            info["desc"],
            "",
            "مسیر: اول هولدینگ را می‌خری → 🏨 هتل باز می‌شود → بعد ایرلاین، مجتمعِ تفریحی، صنعتِ سرگرمی و رسانه را انتخاب می‌کنی.",
            f"💰 هزینه‌ی خرید: <b>{info['cost']:,}</b>$",
        ])
        await safe_show(message, text, holding_buy_menu(uid))
        return
    hold = owned[BR.HOLDING_KEY]
    units = await _holding_units(session, uid)
    total = BR.holding_total_income([(u.unit_key, _tracks(u)) for u in units.values()])
    anchor = min([u.last_collected_at or u.created_at or datetime.utcnow() for u in units.values()], default=datetime.utcnow())
    hours = min(HOLDING_MAX_OFFLINE_HOURS, max(0.0, (datetime.utcnow() - anchor).total_seconds() / 3600.0))
    lines = [
        f"🎡 <b>{hold.title or BR.COMPANIES[BR.HOLDING_KEY]['name']}</b>",
        f"💵 موجودی: <b>{int(player.cash or 0):,}</b> دلار",
        "",
        "این بخش محصول تولید نمی‌کند — درآمدِ خودکار دارد و فقط ارتقاش می‌دهی.",
        f"💰 درآمدِ کل: <b>{total:,}</b>$/ساعت",
        f"🕐 درآمدِ جمع‌نشده: <b>{int(total * hours):,}</b>$ ({hours:.1f} ساعت — سقف {HOLDING_MAX_OFFLINE_HOURS} ساعت)",
        "",
        "<b>واحدها:</b>",
    ]
    for key in BR.HOLDING_UNIT_ORDER:
        info = BR.HOLDING_UNITS[key]
        u = units.get(key)
        if u is None:
            tag = "🏨 پا��ه" if info["base"] else f"{info['cost']:,}$"
            lines.append(f"➕ {info['name']} — {tag}")
        else:
            tr = _tracks(u)
            lv = sum(tr.values())
            lines.append(
                f"✅ {u.title or info['name']} — 💰 {BR.unit_income_per_hour(key, tr):,}$/ساعت | ⬆️ {lv} ارتقا"
            )
    await safe_show(message, "\n".join(lines), holding_menu(units, uid, page))


@router.callback_query(F.data.startswith("brd:hold") | F.data.startswith("brd:holdp:"))
async def holding_home(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    uid = callback.from_user.id
    parts = _parts(callback)
    page = _int(parts[2], 0) if len(parts) > 2 else 0
    async with async_session() as session:
        brand = await BS.get_brand(session, uid)
        if brand is None:
            await safe_answer(callback, "اول یک برند بساز.", show_alert=True)
            return
        await _render_holding(session, callback.message, uid, page)
    await safe_answer(callback)


@router.callback_query(F.data.startswith("brd:hbuy:"))
async def holding_buy_unit(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    uid = callback.from_user.id
    ukey = _parts(callback)[2]
    info = BR.get_holding_unit(ukey)
    if not info:
        await safe_answer(callback, "واحدِ نامعتبر.", show_alert=True)
        return
    async with async_session() as session:
        owned = await _companies(session, uid)
        if BR.HOLDING_KEY not in owned:
            await safe_answer(callback, "اول خودِ هولدینگ را بخر.", show_alert=True)
            return
        units = await _holding_units(session, uid)
        if ukey in units:
            await safe_answer(callback, "این واحد را قبلاً داری.", show_alert=True)
            return
        if not info["base"] and "hotel" not in units:
            await safe_answer(callback, "🏨 اول باید هتل را داشته باشی.", show_alert=True)
            return
        cost = int(info["cost"])
        player = await get_player(session, uid)
        if cost and (player is None or int(player.cash or 0) < cost):
            await safe_answer(callback, f"💸 پولت کافی نیست. هزینه: {cost:,}$", show_alert=True)
            return
        if cost:
            player.cash = int(player.cash or 0) - cost
        from app.data import leveling as _lv
        _xp_res = {}
        try:   # XP for buying a holding unit
            _xp_res = await _lv.grant_xp(session, player, (max(20, cost // 500) if cost else 30) // 2, source="holding_buy")
        except Exception:
            pass
        session.add(HoldingUnit(
            owner_id=uid,
            unit_key=ukey,
            title=info["default_name"],
            tracks="{}",
            last_collected_at=datetime.utcnow(),
        ))
        await session.commit()
        await safe_answer(callback, f"🎉 {info['name']} به هولدینگ اضافه شد!", show_alert=True)
        await _render_holding(session, callback.message, uid)


async def _get_unit(session, uid: int, unit_id: int):
    u = await session.get(HoldingUnit, unit_id)
    if u is None or int(u.owner_id) != int(uid):
        return None
    return u


async def _render_unit(session, message: Message, uid: int, unit, page: int = 0) -> None:
    player = await get_player(session, uid)
    info = BR.HOLDING_UNITS.get(unit.unit_key) or {"name": unit.unit_key, "tracks": {}}
    tr = _tracks(unit)
    lines = [
        f"{info['name']} — <b>{unit.title or info['name']}</b>",
        f"💵 موجودی: <b>{int(player.cash or 0):,}</b> دلار",
        "",
        f"💰 درآمدِ فعلی: <b>{BR.unit_income_per_hour(unit.unit_key, tr):,}</b>$/ساعت",
        f"📈 درآمدِ پایه: {int(info.get('income', 0)):,}$/ساعت",
        "",
        "<b>مسیرهای ارتقا:</b>",
    ]
    for tkey, t in (info.get("tracks") or {}).items():
        lv = int(tr.get(tkey, 0) or 0)
        lines.append(f"• {t['name']} — سطح {lv}/{BR.HOLDING_TRACK_MAX} (هر سطح +{int(t['gain'] * 100)}٪ درآمد)")
    await safe_show(message, "\n".join(lines), holding_unit_menu(unit, tr, uid, page))


@router.callback_query(F.data.startswith("brd:hu:") | F.data.startswith("brd:hup:"))
async def holding_unit_home(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    uid = callback.from_user.id
    parts = _parts(callback)
    uid_unit = _int(parts[2], 0)
    page = _int(parts[3], 0) if len(parts) > 3 else 0
    async with async_session() as session:
        unit = await _get_unit(session, uid, uid_unit)
        if unit is None:
            await safe_answer(callback, "واحد پیدا نشد.", show_alert=True)
            return
        await _render_unit(session, callback.message, uid, unit, page)
    await safe_answer(callback)


@router.callback_query(F.data.startswith("brd:ht:"))
async def holding_track_upgrade(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    uid = callback.from_user.id
    parts = _parts(callback)
    unit_id, tkey = _int(parts[2], 0), parts[3]
    async with async_session() as session:
        unit = await _get_unit(session, uid, unit_id)
        if unit is None:
            await safe_answer(callback, "واحد پیدا نشد.", show_alert=True)
            return
        t = BR.unit_track(unit.unit_key, tkey)
        if not t:
            await safe_answer(callback, "مسیرِ نامعتبر.", show_alert=True)
            return
        tr = _tracks(unit)
        lv = int(tr.get(tkey, 0) or 0)
        if lv >= BR.HOLDING_TRACK_MAX:
            await safe_answer(callback, "✅ این مسیر به سطحِ نهایی رسیده.", show_alert=True)
            return
        cost = BR.unit_track_cost(unit.unit_key, tkey, lv)
        player = await get_player(session, uid)
        if player is None or int(player.cash or 0) < cost:
            await safe_answer(callback, f"💸 پولت کافی نیست. هزینه: {cost:,}$", show_alert=True)
            return
        player.cash = int(player.cash or 0) - cost
        tr[tkey] = lv + 1
        unit.tracks = json.dumps(tr)
        from app.data import leveling as _lv
        _xp_res = {}
        try:   # XP for holding track upgrades
            _xp_res = await _lv.grant_xp(session, player, (20 + 10 * (lv + 1)) // 2, source="holding_track_upgrade")
        except Exception:
            pass
        await session.commit()
        await safe_answer(callback, 
            f"⬆️ {t['name']} به سطح {lv + 1} رسید — درآمدِ جدید: {BR.unit_income_per_hour(unit.unit_key, tr):,}$/ساعت",
            show_alert=True,
        )
        unit = await _get_unit(session, uid, unit_id)
        await _render_unit(session, callback.message, uid, unit)


@router.callback_query(F.data.startswith("brd:hcol"))
async def holding_collect(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    uid = callback.from_user.id
    async with async_session() as session:
        units = await _holding_units(session, uid)
        if not units:
            await safe_answer(callback, "هنوز واحدی نداری.", show_alert=True)
            return
        now = datetime.utcnow()
        total = 0
        for u in units.values():
            anchor = u.last_collected_at or u.created_at or now
            hours = min(HOLDING_MAX_OFFLINE_HOURS, max(0.0, (now - anchor).total_seconds() / 3600.0))
            total += int(BR.unit_income_per_hour(u.unit_key, _tracks(u)) * hours)
            u.last_collected_at = now
        if total <= 0:
            await safe_answer(callback, "🕐 هنوز درآمدی جمع نشده.", show_alert=True)
            return
        # بونس فقط شهرت برند (نه سطح)
        try:
            brand = await BS.get_brand(session, uid)
            rep_pct = (await BS.reputation_bonus_pct(session, int(getattr(brand, "reputation", 0) or 0))) if brand else 0
            if rep_pct:
                total = int(round(total * (100 + rep_pct) / 100))
        except Exception:
            pass
        try:
            from app.services import referral_service
            total = int(total * (1 + (await referral_service.bonus_pct(session, uid)) / 100))
        except Exception:
            pass
        from app.services.bonus_breakdown import income_breakdown, append_note
        br = await income_breakdown(session, uid, int(total))
        total = int(br["total"])
        player = await get_player(session, uid)
        player.cash = int(player.cash or 0) + total
        await session.commit()
        await safe_answer(callback, append_note(f"💰 +{total:,}$ از هولدینگ دریافت شد.", br.get("note") or ""), show_alert=True)
        await _render_holding(session, callback.message, uid)


@router.callback_query(F.data.startswith("brd:hmax") | F.data.startswith("brd:wait"))
async def brand_noop(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    await safe_answer(callback, "ℹ️ فعلاً کاری نمی‌توان کرد.", show_alert=False)


# ===========================================================================
# \U0001f195 نام‌گذاری / تغییرِ نام
# ===========================================================================
_RENAME_LABEL = {
    "brand": "🏷️ نامِ جدیدِ برند",
    "co": "🏢 نامِ جدیدِ شرکت",
    "hold": "🎡 نامِ جدیدِ هولدینگ",
    "hu": "🏨 نامِ جدیدِ این واحد",
}


@router.callback_query(F.data.startswith("brd:rn:"))
async def rename_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not await ensure_owner(callback):
        return
    uid = callback.from_user.id
    parts = _parts(callback)
    kind, target = parts[2], _int(parts[3], 0)
    if kind not in _RENAME_LABEL:
        await safe_answer(callback, "نوعِ نامعتبر.", show_alert=True)
        return
    await state.set_state(BrandStates.renaming)
    await state.update_data(rename_kind=kind, rename_id=target)
    await callback.message.answer(
        f"✏️ {_RENAME_LABEL[kind]} را بفرست (حداکثر ۴۸ کاراکتر)." + CANCEL_HINT,
    )
    await safe_answer(callback)


@router.message(BrandStates.renaming)
async def rename_apply(message: Message, state: FSMContext) -> None:
    if await handle_cancel_word(message, state):
        return
    data = await state.get_data()
    await state.clear()
    kind = data.get("rename_kind")
    target = _int(data.get("rename_id"), 0)
    uid = message.from_user.id
    name = (message.text or "").strip()[:48]
    if not name:
        await message.reply("نا��ِ معتبر بفرست.")
        return
    async with async_session() as session:
        if kind == "brand":
            brand = await BS.get_brand(session, uid)
            if brand is None:
                await message.reply("برندی پیدا نشد.")
                return
            brand.name = name
            await session.commit()
            await message.reply(f"✅ نامِ برند شد: <b>{name}</b>")
            await _show_home(message, uid)
            return
        if kind == "co":
            co = await _get_company(session, uid, target)
            if co is None:
                await message.reply("شرکت پیدا نشد.")
                return
            co.title = name
            await session.commit()
            await message.reply(f"✅ نامِ شرکت شد: <b>{name}</b>")
            co = await _get_company(session, uid, target)
            await _render_company(session, message, uid, co)
            return
        if kind == "hold":
            owned = await _companies(session, uid)
            hold = owned.get(BR.HOLDING_KEY)
            if hold is None:
                await message.reply("هولدینگ پیدا نشد.")
                return
            hold.title = name
            await session.commit()
            await message.reply(f"✅ نامِ هولدینگ شد: <b>{name}</b>")
            await _render_holding(session, message, uid)
            return
        if kind == "hu":
            unit = await _get_unit(session, uid, target)
            if unit is None:
                await message.reply("واحد پیدا نشد.")
                return
            unit.title = name
            await session.commit()
            await message.reply(f"✅ نامِ این واحد شد: <b>{name}</b>")
            unit = await _get_unit(session, uid, target)
            await _render_unit(session, message, uid, unit)
            return
    await message.reply("نوعِ نامعتبر.")


# --------------------------- v1.7.6 لغو تولید برند ---------------------------
@router.callback_query(F.data.startswith("brd:ccancel:") & ~F.data.startswith("brd:ccancelall"))
async def brand_cancel_one(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    parts = _parts(callback)
    # brd:ccancel:cid:pkey
    try:
        cid = int(parts[2]); pkey = parts[3]
    except Exception:
        await safe_answer(callback, "نامعتبر", show_alert=True); return
    uid = callback.from_user.id
    async with async_session() as session:
        co = await session.get(BrandCompany, cid)
        if co is None or int(co.owner_id) != uid:
            await safe_answer(callback, "شرکت پیدا نشد.", show_alert=True); return
        bps = await _company_products(session, cid)
        bp = next((x for x in bps if x.product_key == pkey), None)
        # 🆕 v1.7.8.18 — همهٔ خطوطِ فعالِ این محصول لغو می‌شوند
        busy = _busy_slots(bp) if bp is not None else []
        if bp is None or not busy:
            await safe_answer(callback, "تولیدی در جریان نیست.", show_alert=True); return
        player = await get_player(session, uid)
        # بازپرداختِ ۵۰٪ از همان مبلغی که هنگامِ شروعِ تولید واقعاً کم شده است.
        # هشدار: "raw_cost" در دادهٔ محصول هزینهٔ یک «دسته» (batch) است، نه یک واحد.
        # پس باید از همان تابعِ شروعِ تولید استفاده شود، وگرنه بازپرداخت
        # به‌اندازهٔ batch برابر می‌شود (باگِ چاپِ پول).
        refund = 0
        for _s in busy:
            units = int(_sg(bp, _s, "pending_units", 0) or 0)
            paid = int(BR.raw_cost_for_units(pkey, units, co.speed_level))
            refund += max(0, paid // 2)
            # موجودی ناپدید نشود: pending از بین می‌رود ولی stock دست نمی‌خورد
            _slot_clear(bp, _s)
        if player is not None and refund:
            player.cash = int(player.cash or 0) + refund
        await session.commit()
    await safe_answer(
        callback,
        f"🛑 {len(busy)} خطِ تولید لغو شد. بازپرداخت: {refund:,}$",
        show_alert=True,
    )
    async with async_session() as session:
        co = await _get_company(session, uid, cid)
        bp = await _get_bp(session, cid, pkey)
        if co is not None and bp is not None:
            await _render_product(session, callback.message, uid, co, bp)


@router.callback_query(F.data.startswith("brd:ccancelall:"))
async def brand_cancel_all(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    parts = _parts(callback)
    cid = int(parts[2]); uid = callback.from_user.id
    async with async_session() as session:
        co = await session.get(BrandCompany, cid)
        if co is None or int(co.owner_id) != uid:
            await safe_answer(callback, "شرکت پیدا نشد.", show_alert=True); return
        player = await get_player(session, uid)
        bps = await _company_products(session, cid)
        n=0; refund=0
        for bp in bps:
            # 🆕 v1.7.8.18 — هر دو خطِ هر محصول
            for _s in _busy_slots(bp):
                units = int(_sg(bp, _s, "pending_units", 0) or 0)
                # ۵۰٪ از همان مبلغِ پرداخت‌شده (raw_cost هزینهٔ دسته است، نه واحد)
                paid = int(BR.raw_cost_for_units(bp.product_key, units, co.speed_level))
                refund += max(0, paid // 2)
                _slot_clear(bp, _s); n+=1
        if player is not None and refund:
            player.cash=int(player.cash or 0)+refund
        if n:
            await session.commit()
    await safe_answer(callback, f"🛑 {n} خط لغو شد. بازپرداخت: {refund:,}$" if n else "خط فعالی نبود.", show_alert=True)
    async with async_session() as session:
        co = await _get_company(session, uid, cid)
        if co is not None:
            await _render_company(session, callback.message, uid, co)
