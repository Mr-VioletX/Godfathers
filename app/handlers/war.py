# -*- coding: utf-8 -*-
"""مرحله ۱۷ — جنگِ شخصی، سپر/حالتِ ایمن، تصرفِ شهر و تأسیسِ کشور.

همه‌ی عملیاتِ جنگ فقط داخلِ PVِ ربات انجام می‌شود.

منطقِ خالص (احتمالِ برد، درصدِ غنیمت/غرامت، رده‌ی کشور) در app/data/war.py است،
و محاسبه‌ی قدرتِ رزمی/درآمد/جمعیت در app/services/war_service.py.
"""
from datetime import datetime, timedelta

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import func, select

from app.data import war as W
from app.database.engine import async_session
from app.handlers.profile import get_player
from app.keyboards.war_menu import (
    attack_targets_menu,
    back_only_menu,
    confirm_attack_menu,
    battle_live_menu,
    war_back_menu,
    war_home_menu,
)
from app.models.contact import Contact
from app.models.player import Player
from app.models.live_battle import LiveBattle
from app.models.war import Battle, WarState
from app.services import alliance_service, battle_live, spy_service, war_service, military_service
from app.states import WarStates
from app.utils.ui import CANCEL_HINT, ensure_owner, handle_cancel_word, safe_show, split_owner, with_owner, safe_answer

router = Router(name="war")

WAR_ONLY_BOT = "⚔️ بخشِ جنگ فقط داخلِ خودِ ربات در دسترس است، نه در گروه."
COUNTRY_ONLY_BOT = "👑 تأسیسِ کشور فقط داخلِ خودِ ربات (چتِ خصوصی) امکان‌پذیر است، نه در گروه."
COUNTRY_RENAME_ONLY_BOT = "✏️ تغییرِ نامِ کشور فقط داخلِ خودِ ربات (چتِ خصوصی) امکان‌پذیر است، نه در گروه."

# 🆕 مرحله ۳۱ — شهرِ تصرفی هم یک شهرِ کامل می‌شود (ارتقا، مالیات، درآمد، فروش).
# جغرافیا به صورتِ قطعی و تکرارپذیر از روی کلیدِ شهر انتخاب می‌شود.
_CAPTURE_GEOS = ("plain", "coastal", "mountain", "desert", "island")


def _geo_for_key(key: str) -> str:
    return _CAPTURE_GEOS[sum(ord(ch) for ch in str(key)) % len(_CAPTURE_GEOS)]


def _is_private(chat_type: str) -> bool:
    return chat_type == "private"


async def _deny_group(callback: CallbackQuery) -> None:
    """🆕 مرحله ۲۸ — پیامِ «جنگ فقط در ربات» را با دکمه‌ی بازگشتِ سالم نشان می‌دهد."""
    builder = InlineKeyboardBuilder()
    builder.button(
        text="↩️ بازگشت به منو",
        callback_data=with_owner("menu:main", callback.from_user.id),
    )
    builder.adjust(1)
    await safe_show(
        callback.message,
        WAR_ONLY_BOT + "\n\n🤖 داخلِ خودِ ربات «⚡️ جنگ» را بزن تا پنلِ جنگ باز شود.",
        builder.as_markup(),
    )
    await safe_answer(callback)


# --------------------------- متن‌ها ---------------------------
async def _home_text(session, uid: int) -> str:
    power = await war_service.compute_combat_power(session, uid)
    st = await session.get(WarState, uid)
    lines = [
        "⚔️ <b>اتاقِ جنگ</b>",
        "",
        f"💥 قدرتِ رزمیِ شما: <b>{power:,}</b>",
    ]
    if war_service.is_shielded(st):
        lines.append(f"🛡️ شما زیرِ سپر هستید — {war_service.shield_days_left(st)} روز مصونیت.")
    cd = war_service.attack_cooldown_left_min(st)
    if cd:
        lines.append(f"⏳ کول‌داونِ حمله: {cd} دقیقه‌ی دیگر.")
    lines += [
        "",
        "• ⚔️ حمله به حریف — در صورتِ برد، غنیمت؛ در صورتِ باخت، غرامت.",
        "• 🏅 جنگِ رنکینگ: به رقبای هم‌رده حمله کن و در جدول بالا برو.",
        "• 📜 پیامِ گزارشِ نبرد را بستی؟ با «گزارشِ آخرین نبرد» برگردانش — مهاجم باشی یا مدافع.",
    ]
    return "\n".join(lines)


