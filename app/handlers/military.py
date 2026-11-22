# -*- coding: utf-8 -*-
"""مرحله ۱۹ — بخشِ نظامی: خرید/ارتقا/آموزشِ نیروها و آوردگاهِ آزمایشی.

پیشوندِ کالبک: mil:  —  فقط داخلِ PVِ ربات.
کلمه‌ی فرمان: «نظامی» / «ارتش» → منوی نظامی را باز می‌کند.
"""
import random

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.data import military as M
from app.database.engine import async_session
from app.handlers.profile import get_player
from app.keyboards.military_menu import (
    buy_confirm_menu,   # 🐞 مرحله ۷۱ — این ایمپورت جا افتاده بود و دکمه‌های ۱/۲۵۰/۵۰۰/۱۰۰۰ را از کار انداخته بود
    buy_qty_menu,
    category_units_menu,
    military_back_menu,
    barracks_upgrade_menu,
    hospital_detail_menu,   # 🆕 v1.7.6.3 — بیمارستانِ دستی
    hospital_list_menu,     # 🆕 v1.7.6.3 — بیمارستانِ دستی
    military_home_menu,
    shop_categories_menu,
    training_queue_menu,
    training_cancel_menu,
    upgrade_units_menu,
)
from app.models.player import Player
from app.services import hospital_service as HS
from app.services import military_service
from app.states import MilitaryStates
from app.utils.ui import ensure_owner, safe_show, split_owner, paginate, safe_answer

router = Router(name="military")

MILITARY_ONLY_BOT = "🛡️ بخشِ نظامی فقط داخلِ خودِ ربات در دسترس است."


def _is_private(chat_type: str) -> bool:
    return chat_type == "private"


async def _levels(session, uid: int) -> dict:
    units = await military_service.get_units(session, uid)
    return {u.unit_key: int(u.upgrade_level) for u in units}


async def _home_text(session, uid: int) -> str:
    units = await military_service.get_units(session, uid)
    stacks = [(u.unit_key, int(u.count), int(u.upgrade_level)) for u in units if u.count > 0]
    power = M.army_power(stacks)
    total_units = sum(int(u.count) for u in units)
    rank = M.military_rank(power)
    player = await get_player(session, uid)
    cash = int(player.cash or 0) if player else 0
    pending = await military_service.pending_training(session, uid)
    barracks, max_cap, levels, capacity = await military_service.barracks_status(session, uid)
    queued_units = sum(int(p["qty"] or 0) for p in pending)
    occupied_capacity = total_units + queued_units
    free_capacity = max(0, capacity - occupied_capacity)
    lines = [
        "🎖️ <b>فرماندهیِ نظامی</b>",
        "",
        f"🎖️ رده‌ی نظامی: <b>{rank}</b>",
        f"💥 قدرتِ کلِ ارتش: <b>{power:,}</b>",
        f"🪖 سربازخانه لول {barracks.level}/{levels} — ظرفیت: {capacity:,} واحد",
        f"📦 حجم اشغال‌شده: {occupied_capacity:,}/{capacity:,} | فضای خالی: {free_capacity:,}",
        f"🫡 نیروهای فعال: {total_units:,} | در صف پرورش: {queued_units:,}",
        f"💰 موجودی: {cash:,}$",
    ]
    if pending:
        total_pending = sum(p["qty"] for p in pending)
        soonest = min(p["remaining"] for p in pending)
        # 🐞 مرحله ۶۷ — قبلاً فقط «نزدیک‌ترین» بچ نمایش داده می‌شد؛ برای همین ۸۴۰۰ نیرو
        # کمتر از ۹۰۲ نیرو به نظر می‌رسید. حالا هم مجموع و هم نزدیک‌ترین را نشان می‌دهیم.
        latest = max(p["remaining"] for p in pending)
        lines.append(
            f"🏗️ در حالِ پرورش: {total_pending:,} واحد — نزدیک‌ترین تا {M.fmt_eta(soonest)}"
            f" | پایانِ کلِ صف تا {M.fmt_eta(latest)}"
        )
    lines += [
        "",
        "ارتشت را بساز، ارتقا بده و ترکیبِ درست را برای نبردها بچین.",
    ]
    return "\n".join(lines)


async def _show_home(message: Message, uid: int) -> None:
    async with async_session() as session:
        await military_service.settle_training(session, uid)
        text = await _home_text(session, uid)
    await safe_show(message, text, military_home_menu(uid))


@router.message(F.text.in_({"نظامی", "🎖️ نظامی", "ارتش"}))
async def summon_military(message: Message) -> None:
    if not _is_private(message.chat.type):
        await message.reply(MILITARY_ONLY_BOT)
        return
    async with async_session() as session:
        player = await get_player(session, message.from_user.id)
    if not player:
        await message.reply("اول در چتِ خصوصیِ ربات /start را بزن.")
        return
    if int(player.level or 1) < M.MILITARY_UNLOCK_LEVEL:
        await message.reply(f"🔒 بخشِ نظامی از سطحِ {M.MILITARY_UNLOCK_LEVEL} باز می‌شود.")
        return
    await _show_home(message, message.from_user.id)


