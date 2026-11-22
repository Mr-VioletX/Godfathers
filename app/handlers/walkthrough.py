# -*- coding: utf-8 -*-
"""مرحله ۲۱.۱ — بخشِ «راهنما»: راهنمایِ خلاقانه/داستانی برای کاربران.

کلمه‌ی فعال‌ساز: «راهنما» (باید دقیقاً همین کلمه، تنها و کاملِ پیام باشد — نه وسطِ جمله).
سه زیرمنوی دارد: راهنما فاز کاربر، راهنما کامل، راهنمای دستورات.
"""
from aiogram import F, Router
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.data import walkthrough as WT
from app.keyboards.main_menu import BTN_WALKTHROUGH  # 🆕 مرحله ۳۰
from app.utils.ui import ensure_owner, safe_show, split_owner, with_owner

router = Router()

WORD_WALKTHROUGH = WT.WORD_WALKTHROUGH  # "راهنما"

_INTRO = (
    "🎬 <b>راهنما</b>\n"
    "<i>راهنمایِ داستانیِ خانواده — یکی از سه بخش را انتخاب کن:</i>"
)


def _menu(owner_id: int):
    b = InlineKeyboardBuilder()
    b.button(text="📖 راهنما فاز کاربر", callback_data=with_owner("wt:user", owner_id))
    b.button(text="📚 راهنما کامل", callback_data=with_owner("wt:full", owner_id))
    b.button(text="🗒️ راهنمایِ دستوراتِ کاربران", callback_data=with_owner("wt:cmds", owner_id))
    b.button(text="⭐ منابع XP", callback_data=with_owner("wt:xp", owner_id))
    b.button(text="🆕 آپدیت v1.7.6", callback_data=with_owner("wt:v176", owner_id))
    b.button(text="↩️ بازگشت به منو", callback_data=with_owner("menu:main", owner_id))
    b.adjust(1)
    return b.as_markup()


def _back_menu(owner_id: int):
    b = InlineKeyboardBuilder()
    b.button(text="↩️ بازگشت به راهنما", callback_data=with_owner("menu:walkthrough", owner_id))
    b.button(text="↩️ بازگشت به منو", callback_data=with_owner("menu:main", owner_id))
    b.adjust(1)
    return b.as_markup()


@router.message(F.text.in_({WORD_WALKTHROUGH, BTN_WALKTHROUGH, "واکترو", "🎬 واکترو"}))
async def open_walkthrough(message: Message) -> None:
    await message.reply(_INTRO, reply_markup=_menu(message.from_user.id))


@router.callback_query(F.data.startswith("menu:walkthrough"))
async def open_walkthrough_cb(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    await safe_show(callback.message, _INTRO, _menu(callback.from_user.id))
    await callback.answer()


@router.callback_query(F.data.startswith("wt:user"))
async def wt_user_cb(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    await safe_show(callback.message, WT.user_phase_text(), _back_menu(callback.from_user.id))
    await callback.answer()


@router.callback_query(F.data.startswith("wt:full"))
async def wt_full_cb(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    await safe_show(callback.message, WT.full_text(), _back_menu(callback.from_user.id))
    await callback.answer()


# 🆕 مرحله ۳۰ — راهنمایِ دستورات چندصفحه‌ای و قابلِ پیمایش شد
def _cmds_nav(owner_id: int, page: int, total: int):
    b = InlineKeyboardBuilder()
    if page > 0:
        b.button(text="◀️ صفحهٔ قبل", callback_data=with_owner(f"wt:cmds:{page - 1}", owner_id))
    b.button(text=f"📄 {page + 1}/{total}", callback_data=with_owner("wt:cmds:noop", owner_id))
    if page < total - 1:
        b.button(text="صفحهٔ بعد ▶️", callback_data=with_owner(f"wt:cmds:{page + 1}", owner_id))
    b.button(text="↩️ بازگشت به راهنما", callback_data=with_owner("menu:walkthrough", owner_id))
    b.button(text="↩️ بازگشت به منو", callback_data=with_owner("menu:main", owner_id))
    row = 1 + (1 if page > 0 else 0) + (1 if page < total - 1 else 0)
    b.adjust(row, 1, 1)
    return b.as_markup()


@router.callback_query(F.data.startswith("wt:cmds"))
async def wt_cmds_cb(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    base, _owner = split_owner(callback.data)
    raw = base.split("wt:cmds", 1)[1].lstrip(":")
    if raw == "noop":
        await callback.answer()
        return
    try:
        page = int(raw) if raw else 0
    except ValueError:
        page = 0
    text, page, total = WT.commands_page(page)
    await safe_show(callback.message, text, _cmds_nav(callback.from_user.id, page, total))
    await callback.answer()


@router.callback_query(F.data.startswith("wt:xp"))
async def wt_xp_cb(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    try:
        from app.data.xp_sources import guide_text
        text = guide_text()
    except Exception:
        text = "⭐ فهرست XP در دسترس نیست."
    await safe_show(callback.message, text, _back_menu(callback.from_user.id))
    await callback.answer()


@router.callback_query(F.data.startswith("wt:v176"))
async def wt_v176_cb(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    from app.data import walkthrough as WT
    text = getattr(WT, "V176_FEATURES", "آپدیت v1.7.6")
    if getattr(WT, "XP_GUIDE_SHORT", None):
        text = text + WT.XP_GUIDE_SHORT
    await safe_show(callback.message, text, _back_menu(callback.from_user.id))
    await callback.answer()
