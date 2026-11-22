# -*- coding: utf-8 -*-
"""جوین اجباری — v1.7.8.13

- داخل ربات (private): هر دستور تا عضویت → پیام کامل + دکمه‌ها
- داخل گروه: 🔇 هیچ پیامی فرستاده نمی‌شود؛ پیامِ کاربر فقط
  نادیده گرفته (بلاک) می‌شود. فقط وقتی کاربر روی دکمه کلیک کند،
  یک توستِ خصوصی (فقط برای خودش) با کول‌داونِ ۳۰ دقیقه نشان داده می‌شود.
"""
from __future__ import annotations

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message


def _skip(event) -> bool:
    user = getattr(event, "from_user", None)
    if user is None or getattr(user, "is_bot", False):
        return True
    if isinstance(event, CallbackQuery):
        data = event.data or ""
        if data.startswith("adm:") or data.startswith("fj:"):
            return True
        return False
    if isinstance(event, Message):
        txt = (event.text or "").strip()
        low = txt.lower()
        if low.startswith("/admin") or txt in {"ادمین", "پنل ادمین", "حالت ادمین"}:
            return True
        # پیام‌های سرویس گروه را رد کن
        if getattr(event, "new_chat_members", None) or getattr(event, "left_chat_member", None):
            return True
        return False
    return True


def _chat_type(event) -> str:
    try:
        if isinstance(event, Message):
            ch = event.chat
        elif isinstance(event, CallbackQuery):
            ch = event.message.chat if event.message else None
        else:
            ch = None
        if ch is None:
            return ""
        return str(getattr(getattr(ch, "type", None), "value", getattr(ch, "type", "")) or "").lower()
    except Exception:
        return ""


class ForceJoinMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data: dict):
        if _skip(event):
            return await handler(event, data)
        user = getattr(event, "from_user", None)
        bot = data.get("bot") or getattr(event, "bot", None)
        if user is None or bot is None:
            return await handler(event, data)

        chat_type = _chat_type(event)
        is_private = chat_type in ("private", "")
        is_group = chat_type in ("group", "supergroup")

        try:
            from app.database.engine import async_session
            from app.services import force_join as FJ
            from app.services import admin_service as adm

            async with async_session() as session:
                try:
                    if await adm.is_admin(session, int(user.id)):
                        return await handler(event, data)
                except Exception:
                    pass
                try:
                    if await adm.is_in_admin_mode(int(user.id)):
                        return await handler(event, data)
                except Exception:
                    pass

                # گروه: فقط بازیکن ثبت‌شده
                if is_group:
                    if not await FJ.is_game_player(session, int(user.id)):
                        return await handler(event, data)

                ok, missing = await FJ.check_user(bot, session, int(user.id))

            if ok:
                return await handler(event, data)

            # --- گروه: کاملاً بی‌صدا — فقط پیامِ کاربر نادیده گرفته می‌شود ---
            # 🐞 v1.7.8.13 — قبلاً اینجا داخلِ گروه ریپلای می‌فرستاد و چون چکِ
            # کول‌داون و ثبتِ آن دو طرفِ یک await بودند، پیام‌های پشتِ‌هم همگی
            # رد می‌شدند و گروه اسپم می‌شد. طبقِ درخواست، حالا در گروه
            # هیچ پیامی ارسال نمی‌شود.
            if is_group and isinstance(event, Message):
                return None  # بلاکِ بی‌صدا

            if is_group and isinstance(event, CallbackQuery):
                # فقط پاسخِ خودِ دکمه (توستِ خصوصیِ کلیک‌کننده) تا لودینگ نچرخد؛
                # هیچ پیامی داخلِ گروه فرستاده نمی‌شود.
                if FJ.try_nudge_in_group(int(user.id)):
                    try:
                        await event.answer("برای فعال‌سازی به ربات سر بزن.", show_alert=True)
                    except Exception:
                        pass
                else:
                    try:
                        await event.answer()
                    except Exception:
                        pass
                return None

            # --- پیوی ربات: هر بار پیام کامل تا عضویت ---
            text = FJ.missing_text(missing)
            markup = FJ.join_keyboard(missing)
            if isinstance(event, CallbackQuery):
                try:
                    await event.answer("اول باید عضو کانال‌ها شوی.", show_alert=True)
                except Exception:
                    pass
                try:
                    # ترجیح: ادیت همان پیام؛ وگرنه پیام جدید
                    await event.message.edit_text(text, reply_markup=markup, disable_web_page_preview=True)
                except Exception:
                    try:
                        await event.message.answer(text, reply_markup=markup, disable_web_page_preview=True)
                    except Exception:
                        pass
                return None
            if isinstance(event, Message):
                # v1.7.9 — payload لینک دعوت را پیش از بلاک نجات بده تا بعد از
                # عضویت و /startِ ساده هم دعوت ثبت شود.
                try:
                    from app.services import referral_service as _refs
                    _rid = _refs.parse_referral_payload(getattr(event, "text", None), int(user.id))
                    if _rid:
                        async with async_session() as _s:
                            await _refs.stash_pending(_s, int(user.id), _rid)
                except Exception:
                    pass
                try:
                    await event.answer(text, reply_markup=markup, disable_web_page_preview=True)
                except Exception:
                    pass
                return None
        except Exception:
            return await handler(event, data)
        return await handler(event, data)
