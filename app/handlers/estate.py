from datetime import datetime

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select

from app.database.engine import async_session
from app.models.player import Player
from app.models.hideout import get_hideout
from app.models.estate import Estate
from app.models.professional import OwnedProfessional
from app.data.estates import (
    CUPOLA_KEY,
    ESTATES,
    ESTATE_MAX_LEVEL,
    MAX_BASE_TYPE,
    SLOTS_PER_ESTATE,
    aggregate_effects,
    describe_effects,
    estate_effect_line,
    estate_income_label,
    estate_income_mult,
    estate_upgrade_cost,
    get_estate_role,
    is_estate_unlocked,
    missing_prereqs,
)
from app.data import events
from app.data.bases import tier4_base_for_estate
from app.data.professionals import (
    GROUPS,
    get_professional,
    professionals_for_estate,
)
from app.data.upgrades import MAX_FEATURE_LEVEL
from app.data.economy import (
    MAX_OFFLINE_HOURS,
    MAX_PROF_LEVEL,
    effective_subs,
    hours_between,
    income_rate_per_hour,
    promote_cost,
    salary_accrued_for,
    salary_due_for,
    salary_rate_per_hour,
    subordinates_for_level,
)
from app.keyboards.estate_menu import (
    assign_menu,
    build_list_menu,
    estate_hire_menu,
    estate_menu,
    estates_hub_menu,
    hire_categories_menu,
    hire_group_menu,
    locked_menu,
    promote_menu,
    salary_menu,
)
from app.keyboards.main_menu import BTN_ESTATE, WORD_ESTATE

from app.utils.ui import ensure_owner, safe_edit, safe_answer, click_debounce

router = Router()

# Stage 27: congratulation messages for estate milestones
ESTATE_BUILT_MSG = (
    "🎉 <b>تبریک!</b>\n"
    "عمارتِ {name} به امپراتوری‌ات اضافه شد.\n"
    "حالا دوباره به بخشِ پایگاه برو و پایگاهِ تخصصیِ بعدی را بساز تا عمارتِ تازه‌ای باز شود."
)
ALL_ESTATES_DONE_MSG = (
    "🏆 <b>تمامِ عمارت‌ها را ساختی!</b>\n"
    "هرمِ ده‌گانه‌ی خانواده کامل شد و دیگر نیازی به ساختِ پایگاهِ تخصصیِ جدید نیست.\n"
    "از این پس روی ارتقای عمارت‌ها، حرفه‌ای‌ها و قدرتِ نظامی‌ات تمرکز کن."
)

ONLY_BOT = "🏛️ مدیریت عمارت فقط داخلِ خودِ ربات ممکن است، نه در گروه."
REQUIRED_LEVEL = 10  # سطحِ لازم برای ساختِ هر عمارت (پایگاهِ تخصصیِ تیرِ ۴ هم همین را می‌خواهد)


# ---------- توابع کمکی دیتابیس ----------
async def get_player(session, tg_user_id: int):
    result = await session.execute(select(Player).where(Player.tg_user_id == tg_user_id))
    return result.scalar_one_or_none()


async def get_all_estates(session, tg_user_id: int):
    """همه‌ی عمارت‌های یک بازیکن (به ترتیبِ ساخت)."""
    result = await session.execute(
        select(Estate).where(Estate.tg_user_id == tg_user_id).order_by(Estate.id)
    )
    return list(result.scalars().all())


async def get_estate(session, estate_id: int, tg_user_id: int):
    """یک عمارتِ مشخص را با چکِ مالکیت برمی‌گرداند (یا None)."""
    estate = await session.get(Estate, estate_id)
    if estate is None or estate.tg_user_id != tg_user_id:
        return None
    return estate


async def owned_pros(session, tg_user_id: int):
    result = await session.execute(
        select(OwnedProfessional).where(OwnedProfessional.tg_user_id == tg_user_id)
    )
    return list(result.scalars().all())


async def assigned_pros(session, estate_id: int):
    result = await session.execute(
        select(OwnedProfessional).where(OwnedProfessional.assigned_estate_id == estate_id)
    )
    return list(result.scalars().all())


async def _edit(callback: CallbackQuery, text: str, markup=None):
    # پیام را «درجا» ادیت می‌کند (چه متنی چه عکس‌دار) تا پیامِ جدید ارسال نشود.
    await safe_edit(callback.message, text, markup)


def _villa_maxed(hideout, required_base: str) -> bool:
    return (
        hideout is not None
        and hideout.base_type == required_base
        and hideout.authority_level >= MAX_FEATURE_LEVEL
    )


# 🆕 مرحله ۲۶.۱: پایگاهِ فعلی (اگه برایِ عمارتِ خاصی نام‌گذاری شده) دقیقاً همون یکی را می‌سازد
def _currently_buildable(hideout, unlocked_keys):
    if not _villa_maxed(hideout, MAX_BASE_TYPE):
        return []
    variant = getattr(hideout, "final_variant", None)
    if variant and variant in unlocked_keys:
        return [variant]
    return []


# ---------- افکتِ امپراتوری ----------
async def empire_totals(session, tg_user_id: int):
    """جمعِ افکتِ همه‌ی عمارت‌های بازیکن (dict بر حسبِ نوعِ افکت)."""
    estates = await get_all_estates(session, tg_user_id)
    return aggregate_effects([(e.role_key, e.level) for e in estates])


def income_multiplier(totals) -> float:
    """ضریبِ نهاییِ درآمد از روی جمعِ افکت‌ها."""
    return 1.0 + totals.get("income_pct", 0.0)


