import logging

from aiogram import Router
from aiogram.types import Message

router = Router()
log = logging.getLogger(__name__)

# فقط پیام‌های private بدون هندلر را لاگ کن — چت عادی گروه را اسپم نکن.


@router.message()
async def _debug_unmatched(message: Message):
    try:
        ctype = str(getattr(message.chat, "type", "") or "")
    except Exception:
        ctype = ""
    if ctype != "private":
        return
    text = message.text or message.caption
    if not text:
        return
    log.info("UNMATCHED chat=%s text=%r", ctype, text[:200])
