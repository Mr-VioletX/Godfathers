# -*- coding: utf-8 -*-
"""هندلرِ سیستمِ ورزشی (مرحله ۱۴).

ورودی‌ها:
  • دکمه‌ی کیبوردیِ «⚽ ورزش» و کلمه‌ی «ورزش»
  • دکمه‌ی شیشه‌ای menu:sports
  • دکمه‌های sport:...
  • FSM برای نام‌گذاری/برندسازی

مدیریتِ ورزش فقط داخلِ خودِ ربات (چتِ خصوصی) ممکن است.
"""
import random

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.data import sports as S
from app.database.engine import async_session
from app.keyboards.sports_menu import (
    after_match_menu,
    back_menu,
    brand_manage_menu,
    branding_menu,
    create_menu,
    events_menu,
    sports_hub,
    team_manage_menu,
)
from app.services import sports_service as svc
from app.states import SportsStates
from app.utils.ui import CANCEL_HINT, ensure_owner, handle_cancel_word, safe_show, split_owner, safe_answer

router = Router()

BTN_SPORTS = "⚽ ورزش"
WORD_SPORTS = "ورزش"
ONLY_BOT = "⚽ مدیریتِ امپراتوریِ ورزشی فقط داخلِ خودِ ربات ممکن است، نه در گروه."

# لیبلِ فارسیِ فیلدهای برندسازی
_FIELD_PROMPT = {
    "name": "نامِ جدید را بفرست",
    "color": "رنگِ دلخواه را بفرست (مثلاً: قرمز-مشکی)",
    "slogan": "شعارِ تیم را بفرست",
    "stadium": "نامِ استادیوم را بفرست",
    "raceteam": "نامِ تیمِ مسابقه را بفرست",
    "track": "نامِ پیست را بفرست",
}


def _fmt(n: int) -> str:
    return f"{int(n):,}"


def _fmt_hm(seconds: int) -> str:
    """🆕 پچ — نمایشِ زمانِ باقی‌مانده تا ریستِ سهمیه‌ی روزانه، به ساعت/دقیقه."""
    m = max(0, int(seconds)) // 60
    h, mm = divmod(m, 60)
    if h and mm:
        return f"{h} ساعت و {mm} دقیقه"
    if h:
        return f"{h} ساعت"
    return f"{mm} دقیقه"


# ---------------------------------------------------------------------------
# رندرِ متن‌ها
# ---------------------------------------------------------------------------
async def _hub_text(session, uid: int) -> str:
    teams = await svc.list_teams(session, uid)
    brands = await svc.list_brands(session, uid)
    ev = svc.current_event()
    lines = ["⚽ <b>امپراتوریِ ورزشی</b>", ""]
    lines.append(f"📅 اونتِ امروز: <b>{ev['name']}</b>")
    if ev.get("key") != "normal":
        lines.append(f"⏰ فعال‌سازی: {ev.get('window', '—')} — {ev.get('effect', '')}")
    lines.append("")
    if teams or brands:
        lines.append("📋 <b>دارایی‌های ورزشیِ تو:</b>")
        for t in teams:
            lines.append(f"  {S.SPORT_EMOJI[t.sport]} {t.name} — {t.points} امتیاز")
        for br in brands:
            lines.append(f"  {S.SPORT_EMOJI[br.sport]} {br.name} — {br.points} امتیاز")
    else:
        lines.append("هنوز هیچ تیم یا برندی نساخته‌ای. یکی از ورزش‌ها را انتخاب کن.")
    return "\n".join(lines)


