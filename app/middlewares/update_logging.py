# -*- coding: utf-8 -*-
"""🆕 v1.8.2.0 — لاگِ دقیقِ آپدیت‌ها و خطاها برای پیداکردنِ باگ.

دو لایه:

۱) UpdateLoggingMiddleware — بیرونی‌ترین میدل‌ور روی message و callback_query:
   برای هر آپدیت یک خط «⬅️ شروع» و یک خط «➡️ پایان (مدت)» در updates.log می‌نویسد:
   آیدی/یوزرنیمِ کاربر، چت، متنِ پیام یا callback_data (تا ۱۲۰ کاراکتر)، وضعیتِ FSM،
   و مدتِ پردازش. پس برای بازتولیدِ باگ دقیقاً می‌بینی کاربر چه کلیک‌هایی را با چه
   ترتیبی زده است. اگر هندلر خطا بدهد، یک خطِ 💥 با همان متن در updates.log می‌نشیند
   (بدونِ traceback — آن در لایه‌ی دوم می‌آید تا تکراری نباشد).

۲) log_unhandled_error — هندلرِ dp.errors: هر استثنایِ گرفته‌نشده با tracebackِ کامل
   + متنِ آپدیت (کاربر/چت/دیتا) در errors.log و bot.log ثبت می‌شود.

نصب در bot.py:
    dp.message.outer_middleware(UpdateLoggingMiddleware())        # قبل از بقیه
    dp.callback_query.outer_middleware(UpdateLoggingMiddleware())
    dp.errors.register(log_unhandled_error)
"""
from __future__ import annotations

import logging
import time
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, ErrorEvent, Message, Update

ulog = logging.getLogger("godfather.updates")
elog = logging.getLogger("godfather.errors")

_MAX = 120  # سقفِ طولِ متن/دیتا در لاگ تا لاگ شلوغ نشود


def _clip(text: Any) -> str:
    s = str(text or "").replace("\n", " ⏎ ")
    return s if len(s) <= _MAX else s[: _MAX - 1] + "…"


def _user_tag(user) -> str:
    if user is None:
        return "user=?"
    un = f"@{user.username}" if getattr(user, "username", None) else ""
    name = getattr(user, "full_name", "") or ""
    return f"uid={user.id}{un}({name})"


def _describe(event) -> str:
    """خلاصه‌ی یک‌خطیِ آپدیت — چه کسی، کجا، چه چیزی."""
    if isinstance(event, CallbackQuery):
        chat = getattr(event.message, "chat", None) if getattr(event, "message", None) else None
        return (
            f"CLICK data=«{_clip(getattr(event, 'data', None))}» {_user_tag(getattr(event, 'from_user', None))} "
            f"chat={getattr(chat, 'id', '?')}"
        )
    chat = getattr(event, "chat", None)
    kind = "text" if getattr(event, "text", None) else ("photo" if getattr(event, "photo", None) else getattr(event, "content_type", "?"))
    return (
        f"MSG[{kind}] «{_clip(getattr(event, 'text', None) or getattr(event, 'caption', None) or '')}» "
        f"{_user_tag(getattr(event, 'from_user', None))} chat={getattr(chat, 'id', '?')}"
    )


async def _fsm_state(data: dict) -> str:
    """وضعیتِ فعلیِ FSM کاربر (اگر در میانه‌ی یک عملیاتِ چندمرحله‌ای است)."""
    try:
        state = data.get("state")
        if state is None:
            return "-"
        cur = await state.get_state()
        return str(cur) if cur else "-"
    except Exception:
        return "?"


class UpdateLoggingMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Any, dict], Awaitable[Any]],
        event: Any,
        data: dict,
    ) -> Any:
        desc = _describe(event)
        state_str = await _fsm_state(data)
        ulog.info("⬅️ %s | state=%s", desc, state_str)
        started = time.monotonic()
        try:
            result = await handler(event, data)
        except Exception:
            # فقط نشانه‌گذاری در ردِ آپدیت‌ها؛ tracebackِ کامل در log_unhandled_error می‌آید.
            ulog.error("💥 خطا حینِ پردازش | %s | state=%s", desc, state_str)
            raise
        took_ms = (time.monotonic() - started) * 1000
        ulog.info("➡️ OK (%.0fms) | %s", took_ms, desc)
        if took_ms > 3000:
            elog.warning("🐢 آپدیتِ کند (%.0fms): %s", took_ms, desc)
        return result


# ---------------------------------------------------------------------------
# لایه‌ی دوم: ثبتِ کاملِ خطاهای گرفته‌نشده (traceback + متنِ آپدیت)
# ---------------------------------------------------------------------------
def _update_context(update: Update) -> str:
    """متنِ یک‌خطیِ آپدیت برای کنارِ traceback."""
    try:
        ev = update.message or update.edited_message or update.callback_query or None
        if ev is None:
            return f"update_id={update.update_id} (نوعِ دیگر)"
        return f"update_id={update.update_id} | {_describe(ev)}"
    except Exception:
        return f"update_id={getattr(update, 'update_id', '?')}"


async def log_unhandled_error(event: ErrorEvent) -> None:
    """هر استثنایی که به dispatcher برسد اینجا با جزئیاتِ کامل ثبت می‌شود."""
    ctx = _update_context(event.update) if event.update else "update=?"
    elog.error(
        "Unhandled exception while processing %s",
        ctx,
        exc_info=event.exception,
    )
