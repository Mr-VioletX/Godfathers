# -*- coding: utf-8 -*-
"""🆕 بچ ۴ — هندلرهای شهرساتِ جدید (تک‌شهری).

جایگزینِ کاملِ هندلرهای قدیمیِ شهر/کشور. هر بازیکن یک شهر دارد؛
مدیریتِ مسکونی/زیرساخت/رفاه/صنعت، انبار، مالیات و درآمد.
"""
from datetime import datetime
from aiogram import F, Router
from aiogram.filters import Command, StateFilter
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from sqlalchemy import select

from app.database.engine import async_session
from app.data import mafia_city as C
from app.keyboards.city_menu import (
    buy_menu,
    build_confirm_menu,
    build_quantity_menu,
    category_menu,
    city_menu,
    city_control_menu,
    city_economy_menu,
    city_mayor_menu,
    resources_menu,
    tax_menu,
)
from app.keyboards.main_menu import BTN_CITY, WORD_CITY
from app.models.player import Player
from app.states import CityStates
from app.services import mafia_city_service as CS
from app.utils.ui import CANCEL_HINT, ensure_owner, handle_cancel_word, safe_answer, safe_edit, split_owner, with_owner

router = Router(name="city")


async def get_player(session, uid: int) -> Player | None:
    res = await session.execute(select(Player).where(Player.tg_user_id == int(uid)))
    return res.scalar_one_or_none()


def _cd(callback) -> str:
    base, _owner = split_owner(callback.data or "")
    return base


def _cb(data: str, owner_id=None) -> str:
    """🐞 v1.7.8.12 — این هِلپر قبلاً در city.py تعریف نشده بود و باعثِ
    NameError داخلِ هندلرِ «در حال ساخت‌وساز» می‌شد."""
    return with_owner(data, owner_id) if owner_id is not None else data


async def render_hub(session, uid: int):
    """متن + کیبوردِ صفحه‌ی اصلیِ شهر."""
    city = await CS.get_city(session, uid)
    if not city:
        text = await CS.status_text(session, uid)
        return text, buy_menu(uid)
    text = await CS.status_text(session, uid)
    try:
        _pend = await CS.pending_builds(session, city.id)
    except Exception:
        _pend = []
    if _pend:
        _now = datetime.utcnow()
        text += chr(10) + chr(10) + "<b>🏗️ در حال ساخت:</b>"
        for _q in _pend[:5]:
            _left = max(0, int((_q.ready_at - _now).total_seconds()))
            _lbl = C.building_name(_q.btype) if _q.kind != "warehouse" else "🏪 انبار شهر"
            _qty = max(1, int(_q.qty or 1))
            _qtxt = f" ×{_qty:,}" if _qty > 1 else ""
            text += chr(10) + f"  • {_lbl}{_qtxt} — {C.fmt_duration(_left)} مانده"
    return text, city_menu(uid, int(city.warehouse_level))



# ---------------------------------------------------------------------------
# ورودی
# ---------------------------------------------------------------------------
@router.message(Command("city"))
@router.message(F.text == BTN_CITY)
@router.message(F.text == WORD_CITY)
async def city_entry(message: Message):
    async with async_session() as session:
        player = await get_player(session, message.from_user.id)
        if player is None:
            await message.answer("ابتدا /start را بزن.")
            return
        text, kb = await render_hub(session, message.from_user.id)
    await message.answer(text, reply_markup=kb)


@router.callback_query(F.data.startswith("menu:city"))
async def city_menu_entry(callback: CallbackQuery):
    if not await ensure_owner(callback):
        return
    async with async_session() as session:
        text, kb = await render_hub(session, callback.from_user.id)
    await safe_edit(callback.message, text, kb)
    await safe_answer(callback)


@router.callback_query(F.data.startswith("city:hub"))
async def city_hub(callback: CallbackQuery):
    if not await ensure_owner(callback):
        return
    async with async_session() as session:
        text, kb = await render_hub(session, callback.from_user.id)
    await safe_edit(callback.message, text, kb)
    await safe_answer(callback)


# ---------------------------------------------------------------------------
# زیرمنوهای مرتب‌شده شهر
# ---------------------------------------------------------------------------
@router.callback_query(F.data.startswith("city:rename"))
async def city_rename(callback: CallbackQuery, state: FSMContext):
    if not await ensure_owner(callback):
        return
    # 🆕 v1.7.5.1 — set_state + data در یک مسیر پایدار؛ پیام خصوصی اجباری
    await state.set_state(CityStates.renaming_city)
    await state.update_data(city_rename_pending=1, city_input_mode="rename")
    tip = (
        "✏️ نام جدید شهر را <b>همین‌جا در چت خصوصی ربات</b> بفرست.\n"
        "(۲ تا ۶۴ نویسه)" + CANCEL_HINT
    )
    try:
        await callback.bot.send_message(callback.from_user.id, tip)
    except Exception:
        await callback.message.answer(tip)
    await safe_answer(callback)