async def _show_home(message: Message, uid: int) -> None:
    async with async_session() as session:
        text = await _home_text(session, uid)
    await safe_show(message, text, war_home_menu(uid))


async def _bump_stats(session, uid: int, **deltas) -> None:
    """افزایشِ ایمنِ آمارِ بازیکن + ارزیابیِ القاب (در try/except)."""
    try:
        from app.models.title import PlayerStats
        from app.services.titles import evaluate_titles

        st = await session.get(PlayerStats, uid)
        if st is None:
            st = PlayerStats(tg_user_id=uid)
            session.add(st)
            await session.flush()
        for key, val in deltas.items():
            if hasattr(st, key):
                setattr(st, key, (getattr(st, key) or 0) + val)
        await evaluate_titles(session, uid)
    except Exception:
        pass


async def _damage_active_city(session, uid: int) -> None:
    """آسیبِ زیرساخت: کاهشِ رضایتِ شهرِ مهاجمِ باخته. 🆕 بچ ۴: شهرسازِ جدید."""
    try:
        from app.models.mafia_city import MafiaCity
        res = await session.execute(select(MafiaCity).where(MafiaCity.tg_user_id == uid))
        city = res.scalars().first()
        if city is not None and hasattr(city, "satisfaction"):
            city.satisfaction = max(0, int(city.satisfaction or 0) - W.INFRA_DAMAGE_SAT)
    except Exception:
        pass


# --------------------------- ورودی‌ها ---------------------------
@router.message(F.text.in_({"جنگ", "⚔️ جنگ"}))
async def summon_war(message: Message) -> None:
    if not _is_private(message.chat.type):
        await message.reply(WAR_ONLY_BOT)
        return
    async with async_session() as session:
        player = await get_player(session, message.from_user.id)
    if not player:
        await message.reply("اول در چتِ خصوصیِ ربات /start را بزن.")
        return
    if int(player.level or 1) < W.WAR_UNLOCK_LEVEL:
        await message.reply(f"🔒 بخشِ جنگ از سطحِ {W.WAR_UNLOCK_LEVEL} باز می‌شود.")
        return
    await _show_home(message, message.from_user.id)


