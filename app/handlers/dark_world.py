# -*- coding: utf-8 -*-
"""Stage 87.1 — Dark World hub, contracts, ranking and starter recruitment."""
from __future__ import annotations

import html

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from app.database.engine import async_session
from app.data import dark_world as D
from app.data import dark_world_npcs as N  # extends NPC catalog
from app.data import leveling
from app.keyboards.dark_world_menu import (
    active_menu,
    approaches_menu,
    back_to_hub,
    contracts_menu,
    hub_menu,
    operations_hub_menu, crew_hub_menu, economy_hub_menu, competition_hub_menu, production_hub_menu, guide_hub_menu, guide_page_menu,
    preview_menu,
    recruits_menu,
)
from app.keyboards.main_menu import BTN_DARK_WORLD, WORD_DARK_WORLD
from app.services import dark_world_service as DS
from app.services.operation_guard import BusyOperation, DuplicateOperation, economic_operation
from app.utils.ui import click_debounce, ensure_owner, safe_answer, safe_show, split_owner

router = Router(name="dark_world")

GUIDE_PAGES = [
("🚀 شروع سریع", "برای شروع فقط این مسیر را برو:\n\n1) از مأموریت‌ها یک عملیات ساده انتخاب کن.\n2) نفوذ و XP سیاه جمع کن.\n3) یک نیروی NPC استخدام و تیم سه‌نفره بساز.\n4) وقتی سرمایه کافی داشتی وارد تجارت یا تولید شو.\n5) Heat و Trace را همیشه پایین نگه دار.\n\nلازم نیست همه بخش‌ها را هم‌زمان یاد بگیری؛ هر شاخه مستقل است."),
("🎯 عملیات و پرونده‌ها", "«عملیات سایه» مسیر کوتاه و مستقیم دارد. نوع قرارداد و روش اجرا روی شانس، زمان، پاداش و Heat اثر می‌گذارد.\n\n«پرونده‌های چندشاخه» انتخاب‌محورند و تصمیم‌ها مسیر بعدی را عوض می‌کنند. ابزار انتخابی مصرف می‌شود.\n\n«تعقیب و مخفیگاه» وقتی خطر بالا برود فعال می‌شود؛ سرنخ جمع کن، ضدنقشه انتخاب کن و مخفیگاه را ارتقا بده."),
("👥 نیروها و قراردادها", "NPCها سطح، وفاداری، خستگی، جراحت و حقوق دارند. سه نیروی مکمل انتخاب کن و تاکتیک مناسب عملیات را بگذار.\n\nدر بازار کار کاربران، کارفرما مبلغ را در escrow قفل می‌کند؛ کاربر دیگر قرارداد را می‌پذیرد و تسویه فقط بر اساس نتیجه ثبت‌شده انجام می‌شود."),
("💰 تجارت و اقتصاد", "در حمل‌ونقل، کالا، مقدار، بسته‌بندی، مسیر و مقصد را انتخاب می‌کنی. هر انتخاب بین سود، زمان و خطر تفاوت ایجاد می‌کند.\n\nبازار کاربران اختیاری است و قیمت آن با عرضه و تقاضا تغییر می‌کند. درآمدهای زیرزمینی ابتدا پول کثیف‌اند. روش پول‌شویی سریع‌تر معمولاً Trace و احتمال مصادره بیشتری دارد."),
("🧪 آزمایشگاه و ۱۲۵ فرمول", "آزمایشگاه استاندارد ۲۴ محصول آماده دارد. تجهیزات کیفیت، برق قدرت، تهویه پایداری و ایمنی شانس موفقیت را بهتر می‌کند.\n\nبرای فرمول ترکیبی: یک پایه + یک عامل + یک امضا انتخاب کن. ۵×۵×۵ یعنی ۱۲۵ ترکیب یکتا. پایه را می‌توان خرید یا در گلخانه کاشت. کشف یک واحد و تولید دو واحد از هر جزء مصرف می‌کند."),
("🚚 فروش و قیمت", "قیمت از ارزش اجزا، کیفیت، قدرت، پایداری، تقاضای روز، ثروت محله، کانال فروش و نوع مشتری ساخته می‌شود.\n\nفروش مستقیم سود واحد بیشتر و خطر بالاتر دارد؛ توزیع‌کننده متعادل است؛ عمده‌فروش حجم بیشتر و حاشیه سود کمتر دارد. بررسی هویت مشتری امنیت را بالا می‌برد اما زمان یا سود را کم می‌کند."),
("⚔️ رقابت و فصل", "شبیخون به اطلاعات، روش حمله، دفاع و حمایت متحدان وابسته است. در روایت فصلی به جناح ملحق می‌شوی و رأی جمعی روی جهان اثر می‌گذارد.\n\nرتبه پایان فصل چندمحوره است؛ فقط ثروت کافی نیست و فعالیت، حمل، امور مالی، نبرد و مشارکت هم سنجیده می‌شوند."),
("🏰 امپراتوری و بازرسی", "تا پنج مرکز تولید بساز و بین ظرفیت، پنهان‌کاری، مقاومت و تحقیق تعادل ایجاد کن. مرکز بزرگ‌تر ظرفیت بیشتری دارد اما هزینه و ریسک شبکه را بالا می‌برد.\n\nHeat، Trace، تعداد مراکز و پنهان‌کاری احتمال بازرسی را تعیین می‌کنند. پس از هشدار، واکنش انتخاب کن؛ نتیجه همان لحظه روی سرور قفل می‌شود."),
("🚨 Heat، Trace و نتیجه‌ها", "Heat خطر عملیاتی است و با گذر زمان کم می‌شود. Trace رد مالی است و روی خریدار مشکوک، پول‌شویی و بازرسی اثر دارد.\n\nنتیجه عملیات حساس هنگام شروع ذخیره می‌شود؛ بستن منو، ری‌استارت یا چندبار کلیک‌کردن نتیجه تازه ایجاد نمی‌کند. دکمه‌های ◀️ برای برگشت به مرحله قبلی و 🏠 برای خروج کامل از بخش هستند."),
]