async def _team_text(session, uid: int, team) -> str:
    power = await svc.compute_team_power(session, team)
    sat, pop = await svc.team_fan_context(session, uid)
    played = team.wins + team.draws + team.losses
    lines = [
        f"{S.SPORT_EMOJI[team.sport]} <b>{team.name}</b>  ({S.SPORT_LABEL[team.sport]})",
    ]
    if team.slogan:
        lines.append(f"<i>«{team.slogan}»</i>")
    lines += [
        "",
        f"⚡ قدرتِ تیم (TP): <b>{power}</b>",
        f"🏟️ استادیوم: لول {team.stadium_level}/{S.STADIUM_MAX_LEVEL}"
        + (f" — {team.stadium_name}" if team.stadium_name else ""),
        f"🧑‍🏫 کادرِ فنی: لول {team.coach_level}/{S.COACH_MAX_LEVEL}",
        f"⭐ میانگینِ بازیکنان: {team.avg_player_level}/{S.AVG_PLAYER_MAX}",
        f"💰 بودجه: {_fmt(team.budget)}$",
        f"📣 هواداران: رضایت {sat}٪ × جمعیت {_fmt(pop)}",
        "",
        f"🏆 لیگ ({S.DIVISION_LABEL[team.division]}): {team.points} امتیاز — "
        f"{team.wins}برد/{team.draws}مساوی/{team.losses}باخت ({played} بازی)",
        f"⚽ تفاضلِ گل: {team.goals_for - team.goals_against:+d}",
    ]
    # Stage 27: 50-level ladder view for team components
    lines += [
        "",
        "\U0001f4ca \u0646\u0631\u062f\u0628\u0627\u0646\u0650 \u06f5\u06f0 \u0644\u0648\u0644\u06cc:",
        f"  \U0001f3df\ufe0f {S.level_bar(team.stadium_level)} {team.stadium_level}/{S.SPORT_MAX_LEVEL} \u2014 {S.level_tier(team.stadium_level)}",
        f"  \U0001f9d1\u200d\U0001f3eb {S.level_bar(team.coach_level)} {team.coach_level}/{S.SPORT_MAX_LEVEL} \u2014 {S.level_tier(team.coach_level)}",
    ]
    if int(team.stadium_level) < S.STADIUM_MAX_LEVEL:
        lines.append(
            "  \U0001f3df\ufe0f \u0627\u0631\u062a\u0642\u0627\u06cc \u0628\u0639\u062f\u06cc: "
            f"{_fmt(S.stadium_upgrade_cost(team.stadium_level))}$"
        )
    if int(team.coach_level) < S.COACH_MAX_LEVEL:
        lines.append(
            "  \U0001f9d1\u200d\U0001f3eb \u0627\u0631\u062a\u0642\u0627\u06cc \u0628\u0639\u062f\u06cc: "
            f"{_fmt(S.coach_upgrade_cost(team.coach_level))}$"
        )
    return "\n".join(lines)


async def _brand_text(session, uid: int, brand) -> str:
    power = await svc.compute_brand_power(session, brand)
    lines = [
        f"{S.SPORT_EMOJI[brand.sport]} <b>{brand.name}</b>  ({S.SPORT_LABEL[brand.sport]})",
    ]
    if brand.race_team_name:
        lines.append(f"🏎️ تیمِ مسابقه: {brand.race_team_name}")
    lines += [
        "",
        f"⚡ قدرتِ تیم (RP): <b>{power}</b>",
        f"🚗 برندِ خودروسازی: لول {brand.brand_level}/{S.BRAND_MAX_LEVEL}",
        f"🛩️ کارخانه‌ی لاستیک: لول {brand.tire_level}/{S.TIRE_MAX_LEVEL}",
        f"🔧 تیمِ فنی: لول {brand.tech_level}/{S.TECH_MAX_LEVEL}",
        f"🏁 مهارتِ راننده: {brand.driver_skill}/{S.DRIVER_MAX_SKILL}",
        f"🏟️ پیست‌ها: {brand.track_count}/{S.MAX_TRACKS}"
        + (f" — {brand.track_name}" if brand.track_name else ""),
        "",
        f"🏆 مسابقات: {brand.points} امتیاز — {brand.wins}برد/{brand.losses}باخت",
    ]
    # Stage 27: 50-level ladder view for racing components
    lines += [
        "",
        "\U0001f4ca \u0646\u0631\u062f\u0628\u0627\u0646\u0650 \u06f5\u06f0 \u0644\u0648\u0644\u06cc:",
        f"  \U0001f697 {S.level_bar(brand.brand_level)} {brand.brand_level}/{S.SPORT_MAX_LEVEL} \u2014 {S.level_tier(brand.brand_level)}",
        f"  \U0001f6de {S.level_bar(brand.tire_level)} {brand.tire_level}/{S.SPORT_MAX_LEVEL} \u2014 {S.level_tier(brand.tire_level)}",
        f"  \U0001f527 {S.level_bar(brand.tech_level)} {brand.tech_level}/{S.SPORT_MAX_LEVEL} \u2014 {S.level_tier(brand.tech_level)}",
    ]
    nxt = []
    if int(brand.brand_level) < S.BRAND_MAX_LEVEL:
        nxt.append(f"\U0001f697 {_fmt(S.brand_upgrade_cost(brand.brand_level))}$")
    if int(brand.tire_level) < S.TIRE_MAX_LEVEL:
        nxt.append(f"\U0001f6de {_fmt(S.tire_upgrade_cost(brand.tire_level))}$")
    if int(brand.tech_level) < S.TECH_MAX_LEVEL:
        nxt.append(f"\U0001f527 {_fmt(S.tech_upgrade_cost(brand.tech_level))}$")
    if int(brand.driver_skill) < S.DRIVER_MAX_SKILL:
        nxt.append(f"\U0001f3c1 {_fmt(S.driver_upgrade_cost(brand.driver_skill))}$")
    if int(brand.track_count) < S.MAX_TRACKS:
        nxt.append(f"\U0001f3df\ufe0f {_fmt(S.track_build_cost(brand.track_count))}$")
    if nxt:
        lines.append(
            "  \u0627\u0631\u062a\u0642\u0627\u06cc \u0628\u0639\u062f\u06cc: " + " | ".join(nxt)
        )
    return "\n".join(lines)


