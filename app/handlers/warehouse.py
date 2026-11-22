from aiogram import F, Router
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select

from app.database.engine import async_session
from app.models.warehouse import MainWarehouse, WarehouseStock
from app.data.market import get_product
from app.data import warehouse as WH
from app.data import brands as BR
from app.data import branding as BD
from app.handlers.factory import (
    get_factories,
    get_or_refresh_price,
    get_player,
    market_multiplier,
)
from app.handlers.branding import _brand_price
from app.services import branding_service as BS
from app.keyboards.warehouse_menu import (
    warehouse_build_menu,
    warehouse_locked_menu,
    warehouse_menu,
)
from app.keyboards.main_menu import BTN_WAREHOUSE, WORD_WAREHOUSE
from app.utils.ui import ensure_owner, safe_edit, safe_show

router = Router()


async def get_warehouse(session, tg_user_id):
    res = await session.execute(select(MainWarehouse).where(MainWarehouse.tg_user_id == tg_user_id))
    return res.scalar_one_or_none()


async def warehouse_rows(session, warehouse_id):
    res = await session.execute(select(WarehouseStock).where(WarehouseStock.warehouse_id == warehouse_id))
    return list(res.scalars().all())


def _display_name(product_key: str) -> str:
    """🆕 نامِ محصول را از بازار یا از برندها پیدا می‌کند."""
    p = get_product(product_key)
    if p:
        return p["name"]
    bp = BR.get_brand_product(product_key)
    if bp:
        return bp["name"]
    return product_key


async def _resolve_sale(session, player, product_key: str):
    """🆕 قیمتِ فروش برای هر واحد را برمی‌گرداند — از موتورِ قیمت‌گذاریِ بازار یا برند (هر کدام مناسب باشد)."""
    p = get_product(product_key)
    if p is not None:
        mp = await get_or_refresh_price(session, product_key)
        mult = await market_multiplier(session, player.tg_user_id)
        return mp.price, mult
    bp = BR.get_brand_product(product_key)
    if bp is not None:
        mp = await _brand_price(session, product_key)
        brand = await BS.get_brand(session, player.tg_user_id)
        from app.services import branding_service as _BS
        _rep_pct = await _BS.reputation_bonus_pct(session, int(getattr(brand, "reputation", 0) or 0)) if brand else 0
        mult = 1.0 + (_rep_pct / 100.0)
        return mp.price, mult
    return 0, 1.0


async def render_warehouse(session, player):
    factories = await get_factories(session, player.tg_user_id)
    wh = await get_warehouse(session, player.tg_user_id)

    if wh is None:
        if len(factories) < WH.REQUIRED_FACTORIES:
            remain = WH.REQUIRED_FACTORIES - len(factories)
            text = (
                "🏢 <b>انبارِ اصلی</b> 🔒\n\n"
                f"برای ساختِ انبارِ اصلی باید حداقل <b>{WH.REQUIRED_FACTORIES}</b> کارخانه داشته باشی.\n"
                f"اکنون <b>{len(factories)}</b> کارخانه داری — <b>{remain}</b> تای دیگر مانده.\n\n"
                "انبارِ اصلی جایی است که محصولاتِ کارخانه‌هایت را یکجا ذخیره و مدیریت می‌کنی."
            )
            return text, warehouse_locked_menu()
        text = (
            "🏢 <b>انبارِ اصلی</b> ✅\n\n"
            f"💵 موجودی: <b>{player.cash:,}</b> دلار\n"
            f"🏭 کارخانه‌هایت: <b>{len(factories)}</b> (پیش‌نیاز فراهم است)\n\n"
            f"می‌توانی انبارِ اصلی را با <b>{WH.BUILD_COST:,}$</b> بسازی.\n"
            f"ظرفیتِ اولیه: <b>{WH.warehouse_volume(1):,}</b> واحد — امنیت: <b>{WH.warehouse_security(1) * 100:.0f}%</b>"
        )
        return text, warehouse_build_menu(WH.BUILD_COST, player.cash >= WH.BUILD_COST)

    rows = await warehouse_rows(session, wh.id)
    total = sum(r.qty for r in rows)
    vol = WH.warehouse_volume(wh.level)
    sec = WH.warehouse_security(wh.level)
    lines = [
        f"🏢 <b>انبارِ اصلی</b> — سطح {wh.level}/{WH.MAX_LEVEL}",
        f"💵 موجودی: <b>{player.cash:,}</b> دلار",
        f"📦 حجم: <b>{total:,}</b>/{vol:,} واحد",
        f"🛡️ امنیت در برابرِ غارتِ جاسوس: <b>{sec * 100:.0f}%</b>",
        "",
    ]
    sellables = [r for r in rows if r.qty > 0]
    if not sellables:
        lines.append("انبار خالی است. از صفحه‌ی هر محصولِ کارخانه دکمه‌ی «🏢 انتقال به انبارِ اصلی» را بزن.")
    else:
        from app.utils.table import render_table, table_mode_on
        if await table_mode_on("warehouse", session):
            _rows = [[_display_name(r.product_key), f"{int(r.qty):,}"] for r in sellables]
            lines.append("<b>موجودی:</b>")
            lines.append(render_table(["محصول", "موجودی"], _rows))
        else:
            lines.append("<b>موجودی:</b>")
            for r in sellables:
                name = _display_name(r.product_key)
                lines.append(f"• {name} — 📦 {r.qty:,}")
    up_cost = WH.upgrade_cost(wh.level) if wh.level < WH.MAX_LEVEL else None
    return "\n".join(lines), warehouse_menu(sellables, up_cost, wh.level)