def _base(callback: CallbackQuery) -> str:
    return split_owner(callback.data or "")[0]


def _rank_progress(profile) -> str:
    progress = D.progress_to_next_rank(int(profile.influence or 0))
    if progress is None:
        return "👑 بالاترین رنک داخلی"
    current, needed = progress
    return f"پیشرفت رنک: {current:,}/{needed:,}"


def hub_text(snapshot: dict) -> str:
    player = snapshot["player"]
    profile = snapshot["profile"]
    tier = snapshot["tier"]
    next_tier = snapshot["next_tier"]
    active = "نداری"
    if profile.active_contract_key:
        contract = D.get_contract(profile.active_contract_key)
        name = contract["name"] if contract else profile.active_contract_key
        remaining = int(snapshot.get("remaining") or 0)
        active = f"{name} — {'آماده دریافت' if remaining <= 0 else D.fmt_duration(remaining) + ' مانده'}"
    next_line = (
        f"🔓 رنک بعدی: {next_tier['icon']} {next_tier['name']} در {int(next_tier['threshold']):,} نفوذ"
        if next_tier else "👑 به آخرین رنک داخلی رسیده‌ای"
    )
    return (
        "🌑 <b>دنیای سیاه — فصل صفر</b>\n"
        "<i>جایی که نتیجه پیش از نمایش ثبت می‌شود و انتخاب روش، ریسک را عوض می‌کند.</i>\n"
        "🧭 تازه‌واردی؟ ابتدا «راهنمای شروع و قوانین» را باز کن.\n\n"
        f"🎚️ لول عمومی: <b>{int(player.level)}/{leveling.MAX_LEVEL}</b>\n"
        f"{tier['icon']} رنک داخلی: <b>{tier['name']}</b>\n"
        f"🗝️ نفوذ: <b>{int(profile.influence or 0):,}</b> — {_rank_progress(profile)}\n"
        f"🌘 XP سیاه: <b>{int(profile.dark_xp or 0):,}</b>\n"
        f"⚡ انرژی: <b>{int(profile.energy or 0)}/{D.ENERGY_MAX}</b>\n"
        f"🚨 گرما: <b>{int(profile.heat or 0)}/{D.HEAT_MAX}</b> — {D.heat_label(int(profile.heat or 0))}\n"
        f"👁️ اطلاعات: <b>{int(profile.intel or 0):,}</b>\n"
        f"🔥 برد پیاپی: <b>{int(profile.current_streak or 0)}</b> (بهترین {int(profile.best_streak or 0)})\n"
        f"📊 رکورد: {int(profile.successes or 0)} موفق / {int(profile.failures or 0)} ناموفق — {DS.success_rate(profile)}٪\n"
        f"👥 نیروهای استخدامی: <b>{len(snapshot.get('recruits') or [])}/{len(D.RECRUIT_ORDER)}</b>\n"
        f"🎯 عملیات فعال: <b>{active}</b>\n\n"
        f"{next_line}\n\n"
        "⚠️ انرژی هر ۶ دقیقه ۱ واحد برمی‌گردد؛ گرما هر ۳۰ دقیقه ۱ واحد کم می‌شود."
    )