async def _apply_city_name_input(message: Message, state: FSMContext) -> bool:
    """اگر کاربر در حالت نام‌گذاری/تغییر نام شهر باشد True و کار را انجام می‌دهد."""
    if message.from_user is None:
        return False
    if message.chat and message.chat.type != "private":
        return False
    try:
        cur = await state.get_state()
    except Exception:
        cur = None
    data = {}
    try:
        data = await state.get_data()
    except Exception:
        data = {}
    mode = None
    if cur == CityStates.renaming_city.state or cur == "CityStates:renaming_city":
        mode = "rename"
    elif cur == CityStates.naming_city.state or cur == "CityStates:naming_city":
        mode = "name"
    elif data.get("city_input_mode") in ("rename", "name"):
        mode = data.get("city_input_mode")
    elif data.get("city_rename_pending"):
        mode = "rename"
    elif data.get("city_name_pending"):
        mode = "name"
    if not mode:
        return False
    if await handle_cancel_word(message, state):
        return True
    name = (message.text or "").strip()
    if not name:
        await message.answer("⚠️ یک نام متنی بفرست (نه عکس/فایل).")
        return True
    if not 2 <= len(name) <= 64:
        await message.answer("⚠️ نام شهر باید بین ۲ تا ۶۴ نویسه باشد.")
        return True
    async with async_session() as session:
        if mode == "rename":
            ok, msg = await CS.rename_city(session, message.from_user.id, name)
        else:
            ok, msg = await CS.found_city(session, message.from_user.id, name)
        text, kb = await render_hub(session, message.from_user.id)
    try:
        await state.clear()
    except Exception:
        pass
    prefix = "✅ نام شهر تغییر کرد.\n\n" if (mode == "rename" and ok) else (msg + "\n\n")
    if mode == "rename" and ok:
        await message.answer(prefix + text, reply_markup=kb)
    else:
        await message.answer((msg if msg else prefix) + ("\n\n" + text if text else ""), reply_markup=kb)
    return True


@router.message(StateFilter(CityStates.renaming_city), F.text)
async def city_rename_receive(message: Message, state: FSMContext):
    await _apply_city_name_input(message, state)


# 🆕 v1.7.5.1 — fallback فقط وقتی pending/mode شهر باشد (بقیه پیام‌ها Skip می‌شوند)
@router.message(F.chat.type == "private", F.text)
async def city_name_fallback(message: Message, state: FSMContext):
    from aiogram.dispatcher.event.bases import SkipHandler

    handled = await _apply_city_name_input(message, state)
    if not handled:
        raise SkipHandler

@router.callback_query(F.data.startswith("city:help"))
async def city_help(callback: CallbackQuery):
    if not await ensure_owner(callback): return
    text = ("❔ <b>راهنمای سریع شهر</b>\n\n"
            "🏗️ از «کنترل شهر» خانه، زیرساخت، صنعت و رفاه را بساز.\n"
            "🛒 از «بازار و منابع» مواد اولیه را تهیه کن.\n"
            "🏦 از «اقتصاد شهر» مالیات، درآمد و تولید را مدیریت کن.\n"
            "👥 بخش شهروندان کمبودها و رضایت را نشان می‌دهد.\n"
            "📦 قبل از ساخت، ظرفیت انبار و پیش‌نیازهای نوشته‌شده بالای دکمه‌ها را بررسی کن.")
    async with async_session() as session:
        _, kb = await render_hub(session, callback.from_user.id)
    await safe_edit(callback.message, text, kb)
    await safe_answer(callback)


@router.callback_query(F.data.startswith("city:control"))
async def city_control_menu_cb(callback: CallbackQuery):
    if not await ensure_owner(callback): return
    await safe_edit(callback.message, "🏗️ <b>کنترل شهر</b>\nساخت‌وساز را از دسته موردنظر انتخاب کن.", city_control_menu(callback.from_user.id))
    await safe_answer(callback)


@router.callback_query(F.data.startswith("city:economy"))
async def city_economy_menu_cb(callback: CallbackQuery):
    if not await ensure_owner(callback): return
    await safe_edit(callback.message, "🏦 <b>اقتصاد شهر</b>\nدرآمد، مالیات و توان اقتصادی شهر از این بخش مدیریت می‌شود.", city_economy_menu(callback.from_user.id))
    await safe_answer(callback)