@router.callback_query(F.data.startswith("menu:military") | F.data.startswith("mil:hub"))
async def open_military(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    if not _is_private(callback.message.chat.type):
        await safe_answer(callback, MILITARY_ONLY_BOT, show_alert=True)
        return
    async with async_session() as session:
        player = await get_player(session, callback.from_user.id)
    if player and int(player.level or 1) < M.MILITARY_UNLOCK_LEVEL:
        await safe_answer(callback, f"🔒 بخشِ نظامی از سطحِ {M.MILITARY_UNLOCK_LEVEL} باز می‌شود.", show_alert=True)
        return
    await _show_home(callback.message, callback.from_user.id)
    await safe_answer(callback)


# --------------------------- ارتشِ من ---------------------------
@router.callback_query(F.data.startswith("mil:army"))
async def show_army(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    uid = callback.from_user.id
    async with async_session() as session:
        await military_service.settle_training(session, uid)
        units = await military_service.get_units(session, uid)
    if not any(u.count > 0 for u in units):
        await safe_show(callback.message, "🫡 هنوز هیچ نیرویی نداری. از کارخانه‌ی تسلیحاتی شروع کن.", military_back_menu(uid))
        await safe_answer(callback)
        return
    power = M.army_power([(u.unit_key, int(u.count), int(u.upgrade_level)) for u in units if u.count > 0])
    lines = [f"🛠️ <b>ارتشِ تو</b> — 💥 قدرتِ کل: <b>{power:,}</b>"]
    lines += military_service.army_summary_lines(units)
    await safe_show(callback.message, "\n".join(lines), military_back_menu(uid))
    await safe_answer(callback)


# --------------------------- کارخانه‌ی تسلیحاتی ---------------------------
@router.callback_query(F.data.startswith("mil:shop"))
async def show_shop(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    uid = callback.from_user.id
    text = (
        "🏪 <b>کارخانه‌ی تسلیحاتی</b>\n\n"
        "یک دسته را انتخاب کن. هر دسته چند نوع نیروی متفاوت با نقاطِ قوت/ضعف دارد.\n"
        "⚠️ یادت باشد: پدافند فقط هوایی را می‌زند، تانک و سرباز فقط زمینی، و ..."
    )
    await safe_show(callback.message, text, shop_categories_menu(uid))
    await safe_answer(callback)


@router.callback_query(F.data.startswith("mil:cat:"))
async def show_category(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    base, _ = split_owner(callback.data)
    cat = base.split(":", 2)[2]
    uid = callback.from_user.id
    async with async_session() as session:
        player = await get_player(session, uid)
        levels = await _levels(session, uid)
    plevel = int(player.level or 1) if player else 1
    lines = [f"<b>{M.CATEGORY_LABELS.get(cat, cat)}</b>", ""]
    for k in M.units_in_category(cat):
        u = M.get_unit(k)
        lines.append(
            f"{u['name']} — 🗡{u['atk']} 🛡{u['def']} ❤️{u['hp']}\n"
            f"   ➕ {u['pros']}\n   ➖ {u['cons']}\n"
            f"   ⏳ زمان پرورش هر واحد: <b>{M.fmt_eta(M.train_seconds(k, 1))}</b>"
        )
    await safe_show(callback.message, "\n".join(lines), category_units_menu(uid, cat, plevel, levels))
    await safe_answer(callback)


@router.callback_query(F.data.startswith("mil:locked"))
async def locked(callback: CallbackQuery) -> None:
    await safe_answer(callback, "🔒 سطحِ بازیکن‌ات برای این نیرو کافی نیست.", show_alert=True)


@router.callback_query(F.data.startswith("mil:noop"))
async def noop(callback: CallbackQuery) -> None:
    await safe_answer(callback, "✅ این نوع به بیشینه‌ی ارتقا رسیده.", show_alert=True)


@router.callback_query(F.data.startswith("mil:buy:"))
async def buy_choose_qty(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    base, _ = split_owner(callback.data)
    unit_key = base.split(":", 2)[2]
    u = M.get_unit(unit_key)
    if not u:
        await safe_answer(callback, "❌ نیروی نامعتبر.", show_alert=True)
        return
    uid = callback.from_user.id
    async with async_session() as session:
        levels = await _levels(session, uid)
    lv = int(levels.get(unit_key, 0))
    price = M.buy_cost(unit_key, lv)
    text = (
        f"{u['name']}\n\n"
        f"🗡 حمله: {u['atk']} | 🛡 دفاع: {u['def']} | ❤️ جان: {u['hp']}\n"
        f"💲 قیمتِ فعلیِ هر واحد: {price:,}$ (سطحِ ارتقا: {lv})\n"
        f"➕ {u['pros']}\n➖ {u['cons']}\n\nچند واحد می‌خری?"
    )
    await safe_show(callback.message, text, buy_qty_menu(uid, unit_key))
    await safe_answer(callback)


@router.callback_query(F.data.startswith("mil:buyq:"))
async def buy_preview(callback: CallbackQuery) -> None:
    """🐞 مرحله ۷۱ — دکمه‌های آماده‌ی تعداد (۱ / ۲۵۰ / ۵۰۰ / ۱۰۰۰).

    دو مشکل داشت:
      ۱) `buy_confirm_menu` ایمپورت نشده بود → NameError و دکمه کاملاً بی‌اثر.
      ۲) هر خطا فقط به‌شکلِ alert نشان داده می‌شد؛ اگر کالبک پیش‌تر پاسخ گرفته بود
         (مثلاً نگهبانِ وضعیت عملیاتِ نیمه‌کاره را لغو کرده بود) آن alert گم می‌شد.
    حالا اول کالبک بسته می‌شود و علتِ خطا داخلِ متنِ پیام می‌آید، پس همیشه دیده می‌شود.
    """
    if not await ensure_owner(callback):
        return
    await safe_answer(callback)
    uid = callback.from_user.id
    base, _ = split_owner(callback.data)
    parts = base.split(":")
    if len(parts) != 4 or not parts[3].isdigit() or not M.get_unit(parts[2]):
        await safe_show(
            callback.message,
            "❌ درخواستِ خرید نامعتبر است. از منوی نظامی دوباره تلاش کن.",
            military_back_menu(uid),
        )
        return
    unit_key, qty = parts[2], int(parts[3])
    u = M.get_unit(unit_key)
    from sqlalchemy import select as _select

    from app.models.military import MilitaryTrainingQueue as _MTQ

    async with async_session() as session:
        levels = await _levels(session, uid)
        unit_price = M.buy_cost(unit_key, int(levels.get(unit_key, 0)))
        price = unit_price * qty
        player = await get_player(session, uid)
        _b, _mx, _lv, capacity = await military_service.barracks_status(session, uid)
        active_total = sum(
            int(x.count or 0) for x in await military_service.get_units(session, uid)
        )
        queued_total = sum(
            int(q.qty or 0)
            for q in (
                await session.execute(_select(_MTQ).where(_MTQ.owner_id == uid))
            ).scalars().all()
        )
    cash = int(getattr(player, "cash", 0) or 0) if player is not None else 0
    used = active_total + queued_total
    free = max(0, int(capacity) - used)
    header = (
        f"🪖 <b>تأیید خرید نیرو</b>\n"
        f"{u['name']} × {qty:,}\n"
        f"💲 هر واحد: {unit_price:,}$\n"
        f"💰 هزینه نهایی: {price:,}$\n"
        f"🏦 موجودیِ تو: {cash:,}$\n"
        f"🏗️ ظرفیت سربازخانه: {used:,}/{int(capacity):,} (جای آزاد: {free:,})"
    )
    if player is None:
        await safe_show(callback.message, "❌ اول /start را بزن.", military_back_menu(uid))
        return
    if int(player.level or 1) < int(u["unlock"]):
        await safe_show(
            callback.message,
            f"{header}\n\n🔒 این نیرو از سطحِ {u['unlock']} باز می‌شود.",
            buy_qty_menu(uid, unit_key),
        )
        return
    if cash < price:
        await safe_show(
            callback.message,
            f"{header}\n\n❌ پولت کافی نیست — <b>{price - cash:,}$</b> کم داری.\n"
            f"💡 تعدادِ کمتری انتخاب کن یا اول درآمدت را جمع کن.",
            buy_qty_menu(uid, unit_key),
        )
        return
    if qty > free:
        await safe_show(
            callback.message,
            f"{header}\n\n🪖 ظرفیتِ سربازخانه کافی نیست؛ فقط جای <b>{free:,}</b> نیروی دیگر داری.\n"
            f"💡 اول سربازخانه را ارتقا بده، یا تعدادِ کمتری بخر.",
            buy_qty_menu(uid, unit_key),
        )
        return
    await safe_show(
        callback.message,
        f"{header}\n\n✅ خرید را تأیید می‌کنی؟",
        buy_confirm_menu(uid, unit_key, qty),
    )

@router.callback_query(F.data.startswith("mil:buyok:"))
async def buy_do(callback: CallbackQuery) -> None:
    """خرید با دکمهٔ تعداد آماده؛ پاسخ فوری مانع ماندنِ دکمه روی حالت لود می‌شود."""
    if not await ensure_owner(callback):
        return
    await safe_answer(callback, "⏳ در حال ثبت خرید...")
    base, _ = split_owner(callback.data)
    parts = base.split(":")
    if len(parts) != 4 or not parts[3].isdigit():
        await callback.message.answer("❌ درخواست خرید نامعتبر است. دوباره از منوی نظامی تلاش کن.")
        return
    unit_key, qty = parts[2], int(parts[3])
    if qty <= 0 or qty > MAX_BUY_QTY or not M.get_unit(unit_key):
        await callback.message.answer("❌ تعداد یا نوع نیروی انتخاب‌شده نامعتبر است.")
        return
    uid = callback.from_user.id
    try:
        async with async_session() as session:
            ok, msg = await military_service.buy_unit(session, uid, unit_key, qty)
            if not ok:
                await session.rollback()
                await callback.message.answer(msg)
                return
            await session.commit()
            levels = await _levels(session, uid)
            player = await get_player(session, uid)
    except Exception:
        await callback.message.answer("❌ ثبت خرید انجام نشد. موجودی و صف پرورش را بررسی کن و دوباره تلاش کن.")
        return
    cat = M.get_unit(unit_key)["cat"]
    plevel = int(player.level or 1) if player else 1
    # پیام مستقل، حتی ��گر ادیت منوی قبلی در تلگرام ممکن نباشد.
    await callback.message.answer(msg)
    await safe_show(
        callback.message,
        f"<b>{M.CATEGORY_LABELS.get(cat, cat)}</b>\n\n{msg}",
        category_units_menu(uid, cat, plevel, levels),
    )


# --------------------------- ارتقا/آموزش ---------------------------
@router.callback_query(F.data.startswith("mil:upgrade"))
async def show_upgrade(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    uid = callback.from_user.id
    async with async_session() as session:
        await military_service.settle_training(session, uid)
        units = await military_service.get_units(session, uid)
        player = await get_player(session, uid)
        cash = int(player.cash or 0) if player else 0
    owned = [(u.unit_key, int(u.count), int(u.upgrade_level)) for u in units if u.count > 0]
    if not owned:
        await safe_show(callback.message, "اول چند نیرو بخر تا بتوان�� ارتقایشان بدهی.", military_back_menu(uid))
        await safe_answer(callback)
        return
    text = (
        "⬆️ <b>ارتقا و آموزش</b>\n\n"
        "هر ارتقا قدرتِ <b>همه‌ی</b> واحدهای آن نوع را بالا می‌برد (حمله/دفاع/جان).\n"
        "⚠️ پس از ارتقا، خریدِ واحدِ جدیدِ آن نوع گران‌تر می‌شود."
    )
    await safe_show(callback.message, text, upgrade_units_menu(uid, owned, cash))
    await safe_answer(callback)


@router.callback_query(F.data.startswith("mil:upgo:"))
async def upgrade_do(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    base, _ = split_owner(callback.data)
    unit_key = base.split(":", 2)[2]
    uid = callback.from_user.id
    async with async_session() as session:
        ok, msg = await military_service.upgrade_unit(session, uid, unit_key)
        if ok:
            await session.commit()
        units = await military_service.get_units(session, uid)
        player = await get_player(session, uid)
        cash = int(player.cash or 0) if player else 0
    await safe_answer(callback, msg, show_alert=True)
    owned = [(u.unit_key, int(u.count), int(u.upgrade_level)) for u in units if u.count > 0]
    await safe_show(callback.message, msg, upgrade_units_menu(uid, owned, cash))


# --------------------------- راهنما ---------------------------
@router.callback_query(F.data.startswith("mil:guide"))
async def show_guide(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    uid = callback.from_user.id
    text = (
        "📖 <b>چرخه‌ی برتری (سنگ‌کاغذ‌قیچی)</b>\n\n"
        "✈️ جنگنده ▸ شکارچیِ بمب‌افکن و برتریِ هوایی\n"
        "🛩️ بمب‌افکن ▸ ویرانگرِ زمین (تانک/سرباز)، اما طعمه‌ی جنگنده و پدافند\n"
        "🎯 پدافندِ هوایی ▸ فقط هوایی را می‌زند (ضدِ جنگنده/بمبر/موشک)\n"
        "🛡️ تانک ▸ مشتِ زمینی (ضدِ سرباز و پدافند)، اما آسیب‌پذیر از هوا\n"
        "🪖 سرباز ▸ ارزان؛ با تسلیحاتِ سبک قوی‌تر می‌شود\n"
        "🚀 موشک ▸ هم زمین هم هوا، ولی در برابرِ پدافند شکننده\n\n"
        "💡 ترکیبِ متوازن (زمینی + هوایی + پدافند) برنده‌ی نبردهاست؛ ارتشِ یک‌دست را آسان شکست می‌دهند."
    )
    from app.services import war_service
    text = text + "\n\n➖➖➖\n\n" + war_service.power_formula_help()
    await safe_show(callback.message, text, military_back_menu(uid))
    await safe_answer(callback)


# --------------------------- آوردگاهِ آزمایشی (شبیه‌سازیِ بدونِ تلفات) ---------------------------
@router.callback_query(F.data.startswith("mil:spar"))
async def sparring(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    uid = callback.from_user.id
    async with async_session() as session:
        stacks = await military_service.army_stacks(session, uid)
    if not stacks:
        await safe_answer(callback, "اول ارتشی بساز.", show_alert=True)
        return
    # یک دشمنِ فرضی متناسب با قدرتِ بازیکن می‌سازیم
    power = M.army_power(stacks)
    rng = random.Random()
    dummy = _make_dummy_army(power, rng)
    result = M.simulate_battle(stacks, dummy, rng)
    won = result["attacker_won"]
    lines = [
        "⚔️ <b>آوردگاهِ آزمایشی</b> (تلفاتِ واقعی ندارد)",
        "",
        f"دشمنِ فرضی با قدرتِ تقریبی {M.army_power(dummy):,} روبه‌رویت قرار گرفت.",
        f"🏁 نتیجه: {'🎉 پیروزی!' if won else '💀 شکست.'}",
        f"🔁 راندها: {result['rounds']}",
    ]
    for ln in result.get("log", [])[:3]:
        lines.append(ln)
    await safe_show(callback.message, "\n".join(lines), military_back_menu(uid))
    await safe_answer(callback)


def _make_dummy_army(target_power: int, rng: random.Random) -> list[tuple[str, int, int]]:
    """یک ارتشِ فرضیِ متوازن با قدرتِ نزدیک به target_power می‌سازد."""
    mix = ["rifleman", "tank", "aa_gun", "fighter", "rocket"]
    target = max(1000, int(target_power * rng.uniform(0.8, 1.2)))
    per = target // len(mix)
    army = []
    for k in mix:
        pw1 = max(1, M.unit_power(k, 1, 0))
        cnt = max(1, per // pw1)
        army.append((k, cnt, 0))
    return army


@router.callback_query(F.data.startswith("mil:barracksgo"))
async def barracks_upgrade_go(callback: CallbackQuery):
    if not await ensure_owner(callback):
        return
    async with async_session() as session:
        ok, msg = await military_service.start_barracks_upgrade(session, callback.from_user.id)
    # همیشه به تلگرام جواب بده تا دکمه در حالت loading نماند.
    await safe_answer(callback, msg, show_alert=True)
    await _show_home(callback.message, callback.from_user.id)


@router.callback_query(F.data.startswith("mil:barracks"))
async def barracks_upgrade(callback: CallbackQuery):
    if not await ensure_owner(callback):
        return
    from datetime import datetime
    async with async_session() as session:
        b, mx, levels, cap = await military_service.barracks_status(session, callback.from_user.id)
        if b.upgrading_until and b.upgrading_until > datetime.utcnow():
            text = f"🪖 سربازخانه لول {b.level}/{levels}\nظرفیت: {cap:,}/{mx:,}\n⏳ ارتقا در جریان است."
            can_upgrade = False
        elif b.level >= levels:
            text = f"🪖 سربازخانه در سقف ظرفیت {mx:,} واحد است."
            can_upgrade = False
        else:
            cost = M.barracks_upgrade_cost(b.level, mx)
            text = (
                f"🪖 سربازخانه لول {b.level}/{levels}\n"
                f"ظرفیت فعلی: {cap:,}\n"
                f"ظرفیت بعدی: {M.barracks_capacity(b.level + 1, mx):,}\n"
                f"💰 هزینه: {M.fmt_money(cost)}$\n"
                "⏳ زمان ارتقا: ۱ روز"
            )
            can_upgrade = True
    await safe_show(callback.message, text, barracks_upgrade_menu(callback.from_user.id, can_upgrade))
    await safe_answer(callback)


# --------------------------- 🏗️ صفِ پرورشِ نیرو (مرحله ۴۵) ---------------------------
async def _render_queue(message: Message, uid: int, page: int = 0, *, cancel_mode: bool = False, materialized: int = 0) -> None:
    async with async_session() as session:
        if not cancel_mode:
            materialized += await military_service.settle_training(session, uid)
        pending = await military_service.pending_training(session, uid)
    active = [q for q in pending if q["active"]]
    inactive = [q for q in pending if not q["active"]]
    page_items, page, total_pages = paginate(inactive, page, per=6)
    lines = ["🏗️ <b>صف پرورش نیرو</b>", ""]
    if materialized:
        lines += [f"✅ {materialized:,} واحد آماده شد و به ارتشت پیوست.", ""]
    lines.append(f"🟢 <b>صف‌های فعال ({len(active)}/10)</b>")
    if active:
        for q in active:
            lines.append(f"⛔ {q['name']} ×{q['qty']:,} — سربازخانه پر است؛ ارتقا بده یا صف را لغو کن." if q.get('blocked') else f"🔧 {q['name']} ×{q['qty']:,} — ⏳ {M.fmt_eta(q['remaining'])}")
    else:
        lines.append("— صف فعالی وجود ندارد —")
    lines += ["", "━━━━━━━━━━━━", "", f"⚪ <b>صف‌های غیرفعال ({len(inactive)})</b>"]
    if page_items:
        for q in page_items:
            lines.append(f"▫️ {q['name']} ×{q['qty']:,} — شروع پس از {M.fmt_eta(q['starts_in'])}")
    else:
        lines.append("— صف غیرفعالی وجود ندارد —")
    if cancel_mode:
        all_cancelable = active + page_items
        lines += ["", "برای لغو، روی صف موردنظر بزن. صف فعال یا غیرفعال لغو می‌شود و هزینهٔ پرداخت‌شده به حسابت برمی‌گردد."]
        markup = training_cancel_menu(uid, all_cancelable, page, total_pages)
    else:
        markup = training_queue_menu(uid, page, total_pages)
    await safe_show(message, "\n".join(lines), markup)


@router.callback_query(F.data.startswith("mil:queue"))
async def show_queue(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback): return
    base, _ = split_owner(callback.data)
    parts = base.split(":")
    page = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0
    await _render_queue(callback.message, callback.from_user.id, page)
    await safe_answer(callback)


@router.callback_query(F.data.startswith("mil:qcancelmenu:"))
async def cancel_queue_menu(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback): return
    base, _ = split_owner(callback.data)
    parts = base.split(":")
    page = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0
    await _render_queue(callback.message, callback.from_user.id, page, cancel_mode=True)
    await safe_answer(callback)


@router.callback_query(F.data.startswith("mil:qcancel:"))
async def cancel_queue(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback): return
    base, _ = split_owner(callback.data)
    parts = base.split(":")
    if len(parts) != 4 or not parts[2].isdigit():
        await safe_answer(callback, "❌ درخواست نامعتبر است.", show_alert=True); return
    queue_id = int(parts[2]); page = int(parts[3]) if parts[3].isdigit() else 0
    async with async_session() as session:
        ok, msg = await military_service.cancel_inactive_training(session, callback.from_user.id, queue_id)
        if ok: await session.commit()
        else: await session.rollback()
    await _render_queue(callback.message, callback.from_user.id, page, cancel_mode=True)
    await safe_answer(callback, msg, show_alert=not ok)


# --------------------------- 🆕 مرحله ۴۶ — تعدادِ دلخواهِ نیرو ---------------------------
MAX_BUY_QTY = 1_000_000


@router.callback_query(F.data.startswith("mil:buyn:"))
async def buy_manual_qty(callback: CallbackQuery, state: FSMContext) -> None:
    if not await ensure_owner(callback):
        return
    base, _ = split_owner(callback.data)
    unit_key = base.split(":", 2)[2]
    u = M.get_unit(unit_key)
    if not u:
        await safe_answer(callback, "❌ نیروی نامعتبر.", show_alert=True)
        return
    await state.set_state(MilitaryStates.entering_qty)
    await state.update_data(unit_key=unit_key)
    await callback.message.answer(
        f"⌨️ چند واحد {u['name']} می‌خواهی؟ عدد را بفرست (مثلاً 250).\n"
        "🏗️ هر واحد به‌محضِ ساخته‌شدن به ارتشت اضافه می‌شود."
    )
    await safe_answer(callback)


@router.message(MilitaryStates.entering_qty)
async def buy_manual_qty_do(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    unit_key = data.get("unit_key") or ""
    raw = (message.text or "").strip().replace(",", "").replace("٬", "")
    raw = raw.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789"))
    if not raw.isdigit():
        await message.reply("❌ فقط عدد بفرست.")
        return
    qty = int(raw)
    if qty <= 0 or qty > MAX_BUY_QTY:
        await message.reply(f"❌ تعداد باید بینِ 1 تا {MAX_BUY_QTY:,} باشد.")
        return
    await state.clear()
    uid = message.from_user.id
    async with async_session() as session:
        ok, msg = await military_service.buy_unit(session, uid, unit_key, qty)
        if ok:
            await session.commit()
    await message.reply(msg)
    if ok:
        await _show_home(message, uid)

@router.callback_query(F.data.startswith("mil:hospital"))
async def mil_hospital_cb(callback: CallbackQuery):
    """🏥 بیمارستان / تعمیر — فهرستِ مجروحانِ هر نبرد.

    🆕 v1.7.6.3 — درمان دیگر خودکار نیست. قبلاً همین دکمه فوراً
    ۴۰–۸۰٪ از تلفاتِ «آخرین» جنگ را خودش درمان می‌کرد. حالا فقط
    «فهرست» را نشان می‌دهد: هر نبرد یک ردیفِ جداگانه با مهلتِ ۲۴
    ساعتهٔ خودش دارد و کاربر باید خودش ردیف را باز کند و هزینه را
    بپردازد؛ وگرنه پس از ۲۴ ساعت نیروهای آن ردیف می‌میرند.

    🐞 v1.7.6.3 — رفعِ باگِ «دکمه روی لوپ گیر می‌کند»:
      ۱) ریشهٔ ماجرا در hospital_heal بود که با UnboundLocalError می‌ترکید
         (در battle_live.py اصلاح شد). چون callback.answer() پس از آن صدا
         زده می‌شد، تلگرام هیچ پاسخی نمی‌گرفت و دکمه تا ابد در حالتِ
         «در حالِ بارگذاری» می‌ماند.
      ۲) حالا اول به تلگرام پاسخ داده می‌شود و بعد کارِ سنگین انجام
         می‌شود؛ پس هر خطای دیگری هم پیش بیاید، دکمه معلق نمی‌ماند.
      ۳) هر استثنای غیرمنتطره گرفته و به کاربر گزارش می‌شود، نه اینکه
         بی‌صدا گم شود.
      ۴) با safe_show نمایش داده می‌شود؛ قبلاً اگر متن عوض نشده بود
         تلگرام خطای «message is not modified» می‌داد و هر بار یک پیامِ
         تکراریِ تازه فرستاده می‌شد.
    """
    if not await ensure_owner(callback):
        return
    uid = callback.from_user.id
    # اول چرخانِ دکمه را خاموش کن تا در هیچ حالتی معلق نماند.
    await safe_answer(callback)
    try:
        async with async_session() as session:
            wards = await HS.list_wards(session, uid)
            dead = await HS.recent_dead(session, uid, limit=3)
            await session.commit()
        text = _hospital_list_text(wards, dead)
        markup = hospital_list_menu(uid, wards)
    except Exception as e:
        text = f"🏥 <b>بیمارستان / تعمیر</b>\n\n⚠️ خطای غیرمنتظره: {e}"
        markup = military_back_menu(uid)
    await safe_show(callback.message, text, markup)


def _hospital_list_text(wards, dead=None) -> str:
    """متنِ صفحهٔ فهرستِ بیمارستان.

    🆕 v1.7.6.4 — ردیف‌های «در حالِ درمان» دیگر غیب نمی‌شوند؛ در یک
    بخشِ جداگانه با تایمرِ باقی‌مانده تا پایانِ درمان نمایش داده می‌شوند.
    """
    wards = list(wards or [])
    waiting = [w for w in wards if str(w.status) == "wounded"]
    healing = [w for w in wards if str(w.status) == "healing"]

    lines = ["🏥 <b>بیمارستان / تعمیرگاه</b>", ""]

    if not wards:
        lines.append(
            "📭 الان هیچ نیروی مجروحی نداری و چیزی هم در حالِ درمان نیست."
        )
        lines.append("")
        lines.append(
            "بعد از هر نبرد، مجروحانِ همان نبرد اینجا یک <b>ردیفِ جداگانه</b> "
            f"می‌گیرند و <b>{HS.HEAL_DEADLINE_HOURS} ساعت</b> فرصت داری "
            "هزینهٔ درمانشان را بدهی."
        )
        lines.append(
            "⏳ خودِ درمان پس از پرداخت بینِ "
            f"<b>{HS.HEAL_MIN_HOURS} تا {HS.HEAL_MAX_HOURS} ساعت</b> طول می‌کشد."
        )
    else:
        if waiting:
            total_units = sum(int(w.unit_count or 0) for w in waiting)
            total_cost = sum(int(w.cost or 0) for w in waiting)
            lines.append(
                f"🩹 <b>در انتظارِ پرداخت: {len(waiting)} ردیف</b>"
            )
            lines.append(f"🪖 مجموعِ واحدها: <b>{total_units:,}</b>")
            lines.append(f"💰 مجموعِ هزینه: <b>{total_cost:,}$</b>")
            lines.append("")
            for w in waiting:
                mark = "🔴" if HS.is_urgent(w) else "⏳"
                rival = w.opponent_name or "—"
                lines.append(
                    f"{mark} <b>#{int(w.id)}</b> — نبرد با {rival}\n"
                    f" 🪖 {int(w.unit_count or 0):,} واحد · "
                    f"💰 {int(w.cost or 0):,}$ · "
                    f"⏳ مهلت: {HS.remaining_text(w)}"
                )
            lines.append("")
            lines.append(
                f"⚠️ هر ردیف <b>{HS.HEAL_DEADLINE_HOURS} ساعت</b> مهلتِ پرداخت دارد؛ "
                "پس از آن نیروهای همان ردیف <b>می‌میرند</b>."
            )

        if healing:
            if waiting:
                lines.append("")
            heal_units = sum(int(w.unit_count or 0) for w in healing)
            lines.append(f"🏥 <b>در حالِ درمان: {len(healing)} ردیف</b>")
            lines.append(f"🪖 در درمان: <b>{heal_units:,}</b> واحد")
            lines.append("")
            for w in healing:
                rival = w.opponent_name or "—"
                left = HS.heal_seconds_left(w)
                mark = "✅" if left <= 0 else "🏥"
                lines.append(
                    f"{mark} <b>#{int(w.id)}</b> — نبرد با {rival}\n"
                    f" 🪖 {int(w.unit_count or 0):,} واحد · "
                    f"⏳ تا پایانِ درمان: <b>{HS.heal_remaining_text(w)}</b>"
                )
            lines.append("")
            lines.append(
                "🔔 هزینهٔ این ردیف‌ها پرداخت شده و دیگر نمی‌میرند. "
                "پس از پایانِ تایمر، نیروها خودبه‌خود به ارتش برمی‌گردند "
                "و خبرت می‌دهم."
            )

        lines.append("")
        lines.append(
            "👇 روی هر ردیف بزن تا جزئیاتش را ببینی."
        )

    if dead:
        lines.append("")
        lines.append("⚰️ <b>از دست‌رفته‌های اخیر</b>")
        for w in dead:
            lines.append(
                f"• #{int(w.id)} — {int(w.unit_count or 0):,} واحد"
            )
    return "\n".join(lines)


def _hospital_detail_text(ward) -> str:
    """متنِ جزئیاتِ یک ردیفِ مجروحان.

    🆕 v1.7.6.4 — دو افزوده:
      ۱) وضعیتِ «در حالِ درمان» با تایمرِ باقی‌مانده.
      ۲) خطِ شفافیتِ «از X تلفات، Y مجروح = Z٪» تا کاربر بتواند
         راستی‌آزمایی کند که سقفِ ۴۰–۸۰٪ رعایت شده است.
    """
    units = HS.units_of(ward)
    status = str(ward.status)
    status_fa = {
        "wounded": "🩹 در انتظارِ پرداخت",
        "healing": "🏥 در حالِ درمان",
        "healed": "✅ درمان‌شده",
        "dead": "⚰️ از دست رفته",
    }.get(status, status)
    lines = [
        f"🏥 <b>ردیفِ مجروحان #{int(ward.id)}</b>",
        "",
        f"⚔️ نبرد با: <b>{ward.opponent_name or '—'}</b>",
        f"📌 وضعیت: {status_fa}",
        HS.wounded_ratio_text(ward),
        f"📋 {HS.units_text(units)}",
        f"💰 هزینهٔ درمان: <b>{int(ward.cost or 0):,}$</b>",
    ]
    if status == "wounded":
        lines.append(
            f"⏳ مهلتِ پرداخت: <b>{HS.remaining_text(ward)}</b>"
        )
        lines.append("")
        lines.append(
            "⏳ پس از پرداخت، درمان بینِ "
            f"<b>{HS.HEAL_MIN_HOURS} تا {HS.HEAL_MAX_HOURS} ساعت</b> طول می‌کشد."
        )
        lines.append(
            "⚠️ اگر تا پایانِ مهلت پرداخت نکنی، "
            "این نیروها <b>می‌میرند</b>."
        )
    elif status == "healing":
        hours = int(getattr(ward, "heal_hours", 0) or 0)
        lines.append("")
        if hours:
            lines.append(
                f"🩺 مدتِ درمانِ این ردیف: <b>{hours} ساعت</b>"
            )
        left = HS.heal_seconds_left(ward)
        if left <= 0:
            lines.append(
                "✅ درمان تمام شده — نیروها در اولین بروزرسانی تحویل می‌شوند."
            )
        else:
            lines.append(
                f"⏳ تا پایانِ درمان: <b>{HS.heal_remaining_text(ward)}</b>"
            )
        lines.append("")
        lines.append(
            "🔔 هزینه پرداخت شده و این نیروها دیگر نمی‌میرند. "
            "پس از پایانِ تایمر، خودبه‌خود به ارتش اضافه می‌شوند."
        )
    elif status == "healed":
        lines.append("")
        lines.append(
            "✅ این ردیف درمان شده و نیروها به ارتش بازگشته‌اند."
        )
    elif status == "dead":
        lines.append("")
        lines.append(
            "⚰️ مهلتِ پرداخت تمام شد و این نیروها برای همیشه از دست رفتند."
        )
    return "\n".join(lines)


@router.callback_query(F.data.startswith("mil:hosp:v:"))
async def mil_hospital_view_cb(callback: CallbackQuery):
    """🆕 v1.7.6.3 — جزئیاتِ یک ردیفِ مجروحان."""
    if not await ensure_owner(callback):
        return
    uid = callback.from_user.id
    await safe_answer(callback)
    base, _owner = split_owner(callback.data)
    try:
        wid = int(base.split(":")[3])
    except Exception:
        await safe_show(callback.message, "❌ شناسهٔ ردیف نامعتبر است.", military_back_menu(uid))
        return
    try:
        async with async_session() as session:
            await HS.sweep_expired(session, uid=uid)
            ward = await HS.get_ward(session, uid, wid)
            await session.commit()
        if ward is None:
            text = "🏥 <b>بیمارستان</b>\n\n❌ این ردیف پیدا نشد."
            markup = military_back_menu(uid)
        else:
            text = _hospital_detail_text(ward)
            markup = hospital_detail_menu(uid, wid, payable=(str(ward.status) == "wounded"))
    except Exception as e:
        text = f"🏥 <b>بیمارستان</b>\n\n⚠️ خطای غیرمنتظره: {e}"
        markup = military_back_menu(uid)
    await safe_show(callback.message, text, markup)


@router.callback_query(F.data.startswith("mil:hosp:pay:"))
async def mil_hospital_pay_cb(callback: CallbackQuery):
    """🆕 v1.7.6.3 — پرداختِ هزینهٔ درمانِ یک ردیف (دستی)."""
    if not await ensure_owner(callback):
        return
    uid = callback.from_user.id
    await safe_answer(callback)
    base, _owner = split_owner(callback.data)
    try:
        wid = int(base.split(":")[3])
    except Exception:
        await safe_show(callback.message, "❌ شناسهٔ ردیف نامعتبر است.", military_back_menu(uid))
        return
    ok = False
    wards = []
    try:
        async with async_session() as session:
            ok, msg = await HS.heal_ward(session, uid, wid)
            wards = await HS.list_wards(session, uid)
            await session.commit()
    except Exception as e:
        msg = f"⚠️ خطای غیرمنتظره در درمان: {e}"
    text = "🏥 <b>بیمارستان / تعمیر</b>\n\n" + str(msg)
    if ok:
        if wards:
            text += f"\n\n🩹 هنوز <b>{len(wards)}</b> ردیفِ درمان‌نشده داری."
        else:
            text += "\n\n✅ دیگر هیچ مجروحی نداری."
        markup = hospital_list_menu(uid, wards)
    else:
        markup = hospital_detail_menu(uid, wid, payable=(not ok))
    await safe_show(callback.message, text, markup)

