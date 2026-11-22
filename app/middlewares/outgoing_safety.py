# -*- coding: utf-8 -*-
"""🆕 نگهبانِ خروجی — همهٔ درخواست‌هایی که ربات به تلگرام می‌فرستد از اینجا رد می‌شوند.

سه دسته خطا که در لاگِ هاست باعثِ «ربات هیچ کاری نمی‌کند» می‌شدند، اینجا به‌صورت
سراسری حل می‌شود:

1) MESSAGE_TOO_LONG  → متن‌های بلندتر از سقفِ تلگرام خودکار تکه‌تکه فرستاده می‌شوند
   (۳۹ بار در military.py و ۳۰ بار در alliance.py رخ داده بود).
2) can't parse entities → اگر HTML خراب باشد (مثلاً «<مبلغ>»)، به‌جای کرش، همان پیام
   بدونِ parse_mode و با کاراکترهای امن دوباره فرستاده می‌شود.
3) query is too old / message to be replied not found → بی‌صدا نادیده گرفته می‌شوند.
"""
from __future__ import annotations

import logging

from aiogram.exceptions import TelegramBadRequest
from aiogram.methods import (
    AnswerCallbackQuery,
    EditMessageCaption,
    EditMessageText,
    SendMessage,
    SendPhoto,
)

log = logging.getLogger(__name__)

TEXT_LIMIT = 4000        # سقفِ واقعیِ تلگرام ۴۰۹۶ است؛ کمی حاشیهٔ امن می‌گذاریم
CAPTION_LIMIT = 1000     # سقفِ کپشن ۱۰۲۴ است


def _split_text(text: str, limit: int) -> list[str]:
    """تکه‌کردنِ متن روی مرزِ خط (و در بدترین حالت روی مرزِ کاراکتر)."""
    text = text or ""
    if len(text) <= limit:
        return [text]
    chunks: list[str] = []
    current = ""
    for line in text.split("\n"):
        while len(line) > limit:
            if current:
                chunks.append(current)
                current = ""
            chunks.append(line[:limit])
            line = line[limit:]
        if len(current) + len(line) + 1 > limit:
            chunks.append(current)
            current = line
        else:
            current = f"{current}\n{line}" if current else line
    if current:
        chunks.append(current)
    return [c for c in chunks if c.strip()] or [text[:limit]]


def _plain(text: str) -> str:
    """حذفِ خطرِ HTML: تبدیلِ کاراکترهای زاویه‌دار به معادلِ بی‌خطر."""
    return (text or "").replace("<", "‹").replace(">", "›")


async def outgoing_safety_middleware(make_request, bot, method):
    # ── ۱) کوتاه‌سازیِ پیش‌دستانه‌ی متنِ بلند ───────────────────────────────
    extra_chunks: list[str] = []
    chat_id = None
    try:
        if isinstance(method, SendMessage) and method.text and len(method.text) > TEXT_LIMIT:
            parts = _split_text(method.text, TEXT_LIMIT)
            method.text = parts[0]
            extra_chunks = parts[1:]
            chat_id = method.chat_id
        elif isinstance(method, (EditMessageText,)) and method.text and len(method.text) > TEXT_LIMIT:
            parts = _split_text(method.text, TEXT_LIMIT)
            method.text = parts[0]
            extra_chunks = parts[1:]
            chat_id = method.chat_id
        elif isinstance(method, (SendPhoto, EditMessageCaption)):
            caption = getattr(method, "caption", None)
            if caption and len(caption) > CAPTION_LIMIT:
                parts = _split_text(caption, CAPTION_LIMIT)
                method.caption = parts[0]
                extra_chunks = parts[1:]
                chat_id = getattr(method, "chat_id", None)
    except Exception:
        extra_chunks = []

    # ── ۲) ارسال با شبکهٔ ایمنی ───────────────────────────────────────────
    try:
        result = await make_request(bot, method)
    except TelegramBadRequest as e:
        msg = str(e)

        # الف) خطای HTML خراب → ارسالِ دوباره بدونِ parse_mode
        if "can't parse entities" in msg or "can't parse message text" in msg:
            try:
                if hasattr(method, "text") and getattr(method, "text", None):
                    method.text = _plain(method.text)
                if hasattr(method, "caption") and getattr(method, "caption", None):
                    method.caption = _plain(method.caption)
                if hasattr(method, "parse_mode"):
                    method.parse_mode = None
                log.warning("outgoing_safety: HTML نامعتبر بود؛ بدون parse_mode ارسال شد (%s)", msg)
                result = await make_request(bot, method)
            except Exception:
                log.exception("outgoing_safety: ارسالِ جایگزین هم شکست خورد")
                return None

        # ب) متنِ بلند (اگر با وجودِ کوتاه‌سازی باز هم رخ داد)
        elif "MESSAGE_TOO_LONG" in msg or "message is too long" in msg.lower():
            try:
                raw = getattr(method, "text", None) or getattr(method, "caption", None) or ""
                parts = _split_text(raw, TEXT_LIMIT // 2)
                if hasattr(method, "text") and getattr(method, "text", None):
                    method.text = parts[0]
                elif hasattr(method, "caption"):
                    method.caption = parts[0]
                extra_chunks = parts[1:] + extra_chunks
                chat_id = getattr(method, "chat_id", None)
                result = await make_request(bot, method)
            except Exception:
                log.exception("outgoing_safety: تکه‌کردنِ متنِ بلند شکست خورد")
                return None

        # ج) کلیکِ قدیمی / پیامِ ریپلای‌شده حذف‌شده → بی‌صدا رد شو
        elif "query is too old" in msg or "query ID is invalid" in msg:
            return True
        elif "message to be replied not found" in msg:
            try:
                if hasattr(method, "reply_parameters"):
                    method.reply_parameters = None
                if hasattr(method, "reply_to_message_id"):
                    method.reply_to_message_id = None
                result = await make_request(bot, method)
            except Exception:
                return None
        elif "message is not modified" in msg:
            return None
        else:
            raise

    # ── ۳) ارسالِ تکه‌های باقی‌مانده ───────────────────────────────────────
    if extra_chunks:
        target = chat_id or getattr(method, "chat_id", None)
        if target is not None:
            for chunk in extra_chunks:
                try:
                    await bot(SendMessage(chat_id=target, text=chunk))
                except TelegramBadRequest:
                    try:
                        await bot(SendMessage(chat_id=target, text=_plain(chunk), parse_mode=None))
                    except Exception:
                        log.warning("outgoing_safety: ارسالِ تکهٔ اضافه ناموفق بود")
                        break
                except Exception:
                    break

    return result


def install(bot) -> None:
    """نصبِ نگهبان روی سشنِ ربات."""
    try:
        bot.session.middleware(outgoing_safety_middleware)
    except Exception:
        log.exception("outgoing_safety: نصب ناموفق بود")