# ---------------------------------------------------------------------------
# صفحات اطلاعاتی جداگانه شهر
# ---------------------------------------------------------------------------
@router.callback_query(F.data.startswith("city:info:"))
async def city_info(callback: CallbackQuery):
    if not await ensure_owner(callback): return
    detail = _cd(callback).split(":")[2]
    if detail not in {"needs", "services", "production"}:
        await safe_answer(callback, "بخش نامعتبر است.", show_alert=True); return
    async with async_session() as session:
        text = await CS.city_detail_text(session, callback.from_user.id, detail)
        _, kb = await render_hub(session, callback.from_user.id)
    await safe_edit(callback.message, text, kb)
    await safe_answer(callback)


# ---------------------------------------------------------------------------
# خریدِ شهر
# ---------------------------------------------------------------------------
@router.callback_query(F.data.startswith("city:buy"))
async def city_buy(callback: CallbackQuery, state: FSMContext):
    if not await ensure_owner(callback):
        return
    await state.set_state(CityStates.naming_city)
    await state.update_data(city_name_pending=1, city_input_mode="name")
    tip = (
        "🏙️ نام تک‌شهر خود را <b>همین‌جا در چت خصوصی ربات</b> بفرست.\n"
        "این نام بعداً قابل تغییر است. (۲ تا ۶۴ نویسه)" + CANCEL_HINT
    )
    try:
        await callback.bot.send_message(callback.from_user.id, tip)
    except Exception:
        await callback.message.answer(tip)
    await safe_answer(callback)


@router.message(StateFilter(CityStates.naming_city), F.text)
async def city_name_first(message: Message, state: FSMContext):
    await _apply_city_name_input(message, state)


# ---------------------------------------------------------------------------
# جمع‌آوریِ درآمد
# ---------------------------------------------------------------------------
@router.callback_query(F.data.startswith("city:collect"))
async def city_collect(callback: CallbackQuery):
    if not await ensure_owner(callback):
        return
    async with async_session() as session:
        ok, msg = await CS.collect_income(session, callback.from_user.id)
        text, kb = await render_hub(session, callback.from_user.id)
    await safe_edit(callback.message, text, kb)
    await safe_answer(callback, msg, show_alert=True)


