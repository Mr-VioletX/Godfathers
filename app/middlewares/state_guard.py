# -*- coding: utf-8 -*-
"""🆕 مرحله ۳۲ — نگهبانِ عمومیِ وضعیت (نسخهٔ ۲ — پیام + دکمهٔ شیشه‌ای).

🐞 رفعِ باگ (گزارشِ کاربر):
  • «انصراف خیلی وقت‌ها جواب نمی‌دهد» → این میدل‌ورِ بیرونی پیش از همهٔ
    روترها اجرا می‌شود، پس انصراف ۱۰۰٪ کار می‌کند.
  • «دستورِ قبلی لغو نمی‌شود» → هر دستورِ متنی دیگر، عملیاتِ نیمه‌کاره را
    لغو می‌کند.

🆕 مرحله ۳۲ — مهم‌ترین تغییر:
  قبلاً این نگهبان فقط روی پیامِ متنی (Message) نصب بود. پس اگر کاربر
  وسطِ یک عملیات، یک دکمهٔ شیشه‌ای (CallbackQuery) می‌زد، عملیاتِ قبلی
  زنده می‌ماند و بعداً هر متنی که می‌نوشت، به‌جایِ مقدارِ همان عملیاتِ
  فراموش‌شده خوانده می‌شد («مدام می‌گوید مقدار را وارد کن»).
  حالا نگهبان روی callback_query هم نصب می‌شود.
"""
from __future__ import annotations

from aiogram import BaseMiddleware
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.keyboards import main_menu as MM
from app.utils.ui import CANCEL_WORDS, with_owner

# نامِ فارسیِ عملیات‌ها (برای پیامِ دقیقِ لغو)
STATE_LABELS: dict[str, str] = {
    "Registration": "ثبت‌نام",
    "ProfileStates:editing_name": "تغییرِ نامِ پروفایل",
    "ProfileStates:editing_photo": "تغییرِ عکسِ پروفایل",
    "ProfileStates": "ویرایشِ پروفایل",
    "BrandStates:creating_name": "ساختِ برند",
    "BrandStates:renaming": "تغییرِ نامِ برند",
    "BrandStates": "عملیاتِ برند",
    "AllianceStates:creating_tag": "ساختِ اتحادیه (انتخابِ آیدی)",
    "AllianceStates:creating_name": "ساختِ اتحادیه (انتخابِ نام)",
    "AllianceStates:setting_name": "تغییرِ نامِ اتحادیه",
    "AllianceStates:setting_tag": "تغییرِ آیدیِ اتحادیه",
    "AllianceStates:setting_sub": "تنطیمِ درصدِ اشتراکِ اتحادیه",
    "AllianceStates:setting_power": "تنطیمِ آستانه‌ی قدرتِ عضویت",
    "AllianceStates": "عملیاتِ اتحادیه",
    "WorldAllianceStates": "عملیاتِ اتحادیه‌ی جهانی",
    "WarStates:entering_target": "انتخابِ هدفِ حمله",
    "WarStates": "عملیاتِ جنگ",
    "SpyStates": "عملیاتِ جاسوسی",
    "ChatStates": "عملیاتِ خطِ محرمانه",
    "SportsStates": "عملیاتِ ورزشی",
    "BankStates": "عملیاتِ بانک",
    "TransferStates:cash_amount": "انتقالِ پول (مبلغ)",
    "TransferStates:cash_target": "انتقالِ پول (گیرنده)",
    "TransferStates:resource_amount": "انتقالِ منابع (مقدار)",
    "TransferStates:resource_target": "انتقالِ منابع (گیرنده)",
    "TransferStates": "انتقالِ دارایی",
    "SubStates": "عملیاتِ اشتراک",
    "AdminStates": "عملیاتِ ادمین",
    "CityStates:naming_city": "نام‌گذاریِ شهر",
    "CityStates:renaming_city": "تغییرِ نامِ شهر",
    "CityStates:buying_resource_amount": "خریدِ منابعِ شهر",
    "CityStates": "عملیاتِ شهر",
}

# در این وضعیت‌ها متنِ کاربر می‌تواند عیناً شبیهِ یک دستور باشد (متنِ همگانی،
# خبر، رمز، لقبِ سفارشی، پیامِ آفلاین …)؛ پس فقط با کلمهٔ انصراف لغو می‌شوند.
FREEFORM_STATES = {
    "AdminStates:waiting_login_password",
    "AdminStates:waiting_new_password",
    "AdminStates:self_change_password",
    "AdminStates:admins_wait_initpw",
    "AdminStates:broadcast_wait_text",
    "AdminStates:news_wait_text",
    "AdminStates:title_wait_custom",
    "AdminStates:event_wait_title",
    "ChatStates:offline_message",
    "ChatStates:reporting",
    "CityStates:naming_city",
    "CityStates:renaming_city",
}