def active_text(profile) -> tuple[str, bool]:
    if not profile or not profile.active_contract_key:
        return "🌑 عملیات فعالی نداری.", False
    contract = D.get_contract(profile.active_contract_key) or {"name": profile.active_contract_key, "icon": "🌑"}
    approach = D.get_approach(profile.active_approach_key) or {"name": "نامشخص", "icon": "🎭"}
    remaining = DS.active_remaining(profile)
    ready = remaining <= 0
    status = "🎁 نتیجه آماده است؛ پاکت را باز کن." if ready else f"⏳ {D.fmt_duration(remaining)} تا آماده‌شدن نتیجه"
    return (
        "🎯 <b>عملیات فعال</b>\n\n"
        f"{contract.get('icon', '🌑')} قرارداد: <b>{contract['name']}</b>\n"
        f"{approach.get('icon', '🎭')} روش: <b>{approach['name']}</b>\n"
        f"🎲 شانس ثبت‌شده: <b>{int(profile.active_chance_bp or 0) / 100:.2f}٪</b>\n"
        f"{status}\n\n"
        "🔒 نتیجه هنگام شروع به‌صورت مخفی ذخیره شده؛ بازکردن صفحه یا ری‌استارت، آن را عوض نمی‌کند."
    ), ready


def preview_text(plan: dict, ready: bool) -> str:
    contract = D.get_contract(plan["contract_key"])
    approach = D.get_approach(plan["approach_key"])
    low_cash = int(plan["cash_success"] * 0.90)
    high_cash = int(plan["cash_success"] * 1.10)
    lines = [
        "🧾 <b>پرونده عملیات</b>", "",
        f"{contract['icon']} قرارداد: <b>{contract['name']}</b>",
        f"🎭 روش: {approach['icon']} <b>{approach['name']}</b>",
        f"☠️ سختی: {contract['difficulty']}/4 — {contract['difficulty_name']}",
        f"🎲 شانس موفقیت نهایی: <b>{float(plan['chance']):.2f}٪</b>",
        f"⏱️ زمان: <b>{D.fmt_duration(int(plan['duration']))}</b>",
        f"⚡ انرژی: {int(plan['energy'])} (موجود {int(plan['available_energy'])})",
        f"👁️ اطلاعات مصرفی: {int(plan['intel_cost'])} (موجود {int(plan['available_intel'])})",
        f"🎟️ هزینه ورودِ غیرقابل‌برگشت: <b>{int(plan['entry_cost']):,}</b>",
        "",
        f"💵 برد احتمالی: <b>{low_cash:,} تا {high_cash:,}</b>",
        f"✨ XP عمومی در موفقیت/شکست: <b>{int(plan['xp_success']):,} / {int(plan['xp_failure']):,}</b>",
        f"🌘 XP سیاه در موفقیت/شکست: {int(plan['dark_xp_success']):,} / {int(plan['dark_xp_failure']):,}",
        f"🗝️ نفوذ در موفقیت/شکست: +{int(plan['influence_success']):,} / {int(plan['influence_failure']):,}",
        f"🚨 گرمای موفقیت/شکست: +{int(plan['heat_success'])} / +{int(plan['heat_failure'])}",
    ]
    if int(plan.get("streak_bonus_pct") or 0):
        lines.append(f"🔥 ضریب برد پیاپی روی غنیمت: +{int(plan['streak_bonus_pct'])}٪")
    if plan.get("recruit_keys"):
        lines.append(f"👥 اثر نیروهای استخدامی: {len(plan['recruit_keys'])} نیرو فعال")
    lines += ["", "✅ آمادهٔ شروع است." if ready else "⚠️ فعلاً نمی‌توانی شروع کنی:"]
    if not ready:
        lines.extend(f"• {issue}" for issue in plan.get("issues") or ["شرایط کامل نیست."])
    return "\n".join(lines)