# ---------- اقتصاد (مرحله ۷، حالا با ضریبِ امپراتوری) ----------
async def _active_income_rate(session, estate, now, mult: float = 1.0) -> int:
    active = await assigned_pros(session, estate.id)
    rate = 0
    for op in active:
        _, _, strike = salary_due_for(op, now)
        if strike:
            continue
        rate += income_rate_per_hour(effective_subs(op))
    # 🆕 مرحله ۲۸ — هر عمارت بسته به ویژگی‌هایش ضریبِ درآمدِ متفاوتی دارد
    # (پلوس سطحِ خودِ عمارت: هر سطح +۸٪).
    role_mult = estate_income_mult(estate.role_key)
    level_mult = 1.0 + 0.08 * max(0, int(estate.level or 1) - 1)
    # 🆕 مرحله ۳۰ — بونوسِ income_pct ِ لقب‌ها واقعاً رویِ درآمد اعمال می‌شود
    title_mult = 1.0
    try:
        from app.services import title_effects
        title_mult = await title_effects.multiplier(session, estate.tg_user_id, "income_pct")
    except Exception:
        title_mult = 1.0
    referral_mult = 1.0
    try:
        from app.services import referral_service
        referral_mult += (await referral_service.bonus_pct(session, estate.tg_user_id)) / 100
    except Exception:
        pass
    return int(rate * mult * role_mult * level_mult * title_mult * referral_mult)


async def pending_income(session, estate, mult: float = 1.0) -> int:
    now = datetime.utcnow()
    anchor = estate.last_collected_at or estate.created_at or now
    hours = min(MAX_OFFLINE_HOURS, hours_between(anchor, now))
    rate = await _active_income_rate(session, estate, now, mult)
    return int(rate * hours)


def salary_text(rows) -> str:
    # 🆕 مرحله ۶۹ — حقوق دیگر سررسیدِ هفتگی ندارد؛ مثلِ درآمد لحظه‌ای جمع می‌شود.
    lines = ["💵 <b>حقوقِ حرفه‌ای‌ها (لحظه‌ای)</b>", ""]
    any_due = False
    total = 0
    total_rate = 0.0
    for op, due, late, strike in rows:
        info = get_professional(op.prof_key)
        name = info["name"] if info else op.prof_key
        rate = salary_rate_per_hour(effective_subs(op))
        total_rate += rate
        total += max(0, due)
        if strike:
            lines.append(f"🚨 {name}: اعتصاب! ({due:,}$ برای پایانِ اعتصاب)")
            any_due = True
        elif due > 0:
            extra = f" (+{late} روز دیرکرد)" if late else ""
            lines.append(f"💰 {name}: {due:,}$ قابلِ پرداخت{extra} — نرخ {rate:,.0f}$/ساعت")
            any_due = True
        else:
            lines.append(f"✅ {name}: تازه تسویه شده — نرخ {rate:,.0f}$/ساعت")
    lines.append("")
    if any_due:
        lines.append(f"🧾 جمعِ قابلِ پرداخت: <b>{total:,}$</b>")
    else:
        lines.append("همه‌ی حرفه‌ای‌ها تسویه‌اند 🎉")
    lines.append(f"⏱ نرخِ کلِ انباشت: {total_rate:,.0f}$/ساعت — هر وقت خواستی پرداخت کن.")
    return "\n".join(lines)


# ---------- داشبوردِ امپراتوری ----------
async def render_hub(session, player: Player):
    estates = await get_all_estates(session, player.tg_user_id)

    # حالت A: هنوز هیچ عمارتی ندارد
    if not estates:
        hideout = await get_hideout(session, player.tg_user_id)
        villa_ok = _villa_maxed(hideout, MAX_BASE_TYPE)
        level_ok = player.level >= REQUIRED_LEVEL
        if not (villa_ok and level_ok):
            lines = [
                "🔒 <b>هنوز عمارت نساخته‌ای!</b>",
                "",
                "برای ساختِ اولین عمارتت <b>Cupola</b> باید هر دو شرط را کامل کنی:",
                f"{'✅' if level_ok else '❌'} رسیدن به سطح {REQUIRED_LEVEL} (فعلی: {player.level})",
                f"{'✅' if villa_ok else '❌'} پایگاهِ 🏛️ Palazzo (پایگاهِ مرکزی) با اقتدارِ مکس (سطح ۵)",
            ]
            return "\n".join(lines), locked_menu()
        # واجدِ شرایط → مستقیم لیستِ ساخت
        return await render_build_list(session, player)

    # حالت B: یک یا چند عمارت دارد → داشبورد
    now = datetime.utcnow()
    totals = aggregate_effects([(e.role_key, e.level) for e in estates])
    mult = income_multiplier(totals)
    built = {e.role_key for e in estates}

    lines = [
        "🏛️ <b>امپراتوریِ عمارت‌ها</b>",
        f"💵 موجودی: <b>{player.cash:,}</b> دلار",
        f"🏰 عمارت‌ها: <b>{len(estates)}/{len(ESTATES)}</b>",
        "",
    ]
    total_pending = 0
    for e in estates:
        role = get_estate_role(e.role_key)
        active = await assigned_pros(session, e.id)
        pend = await pending_income(session, e, mult)
        total_pending += pend
        # 🆕 مرحله ۶۹ — حقوق لحظه‌ای است، پس جایِ «تعدادِ عقب‌افتاده» مبلغ را نشان می‌دهیم.
        salary_due = sum(salary_due_for(op, now)[0] for op in active)
        warn = f" | 💵{salary_due:,}$" if salary_due else ""
        lines.append(
            f"• {role['name']} — سطح {e.level} | 🎯{len(active)}/{SLOTS_PER_ESTATE} | 💰{pend:,}${warn}"
        )

    eff_lines = describe_effects(totals)
    if eff_lines:
        lines.append("")
        lines.append("✨ <b>افکتِ کلِ امپراتوری:</b>")
        lines.extend(f"  {x}" for x in eff_lines)

    lines.append("")
    lines.append(f"���� ��جموعِ درآمدِ آماده: <b>{total_pending:,}</b> دلار")

    hideout = await get_hideout(session, player.tg_user_id)
    unlocked = [k for k in ESTATES if k not in built and is_estate_unlocked(k, built)]
    effective = _currently_buildable(hideout, unlocked)
    # Stage 27: batch collect / batch salary buttons
    overdue_total = 0
    for e in estates:
        for op in await assigned_pros(session, e.id):
            overdue_total += salary_due_for(op, now)[0]
    return "\n".join(lines), estates_hub_menu(
        estates, len(effective), total_pending, overdue_total
    )


