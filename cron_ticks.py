# -*- coding: utf-8 -*-
"""cron_ticks.py -- مخصوص هاست اشتراکی (مرحله 22، مسیر A).

چرا این فایل لازم است؟
-----------------------
روی هاست اشتراکی، ربات دیگر با Polling اجرا نمی‌شود؛ هر آپدیت تلگرام از طریق
passenger_wsgi.py و در یک درخواست HTTP کوتاه پردازش می‌شود. یعنی دیگر یک
پردازه‌ی همیشه‌روشن نداریم که بتواند این حلقه‌های پس‌زمینه را اجرا کند:
  - assistant_reminder_loop   (یادآوری دستیار، هر 24 ساعت)
  - spy_ticker_loop           (رسیدگی به جاسوس‌ها، هر ~1 دقیقه)
  - chat_request_expiry_loop  (انقضای درخواست‌های چت، هر ~30 ثانیه)
  - news_daily_loop            (اخبار روزانه، ساعت 20:00 تهران)

راه‌حل: این اسکریپت را با cPanel -> Cron Jobs هر 5 دقیقه اجرا کن تا همان کارها
به‌صورت "یک‌ضربه‌ای" (tick) انجام شوند. cron_state.json کنار همین فایل، زمان
آخرین اجرای موفق هر کار را نگه می‌دارد تا یادآوری/اخبار تکراری ارسال نشود.

نحوه‌ی افزودن Cron Job در cPanel (هر 5 دقیقه):
  */5 * * * * /home/USERNAME/virtualenv/PATH/3.x/bin/python /home/USERNAME/APP_PATH/cron_ticks.py >> /home/USERNAME/APP_PATH/cron.log 2>&1
(مسیر دقیق venv را از بخش "Setup Python App" در cPanel کپی کن.)
"""
import asyncio
import json
import logging
import os
from datetime import datetime, timedelta

log = logging.getLogger("cron_ticks")

from bot import bot, ensure_started
from app.services.assistant_ticker import assistant_tick_once
from app.services.spy_ticker import spy_tick_once
from app.services.chat_ticker import chat_tick_once
from app.services.news_ticker import news_tick_once
from app.services.alliance_ticker import alliance_tick_once  # 🆕 v1.7.9.1
from app.services.league_ticker import league_tick_once, LEAGUE_WEEKDAY, LEAGUE_HOUR
from app.data import news as N
from app.services.ranked_battle_finalizer import finalize_finished_ranked_battles
from app.database.engine import async_session

STATE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cron_state.json")
ASSISTANT_EVERY_SECONDS = 24 * 60 * 60


def _load_state() -> dict:
    try:
        with open(STATE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_state(state: dict) -> None:
    try:
        with open(STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(state, f)
    except Exception as e:
        log.warning("cron_state save failed: %s", e)


async def _run() -> None:
    from app.utils.stderr_cleanup import maybe_cleanup_stderr

    cleanup = maybe_cleanup_stderr()
    if cleanup.get("cleaned_files"):
        log.info(
            "stderr maintenance cleared %s file(s), %s byte(s)",
            cleanup["cleaned_files"],
            cleanup.get("removed_bytes", 0),
        )
    await ensure_started()
    state = _load_state()
    now = datetime.utcnow()

    # جاسوسی و انقضای چت: اجرای هر بار بی‌خطر است (idempotent، بر اساس وضعیت دیتابیس)
    await spy_tick_once(bot)
    await chat_tick_once(bot)
    try:
        from app.services.backup_service import maybe_auto_backup
        await maybe_auto_backup(bot)
    except Exception as e:
        log.warning("backup tick failed: %s", e)
    async with async_session() as session:
        # 🆕 v1.7.6.4 — گزارشِ پایانِ نبرد به دو طرف پیام می‌شود
        finalized = await finalize_finished_ranked_battles(session, bot=bot)
        if finalized:
            await session.commit()
            log.info("auto-finalized %s ranked battles", finalized)

    # 🆕 v1.7.9.1 — نبردهای اتحادیه + تولیدِ خودکار + اشتراکِ عضویت
    try:
        await alliance_tick_once(bot)
    except Exception as e:
        log.warning("alliance tick failed: %s", e)

    # 🆕 v1.7.9.7 — مزایده/صف پرداخت بازار نقل‌وانتقال
    try:
        from app.services.football_market import tick as _fmtick
        async with async_session() as _ms:
            await _fmtick(_ms, bot)
            await _ms.commit()
    except Exception as e:
        log.warning("football market tick failed: %s", e)

    # 🆕 v1.7.9.9 — لیگ جمعه (اگر جمعه است اجرا می‌شود)
    try:
        from app.services.football_friday import friday_tick as _ftick
        async with async_session() as _fs:
            await _ftick(_fs, bot)
            await _fs.commit()
    except Exception as e:
        log.warning("friday league tick failed: %s", e)

    # 🆕 v1.7.10.0 — پیشروش بازی‌های زنده (۱۰ دقیقه‌ای)
    try:
        from app.services.football_live import tick as _flivetick
        async with async_session() as _ls:
            await _flivetick(_ls, bot)
            await _ls.commit()
    except Exception as e:
        log.warning("football live tick failed: %s", e)

    # 🆕 v1.7.10.0 — لیگ قهرمانان دوشنبه
    try:
        from app.services.football_ucl import advance_ucl as _ucladv
        async with async_session() as _us:
            await _ucladv(_us, bot)
            await _us.commit()
    except Exception as e:
        log.warning("ucl tick failed: %s", e)

    # یادآوری دستیار: فقط هر 24 ساعت یک‌بار
    last_assistant = state.get("last_assistant")
    should_run_assistant = True
    if last_assistant:
        try:
            should_run_assistant = (now - datetime.fromisoformat(last_assistant)) >= timedelta(seconds=ASSISTANT_EVERY_SECONDS)
        except Exception:
            should_run_assistant = True
    if should_run_assistant:
        await assistant_tick_once(bot)
        state["last_assistant"] = now.isoformat()

    # اخبار روزانه: فقط یک‌بار در روز، بعد از ساعت 20:00 تهران
    teh = N.now_tehran(now)
    today_label = teh.strftime("%Y-%m-%d")
    if teh.hour >= N.POST_HOUR and state.get("last_news_date") != today_label:
        if await news_tick_once(bot):
            state["last_news_date"] = today_label
        else:
            log.warning("daily news failed; date not marked so the next cron run retries")

    # لیگِ حذفیِ هفتگی: فقط جمعه، بعد از ساعت 12:00 تهران، یک‌بار در هفته
    week_label = f"{teh.isocalendar()[0]}-W{teh.isocalendar()[1]}"
    if teh.weekday() == LEAGUE_WEEKDAY and teh.hour >= LEAGUE_HOUR and state.get("last_league_week") != week_label:
        await league_tick_once(bot)
        state["last_league_week"] = week_label

    _save_state(state)
    log.info("cron_ticks run finished at %s UTC", now.isoformat())


if __name__ == "__main__":
    asyncio.run(_run())
