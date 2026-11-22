# -*- coding: utf-8 -*-
"""v1.7.9.2 — هندلرهای فوتبال منیجر (مرحله ۷۹ — فاز F1: اسکلت + دوستانه).

این روتر قبل از sports.router ثبت می‌شود تا «sport:open:football» و «sport:create:football»
و «sport:play:football» به سیستمِ جدید برسند — فوتبالِ قدیمی کاملاً جایگزین می‌شود؛
باقی ورزش‌ها (بسکتبال/مسابقه‌ای) دست‌نخورده می‌مانند.
"""
from __future__ import annotations

import random

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select

from app.data import football_players as FP
from app.database.engine import async_session
from app.handlers.profile import get_player
from app.keyboards.football_menu import (
    football_back_menu,
    football_hub_menu,
    football_no_club_menu,
    football_sec_club_menu,
    football_sec_comp_menu,
    football_sec_shop_menu,
    football_sec_team_menu,
)
from app.models.football import FootballMatch
from app.services import football_service as FS
from app.states import FootballStates
from app.utils.ui import (
    CANCEL_HINT,
    ensure_owner,
    handle_cancel_word,
    safe_answer,
    safe_show,
    split_owner,
    with_owner,
)


def _fb_exact(base: str):
    """فیلتر: تطبیق دقیقِ callback روی بخشِ پایه (بدون پسوند :owner).

    دکمه‌ها با with_owner ساخته می‌شوند (`fb:X:uid`)، پس F.data == "fb:X" هرگز نمی‌خواند.
    این فیلتر base را مقایسه می‌کند تا دکمه‌ها کار کنند و با fb:X:sub برخورد پیشوندی نباشد.
    """
    async def _f(callback: CallbackQuery) -> bool:
        return split_owner(callback.data)[0] == base
    return _f


router = Router(name="football")

_TIER_FA = {"common": "عادی", "rare": "نایاب", "epic": "حماسی", "legend": "افسانه‌ای", "mythic": "اساطیر"}