async def _render_open(session, uid: int, sport: str) -> tuple[str, object]:
    """وضعیتِ یک ورزش را رندر می‌کند (مدیریت یا پیشنهادِ ساخت)."""
    if sport in S.TEAM_SPORTS:
        team = await svc.get_team(session, uid, sport)
        if team is None:
            text = (
                f"{S.SPORT_LABEL[sport]}\n\nهنوز تیمی نداری.\n\n"
                f"🏆 ساختِ تیم — هزینه: <b>{_fmt(S.TEAM_CREATE_COST)}$</b>\n"
                "(شاملِ استادیومِ لول ۱)"
            )
            return text, create_menu(uid, sport)
        return await _team_text(session, uid, team), team_manage_menu(uid, sport)
    else:
        brand = await svc.get_brand(session, uid, sport)
        if brand is None:
            text = (
                f"{S.SPORT_LABEL[sport]}\n\nهنوز برندی نداری.\n\n"
                f"🆕 ساختِ برند — هزینه: <b>{_fmt(S.RACING_CREATE_COST)}$</b>\n"
            )
            if sport == S.F1:
                text += (
                    "\n⚠️ فرمول‌یک وابسته به صنعت است. اول باید برندِ موتورسواری‌ات را به این سطح برسانی:\n"
                    f"• کارخانه‌ی لاستیک لول {S.F1_REQUIRE_TIRE_LEVEL}+\n"
                    f"• برندِ خودروسازی لول {S.F1_REQUIRE_BRAND_LEVEL}+\n"
                    f"• حداقل {S.F1_REQUIRE_TRACKS} پیست\n"
                )
            return text, create_menu(uid, sport)
        return await _brand_text(session, uid, brand), brand_manage_menu(uid, sport)


# ---------------------------------------------------------------------------
# ورودی‌های اصلی
# ---------------------------------------------------------------------------
async def _open_hub_message(message: Message) -> None:
    # 🔄 مرحله ۱۵.۵: قفلِ گروه برداشته شد — ورزش در گروه هم قابلِ دسترس است
    async with async_session() as session:
        text = await _hub_text(session, message.from_user.id)
    await message.answer(text, reply_markup=sports_hub(message.from_user.id))


@router.message(F.text.in_({BTN_SPORTS, WORD_SPORTS}))
async def summon_sports(message: Message) -> None:
    await _open_hub_message(message)


