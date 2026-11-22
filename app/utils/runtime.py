# -*- coding: utf-8 -*-
"""🆕 مرحله ۳۱ — تنظیماتِ زمانِ اجرا برای هاستِ اشتراکی.

چرا؟ در stderr.log بیش از ۹۰۰ بار این خطا دیده شد:
    RuntimeError: can't start new thread
منشأ: aiogram هر فیلتر/هندلرِ «غیرِ async» را با loop.run_in_executor در یک نخِ
تازه اجرا می‌کند. ThreadPoolExecutor پیش‌فرضِ پایتون تا (cpu+4) نخ می‌سازد و روی
هاستِ اشتراکی (CloudLinux/LVE) سقفِ نخِ حساب زود پر می‌شود؛ نتیجه: پردازشِ آپدیت
شکست می‌خورد، تلگرام همان آپدیت را دوباره می‌فرستد و کاربر «کندی» و «دستور دریافت
نشد» می‌بیند.

راهکار: یک اجراکننده‌ی کوچکِ ثابت نصب می‌کنیم تا هرگز از این سقف عبور نکنیم.
"""
from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor

log = logging.getLogger(__name__)

MAX_WORKERS = 4
_executor: ThreadPoolExecutor | None = None
_installed = False


def install() -> None:
    """یک‌بار در طولِ عمرِ پردازه، اجراکننده‌ی محدود را روی حلقه نصب می‌کند."""
    global _executor, _installed
    if _installed:
        return
    _installed = True
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        _installed = False
        return
    try:
        _executor = ThreadPoolExecutor(
            max_workers=MAX_WORKERS, thread_name_prefix="gf"
        )
        loop.set_default_executor(_executor)
        log.info("runtime: default executor capped at %d threads", MAX_WORKERS)
    except Exception as e:   # pragma: no cover
        log.warning("runtime: could not install executor: %s", e)