# ---------- لیستِ ساختِ عمارتِ جدید ----------
async def render_build_list(session, player: Player):
    estates = await get_all_estates(session, player.tg_user_id)
    built = {e.role_key for e in estates}
    hideout = await get_hideout(session, player.tg_user_id)
    villa_ok = _villa_maxed(hideout, MAX_BASE_TYPE)
    all_built = len(built) >= len(ESTATES)

    unlocked = [k for k in ESTATES if k not in built and is_estate_unlocked(k, built)]
    locked = [k for k in ESTATES if k not in built and not is_estate_unlocked(k, built)]
    # 🆕 مرحله ۲۶.۱: پایگاهِ فعلی (اگه نام‌گذاری شده) دقیقاً برایِ کدوم عمارت مصرف می‌شود
    effective = _currently_buildable(hideout, unlocked)
    other_available = [k for k in unlocked if k not in effective]

    lines = [
        "🏗️ <b>ساختِ عمارتِ جدید</b>",
        f"💵 موجودی: <b>{player.cash:,}</b> دلار",
    ]
    if not all_built:
        lines.append(f"{'✅' if villa_ok else '❌'} پایگاهِ تخصصیِ تیرِ ۴ با اقتدارِ مکس (برای هر ساخت لازم است)")
    lines.append("")

    if all_built:
        lines.append("🎉 <b>تبریک! تمام عمارت‌هایِ هرم رو ساختی؛ دیگه عمارتِ جدیدی برای ساخت نمونده.</b>")
    elif effective:
        lines.append("<b>قابلِ ساخت با پایگاهِ تخصصیِ فعلی‌ات:</b>")
        for k in effective:
            role = get_estate_role(k)
            lines.append(f"• {role['name']} — {role['found_cost']:,}$")
            lines.append(f"    ↳ پایگاه: {tier4_base_for_estate(k)}")
    elif villa_ok:
        lines.append(
            "⚠️ پایگاهِ فعلی‌ات برایِ عمارتی که قابلِ ساخت باشد مخصوص نشده؛ "
            "دوباره در بخشِ «🏰 پایگاه» یک پایگاهِ تخصصیِ تیرِ ۴ برایِ عمارتِ موردِ نظرت بساز."
        )
    else:
        lines.append("فعلاً عمارتِ جدیدی برای ساخت باز نشده.")

    if other_available:
        lines.append("")
        lines.append("🔓 <b>باز شده در هرم (نیازمندِ پایگاهِ تخصصیِ خودشون):</b>")
        for k in other_available:
            role = get_estate_role(k)
            lines.append(f"• {role['name']} — نیازمندِ {tier4_base_for_estate(k)}")

    if locked:
        lines.append("")
        lines.append("🔒 <b>هنوز قفل:</b>")
        for k in locked:
            role = get_estate_role(k)
            miss = "، ".join(get_estate_role(p)["name"] for p in missing_prereqs(k, built))
            lines.append(f"• {role['name']} — نیازمندِ: {miss}")

    return "\n".join(lines), build_list_menu(effective, bool(estates))


# ---------- جزئیاتِ یک عمارت ----------
async def render_estate_detail(session, player: Player, estate):
    now = datetime.utcnow()
    totals = await empire_totals(session, player.tg_user_id)
    mult = income_multiplier(totals)
    role = get_estate_role(estate.role_key)
    active = await assigned_pros(session, estate.id)
    all_owned = await owned_pros(session, player.tg_user_id)
    rate = await _active_income_rate(session, estate, now, mult)
    pend = await pending_income(session, estate, mult)

    overdue = 0
    lines = [
        f"{role['name']} — سطح <b>{estate.level}</b>/{ESTATE_MAX_LEVEL}",
        f"💵 موجودی: <b>{player.cash:,}</b> دلار",
    ]
    eff = estate_effect_line(estate.role_key, estate.level)
    if eff:
        lines.append(f"🎖️ نقشِ عمارت: {eff}")
    lines += [
        "",
        f"🎯 اسلات‌های فعال: <b>{len(active)}/{SLOTS_PER_ESTATE}</b>",
        f"📈 درآمدِ ساعتی: <b>{rate:,}</b> دلار/ساعت",
        f"🏷️ ماهیتِ اقتصادی: {estate_income_label(estate.role_key)} "
        f"(×{estate_income_mult(estate.role_key):.2f})",
        f"💰 درآمدِ آماده: <b>{pend:,}</b> دلار",
    ]
    if active:
        lines.append("")
        for op in active:
            info = get_professional(op.prof_key)
            name = info["name"] if info else op.prof_key
            subs = effective_subs(op)
            due, _late, strike = salary_due_for(op, now)
            overdue += max(0, due)
            status = "🚨 اعتصاب" if strike else (f"💵 {due:,}$ حقوقِ آماده" if due > 0 else "✅ فعال")
            lines.append(f"  • {name} — سطح {op.level} | 👥{subs:,} | {status}")
    else:
        lines.append("  (هیچ حرفه‌ای در اسلات نیست)")

    up_cost = estate_upgrade_cost(estate.level) if estate.level < ESTATE_MAX_LEVEL else None
    # Stage 27: theft-cooldown upgrade shown inside the Cupola estate menu
    is_cupola = estate.role_key == CUPOLA_KEY
    cd_level = cd_cost = None
    cd_minutes = None
    if is_cupola:
        from app.data import kapatolo as _kap

        lvl = int(getattr(player, "kapatolo_cd_level", 0) or 0)
        cd_minutes = _kap.cooldown_minutes(lvl)
        if lvl < _kap.KAPATOLO_COOLDOWN_MAX_LEVEL:
            cd_level = lvl + 1
            cd_cost = _kap.cooldown_upgrade_cost(lvl)
        lines.append("")
        lines.append(
            f"🕰️ زمانِ انتظارِ دزدی: <b>{cd_minutes:g}</b> دقیقه "
            f"(لِوِل {lvl}/{_kap.KAPATOLO_COOLDOWN_MAX_LEVEL})"
        )
    return "\n".join(lines), estate_menu(
        estate.id, len(active), pend, overdue, up_cost,
        is_cupola=is_cupola, cd_level=cd_level, cd_cost=cd_cost, cd_minutes=cd_minutes,
    )


