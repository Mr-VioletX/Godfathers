# -*- coding: utf-8 -*-
"""کارخانه‌ها و بازار — مرحله ۲۸.

تغییرات:
  • ۵ کارخانه‌ی یکتا که هر کدام فقط یک‌بار قابلِ ساخت‌اند (دیگر کارخانه #۱/#۲ نداریم).
  • هر کارخانه محصولاتِ مربوط به خودش دارد (سه سطح).
  • تولید با انتخابِ درصدِ حجمِ خالیِ باقی‌مانده‌ی انبار (پله‌ی ۱۰٪).
  • نمودارِ قیمت بر اساسِ کارخانه‌ها گروه‌بندی شده و هر گروه فقط محصولاتِ همان کارخانه را دارد.
"""
import json
from datetime import datetime, timedelta

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select

from app.database.engine import async_session
from app.models.player import Player
from app.models.estate import Estate
from app.models.factory import Factory, FactoryProduct, FactoryQueueItem
from app.models.market import MarketPrice
from app.models.warehouse import MainWarehouse, WarehouseStock
from app.data.estates import aggregate_effects
from app.data.market import (
    HISTORY_LEN,
    advance_price,
    get_product,
    heal_price,
    initial_price,
    price_arrow,
    sparkline,
    ticks_elapsed,
)
from app.data import factories as FAC
from app.data import warehouse as WH
from app.keyboards.market_menu import (
    build_list_menu,
    chart_back_menu,
    expand_list_menu,
    factory_menu,
    factory_prices_menu,
    factory_queue_menu,
    locked_menu,
    market_hub_menu,
    percent_menu,
    prices_menu,
    product_menu,
    queue_percent_menu,
)
from app.keyboards.main_menu import BTN_MARKET, WORD_MARKET

from app.utils.ui import ensure_owner, safe_edit, safe_answer

router = Router()

ONLY_BOT = "🏭 مدیریتِ کارخانه‌ها و بازار فقط داخلِ خودِ ربات ممکن است، نه در گروه."
EMPORIO_KEY = "emporio"
FONDERIA_KEY = "fonderia"


# ---------- کمکی‌ها ----------
async def get_player(session, tg_user_id):
    result = await session.execute(select(Player).where(Player.tg_user_id == tg_user_id))
    return result.scalar_one_or_none()


async def get_estates(session, tg_user_id):
    result = await session.execute(select(Estate).where(Estate.tg_user_id == tg_user_id))
    return list(result.scalars().all())


async def get_factories(session, tg_user_id):
    result = await session.execute(
        select(Factory).where(Factory.tg_user_id == tg_user_id).order_by(Factory.id)
    )
    return list(result.scalars().all())


async def get_factory(session, factory_id, tg_user_id):
    f = await session.get(Factory, factory_id)
    if f is None or f.tg_user_id != tg_user_id:
        return None
    return f


async def get_factory_products(session, factory_id):
    result = await session.execute(
        select(FactoryProduct)
        .where(FactoryProduct.factory_id == factory_id)
        .order_by(FactoryProduct.id)
    )
    return list(result.scalars().all())


async def get_fp(session, fp_id, tg_user_id):
    fp = await session.get(FactoryProduct, fp_id)
    if fp is None:
        return None, None
    factory = await session.get(Factory, fp.factory_id)
    if factory is None or factory.tg_user_id != tg_user_id:
        return None, None
    return fp, factory


async def _user_warehouse(session, tg_user_id):
    res = await session.execute(select(MainWarehouse).where(MainWarehouse.tg_user_id == tg_user_id))
    return res.scalar_one_or_none()


async def _warehouse_rows(session, warehouse_id):
    res = await session.execute(select(WarehouseStock).where(WarehouseStock.warehouse_id == warehouse_id))
    return list(res.scalars().all())


async def _edit(callback, text, markup=None):
    await safe_edit(callback.message, text, markup)


def _built_keys(estates):
    return {e.role_key for e in estates}


def _page_arg(data, index):
    """شماره‌ی صفحه را از انتهای callback_data می‌خواند."""
    parts = data.split(":")
    try:
        return int(parts[index])
    except (IndexError, ValueError):
        return 0


def _factory_key(factory):
    key = getattr(factory, "factory_key", None)
    if key in FAC.FACTORY_TYPES:
        return key
    # سازگاری با ردیف‌های قدیمی: از محصولِ اولیه حدس می‌زنیم
    return FAC.factory_of_product(factory.product_key) or "textile"


def _factory_title(factory):
    return (factory.title or "").strip() or FAC.factory_name(_factory_key(factory))


async def market_multiplier(session, tg_user_id):
    """ضریبِ قیمتِ فروش از افکتِ عمارتِ تجاری (Emporio) — market_pct."""
    estates = await get_estates(session, tg_user_id)
    totals = aggregate_effects([(e.role_key, e.level) for e in estates])
    return 1.0 + totals.get("market_pct", 0.0)


async def _require_emporio(session, tg_user_id):
    estates = await get_estates(session, tg_user_id)
    return EMPORIO_KEY in _built_keys(estates), estates


async def _giga_access(session, uid: int) -> bool:
    """v1.7.8.5 — دسترسی ابرکارخانهٔ دون: گیت ثروت + دسترسی ادمین + ماندگاری برای <۳۰۰ میلیارد."""
    try:
        from app.models.admin import GameNumberSetting
        row = await session.get(GameNumberSetting, f"giga.access.{int(uid)}")
        if row is not None:
            v = str(row.value).strip()
            if v == "1":
                return True
            if v == "0":
                return False
        row = await session.get(GameNumberSetting, f"giga.seen.{int(uid)}")
        if row is not None and str(row.value).strip() == "1":
            return True
    except Exception:
        pass
    try:
        from app.services import worldbank_service as _WBS
        net = int((await _WBS.compute_net_worth(session, uid))["net_worth"])
    except Exception:
        net = 0
    if net < FAC.GIGA_MAX_NET_WORTH:
        if net < FAC.GIGA_PERSIST_BELOW:
            try:
                from app.models.admin import GameNumberSetting
                row = await session.get(GameNumberSetting, f"giga.seen.{int(uid)}")
                if row is None:
                    session.add(GameNumberSetting(key=f"giga.seen.{int(uid)}", value="1"))
                    await session.flush()
            except Exception:
                pass
        return True
    return False


async def get_or_refresh_price(session, product_key):
    """قیمتِ محصول را می‌خوانَد؛ اگر نبود می‌سازد و به‌اندازه‌ی زمانِ گذشته جلو می‌بَرد."""
    now = datetime.utcnow()
    mp = await session.get(MarketPrice, product_key)
    if mp is None:
        price = initial_price(product_key)
        mp = MarketPrice(
            product_key=product_key,
            price=price,
            history=json.dumps([price]),
            updated_at=now,
        )
        session.add(mp)
        await session.commit()
        return mp
    ticks = ticks_elapsed(mp.updated_at, now)
    history = json.loads(mp.history or "[]")
    # v1.7.8.15: اگر بازه‌ی مجازِ محصول در کد عوض شده باشد، قیمتِ قدیمیِ
    # ذخیره‌شده فوراً به بازه‌ی جدید برگردانده می‌شود و منتظرِ تیکِ ساعتی نمی‌مانیم.
    price, history, healed = heal_price(product_key, mp.price, history)
    if ticks > 0:
        price, history = advance_price(product_key, price, history, ticks)
    if healed or ticks > 0:
        mp.price = price
        mp.history = json.dumps(history)
        if ticks > 0:
            mp.updated_at = now
        await session.commit()
    return mp


# ---------- 🆕 v1.7.8.18 — دو خطِ تولیدِ مستقل برایِ هر محصول ----------
# خطِ ۱ = ستون‌هایِ قدیمی (status / started_at / percent / pending_units)
# خطِ ۲ = ستون‌هایِ تازه (status2 / started_at2 / percent2 / pending_units2)
_SLOT_SUFFIX = ("", "2")


def _slots_count() -> int:
    return int(getattr(FAC, "LINES_PER_PRODUCT", 2) or 2)


def _sg(fp, slot, field, default=None):
    return getattr(fp, field + _SLOT_SUFFIX[slot], default)


def _ss(fp, slot, field, value):
    setattr(fp, field + _SLOT_SUFFIX[slot], value)


def _slot_busy(fp, slot) -> bool:
    return str(_sg(fp, slot, "status", "idle") or "idle") == "producing"


def _busy_slots(fp):
    return [s for s in range(_slots_count()) if _slot_busy(fp, s)]


def _free_slots(fp) -> int:
    return max(0, _slots_count() - len(_busy_slots(fp)))


def _free_slot(fp):
    """شمارهٔ اولین خطِ آزادِ این محصول (یا None اگر همه مشغول‌اند)."""
    for s in range(_slots_count()):
        if not _slot_busy(fp, s):
            return s
    return None


def _slot_clear(fp, slot):
    _ss(fp, slot, "status", "idle")
    _ss(fp, slot, "started_at", None)
    _ss(fp, slot, "pending_units", 0)


def _slot_start(fp, slot, units, pct):
    _ss(fp, slot, "status", "producing")
    _ss(fp, slot, "started_at", datetime.utcnow())
    _ss(fp, slot, "pending_units", int(units))
    _ss(fp, slot, "percent", FAC.normalize_percent(pct or FAC.DEFAULT_PERCENT))


def _slot_units(fp, slot, factory=None) -> int:
    if not _slot_busy(fp, slot):
        return 0
    u = int(_sg(fp, slot, "pending_units", 0) or 0)
    if u > 0:
        return u
    if factory is None:
        return 0
    return FAC.batch_output(fp.product_key, factory.capacity_level, factory.line_level)


def _slot_ready(fp, slot, speed_level) -> bool:
    if not _slot_busy(fp, slot):
        return False
    st = _sg(fp, slot, "started_at")
    if st is None:
        return False
    hrs = FAC.effective_produce_hours(fp.product_key, speed_level)
    return datetime.utcnow() >= st + timedelta(hours=hrs)


def _ready_slots(fp, speed_level):
    return [s for s in range(_slots_count()) if _slot_ready(fp, s, speed_level)]


