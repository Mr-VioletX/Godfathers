from aiogram import F, Router
from aiogram.filters import Command   # 🆕 مرحله ۳۱
from aiogram.types import CallbackQuery, Message

from app.database.engine import async_session
from app.data.profile import load_privacy
from app.handlers.profile import get_player, profile_text
from app.keyboards.main_menu import (
    BTN_PROFILE,
    WORD_KEYBOARD,      # 🆕 مرحله ۳۱
    WORD_MENU,
    WORD_PROFILE,
    WORD_THEFT,
    main_inline_menu,
    main_menu,          # 🆕 مرحله ۳۱
)
from app.keyboards.profile_menu import profile_back_menu, profile_menu
from app.keyboards.theft_menu import theft_menu
from app.handlers.theft import build_theft_panel
from app.utils.ui import ensure_owner, safe_show, safe_answer

router = Router()

MENU_TITLE = "🎩 <b>منوی اصلی گادفادر</b>\nیکی از گزینه‌ها را انتخاب کن:"
THEFT_TITLE = "🕵️ <b>کدام دزدی؟</b>\nهدفت را انتخاب کن:"
THEFT_ONLY_GROUP = "🕵️ دزدی فقط داخل گروه انجام می‌شود، نه در خودِ ربات."


def _is_private(chat_type: str) -> bool:
    return chat_type == "private"


def _profile_photo(player, private: bool) -> str | None:
    """file_id عکس را برمی‌گرداند اگر باید نمایش داده شود.
    در خصوصی همیشه؛ در گروه فقط اگر گزینه‌ی «🖼️ عکس» در حریم خصوصی روشن باشد."""
    if not (player and player.photo_file_id):
        return None
    if private:
        return player.photo_file_id
    privacy = load_privacy(player.privacy_settings)
    return player.photo_file_id if privacy.get("photo", True) else None


# ---------- 🆕 مرحله ۳۱: بازآوریِ کیبوردِ زیرِ کادرِ تایپ ----------
# دکمه‌ی «🎬 واکترو» در کیبوردِ معمولی هست، ولی تلگرام کیبوردِ قبلی را کش می‌کند
# تا وقتی پیامی با reply_markup تازه برسد. این فرمان همین کار را می‌کند.
@router.message(Command("keyboard"))
@router.message(F.text == WORD_KEYBOARD)
async def refresh_keyboard(message: Message) -> None:
    if not _is_private(message.chat.type):
        await message.reply("⌨️ کیبوردِ زیرِ کادرِ تایپ فقط داخلِ خودِ ربات معنا دارد.")
        return
    await message.answer(
        "⌨️ <b>کیبورد به‌روز شد.</b>\n"
        "دکمه‌ی «🎬 واکترو» حالا زیرِ کادرِ تایپ در دسترس است.",
        reply_markup=main_menu(),
    )


# ---------- «منو» ----------
@router.message(F.text == WORD_MENU)
async def summon_menu(message: Message) -> None:
    private = _is_private(message.chat.type)
    async with async_session() as session:
        player = await get_player(session, message.from_user.id)
    markup = main_inline_menu(private, message.from_user.id)
    photo = player.photo_file_id if (private and player and player.photo_file_id) else None
    if photo:
        await message.reply_photo(photo, caption=MENU_TITLE, reply_markup=markup)
    else:
        await message.reply(MENU_TITLE, reply_markup=markup)


@router.callback_query(F.data.startswith("menu:main"))
async def back_to_menu(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    private = _is_private(callback.message.chat.type)
    async with async_session() as session:
        player = await get_player(session, callback.from_user.id)
    markup = main_inline_menu(private, callback.from_user.id)
    photo = player.photo_file_id if (private and player and player.photo_file_id) else None
    await safe_show(callback.message, MENU_TITLE, markup, photo=photo)
    await safe_answer(callback)


# ---------- دزدی (فقط گروه) ----------
@router.message(F.text == WORD_THEFT)
async def summon_theft(message: Message) -> None:
    if _is_private(message.chat.type):
        await message.reply(THEFT_ONLY_GROUP)
        return
    async with async_session() as session:
        player = await get_player(session, message.from_user.id)
        if not player:
            await message.reply("اول در چت خصوصی ربات /start را بزن.")
            return
        panel = await build_theft_panel(session, player)
    await message.reply(
        panel, reply_markup=theft_menu(player.level, message.from_user.id)
    )


@router.callback_query(F.data.startswith("menu:theft"))
async def open_theft(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    if _is_private(callback.message.chat.type):
        await safe_answer(callback, THEFT_ONLY_GROUP, show_alert=True)
        return
    async with async_session() as session:
        player = await get_player(session, callback.from_user.id)
        if not player:
            await safe_answer(callback, "اول در چت خصوصی ربات /start را بزن.", show_alert=True)
            return
        panel = await build_theft_panel(session, player)
    await safe_show(
        callback.message,
        panel,
        theft_menu(player.level, callback.from_user.id),
    )
    await safe_answer(callback)


# ---------- پروفایل (کلمه‌ی «پروفایل» + دکمه‌ی کیبوردیِ «👤 پروفایل») ----------
@router.message(F.text.in_({WORD_PROFILE, BTN_PROFILE}))
async def summon_profile(message: Message) -> None:
    private = _is_private(message.chat.type)
    async with async_session() as session:
        player = await get_player(session, message.from_user.id)
    if not player:
        await message.reply("اول در چت خصوصی ربات /start را بزن.")
        return
    text = await profile_text(player.tg_user_id, player, private)
    markup = profile_menu(message.from_user.id) if private else profile_back_menu(message.from_user.id)
    photo = _profile_photo(player, private)
    if photo:
        await message.reply_photo(photo, caption=text, reply_markup=markup)
    else:
        await message.reply(text, reply_markup=markup)


@router.callback_query(F.data.startswith("menu:profile"))
async def open_profile_cb(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    private = _is_private(callback.message.chat.type)
    async with async_session() as session:
        player = await get_player(session, callback.from_user.id)
    if not player:
        await safe_answer(callback, "اول در چت خصوصی ربات /start را بزن.", show_alert=True)
        return
    text = await profile_text(player.tg_user_id, player, private)
    markup = profile_menu(callback.from_user.id) if private else profile_back_menu(callback.from_user.id)
    photo = _profile_photo(player, private)
    await safe_show(callback.message, text, markup, photo=photo)
    await safe_answer(callback)


# ---------- moderngroup handling removed; ranking در ranking.py ----------


# 🗑 مرحله ۱۹: placeholderِ «menu:war» حذف شد — حالا روترهای واقعی
# (war/alliance/military/world_alliance/branding/worldbank) خودشان پاسخ می‌دهند.