# ---------- نقاط ورود ----------
@router.message(F.text.in_({BTN_ESTATE, WORD_ESTATE}))   # 🔄 مرحله ۲۱.۱ — تطبیقِ دقیق به‌جای contains
async def estate_button(message: Message):
    # 🆕 مرحله ۱۲: در گروه هم فعال است (مثلِ پایگاه).
    async with async_session() as session:
        player = await get_player(session, message.from_user.id)
        if player is None:
            await message.answer("❗ ابتدا /start را بزن تا ثبت‌نام شوی.")
            return
        text, markup = await render_hub(session, player)
    await message.answer(text, reply_markup=markup)


@router.callback_query(F.data.startswith("menu:estate"))
async def estate_menu_cb(callback: CallbackQuery):
    if not await ensure_owner(callback):
        return
    # 🆕 مرحله ۱۲: در گروه هم باز می‌شود (پیام ادیت می‌شود).
    async with async_session() as session:
        player = await get_player(session, callback.from_user.id)
        if player is None:
            await safe_answer(callback, "❗ ابتدا /start را بزن.", show_alert=True)
            return
        text, markup = await render_hub(session, player)
    await _edit(callback, text, markup)
    await safe_answer(callback)


@router.callback_query(F.data == "estate:hub")
async def hub_cb(callback: CallbackQuery):
    async with async_session() as session:
        player = await get_player(session, callback.from_user.id)
        if player is None:
            await safe_answer(callback, "❗ ابتدا /start را بزن.", show_alert=True)
            return
        text, markup = await render_hub(session, player)
    await _edit(callback, text, markup)
    await safe_answer(callback)


@router.callback_query(F.data == "estate:build")
async def build_cb(callback: CallbackQuery):
    async with async_session() as session:
        player = await get_player(session, callback.from_user.id)
        if player is None:
            await safe_answer(callback, "❗ ابتدا /start را بزن.", show_alert=True)
            return
        text, markup = await render_build_list(session, player)
    await _edit(callback, text, markup)
    await safe_answer(callback)


@router.callback_query(F.data.startswith("estate:view:"))
async def view_cb(callback: CallbackQuery):
    estate_id = int(callback.data.split(":")[2])
    async with async_session() as session:
        player = await get_player(session, callback.from_user.id)
        estate = await get_estate(session, estate_id, callback.from_user.id)
        if player is None or estate is None:
            await safe_answer(callback, "عمارت پیدا نشد.", show_alert=True)
            return
        text, markup = await render_estate_detail(session, player, estate)
    await _edit(callback, text, markup)
    await safe_answer(callback)


# ---------- ساختِ عمارت (عمومی: هر کلیدِ هرم) ----------
@router.callback_query(F.data.startswith("estate:found:"))
async def found_estate(callback: CallbackQuery):
    key = callback.data.split(":")[2]
    role = get_estate_role(key)
    if role is None:
        await safe_answer(callback, "عمارت نامعتبر.", show_alert=True)
        return
    async with async_session() as session:
        player = await get_player(session, callback.from_user.id)
        if player is None:
            await safe_answer(callback, "❗ ابتدا /start را بزن.", show_alert=True)
            return

        estates = await get_all_estates(session, player.tg_user_id)
        built = {e.role_key for e in estates}
        if key in built:
            await safe_answer(callback, "این عمارت را از قبل داری!", show_alert=True)
            return
        if not is_estate_unlocked(key, built):
            miss = "، ".join(get_estate_role(p)["name"] for p in missing_prereqs(key, built))
            await safe_answer(callback, "⛔ اول این عمارت‌ها را بساز: " + miss, show_alert=True)
            return

        hideout = await get_hideout(session, player.tg_user_id)
        if not _villa_maxed(hideout, MAX_BASE_TYPE):
            await safe_answer(callback, 
                f"⛔ اول پایگاهِ {tier4_base_for_estate(key)} را با اقتدارِ مکس بساز.", show_alert=True
            )
            return
        # 🔄 مرحله ۲۶.۳: هر پایگاهِ تخصصی فقط پیش‌نیازِ ساختِ همان یک عمارت است
        variant = getattr(hideout, "final_variant", None)
        if variant and variant != key:
            target = get_estate_role(variant)
            target_name = target["name"] if target else variant
            await safe_answer(callback, 
                f"⛔ تو {tier4_base_for_estate(variant)} را ساختی؛ "
                f"با این پایگاه فقط می‌تونی «{target_name}» را بسازی.",
                show_alert=True,
            )
            return
        if player.level < REQUIRED_LEVEL:
            await safe_answer(callback, f"⛔ باید سطح {REQUIRED_LEVEL} باشی.", show_alert=True)
            return
        if player.cash < role["found_cost"]:
            await safe_answer(callback, f"💸 پول کافی نداری! هزینه: {role['found_cost']:,}$", show_alert=True)
            return

        player.cash -= role["found_cost"]
        await session.delete(hideout)  # پایگاهِ تخصصی مصرف می‌شود
        session.add(Estate(tg_user_id=player.tg_user_id, role_key=key, level=1))
        await session.commit()

        all_done_now = len(built | {key}) >= len(ESTATES)
        # Stage 27: XP + congratulation message for the new estate
        from app.data import leveling as _lv
        _xp_res = {}
        try:
            _xp_res = await _lv.grant_xp(session, player, 500 if all_done_now else 150, source="estate_found")
            await session.commit()
        except Exception:
            pass
        try:
            if callback.message is not None:
                await callback.message.answer(
                    ALL_ESTATES_DONE_MSG if all_done_now
                    else ESTATE_BUILT_MSG.format(name=role["name"])
                )
        except Exception:
            pass

        text, markup = await render_hub(session, player)
    await _edit(callback, text, markup)
    extra = " 🏆 تمام عمارت‌هات رو ساختی!" if all_done_now else ""
    await safe_answer(callback, f"🎉 {role['name']} ساخته شد!{extra}" + _lv.xp_note(_xp_res))


