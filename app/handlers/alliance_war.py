# -*- coding: utf-8 -*-
"""v1.7.9.1 — هندلرهای ارتش و جنگِ زنده‌ی اتحادیه. پیشوندِ کالبک: alw:

بخش‌ها: سربازخانه (تولید اسکادرانی دستی/خودکار + ارتقا)، صندوق (واریز برای همه‌ی
اعضا + امتیازِ مشارکت)، نبردِ زنده (فاز/آتش‌بس)، بیمارستان، رنکینگِ کاپ و راهنما.
"""
from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.data import alliance as A
from app.data import alliance_military as AM
from app.data import military as M  # 🆕 v1.8.2.0 — آمار/مزایا/زمان از واحدِ پایه
from app.keyboards import alliance_menu as ALKB  # 🆕 v1.8.2.0 — منوهای سربازخانه‌ی اتحادیه
from app.database.engine import async_session
from app.handlers.profile import get_player
from app.services import alliance_battle as AB
from app.services import alliance_military_service as AMS
from app.services import alliance_service
from app.states import AllianceStates
from app.utils.ui import (
    CANCEL_HINT,
    ensure_owner,
    handle_cancel_word,
    paginate,  # 🆕 v1.8.2.0
    safe_answer,
    safe_show,
    split_owner,
    with_owner,
)

router = Router(name="alliance_war")

log = logging.getLogger(__name__)


# --------------------------- کمکی‌ها ---------------------------
def _kb() -> InlineKeyboardBuilder:
    return InlineKeyboardBuilder()


async def _member_and_alliance(session, uid: int):
    membership = await alliance_service.get_membership(session, uid)
    if membership is None:
        return None, None
    al = await alliance_service.get_alliance(session, membership.alliance_id)
    return membership, al


async def _can_manage(session, membership) -> bool:
    """ارتقا/خرید فقط برای رئیس یا معاونِ دارای دسترسیِ ارتقا."""
    return await alliance_service.has_permission(session, membership, A.PERM_UPGRADE)


def _back_kb(uid: int):
    b = _kb()
    b.button(text="↩️ بازگشت به اتحادیه", callback_data=with_owner("all:hub", uid))
    b.adjust(1)
    return b.as_markup()


def _barracks_kb(uid: int, can_manage: bool, auto_on: bool, queued_count: int = 0):
    """🆕 v1.8.2.0 — کیبوردِ هاب به app/keyboards/alliance_menu.py منتقل شد (ساختارِ بخشِ نظامی)."""
    return ALKB.alw_barracks_home_menu(uid, can_manage, auto_on, queued_count)