# ---------------------------------------------------------------------------
# دسته‌ی ساختمان‌ها (مسکونی/زیرساخت/رفاه/صنعت)
# ---------------------------------------------------------------------------
async def _render_category(session, uid: int, ckey: str, page: int):
    city = await CS.get_city(session, uid)
    if not city:
        return await CS.status_text(session, uid), buy_menu(uid)
    counts = await CS.buildings_summary(session, uid)
    cat = C.CATEGORIES.get(ckey, {})
    resources = CS._resources(city)
    from app.utils.ui import paginate
    order = list(cat.get("order", ()))
    is_housing = ckey == "housing"
    if is_housing:
        rows = order
        total_pages = 1
    else:
        rows, page, total_pages = paginate(order, page, per=8)
    try:
        pending_rows = await CS.pending_builds(session, city.id)
    except Exception:
        pending_rows = []
    now = datetime.utcnow()
    pending: dict[str, int] = {}
    for q in pending_rows:
        pending[q.btype] = pending.get(q.btype, 0) + max(1, int(q.qty or 1))
    lines = [cat.get('name', ckey),
             f"📦 انبار: {C.resource_total(resources):,}/{C.warehouse_capacity(city.warehouse_level):,}"]
    # ── دارایی‌های فعلی (بالای صفحه) ──
    owned = [(bt, int(counts.get(bt, 0))) for bt in order if int(counts.get(bt, 0)) > 0]
    if owned:
        from app.utils.table import render_table, table_mode_on
        lines.append("")
        if await table_mode_on("city"):
            _rows = []
            for bt, qty in owned:
                info = C.get_building(bt) or {}
                extra = ""
                if is_housing:
                    extra = f"{int(info.get('residents', 0)) * qty:,} نفر"
                _rows.append([info.get("name", bt), str(qty), extra or "-"])
            lines.append("<b>🏠 دارایی‌های تو:</b>")
            lines.append(render_table(["ساختمان", "تعداد", "ظرفیت"], _rows))
        else:
            lines.append("<b>🏠 دارایی‌های تو:</b>")
            for bt, qty in owned:
                info = C.get_building(bt) or {}
                extra = ""
                if is_housing:
                    extra = f" — ظرفیت {int(info.get("residents", 0)) * qty:,} نفر"
                lines.append(f"  {info.get("name", bt)} × <b>{qty}</b>{extra}")
    # ── در حال ساخت ──
    if pending_rows:
        from app.utils.table import render_table as _rt2, table_mode_on as _tmo2
        lines.append("")
        lines.append("<b>🏗️ در حال ساخت:</b>")
        if await _tmo2("city"):
            _rows = []
            for q in pending_rows:
                left = max(0, int((q.ready_at - now).total_seconds()))
                label = C.building_name(q.btype) if q.kind != "warehouse" else "🏪 انبار شهر"
                if q.kind == "upgrade":
                    label = "⬆️ " + label
                _rows.append([label, f"×{max(1, int(q.qty or 1)):,}", C.fmt_duration(left)])
            lines.append(_rt2(["ساختمان", "تعداد", "مانده"], _rows))
        else:
            for q in pending_rows:
                left = max(0, int((q.ready_at - now).total_seconds()))
                label = C.building_name(q.btype) if q.kind != "warehouse" else "🏪 انبار شهر"
                if q.kind == "upgrade":
                    label = "⬆️ " + label
                qty_text = f" ×{max(1, int(q.qty or 1)):,}" if int(q.qty or 1) > 1 else ""
                lines.append(f"  • {label}{qty_text} — {C.fmt_duration(left)} مانده")
    # ── خرید (پایین صفحه) ──
    lines.append("")
    lines.append("<b>🛒 ساخت جدید:</b>")
    for btype in rows:
        info = C.get_building(btype) or {}
        have = int(counts.get(btype, 0))
        prereq = info.get("requires") or ()
        if isinstance(prereq, str):
            prereq = (prereq,)
        prereq_text = "، ".join(C.building_name(x) for x in prereq) if prereq else "ندارد"
        sec = C.build_seconds(btype)
        detail = (
            f"• <b>{info.get("name", btype)}</b> — "
            f"💰 {int(info.get("cost", 0)):,}$ + {C.requirements_text(C.material_requirements(btype))}"
            + f" | ⏱ {C.fmt_duration(sec)}"
        )
        if ckey == "industry":
            detail += chr(10) + f"  تولید: {C.industry_output_text(btype, have)} → {C.industry_output_text(btype, have + 1)}"
        elif btype in C.HOUSING:
            detail += chr(10) + f"  ظرفیت هر واحد: {int(info.get("residents", 0)):,} نفر"
            if info.get("next"):
                detail += chr(10) + f"  ♻️ تبدیل: {C.CONVERT_RATIO} واحد → ۱ {C.building_name(info["next"])}"
        if prereq_text != "ندارد":
            detail += chr(10) + f"  پیش‌نیاز: {prereq_text}"
        lines.append(detail)
        lines.append("")
        lines.append("──────────────")
    if not is_housing:
        lines.append(f"📄 صفحه {page + 1} از {total_pages}")
    kb = category_menu(ckey, counts, int(city.population), C.resource_total(resources), page, uid, pending=pending)
    return chr(10).join(lines), kb


@router.callback_query(F.data.startswith("city:cat:"))
async def city_category(callback: CallbackQuery):
    if not await ensure_owner(callback):
        return
    base = _cd(callback)
    parts = base.split(":")            # city:cat:{ckey}:{page}
    ckey = parts[2]
    page = int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else 0
    async with async_session() as session:
        text, kb = await _render_category(session, callback.from_user.id, ckey, page)
    await safe_edit(callback.message, text, kb)
    await safe_answer(callback)


@router.callback_query(F.data.startswith("city:wip"))
async def city_wip(callback: CallbackQuery):
    # 🐞 v1.7.8.12 — فیلتر قبلاً «F.data == "city:wip"» بود، ولی کیبورد
    # همیشه owner_id را به دادهٔ دکمه می‌چسباند («city:wip:<owner_id>»)،
    # پس این هندلر هیچ‌وقت اجرا نمی‌شد و دکمه بی‌کار می‌ماند.
    if not await ensure_owner(callback):
        return
    async with async_session() as session:
        city = await CS.get_city(session, callback.from_user.id)
        if not city:
            await safe_answer(callback, "شهر نداری.", show_alert=True)
            return
        rows = await CS.pending_builds(session, city.id)
        now = datetime.utcnow()
        if not rows:
            text = "🏗️ <b>در حال ساخت‌وساز</b>" + chr(10) + chr(10) + "فعلاً هیچ ساختمانی در حال ساخت نیست."
        else:
            lines = ["🏗️ <b>در حال ساخت‌وساز</b>", ""]
            for q in rows:
                left = max(0, int((q.ready_at - now).total_seconds()))
                label = C.building_name(q.btype) if q.kind != "warehouse" else "🏪 انبار شهر"
                if q.kind == "upgrade":
                    label = "⬆️ " + label
                qty_text = f" ×{max(1, int(q.qty or 1)):,}" if int(q.qty or 1) > 1 else ""
                lines.append(f"• {label}{qty_text} — {C.fmt_duration(left)} مانده")
            text = chr(10).join(lines)
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    b = InlineKeyboardBuilder()
    b.button(text="🔄 بروزرسانی", callback_data=_cb("city:wip", callback.from_user.id))
    b.button(text="↩️ بازگشت به شهر", callback_data=_cb("city:hub", callback.from_user.id))
    b.adjust(2)
    if not await safe_edit(callback.message, text, b.as_markup()):
        await callback.message.answer(text, reply_markup=b.as_markup())
    await safe_answer(callback)