# ---------- ورودی‌ها ----------
@router.message(F.text.in_({BTN_WAREHOUSE, WORD_WAREHOUSE, "انبار اصلی"}))   # 🔄 مرحله ۲۱.۱ — تطبیقِ دقیق
async def warehouse_button(message: Message):
    async with async_session() as session:
        player = await get_player(session, message.from_user.id)
        if player is None:
            await message.answer("❗ ابتدا /start را بزن.")
            return
        text, markup = await render_warehouse(session, player)
    await message.answer(text, reply_markup=markup)


@router.callback_query(F.data.startswith("menu:warehouse") | (F.data == "wh:hub"))
async def warehouse_hub_cb(callback: CallbackQuery):
    if not await ensure_owner(callback):
        return
    async with async_session() as session:
        player = await get_player(session, callback.from_user.id)
        if player is None:
            await callback.answer("❗ ابتدا /start را بزن.", show_alert=True)
            return
        text, markup = await render_warehouse(session, player)
    await safe_show(callback.message, text, markup)
    await callback.answer()


@router.callback_query(F.data == "wh:build")
async def warehouse_build(callback: CallbackQuery):
    async with async_session() as session:
        player = await get_player(session, callback.from_user.id)
        if player is None:
            await callback.answer("❗ ابتدا /start را بزن.", show_alert=True)
            return
        factories = await get_factories(session, player.tg_user_id)
        if len(factories) < WH.REQUIRED_FACTORIES:
            await callback.answer(f"⛔ نیازمندِ {WH.REQUIRED_FACTORIES} کارخانه هستی.", show_alert=True)
            return
        existing = await get_warehouse(session, player.tg_user_id)
        if existing is not None:
            await callback.answer("انبارِ اصلی از قبل ساخته شده.", show_alert=True)
            return
        if player.cash < WH.BUILD_COST:
            await callback.answer(f"💸 پول کافی نداری! هزینه: {WH.BUILD_COST:,}$", show_alert=True)
            return
        player.cash -= WH.BUILD_COST
        from app.data import leveling as _lv
        _xp_res = {}
        try:   # Stage 27: XP for building the main warehouse
            _xp_res = await _lv.grant_xp(session, player, 125, source="warehouse_build")
        except Exception:
            pass
        session.add(MainWarehouse(tg_user_id=player.tg_user_id, level=1))
        await session.commit()
        text, markup = await render_warehouse(session, player)
    await safe_edit(callback.message, text, markup)
    await callback.answer("🏢 انبارِ اصلی ساخته شد!" + _lv.xp_note(_xp_res))