def _slot_remaining(fp, slot, speed_level) -> str:
    st = _sg(fp, slot, "started_at")
    if st is None:
        return "0د"
    hrs = FAC.effective_produce_hours(fp.product_key, speed_level)
    mins = max(0, int((st + timedelta(hours=hrs) - datetime.utcnow()).total_seconds() // 60))
    h, m = divmod(mins, 60)
    return f"{h}س {m}د" if h else f"{m}د"


def _fp_ready(fp, speed_level):
    """دستِ‌کم یکی از خطوطِ این محصول آمادهٔ جمع‌آوری است؟"""
    return bool(_ready_slots(fp, speed_level))


def _fp_remaining(fp, speed_level):
    """نزدیک‌ترین زمانِ آماده‌شدن بینِ خطوطِ فعالِ این محصول."""
    best, best_txt = None, "0د"
    hrs = FAC.effective_produce_hours(fp.product_key, speed_level)
    for s in _busy_slots(fp):
        st = _sg(fp, s, "started_at")
        if st is None:
            continue
        ready_at = st + timedelta(hours=hrs)
        if best is None or ready_at < best:
            best, best_txt = ready_at, _slot_remaining(fp, s, speed_level)
    return best_txt


def _fp_lines_text(fp, factory) -> str:
    """وضعیتِ خط‌به‌خطِ یک محصول برایِ نمایش."""
    busy = _busy_slots(fp)
    if not busy:
        return f"⚪ بی‌کار ({_slots_count()} خطِ آزاد)"
    parts = []
    for s in busy:
        u = _slot_units(fp, s, factory)
        if _slot_ready(fp, s, factory.speed_level):
            parts.append(f"✅ خطِ {s + 1}: آماده ({u:,})")
        else:
            parts.append(
                f"⏳ خطِ {s + 1}: {_slot_remaining(fp, s, factory.speed_level)} ({u:,})"
            )
    free = _free_slots(fp)
    if free:
        parts.append(f"⚪ {free} خطِ آزاد")
    return " | ".join(parts)


def _lines_block_msg(fp) -> str:
    """پیام وقتی همهٔ خطوطِ خودِ این محصول مشغول است."""
    return chr(10).join([
        "🧵 همهٔ خطوطِ تولیدِ این محصول مشغول است!",
        "",
        f"هر محصول {_slots_count()} خطِ تولیدِ مستقل دارد و الان همه پرند.",
        "",
        "یا صبر کن تا یکی آزاد شود، یا سفارش را به «🧾 صفِ ساخت» بسپار.",
    ])


def _reserved_units(rows) -> int:
    """🆕 v1.7.8.16 - واحدهایی که تولیدِ در جریان از انبار رزرو کرده.

    🆕 v1.7.8.18 — مجموعِ همهٔ خطوطِ فعالِ هر محصول.
    """
    total = 0
    for x in rows:
        for s in range(_slots_count()):
            if _slot_busy(x, s):
                total += int(_sg(x, s, "pending_units", 0) or 0)
    return total


def _p_cap(fp) -> int:
    """🆕 v1.7.8.17 — ظرفیتِ انبارِ اختصاصیِ همین محصول."""
    return FAC.product_capacity(getattr(fp, "capacity_level", 1) or 1)


def _p_used(fp, reserve: bool = True) -> int:
    """موجودی + (با reserve) واحدهایِ در حالِ تولیدِ همین محصول (هر دو خط)."""
    used = int(getattr(fp, "stock", 0) or 0)
    if reserve:
        for s in range(_slots_count()):
            if _slot_busy(fp, s):
                used += int(_sg(fp, s, "pending_units", 0) or 0)
    return used


def _fp_room(fp, reserve: bool = True) -> int:
    """🆕 v1.7.8.17 — حجمِ خالیِ انبارِ *خودِ محصول* (نه کلِ کارخانه)."""
    return max(0, _p_cap(fp) - _p_used(fp, reserve))


def _room_block_msg(fp) -> str:
    """🆕 v1.7.8.17 — پیامِ دقیق وقتی انبارِ همین محصول جا ندارد."""
    cap = _p_cap(fp)
    stock = int(getattr(fp, "stock", 0) or 0)
    pend = sum(int(_sg(fp, s, "pending_units", 0) or 0)
               for s in range(_slots_count()) if _slot_busy(fp, s))
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


def _factory_block_msg(factory, fps) -> str:
    """🆕 v1.7.8.17 — پیامِ کلی وقتی هیچ‌کدام از انبارهایِ محصولات جا ندارند."""
    cap = FAC.factory_total_capacity(fps)
    stock = sum(int(getattr(x, "stock", 0) or 0) for x in fps)
    reserved = _reserved_units(fps)
    if reserved > 0:
        return chr(10).join([
            "⏳ جا برای تولیدِ تازه نیست!",
            "",
            f"📦 انبارِ کارخانه: {stock + reserved:,}/{cap:,} واحد",
            f"🏭 {reserved:,} واحد در حالِ تولید است و جا را گرفته.",
            "",
            "جمع‌آوری کن و بفروش، یا سفارش‌ها را ��ه «🧾 صفِ ساخت» بسپار.",
        ])
    return chr(10).join([
        "📦 انبارِ همه‌ی محصولات پر است!",
        "",
        f"📦 انبارِ کارخانه: {stock:,}/{cap:,} واحد",
        "",
        "بفروش یا به انبارِ اصلی منتقل کن، یا انبارِ ��������������حصولات را ارتقا بده.",
    ])


def _free_room(factory, fps, reserve: bool = False):
    """حجمِ خالیِ کلِ کارخانه = جمعِ حجمِ خالیِ انبارِ محصولاتش.

    🆕 v1.7.8.17 — فقط برایِ نمایشِ کلی. گیتِ تولید از `_fp_room`
    استفاده می‌کند، چون هر محصول انبارِ جداگانهٔ خودش را دارد.
    """
    return sum(_fp_room(x, reserve) for x in fps)


def _pending_units(fp, factory):
    """جمعِ واحدهایِ درِ حالِ تولیدِ همهٔ خطوطِ این محصول."""
    return sum(_slot_units(fp, s, factory) for s in range(_slots_count()))


# ---------- 🆕 v1.7.8.17 — صفِ ساختِ کارخانه ----------
async def _queue_rows(session, factory_id):
    """همه‌ی سفارش‌هایِ صفِ یک کارخانه، به‌ترتیبِ ثبت."""
    res = await session.execute(
        select(FactoryQueueItem)
        .where(FactoryQueueItem.factory_id == factory_id)
        .order_by(FactoryQueueItem.id)
    )
    return list(res.scalars().all())


async def _queue_for_fp(session, fp_id):
    """سفارش‌هایِ صفِ مربوط به یک محصول."""
    res = await session.execute(
        select(FactoryQueueItem)
        .where(FactoryQueueItem.fp_id == fp_id)
        .order_by(FactoryQueueItem.id)
    )
    return list(res.scalars().all())


async def _try_start_queue(session, factory, fps=None):
    """هر جا در انبار جا باز شود، سفارش‌هایِ صف را جلو می‌بَرد.

    پولِ موادِ اولیه هنگامِ ثبت در صف کسر شده، پس اینجا دوباره پول
    گرفته نمی‌شود. اگر جا فقط برایِ بخشی از سفارش باشد، همان بخش
    شروع می‌شود و باقی‌مانده (با سهمِ پولِ خودش) در صف می‌ماند.

    تراکنش را commit نمی‌کند؛ این کار بر عهدهٔ صدازننده است.
    """
    items = await _queue_rows(session, factory.id)
    if not items:
        return 0, 0
    if fps is None:
        fps = await get_factory_products(session, factory.id)
    by_id = {fp.id: fp for fp in fps}
    started, units_total = 0, 0
    for it in items:
        fp = by_id.get(int(getattr(it, "fp_id", 0) or 0))
        want = max(0, int(getattr(it, "units", 0) or 0))
        if fp is None or want <= 0:
            await session.delete(it)
            continue
        # 🆕 v1.7.8.18 — گیتِ خط دیگر کلِ کارخانه نیست؛ هر محصول خطوطِ
        # مستقلِ خودش را دارد و تا حدِ جایِ خالیِ انبارِ همان محصول می‌سازد.
        slot = _free_slot(fp)
        if slot is None:
            continue
        room = _fp_room(fp)
        if room <= 0:
            continue
        take = min(want, room)
        _slot_start(fp, slot, take, getattr(it, "percent", None) or FAC.START_ALL_PERCENT)
        started += 1
        units_total += take
        if take >= want:
            await session.delete(it)
        else:
            paid = max(0, int(getattr(it, "paid_cost", 0) or 0))
            it.paid_cost = max(0, paid - (paid * take) // want)
            it.units = want - take
    return started, units_total


# ---------- رندرها ----------
async def render_market_hub(session, player, page=0):
    ok, estates = await _require_emporio(session, player.tg_user_id)
    if not ok:
        return (
            "🔒 <b>بازار و کارخانه‌ها هنوز قفل است</b>\n\n"
            "برای فعال‌شدنِ این بخش باید عمارتِ <b>📈 Emporio</b> (تجاری) را بسازی."
        ), locked_menu()

    factories = await get_factories(session, player.tg_user_id)
    built_types = {_factory_key(f) for f in factories}
    mult = await market_multiplier(session, player.tg_user_id)
    wh = await _user_warehouse(session, player.tg_user_id)

    lines = [
        "🏭 <b>��ارخانه‌ها و بازار</b>",
        f"💵 موجودی: <b>{player.cash:,}</b> دلار",
        f"📈 بونوسِ فروشِ Emporio: <b>+{(mult - 1) * 100:.0f}%</b>",
        f"🏭 کارخانه‌های ساخته‌شده: <b>{len(built_types)}</b> از {FAC.FACTORY_COUNT}",
    ]
    if wh is None:
        remain = max(0, WH.REQUIRED_FACTORIES - len(factories))
        if remain > 0:
            lines.append(f"🏢 انبارِ اصلی: 🔒 با {remain} کارخانه‌ی دیگر باز می‌شود")
        else:
            lines.append("🏢 انبارِ اصلی: ✅ آماده‌ی ساخت")
    else:
        lines.append(f"🏢 انبارِ اصلی: ✅ سطح {wh.level}")
    lines.append("")
    if not factories:
        lines.append("هنوز کارخانه‌ای نساخته‌ای. با «🏗️ ساختِ کارخانه» شروع کن.")
    else:
        for f in factories:
            fps = await get_factory_products(session, f.id)
            producing = sum(len(_busy_slots(fp)) for fp in fps)   # 🆕 v1.7.8.18
            stock = sum(fp.stock for fp in fps)
            lines.append(
                f"• {_factory_title(f)} — 🏗️ {len(fps)} محصول | ⚙️ {producing} خط در حالِ تولید | 📦 {stock:,}"
            )
    can_build = len(built_types) < FAC.FACTORY_COUNT
    return "\n".join(lines), market_hub_menu(factories, can_build, page, player.tg_user_id)


async def render_build_list(session, player, page=0):
    ok, estates = await _require_emporio(session, player.tg_user_id)
    if not ok:
        return "🔒 اول عمارتِ Emporio را بساز.", locked_menu()
    built = {_factory_key(f) for f in await get_factories(session, player.tg_user_id)}
    has_fonderia = FONDERIA_KEY in _built_keys(estates)

    lines = [
        "🏗️ <b>ساختِ کارخانه</b>",
        f"💵 موجودی: <b>{player.cash:,}</b> دلار",
        "",
        "در کلِ بازی ۶ کارخانه وجود دارد و هر کدام <b>فقط یک‌بار</b> قابلِ ساخت است.",
        "",
    ]
    items = []
    for key in FAC.FACTORY_ORDER:
        t = FAC.FACTORY_TYPES[key]
        cost = t["build_cost"]
        if key in built:
            lines.append(f"✅ {t['name']} — ساخته شده")
            continue
        needs_fonderia = t["requires"] == FONDERIA_KEY
        buildable = (not needs_fonderia) or has_fonderia
        lock_kind = None
        if key == FAC.GIGA_KEY and not await _giga_access(session, player.tg_user_id):
            buildable = False
            lock_kind = "giga"
        items.append((key, cost, buildable, lock_kind))
        prods = " ، ".join(get_product(k)["name"] for k in FAC.products_for_factory(key))
        if lock_kind == "giga":
            lock = " 🔒 (مخصوص ثروتِ خالصِ زیر ۳۰۰ میلیارد — یا با دسترسیِ ادمین)"
        else:
            lock = "" if buildable else " 🔒 (نیازمندِ عمارتِ Fonderia)"
        lines.append(f"• {t['name']} — {cost:,}$ {lock}")
        lines.append(f"   محصولات: {prods}")
    if not items:
        lines.append("🎉 همه‌ی ۶ کارخانه را ساخته‌ای!")
    return "\n".join(lines), build_list_menu(items, page, player.tg_user_id)


def _factory_costs(factory, fps, fkey):
    unlocked = len(fps)
    max_prod = len(FAC.products_for_factory(fkey))
    line_max = min(FAC.MAX_TRACK_LEVEL, max_prod)
    return {
        "expand": FAC.expansion_upgrade_cost(unlocked) if unlocked < max_prod else None,
        # 🆕 v1.7.8.17 — انبارِ کارخانه دیگر مستقیم ارتقا نمی‌شود؛ از صفحهٔ هر محصول.
        "cap": None,
        "spd": FAC.speed_upgrade_cost(factory.speed_level) if factory.speed_level < FAC.MAX_TRACK_LEVEL else None,
        "line": FAC.line_upgrade_cost(factory.line_level) if factory.line_level < line_max else None,
    }, unlocked < max_prod


async def render_factory_detail(session, player, factory, page=0):
    fkey = _factory_key(factory)
    fps = await get_factory_products(session, factory.id)
    total_stock = sum(fp.stock for fp in fps)
    reserved = _reserved_units(fps)  # 🆕 v1.7.8.16 — تولیدِ در جریان هم جا می‌گیرد
    # 🆕 v1.7.8.17 — ظرفیتِ کارخانه = جمعِ انبارِ محصولاتش
    cap = FAC.factory_total_capacity(fps)
    max_prod = len(FAC.products_for_factory(fkey))
    # 🆕 v1.7.8.18 — هر محصول ۲ خطِ مستقل دارد
    producing = sum(len(_busy_slots(fp)) for fp in fps)
    total_lines = len(fps) * _slots_count()
    ready_map = {}

    lines = [
        f"🏭 <b>{_factory_title(factory)}</b>",
        f"💵 موجودی: <b>{player.cash:,}</b> دلار",
        "",
        f"📦 انبارِ کارخانه: <b>{total_stock + reserved:,}</b>/{cap:,} واحد (جمعِ انبارِ {len(fps)} محصول)"
        + (
            chr(10) + f"   ├ 💰 قابلِ فروش: <b>{total_stock:,}</b> واحد"
            + chr(10) + f"   └ 🏭 در حالِ تولید: <b>{reserved:,}</b> واحد (هنوز قابلِ فروش نیست)"
            if reserved else ""
        ),
        f"🔳 حجمِ خالی: <b>{max(0, cap - total_stock - reserved):,}</b> واحد",
        f"⚡ سرعت: سطح {factory.speed_level} (زمانِ تولید ×{FAC.speed_factor(factory.speed_level):.2f})",
        f"🧵 خطِ تولیدِ همزمان: {producing}/{total_lines} "
        f"({_slots_count()} خط برایِ هر محصول)",
        f"🏗️ محصولاتِ بازشده: {len(fps)}/{max_prod}",
        "",
        "<b>محصولاتِ این کارخانه:</b>",
    ]
    for fp in fps:
        p = get_product(fp.product_key) or {"name": fp.product_key}
        # 🆕 v1.7.8.18 — وضعیتِ دو خطِ هر محصول
        ready_map[fp.id] = _fp_ready(fp, factory.speed_level)
        st = _fp_lines_text(fp, factory)
        stock = f" | 📦 {fp.stock:,}/{_p_cap(fp):,}"   # 🆕 v1.7.8.17
        lines.append(f"• {p['name']} — {st}{stock}")

    costs, can_expand = _factory_costs(factory, fps, fkey)
    qn = len(await _queue_rows(session, factory.id))   # 🆕 v1.7.8.17
    return "\n".join(lines), factory_menu(
        factory, fps, ready_map, can_expand, costs, page, player.tg_user_id, queue_count=qn
    )


async def render_product_detail(session, player, factory, fp):
    p = get_product(fp.product_key) or {"name": fp.product_key, "min": 0, "max": 0}
    mp = await get_or_refresh_price(session, fp.product_key)
    history = json.loads(mp.history or "[]")
    mult = await market_multiplier(session, player.tg_user_id)
    unit_price = mp.price * mult
    sell_value = int(fp.stock * unit_price)
    ready = _fp_ready(fp, factory.speed_level)
    can_start = _free_slot(fp) is not None          # 🆕 v1.7.8.18
    hrs = FAC.effective_produce_hours(fp.product_key, factory.speed_level)
    fps = await get_factory_products(session, factory.id)
    # 🆕 v1.7.8.17 — جا فقط در انبارِ خودِ همین محصول سنجیده می‌شود
    room = _fp_room(fp)
    p_cap = _p_cap(fp)
    p_lvl = int(getattr(fp, "capacity_level", 1) or 1)
    cap_cost = (FAC.product_capacity_upgrade_cost(p_lvl)
                if p_lvl < FAC.PRODUCT_CAP_MAX_LEVEL else None)
    qrows = await _queue_for_fp(session, fp.id)
    unit_cost = FAC.unit_raw_cost(fp.product_key, factory.speed_level)

    lines = [
        f"{p['name']} — {_factory_title(factory)}",
        f"💵 موجودی: <b>{player.cash:,}</b> دلار",
        "",
        f"📈 قیمتِ بازار: <b>{mp.price:,.0f}</b>$ {price_arrow(history)}",
        f"🏦 با بونوسِ Emporio: <b>{unit_price:,.0f}</b>$ / واحد",
        f"🧾 هزینه‌ی موادِ هر واحد: <b>{unit_cost:,}</b>$",
        f"📦 انبارِ این محصول: <b>{fp.stock:,}</b>/{p_cap:,} واحد "
        f"(سطح {p_lvl}/{FAC.PRODUCT_CAP_MAX_LEVEL}) — ≈ {sell_value:,}$"
        + (f"{chr(10)}   └ 🏭 در حالِ تولید: <b>{_pending_units(fp, factory):,}</b> واحد"
           " (جا گرفته، هنوز قابلِ فروش نیست)" if _busy_slots(fp) else ""),
        f"🔳 حجمِ خالیِ انبارِ این محصول: <b>{room:,}</b> واحد"
        + (f"{chr(10)}🧾 صفِ ساخت: <b>{len(qrows)}</b> سفارش "
           f"({sum(int(q.units or 0) for q in qrows):,} واحد منتظر)" if qrows else ""),
        "",
    ]
    # 🆕 v1.7.8.18 — وضعیتِ خط‌به‌خط (هر محصول دو خطِ مستقل دارد)
    lines.append(f"🧵 خطوطِ این محصول ({_slots_count()} خط):")
    for _s in range(_slots_count()):
        if not _slot_busy(fp, _s):
            lines.append(f"   • خطِ {_s + 1}: ⚪ بی‌کار — آمادهٔ شروع")
        elif _slot_ready(fp, _s, factory.speed_level):
            lines.append(
                f"   • خطِ {_s + 1}: ✅ {_slot_units(fp, _s, factory):,} واحد آماده است!"
            )
        else:
            lines.append(
                f"   • خطِ {_s + 1}: ⏳ {_slot_units(fp, _s, factory):,} واحد — "
                f"{_slot_remaining(fp, _s, factory.speed_level)} باقی مانده"
            )
    lines.append(f"⏱️ هر دوره‌ی تولید: {hrs:.1f} ساعت.")
    if can_start and room > 0:
        lines.append(
            "▶️ تا حدِ جایِ خالیِ انبارِ این محصول می‌توانی تولیدِ تازه شروع کنی"
            "، حتی وقتی خطِ دیگر مشغول است."
        )
    wh = await _user_warehouse(session, player.tg_user_id)
    return "\n".join(lines), product_menu(
        fp, ready, sell_value, wh is not None,
        cap_cost=cap_cost, cap_level=p_lvl, queue_count=len(qrows),
        can_start=can_start, busy=bool(_busy_slots(fp)),
    )


# ---------- ورودی از کیبوردِ اصلی ----------
@router.message(F.text.in_({BTN_MARKET, WORD_MARKET, "کارخانه"}))
async def market_button(message: Message):
    async with async_session() as session:
        player = await get_player(session, message.from_user.id)
        if player is None:
            await message.answer("❗ ابتدا /start را بزن.")
            return
        text, markup = await render_market_hub(session, player)
    await message.answer(text, reply_markup=markup)


@router.callback_query(F.data == "ui:noop")
async def ui_noop(callback: CallbackQuery):
    await safe_answer(callback)


@router.callback_query(F.data.startswith("menu:market") | (F.data == "market:hub") | F.data.startswith("market:hubp:"))
async def market_hub_cb(callback: CallbackQuery):
    if not await ensure_owner(callback):
        return
    page = _page_arg(callback.data, 2) if callback.data.startswith("market:hubp:") else 0
    async with async_session() as session:
        player = await get_player(session, callback.from_user.id)
        if player is None:
            await safe_answer(callback, "❗ ابتدا /start را بزن.", show_alert=True)
            return
        text, markup = await render_market_hub(session, player, page)
    await _edit(callback, text, markup)
    await safe_answer(callback)


@router.callback_query((F.data == "factory:build") | F.data.startswith("factory:buildp:"))
async def factory_build_cb(callback: CallbackQuery):
    page = _page_arg(callback.data, 2) if callback.data.startswith("factory:buildp:") else 0
    async with async_session() as session:
        player = await get_player(session, callback.from_user.id)
        if player is None:
            await safe_answer(callback, "❗ ابتدا /start را بزن.", show_alert=True)
            return
        text, markup = await render_build_list(session, player, page)
    await _edit(callback, text, markup)
    await safe_answer(callback)


@router.callback_query(F.data == "factory:locked")
async def factory_locked(callback: CallbackQuery):
    await safe_answer(callback, "🔒 این کارخانه نیازمندِ عمارتِ صنعتی (Fonderia) است.", show_alert=True)


@router.callback_query(F.data == "factory:locked_giga")
async def factory_locked_giga(callback: CallbackQuery):
    await safe_answer(
        callback,
        (
            "🔒 <b>ابرکارخانهٔ دون</b> مخصوص بازیکنانی است که ثروتِ خالص‌شان زیر "
            "<b>۳۰۰ میلیارد</b> است." + chr(10) + chr(10) +
            "اگر بالاتر رفته‌ای، فقط ادمین می‌تواند به تو دسترسیِ ویژه بدهد."
        ),
        show_alert=True,
    )



@router.callback_query(F.data.startswith("factory:new:"))
async def factory_new(callback: CallbackQuery):
    fkey = callback.data.split(":")[2]
    t = FAC.get_factory_type(fkey)
    if t is None:
        await safe_answer(callback, "کارخانه‌ی نامعتبر.", show_alert=True)
        return
    async with async_session() as session:
        player = await get_player(session, callback.from_user.id)
        if player is None:
            await safe_answer(callback, "❗ ابتدا /start را بزن.", show_alert=True)
            return
        ok, estates = await _require_emporio(session, player.tg_user_id)
        if not ok:
            await safe_answer(callback, "⛔ اول عمارتِ Emporio را بساز.", show_alert=True)
            return
        if fkey == FAC.GIGA_KEY and not await _giga_access(session, player.tg_user_id):
            await safe_answer(
                callback,
                "🔒 ابرکارخانهٔ دون مخصوص بازیکنان با ثروتِ خالصِ زیر ۳۰۰ میلیارد است — یا با دسترسیِ ادمین.",
                show_alert=True,
            )
            return
        if t["requires"] == FONDERIA_KEY and FONDERIA_KEY not in _built_keys(estates):
            await safe_answer(callback, "⛔ این کارخانه نیازمندِ عمارتِ صنعتی (Fonderia) است.", show_alert=True)
            return
        factories = await get_factories(session, player.tg_user_id)
        if fkey in {_factory_key(f) for f in factories}:
            await safe_answer(callback, "⛔ این کارخانه یکتاست و قبلاً ساخته‌ای.", show_alert=True)
            return
        cost = t["build_cost"]
        if player.cash < cost:
            await safe_answer(callback, f"💸 پول کافی نداری! هزینه: {cost:,}$", show_alert=True)
            return
        first_product = FAC.products_for_factory(fkey)[0]
        player.cash -= cost
        factory = Factory(
            tg_user_id=player.tg_user_id,
            factory_key=fkey,
            product_key=first_product,
            level=1,
            status="idle",
            stock=0,
            capacity_level=1,
            speed_level=1,
            expansion_level=1,
            line_level=1,
        )
        session.add(factory)
        await session.flush()
        session.add(FactoryProduct(
            factory_id=factory.id,
            product_key=first_product,
            stock=0,
            status="idle",
            percent=FAC.DEFAULT_PERCENT,
            pending_units=0,
        ))
        from app.data import leveling as _lv
        _xp_res = {}
        try:   # XP for building a new factory
            _xp_res = await _lv.grant_xp(session, player, min(250, max(15, cost // 6000)), source="factory_build")
        except Exception:
            pass
        await session.commit()
        text, markup = await render_market_hub(session, player)
    await _edit(callback, text, markup)
    await safe_answer(callback, f"🏭 {t['name']} ساخته شد!")


@router.callback_query(F.data.startswith("factory:view:") | F.data.startswith("factory:page:"))
async def factory_view(callback: CallbackQuery):
    parts = callback.data.split(":")
    factory_id = int(parts[2])
    page = _page_arg(callback.data, 3) if parts[1] == "page" else 0
    async with async_session() as session:
        player = await get_player(session, callback.from_user.id)
        factory = await get_factory(session, factory_id, callback.from_user.id)
        if player is None or factory is None:
            await safe_answer(callback, "کارخانه پیدا نشد.", show_alert=True)
            return
        if _factory_key(factory) == FAC.GIGA_KEY and not await _giga_access(session, callback.from_user.id):
            await safe_answer(
                callback,
                "🔒 دسترسی به ابرکارخانهٔ دون نداری (ثروتِ خالص بالای سقف — نیاز به دسترسیِ ادمین).",
                show_alert=True,
            )
            return
        text, markup = await render_factory_detail(session, player, factory, page)
    await _edit(callback, text, markup)
    await safe_answer(callback)


@router.callback_query(F.data == "factory:wait")
async def factory_wait(callback: CallbackQuery):
    await safe_answer(callback, "هنوز در حالِ تولید است. کمی صبر کن.", show_alert=True)


@router.callback_query(F.data.startswith("factory:expand:") | F.data.startswith("factory:expandp:"))
async def factory_expand(callback: CallbackQuery):
    parts = callback.data.split(":")
    factory_id = int(parts[2])
    page = _page_arg(callback.data, 3) if parts[1] == "expandp" else 0
    async with async_session() as session:
        player = await get_player(session, callback.from_user.id)
        factory = await get_factory(session, factory_id, callback.from_user.id)
        if player is None or factory is None:
            await safe_answer(callback, "کارخانه پیدا نشد.", show_alert=True)
            return
        fkey = _factory_key(factory)
        fps = await get_factory_products(session, factory.id)
        have = {fp.product_key for fp in fps}
        avail = [k for k in FAC.products_for_factory(fkey) if k not in have]
        if not avail:
            await safe_answer(callback, "همه‌ی محصولاتِ این کارخانه باز شده‌اند.", show_alert=True)
            return
        cost = FAC.expansion_upgrade_cost(len(fps))
        lines = [
            f"🏗️ <b>بازکردنِ محصولِ جدید — {_factory_title(factory)}</b>",
            f"💵 موجودی: <b>{player.cash:,}</b> دلار",
            f"💰 هزینه: <b>{cost:,}</b>$",
            "",
        ]
        for k in avail:
            p = get_product(k)
            # v1.7.8.15: به‌جای قیمتِ ثابتِ پایه، قیمتِ زنده‌ی بازار نشان داده می‌شود.
            kmp = await get_or_refresh_price(session, k)
            lines.append(
                f"• {p['name']} — موادِ هر واحد {FAC.unit_raw_cost(k, factory.speed_level):,}$ | "
                f"قیمتِ بازار {kmp.price:,.0f}$ | {p['produce_hours']}س"
            )
    await _edit(callback, "\n".join(lines), expand_list_menu(factory.id, avail, cost, page, player.tg_user_id))
    await safe_answer(callback)


@router.callback_query(F.data.startswith("factory:addprod:"))
async def factory_addprod(callback: CallbackQuery):
    parts = callback.data.split(":")
    factory_id = int(parts[2])
    product_key = parts[3]
    async with async_session() as session:
        player = await get_player(session, callback.from_user.id)
        factory = await get_factory(session, factory_id, callback.from_user.id)
        if player is None or factory is None:
            await safe_answer(callback, "کارخانه پیدا نشد.", show_alert=True)
            return
        fkey = _factory_key(factory)
        if product_key not in FAC.products_for_factory(fkey):
            await safe_answer(callback, "این محصول مربوط به این کارخانه نیست.", show_alert=True)
            return
        fps = await get_factory_products(session, factory.id)
        if product_key in {fp.product_key for fp in fps}:
            await safe_answer(callback, "این محصول از قبل باز شده است.", show_alert=True)
            return
        cost = FAC.expansion_upgrade_cost(len(fps))
        if player.cash < cost:
            await safe_answer(callback, f"💸 پول کافی نداری! هزینه: {cost:,}$", show_alert=True)
            return
        player.cash -= cost
        factory.expansion_level += 1
        from app.data import leveling as _lv
        _xp_res = {}
        try:   # XP for expanding a factory's product line
            _xp_res = await _lv.grant_xp(session, player, min(150, max(8, cost // 6000)), source="factory_expand")
        except Exception:
            pass
        session.add(FactoryProduct(
            factory_id=factory.id,
            product_key=product_key,
            stock=0,
            status="idle",
            percent=FAC.DEFAULT_PERCENT,
            pending_units=0,
        ))
        await session.commit()
        text, markup = await render_factory_detail(session, player, factory)
    await _edit(callback, text, markup)
    await safe_answer(callback, f"🏗️ {get_product(product_key)['name']} باز شد!")


@router.callback_query(F.data.startswith("factory:up:"))
async def factory_upgrade_track(callback: CallbackQuery):
    parts = callback.data.split(":")
    track = parts[2]
    factory_id = int(parts[3])
    async with async_session() as session:
        player = await get_player(session, callback.from_user.id)
        factory = await get_factory(session, factory_id, callback.from_user.id)
        if player is None or factory is None:
            await safe_answer(callback, "کارخانه پیدا نشد.", show_alert=True)
            return
        fkey = _factory_key(factory)
        line_max = min(FAC.MAX_TRACK_LEVEL, len(FAC.products_for_factory(fkey)))
        if track == "cap":
            # 🆕 v1.7.8.17 — ظرفیتِ کارخانه دیگر مستقیم ارتقا نمی‌شود
            await safe_answer(
                callback,
                "📦 انبارِ کارخانه دیگر مستقیم ارتقا نمی‌شود — ظرفیتش جمعِ انبارِ محصولاتش است."
                " از صفحهٔ هر محصول، انبارِ همان محصول را ارتقا بده.",
                show_alert=True,
            )
            return
        elif track == "spd":
            lvl, mx, cost = factory.speed_level, FAC.MAX_TRACK_LEVEL, FAC.speed_upgrade_cost(factory.speed_level)
            label = "⚡ سرعت"
        elif track == "line":
            lvl, mx, cost = factory.line_level, line_max, FAC.line_upgrade_cost(factory.line_level)
            label = "🧵 خطِ تولید"
        else:
            await safe_answer(callback, "ارتقای نامعتبر.", show_alert=True)
            return
        if lvl >= mx:
            await safe_answer(callback, "این مسیر در بالاترین سطح است.", show_alert=True)
            return
        if player.cash < cost:
            await safe_answer(callback, f"💸 پول کافی نداری! هزینه: {cost:,}$", show_alert=True)
            return
        player.cash -= cost
        if track == "cap":
            factory.capacity_level += 1
            new_lv = factory.capacity_level
        elif track == "spd":
            factory.speed_level += 1
            new_lv = factory.speed_level
        else:
            factory.line_level += 1
            new_lv = factory.line_level
        from app.data import leveling as _lv
        _xp_res = {}
        try:   # XP for factory track upgrades
            _xp_res = await _lv.grant_xp(session, player, (20 + 10 * int(new_lv)) // 2, source="factory_upgrade")
        except Exception:
            pass
        await session.commit()
        text, markup = await render_factory_detail(session, player, factory)
    await _edit(callback, text, markup)
    await safe_answer(callback, f"⬆️ {label} ارتقا یافت!")


# ---------- عملیا��ِ محصول (FactoryProduct) ----------
@router.callback_query(F.data.startswith("fp:view:"))
async def fp_view(callback: CallbackQuery):
    fp_id = int(callback.data.split(":")[2])
    async with async_session() as session:
        player = await get_player(session, callback.from_user.id)
        fp, factory = await get_fp(session, fp_id, callback.from_user.id)
        if player is None or fp is None:
            await safe_answer(callback, "محصول پیدا نشد.", show_alert=True)
            return
        text, markup = await render_product_detail(session, player, factory, fp)
    await _edit(callback, text, markup)
    await safe_answer(callback)


@router.callback_query(F.data.startswith("fp:pct:"))
async def fp_percent(callback: CallbackQuery):
    """انتخابِ درصدِ حجمِ خالیِ انبار برای تولید."""
    fp_id = int(callback.data.split(":")[2])
    async with async_session() as session:
        player = await get_player(session, callback.from_user.id)
        fp, factory = await get_fp(session, fp_id, callback.from_user.id)
        if player is None or fp is None:
            await safe_answer(callback, "محصول پیدا نشد.", show_alert=True)
            return
        # 🆕 v1.7.8.18 — تا وقتی یکی از دو خطِ این محصول آزاد باشد، تولیدِ تازه مجاز است
        if _free_slot(fp) is None:
            await safe_answer(callback, _lines_block_msg(fp), show_alert=True)
            return
        fps = await get_factory_products(session, factory.id)
        room = _fp_room(fp)   # 🆕 v1.7.8.17 — انبارِ خودِ محصول
        unit_cost = FAC.unit_raw_cost(fp.product_key, factory.speed_level)
        p = get_product(fp.product_key) or {"name": fp.product_key}
        hrs = FAC.effective_produce_hours(fp.product_key, factory.speed_level)
        if room <= 0:
            await safe_answer(callback, _room_block_msg(fp), show_alert=True)
            return
        lines = [
            f"⚙️ <b>تولیدِ {p['name']}</b>",
            f"💵 موجودی: <b>{player.cash:,}</b> دلار",
            "",
            f"🔳 حجمِ خالیِ انبارِ این محصول: <b>{room:,}</b>/{_p_cap(fp):,} واحد",
            f"🧾 هزینه‌ی موادِ هر واحد: <b>{unit_cost:,}</b>$",
            f"⏱️ زمانِ دوره: <b>{hrs:.1f}</b> ساعت",
            "",
            "چند درصد از حجمِ خالیِ انبارِ این محصول تولید شود؟",
            "برایِ تولیدِ بیشتر از این حجم، از «🧾 افزودن به صفِ ساخت» استفاده کن.",
        ]
    await _edit(callback, "\n".join(lines), percent_menu(fp_id, unit_cost, room))
    await safe_answer(callback)


@router.callback_query(F.data.startswith("fp:start:"))
async def fp_start(callback: CallbackQuery):
    parts = callback.data.split(":")
    fp_id = int(parts[2])
    pct = FAC.normalize_percent(parts[3] if len(parts) > 3 else FAC.DEFAULT_PERCENT)
    async with async_session() as session:
        player = await get_player(session, callback.from_user.id)
        fp, factory = await get_fp(session, fp_id, callback.from_user.id)
        if player is None or fp is None:
            await safe_answer(callback, "محصول پیدا نشد.", show_alert=True)
            return
        fps = await get_factory_products(session, factory.id)
        # 🆕 v1.7.8.18 — گ��تِ خط فقط مربوط به دو خطِ خودِ همین محصول است
        slot = _free_slot(fp)
        if slot is None:
            await safe_answer(callback, _lines_block_msg(fp), show_alert=True)
            return
        room = _fp_room(fp)   # 🆕 v1.7.8.17 — انبارِ خودِ محصول (جایِ باقی‌مانده)
        units = FAC.units_for_percent(room, pct)
        if units <= 0:
            await safe_answer(callback, _room_block_msg(fp), show_alert=True)
            return
        cost = FAC.raw_cost_for_units(fp.product_key, units, factory.speed_level)
        if player.cash < cost:
            await safe_answer(callback, 
                f"💸 برای {units:,} واحد، {cost:,}$ موادِ اولیه لازم است! درصدِ کمتری انتخاب کن.",
                show_alert=True,
            )
            return
        player.cash -= cost
        _slot_start(fp, slot, units, pct)
        await session.commit()
        text, markup = await render_product_detail(session, player, factory, fp)
    await _edit(callback, text, markup)
    await safe_answer(
        callback,
        f"▶️ خطِ {slot + 1}: تولیدِ {units:,} واحد ({pct}%) شروع شد — مواد: {cost:,}$",
    )


@router.callback_query(F.data.startswith("fp:collect:"))
async def fp_collect(callback: CallbackQuery):
    fp_id = int(callback.data.split(":")[2])
    async with async_session() as session:
        player = await get_player(session, callback.from_user.id)
        fp, factory = await get_fp(session, fp_id, callback.from_user.id)
        if player is None or fp is None:
            await safe_answer(callback, "محصول پیدا نشد.", show_alert=True)
            return
        if not _fp_ready(fp, factory.speed_level):
            await safe_answer(callback, "هنوز آماده نیست.", show_alert=True)
            return
        fps = await get_factory_products(session, factory.id)
        room = _fp_room(fp, reserve=False)   # 🆕 v1.7.8.17
        # v1.7.6 — جمع‌آوری فقط به انبار کارخانه؛ انتقال به انبار اصلی فقط دستی
        # 🆕 v1.7.8.18 — همهٔ خطوطِ آمادهٔ این محصول یک‌جا جمع می‌شوند
        added, leftover = 0, 0
        for _s in _ready_slots(fp, factory.speed_level):
            _u = _slot_units(fp, _s, factory)
            _add = max(0, min(_u, room))
            fp.stock += _add
            room -= _add
            added += _add
            _left = max(0, _u - _add)
            if _left > 0:
                _ss(fp, _s, "pending_units", _left)   # خط منتظرِ خالی‌شدنِ انبار می‌ماند
                leftover += _left
            else:
                _slot_clear(fp, _s)
        from app.data import leveling as _lv
        _xp_res = {}
        try:
            _xp_res = await _lv.grant_xp(session, player, FAC.xp_for_units(added) // 2, source="factory_produce")
        except Exception:
            pass
        await _try_start_queue(session, factory, fps)   # 🆕 v1.7.8.17
        await session.commit()
        text, markup = await render_product_detail(session, player, factory, fp)
    await _edit(callback, text, markup)
    if leftover > 0:
        await safe_answer(callback, f"⚠️ انبار کارخانه {added:,} واحد جا داشت. {leftover:,} واحد باقی ماند؛ اول انبار را خالی/منتقل کن.", show_alert=True)
    else:
        await safe_answer(callback, f"📦 {added:,} واحد در انبار کارخانه قرار گرفت." + (_lv.xp_note(_xp_res) if '_lv' in dir() else ""))


@router.callback_query(F.data.startswith("fp:sell:"))
async def fp_sell(callback: CallbackQuery):
    fp_id = int(callback.data.split(":")[2])
    async with async_session() as session:
        player = await get_player(session, callback.from_user.id)
        fp, factory = await get_fp(session, fp_id, callback.from_user.id)
        if player is None or fp is None:
            await safe_answer(callback, "محصول پیدا نشد.", show_alert=True)
            return
        if fp.stock <= 0:
            await safe_answer(callback, "انبار خالی است.", show_alert=True)
            return
        mp = await get_or_refresh_price(session, fp.product_key)
        mult = await market_multiplier(session, player.tg_user_id)
        units = fp.stock
        base_amount = int(units * mp.price * mult)
        from app.services.bonus_breakdown import income_breakdown, append_note
        br = await income_breakdown(session, player.tg_user_id, base_amount)
        amount = int(br["total"])
        player.cash += amount
        fp.stock = 0
        from app.data import leveling as _lv
        _xp_res = {}
        try:
            _xp_res = await _lv.grant_xp(session, player, FAC.xp_for_units(units) // 2, source="factory_sell")
        except Exception:
            pass
        await _try_start_queue(session, factory)   # 🆕 v1.7.8.17
        await session.commit()
        text, markup = await render_product_detail(session, player, factory, fp)
    await _edit(callback, text, markup)
    await safe_answer(callback, append_note(f"💵 {units:,} واحد فروخته شد: +{amount:,}$" + _lv.xp_note(_xp_res), br.get("note") or ""), show_alert=bool(br.get("note")))


@router.callback_query(F.data.startswith("fp:tomain:"))
async def fp_tomain(callback: CallbackQuery):
    fp_id = int(callback.data.split(":")[2])
    async with async_session() as session:
        player = await get_player(session, callback.from_user.id)
        fp, factory = await get_fp(session, fp_id, callback.from_user.id)
        if player is None or fp is None:
            await safe_answer(callback, "محصول پیدا نشد.", show_alert=True)
            return
        if fp.stock <= 0:
            await safe_answer(callback, "انبار خالی است.", show_alert=True)
            return
        wh = await _user_warehouse(session, player.tg_user_id)
        if wh is None:
            await safe_answer(callback, "⛔ اول «🏢 انبارِ اصلی» را بساز.", show_alert=True)
            return
        moved = await _wh_add(session, wh, fp.product_key, fp.stock)
        if moved <= 0:
            await safe_answer(callback, "🏢 انبارِ اصلی پر است! ارتقا بده یا بفروش.", show_alert=True)
            return
        fp.stock -= moved
        await _try_start_queue(session, factory)   # 🆕 v1.7.8.17
        await session.commit()
        text, markup = await render_product_detail(session, player, factory, fp)
    await _edit(callback, text, markup)
    await safe_answer(callback, f"🏢 {moved:,} واحد به انبارِ اصلی منتقل شد.")


# ---------- عملیاتِ گروهیِ یک کارخانه ----------
async def _wh_add(session, wh, product_key, qty, rows=None):
    """افزودن به انبارِ اصلی با رعایتِ حجم؛ تعدادِ انجام‌شده را برمی‌گرداند."""
    rows = rows if rows is not None else await _warehouse_rows(session, wh.id)
    total = sum(r.qty for r in rows)
    room = max(0, WH.warehouse_volume(wh.level) - total)
    moved = min(int(qty or 0), room)
    if moved <= 0:
        return 0
    row = next((r for r in rows if r.product_key == product_key), None)
    if row is None:
        session.add(WarehouseStock(warehouse_id=wh.id, product_key=product_key, qty=moved))
    else:
        row.qty += moved
    return moved


@router.callback_query(F.data.startswith("factory:startall:"))
async def factory_start_all(callback: CallbackQuery):
    factory_id = int(callback.data.split(":")[2])
    async with async_session() as session:
        player = await get_player(session, callback.from_user.id)
        factory = await get_factory(session, factory_id, callback.from_user.id)
        if player is None or factory is None:
            await safe_answer(callback, "کارخانه پیدا نشد.", show_alert=True)
            return
        fps = await get_factory_products(session, factory.id)
        # 🆕 v1.7.8.17 — هر محصول از انبارِ خودش سهم می‌گیرد؛ دیگر فضایِ
        # مشترک تقسیم نمی‌شود پس هیچ محصولی جایِ دیگری را نمی‌خورد.
        _qrows = await _queue_rows(session, factory.id)
        if not _qrows and _free_room(factory, fps, reserve=True) <= 0:
            await safe_answer(callback, _factory_block_msg(factory, fps), show_alert=True)
            return
        # 🆕 v1.7.8.18 — «شروعِ همه‌ی خط‌ها» همیشه ۱۰۰٪ جایِ خالیِ انبارِ هر
        # محصول را تولید می‌کند و اگر جا ماند، خطِ دومِ همان محصول را هم پر می‌کند.
        pct_all = int(getattr(FAC, "START_ALL_PERCENT", 100) or 100)
        started, spent, no_cash = 0, 0, False
        for fp in fps:
            for _ in range(_slots_count()):
                slot = _free_slot(fp)
                if slot is None:
                    break
                room = _fp_room(fp)
                if room <= 0:
                    break
                units = FAC.units_for_percent(room, pct_all)
                if units <= 0:
                    break
                cost = FAC.raw_cost_for_units(fp.product_key, units, factory.speed_level)
                if player.cash < cost:
                    no_cash = True
                    break
                player.cash -= cost
                spent += cost
                _slot_start(fp, slot, units, pct_all)
                started += 1
        # 🆕 v1.7.8.17 — «شروعِ همه» صفِ ساخت را هم جلو می‌بَرد
        q_started, q_units = await _try_start_queue(session, factory, fps)
        if started or q_started:
            await session.commit()
        text, markup = await render_factory_detail(session, player, factory)
    await _edit(callback, text, markup)
    if started or q_started:
        _msg = f"▶️ {started} خط با ۱۰۰٪ حجمِ خالی شروع شد — مواد: {spent:,}$"
        if q_started:
            _msg += f" | 🧾 {q_started} سفارش از صف ({q_units:,} واحد)"
        if no_cash:
            _msg += " | 💸 برایِ باقیِ خط‌ها پولِ مواد کم بود"
        await safe_answer(callback, _msg, show_alert=no_cash)
    else:
        await safe_answer(callback, "خطِ آزادی نبود، یا انبارِ محصولات پر است، یا پولِ مواد کافی نبود.", show_alert=True)


@router.callback_query(F.data.startswith("factory:collectall:"))
async def factory_collect_all(callback: CallbackQuery):
    factory_id = int(callback.data.split(":")[2])
    async with async_session() as session:
        player = await get_player(session, callback.from_user.id)
        factory = await get_factory(session, factory_id, callback.from_user.id)
        if player is None or factory is None:
            await safe_answer(callback, "کارخانه پیدا نشد.", show_alert=True)
            return
        fps = await get_factory_products(session, factory.id)
        wh = await _user_warehouse(session, player.tg_user_id)
        got, to_wh_total = 0, 0
        for fp in fps:
            if not _fp_ready(fp, factory.speed_level):
                continue
            # 🆕 v1.7.8.17 — جا در انبارِ خودِ همین محصول سنجیده می‌شود
            # 🆕 v1.7.8.18 — هر دو خطِ محصول جمع‌آوری می‌شوند
            room = _fp_room(fp, reserve=False)
            for _s in _ready_slots(fp, factory.speed_level):
                _u = _slot_units(fp, _s, factory)
                _add = max(0, min(_u, room))
                fp.stock += _add
                room -= _add
                got += _add
                if _u - _add > 0:
                    _ss(fp, _s, "pending_units", _u - _add)
                else:
                    _slot_clear(fp, _s)
        _xp_res = {}
        if got:
            from app.data import leveling as _lv
            try:
                _xp_res = await _lv.grant_xp(session, player, FAC.xp_for_units(got) // 2, source="factory_produce")
            except Exception:
                pass
        # 🆕 v1.7.8.17 — پس از جمع‌آوری، صفِ ساخت خودکار جلو می‌رود
        q_started, q_units = await _try_start_queue(session, factory, fps)
        if got or q_started:
            await session.commit()
        text, markup = await render_factory_detail(session, player, factory)
    await _edit(callback, text, markup)
    if got or q_started:
        await safe_answer(callback, 
            f"📦 {got:,} واحد جمع‌آوری شد"
            + (f" | 🏢 {to_wh_total:,} به انبارِ اصلی" if to_wh_total else "")
            + (f" | 🧾 {q_started} سفارش از صف ({q_units:,} واحد)" if q_started else "")
        )
    else:
        await safe_answer(callback, "چیزی برای جمع‌آوری نبود.", show_alert=True)


@router.callback_query(F.data.startswith("factory:allmain:"))
async def factory_all_to_main(callback: CallbackQuery):
    factory_id = int(callback.data.split(":")[2])
    async with async_session() as session:
        player = await get_player(session, callback.from_user.id)
        factory = await get_factory(session, factory_id, callback.from_user.id)
        if player is None or factory is None:
            await safe_answer(callback, "کارخانه پیدا نشد.", show_alert=True)
            return
        wh = await _user_warehouse(session, player.tg_user_id)
        if wh is None:
            await safe_answer(callback, "⛔ اول انبارِ اصلی را بساز.", show_alert=True)
            return
        fps = await get_factory_products(session, factory.id)
        moved_total = 0
        for fp in fps:
            if fp.stock <= 0:
                continue
            moved = await _wh_add(session, wh, fp.product_key, fp.stock)
            fp.stock -= moved
            moved_total += moved
            if moved == 0:
                break
        # 🆕 v1.7.8.17 — خالی‌شدنِ انبار یعنی صف می‌تواند شروع کند
        q_started, q_units = await _try_start_queue(session, factory, fps)
        if moved_total or q_started:
            await session.commit()
        text, markup = await render_factory_detail(session, player, factory)
    await _edit(callback, text, markup)
    if moved_total:
        await safe_answer(
            callback,
            f"🏢 {moved_total:,} واحد به انبارِ اصلی منتقل شد."
            + (f" | 🧾 {q_started} سفارش از صف شروع شد" if q_started else ""),
        )
    else:
        await safe_answer(callback, "🏢 انبارِ اصلی جا ندارد یا موجودی صفر است.", show_alert=True)


@router.callback_query(F.data.startswith("factory:sellall:"))
async def factory_sell_all(callback: CallbackQuery):
    """🆕 فروشِ ��کجای همه‌ی محصولاتی که در انبارِ هر خطِ این کارخانه موجودند."""
    factory_id = int(callback.data.split(":")[2])
    async with async_session() as session:
        player = await get_player(session, callback.from_user.id)
        factory = await get_factory(session, factory_id, callback.from_user.id)
        if player is None or factory is None:
            await safe_answer(callback, "کارخانه پیدا نشد.", show_alert=True)
            return
        fps = await get_factory_products(session, factory.id)
        mult = await market_multiplier(session, player.tg_user_id)
        total_units, base_total = 0, 0
        for fp in fps:
            if fp.stock <= 0:
                continue
            mp = await get_or_refresh_price(session, fp.product_key)
            units = fp.stock
            base_total += int(units * mp.price * mult)
            fp.stock = 0
            total_units += units
        from app.services.bonus_breakdown import income_breakdown, append_note
        br = {"note": "", "total": base_total}
        if total_units > 0:
            br = await income_breakdown(session, player.tg_user_id, base_total)
            total_amount = int(br["total"])
            player.cash += total_amount
            from app.data import leveling as _lv
            _xp_res = {}
            try:
                _xp_res = await _lv.grant_xp(session, player, FAC.xp_for_units(total_units) // 2, source="factory_sell_all")
            except Exception:
                pass
            await _try_start_queue(session, factory, fps)   # 🆕 v1.7.8.17
            await session.commit()
        else:
            total_amount = 0
            _xp_res = {}
        text, markup = await render_factory_detail(session, player, factory)
    await _edit(callback, text, markup)
    if total_units > 0:
        msg = f"💵 {total_units:,} واحد از همه‌ی محصولات فروخته شد: +{total_amount:,}$"
        try:
            msg = msg + _lv.xp_note(_xp_res)
        except Exception:
            pass
        await safe_answer(callback, append_note(msg, br.get("note") or ""), show_alert=bool(br.get("note")))
    else:
        await safe_answer(callback, "چیزی برای فروش نبود.", show_alert=True)


# ---------- 🆕 v1.7.8.17 — ارتقایِ انبارِ هر محصول ----------
@router.callback_query(F.data.startswith("fp:upcap:"))
async def fp_upcap(callback: CallbackQuery):
    """ارتقایِ انبارِ اختصاصیِ یک محصول (حداکثر ۱۰ سطح)."""
    fp_id = int(callback.data.split(":")[2])
    async with async_session() as session:
        player = await get_player(session, callback.from_user.id)
        fp, factory = await get_fp(session, fp_id, callback.from_user.id)
        if player is None or fp is None:
            await safe_answer(callback, "محصول پیدا نشد.", show_alert=True)
            return
        lvl = int(getattr(fp, "capacity_level", 1) or 1)
        if lvl >= FAC.PRODUCT_CAP_MAX_LEVEL:
            await safe_answer(
                callback,
                f"📦 انبارِ این محصول در بالاترین سطح است ({FAC.PRODUCT_CAP_MAX:,} واحد).",
                show_alert=True,
            )
            return
        cost = FAC.product_capacity_upgrade_cost(lvl)
        if player.cash < cost:
            await safe_answer(callback, f"💸 پول کافی نداری! هزینه: {cost:,}$", show_alert=True)
            return
        player.cash -= cost
        fp.capacity_level = lvl + 1
        new_cap = FAC.product_capacity(fp.capacity_level)
        from app.data import leveling as _lv
        _xp_res = {}
        try:
            _xp_res = await _lv.grant_xp(session, player, (20 + 10 * (lvl + 1)) // 2, source="factory_upgrade")
        except Exception:
            pass
        # جایِ تازه یعنی صف می‌ت��اند شروع کند
        await _try_start_queue(session, factory)
        await session.commit()
        text, markup = await render_product_detail(session, player, factory, fp)
    await _edit(callback, text, markup)
    await safe_answer(
        callback,
        f"⬆️ انبارِ این محصول سطح {lvl + 1} شد — ظرفیت: {new_cap:,} واحد.",
    )


# ---------- 🆕 v1.7.8.17 — صفِ ساخت ----------
@router.callback_query(F.data.startswith("fpq:pct:"))
async def fpq_percent(callback: CallbackQuery):
    """انتخابِ حجمِ سفارشی که به صفِ ساخت فرستاده می‌شود."""
    fp_id = int(callback.data.split(":")[2])
    async with async_session() as session:
        player = await get_player(session, callback.from_user.id)
        fp, factory = await get_fp(session, fp_id, callback.from_user.id)
        if player is None or fp is None:
            await safe_answer(callback, "محصول پیدا نشد.", show_alert=True)
            return
        cap = _p_cap(fp)
        unit_cost = FAC.unit_raw_cost(fp.product_key, factory.speed_level)
        p = get_product(fp.product_key) or {"name": fp.product_key}
        qrows = await _queue_for_fp(session, fp.id)
        lines = [
            f"🧾 <b>صفِ ساخت — {p['name']}</b>",
            f"💵 موجودی: <b>{player.cash:,}</b> دلار",
            "",
            f"📦 انبارِ این محصول: <b>{int(fp.stock or 0):,}</b>/{cap:,} واحد",
            f"🔳 حجمِ خالی: <b>{_fp_room(fp):,}</b> واحد",
            f"🧾 سفارش‌هایِ در صف: <b>{len(qrows)}</b>",
            f"🧾 هزینه‌ی موادِ هر واحد: <b>{unit_cost:,}</b>$",
            "",
            "درصدِ انتخابی از <b>کلِ ظرفیتِ انبارِ این محصول</b> حساب می‌شود.",
            "پولِ مواد همین حالا کسر می‌شود؛ اگر سفارش را حذف کنی کامل برمی‌گردد.",
            "به‌محضِ خالی‌شدنِ انبار (فروش یا انتقال به انبارِ اصلی) خودکار شروع می‌شود.",
        ]
    await _edit(callback, "\n".join(lines), queue_percent_menu(fp_id, unit_cost, cap))
    await safe_answer(callback)


@router.callback_query(F.data.startswith("fpq:add:"))
async def fpq_add(callback: CallbackQuery):
    """ثبتِ یک سفارش در صفِ ساخت (پول همین جا کسر می‌شود)."""
    parts = callback.data.split(":")
    fp_id = int(parts[2])
    pct = FAC.normalize_percent(parts[3] if len(parts) > 3 else FAC.DEFAULT_PERCENT)
    async with async_session() as session:
        player = await get_player(session, callback.from_user.id)
        fp, factory = await get_fp(session, fp_id, callback.from_user.id)
        if player is None or fp is None:
            await safe_answer(callback, "محصول پیدا نشد.", show_alert=True)
            return
        rows = await _queue_rows(session, factory.id)
        if len(rows) >= FAC.QUEUE_MAX:
            await safe_answer(
                callback,
                f"🧾 صفِ ساخت پر است ({FAC.QUEUE_MAX} سفارش). اول بخشی از صف را خالی کن.",
                show_alert=True,
            )
            return
        cap = _p_cap(fp)
        units = max(1, int(cap * pct // 100))
        cost = FAC.raw_cost_for_units(fp.product_key, units, factory.speed_level)
        if player.cash < cost:
            await safe_answer(
                callback,
                f"💸 برای {units:,} واحد، {cost:,}$ موادِ اولیه لازم است! درصدِ کمتری انتخاب کن.",
                show_alert=True,
            )
            return
        player.cash -= cost
        session.add(FactoryQueueItem(
            factory_id=factory.id,
            fp_id=fp.id,
            product_key=fp.product_key,
            units=units,
            percent=pct,
            paid_cost=cost,
        ))
        await session.flush()
        started, q_units = await _try_start_queue(session, factory)
        await session.commit()
        text, markup = await render_product_detail(session, player, factory, fp)
    await _edit(callback, text, markup)
    if started:
        await safe_answer(
            callback,
            f"🧾 {units:,} واحد ثبت شد و {q_units:,} واحدش فوری شروع شد — مواد: {cost:,}$",
        )
    else:
        await safe_answer(
            callback,
            f"🧾 {units:,} واحد به صفِ ساخت رفت — مواد: {cost:,}$. به‌محضِ بازشدنِ جا خودکار شروع می‌شود.",
        )


async def render_queue(session, player, factory, page=0):
    """رندرِ صفحهٔ صفِ ساختِ یک کارخانه."""
    items = await _queue_rows(session, factory.id)
    fps = await get_factory_products(session, factory.id)
    by_id = {fp.id: fp for fp in fps}
    lines = [
        f"🧾 <b>صفِ ساخت — {_factory_title(factory)}</b>",
        f"💵 موجودی: <b>{player.cash:,}</b> دلار",
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
            p = get_product(it.product_key) or {"name": it.product_key}
            fp = by_id.get(int(getattr(it, "fp_id", 0) or 0))
            if fp is None:
                st = "⚠️ محصول حذف شده"
            elif _free_slot(fp) is None:
                st = f"⏳ هر {_slots_count()} خطِ این محصول مشغول است"
            elif _fp_room(fp) > 0:
                st = "▶️ آمادهٔ شروع"
            else:
                st = "⏸️ منتظرِ خالی‌شدنِ انبار"
            lines.append(f"{i}. {p['name']} — {int(getattr(it, 'units', 0) or 0):,} واحد | {st}")
        lines.append("")
        lines.append("💡 با حذفِ سفارش، پولِ موادِ آن <b>کامل</b> برمی‌گردد.")
    return "\n".join(lines), factory_queue_menu(factory.id, items, by_id, page, None)


@router.callback_query(F.data.startswith("fq:menu:") | F.data.startswith("fq:page:"))
async def factory_queue_view(callback: CallbackQuery):
    parts = callback.data.split(":")
    factory_id = int(parts[2])
    page = int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else 0
    async with async_session() as session:
        player = await get_player(session, callback.from_user.id)
        factory = await get_factory(session, factory_id, callback.from_user.id)
        if player is None or factory is None:
            await safe_answer(callback, "کارخانه پیدا نشد.", show_alert=True)
            return
        text, markup = await render_queue(session, player, factory, page)
    await _edit(callback, text, markup)
    await safe_answer(callback)


@router.callback_query(F.data.startswith("fq:run:"))
async def factory_queue_run(callback: CallbackQuery):
    """شروعِ دستیِ هر چه از صف که الان جا دارد."""
    factory_id = int(callback.data.split(":")[2])
    async with async_session() as session:
        player = await get_player(session, callback.from_user.id)
        factory = await get_factory(session, factory_id, callback.from_user.id)
        if player is None or factory is None:
            await safe_answer(callback, "کارخانه پیدا نشد.", show_alert=True)
            return
        started, units = await _try_start_queue(session, factory)
        if started:
            await session.commit()
        text, markup = await render_queue(session, player, factory)
    await _edit(callback, text, markup)
    if started:
        await safe_answer(callback, f"▶️ {started} سفارش از صف شروع شد ({units:,} واحد).")
    else:
        await safe_answer(
            callback,
            "هنوز جا یا خطِ آزاد نیست. به‌محضِ خالی‌شدنِ انبار، صف خودکار جلو می‌رود.",
            show_alert=True,
        )


@router.callback_query(F.data.startswith("fq:del:"))
async def factory_queue_del(callback: CallbackQuery):
    """حذفِ یک سفارش از صف با بازپرداختِ کاملِ مواد."""
    item_id = int(callback.data.split(":")[2])
    async with async_session() as session:
        player = await get_player(session, callback.from_user.id)
        res = await session.execute(
            select(FactoryQueueItem).where(FactoryQueueItem.id == item_id)
        )
        it = res.scalar_one_or_none()
        if player is None or it is None:
            await safe_answer(callback, "سفارش پیدا نشد.", show_alert=True)
            return
        factory = await get_factory(session, int(it.factory_id), callback.from_user.id)
        if factory is None:
            await safe_answer(callback, "کارخانه پیدا نشد.", show_alert=True)
            return
        refund = max(0, int(getattr(it, "paid_cost", 0) or 0))
        player.cash += refund
        await session.delete(it)
        await session.commit()
        text, markup = await render_queue(session, player, factory)
    await _edit(callback, text, markup)
    await safe_answer(callback, f"🗑️ سفارش حذف شد — {refund:,}$ بازپرداخت شد.")


@router.callback_query(F.data.startswith("fq:clear:"))
async def factory_queue_clear(callback: CallbackQuery):
    """خالی‌کردنِ کلِ صف با بازپرداختِ کامل."""
    factory_id = int(callback.data.split(":")[2])
    async with async_session() as session:
        player = await get_player(session, callback.from_user.id)
        factory = await get_factory(session, factory_id, callback.from_user.id)
        if player is None or factory is None:
            await safe_answer(callback, "کارخانه پیدا نشد.", show_alert=True)
            return
        items = await _queue_rows(session, factory.id)
        n = len(items)
        refund = sum(max(0, int(getattr(it, "paid_cost", 0) or 0)) for it in items)
        for it in items:
            await session.delete(it)
        if n:
            player.cash += refund
            await session.commit()
        text, markup = await render_queue(session, player, factory)
    await _edit(callback, text, markup)
    if n:
        await safe_answer(callback, f"🗑️ {n} سفارش حذف شد — {refund:,}$ بازپرداخت شد.")
    else:
        await safe_answer(callback, "صف از قبل خالی بود.", show_alert=True)


# ---------- بازار: نمودارِ قیمتِ هر کارخانه ----------
@router.callback_query((F.data == "market:prices") | F.data.startswith("market:pricesp:"))
async def market_prices(callback: CallbackQuery):
    """فهرستِ کارخانه‌ها — نمودارِ قیمتِ هر کارخانه جداگانه است."""
    page = _page_arg(callback.data, 2) if callback.data.startswith("market:pricesp:") else 0
    lines = ["📊 <b>نمودارِ قیمت — به تفکیکِ کارخانه‌ها</b>", ""]
    async with async_session() as session:
        for fkey in FAC.FACTORY_ORDER:
            keys = FAC.products_for_factory(fkey)
            lines.append(f"<b>{FAC.factory_name(fkey)}</b>")
            for key in keys:
                mp = await get_or_refresh_price(session, key)
                history = json.loads(mp.history or "[]")
                p = get_product(key)
                lines.append(f"  {p['name']} {price_arrow(history)} <b>{mp.price:,.0f}</b>$")
            lines.append("")
    lines.append("💡 برای دیدنِ نمودارِ دقیقِ هر محصول، کارخانه‌اش را انتخاب کن.")
    await _edit(callback, "\n".join(lines), prices_menu(page, callback.from_user.id))
    await safe_answer(callback)


@router.callback_query(F.data.startswith("market:pf:") | F.data.startswith("market:pfp:"))
async def market_prices_of_factory(callback: CallbackQuery):
    """نمودارِ قیمتِ محصولاتِ یک کارخانه‌ی مشخص (متناسب با محصولاتِ همان کارخانه)."""
    parts = callback.data.split(":")
    fkey = parts[2]
    page = _page_arg(callback.data, 3) if parts[1] == "pfp" else 0
    if fkey not in FAC.FACTORY_TYPES:
        await safe_answer(callback, "کارخانه‌ی نامعتبر.", show_alert=True)
        return
    t = FAC.FACTORY_TYPES[fkey]
    uid = callback.from_user.id
    lines = [f"📈 <b>نمودارِ قیمت — {t['name']}</b>", t["desc"], ""]
    async with async_session() as session:
        # 🐞 v1.7.8.14 — همان باگِ نمایشِ ب��ند: هزینه‌ی مواد بدون سطحِ
        # سرعت نشان داده می‌شد، ولی هنگامِ تولید با سطحِ سرعت کسر می‌شود.
        spd = int(await session.scalar(
            select(Factory.speed_level).where(
                Factory.tg_user_id == uid,
                Factory.factory_key == fkey,
            )
        ) or 1)
        if spd > 1:
            lines.append(f"⚡ سرعتِ کارخانه‌ی تو: سطح {spd} ← مواد +{2 * (spd - 1)}٪")
            lines.append("")
        for key in FAC.products_for_factory(fkey):
            p = get_product(key)
            mp = await get_or_refresh_price(session, key)
            history = json.loads(mp.history or "[]")
            recent = history[-HISTORY_LEN:]
            lines.append(f"{p['name']} {price_arrow(history)} <b>{mp.price:,.0f}</b>$")
            lines.append(f"  <code>{sparkline(recent)}</code>")
            lines.append(
                f"  موادِ هر واحد ≈ {FAC.unit_raw_cost(key, spd):,}$ | بازه: {p['min']:,}$–{p['max']:,}$"
            )
            lines.append("")
    await _edit(callback, "\n".join(lines), factory_prices_menu(fkey, page, callback.from_user.id))
    await safe_answer(callback)


@router.callback_query(F.data.startswith("market:chart:"))
async def market_chart(callback: CallbackQuery):
    product_key = callback.data.split(":")[2]
    p = get_product(product_key)
    if p is None:
        await safe_answer(callback, "محصول نامعتبر.", show_alert=True)
        return
    async with async_session() as session:
        mp = await get_or_refresh_price(session, product_key)
    history = json.loads(mp.history or "[]")
    recent = history[-HISTORY_LEN:]
    lo = min(recent) if recent else mp.price
    hi = max(recent) if recent else mp.price
    fkey = p.get("factory")
    lines = [
        f"📈 <b>نمودارِ قیمت — {p['name']}</b>",
        f"🏭 تولیدیِ: {FAC.factory_name(fkey) if fkey else '💎 برندسازی'}",
        "",
        f"<code>{sparkline(recent)}</code>",
        "",
        f"قیمتِ فعلی: <b>{mp.price:,.0f}</b>$ {price_arrow(history)}",
        f"کمترین (اخیر): {lo:,.0f}$ | بیشترین: {hi:,.0f}$",
        f"بازه‌ی مجاز: {p['min']:,}$ تا {p['max']:,}$",
        "",
        "💡 وقتی قیمت بالای میانگین است بفروش، وقتی پایین است تولید/انبار کن.",
    ]
    await _edit(callback, "\n".join(lines), chart_back_menu(product_key))
    await safe_answer(callback)


# --------------------------- v1.7.6 لغو تولید ---------------------------
@router.callback_query(F.data.startswith("fp:cancel:"))
async def fp_cancel(callback: CallbackQuery):
    fp_id = int(callback.data.split(":")[2])
    async with async_session() as session:
        player = await get_player(session, callback.from_user.id)
        fp, factory = await get_fp(session, fp_id, callback.from_user.id)
        if player is None or fp is None:
            await safe_answer(callback, "محصول پیدا نشد.", show_alert=True); return
        # 🆕 v1.7.8.18 — همهٔ خطوطِ فعالِ این محصول لغو می‌شوند
        busy = _busy_slots(fp)
        if not busy:
            await safe_answer(callback, "تولیدی در جریان نیست.", show_alert=True); return
        # بازپرداختِ ۵۰٪ از همان مبلغی که هنگامِ شروعِ تولید واقعاً کم شده است.
        # هشدار: "raw_cost" در دادهٔ محصول هزینهٔ یک «دسته» (batch) است، نه یک واحد.
        # پس هزینهٔ هر واحد = raw_cost / batch. استفادهٔ مستقیم از raw_cost به‌عنوان
        # قیمتِ واحد، بازپرداخت را به‌اندازهٔ batch برابر می‌کرد (باگِ چاپِ پول).
        # همیشه از همان تابعی استفاده شود که در شروعِ تولید پول کم می‌کند.
        refund = 0
        for _s in busy:
            refund_units = int(_sg(fp, _s, "pending_units", 0) or 0)
            paid = int(FAC.raw_cost_for_units(fp.product_key, refund_units, factory.speed_level))
            refund += max(0, paid // 2)
            _slot_clear(fp, _s)
        if refund:
            player.cash = int(player.cash or 0) + refund
        await session.commit()
        text, markup = await render_product_detail(session, player, factory, fp)
    await _edit(callback, text, markup)
    await safe_answer(
        callback,
        f"🛑 {len(busy)} خطِ تولید لغو شد. بازپرداخت مواد: {refund:,}$",
        show_alert=True,
    )


@router.callback_query(F.data.startswith("factory:cancelall:"))
async def factory_cancel_all(callback: CallbackQuery):
    factory_id = int(callback.data.split(":")[2])
    async with async_session() as session:
        player = await get_player(session, callback.from_user.id)
        factory = await get_factory(session, factory_id, callback.from_user.id)
        if player is None or factory is None:
            await safe_answer(callback, "کارخانه پیدا نشد.", show_alert=True); return
        fps = await get_factory_products(session, factory.id)
        n=0; refund=0
        for fp in fps:
            # 🆕 v1.7.8.18 — هر دو خطِ هر محصول
            for _s in _busy_slots(fp):
                units = int(_sg(fp, _s, "pending_units", 0) or 0)
                # ۵۰٪ از همان مبلغِ پرداخت‌شده (raw_cost هزینهٔ دسته است، نه واحد)
                paid = int(FAC.raw_cost_for_units(fp.product_key, units, factory.speed_level))
                refund += max(0, paid // 2)
                _slot_clear(fp, _s); n+=1
        if refund:
            player.cash=int(player.cash or 0)+refund
        if n:
            await session.commit()
        text, markup = await render_factory_detail(session, player, factory)
    await _edit(callback, text, markup)
    await safe_answer(callback, f"🛑 {n} خط لغو شد. بازپرداخت: {refund:,}$" if n else "خط فعالی نبود.", show_alert=True)