@router.callback_query(F.data.startswith("city:build:"))
@router.callback_query(F.data.startswith("city:bq:"))
async def city_build_quantity(callback: CallbackQuery):
    """Open quantity choice; old city:build links stay compatible and spend nothing."""
    if not await ensure_owner(callback):
        return
    parts = _cd(callback).split(":")
    btype = parts[2] if len(parts) > 2 else ""
    page = int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else 0
    info = C.get_building(btype)
    if not info:
        await safe_answer(callback, "ساختمان نامعتبر است.", show_alert=True)
        return
    async with async_session() as session:
        city = await CS.get_city(session, callback.from_user.id)
        if city is None:
            await safe_answer(callback, "اول باید یک شهر بخری.", show_alert=True)
            return
        await CS.tick(session, city)
        counts = await CS.buildings_summary(session, callback.from_user.id)
        pending_rows = await CS.pending_builds(session, city.id)
        await session.commit()
    pending = sum(max(1, int(row.qty or 1)) for row in pending_rows if row.kind == "build" and row.btype == btype)
    text = (
        f"🔢 <b>تعداد ساخت را انتخاب کن</b>\n\n"
        f"🏗️ {C.building_name(btype)}\n"
        f"📊 موجود: {int(counts.get(btype, 0)):,} | در صف: {pending:,}\n"
        f"💵 قیمت هر واحد: {int(info.get('cost', 0)):,}\n"
        f"📦 مصالح هر واحد: {C.requirements_text(C.material_requirements(btype))}\n"
        f"⏱️ زمان دسته: {C.fmt_duration(C.build_seconds(btype))}\n\n"
        f"حد هر درخواست: {C.BATCH_BUILD_MIN:,} تا {C.BATCH_BUILD_MAX:,} واحد. "
        "پس از انتخاب، پیش‌فاکتور و تأیید نهایی نمایش داده می‌شود."
    )
    await safe_edit(callback.message, text, build_quantity_menu(btype, page, callback.from_user.id))
    await safe_answer(callback)


@router.callback_query(F.data.startswith("city:bv:"))
async def city_build_preview(callback: CallbackQuery):
    if not await ensure_owner(callback):
        return
    parts = _cd(callback).split(":")
    btype = parts[2] if len(parts) > 2 else ""
    amount = C.normalize_build_amount(parts[3] if len(parts) > 3 else None)
    page = int(parts[4]) if len(parts) > 4 and parts[4].isdigit() else 0
    if amount is None:
        await safe_answer(callback, "تعداد نامعتبر است.", show_alert=True)
        return
    async with async_session() as session:
        ready, reason, plan = await CS.build_plan(session, callback.from_user.id, btype, amount)
        await session.commit()
    if not plan:
        await safe_answer(callback, reason, show_alert=True)
        return
    await safe_edit(callback.message, CS.build_plan_text(plan, ready), build_confirm_menu(btype, amount, page, callback.from_user.id, can_confirm=ready))
    await safe_answer(callback)


@router.callback_query(F.data.startswith("city:bx:"))
async def city_build_custom_amount(callback: CallbackQuery, state: FSMContext):
    if not await ensure_owner(callback):
        return
    parts = _cd(callback).split(":")
    btype = parts[2] if len(parts) > 2 else ""
    page = int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else 0
    if not C.get_building(btype):
        await safe_answer(callback, "ساختمان نامعتبر است.", show_alert=True)
        return
    await state.update_data(city_build_btype=btype, city_build_page=page)
    await state.set_state(CityStates.building_amount)
    hint = f"🔢 تعداد دلخواه «{C.building_name(btype)}» را بفرست ({C.BATCH_BUILD_MIN:,} تا {C.BATCH_BUILD_MAX:,})." + CANCEL_HINT
    if callback.message.chat.type != "private":
        hint += "\n\n💬 روی همین پیام ریپلای کن و فقط عدد را بفرست."
    await callback.message.answer(hint)
    await safe_answer(callback)