# ---------- ارتقای خودِ عمارت ----------
@router.callback_query(F.data.startswith("estate:upgrade:"))
async def upgrade_estate(callback: CallbackQuery):
    estate_id = int(callback.data.split(":")[2])
    # v1.7.8.19 - کلیک پیاپی فوراً رد می‌شود تا پنل هنگ نکند
    if click_debounce(callback.from_user.id, "estup:" + str(estate_id)):
        await safe_answer(callback, "⏳ در حالِ پردازش…")
        return
    async with async_session() as session:
        player = await get_player(session, callback.from_user.id)
        estate = await get_estate(session, estate_id, callback.from_user.id)
        if player is None or estate is None:
            await safe_answer(callback, "عمارت پیدا نشد.", show_alert=True)
            return
        if estate.level >= ESTATE_MAX_LEVEL:
            await safe_answer(callback, "این عمارت مکس است.", show_alert=True)
            return
        cost = estate_upgrade_cost(estate.level)
        if player.cash < cost:
            await safe_answer(callback, f"💸 پول کافی نداری! هزینه: {cost:,}$", show_alert=True)
            return
        player.cash -= cost
        estate.level += 1
        from app.data import leveling as _lv
        _xp_res = {}
        try:   # Stage 27: XP from estate upgrades
            _xp_res = await _lv.grant_xp(session, player, (40 + 20 * estate.level) // 2, source="estate_upgrade")
        except Exception:
            pass
        await session.commit()
        text, markup = await render_estate_detail(session, player, estate)
    await _edit(callback, text, markup)
    await safe_answer(callback, "🏗️ عمارت ارتقا یافت! نقشش قوی‌تر شد." + _lv.xp_note(_xp_res))


# ---------- استخدام (عمومی، ولی estate_id را برای بازگشت حمل می‌کند) ----------
@router.callback_query(F.data.startswith("estate:hire:"))
async def hire_open(callback: CallbackQuery):
    """🆕 مرحله ۲۸ — هر عمارت ۴ حرفه‌ی مخصوصِ خودش دارد؛ بدونِ گروه‌بندی و بدونِ اسلات."""
    estate_id = int(callback.data.split(":")[2])
    async with async_session() as session:
        estate = await get_estate(session, estate_id, callback.from_user.id)
        if estate is None:
            await safe_answer(callback, "عمارت پیدا نشد.", show_alert=True)
            return
        owned = await owned_pros(session, callback.from_user.id)
        active = await assigned_pros(session, estate.id)
    role = get_estate_role(estate.role_key)
    owned_keys = {op.prof_key for op in owned}
    lines = [
        f"👔 <b>استخدامِ حرفه‌ای‌های {role['name']}</b>",
        "",
        "هر عمارت ۴ حرفه‌ی مخصوصِ خودش دارد و هر حرفه‌ای پس از استخدام",
        "<b>خودکار</b> در همین عمارت مشغول می‌شود.",
        "",
        f"👥 حرفه‌ای‌های فعال: <b>{len(active)}/{SLOTS_PER_ESTATE}</b>",
    ]
    await _edit(
        callback,
        "\n".join(lines),
        estate_hire_menu(estate.role_key, estate_id, owned_keys, len(active)),
    )
    await safe_answer(callback)


@router.callback_query(F.data.startswith("hirecat:"))
async def hire_category(callback: CallbackQuery):
    _, group_key, estate_id = callback.data.split(":")
    async with async_session() as session:
        owned = await owned_pros(session, callback.from_user.id)
    owned_keys = {op.prof_key for op in owned}
    label = GROUPS.get(group_key, group_key)
    await _edit(
        callback,
        f"{label}\nحرفه‌ای موردنظرت را بخر (یک‌بار هزینه):",
        hire_group_menu(group_key, owned_keys, int(estate_id)),
    )
    await safe_answer(callback)


@router.callback_query(F.data == "hire_owned")
async def hire_owned(callback: CallbackQuery):
    await safe_answer(callback, "این حرفه‌ای را قبلاً خریده‌ای.", show_alert=True)


@router.callback_query(F.data.startswith("hire:"))
async def hire_do(callback: CallbackQuery):
    _, prof_key, estate_id = callback.data.split(":")
    estate_id = int(estate_id)
    info = get_professional(prof_key)
    if info is None:
        await safe_answer(callback, "حرفه‌ای نامعتبر.", show_alert=True)
        return
    async with async_session() as session:
        player = await get_player(session, callback.from_user.id)
        if player is None:
            await safe_answer(callback, "❗ ابتدا /start را بزن.", show_alert=True)
            return
        estate = await get_estate(session, estate_id, callback.from_user.id)
        if estate is None:
            await safe_answer(callback, "عمارت پیدا نشد.", show_alert=True)
            return
        estate_role_key = estate.role_key
        # 🆕 مرحله ۲۸ — هر حرفه فقط در عمارتِ خودش قابلِ استخدام است.
        if prof_key not in {k for k, _ in professionals_for_estate(estate_role_key)}:
            await safe_answer(callback, 
                "⛔ این حرفه مربوط به این عمارت نیست.", show_alert=True
            )
            return
        existing = await session.execute(
            select(OwnedProfessional).where(
                OwnedProfessional.tg_user_id == player.tg_user_id,
                OwnedProfessional.prof_key == prof_key,
            )
        )
        if existing.scalar_one_or_none() is not None:
            await safe_answer(callback, "قبلاً خریده‌ای.", show_alert=True)
            return
        if player.cash < info["base_price"]:
            await safe_answer(callback, f"💸 پول کافی نداری! قیمت: {info['base_price']:,}$", show_alert=True)
            return
        player.cash -= info["base_price"]
        from app.data import leveling as _lv
        _xp_res = {}
        try:   # Stage 27: XP from hiring professionals
            _xp_res = await _lv.grant_xp(session, player, max(5, info["base_price"] // 1000), source="hire_professional")
        except Exception:
            pass
        # 🆕 مرحله ۲۸ — حرفه‌ای مستقیماً در همین عمارت مشغول می‌شود (بدونِ مرحله‌ی اسلات).
        active_now = await assigned_pros(session, estate_id)
        auto_assign = estate_id if len(active_now) < SLOTS_PER_ESTATE else None
        session.add(OwnedProfessional(
            tg_user_id=player.tg_user_id, prof_key=prof_key, level=1,
            subordinates=subordinates_for_level(1),
            assigned_estate_id=auto_assign,
            last_paid=datetime.utcnow(),
        ))
        await session.commit()
        owned = await owned_pros(session, player.tg_user_id)
        cash_now = player.cash
    owned_keys = {op.prof_key for op in owned}
    note = (
        "👥 و خودکار در همین عمارت مشغول شد." if auto_assign
        else f"⚠️ هر {SLOTS_PER_ESTATE} جایگاهِ این عمارت پُر بود، پس فعلاً رزرو ماند."
    )
    await _edit(
        callback,
        f"✅ «{info['name']}» استخدام شد!\n{note}\n💵 موجودی: {cash_now:,}$",
        estate_hire_menu(estate_role_key, estate_id, owned_keys),
    )
    await safe_answer(callback, "🎉 استخدام شد")


# ---------- اسلات‌ها (مخصوصِ یک عمارت) ----------
@router.callback_query(F.data.startswith("estate:slots:"))
async def slots_open(callback: CallbackQuery):
    # 🗑 مرحله ۲۸: بخشِ «چیدن در اسلات» حذف شد؛ استخدام خودش حرفه را مشغول می‌کند.
    await safe_answer(callback, 
        "ℹ️ دیگر لازم نیست! حرفه‌ای پس از استخدام خودکار در همان عمارت مشغول می‌شود.",
        show_alert=True,
    )
    return


async def _legacy_slots_open(callback: CallbackQuery):
    estate_id = int(callback.data.split(":")[2])
    async with async_session() as session:
        estate = await get_estate(session, estate_id, callback.from_user.id)
        if estate is None:
            await safe_answer(callback, "عمارت پیدا نشد.", show_alert=True)
            return
        owned = await owned_pros(session, callback.from_user.id)
    if not owned:
        await safe_answer(callback, "هنوز حرفه‌ای نخریده‌ای. اول استخدام کن.", show_alert=True)
        return
    active = [op for op in owned if op.assigned_estate_id == estate.id]
    role = get_estate_role(estate.role_key)
    await _edit(
        callback,
        f"🎯 <b>اسلات‌های {role['name']}</b> ({len(active)}/{SLOTS_PER_ESTATE})\n➕ گذاشتن، ➖ برداشتن:",
        assign_menu(owned, estate.id),
    )
    await safe_answer(callback)


@router.callback_query(F.data == "assign_busy")
async def assign_busy(callback: CallbackQuery):
    await safe_answer(callback, "این حرفه‌ای در عمارتِ دیگری فعال است. اول از آنجا برش دار.", show_alert=True)


@router.callback_query(F.data.startswith("assign:"))
async def assign_do(callback: CallbackQuery):
    _, op_id, estate_id = callback.data.split(":")
    op_id = int(op_id)
    estate_id = int(estate_id)
    async with async_session() as session:
        estate = await get_estate(session, estate_id, callback.from_user.id)
        if estate is None:
            await safe_answer(callback, "عمارت پیدا نشد.", show_alert=True)
            return
        active = await assigned_pros(session, estate.id)
        if len(active) >= SLOTS_PER_ESTATE:
            await safe_answer(callback, f"همه‌ی {SLOTS_PER_ESTATE} اسلات پُر است!", show_alert=True)
            return
        op = await session.get(OwnedProfessional, op_id)
        if op is None or op.tg_user_id != callback.from_user.id:
            await safe_answer(callback, "نامعتبر.", show_alert=True)
            return
        if op.assigned_estate_id is not None:
            await safe_answer(callback, "این حرفه‌ای در عمارتِ دیگری فعال است.", show_alert=True)
            return
        op.assigned_estate_id = estate.id
        op.last_paid = datetime.utcnow()
        await session.commit()
        owned = await owned_pros(session, callback.from_user.id)
    await _edit(callback, "✅ در اسلات گذاشته شد.", assign_menu(owned, estate_id))
    await safe_answer(callback, "گذاشته شد")


@router.callback_query(F.data.startswith("unassign:"))
async def unassign_do(callback: CallbackQuery):
    _, op_id, estate_id = callback.data.split(":")
    op_id = int(op_id)
    estate_id = int(estate_id)
    async with async_session() as session:
        estate = await get_estate(session, estate_id, callback.from_user.id)
        if estate is None:
            await safe_answer(callback, "نامعتبر.", show_alert=True)
            return
        op = await session.get(OwnedProfessional, op_id)
        if op is None or op.tg_user_id != callback.from_user.id:
            await safe_answer(callback, "نامعتبر.", show_alert=True)
            return
        op.assigned_estate_id = None
        await session.commit()
        owned = await owned_pros(session, callback.from_user.id)
    await _edit(callback, "➖ از اسلات برداشته شد.", assign_menu(owned, estate_id))
    await safe_answer(callback, "برداشته شد")


# ---------- برداشتِ درآمد (مخصوصِ یک عمارت، با ضریبِ امپراتوری) ----------
@router.callback_query(F.data.startswith("estate:collect:"))
async def collect_income(callback: CallbackQuery):
    estate_id = int(callback.data.split(":")[2])
    async with async_session() as session:
        player = await get_player(session, callback.from_user.id)
        estate = await get_estate(session, estate_id, callback.from_user.id)
        if player is None or estate is None:
            await safe_answer(callback, "عمارت پیدا نشد.", show_alert=True)
            return
        totals = await empire_totals(session, player.tg_user_id)
        mult = income_multiplier(totals)
        amount = await pending_income(session, estate, mult)
        if amount <= 0:
            await safe_answer(callback, "💰 فعلاً درآمدِ آماده‌ای نیست.", show_alert=True)
            return
        from app.services.bonus_breakdown import income_breakdown, append_note
        br = await income_breakdown(session, player.tg_user_id, int(amount))
        amount = int(br["total"])
        player.cash += amount
        estate.last_collected_at = datetime.utcnow()
        await session.commit()
        text, markup = await render_estate_detail(session, player, estate)
    await _edit(callback, text, markup)
    await safe_answer(callback, append_note(f"💰 {amount:,}$ برداشت شد! (با ضریبِ امپراتوری)", br.get("note") or ""), show_alert=True)


# ---------- ارتقای حرفه‌ای‌ها ----------
# ---------- Stage 27: batch operations across the whole empire ----------
@router.callback_query(F.data == "estate:collectall")
async def collect_all_income(callback: CallbackQuery):
    async with async_session() as session:
        player = await get_player(session, callback.from_user.id)
        if player is None:
            await safe_answer(callback, "اول /start را بزن.", show_alert=True)
            return
        estates = await get_all_estates(session, player.tg_user_id)
        totals = await empire_totals(session, player.tg_user_id)
        mult = income_multiplier(totals)
        now = datetime.utcnow()
        base_total = 0
        for e in estates:
            amount = await pending_income(session, e, mult)
            if amount <= 0:
                continue
            base_total += int(amount)
            e.last_collected_at = now
        if base_total <= 0:
            await safe_answer(callback, "💰 فعلاً درآمدِ آماده‌ای نیست.", show_alert=True)
            return
        from app.services.bonus_breakdown import income_breakdown, append_note
        br = await income_breakdown(session, player.tg_user_id, int(base_total))
        total = int(br["total"])
        player.cash += total
        from app.data import leveling as _lv
        _xp_res = {}
        try:
            _xp_res = await _lv.grant_xp(session, player, min(200, max(5, total // 100_000)), source="estate_collect_all")
        except Exception:
            pass
        await session.commit()
        text, markup = await render_hub(session, player)
    await _edit(callback, text, markup)
    await safe_answer(callback, append_note(f"💰 {total:,}$ از همه‌ی عمارت‌ها جمع‌آوری شد!" + _lv.xp_note(_xp_res), br.get("note") or ""), show_alert=True)


@router.callback_query(F.data == "estate:payall")
async def pay_all_salaries(callback: CallbackQuery):
    now = datetime.utcnow()
    async with async_session() as session:
        player = await get_player(session, callback.from_user.id)
        if player is None:
            await safe_answer(callback, "اول /start را بزن.", show_alert=True)
            return
        estates = await get_all_estates(session, player.tg_user_id)
        due_ops = []
        total = 0
        any_pro = False
        for e in estates:
            for op in await assigned_pros(session, e.id):
                any_pro = True
                # 🐞 مرحله ۶۹ — باگِ اصلی اینجا بود: خروجی تابع
                # (مبلغ، روزهای تأخیر، اعتصاب) است، ولی کد مقدارِ دوم (روزهای تأخیر)
                # را به‌عنوانِ مبلغ جمع می‌کرد. چون تأخیر معمولاً ۰ است، جمع همیشه ۰
                # می‌شد و پیامِ «تسویه است» نشان داده می‌شد.
                amount, _late, _strike = salary_due_for(op, now)
                if amount > 0:
                    due_ops.append(op)
                    total += amount
        if total <= 0:
            msg = (
                "✅ حرفه‌ایِ فعالی نداری که حقوق بخواهد."
                if not any_pro
                else "✅ همین الان تسویه کردی — حقوق لحظه‌به‌لحظه جمع می‌شود، کمی بعد دوباره سر بزن."
            )
            await safe_answer(callback, msg, show_alert=True)
            return
        if player.cash < total:
            await safe_answer(callback, 
                f"💸 پول کافی نداری! لازم: {total:,}$", show_alert=True
            )
            return
        player.cash -= total
        for op in due_ops:
            op.last_paid = now
        await session.commit()
        # 🐞 مرحله ۶۷ — بعد از commit دوباره می‌خوانیم تا داشبورد با مقادیرِ تازه ساخته شود.
        player = await get_player(session, callback.from_user.id) or player
        text, markup = await render_hub(session, player)
    await _edit(callback, text, markup)
    await safe_answer(callback, 
        f"✅ حقوقِ {len(due_ops)} حرفه‌ای پرداخت شد — {total:,}$"
    )


@router.callback_query(F.data.startswith("estate:promote:"))
async def promote_open(callback: CallbackQuery):
    estate_id = int(callback.data.split(":")[2])
    async with async_session() as session:
        estate = await get_estate(session, estate_id, callback.from_user.id)
        if estate is None:
            await safe_answer(callback, "عمارت پیدا نشد.", show_alert=True)
            return
        active = await assigned_pros(session, estate.id)
    if not active:
        await safe_answer(callback, "اول در اسلات‌ها حرفه‌ای بگذار.", show_alert=True)
        return
    await _edit(callback, "⬆️ <b>ارتقای حرفه‌ای‌ها</b>\nهر سطح = زیردستانِ بیشتر = درآمدِ بیشتر:", promote_menu(active, estate.id))
    await safe_answer(callback)


@router.callback_query(F.data == "promote_max")
async def promote_max(callback: CallbackQuery):
    await safe_answer(callback, "این حرفه‌ای به سطحِ مکس رسیده.", show_alert=True)


@router.callback_query(F.data.startswith("promote:"))
async def promote_do(callback: CallbackQuery):
    _, op_id, estate_id = callback.data.split(":")
    op_id = int(op_id)
    estate_id = int(estate_id)
    async with async_session() as session:
        player = await get_player(session, callback.from_user.id)
        op = await session.get(OwnedProfessional, op_id)
        if player is None or op is None or op.tg_user_id != callback.from_user.id:
            await safe_answer(callback, "نامعتبر.", show_alert=True)
            return
        if op.level >= MAX_PROF_LEVEL:
            await safe_answer(callback, "به سطحِ مکس رسیده.", show_alert=True)
            return
        cost = promote_cost(op.level)
        if player.cash < cost:
            await safe_answer(callback, f"💸 پول کافی نداری! هزینه: {cost:,}$", show_alert=True)
            return
        player.cash -= cost
        op.level += 1
        op.subordinates = subordinates_for_level(op.level)
        await session.commit()
        estate = await get_estate(session, estate_id, callback.from_user.id)
        active = await assigned_pros(session, estate.id)
    await _edit(callback, "⬆️ ارتقا انجام شد!", promote_menu(active, estate_id))
    await safe_answer(callback, "⬆️ سطح بالا رفت")


# ---------- پرداختِ حقوق ----------
@router.callback_query(F.data.startswith("estate:salary:"))
async def salary_open(callback: CallbackQuery):
    estate_id = int(callback.data.split(":")[2])
    now = datetime.utcnow()
    async with async_session() as session:
        estate = await get_estate(session, estate_id, callback.from_user.id)
        if estate is None:
            await safe_answer(callback, "عمارت پیدا نشد.", show_alert=True)
            return
        active = await assigned_pros(session, estate.id)
    rows = []
    for op in active:
        amount, late, strike = salary_due_for(op, now)
        rows.append((op, amount, late, strike))
    if not rows:
        await safe_answer(callback, "حرفه‌ای فعالی نداری.", show_alert=True)
        return
    body = salary_text(rows)
    if not any(amount > 0 for _op, amount, _late, _st in rows):
        body += "\n\n✅ همین الان تسویه کردی — حقوق لحظه‌به‌لحظه جمع می‌شود."
    await _edit(callback, body, salary_menu(rows, estate_id))
    await safe_answer(callback)


@router.callback_query(F.data == "sal_ok")
async def salary_ok(callback: CallbackQuery):
    await safe_answer(callback, "حقوقِ این حرفه‌ای به‌روز است.", show_alert=True)


@router.callback_query(F.data.startswith("paysal:"))
async def pay_salary(callback: CallbackQuery):
    _, target, estate_id = callback.data.split(":")
    estate_id = int(estate_id)
    now = datetime.utcnow()
    async with async_session() as session:
        player = await get_player(session, callback.from_user.id)
        estate = await get_estate(session, estate_id, callback.from_user.id)
        if player is None or estate is None:
            await safe_answer(callback, "نامعتبر.", show_alert=True)
            return
        active = await assigned_pros(session, estate.id)
        if target == "all":
            targets = active
        else:
            targets = [op for op in active if op.id == int(target)]
        total = 0
        for op in targets:
            # 🐞 مرحله ۶۹ — همانِ باگِ جابه‌جاییِ خروجی که جمع را همیشه ۰ می‌کرد.
            amount, _late, _strike = salary_due_for(op, now)
            if amount <= 0:
                continue
            total += amount
        if total <= 0:
            msg = (
                "حرفه‌ایِ فعالی نداری."
                if not targets
                else "✅ همین الان تسویه کردی — حقوق لحظه‌به‌لحظه جمع می‌شود، کمی بعد دوباره سر بزن."
            )
            await safe_answer(callback, msg, show_alert=True)
            return
        if player.cash < total:
            await safe_answer(callback, f"💸 پول کافی نداری! لازم: {total:,}$", show_alert=True)
            return
        player.cash -= total
        for op in targets:
            amount, _late, _strike = salary_due_for(op, now)
            if amount <= 0:
                continue
            op.last_paid = now
        await session.commit()
        active = await assigned_pros(session, estate.id)
    rows = [(op, *salary_due_for(op, now)) for op in active]
    await _edit(callback, salary_text(rows), salary_menu(rows, estate_id))
    await safe_answer(callback, f"✅ {total:,}$ حقوق پرداخت شد")