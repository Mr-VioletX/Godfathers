# app/services/spy_ticker.py
"""حلقهٔ پس‌زمینهٔ جاسوسی (مرحله ۱۳) — همان الگوی assistant_ticker.

هر چرخه:
  ۱) جاسوس‌هایِ فعالی که زمانِ گزارش‌شان رسیده → یا دستگیر می‌شوند
     یا گزارش + غارت تحویل می‌دهند.
  ۲) جاسوس‌هایِ دستگیرِ بدونِ غرامت پس از ۴۸ ساعت → کشته می‌شوند (جریمه).
  ۳) جریمهٔ مرگ (۱۰٪ درآمدِ روزانه تا ۳ روز) روزانه به هدف منتقل می‌شود.
"""
import asyncio
import logging
import random
from datetime import datetime, timedelta

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError
from sqlalchemy import select

from app.data.espionage import (
    DEATH_PENALTY_DAYS,
    DEATH_PENALTY_PCT,
    RANSOM_DEADLINE_HOURS,
    capture_pct,
    loot_pct,
    mission_seconds,
    report_accuracy,
)
from app.database.engine import async_session
from app.models.player import Player
from app.models.spy import Spy
from app.models.player_stats import get_or_create_stats
from app.services import spy_service

log = logging.getLogger(__name__)

SPY_TICK_SECONDS = 60   # هر ۱ دقیقه وضعیت را بررسی می‌کند


async def _send(bot: Bot, tg_id: int, text: str) -> None:
    try:
        await bot.send_message(tg_id, text)
    except TelegramForbiddenError:
        pass
    except Exception as e:
        log.warning("spy notify failed for %s: %s", tg_id, e)


async def _process_reports(bot: Bot, session, now: datetime) -> None:
    spies = (await session.execute(
        select(Spy).where(Spy.status == "active", Spy.next_report_at <= now)
    )).scalars().all()
    for spy in spies:
        reduction = await spy_service.owner_capture_reduction(session, spy.owner_id)
        chance = capture_pct(spy.level, reduction)
        target = await spy_service.get_player(session, spy.target_id)
        target_name = target.name if target else str(spy.target_id)

        if random.uniform(0, 100) < chance:
            # دستگیری
            spy.status = "captured"
            spy.captured_at = now
            spy.next_report_at = None
            await session.commit()
            await _send(
                bot, spy.owner_id,
                f"🔒 جاسوسِ #{spy.slot} تو هنگامِ مأموریت رویِ <b>{target_name}</b> دستگیر شد!\n"
                f"تا <b>{RANSOM_DEADLINE_HOURS} ساعت</b> فرصت داری غرامت بدهی وگرنه کشته می‌شود."
            )
            if target:
                await _send(
                    bot, spy.target_id,
                    "🚨 یک جاسوس در قلمروت دستگیر شد! کسی دارد تو را زیرِ نظر می‌گیرد."
                )
            continue

        # گزارشِ موفق + غارت
        acc_bonus = await spy_service.owner_accuracy_bonus(session, spy.owner_id)
        accuracy = report_accuracy(spy.level, acc_bonus)
        intel = await spy_service.gather_intel(session, spy.target_id)
        report = spy_service.format_intel(intel, accuracy)

        loot = int(intel["daily_income"] * loot_pct(spy.level) / 100)
        if target and loot > 0:
            loot = min(loot, target.cash)
            target.cash -= loot
            owner = await spy_service.get_player(session, spy.owner_id)
            if owner:
                owner.cash += loot

        spy.last_intel = report
        spy.next_report_at = now + timedelta(seconds=mission_seconds(spy.level))
        # شمارنده رسمی رنکینگ و القاب: فقط گزارش موفق (نه دستگیری) ثبت می‌شود.
        stats = await get_or_create_stats(session, spy.owner_id)
        stats.spy_success = int(stats.spy_success or 0) + 1
        try:
            from app.services.titles import evaluate_titles
            await evaluate_titles(session, spy.owner_id)
        except Exception:
            # خرابی ارزیابی لقب نباید ثبت موفقیت جاسوسی را متوقف کند.
            pass
        await session.commit()

        loot_line = f"\n\n💰 غارتِ این چرخه: <b>{loot:,}</b>$" if loot > 0 else ""
        await _send(bot, spy.owner_id, f"{report}{loot_line}")