@router.callback_query(F.data.startswith("menu:war") | F.data.startswith("war:hub"))
async def open_war(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    if not _is_private(callback.message.chat.type):
        await _deny_group(callback)
        return
    async with async_session() as session:
        player = await get_player(session, callback.from_user.id)
    if not player:
        await safe_answer(callback, "اول /start را بزن.", show_alert=True)
        return
    if int(player.level or 1) < W.WAR_UNLOCK_LEVEL:
        await safe_answer(callback, f"🔒 بخشِ جنگ از سطحِ {W.WAR_UNLOCK_LEVEL} باز می‌شود.", show_alert=True)
        return
    await _show_home(callback.message, callback.from_user.id)
    await safe_answer(callback)


# --------------------------- وضعیتِ جنگی ---------------------------
@router.callback_query(F.data.startswith("war:status"))
async def war_status(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    uid = callback.from_user.id
    async with async_session() as session:
        power = await war_service.compute_combat_power(session, uid)
        income = await war_service.daily_income(session, uid)
        pop = await war_service.total_population(session, uid)
        cities = await war_service.city_count_total(session, uid)
    lines = [
        "🛡️ <b>وضعیتِ جنگی</b>",
        "",
        f"💥 قدرتِ رزمی: <b>{power:,}</b>",
        f"💰 درآمدِ روزانه (تخمینی): {income:,}$",
        f"🏙️ شهر: {'دارد' if cities else 'ندارد'}",
        f"👥 جمعیتِ شهر: {pop:,}",
    ]
    await safe_show(callback.message, "\n".join(lines), war_back_menu(uid))
    await safe_answer(callback)


# --------------------------- حمله: انتخابِ هدف ---------------------------
@router.callback_query(F.data.startswith("war:attack"))
async def choose_target(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    uid = callback.from_user.id
    async with async_session() as session:
        st = await session.get(WarState, uid)
        cd = war_service.attack_cooldown_left_min(st)
        if cd:
            await safe_answer(callback, f"⏳ تا حمله‌ی بعدی {cd} دقیقه مانده.", show_alert=True)
            return
        contacts = (await session.execute(
            select(Contact).where(Contact.owner_id == uid).order_by(Contact.added_at.desc())
        )).scalars().all()
    await safe_show(
        callback.message,
        "🎯 <b>هدفِ حمله را انتخاب کن</b>\nاز مخاطبین انتخاب کن یا آیدی/یوزرنیم را دستی بفرست.",
        attack_targets_menu(contacts, uid),
    )
    await safe_answer(callback)


async def _preview_target(message: Message, attacker_id: int, target_id: int) -> None:
    async with async_session() as session:
        target = await get_player(session, target_id)
        if target is None:
            await safe_show(message, "❌ این کاربر هنوز در بازی نیست.", war_back_menu(attacker_id))
            return
        my_power = await war_service.compute_combat_power(session, attacker_id)
        enemy_power = await war_service.compute_combat_power(session, target_id)
        st = await session.get(WarState, target_id)
        shielded = war_service.is_shielded(st)
        allied = await alliance_service.same_alliance(session, attacker_id, target_id)
        pre = await battle_live.preview(session, attacker_id, target_id)
    if allied:
        await safe_show(message, "🤝 این بازیکن هم‌اتحادیه‌ی توست؛ نمی‌توانی به او حمله کنی.", war_back_menu(attacker_id))
        return
    if not W.attack_allowed(my_power, enemy_power):
        _floor = W.min_target_power(my_power)
        await safe_show(
            message,
            (
                "🚫 <b>هدف بسیار ضعیف‌تر از توست!</b>\n\n"
                f"💥 قدرتِ تو: {my_power:,}\n"
                f"🛡️ قدرتِ هدف: {enemy_power:,}\n"
                f"برای حمله، قدرتِ هدف باید حداقل {_floor:,} باشد "
                f"(≥{int(W.WEAK_TARGET_RATIO * 100)}٪ قدرتِ تو).\n"
                "زورگیری از ضعیف‌ترها ممنوع است."
            ),
            war_back_menu(attacker_id),
        )
        return
    lines = [
        f"🎯 <b>هدف:</b> {target.name or target_id}",
        "",
        battle_live.preview_text(pre),
        "",
        "⚔️ هر جنگ ۱۵ دقیقه طول می‌کشد و گزارشِ میدان را با دکمه‌ی «🔄 بروزرسانی» دنبال می‌کنی.",
    ]
    if shielded:
        lines.append(f"\n{W.safe_mode_message(war_service.shield_days_left(st))}")
        await safe_show(message, "\n".join(lines), war_back_menu(attacker_id))
        return
    lines.append("\nحمله را تأیید می‌کنی؟")
    await safe_show(message, "\n".join(lines), confirm_attack_menu(target_id, attacker_id))


@router.callback_query(F.data.startswith("war:target:"))
async def target_from_contact(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    base, _owner = split_owner(callback.data)
    target_id = int(base.split(":")[2])
    if target_id == callback.from_user.id:
        await safe_answer(callback, "نمی‌توانی به خودت حمله کنی!", show_alert=True)
        return
    await _preview_target(callback.message, callback.from_user.id, target_id)
    await safe_answer(callback)


@router.callback_query(F.data.startswith("war:manual"))
async def manual_target(callback: CallbackQuery, state: FSMContext) -> None:
    if not await ensure_owner(callback):
        return
    await state.set_state(WarStates.entering_target)
    await callback.message.answer(
        "⌨️ آیدیِ عددی یا یوزرنیمِ هدف را بفرست.\n"
        "⚠️ برای جنگ، فرد موردنظر باید اول در لیست مخاطبین تو باشد؛ از بخش «مخاطبین» می‌توانی دستی اضافه‌اش کنی."
    )
    await safe_answer(callback)


@router.message(WarStates.entering_target)
async def receive_manual_target(message: Message, state: FSMContext) -> None:
    await state.clear()
    async with async_session() as session:
        target_id, err = await spy_service.resolve_target(session, message.from_user.id, message.text or "")
    if err:
        await message.reply(f"❌ {err}")
        return
    if target_id == message.from_user.id:
        await message.reply("نمی‌توانی به خودت حمله کنی!")
        return
    await _preview_target(message, message.from_user.id, int(target_id))


async def _is_contact(session, owner_id: int, target_id: int) -> bool:
    row = (await session.execute(
        select(Contact.id).where(Contact.owner_id == owner_id, Contact.contact_id == target_id)
    )).scalar_one_or_none()
    return row is not None


# --------------------------- حمله: اجرا ---------------------------
async def _resolve_strike(session, attacker_id: int, target_id: int) -> tuple[bool, str]:
    """(ok, text) — یک حمله را کامل اجرا و ن����یجه را اعمال می‌کند."""
    if attacker_id == target_id:
        return False, "نمی‌توانی به خودت حمله کنی!"
    attacker = await get_player(session, attacker_id)
    defender = await get_player(session, target_id)
    if attacker is None:
        return False, "اول /start را بزن."
    if defender is None:
        return False, "این کاربر هنوز در بازی نیست."
    if int(attacker.level or 1) < W.WAR_UNLOCK_LEVEL:
        return False, f"🔒 بخشِ جنگ از سطحِ {W.WAR_UNLOCK_LEVEL} باز می‌شود."
    if not await _is_contact(session, attacker_id, target_id):
        return False, "🚫 برای جنگ، فرد موردنظر باید در مخاطبین تو باشد. از بخش «مخاطبین» با آیدی یا یوزرنیم اضافه‌اش کن."

    now = datetime.utcnow()
    atk_state = await war_service.get_or_create_war_state(session, attacker_id)
    cd = war_service.attack_cooldown_left_min(atk_state, now)
    if cd:
        return False, f"⏳ تا حمله‌ی بعدی {cd} دقیقه مانده."

    def_state = await war_service.get_or_create_war_state(session, target_id)
    if war_service.is_shielded(def_state, now):
        return False, W.safe_mode_message(war_service.shield_days_left(def_state, now))

    my_power = await war_service.compute_combat_power(session, attacker_id)
    enemy_power = await war_service.compute_combat_power(session, target_id)
    if await alliance_service.same_alliance(session, attacker_id, target_id):
        return False, "🤝 این بازیکن هم‌اتحادیه‌ی توست؛ نمی‌توانی به او حمله کنی."
    if not W.attack_allowed(my_power, enemy_power):
        return False, (
            f"🚫 هدف بسیار ضعیف‌تر از توست. قدرتِ هدف باید حداقل {W.min_target_power(my_power):,} باشد "
            f"(≥{int(W.WEAK_TARGET_RATIO * 100)}٪ قدرتِ تو)."
        )
    attacker_won = W.roll_battle(my_power, enemy_power)
    # 🆕 تلفاتِ منطقی: وابسته ب�� نسبتِ قدرتِ مهاجم/مدافع و قدرتِ حریف (نه درصدِ ثابتِ ارتش)
    att_losses = await military_service.apply_scaled_losses(
        session, attacker_id, my_power, enemy_power,
        won=attacker_won, intensity=W.CASUALTY_INTENSITY["personal_attacker"],
    )
    def_losses = await military_service.apply_scaled_losses(
        session, target_id, enemy_power, my_power,
        won=not attacker_won, intensity=W.CASUALTY_INTENSITY["personal_defender"],
    )

    atk_state.last_attack_at = now
    # دفاع‌کننده پس از هر نبرد، در دوره‌ی غنیمت + بازسازی مصون است
    def_state.shield_until = now + timedelta(days=W.SAFE_TOTAL_DAYS)

    if attacker_won:
        loot_pct = W.loot_percent(my_power, enemy_power)
        try:
            from app.services import worldbank_service as _WBS
            pool = await _WBS.lootable_wealth_of(session, target_id)
            lootable = int(pool.get("lootable_total") or 0)
        except Exception:
            lootable = int(defender.cash or 0)
        from app.data import ranks as _RK
        amount = _RK.classic_loot(lootable, int(defender.cash or 0), pct=loot_pct, att_power=my_power, def_power=enemy_power)
        amount = max(0, min(lootable, int(amount)))
        take_cash = min(int(defender.cash or 0), amount)
        defender.cash = int(defender.cash or 0) - take_cash
        need_bank = amount - take_cash
        looted_bank = 0
        if need_bank > 0:
            try:
                from app.services.battle_live import _withdraw_lootable_bank
                looted_bank = await _withdraw_lootable_bank(session, target_id, need_bank)
            except Exception:
                looted_bank = 0
            amount = take_cash + looted_bank
        attacker.cash = int(attacker.cash or 0) + amount
        battle = Battle(
            attacker_id=attacker_id, defender_id=target_id,
            winner_id=attacker_id, loser_id=target_id,
            loot_pct=loot_pct, amount=amount,
            loot_until=now + timedelta(days=W.LOOT_DAYS), attacker_won=1,
        )
        session.add(battle)
        await _bump_stats(session, attacker_id, attacks_success=1, battle_wins=1, enemies_defeated=1)
        await _bump_stats(session, target_id)
        await session.commit()
        return True, (
            "🏆 <b>پیروزی!</b>\n\n"
            f"حریف را شکست دادی و غنیمت گرفتی.\n"
            f"💰 غنیمت: <b>{amount:,}$</b> ({loot_pct}٪ از درآمدِ {W.LOOT_DAYS}روزه)\n"
            f"🩸 تلفات تو: {military_service.losses_text(att_losses)}\n"
            f"🩸 تلفات هدف: {military_service.losses_text(def_losses)}\n"
            f"🛡️ هدف تا {W.SAFE_TOTAL_DAYS} روز زیرِ سپر رفت."
        )
    else:
        penalty_pct = W.penalty_percent(my_power, enemy_power)
        amount = W.penalty_amount(int(attacker.cash or 0), penalty_pct)
        attacker.cash = int(attacker.cash or 0) - amount
        defender.cash = int(defender.cash or 0) + amount
        await _damage_active_city(session, attacker_id)
        battle = Battle(
            attacker_id=attacker_id, defender_id=target_id,
            winner_id=target_id, loser_id=attacker_id,
            loot_pct=0, amount=amount,
            loot_until=None, attacker_won=0,
        )
        session.add(battle)
        await _bump_stats(session, target_id, defenses_won=1)
        await session.commit()
        return True, (
            "💥 <b>شکست!</b>\n\n"
            f"حمله‌ات دفع شد و غرامت پرداختی.\n"
            f"💸 غرامت: <b>{amount:,}$</b> ({penalty_pct}٪ از دارایی)\n"
            f"🩸 تلفات تو: {military_service.losses_text(att_losses)}\n"
            f"🩸 تلفات هدف: {military_service.losses_text(def_losses)}\n"
            f"🏘️ زیرساختِ شهرت آسیب دید (رضایت −{W.INFRA_DAMAGE_SAT})."
        )


@router.callback_query(F.data.startswith("war:strike:"))
async def strike(callback: CallbackQuery) -> None:
    """🆕 مرحله ۴۶ — شروعِ نبردِ زنده‌ی ۱۵ دقیقه‌ای (بدونِ اعلامِ فوریِ نتیجه)."""
    if not await ensure_owner(callback):
        return
    base, _owner = split_owner(callback.data)
    target_id = int(base.split(":")[2])
    uid = callback.from_user.id
    async with async_session() as session:
        ok, err = await _validate_strike(session, uid, target_id)
        if not ok:
            await safe_answer(callback, err, show_alert=True)
            return
        started, res = await battle_live.start(session, uid, target_id, mode="classic")
        if not started:
            await safe_answer(callback, str(res), show_alert=True)
            return
        row = res
        await session.commit()
        text = battle_live.render(row)
        bid = int(row.id)
        def_id = int(row.defender_id)
        att_name = battle_live.plan_of(row).get("att_name", uid)
    await safe_show(callback.message, text, battle_live_menu(bid, uid, can_cease=True))
    await safe_answer(callback, "⚔️ جنگ شروع شد! ۱۵ دقیقه میدان باز است.", show_alert=True)
    try:
        await callback.bot.send_message(
            def_id,
            f"🚨 <b>هشدار!</b> {att_name} به قلمروی‌ات حمله کرد. نبرد ۱۵ دقیقه طول می‌کشد…\n"
            f"📜 در بخشِ جنگ با دکمه‌ی «گزارشِ آخرین نبرد» می‌توانی میدان را دنبال کنی.",
        )
    except Exception:
        pass


@router.callback_query(F.data.startswith("war:live:"))
async def live_refresh(callback: CallbackQuery) -> None:
    """🔄 بروزرسانیِ دستیِ گزارشِ نبرد (فازها به‌ترتیب اضافه می‌شوند)."""
    if not await ensure_owner(callback):
        return
    base, _owner = split_owner(callback.data)
    try:
        bid = int(base.split(":")[2])
    except Exception:
        await safe_answer(callback, "❌ شناسه‌ی نبرد نامعتبر.", show_alert=True)
        return
    uid = callback.from_user.id
    notify = None
    async with async_session() as session:
        row = await session.get(LiveBattle, bid)
        # 🆕 مرحله ۷۰ — مدافع هم حقِ دیدن/بروزرسانیِ گزارشِ نبرد را دارد
        if row is None or int(uid) not in (int(row.attacker_id), int(row.defender_id)):
            await safe_answer(callback, "❌ این نبرد پیدا نشد.", show_alert=True)
            return
        i_am_attacker = int(row.attacker_id) == int(uid)
        finished = battle_live.is_over(row)
        if finished and not row.finalized:
            out = await battle_live.finalize(session, row)
            other = int(row.defender_id) if i_am_attacker else int(row.attacker_id)
            notify = (other, out.get("defender" if i_am_attacker else "attacker", ""))
        text = battle_live.render_for(row, uid)
    await safe_show(callback.message, text, battle_live_menu(bid, uid, finished=finished, can_cease=(not finished and battle_live.phases_unlocked(row) < 3)))
    await safe_answer(callback, "🔄 بروزرسانی شد.")
    if notify and notify[1]:
        try:
            await callback.bot.send_message(notify[0], notify[1])
        except Exception:
            pass


# --------------------------- 🆕 مرحله ۷۰ — بازآوردنِ گزارشِ نبرد ---------------------------
@router.callback_query(F.data.startswith("war:report"))
async def battle_report(callback: CallbackQuery) -> None:
    """🆕 مرحله ۷۰ — گزارشِ نبردِ ردشده/بسته‌شده را برمی‌گرداند.

    هم مهاجم و هم مدافع می‌توانند از این دکمه استفاده کنند؛ اولویت با نبردِ
    درجریان است و اگر نبود، گزارشِ نهاییِ آخرین نبرد نشان داده می‌شود.
    """
    if not await ensure_owner(callback):
        return
    uid = callback.from_user.id
    notify = None
    async with async_session() as session:
        row = await battle_live.last_battle(session, uid)
        if row is None:
            await safe_answer(callback, "📭 هنوز هیچ نبردی نداشته‌ای.", show_alert=True)
            return
        i_am_attacker = int(row.attacker_id) == int(uid)
        finished = battle_live.is_over(row)
        if finished and not row.finalized:
            out = await battle_live.finalize(session, row)
            other = int(row.defender_id) if i_am_attacker else int(row.attacker_id)
            notify = (other, out.get("defender" if i_am_attacker else "attacker", ""))
        bid = int(row.id)
        text = battle_live.render_for(row, uid)
    await safe_show(callback.message, text, battle_live_menu(bid, uid, finished=finished, can_cease=(not finished and battle_live.phases_unlocked(row) < 3)))
    await safe_answer(callback, "📜 گزارشِ نبرد برگشت.")
    if notify and notify[1]:
        try:
            await callback.bot.send_message(notify[0], notify[1])
        except Exception:
            pass


# --------------------------- 🆕 مرحله ۴۶ — اعتبارسنجیِ حمله ---------------------------
async def _validate_strike(session, attacker_id: int, target_id: int) -> tuple[bool, str]:
    """همه‌ی شرط‌های مجازبودنِ حمله (بدونِ اعمالِ هیچ اثری)."""
    if attacker_id == target_id:
        return False, "نمی‌توانی به خودت حمله کنی!"
    attacker = await get_player(session, attacker_id)
    defender = await get_player(session, target_id)
    if attacker is None:
        return False, "اول /start را بزن."
    if defender is None:
        return False, "این کاربر هنوز در بازی نیست."
    if int(attacker.level or 1) < W.WAR_UNLOCK_LEVEL:
        return False, f"🔒 بخشِ جنگ از سطحِ {W.WAR_UNLOCK_LEVEL} باز می‌شود."
    if not await _is_contact(session, attacker_id, target_id):
        return False, "🚫 برای جنگ، فردِ موردنظر باید در مخاطبینِ تو باشد."
    if await alliance_service.same_alliance(session, attacker_id, target_id):
        return False, "🤝 این بازیکن هم‌اتحادیه‌ی توست."
    def_state = await war_service.get_or_create_war_state(session, target_id)
    if war_service.is_shielded(def_state):
        return False, W.safe_mode_message(war_service.shield_days_left(def_state))
    my_power = await war_service.compute_combat_power(session, attacker_id)
    enemy_power = await war_service.compute_combat_power(session, target_id)
    if not W.attack_allowed(my_power, enemy_power):
        return False, (
            f"🚫 هدف بسیار ضعیف‌تر از توست. قدرتِ هدف باید حداقل {W.min_target_power(my_power):,} باشد."
        )
    return True, ""


# ============================================================
# 🆕 مرحله ۴۶ (بچ ۳) — جنگِ رنکینگ (کاپ/لیگ + پنجره‌ی ±۵۰)
# ============================================================
from app.keyboards.war_menu import ranked_confirm_menu, ranked_targets_menu  # noqa: E402
from app.services import rank_service  # noqa: E402
from app.data import ranks as _RANKS  # noqa: E402

_RANKED_PER = 10


async def _ranked_home(message: Message, uid: int, page: int = 0) -> None:
    async with async_session() as session:
        player = await get_player(session, uid)
        if not player:
            await safe_show(message, "اول /start را بزن.", war_back_menu(uid))
            return
        window, my_idx, total = await rank_service.window_targets(session, uid)
        status = await rank_service.status_text(session, uid)
    rows, page, pages = rank_service.page_slice(window, page, _RANKED_PER)
    lines = [
        "🏅 <b>جنگِ رنکینگ</b>",
        "",
        status,
        "",
        f"⚔️ فقط به ±{_RANKS.ATTACK_WINDOW} نفرِ اطرافِ خودت در رتبه‌بندیِ کلی می‌توانی حمله کنی.",
        f"⏳ کول‌داون: هر {_RANKS.RANKED_COOLDOWN_HOURS // 24} روز یک‌بار به هر نفر.",
    ]
    if not window:
        lines.append("\nفعلاً کسی در محدوده‌ی حمله‌ی تو نیست.")
    else:
        lines.append("\n🎯 <b>اهدافِ مجاز:</b>")
    await safe_show(message, "\n".join(lines), ranked_targets_menu(rows, uid, page, pages))


@router.callback_query(F.data.startswith("war:ranked"))
async def ranked_home(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    if not _is_private(callback.message.chat.type):
        await _deny_group(callback)
        return
    # 🆕 v1.7.2 — اگر ادمین این گزینه رنکینگ را خاموش کرده باشد، دیده/باز نشود
    try:
        from app.services import admin_service as _adm
        async with async_session() as session:
            vis = await _adm.get_rank_visibility(session)
        if not vis.get("war_ranked", True):
            await safe_answer(callback, "این بخش توسط ادمین خاموش شده است.", show_alert=True)
            return
    except Exception:
        pass
    await _ranked_home(callback.message, callback.from_user.id, 0)
    await safe_answer(callback)


@router.callback_query(F.data.startswith("war:rpage:"))
async def ranked_page(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    base, _owner = split_owner(callback.data)
    try:
        page = int(base.split(":")[2])
    except Exception:
        page = 0
    await _ranked_home(callback.message, callback.from_user.id, page)
    await safe_answer(callback)


@router.callback_query(F.data.startswith("war:rstatus"))
async def ranked_status(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    async with async_session() as session:
        text = await rank_service.status_text(session, callback.from_user.id)
    await safe_show(callback.message, text, war_back_menu(callback.from_user.id))
    await safe_answer(callback)


@router.callback_query(F.data.startswith("war:rtarget:"))
async def ranked_target(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    base, _owner = split_owner(callback.data)
    target_id = int(base.split(":")[2])
    uid = callback.from_user.id
    if target_id == uid:
        await safe_answer(callback, "نمی‌توانی به خودت حمله کنی!", show_alert=True)
        return
    async with async_session() as session:
        target = await get_player(session, target_id)
        if target is None:
            await safe_show(callback.message, "❌ این کاربر هنوز در بازی نیست.", war_back_menu(uid))
            await safe_answer(callback)
            return
        ok, err = await rank_service.can_attack(session, uid, target_id)
        pre = await battle_live.preview(session, uid, target_id)
    lines = [
        f"🎯 <b>هدفِ رنکینگ:</b> {target.name or target_id}",
        "",
        battle_live.preview_text(pre),
        "",
        "🏅 بردِ رنکینگ = کاپ + غنیمت (بیشترین ۴۲٪ نقد / کمترین ۱۴٪ ثروت) + XP.",
        "⚔️ هر نبرد ۱۵ دقیقه است؛ گزارش را با «🔄 بروزرسانی» دنبال کن.",
    ]
    if not ok:
        lines.append(f"\n{err}")
        await safe_show(callback.message, "\n".join(lines), war_back_menu(uid))
        await safe_answer(callback)
        return
    lines.append("\nحمله‌ی رنکینگ را تأیید می‌کنی؟")
    await safe_show(callback.message, "\n".join(lines), ranked_confirm_menu(target_id, uid))
    await safe_answer(callback)


@router.callback_query(F.data.startswith("war:rstrike:"))
async def ranked_strike(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    base, _owner = split_owner(callback.data)
    target_id = int(base.split(":")[2])
    uid = callback.from_user.id
    async with async_session() as session:
        attacker = await get_player(session, uid)
        if attacker is None:
            await safe_answer(callback, "اول /start را بزن.", show_alert=True)
            return
        if int(attacker.level or 1) < W.WAR_UNLOCK_LEVEL:
            await safe_answer(callback, f"🔒 بخشِ جنگ از سطحِ {W.WAR_UNLOCK_LEVEL} باز می‌شود.", show_alert=True)
            return
        ok, err = await rank_service.can_attack(session, uid, target_id)
        if not ok:
            await safe_answer(callback, err, show_alert=True)
            return
        started, res = await battle_live.start(session, uid, target_id, mode="ranked")
        if not started:
            await safe_answer(callback, str(res), show_alert=True)
            return
        row = res
        await session.commit()
        text = battle_live.render(row)
        bid = int(row.id)
        def_id = int(row.defender_id)
        att_name = battle_live.plan_of(row).get("att_name", uid)
    await safe_show(callback.message, text, battle_live_menu(bid, uid, can_cease=True))
    await safe_answer(callback, "🏅 جنگِ رنکینگ شروع شد! ۱۵ دقیقه میدان باز است.", show_alert=True)
    try:
        await callback.bot.send_message(
            def_id,
            f"🚨 <b>هشدارِ رنکینگ!</b> {att_name} در جنگِ رنکینگ به تو حمله کرد. نبرد ۱۵ دقیقه طول می‌کشد…\n"
            f"📜 در بخشِ جنگ با دکمه‌ی «گزارشِ آخرین نبرد» می‌توانی میدان را دنبال کنی.",
        )
    except Exception:
        pass


# --------------------------- v1.7.6 آتش‌بس + بیمارستان ---------------------------
@router.callback_query(F.data.startswith("war:cease:"))
async def war_cease(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    base, _owner = split_owner(callback.data)
    try:
        bid = int(base.split(":")[2])
    except Exception:
        await safe_answer(callback, "شناسه نامعتبر", show_alert=True); return
    uid = callback.from_user.id
    async with async_session() as session:
        ok, msg, row = await battle_live.ceasefire(session, bid, uid)
        if ok and row is not None:
            # finalize immediately with reduced losses
            if not row.finalized:
                await battle_live.finalize(session, row)
            await session.commit()
            text = battle_live.render_for(row, uid)
            finished = True
        else:
            text = None; finished=False
    if not ok:
        await safe_answer(callback, msg, show_alert=True); return
    await safe_show(callback.message, text, battle_live_menu(bid, uid, finished=True))
    await safe_answer(callback, msg, show_alert=True)


@router.callback_query(F.data.startswith("war:hospital:"))
async def war_hospital(callback: CallbackQuery) -> None:
    """⚠️ v1.7.6.3 — دکمهٔ قدیمیِ بیمارستان در گزارشِ نبرد.

    این دکمه از کیبوردِ battle_live_menu حذف شده، ولی در پیام‌های
    قدیمیِ چت‌ها هنوز وجود دارد؛ پس زنده می‌ماند و جایِ درمانِ
    خودکار (که حذف شد) کاربر را به بخشِ تازه راهنمایی می‌کند.
    """
    if not await ensure_owner(callback):
        return
    uid = callback.from_user.id
    try:
        async with async_session() as session:
            _ok, msg = await battle_live.hospital_heal(session, uid, None)
            await session.commit()
    except Exception as exc:
        msg = f"⚠️ خطا در بیمارستان: {exc}"
    await safe_answer(callback, msg, show_alert=True)