# 🆕 مرحله ۳۲ — دکمه‌هایی که خودشان پارهٔ یک عملیاتِ درجریان‌اند و به
# دادهٔ FSM نیاز دارند. این‌ها نباید وضعیت را پاک کنند.
STATEFUL_CB_PREFIXES = (
    "ui:cancel",
    "adm:",            # کلِ ادمین‌مود با FSM کار می‌کند
    "brd:rn:",         # تغییرِ نامِ برند
    "chat:leavemsg:",  # پیامِ آفلاین
    "sport:rn:",       # تغییرِ نامِ تیم
    "spy:manual:",     # هدفِ دستیِ جاسوسی
    "sub:request:",    # درخواستِ اشتراک
    "transfer:",       # همهٔ مراحلِ انتقال
    "city:buy",        # 🆕 v1.7.2 — نام‌گذاری شهر
    "city:rename",     # 🆕 v1.7.2 — ویرایش نام شهر
    "gender:",         # ثبت‌نام / انتخاب جنسیت (حفظ referral)
)


def _label(state: str | None) -> str:
    if not state:
        return "عملیاتِ قبلی"
    return (
        STATE_LABELS.get(state)
        or STATE_LABELS.get(state.split(":")[0])
        or "عملیاتِ قبلی"
    )


def _command_texts() -> set[str]:
    """همهٔ دکمه‌ها/کلمه‌هایِ فرمانِ ربات (از خودِ main_menu خوانده می‌شود)."""
    words = {
        v
        for k, v in vars(MM).items()
        if isinstance(v, str) and (k.startswith("BTN_") or k.startswith("WORD_"))
    }
    words |= {
        "منو", "شروع", "شروع ربات", "جنگ", "واکترو", "القاب",
        "نطامی", "نظامی", "بانک", "راهنما", "راهنمای ادمین", "ادمین مود",
        "خروج از ادمین", "دیدنِ گزارش‌ها", "جاسوسی", "مخاطبین",
        "چت مود", "اتحادیه", "برند", "اخبار",
        # 🆕 مرحله ۳۲ — کلمه‌هایی که جا افتاده بودند
        "کیبورد", "پروفایل", "پایگاه", "عمارت", "شهر", "کاپولا",
        "بازار", "انبار", "ورزش", "رنکینگ", "دستیار", "اشتراک ویژه",
        "دزدی", "انتقال",
    }
    return {w.strip() for w in words if w and w.strip()}


COMMAND_TEXTS = _command_texts()


def _is_command_text(text: str) -> bool:
    t = (text or "").strip()
    if not t:
        return False
    if t.startswith("/"):
        return True
    if t in COMMAND_TEXTS:
        return True
    # دستورهایِ دوبخشی مانندِ «انتقال ۱۰۰۰۰»
    first = t.split()[0]
    return first in {"انتقال", "دزدی"}


def _menu_hint_kb(owner_id: int):
    b = InlineKeyboardBuilder()
    b.button(text="🏠 بازگشت به منوی اصلی", callback_data=with_owner("menu:main", owner_id))
    b.adjust(1)
    return b.as_markup()


class StateGuardMiddleware(BaseMiddleware):
    """میدل‌ورِ بیرونی: پیش از همهٔ روترها درباره‌ی لغو تصمیم می‌گیرد.

    روی هر دویِ Message و CallbackQuery نصب می‌شود.
    """

    async def __call__(self, handler, event, data: dict):
        if isinstance(event, CallbackQuery):
            return await self._on_callback(handler, event, data)
        if isinstance(event, Message):
            return await self._on_message(handler, event, data)
        return await handler(event, data)

    # ------------------------------------------------------------- callback
    async def _on_callback(self, handler, event: CallbackQuery, data: dict):
        """🆕 مرحله ۳۲ — زدنِ هر دکمهٔ بی‌ربط، عملیاتِ نیمه‌کاره را لغو می‌کند."""
        cb_data = event.data or ""
        if cb_data.startswith(STATEFUL_CB_PREFIXES):
            return await handler(event, data)
        state: FSMContext | None = data.get("state")
        if state is None:
            return await handler(event, data)
        try:
            current = await state.get_state()
        except Exception:
            current = None
        if not current:
            return await handler(event, data)
        label = _label(current)
        try:
            await state.clear()
        except Exception:
            pass
        try:
            await event.answer(f"❌ {label} لغو شد", show_alert=False)
        except Exception:
            pass
        return await handler(event, data)

    # -------------------------------------------------------------- message
    async def _on_message(self, handler, event: Message, data: dict):
        if not event.from_user or not event.text:
            return await handler(event, data)
        state: FSMContext | None = data.get("state")
        if state is None:
            return await handler(event, data)
        try:
            current = await state.get_state()
        except Exception:
            current = None
        if not current:
            return await handler(event, data)

        text = (event.text or "").strip()
        label = _label(current)

        # ۱) کلمه‌ی انصراف → لغویِ قطعی در هر بخشی (بدونِ وابستگی به هندلر)
        if text in CANCEL_WORDS:
            try:
                await state.clear()
            except Exception:
                pass
            try:
                await event.reply(
                    f"✅ {label} لغو شد! هیچ تغییری ثبت نشد.",
                    reply_markup=_menu_hint_kb(event.from_user.id),
                )
            except Exception:
                pass
            return None

        # ۲) هر دستور/دکمهٔ دیگر → عملیاتِ نیمه‌کاره لغو می‌شود و همان بخش باز می‌شود
        if current not in FREEFORM_STATES and _is_command_text(text):
            try:
                await state.clear()
            except Exception:
                pass
            try:
                await event.answer(f"❌ {label} لغو شد (چون دستورِ دیگری فرستادی).")
            except Exception:
                pass
            return await handler(event, data)

        return await handler(event, data)
