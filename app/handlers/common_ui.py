# -*- coding: utf-8 -*-
"""🆕 مرحله ۲۸ — هندلرهای مشترکِ رابطِ کاربری.

• ui:cancel — انصراف از هر ورودیِ متنی/عددی (پاک‌کردنِ FSM)
"""
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.utils.ui import ensure_owner, safe_edit, split_owner, with_owner

router = Router(name="common_ui")


@router.callback_query(F.data.startswith("ui:cancel"))
async def ui_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    """انصرافِ عمومی: وضعیت پاک می‌شود و یک دکمه‌ی واقعی «بازگشت به منو» نشان داده می‌شود.

    🆕 رفعِ باگ: قبلاً بعدِ زدنِ انصراف، پیام فقط به یک متنِ ساده بدونِ هیچ دکمه‌ای تبدیل
    می‌شد (با reply_markup=None)، یعنی هیچ راهی برای ادامه‌دادن نبود و به‌نظر می‌رسید
    دکمه فقط ظاهری بوده. حالا یک دکمه‌ی فعالِ «بازگشت به منوی اصلی» (همان هندلرِ کاریِ menu:main) اضافه شد.
    """
    if not await ensure_owner(callback):
        return
    await state.clear()
    uid = callback.from_user.id
    b = InlineKeyboardBuilder()
    b.button(text="🏠 بازگشت به منوی اصلی", callback_data=with_owner("menu:main", uid))
    b.adjust(1)
    done_text = "✅ با موفقیت لغو شد! هیچ تغییری ثبت نشد."
    edited = await safe_edit(callback.message, done_text, b.as_markup())
    if not edited:
        # 🐞 رفعِ باگ: اگر ادیتِ پیامِ قبلی ممکن نبود (مثلاً قدیمی بود)، باز هم
        # یک پیامِ تازه‌ی تأیید بفرست شود تا کاربر مطمئن شود لغو واقعاً انجام شده.
        try:
            await callback.message.answer(done_text, reply_markup=b.as_markup())
        except Exception:
            pass
    await callback.answer("✅ با موفقیت لغو شد")
