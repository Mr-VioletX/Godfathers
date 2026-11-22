# -*- coding: utf-8 -*-
"""🆕 مرحله ۳۱ — زمان‌بندِ «فرصت‌طلب» برای هاستِ اشتراکی.

مشکل: روی هاست، ربات با وب‌هوک کار می‌کند و هیچ پردازه‌ی همیشه‌روشنی وجود ندارد،
پس حلقه‌های پس‌زمینه (اخبارِ روزانه، جاسوسی، انقضای چت) اجرا نمی‌شوند. فایلِ
cron_ticks.py فقط در صورتی کار می‌کند که کاربر در cPanel یک Cron Job ساخته باشد؛
اگر نساخته باشد «اخبارِ روزانه» هرگز منتشر نمی‌شود — دقیقاً همان چیزی که گزارش شد.

راهکار: هر بار که آپدیتی از تلگرام می‌رسد، این ماژول (با خفه‌کنِ زمانی) بررسی
می‌کند آیا کارِ زمان‌بندی‌شده‌ای سررسید شده یا نه و فقط در آن صورت اجرایش می‌کند.
وضعیت در همان cron_state.json ذخیره می‌شود، پس با cron_ticks.py دوباره‌کاری نمی‌شود.
"""
from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime

log = logging.getLogger(__name__)

_BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
STATE_PATH = os.path.join(_BASE, "cron_state.json")

MIN_GAP_SECONDS = 120.0    # حداکثر هر ۲ دقیقه یک‌بار بررسی شود
_last_check = 0.0
_busy = False


def _load() -> dict:
    try:
        with open(STATE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save(state: dict) -> None:
    try:
        with open(STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(state, f)
    except Exception as e:
        log.warning("host_scheduler: state save failed: %s", e)


async def maybe_run(bot) -> None:
    """اگر وقتش رسیده باشد کارهای سررسیدشده را اجرا می‌کند؛ وگرنه فوراً برمی‌گردد."""
    global _last_check, _busy
    now = time.time()
    if _busy or (now - _last_check) < MIN_GAP_SECONDS:
        return
    _last_check = now
    _busy = True
    try:
        await _run_due(bot)
    except Exception as e:
        log.warning("host_scheduler: run failed: %s", e)
    finally:
        _busy = False


async def _run_due(bot) -> None:
    from app.data import news as N

    try:
        from app.utils.stderr_cleanup import maybe_cleanup_stderr

        cleanup = maybe_cleanup_stderr()
        if cleanup.get("cleaned_files"):
            log.info(
                "host_scheduler: stderr maintenance cleared %s file(s), %s byte(s)",
                cleanup["cleaned_files"],
                cleanup.get("removed_bytes", 0),
            )
    except Exception as exc:
        log.warning("host_scheduler: stderr maintenance failed: %s", exc)

    state = _load()
    utc_now = datetime.utcnow()
    teh = N.now_tehran(utc_now)
    today = teh.strftime("%Y-%m-%d")
    changed = False

    # --- اخبارِ روزانه: یک‌بار در روز، بعد از ساعتِ N.POST_HOUR به وقتِ تهران ---
    if teh.hour >= N.POST_HOUR and state.get("last_news_date") != today:
        try:
            from app.services.news_ticker import news_tick_once

            posted = await news_tick_once(bot)
        except Exception as exc:
            posted = False
            log.warning("host_scheduler: news tick raised unexpectedly: %s", exc)
        if posted:
            state["last_news_date"] = today
            changed = True
            _save(state)
            log.info("host_scheduler: daily news posted for %s", today)
        else:
            log.warning("host_scheduler: daily news failed; it remains due for retry")

    # --- جاسوسی و انقضای چت: سبک و idempotent ---
    try:
        from app.services.spy_ticker import spy_tick_once
        await spy_tick_once(bot)
    except Exception as e:
        log.debug("host_scheduler: spy tick failed: %s", e)
    try:
        from app.services.chat_ticker import chat_tick_once
        await chat_tick_once(bot)
    except Exception as e:
        log.debug("host_scheduler: chat tick failed: %s", e)

    # --- بکاپ خودکار دیتابیس (v1.7.2) ---
    try:
        from app.services.backup_service import maybe_auto_backup
        await maybe_auto_backup(bot)
    except Exception as e:
        log.debug("host_scheduler: backup tick failed: %s", e)

    if changed:
        _save(state)


async def _run_mayor_demands(bot) -> None:
    try:
        from app.services import city_ticker
        fn = getattr(city_ticker, "maybe_mayor_demands", None)
        if fn is not None:
            await fn(bot)
    except Exception:
        pass
