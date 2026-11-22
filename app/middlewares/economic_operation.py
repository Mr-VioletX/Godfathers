# -*- coding: utf-8 -*-
"""سری‌سازی عملیات مالی/تولیدی callback و message با قفل پایدار."""
from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message
from app.services.operation_guard import economic_operation, DuplicateOperation, BusyOperation

# فقط مسیرهایی که دارایی، تولید یا پیشرفت اقتصادی را تغییر می‌دهند.
PREFIXES = ("fp:", "factory:", "estate:", "brd:", "warehouse:", "base:", "sport:", "mil:", "spy:", "transfer:", "bank:", "sub:", "war:", "rank:", "alliance:", "kapatolo:")

class EconomicOperationMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        user = getattr(event, "from_user", None)
        if not user:
            return await handler(event, data)
        if isinstance(event, CallbackQuery):
            raw = event.data or ""
            if not raw.startswith(PREFIXES):
                return await handler(event, data)
            opid = f"cb:{event.id}"
        elif isinstance(event, Message):
            # متن‌های FSM برای انتقال/بانک/خرید نیز با شناسهٔ پیام یک‌بارمصرف محافظت می‌شوند.
            state = data.get("state")
            if not state or not await state.get_state():
                return await handler(event, data)
            opid = f"msg:{event.chat.id}:{event.message_id}"
        else:
            return await handler(event, data)
        try:
            async with economic_operation(user.id, opid):
                return await handler(event, data)
        except DuplicateOperation:
            if isinstance(event, CallbackQuery): await event.answer("این عملیات قبلاً انجام شده است.", show_alert=True)
            return None
        except BusyOperation:
            if isinstance(event, CallbackQuery): await event.answer("⏳ عملیات قبلی هنوز در حال پردازش است.", show_alert=True)
            return None
