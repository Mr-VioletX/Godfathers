# -*- coding: utf-8 -*-
# هندلرِ دزدی — بازطراحیِ مرحله ۱۵.۵ (XP مرکزی) + مرحله ۱۶ (زندان/خستگی/کلماتِ کلیدی)
import random
from datetime import datetime, timedelta

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select

from app.database.engine import async_session
from app.models.player import Player
from app.models.hideout import get_hideout
from app.models.estate import Estate
from app.models.player_stats import get_or_create_stats
from app.utils.ui import ensure_owner, safe_edit, split_owner, with_owner
from app.keyboards.theft_menu import after_theft_menu, theft_menu

from app.data import events, leveling, kapatolo
from app.data.thefts import (
    THEFTS, available_thefts, get_theft, theft_by_keyword, compute_risk,
    MAX_FATIGUE, FATIGUE_PEAK, FATIGUE_RECOVERY_PER_MIN,
    JAIL_SECONDS, BRIBE_LIMIT, bribe_for_remaining,
)
from app.data.upgrades import (
    SECURITY_RISK_REDUCTION,
    SAFEHOUSE_RECOVERY_BONUS,
    VAULT_REWARD_BONUS,
    AUTHORITY_RISK_REDUCTION,
    AUTHORITY_RECOVERY_BONUS,
    AUTHORITY_REWARD_BONUS,
)
from app.data.estates import CUPOLA_KEY, CUPOLA_PERKS
from app.data.sports import event_theft_risk

router = Router()

THEFT_ONLY_GROUP = "🕵️ دزدی فقط داخلِ گروه انجام می‌شود."


def _fmt_mmss(seconds) -> str:
    seconds = max(0, int(seconds))
    return f"{seconds // 60}:{seconds % 60:02d}"


def _jail_remaining(player, now: datetime) -> int:
    if not player.jail_until:
        return 0
    return max(0, int((player.jail_until - now).total_seconds()))


def _jail_keyboard(owner_id: int, can_pay: bool, bribe_amount: int = 0):
    b = InlineKeyboardBuilder()
    if can_pay:
        b.button(
            text=f"💵 پرداختِ باج ({bribe_amount:,}$)",
            callback_data=with_owner("theft:bribe", owner_id),
        )
    b.button(text="↩️ بازگشت به منو", callback_data=with_owner("menu:main", owner_id))
    b.adjust(1)
    return b.as_markup()


async def _defense_bonuses(session, user_id: int):
    """جمعِ اثرِ پایگاه/عمارت: (کاهشِ ریسک، بازیابی، پاداش)."""
    hideout = await get_hideout(session, user_id)
    sec_level = hideout.security_level if hideout else 0
    safe_level = hideout.safehouse_level if hideout else 0
    vault_level = hideout.vault_level if hideout else 0
    auth_level = hideout.authority_level if hideout else 0

    risk_reduction = sec_level * SECURITY_RISK_REDUCTION + auth_level * AUTHORITY_RISK_REDUCTION
    recovery_bonus = safe_level * SAFEHOUSE_RECOVERY_BONUS + auth_level * AUTHORITY_RECOVERY_BONUS
    reward_bonus = vault_level * VAULT_REWARD_BONUS + auth_level * AUTHORITY_REWARD_BONUS

    cupola = await session.execute(
        select(Estate).where(Estate.tg_user_id == user_id, Estate.role_key == CUPOLA_KEY)
    )
    if cupola.scalar_one_or_none() is not None:
        risk_reduction += CUPOLA_PERKS["sec_bonus"]
        reward_bonus += CUPOLA_PERKS["vault_bonus"]
        recovery_bonus += CUPOLA_PERKS["recovery_bonus"]

    return risk_reduction, recovery_bonus, reward_bonus


