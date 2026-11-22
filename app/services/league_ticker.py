# -*- coding: utf-8 -*-
"""تیکرِ «لیگِ حذفیِ هفتگی» (فوتبال/بسکتبال) — مرحله ۲۹.

هر هفته، جمعه ساعتِ ۱۲:۰۰ به وقتِ تهران، تیم‌هایی که برای آن هفته ثبت‌نام کرده‌اند
(دکمهِ «🏆 ثبت‌نامِ لیگ» — هزینهِ S.LEAGUE_ENTRY_FEE) وارد یک تورنمنتِ حذفیِ خودکار
می‌شوند: باخت = حذف؛ اگر تعداد فرد باشد یک تیمِ تصادفی به‌جای استراحت دو مسابقه با
حریفِ رباتی بازی می‌کند و فقط با بردنِ هر دو صعود می‌کند. قهرمانِ نهایی جایزهِ نقدی
و امتیازِ پاداش می‌گیرد و نتیجه به او پیام می‌شود. ثبت‌نام‌ها بعد از هر اجرا ریست
می‌شوند و باید برای هفتهِ بعد دوباره (و جداگانه برای هر رشته) ثبت‌نام کرد.
الگوی حلقه همانندِ news_ticker است.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

from aiogram.exceptions import TelegramForbiddenError

from app.data import sports as S
from app.data import news as N   # برای now_tehran (همان منطقِ منطقهِ زمانیِ تهران)
from app.database.engine import async_session
from app.services import sports_service as svc

log = logging.getLogger(__name__)

LEAGUE_WEEKDAY = 4     # جمعه (دوشنبه=۰ ... یکشنبه=۶ در پایتون، همانندِ WEEKLY_EVENTS در app/data/sports.py)
LEAGUE_HOUR = 12
LEAGUE_MINUTE = 0


def seconds_until_next_league_tick(now_utc=None) -> int:
    """ثانیه تا جمعهِ بعدی ساعتِ ۱۲:۰۰ به وقتِ تهران."""
    teh = N.now_tehran(now_utc)
    target = teh.replace(hour=LEAGUE_HOUR, minute=LEAGUE_MINUTE, second=0, microsecond=0)
    days_ahead = (LEAGUE_WEEKDAY - teh.weekday()) % 7
    if days_ahead == 0 and teh >= target:
        days_ahead = 7
    target = target + timedelta(days=days_ahead)
    delta = target - teh
    return max(60, int(delta.total_seconds()))


async def _notify(bot, tg_id: int, text: str) -> None:
    try:
        await bot.send_message(tg_id, text)
    except TelegramForbiddenError:
        pass
    except Exception as e:
        log.warning("league notify failed for %s: %s", tg_id, e)


async def _run_once(bot) -> None:
    async with async_session() as session:
        for sport in S.TEAM_SPORTS:
            result = await svc.run_weekly_league(session, sport)
            champ = result.get("champion")
            if champ:
                await _notify(
                    bot, champ["uid"],
                    f"🏆 <b>قهرمانِ لیگِ حذفیِ این هفته ({S.SPORT_LABEL[sport]}) شدی!</b>\n"
                    f"از میانِ {result['participants']} تیمِ ثبت‌نام‌شده در {result['rounds']} دور صعود کردی و قهرمان شدی.\n"
                    f"💰 جایزه: +{S.LEAGUE_CHAMPION_PRIZE:,}$  |  ⭐ +{S.LEAGUE_CHAMPION_BONUS_POINTS} امتیاز\n\n"
                    "برای شرکت در لیگِ هفتهِ بعد دوباره از دکمهِ «🏆 ثبت‌نامِ لیگ» استفاده کن."
                )


async def league_tick_once(bot) -> None:
    """یک اجرایِ تکیِ لیگِ حذفیِ هفتگی — از cron_ticks.py (هاستِ اشتراکی) صدا زده می‌شود.
    زمان‌بندیِ «فقط یک‌بار در هفته» را خودِ cron_ticks.py مدیریت می‌کند (مشابهِ news_tick_once)."""
    try:
        await _run_once(bot)
    except Exception as e:
        log.exception("league_tick_once failed: %s", e)


async def league_weekly_loop(bot) -> None:
    """حلقهِ اصلی (فقط Polling/VPS): تا جمعهِ ۱۲:۰۰ِ بعدی می‌خوابد، سپس لیگِ حذفی را اجرا می‌کند.
    روی هاستِ اشتراکی این حلقه اجرا نمی‌شود؛ به‌جایش cron_ticks.py از league_tick_once استفاده می‌کند."""
    while True:
        try:
            delay = seconds_until_next_league_tick()
        except Exception:
            delay = 3600
        await asyncio.sleep(delay)
        try:
            await _run_once(bot)
        except Exception as e:
            log.exception("league_weekly_loop error: %s", e)
            await asyncio.sleep(60)
