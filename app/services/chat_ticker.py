# app/services/chat_ticker.py
"""حلقه‌یِ پس‌زمینه‌یِ چت‌مود (مرحله ۱۳.۶).

هر چرخه: درخواست‌هایِ چتِ معلقی که مهلتِ ۵ دقیقه‌یِ آن‌ها گذشته →
«expired» می‌شوند و به درخواست‌دهنده پیامِ «مخاطب فعال نیست» + دکمه‌یِ گذاشتنِ پیام می‌رود.
"""
import asyncio
import logging
from datetime import datetime

from aiogram import Bot
from sqlalchemy import select

from app.database.engine import async_session
from app.keyboards.chat_menu import offline_leave_menu
from app.models.chat import ChatRequest

log = logging.getLogger(__name__)

CHAT_TICK_SECONDS = 30


async def chat_tick_once(bot: Bot) -> None:
    """یک اجرایِ تکیِ منطقِ انقضایِ درخواست‌هایِ چت — هم از حلقه‌ی Polling و هم از cron_ticks.py (هاستِ اشتراکی) صدا زده می‌شود."""
    try:
        now = datetime.utcnow()
        async with async_session() as session:
            reqs = (await session.execute(
                select(ChatRequest).where(
                    ChatRequest.status == "pending",
                    ChatRequest.expires_at.is_not(None),
                    ChatRequest.expires_at <= now,
                )
            )).scalars().all()
            for r in reqs:
                r.status = "expired"
            await session.commit()
            pending = [(r.requester_id, r.target_id) for r in reqs]
        for requester_id, target_id in pending:
            try:
                await bot.send_message(
                    requester_id,
                    "😴 مخاطب در ۵ دقیقه پاسخ نداد. می‌توانی یک پیام برایش بگذاری.",
                    reply_markup=offline_leave_menu(target_id, requester_id),
                )
            except Exception:
                pass
    except Exception as e:
        log.exception("chat_tick_once failed: %s", e)


async def chat_request_expiry_loop(bot: Bot) -> None:
    """تا وقتی ربات به‌صورتِ Polling روشن است، هر CHAT_TICK_SECONDS انقضایِ درخواست‌ها را بررسی می‌کند.
    روی هاستِ اشتراکی (Passenger/Webhook) این حلقه اجرا نمی‌شود؛ به‌جایش cron_ticks.py از chat_tick_once استفاده می‌کند."""
    while True:
        await asyncio.sleep(CHAT_TICK_SECONDS)
        await chat_tick_once(bot)