async def refresh_fatigue(session, player, recovery_rate: float, commit: bool = True) -> int:
    """🆕 مرحله ۳۰ — ریکاوریِ خستگی را دقیقاً همان لحظه‌ی نمایش هم اعمال می‌کند.

    قبلاً کاهشِ خستگی فقط درونِ do_theft حساب می‌شد، پس عددِ خستگی در پنلِ
    دزدی ثابت دیده می‌شد. حالا هر بار که پنل باز/رفرش می‌شود، عددِ واقعی ذخیره و نشان داده می‌شود.
    """
    fatigue = int(player.fatigue or 0)
    if fatigue > 0 and player.last_theft_at is not None:
        elapsed_min = (datetime.utcnow() - player.last_theft_at).total_seconds() / 60
        recovered = int(elapsed_min * max(1, float(recovery_rate or 1)))
        if recovered > 0:
            fatigue = max(0, fatigue - recovered)
    # 🐞 رفعِ باگ (مرحله ۳۱.۱): این تابع دیگر last_theft_at/fatigue را در دیتابیس دست‌کاری نمی‌کند
    # (قبلاً همان last_theft_at که مبنای کول‌داونِ واقعی بود را هم جلو می‌برد، همین باعثِ
    # ری‌استارتِ کول‌داون و نمایشِ نادرستِ خستگی با هر بار بازکردنِ پنلِ دزدی می‌شد).
    # فقط عددِ خستگیِ به‌روزشده برای نمایش برمی‌گردد؛ کاهشِ واقعی و ذخیره‌سازی فقط
    # درونِ do_theft انجام می‌شود.
    return fatigue


def _cooldown_remaining(player) -> int:
    """ثانیه‌هایِ باقی‌مانده تا دزدیِ بعدی."""
    if player.last_theft_at is None:
        return 0
    cd = kapatolo.cooldown_seconds(player.kapatolo_cd_level)
    elapsed = (datetime.utcnow() - player.last_theft_at).total_seconds()
    return max(0, int(cd - elapsed))


async def arrest_enabled(session) -> bool:
    """🆕 مرحله ۶۷ — کلیدِ سراسری‌ِ دستگیری (قابل تغییر از ادمین‌مود).

    پیش‌فرض روشن است؛ فقط وقتی صریحاً ۰ ذخیره شده باشد خاموش می‌شود.
    """
    try:
        from app.models.admin import GameNumberSetting

        row = await session.get(GameNumberSetting, "theft.arrest_enabled")
    except Exception:
        return True
    if row is None or row.value is None:
        return True
    return str(row.value).strip().lower() not in ("0", "false", "off", "no")


