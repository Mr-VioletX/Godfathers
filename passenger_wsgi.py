# -*- coding: utf-8 -*-
"""passenger_wsgi.py -- نقطه ورود وب‌هوک برای هاست اشتراکی (Passenger) -- مرحله 22، مسیر A.

cPanel برای اجرای هر اپ پایتونی به دنبال دقیقا همین فایل (در ریشه پروژه) می‌گردد و
کالبک به نام application را پیدا می‌کند. هر آپدیت تلگرام (پیام/کلیک) به‌صورت
یک درخواست HTTP POST به اینجا می‌رسد (Webhook)، نه پردازشی همیشه‌روشن متفاوت از
دنیای Polling.

❗ قبل از بالا بردن:
  1) مقدار SECRET_TOKEN زیر را حفظ کن -- همین مقدار باید در فرمان
     setWebhook (مرحله 9 در صفحه) به‌عنوان secret_token ارسال شود.
  2) دامنه و SSL فعال لازم است (تلگرام فقط https را قبول می‌کند).

🆕 مرحله 32: پینگ بیدارباش (keep-alive). درخواست‌هایی که GET/HEAD هستند (تلگرام
فقط POST می‌فرستد) بدون لمس زدن دیتابیس/ربات فقط 200 برمی‌گردانند، تا یک
کرون‌جابِ ساده بتواند پروسه را هر چند دقیقه بیدار نگه دارد (مانع خواب‌کردنِ پروسه
توسط Passenger شود).
"""
import asyncio
import json
import logging
import threading

from aiogram.types import Update

from bot import bot, dp, ensure_started
from app.utils.logging_setup import setup_logging  # 🆕 v1.8.2.0

# 🆕 v1.8.2.0 — لاگ‌های گردش‌پذیرِ کامل (logs/)؛ idempotent است و با bot.py سازگار است
setup_logging()
log = logging.getLogger("passenger_wsgi")

# ⚠️ این را با همان مقداری که در دستور setWebhook استفاده کردی جایگزین کن (تولید‌شده با openssl rand -hex 32):
SECRET_TOKEN = "a04d572efbc5b6fb39660a47a3dea5ab7be2c40a5babe92be7e3c44fbb1b9ecf"

_started = False

# ⚠️ مرحلهٔ عملکرد (کندی دکمهای منوی شیشه‌ای):
# قبلاً هر درخواست (هر کلیک دکمه/پیام) با asyncio.run(...) پردازش می‌شد که هربار
# یک حلقهٔ رویداد (event loop) تازه می‌ساخت و بعد می‌بست. اتصال‌های دیتابیس (SQLAlchemy/aiosqlite)
# درون همان حلقهٔ اول ساخته می‌شوند و با بسته شدنش معتبر می‌مانند؛ در درخواستهای بعدی
# که حلقهٔ جدید می‌سازند, تلاش برای استفاده از کانکشن‌های قبلی با خطا مواجه می‌شود
# یا معلق می‌ماند (همان علتی که دکمههای منوی شیشه‌ای کند بودند).
# راه‌حل: یک حلقهٔ ثابت برای کل عمرِ پروسهٔ پسنجر بسازیم و برای هر درخواست فقط همان را با run_until_complete اجرا کنیم.
_loop_lock = threading.Lock()
_loop: asyncio.AbstractEventLoop | None = None


def _get_persistent_loop() -> asyncio.AbstractEventLoop:
    global _loop
    if _loop is None or _loop.is_closed():
        _loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_loop)
    return _loop


async def _ensure_started_once() -> None:
    global _started
    if not _started:
        await ensure_started()
        _started = True


async def _process(update_data: dict) -> None:
    await _ensure_started_once()
    update = Update.model_validate(update_data)
    await dp.feed_update(bot=bot, update=update)


def application(environ, start_response):
    """ورودی استاندارد WSGI که Passenger مستقیم اجرا می‌کند."""
    # 🆕 مرحله 32: پینگ بیدارباش - درخواستِ غیرپاستی را بدون لمس زدنِ ربات/دیتابیس جواب می‌دهد
    if environ.get("REQUEST_METHOD", "POST").upper() != "POST":
        start_response("200 OK", [("Content-Type", "text/plain; charset=utf-8")])
        return [b"alive"]

    try:
        header_token = environ.get("HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN", "")
        if header_token != SECRET_TOKEN:
            start_response("403 Forbidden", [("Content-Type", "text/plain; charset=utf-8")])
            return [b"forbidden"]

        length = int(environ.get("CONTENT_LENGTH", 0) or 0)
        body = environ["wsgi.input"].read(length) if length else b"{}"
        data = json.loads(body or b"{}")

        # یک حلقهٔ ثابت برای کل پروسه (نه asyncio.run که هربار یک حلقهٔ جدید می‌ساخت و اتصال‌های دیتابیس قبلی را باطل می‌کرد) —
        # رفعِ اصلیِ کندی دکمه‌های منوی شیشه‌ای.
        with _loop_lock:
            loop = _get_persistent_loop()
            loop.run_until_complete(_process(data))
    except Exception:
        log.exception("passenger_wsgi failed to process update")

    start_response("200 OK", [("Content-Type", "text/plain; charset=utf-8")])
    return [b"OK"]