@router.message(StateFilter(CityStates.building_amount))
async def city_build_amount_receive(message: Message, state: FSMContext):
    if await handle_cancel_word(message, state):
        return
    amount = C.normalize_build_amount(message.text)
    if amount is None:
        await message.answer(f"⚠️ یک عدد صحیح بین {C.BATCH_BUILD_MIN:,} تا {C.BATCH_BUILD_MAX:,} بفرست." + CANCEL_HINT)
        return
    data = await state.get_data()
    btype = str(data.get("city_build_btype") or "")
    page = int(data.get("city_build_page") or 0)
    async with async_session() as session:
        ready, reason, plan = await CS.build_plan(session, message.from_user.id, btype, amount)
        await session.commit()
    await state.clear()
    if not plan:
        await message.answer(reason)
        return
    await message.answer(CS.build_plan_text(plan, ready), reply_markup=build_confirm_menu(btype, amount, page, message.from_user.id, can_confirm=ready))


@router.callback_query(F.data.startswith("city:bc:"))
async def city_build_confirm(callback: CallbackQuery):
    if not await ensure_owner(callback):
        return
    parts = _cd(callback).split(":")
    btype = parts[2] if len(parts) > 2 else ""
    amount = C.normalize_build_amount(parts[3] if len(parts) > 3 else None)
    page = int(parts[4]) if len(parts) > 4 and parts[4].isdigit() else 0
    if amount is None:
        await safe_answer(callback, "تعداد نامعتبر است.", show_alert=True)
        return
    async with async_session() as session:
        ok, result = await CS.build_many(session, callback.from_user.id, btype, amount)
        category = C.category_of(btype) or "housing"
        text, kb = await _render_category(session, callback.from_user.id, category, page)
    await safe_edit(callback.message, text, kb)
    await safe_answer(callback, result, show_alert=True)

@router.callback_query(F.data.startswith("city:up:"))
async def city_upgrade(callback: CallbackQuery):
    if not await ensure_owner(callback):
        return
    base = _cd(callback)
    parts = base.split(":")            # city:up:{btype}:{page}
    btype = parts[2]
    page = int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else 0
    async with async_session() as session:
        ok, msg = await CS.upgrade(session, callback.from_user.id, btype)
        ckey = C.category_of(btype) or "infra"
        text, kb = await _render_category(session, callback.from_user.id, ckey, page)
    await safe_edit(callback.message, text, kb)
    await safe_answer(callback, msg, show_alert=True)


@router.callback_query(F.data.startswith("city:conv:"))
async def city_convert(callback: CallbackQuery):
    if not await ensure_owner(callback):
        return
    base = _cd(callback)
    parts = base.split(":")            # city:conv:{btype}:{page}
    btype = parts[2]
    page = int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else 0
    async with async_session() as session:
        ok, msg = await CS.convert_housing(session, callback.from_user.id, btype)
        text, kb = await _render_category(session, callback.from_user.id, "housing", page)
    await safe_edit(callback.message, text, kb)
    await safe_answer(callback, msg, show_alert=True)


# ---------------------------------------------------------------------------
# خرید منابع متنوع شهر
# ---------------------------------------------------------------------------
@router.callback_query(F.data.startswith("city:resources"))
async def city_resources(callback: CallbackQuery):
    if not await ensure_owner(callback):
        return
    async with async_session() as session:
        city = await CS.get_city(session, callback.from_user.id)
        if not city:
            await safe_answer(callback, "اول باید یک شهر بخری.", show_alert=True); return
        await CS.tick(session, city); await session.commit()
        resources = CS._resources(city)
        text = ("🛒 <b>خرید مواد اولیه</b>\n"
                f"📦 فضای انبار: {C.resource_total(resources):,} / {C.warehouse_capacity(city.warehouse_level):,}\n\n"
                + C.resource_text(resources) + "\n\nهر ماده را انتخاب کن و سپس مقدارش را بفرست.")
    await safe_edit(callback.message, text, resources_menu(callback.from_user.id, resources))
    await safe_answer(callback)


