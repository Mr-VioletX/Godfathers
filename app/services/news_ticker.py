# -*- coding: utf-8 -*-
"""تیکرِ «اخبارِ روزانه» (مرحله ۲۰).

هر شب ساعتِ ۲۰:۰۰ به وقتِ تهران:
  ۱) آمارِ بازیکنان همگام و القابِ جدید ارزیابی می‌شود (و به اخبار افزوده می‌شود).
  ۲) خلاصه‌ی ۲۴ ساعتِ گذشته ساخته و در کانالِ اخبار (اگر تنظیم شده) منتشر می‌شود.
  ۳) برای کاربرانی که اولویتِ خبر دارند (اشتراکِ نقره‌ای/طلایی یا دستیارِ سطح ۴) خصوصی ارسال می‌شود.
الگوی حلقه همانندِ assistant_ticker است.
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timedelta

from aiogram.exceptions import TelegramForbiddenError
from sqlalchemy import select

from app.database.engine import async_session
from app.data import news as N

log = logging.getLogger(__name__)


async def _rollback_quietly(session) -> None:
    try:
        await session.rollback()
    except Exception as exc:
        log.error("news session rollback failed: %s", exc)


async def _run_in_fresh_session(job):
    """Run one database job in an isolated session with strict cleanup.

    A failed commit can leave SQLAlchemy in PREPARED/rollback-only state.  That
    session is never reused: rollback is attempted and the context is closed.
    """
    async with async_session() as session:
        try:
            result = await job(session)
            await session.commit()
            return result
        except BaseException:
            await _rollback_quietly(session)
            raise


async def _evaluate_all_and_collect_titles() -> None:
    """Evaluate title news in its own disposable transaction.

    This step is optional for the daily digest.  A failure is logged and rolled
    back, but its SQLAlchemy session can never poison the digest transaction.
    """

    async def _job(session) -> None:
        from app.models.player import Player
        from app.services import stats_bridge, news_service

        result = await session.execute(select(Player.tg_user_id))
        uids = [row[0] for row in result.all()]
        for uid in uids:
            new_titles = await stats_bridge.sync_and_evaluate(session, uid)
            if not session.is_active:
                raise RuntimeError(f"title evaluation left session inactive for uid={uid}")
            for title in new_titles or []:
                name = title.get("name") if isinstance(title, dict) else None
                if not name:
                    continue
                await news_service.add_news(
                    session,
                    category="title",
                    text=f"کاربری لقبِ ویژه‌ی «{name}» را کسب کرد.",
                    actor_id=uid,
                    commit=False,
                )

    try:
        await _run_in_fresh_session(_job)
    except Exception as exc:
        # Optional title collection must not prevent the independent digest job.
        log.exception("news title evaluation failed and was rolled back: %s", exc)


async def _priority_recipients(session) -> list[int]:
    """فهرستِ کاربرانی که باید خلاصه را خصوصی بگیرند (بدونِ تکرار)."""
    uids: set[int] = set()
    # اشتراکِ نقره‌ای/طلایی (news_priority)
    try:
        from app.models.subscription import Subscription
        from app.services import subscription_service
        res = await session.execute(select(Subscription.tg_user_id))
        for row in res.all():
            uid = row[0]
            if await subscription_service.has_news_priority(session, uid):
                uids.add(uid)
    except Exception:
        pass
    # دستیارِ سطح ۴ (هوشِ مصنوعیِ کامل)
    try:
        from app.models.assistant import Assistant
        res = await session.execute(
            select(Assistant.tg_user_id).where(Assistant.upgrade_level >= 4)
        )
        for row in res.all():
            uids.add(row[0])
    except Exception:
        pass
    return list(uids)


async def _post_once(bot) -> None:
    # 1) Optional title evaluation uses a completely separate session.
    await _evaluate_all_and_collect_titles()

    # 2) Build and persist the digest atomically in a fresh transaction.
    async def _prepare_digest(session):
        from app.services import news_service
        from app.models.news import NewsDigestPost

        since = datetime.utcnow() - timedelta(hours=N.DIGEST_LOOKBACK_HOURS)
        items = await news_service.items_since(session, since, only_unpublished=True)
        if items:
            pages = N.paginate_items(items)
            for item in items:
                item.published = True
        else:
            from app.services.game_digest import collect_live_events

            live = await collect_live_events(
                session,
                hours=N.DIGEST_LOOKBACK_HOURS,
                limit=N.MAX_ITEMS_IN_DIGEST,
            )
            pages = N.paginate_items(live) if live else [N.compile_digest([])]

        post = NewsDigestPost(
            pages_json=json.dumps(pages, ensure_ascii=False),
            item_count=len(items) if items else 0,
        )
        session.add(post)
        await session.flush()
        post_id = int(post.id)
        recipients = await _priority_recipients(session)
        if not session.is_active:
            raise RuntimeError("daily digest preparation left session inactive")
        return pages, post_id, recipients

    pages, post_id, recipients = await _run_in_fresh_session(_prepare_digest)

    from app.keyboards.news_menu import news_digest_menu
    text = pages[0]
    keyboard = news_digest_menu(post_id, 0, len(pages))

    # 3) Publish to the configured channel.
    channel_id = None
    try:
        async with async_session() as channel_session:
            from app.services import admin_service as adm

            channel_id = await adm.get_news_channel_id(channel_session)
    except Exception as exc:
        log.warning("news channel lookup failed: %s", exc)
    if not channel_id:
        try:
            from app.config import settings

            channel_id = getattr(settings, "news_channel_id", None)
        except Exception:
            channel_id = None
    if channel_id:
        try:
            await bot.send_message(channel_id, text, reply_markup=keyboard)
        except Exception as exc:
            log.warning("news channel post failed: %s", exc)

    # 4) Send private copies to priority recipients.
    for uid in recipients:
        try:
            await bot.send_message(uid, text, reply_markup=keyboard)
        except TelegramForbiddenError:
            continue
        except Exception as exc:
            log.debug("priority news delivery failed for uid=%s: %s", uid, exc)


async def news_tick_once(bot) -> bool:
    """Run one daily-news tick and report real success to its scheduler."""
    try:
        await _post_once(bot)
        return True
    except Exception as exc:
        log.exception("news_tick_once failed and will be retried: %s", exc)
        return False


async def news_daily_loop(bot) -> None:
    """حلقه‌ی اصلی (فقط Polling/VPS): تا ۲۰:۰۰ِ بعدی می‌خوابد، سپس خلاصه را منتشر می‌کند.
    روی هاستِ اشتراکی (Passenger/Webhook) این حلقه اجرا نمی‌شود؛ به‌جایش cron_ticks.py از news_tick_once استفاده می‌کند."""
    while True:
        try:
            delay = N.seconds_until_next_post()
        except Exception:
            delay = 3600
        await asyncio.sleep(delay)
        # Retry transient transaction/SQLite failures without waiting until tomorrow.
        for attempt in range(3):
            if await news_tick_once(bot):
                break
            await asyncio.sleep(60 * (attempt + 1))