async def build_theft_panel(session, player) -> str:
    """متنِ پنلِ دزدی: درصدِ دستگیریِ شخصی‌شده + بازهٔ درآمدِ هر دزدی."""
    risk_reduction, recovery_bonus, _ = await _defense_bonuses(session, player.tg_user_id)
    recovery_rate = FATIGUE_RECOVERY_PER_MIN + recovery_bonus
    # 🆕 مرحله ۳۰ — خستگی قبل از ساختِ متن به‌روز می‌شود
    fatigue_now = await refresh_fatigue(session, player, recovery_rate)  # 🐞 رفعِ باگ: مقدارِ برگشتی برای نمایش استفاده می‌شود
    lines = [
        "🕵️ <b>کدام دزدی؟</b>",
        "درصدِ کنارِ هر مورد، احتمالِ دستگیریِ خودِ توست (با توجه به سطح، خستگی و پایگاه):",
        "",
    ]
    # v1.7.6.6 — بونس واقعی برای نمایش بازه (پایگاه/لقب/اونت)
    _, _, reward_bonus_ui = await _defense_bonuses(session, player.tg_user_id)
    try:
        from app.services import event_service as _evs
        await _evs.refresh_if_stale(force=True)
    except Exception:
        pass
    try:
        from app.services import title_effects as _te
        title_mult_ui = float(await _te.multiplier(session, player.tg_user_id, "income_pct") or 1.0)
    except Exception:
        title_mult_ui = 1.0
    sub_pct_ui = 0
    try:
        from app.services import subscription_service as _subs
        sub_pct_ui = int(await _subs.income_bonus_pct(session, player.tg_user_id) or 0)
    except Exception:
        sub_pct_ui = 0
    sub_mult_ui = 1.0 + (sub_pct_ui / 100.0)
    event_mult_ui = float(events.BONUS.money_multiplier() or 1.0)
    total_mult = (1.0 + float(reward_bonus_ui or 0)) * max(1.0, title_mult_ui) * sub_mult_ui * max(1.0, event_mult_ui)

    for t in available_thefts(player.level):
        risk = compute_risk(t, player.level, fatigue_now, risk_reduction)
        risk = min(0.95, max(0.02, event_theft_risk(risk, datetime.utcnow())))
        lo = int(t["min_reward"] * total_mult)
        hi = int(t["max_reward"] * total_mult)
        lines.append(
            f"• {t['name']} — 💰 {lo:,}~{hi:,}$ | 🚨 ریسک: {risk:.0%}"
        )
    if total_mult > 1.001:
        bits = []
        if reward_bonus_ui > 0:
            bits.append(f"پایگاه/عمارت +{reward_bonus_ui*100:.0f}٪")
        if title_mult_ui > 1.001:
            bits.append(f"لقب ×{title_mult_ui:.2f}")
        if sub_pct_ui > 0:
            bits.append(f"اشتراک +{sub_pct_ui}٪")
        if event_mult_ui > 1.001:
            bits.append(f"اونت ×{event_mult_ui:g}")
        lines.append(
            "📈 بازه با بونس فعال (" + " | ".join(bits) + f") — ضریب کل ×{total_mult:.2f}"
        )
    else:
        lines.append("📈 بونس اضافه روی غنیمت نداری — بازه همان مقدار پایه است.")

    clear_min = -(-fatigue_now // max(1, int(recovery_rate)))
    lines += [
        "",
        f"😴 خستگی: <b>{fatigue_now}</b>/{MAX_FATIGUE}"
        + (f" (رفعِ کامل ~{clear_min} دقیقه)" if fatigue_now else " — کاملاً سرحالی ✅"),
        f"♻️ بازیابی: <b>{recovery_rate:g}</b> واحد در هر دقیقه",
    ]
    remaining = _cooldown_remaining(player)
    if remaining > 0:
        lines.append(f"⏳ تا دزدیِ بعدی: <b>{kapatolo.fmt_mmss(remaining)}</b>")
    else:
        lines.append("✅ آماده‌ی دزدیِ بعدی هستی.")
    if not await arrest_enabled(session):
        lines.append("🟢 <b>دستگیری توسطِ ادمین غیرفعال شده است</b> — فعلاً زندانی نمی‌شوی.")
    lines.append("💡 می‌توانی نامِ دزدی را هم بنویسی (مثلاً «جیب بری»).")
    return "\n".join(lines)


# هسته‌ی منطق دزدی — خروجی: (متن، کیبورد)
async def do_theft(user_id: int, theft_key: str):
    async with async_session() as session:
        player = await session.scalar(select(Player).where(Player.tg_user_id == user_id))
        if player is None:
            return "❗ ابتدا در چت خصوصی ربات /start را بزن تا ثبت‌نام شوی.", after_theft_menu(user_id)

        theft = get_theft(theft_key)
        if theft is None or player.level < theft["min_level"]:
            return "🔒 این نوع دزدی هنوز برای سطحِ تو باز نشده است.", after_theft_menu(user_id)

        stats = await get_or_create_stats(session, user_id)
        now = datetime.utcnow()

        # ۰) اگر زندانی است
        rem = _jail_remaining(player, now)
        if rem > 0:
            can_pay = not player.jail_forced
            bribe = bribe_for_remaining(player.level, rem) if can_pay else 0
            text = (
                f"🚔 <b>تو در زندانی!</b>\n"
                f"⏳ زمانِ باقی‌مانده: <b>{_fmt_mmss(rem)}</b>\n\n"
            )
            if can_pay:
                text += f"می‌توانی با پرداختِ باج (<b>{bribe:,}$</b>) آزاد شوی، یا صبر کنی تا آزاد شوی."
            else:
                text += "⛓️ این بازداشت <b>اجباری</b> است؛ پرداختِ باج ممکن نیست. باید تحمل کنی."
            return text, _jail_keyboard(user_id, can_pay, bribe)

        # اگر زمانِ زندان تمام شده → آزادی + صفر شدنِ شمارندهٔ باج
        if player.jail_until and rem == 0:
            player.jail_until = None
            player.jail_forced = False
            player.bribe_count = 0

        # ۱) ریکاوریِ خستگی بر اساسِ زمانِ گذشته
        risk_reduction, recovery_bonus, reward_bonus = await _defense_bonuses(session, user_id)
        recovery_rate = FATIGUE_RECOVERY_PER_MIN + recovery_bonus
        elapsed = None
        if player.last_theft_at is not None:
            elapsed = (now - player.last_theft_at).total_seconds()
            recovered = int((elapsed / 60) * recovery_rate)
            if recovered:
                player.fatigue = max(0, player.fatigue - recovered)

        # ۲) کول‌داون (از بخشِ کاپولا)
        cd = kapatolo.cooldown_seconds(player.kapatolo_cd_level)
        if elapsed is not None and elapsed < cd:
            remaining = int(cd - elapsed)
            await session.commit()
            return (
                f"⏳ هنوز زود است! برای دزدیِ بعدی <b>{_fmt_mmss(remaining)}</b> دیگر صبر کن.",
                after_theft_menu(user_id),
            )

        # ۳) خستگیِ اوج → دزدی ممکن نیست
        if player.fatigue >= FATIGUE_PEAK:
            need_min = -(-(player.fatigue - (FATIGUE_PEAK - 1)) // max(1, int(recovery_rate)))
            await session.commit()
            return (
                f"😵 <b>در اوجِ خستگی‌ای!</b> (<b>{player.fatigue}</b>/{MAX_FATIGUE})\n"
                f"تا دزدیِ دوباره دست‌کم <b>{max(1, need_min)}</b> دقیقه استراحت کن.",
                after_theft_menu(user_id),
            )

        # ۴) احتمال دستگیری (شخصی‌شده + اثرِ ایونت)
        arrest_p = compute_risk(theft, player.level, player.fatigue, risk_reduction)
        arrest_p = event_theft_risk(arrest_p, now)
        arrest_p = min(0.95, max(0.02, arrest_p))

        # ۵) ثبتِ زمان و خستگی
        player.last_theft_at = now
        player.fatigue = min(MAX_FATIGUE, player.fatigue + theft["fatigue"])

        # ۶) تاس — 🆕 مرحله ۶۷: اگر ادمین دستگیری را خاموش کرده باشد، تاس ریخته نمی‌شود.
        if not await arrest_enabled(session):
            arrest_p = 0.0
        if arrest_p > 0 and random.random() < arrest_p:
            forced = player.bribe_count >= BRIBE_LIMIT
            player.jail_until = now + timedelta(seconds=JAIL_SECONDS)
            player.jail_forced = forced
            stats.thefts_caught += 1
            stats.times_jailed += 1
            await session.commit()
            can_pay = not forced
            bribe = bribe_for_remaining(player.level, JAIL_SECONDS) if can_pay else 0
            text = (
                f"🚔 <b>دستگیر شدی!</b>\n"
                f"در حینِ «{theft['name']}» پلیس گرفتت و راهیِ زندان شدی.\n\n"
                f"⏳ مدتِ زندان: <b>{kapatolo.fmt_mmss(JAIL_SECONDS)}</b>\n"
                f"😴 خستگی: <b>{player.fatigue}</b>\n"
                f"<i>احتمالِ دستگیریِ این دزدی: {arrest_p:.0%}</i>\n\n"
            )
            if can_pay:
                text += (
                    f"💵 می‌توانی با پرداختِ باج (<b>{bribe:,}$</b>) فوری آزاد شوی — هرچه دیرتر، ارزان‌تر.\n"
                    f"یا صبر کنی تا آزاد شوی (با تحمل، شمارندهٔ باج صفر می‌شود)."
                )
            else:
                text += "⛓️ به سقفِ باج رسیده بودی؛ این بار زندانِ <b>اجباری</b> است و باید تحمل کنی."
            return text, _jail_keyboard(user_id, can_pay, bribe)

        # موفقیت — v1.7.6.6 رفرش اونت + شفاف‌سازی غنیمت
        try:
            from app.services import event_service as _evs
            await _evs.refresh_if_stale(force=True)
        except Exception:
            pass
        base_reward = random.randint(theft["min_reward"], theft["max_reward"])
        after_base = int(base_reward * (1 + reward_bonus))
        title_mult = 1.0
        try:
            from app.services import title_effects
            title_mult = float(await title_effects.multiplier(session, user_id, "income_pct") or 1.0)
        except Exception:
            title_mult = 1.0
        after_title = int(after_base * title_mult)
        # v1.7.6.8 — بونس درآمد اشتراک روی غنیمت دزدی
        sub_pct = 0
        try:
            from app.services import subscription_service as _subs
            sub_pct = int(await _subs.income_bonus_pct(session, user_id) or 0)
        except Exception:
            sub_pct = 0
        after_sub = int(round(after_title * (100 + sub_pct) / 100)) if sub_pct else after_title
        event_mult = float(events.BONUS.money_multiplier() or 1.0)
        reward = int(events.apply_money(after_sub))
        player.cash += reward
        res = leveling.add_xp(player, theft["xp"], stats=stats, source="theft")
        stats.thefts_done += 1
        stats.total_loot += reward
        await session.commit()

        detail = [
            f"💵 پایه قرعه: <b>{base_reward:,}$</b> (بازه {theft['min_reward']:,}~{theft['max_reward']:,})"
        ]
        if reward_bonus > 0:
            detail.append(
                f"🏛 پایگاه/عمارت (+{reward_bonus * 100:.0f}٪): <b>{after_base:,}$</b>"
            )
        if title_mult > 1.001:
            detail.append(
                f"🏷 بونس لقب (×{title_mult:.2f}): <b>{after_title:,}$</b>"
            )
        if sub_pct > 0:
            detail.append(
                f"💎 بونس اشتراک (+{sub_pct}٪): <b>{after_sub:,}$</b>"
            )
        if event_mult > 1.001:
            detail.append(
                f"✨ بونس اونت (×{event_mult:g}): <b>{reward:,}$</b>"
            )
        detail.append(f"✅ دریافتی نهایی: <b>{reward:,}$</b>")

        text = (
            f"🤑 <b>دزدی موفق!</b> ({theft['name']})\n\n"
            f"💰 غنیمت: <b>+{reward:,}</b> دلار\n"
            + "\n".join(detail)
            + "\n\n"
            + f"✨ تجربه: <b>+{theft['xp']}</b> XP  (⭐ {leveling.progress_str(player)})\n"
            f"😴 خستگی: <b>{player.fatigue}</b>/{MAX_FATIGUE} "
            f"(+{theft['fatigue']} این دزدی)\n"
            f"⏳ دزدیِ بعدی تا: <b>{kapatolo.fmt_mmss(cd)}</b> دیگر\n"
            f"💵 موجودی: <b>{player.cash:,}</b> دلار"
        )
        line = leveling.level_up_line(res)
        if line:
            text += "\n\n" + line
        return text, after_theft_menu(user_id)


# --- پرداختِ باج (قبل از هندلرِ عمومیِ theft: ثبت می‌شود) ---
@router.callback_query(F.data.startswith("theft:bribe"))
async def pay_bribe(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    uid = callback.from_user.id
    async with async_session() as session:
        player = await session.scalar(select(Player).where(Player.tg_user_id == uid))
        now = datetime.utcnow()
        rem = _jail_remaining(player, now) if player else 0
        if not player or rem <= 0:
            await callback.answer("تو در زندان نیستی.", show_alert=True)
            return
        if player.jail_forced:
            await callback.answer("⛓️ بازداشتِ اجباری؛ پرداخت ممکن نیست.", show_alert=True)
            return
        bribe = bribe_for_remaining(player.level, rem)
        if player.cash < bribe:
            await callback.answer(f"پولِ کافی نداری. باج: {bribe:,}$", show_alert=True)
            return
        player.cash -= bribe
        player.bribe_count += 1
        player.jail_until = None
        player.jail_forced = False
        stats = await get_or_create_stats(session, uid)
        stats.bribes_paid += 1
        near_limit = player.bribe_count >= BRIBE_LIMIT
        await session.commit()
        cash = player.cash
        bc = player.bribe_count
    warn = ""
    if near_limit:
        warn = "\n⚠️ به سقفِ باج رسیدی! دفعهٔ بعد که دستگیر شوی، زندانِ اجباری خواهی داشت."
    text = (
        f"💵 <b>باج پرداخت شد</b> ({bribe:,}$) و آزاد شدی!\n"
        f"💵 موجودی: <b>{cash:,}</b> دلار\n"
        f"🧾 تعدادِ باج‌ها: <b>{bc}</b>/{BRIBE_LIMIT}" + warn
    )
    await safe_edit(callback.message, text, after_theft_menu(uid))
    await callback.answer()


@router.callback_query(F.data.startswith("theft:"))
async def theft_callback(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    if callback.message.chat.type == "private":
        await callback.answer(THEFT_ONLY_GROUP, show_alert=True)
        return
    base, _ = split_owner(callback.data)   # "theft:pickpocket:123" → base="theft:pickpocket"
    theft_key = base.split(":")[1]
    text, markup = await do_theft(callback.from_user.id, theft_key)
    await safe_edit(callback.message, text, markup)
    await callback.answer()


# --- انجامِ دزدی با تایپِ کلمهٔ کلیدی (مثلاً «جیب بری») — فقط گروه ---
# 🆕 مرحله ۳۱ — فیلترِ async به‌جای lambda (رفعِ RuntimeError: can't start new thread)
async def _is_theft_word(message: Message) -> bool:
    return bool(message.text) and theft_by_keyword(message.text) is not None


@router.message(_is_theft_word)
async def theft_by_word(message: Message) -> None:
    if message.chat.type == "private":
        await message.reply(THEFT_ONLY_GROUP)
        return
    t = theft_by_keyword(message.text)
    text, markup = await do_theft(message.from_user.id, t["key"])
    await message.reply(text, reply_markup=markup)