async def _process_deaths(bot: Bot, session, now: datetime) -> None:
    deadline = now - timedelta(hours=RANSOM_DEADLINE_HOURS)
    captured = (await session.execute(
        select(Spy).where(Spy.status == "captured", Spy.captured_at <= deadline)
    )).scalars().all()
    notify: list[int] = []
    for spy in captured:
        spy.status = "dead"
        # جریمهٔ مرگ برای صاحب: تا ۳ روز به هدف پرداخت می‌شود
        owner = await spy_service.get_player(session, spy.owner_id)
        if owner is not None and spy.target_id:
            owner.spy_penalty_until = now + timedelta(days=DEATH_PENALTY_DAYS)
            owner.spy_penalty_to = spy.target_id
            owner.spy_penalty_last_at = None
        notify.append(spy.owner_id)
    # ⚡ مرحله ۲۸ (سرعت): فقط یک commit برای همه‌ی ردیف‌ها
    if captured:
        await session.commit()
    for owner_id in notify:
        await _send(
            bot, owner_id,
            f"☠️ جاسوسِ #{spy.slot} به‌دلیلِ پرداخت‌نشدنِ غرامت کشته شد.\n"
            f"تا {DEATH_PENALTY_DAYS} روز روزانه {DEATH_PENALTY_PCT:.0f}٪ از درآمدت به هدف پرداخت می‌شود."
        )


async def _process_penalties(bot: Bot, session, now: datetime) -> None:
    players = (await session.execute(
        select(Player).where(Player.spy_penalty_until.is_not(None))
    )).scalars().all()
    dirty = False
    for p in players:
        if p.spy_penalty_until and p.spy_penalty_until <= now:
            p.spy_penalty_until = None
            p.spy_penalty_to = None
            p.spy_penalty_last_at = None
            dirty = True
            continue
        # یک بار در روز
        if p.spy_penalty_last_at and (now - p.spy_penalty_last_at) < timedelta(days=1):
            continue
        income = await spy_service.daily_income(session, p.tg_user_id)
        fee = int(income * DEATH_PENALTY_PCT / 100)
        fee = min(fee, p.cash)
        if fee > 0 and p.spy_penalty_to:
            p.cash -= fee
            beneficiary = await spy_service.get_player(session, p.spy_penalty_to)
            if beneficiary:
                beneficiary.cash += fee
                await _send(
                    bot, beneficiary.tg_user_id,
                    f"💰 غرامتِ جاسوسی: <b>{fee:,}</b>$ از کسی که جاسوسش را رویِ تو فرستاده بود دریافت کردی."
                )
        p.spy_penalty_last_at = now
        dirty = True
    # ⚡ مرحله ۲۸ (سرعت): یک commit برای کلِ حلقه
    if dirty:
        await session.commit()


async def spy_tick_once(bot: Bot) -> None:
    """یک اجرایِ تکیِ منطقِ جاسوسی — هم از حلقه‌ی Polling و هم از cron_ticks.py (هاستِ اشتراکی) صدا زده می‌شود."""
    try:
        now = datetime.utcnow()
        async with async_session() as session:
            await _process_reports(bot, session, now)
            await _process_deaths(bot, session, now)
            await _process_penalties(bot, session, now)
    except Exception as e:
        log.exception("spy_tick_once failed: %s", e)


async def spy_ticker_loop(bot: Bot):
    """تا وقتی ربات به‌صورتِ Polling روشن است (کامپیوترِ شخصی/VPS)، هر SPY_TICK_SECONDS وضعیتِ جاسوس‌ها را پیش می‌برد.
    روی هاستِ اشتراکی (Passenger/Webhook) این حلقه اجرا نمی‌شود؛ به‌جایش cron_ticks.py از spy_tick_once استفاده می‌کند."""
    while True:
        await asyncio.sleep(SPY_TICK_SECONDS)
        await spy_tick_once(bot)
