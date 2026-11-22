# app/services/assistant_ticker.py
"""حلقه‌ی یادآوریِ خودکارِ دستیار (اختیاری).

هر بازه‌ی مشخص (پیش‌فرض ۲۴ ساعت) به همه‌ی کسانی که دستیار دارند،
یک گزارشِ محرمانه در PVِ ربات می‌فرستد.
"""
import asyncio
import logging

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError
from sqlalchemy import select

from app.database.engine import async_session
from app.models.assistant import Assistant
from app.handlers.assistant import get_player, build_private_report

log = logging.getLogger(__name__)

REMINDER_EVERY_SECONDS = 24 * 60 * 60   # هر ۲۴ ساعت — دلخواه تغییرش بده


async def assistant_tick_once(bot: Bot) -> None:
    """یک اجرایِ تکیِ منطقِ یادآوری — هم از حلقه‌ی Polling و هم از cron_ticks.py (هاستِ اشتراکی) صدا زده می‌شود."""
    try:
        async with async_session() as session:
            assistants = (await session.execute(select(Assistant))).scalars().all()
            for a in assistants:
                player = await get_player(session, a.tg_user_id)
                if player is None:
                    continue
                text = await build_private_report(session, a, player)
                try:
                    await bot.send_message(
                        a.tg_user_id,
                        f"🔔 یادآوریِ {a.name}:\n\n{text}",
                    )
                except TelegramForbiddenError:
                    continue   # کاربر ربات را بلاک کرده یا PV را start نکرده
                except Exception as e:
                    log.warning("reminder failed for %s: %s", a.tg_user_id, e)
    except Exception as e:
        log.exception("assistant_tick_once failed: %s", e)


async def assistant_reminder_loop(bot: Bot):
    """تا وقتی ربات به‌صورتِ Polling روشن است (کامپیوترِ شخصی/VPS)، هر REMINDER_EVERY_SECONDS یک‌بار یادآوری می‌فرستد.
    روی هاستِ اشتراکی (Passenger/Webhook) این حلقه اجرا نمی‌شود؛ به‌جایش cron_ticks.py از assistant_tick_once استفاده می‌کند."""
    while True:
        await asyncio.sleep(REMINDER_EVERY_SECONDS)
        await assistant_tick_once(bot)