# --------------------------- سربازخانه ---------------------------
@router.callback_query(F.data.startswith("alw:bk"))
async def barracks_home(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    uid = callback.from_user.id
    async with async_session() as session:
        membership, al = await _member_and_alliance(session, uid)
        if al is None:
            await safe_answer(callback, "اول باید عضوِ اتحادیه باشی.", show_alert=True)
            return
        b = await AMS.get_or_create_barracks(session, al.id)
        await AMS.settle_training(session, al.id)
        stacks = await AMS.stacks(session, al.id)
        power = await AMS.army_power(session, al.id)
        cap = AM.barracks_capacity(b.level)
        used = sum(c for _k, c, _lv in stacks)
        queued_rows = await AMS.pending_training(session, al.id)
        queued = sum(int(r.units or 0) for r in queued_rows)
        can_manage = await _can_manage(session, membership)
        auto_on = bool(int(b.auto_enabled or 0))
        bk_level = int(b.level or 1)
        treasury = int(al.treasury or 0)
        await session.commit()
    lines = [
        "🏰 <b>سربازخانه‌ی اتحادیه</b>",
        "",
        f"🏗️ سطح: {bk_level}  |  ظرفیت: {used + queued:,}/{cap:,}",
        f"💥 قدرتِ ارتش: <b>{power:,}</b>",
        f"💰 صندوق: {treasury:,}$",
        "",
        "🪖 <b>نیروها:</b>",
    ]
    from app.utils.table import render_table, table_mode_on
    if await table_mode_on("alliance_barracks"):
        if stacks:
            _rows = [[(AM.get_unit(key) or {}).get("name", key), f"{cnt:,}", str(lv)] for key, cnt, lv in stacks]
            lines.append(render_table(["نیرو", "تعداد", "سطح"], _rows))
        else:
            lines.append("• هنوز نیرویی ساخته نشده.")
    else:
        if stacks:
            for key, cnt, lv in stacks:
                u = AM.get_unit(key)
                name = u["name"] if u else key
                lines.append(f"• {name} ×{cnt:,} (سطح {lv})")
        else:
            lines.append("• هنوز نیرویی ساخته نشده.")
    if queued_rows:
        lines += ["", "⏳ <b>در صفِ تولید:</b>"]
        from datetime import datetime as _dt
        from app.data.battle_report import fmt_remaining
        if await table_mode_on("alliance_barracks"):
            _rows = []
            for r in queued_rows[:6]:
                u = AM.get_unit(r.unit_key)
                left = max(0, int((r.ready_at - _dt.utcnow()).total_seconds()))
                _rows.append([(u["name"] if u else r.unit_key), f"{int(r.units or 0):,}", fmt_remaining(left)])
            lines.append(render_table(["نیرو", "تعداد", "آماده تا"], _rows))
        else:
            for r in queued_rows[:6]:
                u = AM.get_unit(r.unit_key)
                left = max(0, int((r.ready_at - _dt.utcnow()).total_seconds()))
                lines.append(f"• {(u['name'] if u else r.unit_key)} ×{int(r.units or 0):,} — آماده تا {fmt_remaining(left)}")
    await safe_show(callback.message, "\n".join(lines), _barracks_kb(uid, can_manage, auto_on, len(queued_rows)))
    await safe_answer(callback)


# --------------------------- 🆕 v1.8.2.0 — تولیدِ دسته‌بندی‌شده (مثلِ بخشِ نظامیِ عادی) ---------------------------
# منوی کشوییِ قدیمی (alw:prod) با ساختارِ کاملِ بخشِ نظامی جایگزین شد:
#   alw:shop → دسته‌ها | alw:cat:<cat> → نیروهای دسته | alw:buy:<unit> → انتخابِ تعدادِ اسکادران
#   alw:buyq:<unit>:<n> → پیش‌نمایش/تأیید | alw:buyok:<unit>:<n> → ساخت | alw:buyn:<unit> → عددِ دستی
#   alw:queue[:page] → صفِ تولید (پیمایشِ واقعی + لغو با بازگشتِ هزینه) | alw:upgm → ارتقا و آموزش
# نتیجه: هر دسته جایِ خودش را دارد؛ پس از هر خرید/ارتقا به «همان بخش» برمی‌گردی (نه صفحه‌ی
# اول)؛ تعدادِ اسکادران را خودت طبقِ ظرفیتِ سربازخانه و صندوق انتخاب می‌کنی و هر تعداد بچ
# پشت‌سرِ هم در صف می‌نشیند.


async def _prod_ctx(session, uid: int):
    """زمینه‌ی مشترکِ تولید: عضویت/اتحادیه/سربازخانه/ظرفیتِ خالی/صندوق (به‌صورتِ مقدارِ ساده).

    settle_training هم اینجا اجرا و commit می‌شود تا نیروهای آماده بی‌درنگ به پشته بپیوندند
    و ظرفیتِ خالی همیشه به‌روز باشد.
    """
    membership, al = await _member_and_alliance(session, uid)
    if al is None:
        return None
    b = await AMS.get_or_create_barracks(session, al.id)
    await AMS.settle_training(session, al.id)
    stacks = await AMS.stacks(session, al.id)
    ctx = {
        "membership": membership,
        "al": al,
        "stacks": stacks,
        "counts": {k: c for k, c, _lv in stacks},
        "free": await AMS.capacity_free(session, al.id),
        "treasury": int(al.treasury or 0),
        "bk_level": int(b.level or 1),
    }
    await session.commit()
    return ctx


async def _render_category(message: Message, uid: int, cat: str) -> None:
    """متن + منوی نیروهای یک دسته — بینِ هندلرها و پس از خرید مشترک است (رفعِ باگِ برگشت به صفحه‌ی اول)."""
    async with async_session() as session:
        ctx = await _prod_ctx(session, uid)
        if ctx is None:
            await safe_show(message, "اول باید عضوِ اتحادیه باشی.", _back_kb(uid))
            return
    lines = [f"<b>{AM.CATEGORY_LABELS.get(cat, cat)}</b>", ""]
    for k in AM.units_in_category(cat):
        u = AM.get_unit(k)
        bu = M.get_unit(u["base"]) or {}
        lines.append(
            f"{u['name']} — 🗡{u['atk']} 🛡{u['def']} ❤️{u['hp']}\n"
            f"   اسکادرانِ {u['squad']} نفره | 💲 هر اسکادران: {AM.squad_cost(k, 1):,}$ | "
            f"⏳ {M.fmt_eta(AM.train_seconds(k, 1))}\n"
            f"   ➕ {bu.get('pros', '—')}\n"
            f"   ➖ {bu.get('cons', '—')}"
        )
    lines.append(f"\n💰 صندوق: {ctx['treasury']:,}$  |  ظرفیتِ خالی: {ctx['free']:,}")
    await safe_show(
        message,
        "\n".join(lines),
        ALKB.alw_category_units_menu(uid, cat, ctx["bk_level"], ctx["counts"]),
    )


@router.callback_query(F.data.startswith("alw:prod"))
async def prod_legacy(callback: CallbackQuery) -> None:
    """سازگاری با منوهای قدیمیِ «تولید نیرو»: هدایت به فروشگاهِ دسته‌بندی‌شده."""
    await shop_categories(callback)


@router.callback_query(F.data.startswith("alw:shop"))
async def shop_categories(callback: CallbackQuery) -> None:
    """🏭 تولیدِ اسکادرانی — انتخابِ دسته (مثلِ mil:shop)."""
    if not await ensure_owner(callback):
        return
    uid = callback.from_user.id
    async with async_session() as session:
        ctx = await _prod_ctx(session, uid)
        if ctx is None:
            await safe_answer(callback, "اول باید عضوِ اتحادیه باشی.", show_alert=True)
            return
        if not await _can_manage(session, ctx["membership"]):
            await safe_answer(callback, "🔒 تولید/خرید فقط با رئیس یا معاونِ دارای دسترسی است.", show_alert=True)
            return
    text = (
        "🏭 <b>تولیدِ اسکادرانی</b>\n\n"
        "یک دسته را انتخاب کن؛ هر دسته نیروهای مخصوصِ خودش را دارد.\n"
        f"💰 صندوق: {ctx['treasury']:,}$  |  ظرفیتِ خالی: {ctx['free']:,}\n"
        "هزینه‌ها ۵× جنگِ عادی محاسبه و از صندوقِ اتحادیه کم می‌شود."
    )
    await safe_show(callback.message, text, ALKB.alw_shop_categories_menu(uid))
    await safe_answer(callback)


@router.callback_query(F.data.startswith("alw:cat:"))
async def shop_category(callback: CallbackQuery) -> None:
    """نیروهای یک دسته (مثلِ mil:cat) — پس از خرید هم به همین‌جا برمی‌گردی."""
    if not await ensure_owner(callback):
        return
    base, _ = split_owner(callback.data)
    parts = base.split(":")
    cat = parts[2] if len(parts) > 2 else ""
    if cat not in AM.CATEGORY_ORDER:
        await safe_answer(callback, "دسته‌ی نامعتبر.", show_alert=True)
        return
    await _render_category(callback.message, callback.from_user.id, cat)
    await safe_answer(callback)


@router.callback_query(F.data.startswith("alw:locked"))
async def locked_cb(callback: CallbackQuery) -> None:
    await safe_answer(callback, "🔒 این واحد به ارتقای سربازخانه نیاز دارد.", show_alert=True)


@router.callback_query(F.data.startswith("alw:noop"))
async def noop_cb(callback: CallbackQuery) -> None:
    await safe_answer(callback)


# --------------------------- خرید: انتخابِ تعدادِ اسکادران ---------------------------
@router.callback_query(F.data.startswith("alw:buy:"))
async def buy_choose_squads(callback: CallbackQuery) -> None:
    """انتخابِ تعدادِ اسکادران (مثلِ mil:buy) — دیگر هر کلیک فقط یک اسکادران نمی‌سازد؛
    کاربر تعداد را طبقِ ظرفیتِ سربازخانه و صندوق انتخاب می‌کند."""
    if not await ensure_owner(callback):
        return
    base, _ = split_owner(callback.data)
    parts = base.split(":")
    unit_key = parts[2] if len(parts) > 2 else ""
    u = AM.get_unit(unit_key)
    if not u:
        await safe_answer(callback, "❌ واحد نامعتبر.", show_alert=True)
        return
    uid = callback.from_user.id
    async with async_session() as session:
        ctx = await _prod_ctx(session, uid)
        if ctx is None:
            await safe_answer(callback, "اول باید عضوِ اتحادیه باشی.", show_alert=True)
            return
        if not await _can_manage(session, ctx["membership"]):
            await safe_answer(callback, "🔒 تولید/خرید فقط با رئیس یا معاونِ دارای دسترسی است.", show_alert=True)
            return
    if ctx["bk_level"] < int(u["unlock_barracks"]):
        await safe_answer(
            callback,
            f"🔒 این واحد به سربازخانه‌ی سطح {u['unlock_barracks']} نیاز دارد (فعلی: {ctx['bk_level']}).",
            show_alert=True,
        )
        return
    max_sq = AM.max_squads_possible(unit_key, ctx["free"], ctx["treasury"])
    if max_sq <= 0:
        await safe_answer(
            callback,
            "ظرفیتِ خالیِ سربازخانه یا بودجه‌ی صندوق برای حتی یک اسکادران کافی نیست.",
            show_alert=True,
        )
        return
    text = (
        f"{u['name']}\n\n"
        f"👥 هر اسکادران: {int(u['squad'])} نیرو\n"
        f"💲 هر اسکادران: {AM.squad_cost(unit_key, 1):,}$ (۵× جنگِ عادی)\n"
        f"⏳ زمانِ هر اسکادران: {M.fmt_eta(AM.train_seconds(unit_key, 1))}\n"
        f"🗡 حمله: {u['atk']} | 🛡 دفاع: {u['def']} | ❤️ جان: {u['hp']}\n\n"
        f"💰 صندوق: {ctx['treasury']:,}$ | ظرفیتِ خالی: {ctx['free']:,}\n"
        f"🔢 حداکثرِ قابلِ ساختِ الان: <b>{max_sq}</b> اسکادران ({max_sq * int(u['squad']):,} نیرو)\n\n"
        "چند اسکادران می‌سازی؟"
    )
    await safe_show(
        callback.message,
        text,
        ALKB.alw_buy_squads_menu(uid, unit_key, AM.squad_preset_options(unit_key, max_sq), max_sq),
    )
    await safe_answer(callback)


@router.callback_query(F.data.startswith("alw:buyq:"))
async def buy_preview(callback: CallbackQuery) -> None:
    """پیش‌نمایش/تأیید (مثلِ mil:buyq) — ظرفیت و صندوق اینجا و دوباره در سرویس چک می‌شود."""
    if not await ensure_owner(callback):
        return
    await safe_answer(callback)
    base, _ = split_owner(callback.data)
    parts = base.split(":")
    if len(parts) != 4 or not parts[3].isdigit() or not AM.get_unit(parts[2]):
        await safe_show(callback.message, "❌ درخواستِ تولید نامعتبر است. از منوی سربازخانه دوباره تلاش کن.", _back_kb(callback.from_user.id))
        return
    unit_key, squads = parts[2], int(parts[3])
    u = AM.get_unit(unit_key)
    uid = callback.from_user.id
    async with async_session() as session:
        ctx = await _prod_ctx(session, uid)
        if ctx is None:
            await safe_show(callback.message, "اول باید عضوِ اتحادیه باشی.", _back_kb(uid))
            return
        if not await _can_manage(session, ctx["membership"]):
            await safe_show(callback.message, "🔒 تولید/خرید فقط با رئیس یا معاونِ دارای دسترسی است.", _back_kb(uid))
            return
    squad = int(u["squad"])
    units = squads * squad
    cost = AM.squad_cost(unit_key, squads)
    secs = AM.train_seconds(unit_key, squads)
    max_sq = AM.max_squads_possible(unit_key, ctx["free"], ctx["treasury"])
    header = (
        f"🏭 <b>تأیید تولیدِ اسکادرانی</b>\n"
        f"{u['name']} × {squads} اسکادران ({units:,} نیرو)\n"
        f"💲 هر اسکادران: {AM.squad_cost(unit_key, 1):,}$\n"
        f"💰 هزینه‌ی نهایی: {cost:,}$ از صندوق\n"
        f"🏦 صندوق: {ctx['treasury']:,}$\n"
        f"🏗️ ظرفیت: خالی {ctx['free']:,} (نیاز: {units:,})\n"
        f"⏳ آماده تا: {M.fmt_eta(secs)}"
    )
    if squads <= 0:
        await safe_show(callback.message, "❌ تعداد نامعتبر است.", _back_kb(uid))
        return
    if ctx["bk_level"] < int(u["unlock_barracks"]):
        await safe_show(
            callback.message,
            f"{header}\n\n🔒 این واحد به سربازخانه‌ی سطح {u['unlock_barracks']} نیاز دارد (فعلی: {ctx['bk_level']}).",
            ALKB.alw_buy_squads_menu(uid, unit_key, AM.squad_preset_options(unit_key, max_sq), max_sq),
        )
        return
    if ctx["treasury"] < cost:
        await safe_show(
            callback.message,
            f"{header}\n\n❌ صندوق کافی نیست — <b>{cost - ctx['treasury']:,}$</b> کم است.\n"
            "💡 تعدادِ کمتری انتخاب کن یا اول به صندوق واریز کن.",
            ALKB.alw_buy_squads_menu(uid, unit_key, AM.squad_preset_options(unit_key, max_sq), max_sq),
        )
        return
    if units > ctx["free"]:
        await safe_show(
            callback.message,
            f"{header}\n\n🪖 ظرفیتِ سربازخانه کافی نیست؛ فقط جای <b>{ctx['free']:,}</b> نیروی دیگر هست.\n"
            "💡 سربازخانه را ارتقا بده یا تعدادِ کمتری بساز.",
            ALKB.alw_buy_squads_menu(uid, unit_key, AM.squad_preset_options(unit_key, max_sq), max_sq),
        )
        return
    await safe_show(
        callback.message,
        f"{header}\n\n✅ تولید را تأیید می‌کنی؟",
        ALKB.alw_buy_confirm_menu(uid, unit_key, squads),
    )


@router.callback_query(F.data.startswith("alw:buyok:"))
async def buy_do(callback: CallbackQuery) -> None:
    """ساختِ نهایی (مثلِ mil:buyok) — پاسخِ فوری + بازگشت به «همان دسته»، نه صفحه‌ی اول."""
    if not await ensure_owner(callback):
        return
    await safe_answer(callback, "⏳ در حال ثبت تولید...")
    base, _ = split_owner(callback.data)
    parts = base.split(":")
    if len(parts) != 4 or not parts[3].isdigit() or int(parts[3]) <= 0 or not AM.get_unit(parts[2]):
        await callback.message.answer("❌ درخواستِ تولید نامعتبر است. دوباره از منوی سربازخانه تلاش کن.")
        return
    unit_key, squads = parts[2], int(parts[3])
    uid = callback.from_user.id
    try:
        async with async_session() as session:
            membership, al = await _member_and_alliance(session, uid)
            if al is None or not await _can_manage(session, membership):
                await callback.message.answer("🔒 تولید/خرید فقط با رئیس یا معاونِ دارای دسترسی است.")
                return
            ok, msg = await AMS.buy_squadron(session, al, unit_key, squads)
            if not ok:
                await session.rollback()
                await callback.message.answer(msg)
                return
            await session.commit()
    except Exception:
        log.exception("alliance barracks buy failed | uid=%s unit=%s squads=%s", uid, unit_key, squads)
        await callback.message.answer("❌ ثبت تولید انجام نشد. صندوق و ظرفیت را بررسی کن و دوباره تلاش کن.")
        return
    await callback.message.answer(msg)
    # 🐞 رفعِ باگ: قبلاً پس از خرید به صفحه‌ی اولِ منوی کشویی برمی‌گشتی؛ حالا همان دسته باز می‌شود.
    await _render_category(callback.message, uid, AM.get_unit(unit_key)["cat"])


@router.callback_query(F.data.startswith("alw:buyn:"))
async def buy_manual_start(callback: CallbackQuery, state: FSMContext) -> None:
    """⌨️ تعدادِ دلخواهِ اسکادران (مثلِ mil:buyn) — سقفش ظرفیتِ سربازخانه و صندوق است."""
    if not await ensure_owner(callback):
        return
    base, _ = split_owner(callback.data)
    parts = base.split(":")
    unit_key = parts[2] if len(parts) > 2 else ""
    u = AM.get_unit(unit_key)
    if not u:
        await safe_answer(callback, "❌ واحد نامعتبر.", show_alert=True)
        return
    uid = callback.from_user.id
    async with async_session() as session:
        ctx = await _prod_ctx(session, uid)
        if ctx is None or not await _can_manage(session, ctx["membership"]):
            await safe_answer(callback, "🔒 تولید/خرید فقط با رئیس یا معاونِ دارای دسترسی است.", show_alert=True)
            return
    max_sq = AM.max_squads_possible(unit_key, ctx["free"], ctx["treasury"])
    if max_sq <= 0:
        await safe_answer(callback, "ظرفیتِ خالی یا بودجه‌ی صندوق برای حتی یک اسکادران کافی نیست.", show_alert=True)
        return
    await state.set_state(AllianceStates.buying_squads)
    await state.update_data(unit_key=unit_key)
    await safe_show(
        callback.message,
        f"⌨️ چند اسکادران {u['name']} می‌سازی؟ عدد را بفرست (حداکثر {max_sq}).\n"
        f"هر اسکادران = {int(u['squad'])} نیرو | هر اسکادران {AM.squad_cost(unit_key, 1):,}$ از صندوق.{CANCEL_HINT}",
        _back_kb(uid),
    )
    await safe_answer(callback)


@router.message(AllianceStates.buying_squads)
async def buy_manual_recv(message: Message, state: FSMContext) -> None:
    if await handle_cancel_word(message, state):
        return
    raw = (message.text or "").strip().replace(",", "").replace("٬", "")
    raw = raw.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789"))
    if not raw.isdigit():
        await message.reply("فقط عددِ مثبت بفرست (تعدادِ اسکادران).")
        return
    squads = int(raw)
    if squads <= 0:
        await message.reply("تعداد باید حداقل ۱ باشد.")
        return
    data = await state.get_data()
    unit_key = str(data.get("unit_key") or "")
    u = AM.get_unit(unit_key)
    if not u:
        await message.reply("❌ واحد نامعتبر؛ دوباره از منوی سربازخانه تلاش کن.")
        await state.clear()
        return
    uid = message.from_user.id
    async with async_session() as session:
        ctx = await _prod_ctx(session, uid)
        if ctx is None or not await _can_manage(session, ctx["membership"]):
            await message.reply("🔒 تولید/خرید فقط با رئیس یا معاونِ دارای دسترسی است.")
            await state.clear()
            return
    max_sq = AM.max_squads_possible(unit_key, ctx["free"], ctx["treasury"])
    if squads > max_sq:
        await message.reply(
            f"❌ حداکثرِ قابلِ ساختِ الان {max_sq} اسکادران است (ظرفیت/صندوق). عددِ کمتری بفرست یا «انصراف»."
        )
        return
    await state.clear()
    units = squads * int(u["squad"])
    cost = AM.squad_cost(unit_key, squads)
    await message.answer(
        f"🏭 <b>تأیید تولیدِ اسکادرانی</b>\n"
        f"{u['name']} × {squads} اسکادران ({units:,} نیرو)\n"
        f"💰 هزینه‌ی نهایی: {cost:,}$ از صندوق\n"
        f"⏳ آماده تا: {M.fmt_eta(AM.train_seconds(unit_key, squads))}\n\n"
        "✅ تولید را تأیید می‌کنی؟",
        reply_markup=ALKB.alw_buy_confirm_menu(uid, unit_key, squads),
    )


# --------------------------- 🆕 v1.8.2.0 — صفِ تولید (مثلِ mil:queue) ---------------------------
async def _render_queue(message: Message, uid: int, page: int = 0, *, cancel_mode: bool = False, materialized: int = 0) -> None:
    async with async_session() as session:
        membership, al = await _member_and_alliance(session, uid)
        if al is None:
            await safe_show(message, "اول باید عضوِ اتحادیه باشی.", _back_kb(uid))
            return
        can_manage = await _can_manage(session, membership)
        if not cancel_mode:
            materialized += await AMS.settle_training(session, al.id)
        items = await AMS.queue_items(session, al.id)
        treasury = int(al.treasury or 0)
        await session.commit()
    page_items, page, total_pages = paginate(items, page, per=6)
    lines = ["🏗️ <b>صفِ تولیدِ اتحادیه</b>", ""]
    if materialized:
        lines += [f"✅ {materialized:,} نیرو آماده شد و به ارتشِ اتحادیه پیوست.", ""]
    lines += [f"💰 صندوق: {treasury:,}$ | بچ‌های در صف: {len(items)}", ""]
    if page_items:
        from app.data.battle_report import fmt_remaining
        for q in page_items:
            lines.append(
                f"▫️ {q['name']} — {q['squads']} اسکادران ({q['units']:,} نیرو) — ⏳ آماده تا {fmt_remaining(q['remaining'])}"
            )
    else:
        lines.append("— صفی وجود ندارد —")
    if cancel_mode:
        lines += ["", "برای لغو، روی بچ بزن. هزینه‌ی پرداخت‌شده به‌صورتِ کامل به صندوق برمی‌گردد."]
        markup = ALKB.alw_queue_cancel_menu(uid, page_items, page, total_pages)
    else:
        markup = ALKB.alw_queue_menu(uid, page, total_pages, can_manage)
    await safe_show(message, "\n".join(lines), markup)


@router.callback_query(F.data.startswith("alw:queue"))
async def queue_home(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    base, _ = split_owner(callback.data)
    parts = base.split(":")
    page = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0
    await _render_queue(callback.message, callback.from_user.id, page)
    await safe_answer(callback)


@router.callback_query(F.data.startswith("alw:qcancelmenu:"))
async def queue_cancel_menu(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    base, _ = split_owner(callback.data)
    parts = base.split(":")
    page = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0
    await _render_queue(callback.message, callback.from_user.id, page, cancel_mode=True)
    await safe_answer(callback)


@router.callback_query(F.data.startswith("alw:qcancel:"))
async def queue_cancel(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    base, _ = split_owner(callback.data)
    parts = base.split(":")
    if len(parts) != 4 or not parts[2].isdigit():
        await safe_answer(callback, "❌ درخواست نامعتبر است.", show_alert=True)
        return
    queue_id = int(parts[2])
    page = int(parts[3]) if parts[3].isdigit() else 0
    uid = callback.from_user.id
    async with async_session() as session:
        membership, al = await _member_and_alliance(session, uid)
        if al is None or not await _can_manage(session, membership):
            await safe_answer(callback, "🔒 لغوِ صف فقط با رئیس یا معاونِ دارای دسترسی.", show_alert=True)
            return
        ok, msg = await AMS.cancel_training(session, al, queue_id)
        if ok:
            await session.commit()
        else:
            await session.rollback()
    await _render_queue(callback.message, uid, page, cancel_mode=True)
    await safe_answer(callback, msg, show_alert=not ok)


# --------------------------- 🆕 v1.8.2.0 — ارتقا و آموزش (مثلِ mil:upgrade) ---------------------------
async def _render_upgrade_menu(callback: CallbackQuery) -> None:
    uid = callback.from_user.id
    async with async_session() as session:
        ctx = await _prod_ctx(session, uid)
        if ctx is None:
            await safe_show(callback.message, "اول باید عضوِ اتحادیه باشی.", _back_kb(uid))
            return
        owned = [(k, c, lv) for k, c, lv in ctx["stacks"] if int(c) > 0]
        treasury = ctx["treasury"]
    if not owned:
        await safe_show(
            callback.message,
            "اول از بخشِ «تولید نیرو» چند اسکادران بساز، بعد ارتقا بده.",
            _back_kb(uid),
        )
        return
    text = (
        "🎖️ <b>ارتقا و آموزشِ ارتشِ اتحادیه</b>\n\n"
        "هر ارتقا قدرتِ <b>همه‌ی</b> واحدهای آن نوع را +۱۵٪ می‌کند (هزینه ۳۰× جنگِ عادی، از صندوق)."
    )
    await safe_show(callback.message, text, ALKB.alw_upgrade_menu(uid, owned, treasury))


@router.callback_query(F.data.startswith("alw:upgm"))
async def upgrade_menu_cb(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    await _render_upgrade_menu(callback)
    await safe_answer(callback)


@router.callback_query(F.data.startswith("alw:upgu:"))
async def upgrade_unit_cb(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    base, _ = split_owner(callback.data)
    parts = base.split(":")
    unit_key = parts[2] if len(parts) > 2 else ""
    uid = callback.from_user.id
    async with async_session() as session:
        membership, al = await _member_and_alliance(session, uid)
        if al is None or not await _can_manage(session, membership):
            await safe_answer(callback, "🔒 فقط رئیس یا معاونِ دارای دسترسی.", show_alert=True)
            return
        ok, msg = await AMS.upgrade_unit(session, al, unit_key)
        await session.commit()
    await safe_answer(callback, msg, show_alert=True)
    # 🐞 رفعِ باگ: قبلاً پس از ارتقا به صفحه‌ی اولِ منوی کشویی می‌رفتی؛ حالا همان منوی ارتقا باز می‌شود.
    await _render_upgrade_menu(callback)


@router.callback_query(F.data.startswith("alw:upbk"))
async def upgrade_barracks_cb(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    uid = callback.from_user.id
    async with async_session() as session:
        membership, al = await _member_and_alliance(session, uid)
        if al is None or not await _can_manage(session, membership):
            await safe_answer(callback, "🔒 فقط رئیس یا معاونِ دارای دسترسی.", show_alert=True)
            return
        ok, msg = await AMS.upgrade_barracks(session, al)
        await session.commit()
    await safe_answer(callback, msg, show_alert=True)
    await barracks_home(callback)


# --------------------------- تولیدِ خودکار ---------------------------
@router.callback_query(F.data.startswith("alw:auto:"))  # 🐞 v1.8.2.0 — قبلاً alw:autoset هم اینجا می‌افتاد
async def auto_home(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    base, _ = split_owner(callback.data)
    parts = base.split(":")
    uid = callback.from_user.id
    toggled = False
    async with async_session() as session:
        membership, al = await _member_and_alliance(session, uid)
        if al is None or not await _can_manage(session, membership):
            await safe_answer(callback, "🔒 فقط رئیس یا معاونِ دارای دسترسی.", show_alert=True)
            return
        b = await AMS.get_or_create_barracks(session, al.id)
        if len(parts) >= 3 and parts[2] == "tg":
            b.auto_enabled = 0 if int(b.auto_enabled or 0) else 1
            await session.flush()
            toggled = True
        mins = AMS.auto_minimums(b)
        auto_on = bool(int(b.auto_enabled or 0))
        await session.commit()
    kb = _kb()
    kb.button(text=("⏸ خاموش‌کردنِ خودکار" if auto_on else "▶️ روشن‌کردنِ خودکار"), callback_data=with_owner("alw:auto:tg", uid))
    for key in AM.UNIT_ORDER:
        u = AM.get_unit(key)
        cur = int(mins.get(key, 0))
        kb.button(text=f"🎯 حداقلِ {u['name']}: {cur:,}", callback_data=with_owner(f"alw:autoset:{key}", uid))
    kb.button(text="↩️ بازگشت به سربازخانه", callback_data=with_owner("alw:bk", uid))
    kb.adjust(1)
    text = (
        "🤖 <b>تولیدِ خودکارِ روزانه</b>\n\n"
        "روزی یک‌بار اگر نیرویی از حداقلِ تعیین‌شده کمتر باشد، "
        "با احتسابِ مجروحانِ قابل‌درمانِ بیمارستان و ظرفیتِ خالیِ سربازخانه، "
        "در صورتِ داشتنِ پولِ کافی در صندوق تا حداقل ساخته می‌شود.\n\n"
        "برای تعیینِ حداقل، دکمه‌ی هر واحد را بزن و عدد بفرست."
    )
    if toggled:
        await safe_answer(callback, "🤖 تولیدِ خودکار " + ("روشن شد ✅" if auto_on else "خاموش شد ❌"))
    await safe_show(callback.message, text, kb.as_markup())
    if not toggled:
        await safe_answer(callback)


@router.callback_query(F.data.startswith("alw:autoset:"))
async def auto_set_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not await ensure_owner(callback):
        return
    base, _ = split_owner(callback.data)
    unit_key = base.split(":")[2]
    u = AM.get_unit(unit_key)
    if u is None:
        await safe_answer(callback, "واحد نامعتبر.", show_alert=True)
        return
    await state.set_state(AllianceStates.setting_auto_min)
    await state.update_data(auto_unit=unit_key)
    await safe_show(
        callback.message,
        f"🎯 حداقلِ روزانه‌ی <b>{u['name']}</b> را به‌صورتِ عدد بفرست (۰ یعنی بدونِ حداقل):\n{CANCEL_HINT}",
        _back_kb(callback.from_user.id),
    )
    await safe_answer(callback)


@router.message(AllianceStates.setting_auto_min)
async def auto_set_recv(message: Message, state: FSMContext) -> None:
    if await handle_cancel_word(message, state):
        return
    raw = (message.text or "").strip().replace(",", "")
    if not raw.isdigit():
        await message.reply("فقط عددِ مثبت بفرست.")
        return
    value = int(raw)
    data = await state.get_data()
    unit_key = str(data.get("auto_unit") or "")
    uid = message.from_user.id
    async with async_session() as session:
        membership, al = await _member_and_alliance(session, uid)
        if al is None or not await _can_manage(session, membership):
            await message.reply("🔒 فقط رئیس یا معاونِ دارای دسترسی.")
            await state.clear()
            return
        await AMS.set_auto_minimum(session, al.id, unit_key, value)
        await session.commit()
    await state.clear()
    u = AM.get_unit(unit_key)
    await message.reply(f"✅ حداقلِ روزانه‌ی {(u['name'] if u else unit_key)} روی {value:,} تنظیم شد.")


# --------------------------- صندوق: واریز ---------------------------
@router.callback_query(F.data.startswith("alw:trs"))
async def treasury_home(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    uid = callback.from_user.id
    async with async_session() as session:
        membership, al = await _member_and_alliance(session, uid)
        if al is None:
            await safe_answer(callback, "اول باید عضوِ اتحادیه باشی.", show_alert=True)
            return
        player = await get_player(session, uid)
        cash = int(getattr(player, "cash", 0) or 0) if player else 0
        contrib = int(membership.contributed or 0)
        treasury = int(al.treasury or 0)
        sub_pct, sub_days = al.sub_pct, al.sub_days
    kb = _kb()
    kb.button(text="💵 واریز به صندوق", callback_data=with_owner("alw:dep", uid))
    kb.button(text="↩️ بازگشت به اتحادیه", callback_data=with_owner("all:hub", uid))
    kb.adjust(1)
    text = (
        "💰 <b>صندوقِ اتحادیه</b>\n\n"
        f"🏦 موجودی: <b>{treasury:,}$</b>\n"
        f"💳 اشتراکِ عضویت: {sub_pct}٪ از درآمد، هر {sub_days} روز (خودکار کسر می‌شود)\n"
        f"🎖️ مشارکتِ تو (مجموعِ واریزها): <b>{contrib:,}$</b>\n"
        f"👛 نقدِ تو: {cash:,}$\n\n"
        "واریز بیشتر = امتیازِ مشارکتِ بیشتر — در آپدیت‌های بعدی: فروشگاهِ اتحادیه، "
        "بونسِ درآمد و سهمِ بیشتر از غنیمتِ جنگ‌ها."
    )
    await safe_show(callback.message, text, kb.as_markup())
    await safe_answer(callback)


@router.callback_query(F.data.startswith("alw:dep"))
async def deposit_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not await ensure_owner(callback):
        return
    await state.set_state(AllianceStates.depositing)
    await safe_show(
        callback.message,
        f"💵 مبلغِ واریز به صندوق را به‌صورتِ عدد بفرست:\n{CANCEL_HINT}",
        _back_kb(callback.from_user.id),
    )
    await safe_answer(callback)


@router.message(AllianceStates.depositing)
async def deposit_recv(message: Message, state: FSMContext) -> None:
    if await handle_cancel_word(message, state):
        return
    raw = (message.text or "").strip().replace(",", "").replace("$", "")
    if not raw.isdigit() or int(raw) <= 0:
        await message.reply("فقط عددِ مثبت بفرست (مبلغِ واریز).")
        return
    amount = int(raw)
    uid = message.from_user.id
    async with async_session() as session:
        membership, al = await _member_and_alliance(session, uid)
        if al is None:
            await message.reply("اول باید عضوِ اتحادیه باشی.")
            await state.clear()
            return
        player = await get_player(session, uid)
        ok, msg = await AMS.deposit(session, al, membership, player, amount)
        await session.commit()
    await state.clear()
    await message.reply(msg)


# --------------------------- نبردِ زنده ---------------------------
def _battle_kb(uid: int, battle_id: int, can_war: bool, over: bool):
    b = _kb()
    b.button(text="🔄 بروزرسانی", callback_data=with_owner(f"alw:war:rf:{battle_id}", uid))
    if can_war and not over:
        b.button(text="🕊️ آتش‌بس", callback_data=with_owner(f"alw:war:cf:{battle_id}", uid))
    b.button(text="🏆 رنکینگِ کاپ", callback_data=with_owner("alw:rank:0", uid))
    b.button(text="↩️ بازگشت به اتحادیه", callback_data=with_owner("all:hub", uid))
    b.adjust(1)
    return b.as_markup()


async def _show_battle(callback: CallbackQuery, battle_id: int | None = None) -> None:
    uid = callback.from_user.id
    async with async_session() as session:
        membership, al = await _member_and_alliance(session, uid)
        if al is None:
            await safe_answer(callback, "اول باید عضوِ اتحادیه باشی.", show_alert=True)
            return
        battle = None
        if battle_id is not None:
            from app.models.alliance_war import AllianceBattle
            candidate = await session.get(AllianceBattle, int(battle_id))
            if candidate is not None and al.id in (int(candidate.attacker_id), int(candidate.defender_id)):
                battle = candidate
        if battle is None:
            battle = await AB.running_battle_for(session, al.id) or await AB.last_battle_for(session, al.id)
        if battle is None:
            await safe_show(callback.message, "⚔️ هنوز جنگی برای اتحادیه‌ی تو ثبت نشده.", _back_kb(uid))
            await safe_answer(callback)
            return
        if AB.is_over(battle) and not battle.finalized:
            await AB.finalize(session, battle)
        can_war = await alliance_service.has_permission(session, membership, A.PERM_WAR)
        text = AB.render(battle)
        over = bool(battle.finalized) or AB.is_over(battle)
        bid = int(battle.id)
    await safe_show(callback.message, text, _battle_kb(uid, bid, can_war, over))
    await safe_answer(callback)


@router.callback_query(F.data.startswith("alw:war:rf:"))
async def battle_refresh(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    base, _ = split_owner(callback.data)
    try:
        bid = int(base.split(":")[3])
    except (IndexError, ValueError):
        bid = None
    await _show_battle(callback, bid)


@router.callback_query(F.data.startswith("alw:war:cf:"))
async def battle_ceasefire(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    base, _ = split_owner(callback.data)
    try:
        bid = int(base.split(":")[3])
    except (IndexError, ValueError):
        await safe_answer(callback, "نبرد نامعتبر.", show_alert=True)
        return
    uid = callback.from_user.id
    async with async_session() as session:
        membership, al = await _member_and_alliance(session, uid)
        if al is None or not await alliance_service.has_permission(session, membership, A.PERM_WAR):
            await safe_answer(callback, "🔒 آتش‌بس فقط با رئیس/معاونِ دارای دسترسیِ جنگ.", show_alert=True)
            return
        ok, msg, _row = await AB.ceasefire(session, bid, al.id)
        await session.commit()
    await safe_answer(callback, msg, show_alert=True)
    if ok:
        await _show_battle(callback, bid)


@router.callback_query(F.data.startswith("alw:war"))  # 🐞 v1.8.2.0 — دکمه‌ها پسوندِ مالک دارند؛ == هرگز match نمی‌شد
async def battle_home(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    await _show_battle(callback)


# --------------------------- بیمارستان ---------------------------
@router.callback_query(F.data.startswith("alw:hosp"))
async def hospital_home(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    uid = callback.from_user.id
    async with async_session() as session:
        membership, al = await _member_and_alliance(session, uid)
        if al is None:
            await safe_answer(callback, "اول باید عضوِ اتحادیه باشی.", show_alert=True)
            return
        wards = await AMS.active_wards(session, al.id)
        can_manage = await _can_manage(session, membership)
        treasury = int(al.treasury or 0)
    from datetime import datetime as _dt
    from app.data.battle_report import fmt_remaining
    lines = ["🏥 <b>بیمارستانِ اتحادیه</b>", "", f"💰 صندوق: {treasury:,}$", ""]
    kb = _kb()
    if not wards:
        lines.append("مجروحی برای درمان نیست. 🕊️")
    for w in wards[:8]:
        left = max(0, int((w.expires_at - _dt.utcnow()).total_seconds()))
        lines.append(f"• {int(w.unit_count or 0):,} مجروح (جنگ با {w.opponent_name or '؟'}) — هزینه: {int(w.cost or 0):,}$ — مهلت: {fmt_remaining(left)}")
        if can_manage:
            kb.button(text=f"💊 درمانِ {int(w.unit_count or 0):,} نیرو — {int(w.cost or 0):,}$", callback_data=with_owner(f"alw:heal:{w.id}", uid))
    lines.append("\n⏰ پس از ۲۴ ساعت، مجروحانِ درمان‌نشده می‌میرند.")
    kb.button(text="↩️ بازگشت به سربازخانه", callback_data=with_owner("alw:bk", uid))
    kb.adjust(1)
    await safe_show(callback.message, "\n".join(lines), kb.as_markup())
    await safe_answer(callback)


@router.callback_query(F.data.startswith("alw:heal:"))
async def heal_cb(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    base, _ = split_owner(callback.data)
    try:
        ward_id = int(base.split(":")[2])
    except (IndexError, ValueError):
        await safe_answer(callback, "ردیف نامعتبر.", show_alert=True)
        return
    uid = callback.from_user.id
    async with async_session() as session:
        membership, al = await _member_and_alliance(session, uid)
        if al is None or not await _can_manage(session, membership):
            await safe_answer(callback, "🔒 درمان فقط با رئیس یا معاونِ دارای دسترسی.", show_alert=True)
            return
        ok, msg = await AMS.heal_ward(session, al, ward_id)
        await session.commit()
    await safe_answer(callback, msg, show_alert=True)
    await hospital_home(callback)


# --------------------------- رنکینگِ کاپِ اتحادیه‌ها ---------------------------
@router.callback_query(F.data.startswith("alw:rank:"))
async def cup_ranking(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    base, _ = split_owner(callback.data)
    try:
        page = int(base.split(":")[2])
    except (IndexError, ValueError):
        page = 0
    uid = callback.from_user.id
    async with async_session() as session:
        from sqlalchemy import select as _select
        from app.models.alliance_war import AllianceRankRow
        rows = list((await session.execute(
            _select(AllianceRankRow).order_by(AllianceRankRow.cups.desc())
        )).scalars().all())
        names = {}
        for r in rows:
            al = await alliance_service.get_alliance(session, r.alliance_id)
            names[r.alliance_id] = al.name if al else f"#{r.alliance_id}"
    per = 10
    total = max(1, (len(rows) + per - 1) // per)
    page = max(0, min(page, total - 1))
    chunk = rows[page * per:(page + 1) * per]
    lines = ["🏆 <b>رنکینگِ کاپِ اتحادیه‌ها</b>", ""]
    if not chunk:
        lines.append("هنوز جنگی ثبت نشده.")
    from app.utils.table import render_table, table_mode_on
    if await table_mode_on("alliance_rank"):
        _rows = []
        for i, r in enumerate(chunk, start=page * per + 1):
            _rows.append([str(i), names.get(r.alliance_id, "?"), f"{int(r.cups or 0):,}", f"{int(r.wins or 0)}/{int(r.losses or 0)}"])
        lines.append(render_table(["#", "اتحادیه", "کاپ", "برد/باخت"], _rows))
    else:
        for i, r in enumerate(chunk, start=page * per + 1):
            medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(i, f"{i}.")
            lines.append(f"{medal} <b>{names.get(r.alliance_id, '?')}</b> — 🏆 {int(r.cups or 0):,} کاپ ({int(r.wins or 0)} برد / {int(r.losses or 0)} باخت)")
    kb = _kb()
    if page > 0:
        kb.button(text="◀️ قبلی", callback_data=with_owner(f"alw:rank:{page-1}", uid))
    if page < total - 1:
        kb.button(text="بعدی ▶️", callback_data=with_owner(f"alw:rank:{page+1}", uid))
    kb.button(text="↩️ بازگشت به اتحادیه", callback_data=with_owner("all:hub", uid))
    kb.adjust(1)
    await safe_show(callback.message, "\n".join(lines), kb.as_markup())
    await safe_answer(callback)


# --------------------------- راهنما ---------------------------
@router.callback_query(F.data.startswith("alw:guide"))
async def guide_cb(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    await safe_show(callback.message, AM.rps_guide(), _back_kb(callback.from_user.id))
    await safe_answer(callback)