@router.callback_query(F.data.startswith("menu:sports"))
async def open_sports_cb(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    # 🔄 مرحله ۱۵.۵: قفلِ گروه برداشته شد
    async with async_session() as session:
        text = await _hub_text(session, callback.from_user.id)
    await safe_show(callback.message, text, sports_hub(callback.from_user.id))
    await safe_answer(callback)


@router.callback_query(F.data.startswith("sport:hub"))
async def hub_cb(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    async with async_session() as session:
        text = await _hub_text(session, callback.from_user.id)
    await safe_show(callback.message, text, sports_hub(callback.from_user.id))
    await safe_answer(callback)


@router.callback_query(F.data.startswith("sport:events"))
async def events_cb(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    ev = svc.current_event()
    eff_line = S.active_effect_line()
    async with async_session() as session:
        results = await svc.build_daily_announcement(session)
    text = (
        "📅 <b>اونتِ امروز</b>\n\n"
        f"🎟️ <b>{ev['name']}</b>\n\n"
        f"⚙️ تأثیر: {ev['effect']}\n"
        f"⏰ ساعتِ فعال‌سازی: {ev.get('window', '—')}"
    )
    if ev.get("key") == "normal":
        text += "\n\n🌤️ امروز روزِ عادی است؛ هیچ اثری فعال نمی‌شود (هر ۳ روز یک‌بار)."
    elif eff_line:
        text += f"\n\n{eff_line}"
    else:
        text += "\n\n💤 اثرِ ویژه‌ی این اونت هنوز شروع نشده یا پایان یافته (به ساعتِ فعال‌سازی توجه کن)."
    text += "\n\n➖➖➖➖➖\n\n"
    if results:
        text += results
    else:
        text += (
            "🏆 <b>نتایجِ مسابقاتِ اخیر</b>\n\n"
            "هنوز در ۲۴ ساعتِ گذشته مسابقه‌ای ثبت نشده.\n"
            "یک مسابقه انجام بده تا نتیجه‌اش همین‌جا نمایش داده شود."
        )
    await safe_show(callback.message, text, events_menu(callback.from_user.id))
    await safe_answer(callback)


@router.callback_query(F.data.startswith("sport:open:"))
async def open_sport_cb(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    base, _ = split_owner(callback.data)
    sport = base.split(":")[2]
    # 🆕 v1.8.1.2 — فوتبال از هاب ورزش ← فوتبال منیجر جدید (نه فوتبالِ قدیمی)
    if sport == "football":
        from app.handlers import football as _fb
        await _fb._show_hub(callback)
        return
    if sport not in S.ALL_SPORTS:
        await safe_answer(callback, "ورزشِ نامعتبر.", show_alert=True)
        return
    async with async_session() as session:
        text, markup = await _render_open(session, callback.from_user.id, sport)
    await safe_show(callback.message, text, markup)
    await safe_answer(callback)


@router.callback_query(F.data.startswith("sport:league:"))
async def league_cb(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    base, _ = split_owner(callback.data)
    sport = base.split(":")[2]
    uid = callback.from_user.id
    async with async_session() as session:
        table = await svc.league_table(session, sport, limit=50)
        registered_count = await svc.league_registered_count(session, sport)
        my_status = await svc.league_registration_status(session, uid, sport)
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    lines = [
        f"🏆 <b>جدولِ لیگ — {S.SPORT_LABEL[sport]}</b>",
        "",
    ]
    if sport in S.TEAM_SPORTS:
        lines += [
            "🗓️ لیگ یک تورنمنت حذفیِ هفتگی است: فقط تیم‌هایی که برای این هفته ثبت‌نام کرده‌اند شرکت می‌کنند.",
            "❗️ باخت = حذف. اگر تعداد فرد باشد، یک تیمِ تصادفی به‌جای استراحت دو مسابقه بازی می‌کند و فقط با بردن هر دو صعود می‌کند.",
            f"👥 ثبت‌نام‌شده‌ها برای لیگِ این هفته: <b>{registered_count}</b>",
            ("✅ تو برای لیگِ این هفته ثبت‌نام کرده‌ای." if my_status else "❌ هنوز برای این هفته ثبت‌نام نکرده‌ای — از دکمهِ «🏆 ثبت‌نامِ لیگ» استفاده کن."),
            "",
            "📊 <b>جدولِ کلی</b> (مجموعِ امتیاز‌های همهِ لیگهای حذفیی که تاکنون برگزار شده‌اند):",
            "",
        ]
    else:
        lines.append("")
    if not table:
        lines.append("هنوز هیچ نتیجه‌ای ثبت نشده است.")
    else:
        for i, r in enumerate(table[:15], 1):
            badge = medals.get(i, f"{i}.")
            me = "  👈 <b>تو</b>" if r["uid"] == uid else ""
            lines.append(f"{badge} {r['name']} — {r['points']} امتیاز ({r['wins']}برد){me}")
    await safe_show(callback.message, "\n".join(lines), back_menu(uid, sport))
    await safe_answer(callback)


@router.callback_query(F.data.startswith("sport:regleague:"))
async def register_league_cb(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    base, _ = split_owner(callback.data)
    sport = base.split(":")[2]
    uid = callback.from_user.id
    async with async_session() as session:
        ok, msg = await svc.register_for_league(session, uid, sport)
        text, markup = await _render_open(session, uid, sport)
    if ok:
        await safe_show(callback.message, msg + "\n\n" + text, markup)
        await safe_answer(callback, "✅ ثبت‌نام شد!")
    else:
        await safe_answer(callback, msg, show_alert=True)


# ---------------------------------------------------------------------------
# ساختِ تیم/برند
# ---------------------------------------------------------------------------
@router.callback_query(F.data.startswith("sport:create:"))
async def create_cb(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    base, _ = split_owner(callback.data)
    sport = base.split(":")[2]
    uid = callback.from_user.id
    async with async_session() as session:
        player = await svc.get_player(session, uid)
        if player is None:
            await safe_answer(callback, "اول /start را بزن تا ثبت‌نام شوی.", show_alert=True)
            return
        cost = S.RACING_CREATE_COST if sport in S.RACING_SPORTS else S.TEAM_CREATE_COST
        if sport in S.TEAM_SPORTS:
            existing = await svc.get_team(session, uid, sport)
        else:
            existing = await svc.get_brand(session, uid, sport)
        if existing is not None:
            await safe_answer(callback, "این ورزش را قبلاً ساخته‌ای.", show_alert=True)
            return
        # پیش‌نیازِ فرمول‌یک: داشتنِ برندِ موتوریِ پیشرفته (وابسته به صنعت)
        if sport == S.F1:
            moto = await svc.get_brand(session, uid, S.MOTO)
            if (moto is None
                    or moto.tire_level < S.F1_REQUIRE_TIRE_LEVEL
                    or moto.brand_level < S.F1_REQUIRE_BRAND_LEVEL
                    or moto.track_count < S.F1_REQUIRE_TRACKS):
                await safe_answer(callback, 
                    "⛔ برای فرمول‌یک اول باید برندِ موتورسواری‌ات را بسازی و لاستیک ۳+، برند ۵+ و ۳ پیست داشته باشی.",
                    show_alert=True,
                )
                return
        if int(player.cash or 0) < cost:
            await safe_answer(callback, f"💸 پولت کافی نیست. نیاز: {_fmt(cost)}$", show_alert=True)
            return
        player.cash = int(player.cash) - cost
        default_name = f"{('تیم' if sport in S.TEAM_SPORTS else 'برند')}ِ {player.name}"
        if sport in S.TEAM_SPORTS:
            from app.models.sports import SportsTeam
            session.add(SportsTeam(
                tg_user_id=uid, sport=sport, name=default_name[:64],
                stadium_level=1, coach_level=1, avg_player_level=10, budget=0,
                division=S.DIVISION_TWO, in_league=False,
            ))
        else:
            from app.models.sports import RacingBrand
            session.add(RacingBrand(
                tg_user_id=uid, sport=sport, name=default_name[:64],
                brand_level=1, tire_level=1, tech_level=1, driver_skill=20, track_count=1,
            ))
        await session.commit()
        text, markup = await _render_open(session, uid, sport)
    await safe_show(callback.message, "✅ ساخته شد! از بخشِ برندسازی می‌توانی نام/رنگ/شعار را تغییر دهی.\n\n" + text, markup)
    await safe_answer(callback, "🎉 مبارک!")


# ---------------------------------------------------------------------------
# ارتقاءها
# ---------------------------------------------------------------------------
async def _do_upgrade(session, uid: int, sport: str, what: str) -> tuple[bool, str]:
    player = await svc.get_player(session, uid)
    if player is None:
        return False, "اول /start را بزن."
    ev = svc.current_event()

    if sport in S.TEAM_SPORTS:
        team = await svc.get_team(session, uid, sport)
        if team is None:
            return False, "اول تیم بساز."
        if what == "stadium":
            if team.stadium_level >= S.STADIUM_MAX_LEVEL:
                return False, "استادیوم در بالاترین لول است."
            cost = S.stadium_upgrade_cost(team.stadium_level)
            if int(player.cash) < cost:
                return False, f"💸 نیاز: {_fmt(cost)}$"
            player.cash -= cost
            team.stadium_level += 1
            msg = f"🏟️ استادیوم به لول {team.stadium_level} رسید. (−{_fmt(cost)}$)"
        elif what == "coach":
            if team.coach_level >= S.COACH_MAX_LEVEL:
                return False, "کادرِ فنی در بالاترین لول است."
            cost = S.coach_upgrade_cost(team.coach_level)
            if int(player.cash) < cost:
                return False, f"💸 نیاز: {_fmt(cost)}$"
            player.cash -= cost
            team.coach_level += 1
            msg = f"🧑‍🏫 کادرِ فنی به لول {team.coach_level} رسید. (−{_fmt(cost)}$)"
        elif what == "player":
            if team.avg_player_level >= S.AVG_PLAYER_MAX:
                return False, "میانگینِ بازیکنان در سقف است."
            cost = S.star_player_cost()
            if int(player.cash) < cost:
                return False, f"💸 نیاز: {_fmt(cost)}$"
            player.cash -= cost
            team.avg_player_level = min(S.AVG_PLAYER_MAX, team.avg_player_level + S.STAR_PLAYER_STEP)
            disc = " (تخفیفِ بازارِ سیاه!)" if ev.get("key") == S.STAR_DISCOUNT_EVENT else ""
            msg = f"⭐ بازیکنِ ستاره خریدی! میانگین → {team.avg_player_level} (−{_fmt(cost)}${disc})"
        else:
            return False, "ارتقای نامعتبر."
    else:
        brand = await svc.get_brand(session, uid, sport)
        if brand is None:
            return False, "اول برند بساز."
        if what == "brand":
            if brand.brand_level >= S.BRAND_MAX_LEVEL:
                return False, "برند در بالاترین لول است."
            cost = S.brand_upgrade_cost(brand.brand_level)
            if int(player.cash) < cost:
                return False, f"💸 نیاز: {_fmt(cost)}$"
            player.cash -= cost
            brand.brand_level += 1
            msg = f"🚗 برند به لول {brand.brand_level} رسید. (−{_fmt(cost)}$)"
        elif what == "tire":
            if brand.tire_level >= S.TIRE_MAX_LEVEL:
                return False, "کارخانه‌ی لاستیک در سقف است."
            cost = S.tire_upgrade_cost(brand.tire_level)
            if int(player.cash) < cost:
                return False, f"💸 نیاز: {_fmt(cost)}$"
            player.cash -= cost
            brand.tire_level += 1
            msg = f"🛩️ کارخانه‌ی لاستیک به لول {brand.tire_level} رسید. (−{_fmt(cost)}$)"
        elif what == "tech":
            if brand.tech_level >= S.TECH_MAX_LEVEL:
                return False, "تیمِ فنی در سقف است."
            cost = S.tech_upgrade_cost(brand.tech_level)
            if int(player.cash) < cost:
                return False, f"💸 نیاز: {_fmt(cost)}$"
            player.cash -= cost
            brand.tech_level += 1
            msg = f"🔧 تیمِ فنی به لول {brand.tech_level} رسید. (−{_fmt(cost)}$)"
        elif what == "driver":
            if brand.driver_skill >= S.DRIVER_MAX_SKILL:
                return False, "راننده در بالاترین مهارت است."
            cost = S.driver_upgrade_cost(brand.driver_skill)
            if int(player.cash) < cost:
                return False, f"💸 نیاز: {_fmt(cost)}$"
            player.cash -= cost
            brand.driver_skill = min(S.DRIVER_MAX_SKILL, brand.driver_skill + S.DRIVER_SKILL_STEP)
            msg = f"🏁 راننده ارتقا یافت! مهارت → {brand.driver_skill} (−{_fmt(cost)}$)"
        elif what == "track":
            if brand.track_count >= S.MAX_TRACKS:
                return False, "بیشترین تعدادِ پیست را ساخته‌ای."
            cost = S.track_build_cost(brand.track_count)
            if int(player.cash) < cost:
                return False, f"💸 نیاز: {_fmt(cost)}$"
            player.cash -= cost
            brand.track_count += 1
            msg = f"🏟️ پیستِ جدید ساخته شد! تعداد → {brand.track_count} (−{_fmt(cost)}$)"
        else:
            return False, "ارتقای نامعتبر."

    # Stage 27: XP from everywhere - every sports upgrade grants XP.
    try:
        from app.data import leveling as _lv

        gained = int(min(300, max(10, int(cost) // 40_000)))
        _xp_res = await _lv.grant_xp(session, player, gained, source="sports_upgrade")
        msg = f"{msg}{_lv.xp_note(_xp_res)}"
    except Exception:
        pass
    await session.commit()
    return True, msg


@router.callback_query(F.data.startswith("sport:up:"))
async def upgrade_cb(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    base, _ = split_owner(callback.data)
    parts = base.split(":")   # sport:up:<sport>:<what>
    sport, what = parts[2], parts[3]
    async with async_session() as session:
        ok, msg = await _do_upgrade(session, callback.from_user.id, sport, what)
        text, markup = await _render_open(session, callback.from_user.id, sport)
    if ok:
        await safe_show(callback.message, msg + "\n\n" + text, markup)
        await safe_answer(callback, "✅")
    else:
        await safe_answer(callback, msg, show_alert=True)


# ---------------------------------------------------------------------------
# تزریقِ بودجه (فوتبال/بسکتبال)
# ---------------------------------------------------------------------------
BUDGET_STEP = 100_000


@router.callback_query(F.data.startswith("sport:budget:"))
async def budget_cb(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    base, _ = split_owner(callback.data)
    sport = base.split(":")[2]
    uid = callback.from_user.id
    async with async_session() as session:
        player = await svc.get_player(session, uid)
        team = await svc.get_team(session, uid, sport)
        if team is None or player is None:
            await safe_answer(callback, "اول تیم بساز.", show_alert=True)
            return
        if int(player.cash or 0) < BUDGET_STEP:
            await safe_answer(callback, f"💸 برای تزریق حداقل {_fmt(BUDGET_STEP)}$ لازم است.", show_alert=True)
            return
        player.cash -= BUDGET_STEP
        team.budget += BUDGET_STEP
        await session.commit()
        text, markup = await _render_open(session, uid, sport)
    await safe_show(callback.message, f"💰 {_fmt(BUDGET_STEP)}$ به بودجه‌ی تیم اضافه شد.\n\n" + text, markup)
    await safe_answer(callback, "✅")


# ---------------------------------------------------------------------------
# اجرای مسابقه
# ---------------------------------------------------------------------------
def _match_report(sport: str, info: dict, uid: int) -> str:
    res = info["result"]
    ev = info["event"]
    if sport in S.RACING_SPORTS:
        brand = info["brand"]
        won = res.winner == "A"
        head = "🏁 <b>قهرمانِ پیست شدی!</b>" if won else "🏎️ <b>مسابقه تمام شد</b>"
        lines = [
            head, "",
            f"{brand.race_team_name or brand.name}  ⚡{info['power_a']}",
            f"{info['team_b_name']}  ⚡{info['power_b']}",
            "",
            ("🥇 نتیجه: برد" if won else ("🤝 نتیجه: مساوی" if res.winner == "draw" else "❌ نتیجه: باخت")),
        ]
    else:
        team = info["team"]
        won = res.winner == "A"
        head = "🏆 <b>بردی!</b>" if won else ("🤝 <b>مساوی</b>" if res.winner == "draw" else "❌ <b>باخت</b>")
        lines = [
            head, "",
            f"{team.name}  <b>{res.score_a} - {res.score_b}</b>  {info['team_b_name']}",
            f"⚡ قدرت: {info['power_a']} مقابلِ {info['power_b']}",
        ]
        if info.get("star") and res.score_a > 0:
            lines.append(f"⭐ بهترین بازیکن: {info['star']}")
    if res.events:
        lines.append("")
        lines.append("🃏 <b>رویدادهای مسابقه:</b>")
        for e in res.events:
            lines.append(f"  • {S.EVENT_LABEL.get(e, e)} — {S.EVENT_DESC.get(e, '')}")
    lines.append("")
    if info["prize"]:
        lines.append(f"💰 جایزه: +{_fmt(info['prize'])}$")
    lines.append(f"📅 ایونت: {ev['name']}")
    return "\n".join(lines)


@router.callback_query(F.data.startswith("sport:play:"))
async def play_cb(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    base, _ = split_owner(callback.data)
    sport = base.split(":")[2]
    uid = callback.from_user.id
    rng = random.Random()
    async with async_session() as session:
        # 🆕 پچ — محدودیتِ روزانه: هر ورزش حداکثر S.DAILY_MATCH_LIMIT مسابقه در روز (به‌وقتِ تهران)
        played_today = await svc.matches_played_today(session, uid, sport)
        if played_today >= S.DAILY_MATCH_LIMIT:
            wait_s = await svc.seconds_until_daily_reset()
            await safe_answer(callback, 
                f"🚫 سهمیه‌ی مسابقه‌ی امروزِ {S.SPORT_LABEL[sport]} تمام شده "
                f"({S.DAILY_MATCH_LIMIT} مسابقه در روز). تا نیمه‌شب به‌وقتِ تهران: {_fmt_hm(wait_s)}.",
                show_alert=True,
            )
            return
        if sport in S.RACING_SPORTS:
            info = await svc.play_race(session, uid, sport, rng)
        else:
            info = await svc.play_team_match(session, uid, sport, rng)
    if info is None:
        await safe_answer(callback, "اول تیم/برند بساز.", show_alert=True)
        return
    text = _match_report(sport, info, uid)
    await safe_show(callback.message, text, after_match_menu(uid, sport))
    await safe_answer(callback, "🏁")


# ---------------------------------------------------------------------------
# برندسازی (FSM)
# ---------------------------------------------------------------------------
@router.callback_query(F.data.startswith("sport:brand:"))
async def brand_menu_cb(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    base, _ = split_owner(callback.data)
    sport = base.split(":")[2]
    text = (
        "🎨 <b>برندسازی و شخصی‌سازی</b>\n\n"
        "نام، رنگ و هویتِ دلخواهِ خود را بساز. این نام‌ها در اعلانِ قهرمانِ روزانه، جدولِ لیگ و پیام‌های مسابقه نمایان می‌شوند.\n\n"
        f"ℹ️ تغییرِ نامِ بعدی هزینه‌ی {_fmt(S.RENAME_COST)}$ دارد (ضدِ سوءاستفاده)."
    )
    await safe_show(callback.message, text, branding_menu(callback.from_user.id, sport))
    await safe_answer(callback)


@router.callback_query(F.data.startswith("sport:rn:"))
async def rename_start_cb(callback: CallbackQuery, state: FSMContext) -> None:
    if not await ensure_owner(callback):
        return
    base, _ = split_owner(callback.data)
    parts = base.split(":")   # sport:rn:<sport>:<field>
    sport, field = parts[2], parts[3]
    await state.set_state(SportsStates.naming)
    await state.update_data(sport=sport, field=field)
    prompt = _FIELD_PROMPT.get(field, "مقدارِ جدید را بفرست")
    await callback.message.answer(
        f"✏️ {prompt}\n(۳ تا ۳۲ کاراکتر)" + CANCEL_HINT,
    )
    await safe_answer(callback)


@router.message(SportsStates.naming)
async def rename_apply(message: Message, state: FSMContext) -> None:
    if await handle_cancel_word(message, state):
        return
    raw = (message.text or "").strip()
    data = await state.get_data()
    sport, field = data.get("sport"), data.get("field")
    # رنگ اعتبارسنجیِ سبک‌تر (فقط طول)
    if field == "color":
        value = " ".join(raw.split())[:32]
        err = None if value else "رنگ خالی است."
    elif field == "slogan":
        value = " ".join(raw.split())[:128]
        err = None if value else "شعار خالی است."
    else:
        value, err = S.validate_name(raw)
    if err:
        await message.answer(f"⚠️ {err}\nدوباره بفرست یا «لغو» را بنویس.")
        return

    uid = message.from_user.id
    async with async_session() as session:
        player = await svc.get_player(session, uid)
        if sport in S.TEAM_SPORTS:
            obj = await svc.get_team(session, uid, sport)
        else:
            obj = await svc.get_brand(session, uid, sport)
        if obj is None or player is None:
            await state.clear()
            await message.answer("تیم/برند پیدا نشد.")
            return

        # نام‌گذاریِ اول رایگان (نامِ پیش‌فرض)؛ تغییراتِ بعدی هزینه دارد
        default_prefix = "تیمِ " if sport in S.TEAM_SPORTS else "برندِ "
        is_first_name = field == "name" and obj.name.startswith(default_prefix)
        charge = S.RENAME_COST if not is_first_name else 0
        if charge and int(player.cash or 0) < charge:
            await state.clear()
            await message.answer(f"💸 برای تغییرِ نام به {_fmt(charge)}$ نیاز داری.")
            return

        if field == "name":
            obj.name = value
        elif field == "color":
            obj.color = value
        elif field == "slogan":
            obj.slogan = value
        elif field == "stadium":
            obj.stadium_name = value
        elif field == "raceteam":
            obj.race_team_name = value
        elif field == "track":
            obj.track_name = value
        if charge:
            player.cash -= charge
        await session.commit()
    await state.clear()
    extra = f" (−{_fmt(charge)}$)" if charge else ""
    await message.answer(f"✅ ذخیره شد: <b>{value}</b>{extra}\n«ورزش» را بفرست تا پنل را دوباره ببینی.")