@router.callback_query(F.data.startswith("city:res:"))
async def city_resource_choose(callback: CallbackQuery, state: FSMContext):
    if not await ensure_owner(callback):
        return
    key = _cd(callback).split(":")[2]
    if key not in C.RESOURCES:
        await safe_answer(callback, "منبع نامعتبر است.", show_alert=True); return
    await state.update_data(city_resource_key=key)
    await state.set_state(CityStates.buying_resource_amount)
    hint = f"مقدار {C.resource_name(key)} را بفرست. قیمت هر واحد: {C.resource_price(key):,}$" + CANCEL_HINT
    if callback.message.chat.type != "private":
        hint += "\n\n💬 لطفاً روی همین پیام <b>ریپلای</b> کن و فقط عدد را بفرست تا با دستیار قاطی نشود."
    await callback.message.answer(hint)
    await safe_answer(callback)


@router.message(StateFilter(CityStates.buying_resource_amount))
async def city_resource_amount(message: Message, state: FSMContext):
    if await handle_cancel_word(message, state):
        return
    raw = (message.text or "").strip().replace(",", "").replace("٬", "")
    try:
        qty = int(raw)
    except ValueError:
        await message.answer("⚠️ مقدار باید عدد صحیح مثبت باشد."); return
    data = await state.get_data(); key = data.get("city_resource_key")
    async with async_session() as session:
        ok, msg = await CS.buy_resource(session, message.from_user.id, key, qty)
        text, kb = await render_hub(session, message.from_user.id)
    await state.clear()
    await message.answer(msg, reply_markup=kb)


# ---------------------------------------------------------------------------
# انبار
# ---------------------------------------------------------------------------
@router.callback_query(F.data.startswith("city:wh"))
async def city_warehouse(callback: CallbackQuery):
    if not await ensure_owner(callback):
        return
    async with async_session() as session:
        ok, msg = await CS.upgrade_warehouse(session, callback.from_user.id)
        text, kb = await render_hub(session, callback.from_user.id)
    await safe_edit(callback.message, text, kb)
    await safe_answer(callback, msg, show_alert=True)


# ---------------------------------------------------------------------------
# مالیات
# ---------------------------------------------------------------------------
@router.callback_query(F.data.startswith("city:tax"))
async def city_tax(callback: CallbackQuery):
    if not await ensure_owner(callback):
        return
    if _cd(callback).startswith("city:settax:"):
        return  # توسطِ هندلرِ دیگر پوشش داده می‌شود
    async with async_session() as session:
        city = await CS.get_city(session, callback.from_user.id)
        if not city:
            await safe_answer(callback, "اول باید یک شهر بخری.", show_alert=True)
            return
        text = (f"🧾 نرخِ مالیاتِ فعلی: {city.tax_rate}٪\n"
                f"خنثی: {C.TAX_NEUTRAL}٪ — بالاتر = درآمدِ بیشتر ولی رضایتِ کمتر.")
        kb = tax_menu(callback.from_user.id)
    await safe_edit(callback.message, text, kb)
    await safe_answer(callback)


@router.callback_query(F.data.startswith("city:settax:"))
async def city_settax(callback: CallbackQuery):
    if not await ensure_owner(callback):
        return
    base = _cd(callback)
    parts = base.split(":")            # city:settax:{rate}
    try:
        rate = int(parts[2])
    except (IndexError, ValueError):
        rate = C.TAX_NEUTRAL
    async with async_session() as session:
        ok, msg = await CS.set_tax(session, callback.from_user.id, rate)
        text, kb = await render_hub(session, callback.from_user.id)
    await safe_edit(callback.message, text, kb)
    await safe_answer(callback, msg, show_alert=True)


@router.callback_query(F.data.startswith("city:maxed"))
async def city_maxed(callback: CallbackQuery):
    await safe_answer(callback, "به بالاترین سطح رسیده.", show_alert=True)


@router.callback_query(F.data.startswith("city:sellresall"))
async def city_sell_all_resources(callback: CallbackQuery):
    if not await ensure_owner(callback):
        return
    uid = callback.from_user.id
    async with async_session() as session:
        city = await CS.get_city(session, uid)
        if city is None:
            await callback.answer("شهر نداری.", show_alert=True)
            return
        resources = dict(CS._resources(city) or {})
        total = 0
        for key, qty in list(resources.items()):
            q = int(qty or 0)
            if q <= 0:
                continue
            price = int(C.resource_sell_price(key) or 0)
            gain = (q * price * 80) // 100
            total += gain
            resources[key] = 0
        if total <= 0:
            await callback.answer("منبعی برای فروش نیست.", show_alert=True)
            return
        from sqlalchemy import select as _s
        player = (await session.execute(_s(Player).where(Player.tg_user_id == uid))).scalar_one_or_none()
        if player is None:
            await callback.answer("بازیکن پیدا نشد.", show_alert=True)
            return
        from app.services.bonus_breakdown import income_breakdown, append_note
        _br = await income_breakdown(session, uid, int(total))
        total = int(_br["total"])
        player.cash = int(player.cash or 0) + int(total)
        _sell_note = _br.get("note") or ""
        try:
            CS._set_resources(city, resources)
        except Exception:
            import json as _json
            city.resources_json = _json.dumps({k: int(v) for k, v in resources.items() if int(v or 0)}, ensure_ascii=False)
        await session.commit()
    note = locals().get("_sell_note") or ""
    from app.services.bonus_breakdown import append_note as _an
    await callback.answer(_an(f"💵 فروش همه: +{total:,}$", note), show_alert=bool(note))
    try:
        await city_resources(callback)
    except Exception:
        pass


