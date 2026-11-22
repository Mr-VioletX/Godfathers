# -*- coding: utf-8 -*-
"""🆕 v1.8.1.6 — تبدیلِ خودکارِ ایموجی‌های استاندارد به ایموجی پرمیوم در پیام‌های خروجی.

هر پیامِ خروجی (متن/کپشن) قبل از رسیدن به تلگرام از اینجا رد می‌شود؛ ایموجی‌هایی که
در نگاشتِ پک پرمیوم (app/data/premium_emoji.py ← ساخته‌شده از emoji.txt) وجود دارند
به‌صورت <tg-emoji emoji-id="…"> در می‌آیند تا با ظاهرِ پکِ پرمیوم نمایش داده شوند.

نکته‌ها:
- متنِ دکمه‌های شیشه‌ای و پاسخِ کالبک (toast) دست‌نخورده می‌مانند — تلگرام در آن‌ها entity نمی‌پذیرد.
  🆕 v1.8.2.0 — آیکونِ دکمه‌ها (icon_custom_emoji_id، Bot API 9.4) از مسیرِ رسمیِ
  app/utils/emoji_buttons.py اضافه می‌شود؛ این میدل‌ور فقط «شبکهٔ ایمنی» است: اگر
  تلگرام آیکون/ایموجیِ پرمیوم را رد کند، آیکون‌ها برداشته می‌شوند و پیام سالم می‌رود.
- داخلِ <code>/<pre> (جدول‌های monospace) تبدیل انجام نمی‌شود — entity تودرتو ممنوع است.
- ایموجیِ بدون نگاشت در پک، همان استاندارد باقی می‌ماند.
- شبکهٔ ایمنی: اگر تلگرام custom emoji را رد کرد، همان پیام با ایموجی استاندارد دوباره می‌رود.
"""
from __future__ import annotations

import logging
import re

from aiogram.exceptions import TelegramBadRequest
from aiogram.methods import (
    CopyMessage,
    EditMessageCaption,
    EditMessageText,
    SendAnimation,
    SendAudio,
    SendDocument,
    SendMessage,
    SendPhoto,
    SendVideo,
    SendVoice,
)

from app.data.premium_emoji import EMOJI_IDS
from app.utils.emoji_buttons import has_button_icons, strip_button_icons  # 🆕 v1.8.2.0

log = logging.getLogger(__name__)

# روش‌هایی که فیلد متن/کپشن‌شان با parse_mode=HTML پارس می‌شود
_TEXT_METHODS = (SendMessage, EditMessageText)
_CAPTION_METHODS = (
    SendPhoto,
    SendVideo,
    SendAnimation,
    SendDocument,
    SendAudio,
    SendVoice,
    EditMessageCaption,
    CopyMessage,
)

_TAG = re.compile(r"</?[a-zA-Z][^>]*>")
_RUN = re.compile(
    "["
    "\U0001F000-\U0001FAFF"   # بلوک‌های اصلی ایموجی
    "\u2600-\u27BF"            # Miscellaneous Symbols + Dingbats
    "\u2B00-\u2BFF"            # ستاره/مثلث/…
    "\u200D\uFE0F\u20E3"       # ZWJ + VS16 + keycap
    "0-9#*"                    # پایهٔ کی‌کپ (بدون FE0F/20E3 تبدیل نمی‌شوند)
    "]+"
)

_MAX_KEY = max((len(k) for k in EMOJI_IDS), default=1)


def _convert_run(m: re.Match) -> str:
    """در یک رشتهٔ پشت‌سرِ ایموجی، حریصانهٔ طولانی‌ترین کلیدِ نگاشت را جایگزین می‌کند."""
    s = m.group(0)
    out: list[str] = []
    j = 0
    n = len(s)
    while j < n:
        hit = None
        hi = min(_MAX_KEY, n - j)
        for L in range(hi, 0, -1):
            cand = s[j:j + L]
            if cand in EMOJI_IDS:
                hit = cand
                break
        if hit is not None:
            out.append(f'<tg-emoji emoji-id="{EMOJI_IDS[hit]}">{hit}</tg-emoji>')
            j += len(hit)
        else:
            out.append(s[j])
            j += 1
    return "".join(out)


def premiumize(text: str) -> str:
    """ایموجی‌های نگاشت‌شده را به tg-emoji تبدیل می‌کند؛ تگ‌ها و داخلِ code/pre/tg-emoji دست‌نخورده‌اند."""
    if not text or not EMOJI_IDS:
        return text
    out: list[str] = []
    i = 0
    depth = 0   # داخلِ code/pre/tg-emoji هستیم؟
    for m in _TAG.finditer(text):
        seg = text[i:m.start()]
        out.append(seg if depth else _RUN.sub(_convert_run, seg))
        tag = m.group(0)
        low = tag.lower()
        if low.startswith(("<tg-emoji", "<code", "<pre")):
            depth += 1
        elif low.startswith(("</tg-emoji", "</code", "</pre")):
            depth = max(0, depth - 1)
        out.append(tag)
        i = m.end()
    seg = text[i:]
    out.append(seg if depth else _RUN.sub(_convert_run, seg))
    return "".join(out)


async def premium_emoji_middleware(make_request, bot, method):
    """سشن‌میدل‌ور: قبل از ارسال، متن/کپشن را پرمیوم می‌کند؛ با شبکهٔ ایمنیِ بازگشت به حالت عادی."""
    original: dict[str, str] = {}
    try:
        if isinstance(method, _TEXT_METHODS):
            fields = ("text",)
        elif isinstance(method, _CAPTION_METHODS):
            fields = ("caption",)
        else:
            fields = ()
        for f in fields:
            val = getattr(method, f, None)
            if isinstance(val, str) and val:
                new = premiumize(val)
                if new != val:
                    try:
                        setattr(method, f, new)
                        original[f] = val
                    except Exception:
                        pass
    except Exception:
        original = {}
    # 🆕 v1.8.2.0 — اگر کیبورد آیکونِ پرمیوم دارد، آن هم زیرِ چترِ شبکهٔ ایمنی است.
    try:
        has_icons = has_button_icons(getattr(method, "reply_markup", None))
    except Exception:
        has_icons = False
    if not original and not has_icons:
        return await make_request(bot, method)
    try:
        return await make_request(bot, method)
    except TelegramBadRequest as e:
        msg = str(e).lower()
        if (
            "custom emoji" in msg
            or "custom_emoji" in msg
            or "can't parse" in msg
            or "can't use" in msg
            or "wrong entities" in msg
        ):
            # شبکهٔ ایمنی: با متنِ اصلی (ایموجی استاندارد) و دکمه‌های بدونِ آیکون دوباره تلاش می‌کند
            for f, val in original.items():
                try:
                    setattr(method, f, val)
                except Exception:
                    pass
            if has_icons:
                try:
                    strip_button_icons(getattr(method, "reply_markup", None))
                except Exception:
                    pass
            log.warning("premium_emoji: تلگرام ایموجی پرمیوم را رد کرد؛ با ایموجی استاندارد بازفرستاده شد (%s)", e)
            return await make_request(bot, method)
        raise


def install(bot) -> None:
    """نصب روی سشنِ ربات — بعد از outgoing_safety صدا زده می‌شود (داخلی‌تر) تا خطای custom emoji
    اول اینجا و با متنِ اصلی ریترای شود؛ اگر ردِ دیگری بود، نگهبانِ بیرونی (outgoing_safety) رسیدگی می‌کند."""
    try:
        bot.session.middleware(premium_emoji_middleware)
    except Exception:
        log.exception("premium_emoji: نصب ناموفق بود")