async def _snapshot(session, uid: int):
    ok, reason, snapshot = await DS.hub_snapshot(session, uid)
    await session.commit()
    return ok, reason, snapshot


@router.message(F.text.in_({WORD_DARK_WORLD, BTN_DARK_WORLD, "جهان سیاه", "دنیای تاریک"}))
async def dark_world_message(message: Message) -> None:
    async with async_session() as session:
        ok, reason, snapshot = await _snapshot(session, message.from_user.id)
    if not ok:
        await message.reply(reason, reply_markup=back_to_hub(message.from_user.id))
        return
    profile = snapshot["profile"]
    await message.reply(
        hub_text(snapshot),
        reply_markup=hub_menu(message.from_user.id, bool(profile.active_contract_key), int(snapshot["remaining"]) <= 0),
    )


@router.callback_query(F.data.startswith("menu:darkworld"))
@router.callback_query(F.data.startswith("dw:hub"))
async def dark_world_hub(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    async with async_session() as session:
        ok, reason, snapshot = await _snapshot(session, callback.from_user.id)
    if not ok:
        await safe_show(callback.message, reason, back_to_hub(callback.from_user.id))
        await safe_answer(callback)
        return
    profile = snapshot["profile"]
    await safe_show(
        callback.message, hub_text(snapshot),
        hub_menu(callback.from_user.id, bool(profile.active_contract_key), int(snapshot["remaining"]) <= 0),
    )
    await safe_answer(callback)


@router.callback_query(F.data.startswith("dw:sec:"))
async def dark_world_section(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback): return
    key=_base(callback).split(":")[2]
    menus={"crew":crew_hub_menu,"economy":economy_hub_menu,"competition":competition_hub_menu,"production":production_hub_menu,"guide":guide_hub_menu}
    titles={"ops":"🎯 <b>مأموریت‌ها و پرونده‌ها</b>\nعملیات، پرونده‌های تصمیم‌محور و مدیریت تعقیب.","crew":"👥 <b>نیروها و قراردادها</b>\nاستخدام، ترکیب تیم و همکاری با کاربران.","economy":"💰 <b>تجارت و اقتصاد</b>\nحمل‌ونقل، بازار کاربران و مدیریت پول کثیف.","competition":"⚔️ <b>رقابت و فصل</b>\nشبیخون، جناح‌ها، لیگ و رنک داخلی.","production":"🧪 <b>تولید و توزیع</b>\nآزمایشگاه، فرمول‌ها، مشتریان و امپراتوری.","guide":"📜 <b>راهنما و قوانین</b>\nقوانین، محدودیت‌ها و مسیر روایی."}
    if key=="ops":
        async with async_session() as session: ok,reason,snapshot=await _snapshot(session,callback.from_user.id)
        if not ok:return await safe_answer(callback,reason,show_alert=True)
        pr=snapshot["profile"];kb=operations_hub_menu(callback.from_user.id,bool(pr.active_contract_key),int(snapshot["remaining"])<=0)
    else:kb=menus.get(key,guide_hub_menu)(callback.from_user.id)
    await safe_show(callback.message,titles.get(key,titles["guide"]),kb);await safe_answer(callback)

@router.callback_query(F.data.startswith("dw:guide:"))
async def dark_world_guide(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback): return
    tail=_base(callback).split(":")[2]
    if tail=="none": return await safe_answer(callback)
    page=max(0,min(int(tail),len(GUIDE_PAGES)-1));title,body=GUIDE_PAGES[page]
    await safe_show(callback.message,f"{title}\n\n{body}\n\n<i>راهنمای دنیای سیاه — صفحه {page+1} از {len(GUIDE_PAGES)}</i>",guide_page_menu(callback.from_user.id,page,len(GUIDE_PAGES)));await safe_answer(callback)

@router.callback_query(F.data.startswith("dw:contracts"))
async def dark_world_contracts(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    async with async_session() as session:
        ok, reason, snapshot = await _snapshot(session, callback.from_user.id)
    if not ok:
        await safe_answer(callback, reason, show_alert=True)
        return
    profile = snapshot["profile"]
    lines = [
        "🗺️ <b>عملیات سایه</b>",
        "", "هر قرارداد سه روش دارد؛ انتخاب�� شانس، زمان، گرما و پاداش را تغییر می‌دهد.",
        "هزینه ورود در هر نتیجه‌ای مصرف می‌شود. شکست هم XP آموزشی می‌دهد، اما نفوذ کم می‌کند.", "",
    ]
    for key in D.CONTRACT_ORDER:
        item = D.CONTRACTS[key]
        lock = "✅" if int(profile.influence or 0) >= int(item["required_influence"]) else "🔒"
        lines.append(
            f"{lock} {item['icon']} <b>{item['name']}</b> — سختی {item['difficulty']}/4 · "
            f"نیاز {int(item['required_influence']):,} نفوذ"
        )
    await safe_show(callback.message, "\n".join(lines), contracts_menu(profile.influence, callback.from_user.id))
    await safe_answer(callback)


@router.callback_query(F.data.startswith("dw:contract:"))
async def dark_world_contract_detail(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    key = _base(callback).split(":")[2]
    contract = D.get_contract(key)
    if not contract:
        await safe_answer(callback, "قرارداد نامعتبر است.", show_alert=True)
        return
    text = (
        f"{contract['icon']} <b>{contract['name']}</b>\n"
        f"{contract['description']}\n\n"
        f"☠️ سختی: {contract['difficulty']}/4 — {contract['difficulty_name']}\n"
        f"🎟️ ورودی: {int(contract['entry_cost']):,}\n"
        f"⚡ انرژی: {int(contract['energy'])} · 👁️ اطلاعات: {int(contract['intel_cost'])}\n"
        f"🗝️ حداقل نفوذ: {int(contract['required_influence']):,}\n\n"
        "<b>روش اجرا را انتخاب کن:</b>\n"
        "🥷 نفوذ خاموش: شانس بیشتر، گرما و پول کمتر\n"
        "♟️ نقشه حساب‌شده: حالت متعادل\n"
        "💥 یورش بی‌پروا: سریع و پردرآمد، اما پرخطر"
    )
    await safe_show(callback.message, text, approaches_menu(key, callback.from_user.id))
    await safe_answer(callback)


@router.callback_query(F.data.startswith("dw:preview:"))
async def dark_world_preview(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    parts = _base(callback).split(":")
    contract_key, approach_key = parts[2], parts[3]
    async with async_session() as session:
        ready, reason, plan = await DS.contract_preview(session, callback.from_user.id, contract_key, approach_key)
        await session.commit()
    if not plan:
        await safe_answer(callback, reason, show_alert=True)
        return
    await safe_show(
        callback.message, preview_text(plan, ready),
        preview_menu(contract_key, approach_key, callback.from_user.id, ready),
    )
    await safe_answer(callback)


@router.callback_query(F.data.startswith("dw:start:"))
async def dark_world_start(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    if click_debounce(callback.from_user.id, "dark_world_start", 3.0):
        await safe_answer(callback, "کلیک قبلی در حال پردازش است.")
        return
    parts = _base(callback).split(":")
    contract_key, approach_key = parts[2], parts[3]
    try:
        async with economic_operation(callback.from_user.id, f"dw-start:{callback.id}"):
            async with async_session() as session:
                ok, message = await DS.start_contract(session, callback.from_user.id, contract_key, approach_key)
                if ok:
                    profile = await DS.get_profile(session, callback.from_user.id)
                    text, ready = active_text(profile)
    except (BusyOperation, DuplicateOperation):
        await safe_answer(callback, "این عملیات قبلاً اجرا شده یا کلیک دیگری در حال پردازش است.", show_alert=True)
        return
    if not ok:
        await safe_answer(callback, message[:180], show_alert=True)
        return
    await safe_show(callback.message, text, active_menu(callback.from_user.id, ready))
    await safe_answer(callback, "عملیات آغاز شد")


@router.callback_query(F.data.startswith("dw:active"))
async def dark_world_active(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    async with async_session() as session:
        player = await DS.get_player(session, callback.from_user.id)
        blocked = DS.access_message(player)
        profile = await DS.get_profile(session, callback.from_user.id)
        if profile:
            DS.apply_recovery(profile)
        await session.commit()
    if blocked:
        await safe_answer(callback, blocked, show_alert=True)
        return
    text, ready = active_text(profile)
    await safe_show(callback.message, text, active_menu(callback.from_user.id, ready))
    await safe_answer(callback)


@router.callback_query(F.data.startswith("dw:collect"))
async def dark_world_collect(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    if click_debounce(callback.from_user.id, "dark_world_collect", 3.0):
        await safe_answer(callback, "کلیک قبلی در حال پردازش است.")
        return
    try:
        async with economic_operation(callback.from_user.id, f"dw-collect:{callback.id}"):
            async with async_session() as session:
                ok, message = await DS.collect_contract(session, callback.from_user.id)
                if not ok:
                    profile = await DS.get_profile(session, callback.from_user.id)
                    if profile:
                        DS.apply_recovery(profile)
                    await session.commit()
    except (BusyOperation, DuplicateOperation):
        await safe_answer(callback, "نتیجه قبلاً دریافت شده یا کلیک دیگری در حال پردازش است.", show_alert=True)
        return
    if not ok:
        text, ready = active_text(profile)
        await safe_show(callback.message, text, active_menu(callback.from_user.id, ready))
        await safe_answer(callback, message, show_alert=True)
        return
    await safe_show(callback.message, message, back_to_hub(callback.from_user.id))
    await safe_answer(callback, "نتیجه ثبت شد")


@router.callback_query(F.data.startswith("dw:rank"))
async def dark_world_rank(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    async with async_session() as session:
        player = await DS.get_player(session, callback.from_user.id)
        blocked = DS.access_message(player)
        data = await DS.ranking(session, callback.from_user.id) if not blocked else None
    if blocked:
        await safe_answer(callback, blocked, show_alert=True)
        return
    lines = ["🏆 <b>رنکینگ داخلی دنیای سیاه</b>", "", "ملاک: نفوذ ← XP سیاه ← عملیات موفق", ""]
    for index, entry in enumerate(data["entries"], start=1):
        medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(index, f"{index}.")
        lines.append(
            f"{medal} {entry.tier['icon']} <b>{html.escape(entry.name)}</b> — "
            f"{entry.influence:,} نفوذ · {entry.successes} برد"
        )
    if not data["entries"]:
        lines.append("هنوز هیچ پرونده‌ای در دنیای سیاه ثبت نشده.")
    if data["my_rank"]:
        lines += ["", f"📍 رتبه تو: <b>{data['my_rank']}</b> از {data['total']}"]
    await safe_show(callback.message, "\n".join(lines), competition_hub_menu(callback.from_user.id))
    await safe_answer(callback)


@router.callback_query(F.data.startswith("dw:recruits"))
async def dark_world_recruits(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    async with async_session() as session:
        ok, reason, snapshot = await _snapshot(session, callback.from_user.id)
    if not ok:
        await safe_answer(callback, reason, show_alert=True)
        return
    profile = snapshot["profile"]
    owned = {str(row.recruit_key) for row in snapshot["recruits"]}
    lines = [
        "👥 <b>شبکه نیروهای NPC</b>", "",
        "این نیروهای غیرکاربر دائمی‌اند و اثرشان خودکار روی همه عملیات‌ها اعمال می‌شود.",
        "استخدام کاربران واقعی بخش مستقلی است: کارفرما کار تعریف می‌کند، کاربر دیگر انجامش می‌دهد و دستمزد می‌گیرد.", "",
    ]
    for key in D.RECRUIT_ORDER:
        recruit = D.RECRUITS[key]
        status = "✅ استخدام‌شده" if key in owned else f"💵 {int(recruit['cost']):,} · نیاز {int(recruit['required_influence']):,} نفوذ"
        lines.append(f"{recruit['icon']} <b>{recruit['name']}</b> — {status}\n   {recruit['description']}")
    await safe_show(
        callback.message, "\n".join(lines),
        recruits_menu(owned, int(profile.influence or 0), callback.from_user.id),
    )
    await safe_answer(callback)


@router.callback_query(F.data.startswith("dw:hire:"))
async def dark_world_hire(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    if click_debounce(callback.from_user.id, "dark_world_hire", 3.0):
        await safe_answer(callback, "کلیک قبلی در حال پردازش است.")
        return
    recruit_key = _base(callback).split(":")[2]
    try:
        async with economic_operation(callback.from_user.id, f"dw-hire:{callback.id}"):
            async with async_session() as session:
                ok, message = await DS.hire_recruit(session, callback.from_user.id, recruit_key)
    except (BusyOperation, DuplicateOperation):
        await safe_answer(callback, "استخدام قبلاً اجرا شده یا عملیات دیگری در حال پردازش است.", show_alert=True)
        return
    if not ok:
        await safe_answer(callback, message, show_alert=True)
        return
    await safe_show(callback.message, message, back_to_hub(callback.from_user.id))
    await safe_answer(callback, "استخدام انجام شد")


@router.callback_query(F.data.startswith("dw:userhire"))
async def dark_world_user_hiring_design(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    text = (
        "🤝 <b>استخدام کاربران — بازار کار دنیای سیاه</b>\n\n"
        "منظور این بخش استخدام بازیکن واقعی است، نه NPC: کارفرما یک کار مجاز درون‌بازی، مهلت، "
        "دستمزد ثابت و در صورت نیاز سهم غنیمت تعریف می‌کند. مبلغ از ابتدا در escrow قفل می‌شود؛ "
        "کاربر دیگر قرارداد را می‌پذیرد، عمل محدودِ سرورمحور را انجام می‌دهد و پس از ثبت نتیجه درآمد می‌گیرد.\n\n"
        "• وضعیت‌ها: باز، پذیرفته‌شده، درحال اجرا، تحویل، تسویه، شکست، لغو، انقضا و اختلاف\n"
        "• درآمد کارگر: دستمزد ثابت + پاداش عملکرد + سهم غنیمت\n"
        "• اعتماد دوطرفه، سابقه، نرخ موفقیت، مهلت و جریمه فسخ\n"
        "• ضدتقلب: ممنوعیت self-hire، سقف روزانه، تشخیص قرارداد صوری و ضدپول‌شویی\n"
        "• کارگر هرگز به حساب یا session کارفرما دسترسی نمی‌گیرد.\n\n"
        "این بازار اکنون در مرحله ۸۷.۵ فعال است؛ از دکمهٔ «بازار کار کاربران» در هاب وارد شو."
    )
    await safe_show(callback.message, text, back_to_hub(callback.from_user.id))
    await safe_answer(callback)


@router.callback_query(F.data.startswith("dw:story"))
async def dark_world_story(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    text = (
        "📖 <b>پرونده روایی — به‌زودی</b>\n\n"
        "فصل داستانی دنیای سیاه با جناح‌ها، انتخاب‌های برگشت‌ناپذیر، خیانت و پایان‌های متفاوت "
        "در مرحله ۸۷.۹ فعال می‌شود. انتخاب‌های عملیاتی فعلی، زیرساخت همین روایت هستند."
    )
    await safe_show(callback.message, text, back_to_hub(callback.from_user.id))
    await safe_answer(callback)


@router.callback_query(F.data.startswith("dw:rules"))
async def dark_world_rules(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    text = (
        "📜 <b>قوانین فصل صفر</b>\n\n"
        f"• ورود از لول {D.ACCESS_LEVEL} ممکن است. سقف عمومی برای اولین بار به لول {leveling.MAX_LEVEL} رسیده است.\n"
        "• عملیات سخت‌تر، XP عمومی و XP سیاه بسیار بیشتری می‌دهد.\n"
        "• شکست نیز XP آموزشی دارد، اما هزینه ورود از دست می‌رود و نفوذ کم می‌شود.\n"
        "• گرمای بالاتر از ۲۰ شانس را کم می‌کند؛ از ۴۰ تهدید تعقیب می‌سازد و از ۸۰ عملیات تازه قفل می‌شود.\n"
        "• برد پیاپی تا ۳۰٪ غنیمت بیشتر می‌دهد؛ شکست زنجیره را صفر می‌کند.\n"
        "• نتیجه عملیات زمان‌دار هنگام شروع و هر انتخاب پرونده تعاملی هنگام کلیک ثبت می‌شود؛ ری‌استارت باعث reroll نیست.\n"
        "• رنک داخلی از رنکینگ عمومی بازی مستقل است."
    )
    await safe_show(callback.message, text, back_to_hub(callback.from_user.id))
    await safe_answer(callback)


@router.callback_query(F.data.startswith("dw:locked"))
async def dark_world_locked(callback: CallbackQuery) -> None:
    if await ensure_owner(callback):
        await safe_answer(callback, "🔒 ابتدا نفوذ لازم را از عملیات‌های بازشده به دست بیاور.", show_alert=True)


@router.callback_query(F.data.startswith("dw:owned"))
async def dark_world_owned(callback: CallbackQuery) -> None:
    if await ensure_owner(callback):
        await safe_answer(callback, "این نیرو قبلاً در شبکه تو استخدام شده است.")