@router.callback_query(F.data.startswith("city:sellres:"))
async def city_sell_one_resource(callback: CallbackQuery):
    if not await ensure_owner(callback):
        return
    uid = callback.from_user.id
    parts = callback.data.split(":")
    key = parts[2] if len(parts) >= 3 else ""
    async with async_session() as session:
        city = await CS.get_city(session, uid)
        if city is None:
            await callback.answer("شهر نداری.", show_alert=True)
            return
        resources = dict(CS._resources(city) or {})
        q = int(resources.get(key) or 0)
        if q <= 0:
            await callback.answer("موجودی این منبع صفر است.", show_alert=True)
            return
        price = int(C.resource_sell_price(key) or 0)
        gain = (q * price * 80) // 100
        from sqlalchemy import select as _s
        player = (await session.execute(_s(Player).where(Player.tg_user_id == uid))).scalar_one_or_none()
        if player is None:
            await callback.answer("بازیکن پیدا نشد.", show_alert=True)
            return
        from app.services.bonus_breakdown import income_breakdown, append_note
        _br = await income_breakdown(session, uid, int(gain))
        gain = int(_br["total"])
        player.cash = int(player.cash or 0) + int(gain)
        _sell_note = _br.get("note") or ""
        resources[key] = 0
        try:
            CS._set_resources(city, resources)
        except Exception:
            import json as _json
            city.resources_json = _json.dumps({k: int(v) for k, v in resources.items() if int(v or 0)}, ensure_ascii=False)
        await session.commit()
    note = locals().get("_sell_note") or ""
    from app.services.bonus_breakdown import append_note as _an
    await callback.answer(_an(f"💵 {C.resource_name(key)}: +{gain:,}$", note), show_alert=bool(note))
    try:
        await city_resources(callback)
    except Exception:
        pass




# ---------------------------------------------------------------------------
# v1.7.6.5 -- شهرداری: استخدام، اخراج، پیامِ مردم
# ترتیبِ ثبت مهم است: hire/fire باید قبل از هندلرِ عمومیِ city:mayor بیاید،
# وگرنه startswith("city:mayor") هر دو را می‌بلعد.
# ---------------------------------------------------------------------------
async def _render_mayor(session, uid: int):
    text = await CS.mayor_panel_text(session, uid)
    city = await CS.get_city(session, uid)
    hired = getattr(city, "mayor_key", None) if city else None
    return text, city_mayor_menu(uid, hired)


@router.callback_query(F.data.startswith("city:mayor:hire:"))
async def city_mayor_hire(callback: CallbackQuery):
    if not await ensure_owner(callback):
        return
    parts = _cd(callback).split(":")
    key = parts[3] if len(parts) > 3 else ""
    async with async_session() as session:
        ok, msg = await CS.hire_mayor(session, callback.from_user.id, key)
        text, kb = await _render_mayor(session, callback.from_user.id)
    body = (msg + "\n\n" + text) if ok else text
    await safe_edit(callback.message, body, kb)
    await safe_answer(callback, None if ok else msg)


@router.callback_query(F.data.startswith("city:mayor:fire"))
async def city_mayor_fire(callback: CallbackQuery):
    if not await ensure_owner(callback):
        return
    async with async_session() as session:
        ok, msg = await CS.fire_mayor(session, callback.from_user.id)
        text, kb = await _render_mayor(session, callback.from_user.id)
    body = (msg + "\n\n" + text) if ok else text
    await safe_edit(callback.message, body, kb)
    await safe_answer(callback, None if ok else msg)


@router.callback_query(F.data.startswith("city:mayor"))
async def city_mayor_panel(callback: CallbackQuery):
    if not await ensure_owner(callback):
        return
    async with async_session() as session:
        text, kb = await _render_mayor(session, callback.from_user.id)
    await safe_edit(callback.message, text, kb)
    await safe_answer(callback)
