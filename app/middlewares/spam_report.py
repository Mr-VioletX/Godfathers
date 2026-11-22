# -*- coding: utf-8 -*-
from __future__ import annotations

import time
from collections import deque
from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message

WINDOW_SECONDS = 30
THRESHOLD = 5
COOLDOWN_SECONDS = 120
_HISTORY: dict[int, deque[tuple[float, str]]] = {}
_LAST_REPORT: dict[tuple[int, str], float] = {}


def _event_key(event) -> str | None:
    if isinstance(event, Message):
        if event.text:
            return "msg:" + event.text.strip()[:80]
        if event.content_type:
            return "msgtype:" + str(event.content_type)
    if isinstance(event, CallbackQuery):
        return "cb:" + (event.data or "")[:100]
    return None


def _user_label(user) -> str:
    name = " ".join(x for x in [getattr(user, "first_name", None), getattr(user, "last_name", None)] if x)
    username = getattr(user, "username", None)
    return (f"{name} (@{username})" if username and name else (f"@{username}" if username else (name or "—")))


class SpamReportMiddleware(BaseMiddleware):
    """گزارش اسپم: اگر یک کاربر یک اکشن/دکمه/متن را چند بار پشت سر هم بزند، به کانال گزارش ادمین ارسال می‌شود."""
    async def __call__(self, handler, event, data: dict):
        try:
            await self._track(event, data)
        except Exception:
            pass
        return await handler(event, data)

    async def _track(self, event, data: dict) -> None:
        user = getattr(event, "from_user", None)
        if not user:
            return
        key = _event_key(event)
        if not key:
            return
        uid = int(user.id)
        now = time.time()
        q = _HISTORY.setdefault(uid, deque(maxlen=30))
        q.append((now, key))
        while q and now - q[0][0] > WINDOW_SECONDS:
            q.popleft()
        count = sum(1 for ts, k in q if k == key and now - ts <= WINDOW_SECONDS)
        if count < THRESHOLD:
            return
        rep_key = (uid, key)
        if now - _LAST_REPORT.get(rep_key, 0) < COOLDOWN_SECONDS:
            return
        _LAST_REPORT[rep_key] = now
        bot = data.get("bot")
        from app.database.engine import async_session
        from app.models.admin import SpamReport
        from app.services import admin_service as adm
        chat = getattr(event, "chat", None) or getattr(getattr(event, "message", None), "chat", None)
        chat_title = str(getattr(chat, "title", None) or getattr(chat, "full_name", None) or getattr(chat, "id", "—"))
        kind = "دکمه" if isinstance(event, CallbackQuery) else "پیام"
        action = key.split(":", 1)[1]
        report_id = None
        async with async_session() as session:
            rec = SpamReport(
                tg_user_id=uid, user_label=_user_label(user), chat_label=chat_title,
                kind=kind, action=action, count=count, window_seconds=WINDOW_SECONDS, status="new"
            )
            session.add(rec)
            await session.flush()
            report_id = rec.id
            channel_id = await adm.get_report_channel_id(session)
            await session.commit()
        if bot is not None and channel_id:
            try:
                await bot.send_message(
                    channel_id,
                    "🚨 <b>گزارش اسپم دریافت شد</b>\n"
                    f"🆔 شماره گزارش: <code>{report_id}</code>\n"
                    "برای ارسال مشخصات، در ادمین‌مود بخش گزارش‌ها → اسپم‌های جدید را باز کنید و دکمه ارسال را بزنید."
                )
            except Exception:
                pass