# --------------------------- ورود از بخش ورزش (جایگزینی فوتبال قدیمی) ---------------------------
@router.callback_query(F.data == "sport:open:football")
async def open_football(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    await _show_hub(callback)


@router.callback_query(F.data == "sport:create:football")
async def create_football_redirect(callback: CallbackQuery, state: FSMContext) -> None:
    if not await ensure_owner(callback):
        return
    await create_start(callback, state)


@router.callback_query(F.data == "sport:play:football")
async def play_football_redirect(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    await play_friendly(callback)


# --------------------------- هاب ---------------------------
async def _hub_text(session, uid: int) -> tuple[str, object]:
    club = await FS.get_club(session, uid)
    if club is None:
        text = (
            "⚽ <b>فوتبال منیجر</b>\n\n"
            "هنوز باشگاهی نداری.\n"
            f"🏟️ ساخت باشگاه — هزینه: <b>{FS.CLUB_CREATE_COST:,}$</b>\n"
            "(پکیج شروع: استادیوم ۱۲٬۵۰۰ + سرمربی سطح ۱ + ۱۸ بازیکن رایگان + ۲٬۰۰۰ طرفدار)"
        )
        return text, football_no_club_menu(uid)
    cards = await FS.squad(session, club.id)
    power = FS.team_power(session, club, cards)
    played = await FS.friendlies_today(session, uid)
    style_fa = {"full_attack": "فول‌اتک", "full_defense": "فول‌دیفنس", "possession": "بازی مالکانه", "counter": "ضدحمله"}.get(club.coach_style, club.coach_style)
    text = (
        f"{club.icon} <b>{club.name}</b>\n\n"
        f"⭐ قدرت تیم: <b>{power:,}</b>\n"
        f"👥 طرفدار: {int(club.fans or 0):,}  |  🏟️ استادیوم: {int(club.stadium_capacity or 0):,}\n"
        f"🧠 سرمربی: {style_fa} — سطح {int(club.coach_level or 1)} ({'⭐' * int(club.coach_stars or 1)})\n"
        f"🧑‍💼 بازیکن‌ها: {len(cards)}  |  🤝 دوستانه امروز: {played}/{FS.FRIENDLY_DAILY_LIMIT}"
    )
    return text, football_hub_menu(uid)


async def _show_hub(callback: CallbackQuery) -> None:
    async with async_session() as session:
        text, markup = await _hub_text(session, callback.from_user.id)
    await safe_show(callback.message, text, markup)
    await safe_answer(callback)


@router.callback_query(_fb_exact("fb:hub"))
async def hub_cb(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    await _show_hub(callback)


# --------------------------- ساخت باشگاه (FSM) ---------------------------
@router.callback_query(_fb_exact("fb:create"))
async def create_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not await ensure_owner(callback):
        return
    await state.set_state(FootballStates.creating_name)
    await safe_show(
        callback.message,
        (f"🏟️ <b>ساخت باشگاه</b> — هزینه: {FS.CLUB_CREATE_COST:,}$\n\n"
         f"نام باشگاه را بفرست ({FS.NAME_MIN} تا {FS.NAME_MAX} کاراکتر):\n{CANCEL_HINT}"),
        football_back_menu(callback.from_user.id),
    )
    await safe_answer(callback)


@router.message(FootballStates.creating_name)
async def create_recv(message: Message, state: FSMContext) -> None:
    if await handle_cancel_word(message, state):
        return
    name = (message.text or "").strip()
    uid = message.from_user.id
    async with async_session() as session:
        player = await get_player(session, uid)
        ok, res = await FS.create_club(session, uid, name, player)
        await session.commit()
    await state.clear()
    if ok:
        await message.reply(
            f"✅ باشگاهِ <b>{name}</b> ساخته شد!\n"
            "🎁 پکیج شروع: استادیوم ۱۲٬۵۰۰ + سرمربی سطح ۱ + ۱۸ بازیکن رایگان + ۲٬۰۰۰ طرفدار.\n"
            "از «⚽ ورزش ← فوتبال» وارد باشگاهت شو."
        )
    else:
        await message.reply(res)


# --------------------------- بازیکن‌ها ---------------------------
@router.callback_query(F.data.startswith("fb:squad"))
async def squad_cb(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    base, _ = split_owner(callback.data)
    parts = base.split(":")
    page = int(parts[2]) if len(parts) >= 3 and parts[2].isdigit() else 0
    uid = callback.from_user.id
    async with async_session() as session:
        club = await FS.get_club(session, uid)
        if club is None:
            await safe_answer(callback, "اول باشگاه بساز.", show_alert=True)
            return
        cards = await FS.squad(session, club.id)
        cards.sort(key=lambda c: FS.effective_power(c, club), reverse=True)
        eleven = {c.id for c in FS.best_eleven(cards, club)}
    per = 8
    total = max(1, (len(cards) + per - 1) // per)
    page = max(0, min(page, total - 1))
    chunk = cards[page * per:(page + 1) * per]
    from datetime import datetime as _dt
    _squad_now = _dt.utcnow()
    lines = [f"🧑‍💼 <b>بازیکن‌های {club.name}</b> ({len(cards)} نفر)", ""]
    from app.utils.table import render_table, table_mode_on
    if await table_mode_on("football_squad"):
        _rows = []
        for c in chunk:
            star = "🟢" if c.id in eleven else "⚪"
            inj = "🏥" if (c.injured_until and c.injured_until > _squad_now) else "-"
            _rows.append([star, c.name, c.pos, f"{FS.effective_power(c, club):,}", _TIER_FA.get(c.tier, c.tier), inj])
        lines.append(render_table(["", "نام", "پست", "پاور", "رده", "وضعیت"], _rows))
    else:
        for c in chunk:
            star = "🟢" if c.id in eleven else "⚪"
            inj = " 🏥" if (c.injured_until and c.injured_until > _squad_now) else ""
            lines.append(
                f"{star} <b>{c.name}</b> — {c.pos} — 💪{FS.effective_power(c, club):,} "
                f"({_TIER_FA.get(c.tier, c.tier)}){inj} — <code>{c.tracking_code}</code>"
            )
    lines += ["", "🟢 = ترکیب اصلی (بهترین ۱۱)  |  ⚪ = نیمکت"]
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from app.utils.ui import with_owner
    b = InlineKeyboardBuilder()
    if page > 0:
        b.button(text="◀️ قبلی", callback_data=with_owner(f"fb:squad:{page-1}", uid))
    if page < total - 1:
        b.button(text="بعدی ▶️", callback_data=with_owner(f"fb:squad:{page+1}", uid))
    b.button(text="⚽ بازگشت به باشگاه", callback_data=with_owner("fb:hub", uid))
    b.adjust(2, 1)
    await safe_show(callback.message, "\n".join(lines), b.as_markup())
    await safe_answer(callback)


# --------------------------- بازی دوستانه ---------------------------
@router.callback_query(_fb_exact("fb:play"))
async def play_friendly(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    uid = callback.from_user.id
    async with async_session() as session:
        club = await FS.get_club(session, uid)
        if club is None:
            await safe_answer(callback, "اول باشگاه بساز.", show_alert=True)
            return
        played = await FS.friendlies_today(session, uid)
        if played >= FS.FRIENDLY_DAILY_LIMIT:
            await safe_answer(
                callback,
                f"🚫 سقف دوستانه‌ی امروز ({FS.FRIENDLY_DAILY_LIMIT} مسابقه) پر شد — فردا دوباره.",
                show_alert=True,
            )
            return
        info = await FS.play_friendly(session, uid, random.Random())
        await session.commit()
    if info is None:
        await safe_answer(callback, "اول باشگاه بساز.", show_alert=True)
        return
    if info.get("error"):
        await safe_answer(callback, info["error"], show_alert=True)
        return
    await safe_show(callback.message, info["report"], football_back_menu(uid))
    await safe_answer(callback, "🏁")


# --------------------------- آخرین نتایج ---------------------------
@router.callback_query(_fb_exact("fb:results"))
async def results_cb(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    uid = callback.from_user.id
    async with async_session() as session:
        club = await FS.get_club(session, uid)
        if club is None:
            await safe_answer(callback, "اول باشگاه بساز.", show_alert=True)
            return
        rows = list((await session.execute(
            select(FootballMatch).where(FootballMatch.home_club_id == club.id)
            .order_by(FootballMatch.created_at.desc()).limit(5)
        )).scalars().all())
    lines = [f"📜 <b>آخرین نتایج {club.name}</b>", ""]
    if not rows:
        lines.append("هنوز مسابقه‌ای نداری. از «🤝 بازی دوستانه» شروع کن.")
    for r in rows:
        mark = "✅" if r.home_goals > r.away_goals else ("🟰" if r.home_goals == r.away_goals else "❌")
        lines.append(f"{mark} {r.home_goals}-{r.away_goals} ({r.mode}) — {r.created_at.strftime('%m/%d %H:%M')}")
    await safe_show(callback.message, "\n".join(lines), football_back_menu(uid))
    await safe_answer(callback)


# --------------------------- به‌زودی (فازهای بعدی) ---------------------------
@router.callback_query(F.data.startswith("fb:soon"))
async def soon_cb(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    base, _ = split_owner(callback.data)
    what = base.split(":", 2)[2] if ":" in base[3:] or base.count(":") >= 2 else "این بخش"
    await safe_answer(callback, f"🚧 «{what}» در آپدیت‌های بعدی فعال می‌شود (طبق نقشه‌ی فازها).", show_alert=True)


# --------------------------- راهنما ---------------------------
@router.callback_query(_fb_exact("fb:guide"))
async def guide_cb(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    # 🆕 v1.8.1.6 — راهنمای کاربریِ کامل (به‌جای نقشهٔ فازهای توسعه که برای کاربر بی‌معنی بود)
    text = (
        "📖 <b>راهنمای فوتبال منیجر</b>\n\n"
        f"🏟️ <b>شروع:</b> باشگاهت را بساز (هزینه {FS.CLUB_CREATE_COST:,}$) — پکیج شروع: استادیوم ۱۲٬۵۰۰ نفره + سرمربی سطح ۱ + ۱۸ بازیکن رایگان + ۲٬۰۰۰ طرفدار.\n\n"
        f"🤝 <b>بازی دوستانه:</b> روزی {FS.FRIENDLY_DAILY_LIMIT} مسابقه با حریف تمرینی — نتیجه و گلزنان ثبت می‌شود و جدول لیگ را تغییر می‌دهد.\n"
        "🎮 <b>بازی زنده:</b> هر مسابقه ۱۰ دقیقهٔ واقعی = ۹۰ دقیقه؛ گل‌ها دقیقه‌به‌دقیقه می‌آیند و از «بازی زنده» دنبالشان کن.\n"
        "📜 <b>آخرین نتایج:</b> ۵ بازی اخیرت.\n\n"
        "👥 <b>تیم و تاکتیک:</b>\n"
        "• بازیکن‌ها و نیمکت — ترکیب اصلی (🟢) = بهترین ۱۱ بازیکن سالم بر اساس آرایش؛ مصدوم‌ها 🏥 قدرتشان صفر است.\n"
        "• سرمربی — ۴ سبک (فول‌اتک / فول‌دیفنس / بازی مالکانه / ضدحمله)؛ تعویض سبک هفته‌ای ۱ بار رایگان است. با برد رسمی XP می‌گیری و سطحش بالا می‌رود؛ ستاره تا ۴⭐ با دلار بازی ساخته می‌شود و ۵⭐ فقط از فروشگاه واقعی است.\n"
        "• ترکیب و تاکتیک — تهاجمی (بیشتر می‌زنی، بیشتر می‌خوری) / متعادل / دفاعی (کمتر می‌زنی، کمتر می‌خوری)؛ اتو‌تاکتیک خودکار بر اساس قدرت حریف انتخاب می‌کند.\n"
        "• تمرین و کمپ — روزی ۳ جلسه؛ مصدومیت یک‌بار برای کل تیم رول می‌شود و هر جلسه حداکثر یک مصدوم دارد.\n\n"
        "🏟️ <b>باشگاه و هوادار:</b> استادیوم ۹ سطح تا ۱۲۵٬۰۰۰ نفر ارتقا می‌یابد (بلیت هر سطح گران‌تر)؛ در سوشال مدیا روزی ۲ پست عکس‌دار بگذار ← طرفدار و فالوور می‌گیری؛ هر ۲۰M فالوور = +۱٪ قدرت تیم (سقف ۲۵٪) + جایزهٔ مایلستون‌ها.\n\n"
        "🛒 <b>بازار و فروشگاه:</b> بازیکن عادی با دلار بازی (خرید مستقیم و نامحدود)؛ بازیکن تک‌نسخه‌ای با تومان ← مزایدهٔ ۲ ساعته و بالاترین پیشنهاد بعد از تأیید ادمین ۳۰ دقیقه برای پرداخت وقت دارد؛ بازیکنِ فروخته‌شده فقط با «درخواست به دارنده» جابه‌جا می‌شود؛ فروشگاه سرمربی ۵⭐ با ضریب قدرت ×۱٫۲۵.\n\n"
        "🏆 <b>رقابت‌ها:</b> جدول لیگ دائمی (برد ۳ / مساوی ۱ / باخت ۰)؛ لیگ جمعه (ثبت‌نام تا پنجشنبه، جمعه دوری رفت‌وبرگشت + جایزهٔ قهرمان)؛ لیگ قهرمانان دوشنبه (مرحلهٔ گروهی + صعود، بازی‌ها زنده)."
    )
    await safe_show(callback.message, text, football_back_menu(callback.from_user.id))
    await safe_answer(callback)

# --------------------------- F2 (v1.7.9.4): سرمربی / استادیوم / سوشال / تمرین ---------------------------
@router.callback_query(_fb_exact("fb:coach"))
async def coach_cb(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    uid = callback.from_user.id
    async with async_session() as session:
        club = await FS.get_club(session, uid)
        if club is None:
            await safe_answer(callback, "اول باشگاه بساز.", show_alert=True)
            return
        from app.services import football_progress as FPROG
        from app.data import football_progress as FPD
        state = await FPROG.get_state(session, club.id)
        xp_map = FPROG.coach_xp_map(state)
        cur = int(club.coach_stars or 1)
        level = int(club.coach_level or 1)
        style = club.coach_style
        lines = [
            "🧠 <b>سرمربی</b>", "",
            f"سبک فعلی: <b>{FPD.COACH_STYLES[style]['name']}</b> — {FPD.COACH_STYLES[style]['effect']}",
            f"ستاره: {'⭐' * cur} (ضریب قدرت داخل زمین ×{FPD.coach_star_mult(cur):.2f})",
            f"سطح سرمربی: {level}/{FPD.COACH_LEVEL_MAX}",
            "", "📊 XP هر سبک (جدا برای هر سبک):",
        ]
        for k in FPD.STYLE_ORDER:
            lines.append(f"• {FPD.COACH_STYLES[k]['name']}: {xp_map.get(k, 0)} XP")
        lines.append("")
        if cur < FPD.STAR_MAX_BUILD:
            cost, req = FPD.STAR_BUILD[cur + 1]
            lines.append(f"⭐ ستاره بعدی ({cur+1}⭐): {cost:,}$ + سطح سرمربی {req} (فعلی: {level})")
        else:
            lines.append("⭐ ستاره ۵ فقط از فروشگاه واقعی.")
        lines.append(f"🔄 تعویض سبک: هفته‌ای {FPD.STYLE_FREE_PER_WEEK} بار رایگان، بعد {FPD.STYLE_CHANGE_COST:,}$")
        from app.keyboards.football_menu import football_coach_menu
        mk = football_coach_menu(uid, style)
    await safe_show(callback.message, "\n".join(lines), mk)
    await safe_answer(callback)


@router.callback_query(F.data.startswith("fb:coach:style:"))
async def coach_style_cb(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    base, _ = split_owner(callback.data)
    style = base.split(":")[3]
    uid = callback.from_user.id
    async with async_session() as session:
        club = await FS.get_club(session, uid)
        if club is None:
            await safe_answer(callback, "اول باشگاه بساز.", show_alert=True)
            return
        player = await get_player(session, uid)
        from app.services import football_progress as FPROG
        state = await FPROG.get_state(session, club.id)
        ok, msg = await FPROG.change_style(session, club, state, player, style)
        await session.commit()
    await safe_answer(callback, msg, show_alert=True)
    if ok:
        await coach_cb(callback)


@router.callback_query(_fb_exact("fb:coach:star"))
async def coach_star_cb(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    uid = callback.from_user.id
    async with async_session() as session:
        club = await FS.get_club(session, uid)
        if club is None:
            await safe_answer(callback, "اول باشگاه بساز.", show_alert=True)
            return
        player = await get_player(session, uid)
        from app.services import football_progress as FPROG
        state = await FPROG.get_state(session, club.id)
        ok, msg = await FPROG.build_star(session, club, state, player)
        await session.commit()
    await safe_answer(callback, msg, show_alert=True)
    if ok:
        await coach_cb(callback)


@router.callback_query(_fb_exact("fb:stadium"))
async def stadium_cb(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    uid = callback.from_user.id
    async with async_session() as session:
        club = await FS.get_club(session, uid)
        if club is None:
            await safe_answer(callback, "اول باشگاه بساز.", show_alert=True)
            return
        from app.services import football_progress as FPROG
        from app.data import football_progress as FPD
        level = int(club.stadium_level or 0)
        cap = int(club.stadium_capacity or 0)
        attendance = await FPROG.expected_attendance(session, club)
        lines = [
            "🏟️ <b>استادیوم و هوادار</b>", "",
            f"سطح: {FPD.stadium_display_level(level)}/{FPD.STADIUM_LEVEL_COUNT}  |  ظرفیت: {cap:,}",
            f"🎟️ بلیت: {FPD.TICKET_PRICE_BY_LEVEL[level]}$  |  👥 حضور تقریبی: {attendance:,}",
            f"❤️ طرفدار: {int(club.fans or 0):,}",
            "",
        ]
        if level < FPD.STADIUM_MAX_LEVEL:
            lines.append(f"⬆️ ارتقا به سطح {FPD.stadium_display_level(level)+1}: {FPD.stadium_upgrade_cost(level):,}$ → ظرفیت {FPD.stadium_capacity(level+1):,}")
        else:
            lines.append("✅ استادیوم سطح ۱۰ — بیشینه ظرفیت ۱۲۵٬۰۰۰ و سقف قیمت ۱۰۰ میلیارد دلار بازی.")
        from app.keyboards.football_menu import football_stadium_menu
        mk = football_stadium_menu(uid)
    await safe_show(callback.message, "\n".join(lines), mk)
    await safe_answer(callback)


@router.callback_query(_fb_exact("fb:stadium:up"))
async def stadium_up_cb(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    uid = callback.from_user.id
    async with async_session() as session:
        club = await FS.get_club(session, uid)
        if club is None:
            await safe_answer(callback, "اول باشگاه بساز.", show_alert=True)
            return
        player = await get_player(session, uid)
        from app.services import football_progress as FPROG
        ok, msg = await FPROG.upgrade_stadium(session, club, player)
        await session.commit()
    await safe_answer(callback, msg, show_alert=True)
    if ok:
        await stadium_cb(callback)


@router.callback_query(_fb_exact("fb:social"))
async def social_cb(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    uid = callback.from_user.id
    async with async_session() as session:
        club = await FS.get_club(session, uid)
        if club is None:
            await safe_answer(callback, "اول باشگاه بساز.", show_alert=True)
            return
        from app.services import football_progress as FPROG
        from app.data import football_progress as FPD
        state = await FPROG.get_state(session, club.id)
        today_posts = int(state.social_count or 0) if state.social_date == __import__("datetime").datetime.utcnow().date().isoformat() else 0
        lines = [
            "📱 <b>سوشال مدیا</b>", "",
            f"👥 طرفدار: {int(club.fans or 0):,}  |  📈 فالوور سوشال: {int(club.social_followers or 0):,}",
            f"⭐ بونوس پاور از سوشال: +{FPD.social_power_pct(int(club.social_followers or 0))}٪ (هر ۲۰M فالوور = +۱٪، سقف ۲۵٪)",
            f"📤 پست امروز: {today_posts}/{FPD.SOCIAL_POSTS_PER_DAY}",
            "",
            "هر پست = ۲۵۰ تا ۲٬۰۰۰ طرفدار جدید (فالوور سوشال ×۸).",
        ]
        from app.keyboards.football_menu import football_social_menu
        mk = football_social_menu(uid)
    await safe_show(callback.message, "\n".join(lines), mk)
    await safe_answer(callback)


@router.callback_query(_fb_exact("fb:social:post"))
async def social_post_cb(callback: CallbackQuery, state: FSMContext) -> None:
    if not await ensure_owner(callback):
        return
    await state.set_state(FootballStates.social_wait_photo)
    await safe_show(
        callback.message,
        f"📤 <b>پست جدید سوشال</b>\n\nعکس پست را بفرست (هر پست = طرفدار و فالوور جدید).\n{CANCEL_HINT}",
        football_back_menu(callback.from_user.id),
    )
    await safe_answer(callback)


@router.message(FootballStates.social_wait_photo)
async def social_photo_recv(message: Message, state: FSMContext) -> None:
    if await handle_cancel_word(message, state):
        return
    if not message.photo:
        await message.reply("📷 لطفاً یک <b>عکس</b> بفرست (پست سوشال با عکس است).")
        return
    uid = message.from_user.id
    async with async_session() as session:
        club = await FS.get_club(session, uid)
        if club is None:
            await message.reply("اول باشگاه بساز.")
            await state.clear()
            return
        player = await get_player(session, uid)
        from app.services import football_progress as FPROG
        state_obj = await FPROG.get_state(session, club.id)
        ok, msg = await FPROG.social_post(session, club, state_obj, player)
        await session.commit()
    await state.clear()
    await message.reply(msg)


@router.callback_query(_fb_exact("fb:train"))
async def train_cb(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    uid = callback.from_user.id
    async with async_session() as session:
        club = await FS.get_club(session, uid)
        if club is None:
            await safe_answer(callback, "اول باشگاه بساز.", show_alert=True)
            return
        from app.services import football_progress as FPROG
        from app.data import football_progress as FPD
        state = await FPROG.get_state(session, club.id)
        camps = int(club.training_camps or 0)
        cards = await FS.squad(session, club.id)
        from datetime import datetime as _dt
        now = _dt.utcnow()
        injured = sum(1 for c in cards if c.injured_until and c.injured_until > now)
        avg_bonus = (sum(int(c.training_bonus or 0) for c in cards) / len(cards)) if cards else 0
        today_sessions = int(state.train_count or 0) if state.train_date == now.date().isoformat() else 0
        lines = [
            "🏋️ <b>تمرین و کمپ</b>", "",
            f"🏕️ کمپ‌ها: {camps}/{FPD.CAMP_MAX}  |  اثر هر جلسه: +{FPD.camp_power_per_session(camps)} پاور",
            f"▶️ جلسات امروز: {today_sessions}/{FPD.TRAIN_SESSIONS_PER_DAY}",
            f"💪 میانگین بونوس تمرینی بازیکنان: +{avg_bonus:.1f}",
            f"🏥 مصدوم: {injured} نفر",
            "",
            "⚠️ مصدومیت یک‌بار برای کل تیم رول می‌شود؛ حداکثر یک نفر در هر جلسه و با ۱۱ بازیکن سالم، ریسک صفر است.",
            "📉 خستگی بالاتر و جلسه‌های دوم/سوم ریسک تیمی را کمی زیاد می‌کنند؛ فول‌دیفنس آن را کم می‌کند.",
        ]
        if camps < FPD.CAMP_MAX:
            lines.append(f"🏗️ ساخت کمپ {camps+1}: {FPD.CAMP_COSTS[camps]:,}$")
        from app.keyboards.football_menu import football_training_menu
        mk = football_training_menu(uid)
    await safe_show(callback.message, "\n".join(lines), mk)
    await safe_answer(callback)


@router.callback_query(_fb_exact("fb:train:camp"))
async def train_camp_cb(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    uid = callback.from_user.id
    async with async_session() as session:
        club = await FS.get_club(session, uid)
        if club is None:
            await safe_answer(callback, "اول باشگاه بساز.", show_alert=True)
            return
        player = await get_player(session, uid)
        from app.services import football_progress as FPROG
        ok, msg = await FPROG.build_camp(session, club, player)
        await session.commit()
    await safe_answer(callback, msg, show_alert=True)
    if ok:
        await train_cb(callback)


@router.callback_query(_fb_exact("fb:train:go"))
async def train_go_cb(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    uid = callback.from_user.id
    async with async_session() as session:
        club = await FS.get_club(session, uid)
        if club is None:
            await safe_answer(callback, "اول باشگاه بساز.", show_alert=True)
            return
        from app.services import football_progress as FPROG
        state = await FPROG.get_state(session, club.id)
        ok, msg = await FPROG.train_session(session, club, state)
        await session.commit()
    await safe_answer(callback, msg, show_alert=True)
    if ok:
        await train_cb(callback)

# --------------------------- فروشگاه سرمربی ۵⭐ (v1.7.9.5) ---------------------------
from app.data import football_coaches as FCOACH
from app.services import football_shop as FSHOP
from app.services import football_progress as FPROG
from app.services import football_service as FS

_STATUS_FA = {
    "pending": "⏳ در انتظار تأیید ادمین",
    "awaiting_payment": "💳 منتظر پرداخت و ارسال رسید",
    "receipt_sent": "🧾 رسید ارسال شد — منتظر تأیید",
    "done": "✅ فعال شد",
    "rejected": "❌ رد شد",
}


@router.callback_query(F.data.startswith("fb:coachshop") )
async def coachshop_cb(callback: CallbackQuery, state: FSMContext) -> None:
    if not await ensure_owner(callback):
        return
    base, _ = split_owner(callback.data)
    parts = base.split(":")[1:]   # 🐞 v1.8.1.6 — حذف پیشوند «fb»؛ قبلاً parts[1] همیشه نامِ بخش بود و همهٔ زیرمنوها می‌مردند
    sub = parts[1] if len(parts) > 1 else "0"
    uid = callback.from_user.id
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    async with async_session() as session:
        club = await FS.get_club(session, uid)
        if club is None:
            await safe_answer(callback, "اول باشگاه بساز.", show_alert=True)
            return

        # --- خریدهای من ---
        if sub == "mine":
            rows = await FSHOP.my_purchases(session, uid)
            lines = ["🧾 <b>خریدهای سرمربی‌ام</b>", ""]
            kb = InlineKeyboardBuilder()
            if not rows:
                lines.append("هنوز خریدی نداری.")
            for r in rows:
                lines.append(f"• <b>{r.coach_name}</b> — {int(r.price):,} تومان — {_STATUS_FA.get(r.status, r.status)} — <code>{r.tracking_code}</code>")
                if r.status == FSHOP.STATUS_AWAITING:
                    kb.button(text=f"📤 ارسال رسید ({r.tracking_code})", callback_data=with_owner(f"fb:coachshop:receipt:{r.tracking_code}", uid))
            kb.button(text="🧑‍✈️ فروشگاه سرمربی", callback_data=with_owner("fb:coachshop:0", uid))
            kb.button(text="⚽ بازگشت", callback_data=with_owner("fb:hub", uid))
            kb.adjust(1)
            await safe_show(callback.message, "\n".join(lines), kb.as_markup())
            await safe_answer(callback)
            return

        # --- ارسال رسید ---
        if sub == "receipt" and len(parts) >= 3:
            code = parts[2]
            await state.set_state(FootballStates.coach_receipt_wait)
            await state.update_data(coach_receipt_code=code)
            await safe_show(
                callback.message,
                f"📤 رسید پرداخت برای کد <code>{code}</code> را بفرست (عکس/فایل):\n{CANCEL_HINT}",
                football_back_menu(uid),
            )
            await safe_answer(callback)
            return

        # --- مشخصات + تأیید خرید ---
        if sub == "view" and len(parts) >= 3:
            coach = FCOACH.get(parts[2])
            if coach is None:
                await safe_answer(callback, "سرمربی نامعتبر.", show_alert=True)
                return
            price = await FSHOP.effective_price(session, coach["key"])
            kb = InlineKeyboardBuilder()
            kb.button(text=f"🛒 خرید — {price:,} تومان", callback_data=with_owner(f"fb:coachshop:confirm:{coach['key']}", uid))
            kb.button(text="◀️ لیست", callback_data=with_owner("fb:coachshop:0", uid))
            kb.adjust(1)
            text = (
                f"🧑‍✈️ <b>{coach['name']}</b>\n\n"
                f"⭐⭐⭐⭐⭐ سرمربی ۵ ستاره — ضریب قدرت داخل زمین ×1.25\n"
                f"💰 قیمت: <b>{price:,} تومان</b> (پول واقعی)\n"
                "🔁 غیرتک — هر کاربری می‌تواند بخرد."
            )
            await safe_show(callback.message, text, kb.as_markup())
            await safe_answer(callback)
            return

        # --- ثبت درخواست خرید ---
        if sub == "confirm" and len(parts) >= 3:
            coach = FCOACH.get(parts[2])
            if coach is None:
                await safe_answer(callback, "سرمربی نامعتبر.", show_alert=True)
                return
            ok, code, rec = await FSHOP.request_purchase(session, uid, coach["key"])
            await session.commit()
            if not ok:
                await safe_answer(callback, code, show_alert=True)
                return
            try:
                from app.services import subscription_service as SS
                pm = await SS.get_payment_method(session)
            except Exception:
                pm = None
            try:
                from app.config import MAIN_ADMIN_ID
                if MAIN_ADMIN_ID:
                    await callback.bot.send_message(
                        int(MAIN_ADMIN_ID),
                        f"⚽ درخواست خرید سرمربی: <b>{coach['name']}</b> ({int(rec.price):,} تومان)\n"
                        f"کاربر: <code>{uid}</code> | کد: <code>{code}</code>\n"
                        "از «ادمین‌مود ← ابزارها ← خریدهای ورزشی» مدیریت کن."
                    )
            except Exception:
                pass
            text = (
                f"✅ درخواست خرید <b>{coach['name']}</b> ثبت شد.\n\n"
                f"🔖 کد پیگیری: <code>{code}</code>\n"
                f"💰 مبلغ: <b>{int(rec.price):,} تومان</b>\n\n"
                + (f"💳 روش پرداخت: {pm}\n" if pm else "")
                + "ادمین درخواست را بررسی می‌کند؛ پس از تأیید، مبلغ را پرداخت و رسید را از «🧾 خریدهای من» بفرست."
            )
            kb = InlineKeyboardBuilder()
            kb.button(text="🧾 خریدهای من", callback_data=with_owner("fb:coachshop:mine", uid))
            kb.adjust(1)
            await safe_show(callback.message, text, kb.as_markup())
            await safe_answer(callback, "✅ درخواست ثبت شد")
            return

        # --- لیست سرمربی‌ها (پیش‌فرض) ---
        try:
            page = int(sub)
        except ValueError:
            page = 0
        keys = list(FCOACH.COACH_ORDER)
        per = 8
        total = max(1, (len(keys) + per - 1) // per)
        page = max(0, min(page, total - 1))
        chunk = keys[page * per:(page + 1) * per]
        lines = ["🧑‍✈️ <b>فروشگاه سرمربی ۵⭐</b>", "", "سرمربیان برتر دنیای واقعی — هر کدام ضریب قدرت ×1.25 می‌دهند. غیرتک (هرکس می‌تواند بخرد).", ""]
        kb = InlineKeyboardBuilder()
        for key in chunk:
            c = FCOACH.get(key)
            price = await FSHOP.effective_price(session, key)
            lines.append(f"⭐ <b>{c['name']}</b> — {price:,} تومان")
            kb.button(text=f"🛒 {c['name']} — {price:,}T", callback_data=with_owner(f"fb:coachshop:view:{key}", uid))
        kb.button(text="🧾 خریدهای من", callback_data=with_owner("fb:coachshop:mine", uid))
        if page > 0:
            kb.button(text="◀️ قبلی", callback_data=with_owner(f"fb:coachshop:{page-1}", uid))
        if page < total - 1:
            kb.button(text="بعدی ▶️", callback_data=with_owner(f"fb:coachshop:{page+1}", uid))
        kb.button(text="⚽ بازگشت به باشگاه", callback_data=with_owner("fb:hub", uid))
        kb.adjust(1)
        await safe_show(callback.message, "\n".join(lines), kb.as_markup())
        await safe_answer(callback)


@router.message(FootballStates.coach_receipt_wait)
async def coach_receipt_recv(message: Message, state: FSMContext) -> None:
    if await handle_cancel_word(message, state):
        return
    file_id = None
    if message.photo:
        file_id = message.photo[-1].file_id
    elif message.document:
        file_id = message.document.file_id
    if not file_id:
        await message.reply("📷 لطفاً رسید را به‌صورت عکس یا فایل بفرست.")
        return
    data = await state.get_data()
    code = str(data.get("coach_receipt_code") or "")
    uid = message.from_user.id
    async with async_session() as session:
        rec = await FSHOP.attach_receipt(session, code, file_id)
        await session.commit()
    await state.clear()
    if rec is None:
        await message.reply("❌ کد پیگیری پیدا نشد.")
        return
    try:
        from app.config import MAIN_ADMIN_ID
        if MAIN_ADMIN_ID:
            await message.bot.send_message(
                int(MAIN_ADMIN_ID),
                f"🧾 رسید خرید سرمربی رسید: <b>{rec.coach_name}</b> — کد <code>{code}</code> (کاربر <code>{uid}</code>).\nاز «خریدهای ورزشی» تأیید کن."
            )
    except Exception:
        pass
    await message.reply(f"✅ رسید برای کد <code>{code}</code> ثبت شد — ادمین بررسی و سرمربی فعال می‌شود.")

# --------------------------- 🏆 v1.7.9.6 — جدول لیگ (آمار واقعی) ---------------------------
@router.callback_query(F.data.startswith("fb:league"))
async def league_cb(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    base, _ = split_owner(callback.data)
    parts = base.split(":")
    page = int(parts[2]) if len(parts) >= 3 and parts[2].isdigit() else 0
    uid = callback.from_user.id
    from app.services import football_league as FLG
    async with async_session() as session:
        table = await FLG.league_table(session, limit=200)
    per = 10
    total = max(1, (len(table) + per - 1) // per)
    page = max(0, min(page, total - 1))
    chunk = table[page * per:(page + 1) * per]
    lines = ["🏆 <b>جدول لیگ</b> (امتیاز ← تفاضل ← گل‌زده)", ""]
    if not chunk:
        lines.append("هنوز مسابقه‌ای ثبت نشده — با «🤝 بازی دوستانه» شروع کن.")
    else:
        # 🆕 v1.7.9.7/8 — جدول ستونی monospace با امکان برگشت به حالت اول
        from app.utils.table import render_table, table_mode_on
        if await table_mode_on("football_league"):
            headers = ["#", "باشگاه", "بازی", "ب-م-ب", "گل", "امتیاز"]
            rows = []
            for i, r in enumerate(chunk, start=page * per + 1):
                gd = FLG.goal_diff(r)
                rows.append([
                    str(i), r.club_name, str(int(r.played)),
                    f"{int(r.wins)}-{int(r.draws)}-{int(r.losses)}",
                    f"{int(r.goals_for)}:{int(r.goals_against)}",
                    str(int(r.points)),
                ])
            lines.append(render_table(headers, rows))
        else:
            medals = {1: "🥇", 2: "🥈", 3: "🥉"}
            for i, r in enumerate(chunk, start=page * per + 1):
                m = medals.get(i, f"{i}.")
                gd = FLG.goal_diff(r)
                lines.append(
                    f"{m} <b>{r.club_name}</b> — {int(r.points)} امتیاز | "
                    f"بازی {int(r.played)} | برد {int(r.wins)} مساوی {int(r.draws)} باخت {int(r.losses)} | "
                    f"گل {int(r.goals_for)}:{int(r.goals_against)} (تفاضل {gd:+d})"
                )
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    kb = InlineKeyboardBuilder()
    if page > 0:
        kb.button(text="◀️ قبلی", callback_data=with_owner(f"fb:league:{page-1}", uid))
    if page < total - 1:
        kb.button(text="بعدی ▶️", callback_data=with_owner(f"fb:league:{page+1}", uid))
    kb.button(text="⚽ بازگشت به باشگاه", callback_data=with_owner("fb:hub", uid))
    kb.adjust(1)
    await safe_show(callback.message, "\n".join(lines), kb.as_markup())
    await safe_answer(callback)

# --------------------------- 🛒 بازار نقل‌وانتقال (v1.7.9.7 — F3) ---------------------------
from app.data import football_players as FP
from app.services import football_market as FMKT

_TIER_FA2 = {"common": "عادی", "rare": "نایاب", "epic": "حماسی", "legend": "افسانه‌ای", "mythic": "اساطیر"}
_POS_FA2 = FP.POSITION_FA


@router.callback_query(F.data.startswith("fb:market"))
async def market_cb(callback: CallbackQuery, state: FSMContext) -> None:
    if not await ensure_owner(callback):
        return
    base, _ = split_owner(callback.data)
    parts = base.split(":")[1:]   # 🐞 v1.8.1.6 — حذف پیشوند «fb»؛ قبلاً parts[1] همیشه نامِ بخش بود و همهٔ زیرمنوها می‌مردند
    sub = parts[1] if len(parts) > 1 else ""
    uid = callback.from_user.id
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    async with async_session() as session:
        club = await FS.get_club(session, uid)
        if club is None:
            await safe_answer(callback, "اول باشگاه بساز.", show_alert=True)
            return
        player = await get_player(session, uid)

        # --- بازیکنان من ---
        if sub == "mine":
            cards = await FMKT.purchase_history(session, uid)
            lines = ["🧾 <b>بازیکنان من</b>", ""]
            if not cards:
                lines.append("هنوز بازیکنی نداری.")
            for c in cards[:15]:
                lines.append(f"• <b>{c.name}</b> ({c.pos} — {_TIER_FA2.get(c.tier, c.tier)}) 💪{c.base_power:,} — <code>{c.tracking_code}</code>")
            kb = InlineKeyboardBuilder()
            kb.button(text="🛒 بازار", callback_data=with_owner("fb:market", uid))
            kb.button(text="⚽ باشگاه", callback_data=with_owner("fb:hub", uid))
            kb.adjust(1)
            await safe_show(callback.message, "\n".join(lines), kb.as_markup())
            await safe_answer(callback)
            return

        # --- انتخاب نقش داخل هر رنک ---
        if sub == "tier" and len(parts) >= 3:
            tier = parts[2]
            if tier not in FP.TIER_ORDER:
                await safe_answer(callback, "رنک نامعتبر است.", show_alert=True)
                return
            rows = FP.by_tier(tier)
            lines = [
                f"🧭 <b>{_TIER_FA2[tier]} — انتخاب نقش</b>",
                "",
                f"این رنک {len(rows)} بازیکن دارد. نقش موردنظر را انتخاب کن:",
            ]
            kb = InlineKeyboardBuilder()
            for pos in FP.POSITION_ORDER:
                count = len(FP.by_tier_and_pos(tier, pos))
                kb.button(
                    text=f"{FP.POSITION_EMOJI[pos]} {_POS_FA2[pos]} ({count})",
                    callback_data=with_owner(f"fb:market:role:{tier}:{pos}:0", uid),
                )
            kb.button(
                text=f"📋 همهٔ نقش‌ها ({len(rows)})",
                callback_data=with_owner(f"fb:market:role:{tier}:ALL:0", uid),
            )
            kb.button(text="◀️ رنک‌ها", callback_data=with_owner("fb:market", uid))
            kb.button(text="⚽ باشگاه", callback_data=with_owner("fb:hub", uid))
            kb.adjust(2, 2, 1, 1, 1)
            await safe_show(callback.message, "\n".join(lines), kb.as_markup())
            await safe_answer(callback)
            return

        # --- مرور بازیکنانِ یک رنک و نقش ---
        if sub == "role" and len(parts) >= 5:
            tier, pos = parts[2], parts[3]
            page = int(parts[4]) if parts[4].isdigit() else 0
            if tier not in FP.TIER_ORDER or (pos != "ALL" and pos not in FP.POSITION_ORDER):
                await safe_answer(callback, "فیلتر بازار نامعتبر است.", show_alert=True)
                return
            rows = FP.by_tier_and_pos(tier, pos)
            keys = [p["key"] for p in rows]
            per = 6
            total = max(1, (len(keys) + per - 1) // per)
            page = max(0, min(page, total - 1))
            chunk = keys[page * per:(page + 1) * per]
            role_title = "همهٔ نقش‌ها" if pos == "ALL" else _POS_FA2[pos]
            lines = [
                f"🛒 <b>{_TIER_FA2[tier]} — {role_title}</b> (صفحه {page+1}/{total})",
                "",
            ]
            kb = InlineKeyboardBuilder()
            for key in chunk:
                player_row = FP.get(key)
                price = await FMKT.effective_price(session, key)
                sold = await FMKT.is_sold(session, key)
                active = await FMKT.has_active_sale(session, key)
                price_text = f"{price:,}$" if player_row["currency"] == "game" else f"از {price:,} تومان"
                status = " ❌ فروخته شد" if sold else (" 🔨 مزایده فعال" if active else "")
                lines.append(
                    f"• <b>{player_row['name']}</b> | {player_row['pos']} | OVR {player_row['overall']} "
                    f"| 💪{player_row['power']:,} | {price_text}{status}"
                )
                if sold:
                    kb.button(
                        text=f"📨 درخواست {player_row['name']}",
                        callback_data=with_owner(f"fb:market:req:{key}", uid),
                    )
                elif player_row["sale_mode"] == "direct":
                    kb.button(
                        text=f"🛒 خرید {player_row['name']}",
                        callback_data=with_owner(f"fb:market:buy:{key}", uid),
                    )
                elif active:
                    kb.button(
                        text=f"🔨 پیشنهاد بالاتر: {player_row['name']}",
                        callback_data=with_owner(f"fb:market:bid:{active.id}", uid),
                    )
                else:
                    kb.button(
                        text=f"🔨 مزایده: {player_row['name']}",
                        callback_data=with_owner(f"fb:market:view:{key}", uid),
                    )
            if page > 0:
                kb.button(
                    text="◀️ قبلی",
                    callback_data=with_owner(f"fb:market:role:{tier}:{pos}:{page-1}", uid),
                )
            if page < total - 1:
                kb.button(
                    text="بعدی ▶️",
                    callback_data=with_owner(f"fb:market:role:{tier}:{pos}:{page+1}", uid),
                )
            kb.button(text="◀️ نقش‌ها", callback_data=with_owner(f"fb:market:tier:{tier}:0", uid))
            kb.button(text="◀️ رنک‌ها", callback_data=with_owner("fb:market", uid))
            kb.adjust(1)
            await safe_show(callback.message, "\n".join(lines), kb.as_markup())
            await safe_answer(callback)
            return

        # --- خرید عادی (پول بازی) ---
        if sub == "buy" and len(parts) >= 3:
            ok, msg = await FMKT.buy_common(session, uid, club, parts[2], player)
            await session.commit()
            await safe_answer(callback, msg, show_alert=True)
            return

        # --- مشخصات بازیکن تک + شروع مزایده ---
        if sub == "view" and len(parts) >= 3:
            p = FP.get(parts[2])
            if p is None:
                await safe_answer(callback, "بازیکن نامعتبر.", show_alert=True)
                return
            price = await FMKT.effective_price(session, p["key"])
            if p.get("sale_mode") != "auction":
                await safe_answer(callback, "این بازیکن خرید مستقیم دارد.", show_alert=True)
                return
            text = (
                f"⭐ <b>{p['name']}</b> ({_POS_FA2[p['pos']]} — {_TIER_FA2.get(p['tier'], p['tier'])})\n"
                f"📊 OVR: <b>{p['overall']}</b> | 💪 پاور: {p['power']:,}\n"
                f"📈 اوج ارزش: €{p['peak_value_eur_m']:g}M در {p['peak_year']} → "
                f"€{p['adjusted_value_eur_m']:g}M با تورم فوتبال\n"
                f"💰 قیمت پایه مزایده: {price:,} تومان\n"
                f"🔒 تک‌نسخه‌ای — تمام بازیکنان تومانی فقط از مزایده منتقل می‌شوند.\n\n"
                f"🔨 زمان مزایده: {FMKT.AUCTION_HOURS} ساعت؛ بالاترین پیشنهاد پس از تأیید ادمین برنده است."
            )
            kb = InlineKeyboardBuilder()
            kb.button(text="🔨 شروع مزایده (پیشنهاد اول)", callback_data=with_owner(f"fb:market:bidstart:{p['key']}", uid))
            kb.button(text="◀️ بازار", callback_data=with_owner("fb:market", uid))
            kb.adjust(1)
            await safe_show(callback.message, text, kb.as_markup())
            await safe_answer(callback)
            return

        # --- شروع مزایده (FSM پیشنهاد اول) ---
        if sub == "bidstart" and len(parts) >= 3:
            await state.set_state(FootballStates.market_bid)
            await state.update_data(market_action="start", market_key=parts[2])
            p = FP.get(parts[2])
            price = await FMKT.effective_price(session, parts[2])
            await safe_show(
                callback.message,
                f"🔨 پیشنهاد اول برای <b>{p['name']}</b> را بفرست (حداقل {price:,} تومان):\n{CANCEL_HINT}",
                football_back_menu(uid),
            )
            await safe_answer(callback)
            return

        # --- پیشنهاد بالاتر روی مزایده فعال (FSM) ---
        if sub == "bid" and len(parts) >= 3:
            sale = await session.get(FMKT.FootballMarketSale, int(parts[2]))
            if sale is None or sale.status != "auction":
                await safe_answer(callback, "مزایده فعال نیست.", show_alert=True)
                return
            await state.set_state(FootballStates.market_bid)
            await state.update_data(market_action="bid", market_sale_id=sale.id)
            await safe_show(
                callback.message,
                f"🔨 پیشنهاد بالاتر برای <b>{sale.player_name}</b> (فعلی: {int(sale.highest_bid):,} تومان) را بفرست:\n{CANCEL_HINT}",
                football_back_menu(uid),
            )
            await safe_answer(callback)
            return

        # --- درخواست انتقال از دارنده (بازیکن فروخته‌شده) ---
        if sub == "req" and len(parts) >= 3:
            key = parts[2]
            owner = await FMKT.owner_of(session, key)
            p = FP.get(key)
            if owner is None or p is None:
                await safe_answer(callback, "این بازیکن فروخته نشده.", show_alert=True)
                return
            try:
                from app.config import MAIN_ADMIN_ID
                if MAIN_ADMIN_ID:
                    await callback.bot.send_message(
                        int(MAIN_ADMIN_ID),
                        f"🔁 درخواست انتقال بازیکنِ تک: <b>{p['name']}</b> از کاربر <code>{owner}</code> به <code>{uid}</code>.\n"
                        "از «ادمین‌مود ← ابزارها ← خریدهای ورزشی» با انتقال/تأیید مدیریت کن."
                    )
            except Exception:
                pass
            await safe_answer(callback, f"✅ درخواست انتقال «{p['name']}» به دارنده‌اش (با تأیید ادم��ن) ثبت شد.", show_alert=True)
            return

        # --- انتخاب رده (پیش‌فرض) ---
        lines = [
            "🛒 <b>بازار نقل‌وانتقال</b>", "",
            "💵 عادی = پول بازی، غیرتک و خرید مستقیم",
            "🔨 تمام بازیکنان تومانی = تک‌نسخه‌ای و فقط مزایده",
            "🧭 مسیر منو: رنک ← نقش (دروازه‌بان/مدافع/هافبک/مهاجم) ← بازیکن",
            "📈 رنک و OVR از اوج ارزش بازار و تورم فوتبال محاسبه شده‌اند.",
            "🔒 فروخته‌شده‌ها فقط با درخواست به دارنده و تأیید ادمین جابه‌جا می‌شوند.",
            "",
            "رنک را انتخاب کن:",
        ]
        kb = InlineKeyboardBuilder()
        for tier in ("common", "rare", "epic", "legend", "mythic"):
            cnt = sum(1 for p in FP.PLAYERS.values() if p["tier"] == tier)
            kb.button(text=f"{_TIER_FA2[tier]} ({cnt})", callback_data=with_owner(f"fb:market:tier:{tier}:0", uid))
        kb.button(text="🧾 بازیکنان من", callback_data=with_owner("fb:market:mine", uid))
        kb.button(text="⚽ بازگشت به باشگاه", callback_data=with_owner("fb:hub", uid))
        kb.adjust(2, 2, 1, 1, 1)
        await safe_show(callback.message, "\n".join(lines), kb.as_markup())
        await safe_answer(callback)


@router.message(FootballStates.market_bid)
async def market_bid_recv(message: Message, state: FSMContext) -> None:
    if await handle_cancel_word(message, state):
        return
    raw = (message.text or "").strip().replace(",", "").replace("$", "")
    if not raw.isdigit() or int(raw) <= 0:
        await message.reply("فقط عددِ مثبت بفرست (مبلغ به تومان).")
        return
    amount = int(raw)
    data = await state.get_data()
    uid = message.from_user.id
    async with async_session() as session:
        if data.get("market_action") == "start":
            ok, code, sale = await FMKT.start_auction(session, uid, str(data.get("market_key") or ""), amount)
            if ok and sale is not None:
                await session.commit()
                # اطلاعیه به همه‌ی کاربران
                try:
                    from app.models.profile import Player
                    ids = [r[0] for r in (await session.execute(__import__("sqlalchemy").select(Player.tg_user_id))).all()]
                    for u in ids[:500]:
                        try:
                            await message.bot.send_message(int(u), f"🔨 مزایده‌ی بازیکنِ تک: <b>{sale.player_name}</b> شروع شد! پیشنهاد فعلی {amount:,} تومان. {FMKT.AUCTION_HOURS} ساعت فرصت — از «⚽ ورزش ← بازار نقل‌وانتقال» پیشنهاد بالاتر بده.")
                        except Exception:
                            continue
                except Exception:
                    pass
                await message.reply(f"✅ مزایده‌ی <b>{sale.player_name}</b> با پیشنهاد {amount:,} تومان شروع شد. {FMKT.AUCTION_HOURS} ساعت تا پایان.")
            else:
                await message.reply(code)
        else:
            sale = await session.get(FMKT.FootballMarketSale, int(data.get("market_sale_id") or 0))
            if sale is None:
                await message.reply("مزایده پیدا نشد.")
                await state.clear()
                return
            ok, msg = await FMKT.place_bid(session, uid, sale, amount)
            await session.commit()
            await message.reply(msg)
    await state.clear()

# --------------------------- 🏆 لیگ جمعهٔ رسمی (v1.7.9.9 — F4) ---------------------------
from app.services import football_friday as FFRI


@router.callback_query(F.data.startswith("fb:friday"))
async def friday_cb(callback: CallbackQuery, state: FSMContext) -> None:
    if not await ensure_owner(callback):
        return
    base, _ = split_owner(callback.data)
    parts = base.split(":")[1:]   # 🐞 v1.8.1.6 — حذف پیشوند «fb»؛ قبلاً parts[1] همیشه نامِ بخش بود و همهٔ زیرمنوها می‌مردند
    sub = parts[1] if len(parts) > 1 else ""
    uid = callback.from_user.id
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    async with async_session() as session:
        club = await FS.get_club(session, uid)
        if club is None:
            await safe_answer(callback, "اول باشگاه بساز.", show_alert=True)
            return
        season = await FFRI.current_season(session, create=True)

        if sub == "reg":
            ok, msg = await FFRI.register(session, club)
            await session.commit()
            await safe_answer(callback, msg, show_alert=True)
            return

        if sub == "table":
            table = await FFRI.standings(session, season.id)
            from app.utils.table import render_table, table_mode_on
            lines = [f"🏆 <b>لیگ جمعه — هفتهٔ {season.week_key}</b> ({len(table)} تیم)", ""]
            qualified = set(__import__("app.data.football_competitions", fromlist=["ucl_qualified_ranks"]).ucl_qualified_ranks(len(table))) if season.status == "done" else set()
            if not table:
                lines.append("هنوز تیمی ثبت‌نام نکرده.")
            elif await table_mode_on("football_league"):
                rows = [
                    [str(i), e.club_name, str(int(e.played)), f"{int(e.wins)}-{int(e.draws)}-{int(e.losses)}",
                     f"{int(e.goals_for)}:{int(e.goals_against)}", str(int(e.points)), "🌟" if i in qualified else "—"]
                    for i, e in enumerate(table[:20], 1)
                ]
                lines.append(render_table(["#", "باشگاه", "بازی", "ب-م-ب", "گل", "امتیاز", "UCL"], rows))
            else:
                medals = {1: "🥇", 2: "🥈", 3: "🥉"}
                for i, e in enumerate(table[:20], 1):
                    m = medals.get(i, f"{i}.")
                    ucl_mark = " 🌟 سهمیه UCL" if i in qualified else ""
                    lines.append(f"{m} {e.club_name} — {int(e.points)} امتیاز (برد {int(e.wins)} / مساوی {int(e.draws)} / باخت {int(e.losses)}){ucl_mark}")
            kb = InlineKeyboardBuilder()
            kb.button(text="🗓️ لیگ جمعه", callback_data=with_owner("fb:friday", uid))
            kb.button(text="⚽ بازگشت", callback_data=with_owner("fb:hub", uid))
            kb.adjust(1)
            await safe_show(callback.message, "\n".join(lines), kb.as_markup())
            await safe_answer(callback)
            return

        # hub
        entry = await FFRI.my_season_status(session, club.id)
        cnt = int(season.team_count or 0)
        st_fa = {"registration": "📝 ثبت‌نام باز است (تا پنجشنبه)", "fixtures": "⏳ فیکسچر آماده — جمعه بازی می‌شود", "done": "✅ لیگ این هفته برگزار شد"}.get(season.status, season.status)
        lines = [f"🏆 <b>لیگ جمعه — هفتهٔ {season.week_key}</b>", "", f"وضعیت: {st_fa}", f"تیم‌های ثبت‌نامی: {cnt}", ""]
        if entry:
            lines.append(f"✅ تو ثبت‌نام کرده‌ای — امتیاز فعلی: {int(entry.points)} (برد {int(entry.wins)})")
            if season.status == "done":
                final_table = await FFRI.standings(session, season.id)
                my_rank = next((i for i, row in enumerate(final_table, 1) if int(row.club_id) == int(club.id)), None)
                from app.data import football_competitions as FCOMP
                if FCOMP.is_ucl_rank_eligible(my_rank, len(final_table)):
                    lines.append(f"🌟 رتبهٔ نهایی {my_rank} — سهمیهٔ خودکار UCL را گرفتی.")
                else:
                    lines.append(f"📊 رتبهٔ نهایی: {my_rank or '—'} — این هفته سهمیهٔ UCL نگرفتی.")
        else:
            lines.append("هنوز ثبت‌نام نکرده‌ای.")
        lines += [
            "",
            "📅 ثبت‌نام تا پنجشنبه؛ بازی‌ها جمعه (دوری رفت‌وبرگشت).",
            "🌟 فقط رتبه‌های ۱ تا ۸ جدول نهایی، سهمیهٔ خودکار UCL دوشنبه را می‌گیرند.",
            "🎁 جایزهٔ قهرمان: دلار بازی + XP سرمربی + طرفدار",
        ]
        kb = InlineKeyboardBuilder()
        if season.status == "registration" and not entry:
            kb.button(text="📝 ثبت‌نام در لیگ", callback_data=with_owner("fb:friday:reg", uid))
        kb.button(text="🏆 جدول لیگ", callback_data=with_owner("fb:friday:table", uid))
        kb.button(text="⚽ بازگشت به باشگاه", callback_data=with_owner("fb:hub", uid))
        kb.adjust(1)
        await safe_show(callback.message, "\n".join(lines), kb.as_markup())
        await safe_answer(callback)

# --------------------------- 🎮 بازی در حال انجام (v1.7.10.0) ---------------------------
@router.callback_query(_fb_exact("fb:live"))
async def live_cb(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    uid = callback.from_user.id
    from app.services import football_live as FLIVE
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    async with async_session() as session:
        mine = await FLIVE.my_live_match(session, uid)
        all_live = await FLIVE.live_matches(session)
    lines = ["🎮 <b>بازی‌های در حال انجام</b>", ""]
    kb = InlineKeyboardBuilder()
    if not all_live:
        lines.append("الان بازی زنده‌ای نیست. با «🤝 بازی دوستانه» شروع کن.")
    for m in all_live[:8]:
        tag = " 👈 تو" if (mine and m.id == mine.id) else ""
        lines.append(f"• <b>{m.home_name}</b> {m.home_goals}-{m.away_goals} <b>{m.away_name}</b>{tag}")
        kb.button(text=f"📺 {m.home_name} vs {m.away_name}", callback_data=with_owner(f"fb:live:view:{m.id}", uid))
    kb.button(text="🤝 بازی دوستانهٔ جدید", callback_data=with_owner("fb:play", uid))
    kb.button(text="⚽ بازگشت", callback_data=with_owner("fb:hub", uid))
    kb.adjust(1)
    await safe_show(callback.message, "\n".join(lines), kb.as_markup())
    await safe_answer(callback)


@router.callback_query(F.data.startswith("fb:live:view:"))
async def live_view_cb(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    base, _ = split_owner(callback.data)
    mid = int(base.split(":")[3])
    uid = callback.from_user.id
    from app.services import football_live as FLIVE
    from app.models.football_live import FootballLiveMatch
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    async with async_session() as session:
        m = await session.get(FootballLiveMatch, mid)
        if m is None:
            await safe_answer(callback, "بازی پیدا نشد.", show_alert=True)
            return
        text = FLIVE.build_report(m)
        status = m.status
    kb = InlineKeyboardBuilder()
    if status == "live":
        kb.button(text="🔄 بروزرسانی زنده", callback_data=with_owner(f"fb:live:view:{mid}", uid))
    kb.button(text="🎮 همهٔ بازی‌های زنده", callback_data=with_owner("fb:live", uid))
    kb.button(text="⚽ بازگشت", callback_data=with_owner("fb:hub", uid))
    kb.adjust(1)
    await safe_show(callback.message, text, kb.as_markup())
    await safe_answer(callback)

# --------------------------- 🌟 لیگ قهرمانان (UCL) دوشنبه — v1.7.10.0 ---------------------------
from app.services import football_ucl as FUCL


@router.callback_query(F.data.startswith("fb:ucl"))
async def ucl_cb(callback: CallbackQuery, state: FSMContext) -> None:
    if not await ensure_owner(callback):
        return
    base, _ = split_owner(callback.data)
    parts = base.split(":")[1:]
    sub = parts[1] if len(parts) > 1 else ""
    uid = callback.from_user.id
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    async with async_session() as session:
        club = await FS.get_club(session, uid)
        if club is None:
            await safe_answer(callback, "اول باشگاه بساز.", show_alert=True)
            return
        season = await FUCL.current_season(session, create=True)
        # current_season may create and auto-seed the earned top-eight places.
        await session.commit()
        qualification = await FUCL.qualification_status(session, club.id, season=season)

        # Old buttons/callbacks remain safe, but no public registration is offered.
        if sub == "reg":
            ok, msg = await FUCL.register(session, club)
            await session.commit()
            await safe_answer(callback, msg, show_alert=True)
            return

        if sub == "groups":
            if season is None:
                await safe_answer(callback, "هنوز UCL فعالی از لیگ جمعه ساخته نشده است.", show_alert=True)
                return
            ent = await FUCL.entries(session, season.id)
            groups = sorted({entry.group_no for entry in ent if entry.group_no})
            from app.utils.table import render_table, table_mode_on
            lines = ["🌟 <b>لیگ قهرمانان — گروه‌ها</b>", ""]
            if season.status == "cancelled":
                lines.append("این دوره به‌علت نرسیدن لیگ جمعه به حداقل ۸ تیم تشکیل نشد.")
            elif not groups or season.status == "registration":
                lines.append("۸ تیم برتر مشخص شده‌اند؛ گروه‌بندی دوشنبه انجام می‌شود.")
            for group_no in groups:
                table = await FUCL.group_table(session, season.id, group_no)
                lines.append(f"🔹 گروه {group_no}:")
                if await table_mode_on("football_league"):
                    rows = [[str(i + 1), entry.club_name, str(int(entry.points)), f"{int(entry.goals_for)}:{int(entry.goals_against)}"] for i, entry in enumerate(table)]
                    lines.append(render_table(["#", "باشگاه", "امتیاز", "گل"], rows))
                else:
                    for i, entry in enumerate(table, 1):
                        lines.append(f"  {i}. {entry.club_name} — {int(entry.points)} امتیاز")
                lines.append("")
            kb = InlineKeyboardBuilder()
            kb.button(text="🌟 لیگ قهرمانان", callback_data=with_owner("fb:ucl", uid))
            kb.button(text="⚽ بازگشت", callback_data=with_owner("fb:hub", uid))
            kb.adjust(1)
            await safe_show(callback.message, "\n".join(lines), kb.as_markup())
            await safe_answer(callback)
            return

        # Hub: the Friday League result is the sole gate.
        if season is None:
            lines = [
                "🌟 <b>لیگ قهرمانان</b>", "",
                "⏳ هنوز لیگ جمعهٔ تکمیل‌شده‌ای برای تعیین سهمیه وجود ندارد.",
                "فقط ۸ تیم اول جدول نهایی لیگ جمعه، خودکار به UCL بعدی می‌رسند.",
            ]
            entry = None
            status_text = "در انتظار لیگ جمعه"
            count = 0
        else:
            entry = await FUCL.my_status(session, club.id)
            count = int(season.team_count or 0)
            status_text = {
                "registration": "🎟️ سهمیه‌ها قطعی؛ در انتظار دوشنبه",
                "groups": "⚽ مرحلهٔ گروهی",
                "knockout": "⚔️ مرحلهٔ حذفی",
                "done": "✅ این دوره تمام شد",
                "cancelled": "🚫 این دوره تشکیل نشد",
            }.get(season.status, season.status)
            lines = [
                f"🌟 <b>لیگ قهرمانان — {season.period_key}</b>", "",
                f"وضعیت: {status_text}",
                f"تیم‌های واجد سهمیه: {count}/{FUCL.MAX_TEAMS}",
                f"مبنای سهمیه: لیگ جمعهٔ {qualification.get('source_week') or '—'}",
                "",
            ]
            rank = qualification.get("rank")
            if qualification.get("eligible"):
                lines.append(f"✅ رتبهٔ {rank} لیگ جمعه — سهمیهٔ خودکار UCL را داری.")
            else:
                lines.append(f"❌ {qualification.get('reason')}")
            if entry:
                group_text = f"گروه {entry.group_no}" if entry.group_no else "در انتظار قرعه‌کشی"
                lines.append(f"🎫 ورود ثبت‌شده: {group_text} | امتیاز UCL: {int(entry.points)}")

        lines += [
            "",
            "🔒 ثبت‌نام عمومی حذف شده؛ فقط رتبه‌های ۱ تا ۸ لیگ جمعه وارد می‌شوند.",
            "📅 بازی‌ها دوشنبه زنده و ۱۰ دقیقه‌ای هستند.",
            "🎁 قهرمان: دلار بازی + طرفدار + XP سرمربی",
            "📺 بازی‌ها را از «🎮 بازی در حال انجام» ببین.",
        ]
        kb = InlineKeyboardBuilder()
        if season is not None:
            kb.button(text="🌟 گروه‌ها", callback_data=with_owner("fb:ucl:groups", uid))
        kb.button(text="🏆 لیگ جمعه", callback_data=with_owner("fb:friday", uid))
        kb.button(text="🎮 بازی‌های زنده", callback_data=with_owner("fb:live", uid))
        kb.button(text="⚽ بازگشت", callback_data=with_owner("fb:hub", uid))
        kb.adjust(1)
        await safe_show(callback.message, "\n".join(lines), kb.as_markup())
        await safe_answer(callback)

# --------------------------- 👤 ترکیب و تاکتیک (v1.8.1.0 — F6) ---------------------------
from app.services import football_tactics as FTAC


@router.callback_query(F.data.startswith("fb:tactics"))
async def tactics_cb(callback: CallbackQuery, state: FSMContext) -> None:
    if not await ensure_owner(callback):
        return
    base, _ = split_owner(callback.data)
    parts = base.split(":")[1:]   # 🐞 v1.8.1.6 — حذف پیشوند «fb»؛ قبلاً parts[1] همیشه نامِ بخش بود و همهٔ زیرمنوها می‌مردند
    sub = parts[1] if len(parts) > 1 else ""
    uid = callback.from_user.id
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    async with async_session() as session:
        club = await FS.get_club(session, uid)
        if club is None:
            await safe_answer(callback, "اول باشگاه بساز.", show_alert=True)
            return
        if sub == "set":
            key = parts[2] if len(parts) > 2 else "balanced"
            await FTAC.set_tactic(session, club.id, key)
            await session.commit()
            await safe_answer(callback, f"✅ تاکتیک: {FTAC.tactic_name(key)}")
        elif sub == "auto":
            cur = await FTAC.get(session, club.id)
            await FTAC.set_auto(session, club.id, not cur.auto_enabled)
            await session.commit()
            await safe_answer(callback, "🤖 اتو‌تاکتیک: " + ("روشن" if not cur.auto_enabled else "خاموش"))
        row = await FTAC.get(session, club.id)
        tactic = row.tactic
        auto = bool(row.auto_enabled)
        cards = await FS.squad(session, club.id)
        power = FS.team_power(session, club, cards)

    t = FTAC.TACTICS.get(tactic, FTAC.TACTICS["balanced"])
    lines = [
        "👤 <b>ترکیب و تاکتیک</b>",
        "",
        f"⭐ قدرت تیم: <b>{power:,}</b>",
        f"🎯 تاکتیک فعلی: <b>{FTAC.tactic_name(tactic)}</b> (گل‌زنی ×{t['xg_self']} | گل‌خوردگی ×{t['xg_opp']})",
        f"🤖 اتو‌تاکتیک: <b>{'روشن' if auto else 'خاموش'}</b> — اگر روشن باشد، خودکار بر اساس قدرت حریف انتخاب می‌شود",
        "",
        "اثر تاکتیک‌ها روی بازی‌های زنده:",
        "⚔️ تهاجمی: گل بیشتر می‌زنی ولی بیشتر هم می‌خوری",
        "⚖️ متعادل: خنثی",
        "🛡️ دفاعی: کمتر می‌زنی ولی کمتر هم می‌خوری",
    ]
    kb = InlineKeyboardBuilder()
    for key, info in FTAC.TACTICS.items():
        mark = "✅ " if key == tactic else ""
        kb.button(text=f"{mark}{info['name']}", callback_data=with_owner(f"fb:tactics:set:{key}", uid))
    kb.button(text=("🤖 اتو‌تاکتیک: خاموش" if not auto else "🤖 اتو‌تاکتیک: روشن"), callback_data=with_owner("fb:tactics:auto", uid))
    kb.button(text="⚽ بازگشت", callback_data=with_owner("fb:hub", uid))
    kb.adjust(1)
    await safe_show(callback.message, "\n".join(lines), kb.as_markup())
    await safe_answer(callback)

# --------------------------- 🗂️ زیرمنوهای خوشه‌ای فوتبال (v1.8.1.5) ---------------------------
@router.callback_query(F.data.startswith("fb:sec:team"))
async def sec_team_cb(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    await safe_show(callback.message, "👥 <b>تیم و تاکتیک</b> — اسکادر، ترکیب، سرمربی و تمرین:", football_sec_team_menu(callback.from_user.id))
    await safe_answer(callback)


@router.callback_query(F.data.startswith("fb:sec:club"))
async def sec_club_cb(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    await safe_show(callback.message, "🏟️ <b>باشگاه و هوادار</b> — استادیوم و سوشال مدیا:", football_sec_club_menu(callback.from_user.id))
    await safe_answer(callback)


@router.callback_query(F.data.startswith("fb:sec:shop"))
async def sec_shop_cb(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    await safe_show(callback.message, "🛒 <b>بازار و فروشگاه</b> — نقل‌وانتقال و سرمربی ۵⭐:", football_sec_shop_menu(callback.from_user.id))
    await safe_answer(callback)


@router.callback_query(F.data.startswith("fb:sec:comp"))
async def sec_comp_cb(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    await safe_show(callback.message, "🏆 <b>رقابت‌ها</b> — لیگ، لیگ جمعه و لیگ قهرمانان:", football_sec_comp_menu(callback.from_user.id))
    await safe_answer(callback)