@router.callback_query(F.data.startswith("wh:sell:"))
async def warehouse_sell(callback: CallbackQuery):
    product_key = callback.data.split(":")[2]
    async with async_session() as session:
        player = await get_player(session, callback.from_user.id)
        wh = await get_warehouse(session, player.tg_user_id)
        if player is None or wh is None:
            await callback.answer("انبار پیدا نشد.", show_alert=True)
            return
        rows = await warehouse_rows(session, wh.id)
        row = next((r for r in rows if r.product_key == product_key), None)
        if row is None or row.qty <= 0:
            await callback.answer("موجودیِ این ماده خالی است.", show_alert=True)
            return
        price, mult = await _resolve_sale(session, player, product_key)
        units = row.qty
        base_amount = int(units * price * mult)
        from app.services.bonus_breakdown import income_breakdown, append_note
        br = await income_breakdown(session, player.tg_user_id, base_amount)
        amount = int(br["total"])
        player.cash += amount
        from app.data import leveling as _lv
        _xp_res = {}
        try:
            _xp_res = await _lv.grant_xp(session, player, min(200, max(3, units // 4)), source="warehouse_sell")
        except Exception:
            pass
        row.qty = 0
        await session.commit()
        text, markup = await render_warehouse(session, player)
    await safe_edit(callback.message, text, markup)
    await callback.answer(append_note(f"💵 {units:,} واحد فروخته شد: +{amount:,}$" + _lv.xp_note(_xp_res), br.get("note") or ""), show_alert=bool(br.get("note")))


@router.callback_query(F.data == "wh:sellall")
async def warehouse_sell_all(callback: CallbackQuery):
    """🆕 فروشِ یکجای تمامیِ موجودیِ انبارِ اصلی."""
    async with async_session() as session:
        player = await get_player(session, callback.from_user.id)
        wh = await get_warehouse(session, player.tg_user_id)
        if player is None or wh is None:
            await callback.answer("انبار پیدا نشد.", show_alert=True)
            return
        rows = await warehouse_rows(session, wh.id)
        total_units, base_total = 0, 0
        for row in rows:
            if row.qty <= 0:
                continue
            price, mult = await _resolve_sale(session, player, row.product_key)
            units = row.qty
            base_total += int(units * price * mult)
            row.qty = 0
            total_units += units
        if total_units <= 0:
            await callback.answer("انبار خالی است.", show_alert=True)
            return
        from app.services.bonus_breakdown import income_breakdown, append_note
        br = await income_breakdown(session, player.tg_user_id, base_total)
        total_amount = int(br["total"])
        player.cash += total_amount
        from app.data import leveling as _lv
        _xp_res = {}
        try:
            _xp_res = await _lv.grant_xp(session, player, min(400, max(3, total_units // 4)), source="warehouse_sell_all")
        except Exception:
            pass
        await session.commit()
        text, markup = await render_warehouse(session, player)
    await safe_edit(callback.message, text, markup)
    await callback.answer(append_note(f"💵 {total_units:,} واحد فروخته شد: +{total_amount:,}$" + _lv.xp_note(_xp_res), br.get("note") or ""), show_alert=bool(br.get("note")))


@router.callback_query(F.data == "wh:upgrade")
async def warehouse_upgrade(callback: CallbackQuery):
    async with async_session() as session:
        player = await get_player(session, callback.from_user.id)
        wh = await get_warehouse(session, player.tg_user_id)
        if player is None or wh is None:
            await callback.answer("انبار پیدا نشد.", show_alert=True)
            return
        if wh.level >= WH.MAX_LEVEL:
            await callback.answer("انبار در بالاترین سطح است.", show_alert=True)
            return
        cost = WH.upgrade_cost(wh.level)
        if player.cash < cost:
            await callback.answer(f"💸 پول کافی نداری! هزینه: {cost:,}$", show_alert=True)
            return
        player.cash -= cost
        wh.level += 1
        from app.data import leveling as _lv
        _xp_res = {}
        try:   # Stage 27: XP for warehouse upgrades
            _xp_res = await _lv.grant_xp(session, player, (40 + 20 * wh.level) // 2, source="warehouse_upgrade")
        except Exception:
            pass
        await session.commit()
        text, markup = await render_warehouse(session, player)
    await safe_edit(callback.message, text, markup)
    await callback.answer("⬆️ انبار ارتقا یافت؛ حجم و امنیت بیشتر شد." + _lv.xp_note(_xp_res))
