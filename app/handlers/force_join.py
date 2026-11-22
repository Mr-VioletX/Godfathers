# -*- coding: utf-8 -*-
from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery

from app.database.engine import async_session
from app.services import force_join as FJ

router = Router(name="force_join")


@router.callback_query(F.data == "fj:recheck")
async def fj_recheck(callback: CallbackQuery):
    uid = callback.from_user.id
    # 🐞 v1.7.8.13 — کشِ عضویت را پاک کن؛ وگرنه دکمهٔ «عضو شدم» تا
    # انقضای کش جواب نمی‌دهد و کاربر فکر می‌کند خراب است.
    FJ.invalidate_user(uid)
    async with async_session() as session:
        ok, missing = await FJ.check_user(callback.bot, session, uid, use_cache=False)
    if ok:
        try:
            await callback.answer("✅ عضویت تأیید شد.", show_alert=True)
        except Exception:
            pass
        try:
            await callback.message.edit_text(
                "✅ عضویت تأیید شد. حالا می‌توانی از ربات استفاده کنی.\nاز منوی اصلی ادامه بده."
            )
        except Exception:
            try:
                await callback.message.answer("✅ عضویت تأیید شد. از منوی اصلی ادامه بده.")
            except Exception:
                pass
        return
    text = FJ.missing_text(missing)
    markup = FJ.join_keyboard(missing)
    try:
        await callback.answer("هنوز عضو همه کانال‌ها نیستی.", show_alert=True)
    except Exception:
        pass
    try:
        await callback.message.edit_text(text, reply_markup=markup, disable_web_page_preview=True)
    except Exception:
        try:
            await callback.message.answer(text, reply_markup=markup, disable_web_page_preview=True)
        except Exception:
            pass
