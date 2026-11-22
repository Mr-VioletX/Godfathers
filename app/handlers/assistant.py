# app/handlers/assistant.py
from datetime import datetime, timedelta

from aiogram import F, Router
from aiogram.exceptions import TelegramForbiddenError
from aiogram.filters import BaseFilter, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select

from app.database.engine import async_session
from app.models.player import Player
from app.models.estate import Estate
from app.models.factory import Factory
from app.models.assistant import Assistant, SecondAssistant, SecondAssistantCommand, SecondAssistantChat
from app.data.assistant import (
    ASSISTANT_COST,
    DEFAULT_NAME,
    clean_name,
    progression_for,
    upgrade_info,
    next_upgrade,
    unlocked_features,
    feature_label,
)
from app.keyboards.assistant_menu import (
    back_only_menu,
    buy_menu,
    group_menu,
    panel_menu,
    live_actions_menu,
    photo_edit_menu,
    settings_menu,
    upgrade_menu,
    assistants_home_menu,
    assistant2_menu,
    assistant2_buy_menu,
    assistant2_chat_menu,
)
from app.keyboards.main_menu import BTN_ASSISTANT, main_inline_menu
from app.utils.ui import CANCEL_HINT, ensure_owner, handle_cancel_word, safe_edit

try:
    from aiogram.dispatcher.event.bases import SkipHandler
except Exception:   # سازگاری با نسخه‌های دیگرِ aiogram
    class SkipHandler(Exception):   # type: ignore
        pass

router = Router()

ONLY_BOT = "🤖 شخصی‌سازیِ دستیار فقط داخلِ خودِ ربات ممکن است، نه در گروه."


class AssistantEdit(StatesGroup):
    name = State()
    photo = State()

class SecondAssistantEdit(StatesGroup):
    name = State()
    trigger = State()
    reply = State()
    photo = State()


# ---------- helperها ----------
async def get_player(session, tg_user_id):
    result = await session.execute(select(Player).where(Player.tg_user_id == tg_user_id))
    return result.scalar_one_or_none()


async def get_assistant(session, tg_user_id):
    return await session.get(Assistant, tg_user_id)

async def get_second_assistant(session, tg_user_id):
    return await session.get(SecondAssistant, tg_user_id)

async def _second_allowed(session, uid):
    from app.services import subscription_service, admin_service
    from app.services.restrictions import blocked
    if await blocked(session, uid, "assistant"):
        return False
    if str(await admin_service.get_setting(session, "assistant_second_enabled") or "1") == "0":
        return False
    return (await subscription_service.active_tier(session, uid)) == "gold"


async def user_has_estate(session, tg_user_id) -> bool:
    result = await session.execute(
        select(Estate.id).where(Estate.tg_user_id == tg_user_id).limit(1)
    )
    return result.first() is not None


def _panel_text(assistant) -> str:
    has_photo = "تنظیم شده ✅" if assistant.photo_file_id else "تنظیم نشده ❌"
    level = int(getattr(assistant, "upgrade_level", 1) or 1)
    info = upgrade_info(level)
    feats = unlocked_features(level)
    feat_lines = "\n".join(f"• {feature_label(k)}" for k in feats)
    nxt = next_upgrade(level)
    nxt_line = (
        f"\n🔒 برای دسترسیِ بیشتر دستیار را ارتقا بده («{nxt['name']}»)."
        if nxt else "\n🏆 دستیارت به بالاترین سطح رسیده است."
    )
    return (
        f"🤖 <b>{assistant.name}</b> — مشاورِ زنده‌ی امپراتوری\n"
        f"🧠 سطح: <b>{info['name']}</b> (سطح {level})\n"
        f"🖼️ عکس: {has_photo}\n\n"
        "🔥 <b>ابزارهای پویا:</b>\n"
        "💓 نبض امپراتوری — وضعیت لحظه‌ای با لحن تند\n"
        "🎯 فرصت‌یاب — سودده‌ترین کارِ همین الان\n"
        "⚔️ آمادگی جنگ — امتیاز آمادگی + نقطه‌ضعف ارتش\n"
        "🎖️ مأموریت روزانه — ۳ هدف کوتاهِ امروز\n"
        "📡 رصد میدان — جنگ‌های تو + اخبار زنده\n\n"
        "بخش‌های رصد سطح‌بندی‌شده:\n"
        f"{feat_lines}\n"
        f"{nxt_line}\n\n"
        "بزن بریم — از نبض یا فرصت‌یاب شروع کن."
    )


def _buy_text(player) -> str:
    return (
        "🤖 <b>دستیارِ هوشمند (کنسیلیری)</b>\n\n"
        "یک مشاورِ شخصی که:\n"
        "• 📋 گزارشِ روزانه می‌دهد (در گروه + محرمانه در ربات)\n"
        "• ⏰ کارهای عقب‌مانده‌ات را یادآوری می‌کند\n"
        "• 🧭 برای پیشرفت به مرحله‌ی بعد راهنمایی‌ات می‌کند\n"
        "• 🏷️ نام و 🖼️ عکسِ دلخواهت را می‌گیرد و در گروه با نامش جواب می‌دهد\n\n"
        f"💰 هزینه: <b>{ASSISTANT_COST:,}</b> دلار (یک‌بار، بدونِ حقوق)\n"
        f"💵 موجودیِ تو: <b>{player.cash:,}</b> دلار"
    )


LOCKED_TEXT = (
    "🔒 <b>دستیار هنوز قفل است</b>\n\n"
    "دستیارِ هوشمند بعد از ساختِ <b>اولین عمارت</b> باز می‌شود.\n"
    "به بخشِ «🏛️ عمارت» برو و Cupola را بساز."
)


async def build_home(session, tg_user_id):
    """(متن، کیبورد، وضعیت) خانه‌ی دستیار.
    state یکی از: 'locked' | 'buy' | 'panel'."""
    player = await get_player(session, tg_user_id)
    if player is None:
        return "❗ ابتدا /start را بزن.", back_only_menu(tg_user_id), "locked"
    if not await user_has_estate(session, tg_user_id):
        return LOCKED_TEXT, back_only_menu(tg_user_id), "locked"
    assistant = await get_assistant(session, tg_user_id)
    if assistant is None:
        return _buy_text(player), buy_menu(tg_user_id), "buy"
    return _panel_text(assistant), panel_menu(tg_user_id), "panel"


# ---------- ورودی از کیبوردِ اصلی (🆕 مرحله ۱۲: در گروه هم فعال) ----------
@router.message(StateFilter(None), F.text.in_({BTN_ASSISTANT, "دستیار", "دستیاران"}))   # 🔄 مرحله ۲۱.۱ — تطبیقِ دقیق
async def assistant_button(message: Message):
    async with async_session() as session:
        second = await get_second_assistant(session, message.from_user.id)
    await message.answer("🤖 <b>دستیاران</b>\nدستیار اول عمومی است؛ دستیار دوم ویژه‌ی اشتراک طلایی است.", reply_markup=assistants_home_menu(message.from_user.id, bool(second)))


# ---------- ورودی از منوی شیشه‌ای ----------
@router.callback_query(F.data.startswith("menu:assistant"))
async def assistant_menu_cb(callback: CallbackQuery):
    if not await ensure_owner(callback):
        return
    # 🆕 مرحله ۱۲: در گروه هم باز می‌شود (پیام ادیت می‌شود).
    async with async_session() as session:
        second = await get_second_assistant(session, callback.from_user.id)
    await safe_edit(callback.message, "🤖 <b>دستیاران</b>\nدستیار اول عمومی است؛ دستیار دوم ویژه‌ی اشتراک طلایی است.", assistants_home_menu(callback.from_user.id, bool(second)))
    await callback.answer()


@router.callback_query(F.data.startswith("assistant:hub"))
async def assistant_hub_cb(callback: CallbackQuery, state: FSMContext):
    if not await ensure_owner(callback):
        return
    await state.clear()
    async with async_session() as session:
        from app.services.restrictions import blocked
        if await blocked(session, callback.from_user.id, "assistant"):
            await callback.answer("دستیار شما توسط ادمین محدود شده است.", show_alert=True); return
        text, markup, _ = await build_home(session, callback.from_user.id)
    await safe_edit(callback.message, text, markup)
    await callback.answer()


# ---------- بازگشت به منوی اصلی ----------
@router.callback_query(F.data.startswith("menu:main"))
async def back_to_main_menu_cb(callback: CallbackQuery, state: FSMContext):
    """دکمه‌ی «↩️ بازگشت به منو» در منوهای دستیار.
    وضعیتِ FSM را پاک می‌کند و منوی شیشه‌ایِ اصلی را دوباره نشان می‌دهد.
    """
    if not await ensure_owner(callback):
        return
    await state.clear()
    is_private = callback.message.chat.type == "private"
    await safe_edit(
        callback.message,
        "🏠 منوی اصلی:",
        main_inline_menu(is_private, callback.from_user.id),
    )
    await callback.answer()


# ---------- خرید (یک‌بار، بدونِ حقوق) ----------
@router.callback_query(F.data.startswith("assistant:buy"))
async def assistant_buy_cb(callback: CallbackQuery):
    if not await ensure_owner(callback):
        return
    async with async_session() as session:
        player = await get_player(session, callback.from_user.id)
        if player is None:
            await callback.answer("❗ ابتدا /start را بزن.", show_alert=True)
            return
        if not await user_has_estate(session, player.tg_user_id):
            await callback.answer("⛔ اول باید اولین عمارت را بسازی.", show_alert=True)
            return
        if await get_assistant(session, player.tg_user_id) is not None:
            text, markup, _ = await build_home(session, player.tg_user_id)
            await safe_edit(callback.message, text, markup)
            await callback.answer("همین حالا دستیار داری!")
            return
        if player.cash < ASSISTANT_COST:
            await callback.answer(f"💸 پول کافی نداری! هزینه: {ASSISTANT_COST:,}$", show_alert=True)
            return
        player.cash -= ASSISTANT_COST
        session.add(Assistant(tg_user_id=player.tg_user_id, name=DEFAULT_NAME))
        await session.commit()
        text, markup, _ = await build_home(session, player.tg_user_id)
    await safe_edit(callback.message, text, markup)
    await callback.answer("🎉 دستیارت استخدام شد! حالا نام و عکسش را تنظیم کن.")


# ---------- ویرایشِ نام ----------
@router.callback_query(F.data.startswith("assistant:edit:name"))
async def edit_name_cb(callback: CallbackQuery, state: FSMContext):
    # Stage 27: assistant editing is allowed only inside the bot private chat
    if callback.message is not None and callback.message.chat.type != "private":
        await callback.answer(
            "✏️ ویرایشِ دستیار فقط داخلِ خودِ ربات ممکن است، نه در گروه.",
            show_alert=True,
        )
        return
    if not await ensure_owner(callback):
        return
    await state.set_state(AssistantEdit.name)
    await safe_edit(
        callback.message,
        "✏️ نامِ جدیدِ دستیار را بفرست (حداکثر ۲۰ نویسه).\n"
        "این همان نامی است که در گروه صدایش می‌زنی." + CANCEL_HINT,
        None,
    )
    await callback.answer()


@router.message(StateFilter(AssistantEdit.name), F.chat.type == "private")
async def edit_name_input(message: Message, state: FSMContext):
    if await handle_cancel_word(message, state):
        return
    name = clean_name(message.text or "")
    if name is None:
        await message.answer("⛔ نام نامعتبر است. یک نامِ ۱ تا ۲۰ نویسه‌ای بفرست.")
        return
    async with async_session() as session:
        from app.services.restrictions import blocked
        if await blocked(session, message.from_user.id, "photo"):
            await state.clear(); await message.answer("عکس‌گذاری شما توسط ادمین محدود شده است."); return
        assistant = await get_assistant(session, message.from_user.id)
        if assistant is None:
            await state.clear()
            await message.answer("❗ اول باید دستیار را بخری.")
            return
        assistant.name = name
        await session.commit()
        text, markup, _ = await build_home(session, message.from_user.id)
    await state.clear()
    await message.answer(f"✅ نامِ دستیار به «{name}» تغییر کرد.")
    await message.answer(text, reply_markup=markup)


# ---------- ویرایشِ عکس ----------
@router.callback_query(F.data.startswith("assistant:edit:photo"))
async def edit_photo_cb(callback: CallbackQuery, state: FSMContext):
    # Stage 27: assistant editing is allowed only inside the bot private chat
    if callback.message is not None and callback.message.chat.type != "private":
        await callback.answer(
            "✏️ ویرایشِ دستیار فقط داخلِ خودِ ربات ممکن است، نه در گروه.",
            show_alert=True,
        )
        return
    if not await ensure_owner(callback):
        return
    async with async_session() as session:
        from app.services.restrictions import blocked
        if await blocked(session, callback.from_user.id, "photo"):
            await callback.answer("عکس‌گذاری شما توسط ادمین محدود شده است.", show_alert=True); return
        assistant = await get_assistant(session, callback.from_user.id)
    has_photo = bool(assistant and assistant.photo_file_id)
    await state.set_state(AssistantEdit.photo)
    await safe_edit(
        callback.message,
        "🖼️ یک عکس بفرست تا چهره‌ی دستیارت شود.\n"
        "(عکس را به‌صورتِ Photo بفرست، نه فایل.)"
        + ("\n\nیا با دکمه‌ی «🗑️ حذفِ عکس» عکسِ فعلی را بردار." if has_photo else ""),
        photo_edit_menu(callback.from_user.id, has_photo),
    )
    await callback.answer()


@router.message(StateFilter(AssistantEdit.photo), F.photo)
async def edit_photo_input(message: Message, state: FSMContext):
    file_id = message.photo[-1].file_id
    async with async_session() as session:
        assistant = await get_assistant(session, message.from_user.id)
        if assistant is None:
            await state.clear()
            await message.answer("❗ اول باید دستیار را بخری.")
            return
        assistant.photo_file_id = file_id
        await session.commit()
        text, markup, _ = await build_home(session, message.from_user.id)
    await state.clear()
    await message.answer("✅ عکسِ دستیار ذخیره شد.")
    await message.answer(text, reply_markup=markup)


@router.message(StateFilter(AssistantEdit.photo), F.chat.type == "private")
async def edit_photo_wrong(message: Message):
    await message.answer("⛔ لطفاً یک «عکس» بفرست (نه متن یا فایل)، یا «انصراف» را بزن.")


# ---------- حذفِ عکسِ دستیار ----------
@router.callback_query(F.data.startswith("assistant:photo:delete"))
async def photo_delete_cb(callback: CallbackQuery, state: FSMContext):
    # Stage 27: assistant editing is allowed only inside the bot private chat
    if callback.message is not None and callback.message.chat.type != "private":
        await callback.answer(
            "✏️ ویرایشِ دستیار فقط داخلِ خودِ ربات ممکن است، نه در گروه.",
            show_alert=True,
        )
        return
    if not await ensure_owner(callback):
        return
    await state.clear()
    async with async_session() as session:
        assistant = await get_assistant(session, callback.from_user.id)
        if assistant is None:
            await callback.answer("اول دستیار را بخر.", show_alert=True)
            return
        if not assistant.photo_file_id:
            await callback.answer("عکسی برای حذف وجود ندارد.", show_alert=True)
            return
        assistant.photo_file_id = None
        await session.commit()
        text, markup, _ = await build_home(session, callback.from_user.id)
    await safe_edit(callback.message, text, markup)
    await callback.answer("🗑️ عکسِ دستیار حذف شد.")


# ---------- تنظیماتِ یادآوری ----------
SETTINGS_TEXT = (
    "⚙️ <b>تنظیماتِ یادآوری</b>\n\n"
    "هر دسته را می‌توانی روشن (✅) یا خاموش (���) کنی. "
    "دستیار فقط دسته‌های روشن را یادآوری می‌کند."
)

_TOGGLE_FIELDS = {
    "salary": "notify_salary",
    "production": "notify_production",
    "income": "notify_income",
    "tips": "notify_tips",
}


@router.callback_query(F.data.startswith("assistant:settings"))
async def settings_cb(callback: CallbackQuery):
    if not await ensure_owner(callback):
        return
    async with async_session() as session:
        assistant = await get_assistant(session, callback.from_user.id)
        if assistant is None:
            await callback.answer("اول دستیار را بخر.", show_alert=True)
            return
        markup = settings_menu(assistant, callback.from_user.id)
    await safe_edit(callback.message, SETTINGS_TEXT, markup)
    await callback.answer()


@router.callback_query(F.data.startswith("assistant:toggle:"))
async def toggle_cb(callback: CallbackQuery):
    if not await ensure_owner(callback):
        return
    # callback.data = "assistant:toggle:<key>:<owner_id>"
    key = callback.data.split(":")[2]
    field = _TOGGLE_FIELDS.get(key)
    if field is None:
        await callback.answer("گزینه نامعتبر.", show_alert=True)
        return
    async with async_session() as session:
        assistant = await get_assistant(session, callback.from_user.id)
        if assistant is None:
            await callback.answer("اول دستیار را بخر.", show_alert=True)
            return
        setattr(assistant, field, not getattr(assistant, field))
        await session.commit()
        markup = settings_menu(assistant, callback.from_user.id)
    await safe_edit(callback.message, SETTINGS_TEXT, markup)
    await callback.answer("به‌روزرسانی شد.")


# ---------- ارتقای دستیار (هوشِ مصنوعیِ کوچک) ----------
def _upgrade_text(assistant) -> str:
    level = int(getattr(assistant, "upgrade_level", 1) or 1)
    info = upgrade_info(level)
    feats = unlocked_features(level)
    lines = [
        f"🧠 <b>ارتقای {assistant.name}</b>",
        f"سطحِ فعلی: <b>{info['name']}</b> (سطح {level})",
        "",
        "✅ بخش‌هایی که هم‌اکنون رصد می‌کنم:",
    ]
    lines += [f"• {feature_label(k)}" for k in feats]
    nxt = next_upgrade(level)
    if nxt is not None:
        lines += [
            "",
            f"⬆️ سطحِ بعدی: <b>{nxt['name']}</b>",
            f"{nxt['desc']}",
            "🔓 با این ارتقا باز می‌شود:",
        ]
        lines += [f"• {feature_label(k)}" for k in nxt["unlocks"]]
        lines += ["", f"💰 هزینه: <b>{nxt['cost']:,}</b> دلار"]
    else:
        lines += ["", "🏆 دستیارت به بالاترین سطح (هوشِ مصنوعیِ کامل) رسیده است."]
    return "\n".join(lines)


@router.callback_query(F.data.startswith("assistant:upgrade:do"))
async def upgrade_do_cb(callback: CallbackQuery):
    if not await ensure_owner(callback):
        return
    async with async_session() as session:
        player = await get_player(session, callback.from_user.id)
        assistant = await get_assistant(session, callback.from_user.id)
        if player is None or assistant is None:
            await callback.answer("اول دستیار را بخر.", show_alert=True)
            return
        level = int(getattr(assistant, "upgrade_level", 1) or 1)
        nxt = next_upgrade(level)
        if nxt is None:
            await callback.answer("دستیارت در بالاترین سطح است.", show_alert=True)
            return
        if player.cash < nxt["cost"]:
            await callback.answer(
                f"💸 پول کافی نداری! هزینه‌ی ارتقا: {nxt['cost']:,}$", show_alert=True
            )
            return
        player.cash -= nxt["cost"]
        assistant.upgrade_level = nxt["level"]
        from app.data import leveling as _lv
        _xp_res = {}
        try:   # Stage 27: XP for assistant upgrades
            _xp_res = await _lv.grant_xp(session, player, (60 + 30 * int(nxt["level"])) // 2, source="assistant_upgrade")
        except Exception:
            pass
        await session.commit()
        new_text = _upgrade_text(assistant)
        markup = upgrade_menu(callback.from_user.id, assistant.upgrade_level)
    await safe_edit(callback.message, new_text, markup)
    await callback.answer(f"🎉 دستیار به «{nxt['name']}» ارتقا یافت!" + _lv.xp_note(_xp_res), show_alert=True)


@router.callback_query(F.data.startswith("assistant:upgrade"))
async def upgrade_cb(callback: CallbackQuery):
    if not await ensure_owner(callback):
        return
    async with async_session() as session:
        assistant = await get_assistant(session, callback.from_user.id)
        if assistant is None:
            await callback.answer("اول دستیار را بخر.", show_alert=True)
            return
        text = _upgrade_text(assistant)
        markup = upgrade_menu(callback.from_user.id, int(getattr(assistant, "upgrade_level", 1) or 1))
    await safe_edit(callback.message, text, markup)
    await callback.answer()


# ---------- گزارش‌ها و یادآوری‌ها ----------
async def _gather_state(session, tg_user_id):
    estates = (await session.execute(
        select(Estate).where(Estate.tg_user_id == tg_user_id)
    )).scalars().all()
    factories = (await session.execute(
        select(Factory).where(Factory.tg_user_id == tg_user_id)
    )).scalars().all()
    return list(estates), list(factories)


# 🆕 مرحله ۳۰ — خطوطِ واقعیِ تولید (factory_products) برایِ تشخیصِ درستِ «کارخانهٔ بی‌کار»
async def _gather_lines(session, factories):
    """برایِ هر کارخانه، ردیف‌هایِ FactoryProduct را برمی‌گرداند: {factory_id: [rows]}"""
    out = {}
    if not factories:
        return out
    try:
        from app.models.factory import FactoryProduct
        ids = [int(f.id) for f in factories]
        rows = (await session.execute(
            select(FactoryProduct).where(FactoryProduct.factory_id.in_(ids))
        )).scalars().all()
        for r in rows:
            out.setdefault(int(r.factory_id), []).append(r)
    except Exception:
        return {}
    return out


def _factory_ready(f) -> bool:
    from app.data.market import get_product
    if f.status != "producing" or f.started_at is None:
        return False
    p = get_product(f.product_key)
    if not p:
        return False
    return datetime.utcnow() >= f.started_at + timedelta(hours=p["produce_hours"])


def _fp_is_ready(fp, speed_level) -> bool:
    """آیا این خطِ تولید تمام شده و محصولِ آماده دارد؟"""
    if getattr(fp, "status", "idle") != "producing" or getattr(fp, "started_at", None) is None:
        return False
    try:
        from app.data import factories as FAC
        hrs = FAC.effective_produce_hours(fp.product_key, speed_level)
    except Exception:
        hrs = 2
    return datetime.utcnow() >= fp.started_at + timedelta(hours=hrs)


def build_reminders(assistant, player, estates, factories, lines_by_factory=None) -> list:
    """لیستِ کارهای عقب‌مانده بر اساسِ دسته‌های روشن.

    🐞 مرحله ۳۰: قبلاً این تابع فقط ستونِ قدیمیِ Factory.status را می‌دید که از مرحله ۱۵
    دیگر استفاده نمی‌شود و همیشه «idle» می‌ماند؛ پس حتی وقتی کارخانه در حالِ تولید بود
    پیامِ «کارخانه بی‌کار است» تکرار می‌شد. حالا از خطوطِ واقعیِ factory_products خوانده می‌شود.
    """
    items = []
    if assistant.notify_production and factories:
        lines_by_factory = lines_by_factory or {}
        idle, producing, ready_n, stock_n = [], 0, 0, 0
        for f in factories:
            rows = lines_by_factory.get(int(f.id), [])
            speed = int(getattr(f, "speed_level", 1) or 1)
            if rows:
                busy = [r for r in rows if getattr(r, "status", "idle") == "producing"]
                done = [r for r in busy if _fp_is_ready(r, speed)]
                ready_n += len(done)
                stock_n += sum(1 for r in rows if int(getattr(r, "stock", 0) or 0) > 0)
                # در حالِ تولید = دست‌کم یک خطِ ناتمام دارد
                if len(busy) > len(done):
                    producing += 1
                elif not busy:
                    idle.append(f)
            else:
                # سازگاری با نسخه‌ی قدیمی (کارخانه‌ی بدونِ خطِ ثبت‌شده)
                if getattr(f, "status", "idle") == "producing":
                    if _factory_ready(f):
                        ready_n += 1
                    else:
                        producing += 1
                else:
                    idle.append(f)
                if int(getattr(f, "stock", 0) or 0) > 0:
                    stock_n += 1
        if idle:
            items.append(f"▶️ {len(idle)} کارخانه بی‌کار است — تولید را شروع کن.")
        elif producing and not ready_n:
            items.append(f"⚙️ {producing} کارخانه در حالِ تولید است — همه‌چیز مرتّب است. ✅")
        if ready_n:
            items.append(f"📦 {ready_n} خطِ تولید محصولِ آماده دارد — جمعش کن.")
        if stock_n:
            items.append(f"💵 {stock_n} خطِ تولید انبارِ پر دارد — در اوجِ قیمت بفروش.")
    if assistant.notify_income and estates:
        items.append("🏛️ به عمارت‌هایت سر بزن؛ درآمد آماده‌ی جمع‌آوری است.")
    if assistant.notify_salary and estates:
        items.append("💼 حقوقِ زیردستان را به‌موقع بده تا بازدهی نیفتد.")
    return items


def _xp_line(player) -> str:
    """Stage 27: XP progress + remaining XP for the assistant report."""
    from app.data import leveling as _lv

    try:
        return _lv.progress_line(player)
    except Exception:
        return ""


def build_tips(assistant, player) -> list:
    if not assistant.notify_tips:
        return []
    block = progression_for(player.level)
    lines = [f"🧭 <b>راهنمای سطحِ تو ({block['title']} — سطح {player.level}):</b>"]
    for t in block["tasks"]:
        lines.append(f"• {t}")
    lines.append(f"⏭️ گامِ بعدی: {block['next']}")
    # Stage 27: remind the player that almost everything grants XP now
    try:
        from app.data import leveling as _lv

        remaining = _lv.xp_remaining(player)
        if remaining > 0:
            lines.append(
                f"⚡ فقط <b>{remaining:,}</b> XP تا سطحِ {player.level + 1} مانده — ساخت‌وساز، "
                "ارتقا، استخدام، تولید، فروش، ارتش و ورزش XP می‌دهند؛ پاداش XP همهٔ این فعالیت‌ها طبق بالانس جدید نصف شده است."
            )
    except Exception:
        pass
    return lines


# ---------- بریف‌هایِ سطح‌بندی‌شده (هر کدام کاملاً دفاعی و try/except) ----------
async def _brief_war(session, player) -> list:
    try:
        from app.services import war_service
        from app.models.war import WarState
        power = await war_service.compute_combat_power(session, player.tg_user_id)
        parts = ["⚔️ <b>وضعیتِ نظامی:</b>", f"• قدرتِ رزمی: <b>{int(power):,}</b>"]
        parts.append("• قدرت = سطح + ارتش + عمارت‌های نظامی + ۲۰٪ درآمد روزانه + اثر لقب؛ جزئیات در «راهنمای نظامی».")
        st = await session.get(WarState, player.tg_user_id)
        if st is not None:
            shield = getattr(st, "shield_until", None)
            if shield and shield > datetime.utcnow():
                parts.append("• 🛡️ سپر فعال است.")
        return parts
    except Exception:
        return []


async def _brief_titles(session, player) -> list:
    try:
        from app.services import titles as tsvc
        owned = await tsvc.list_player_titles(session, player.tg_user_id)
        parts = [f"🏷️ <b>القاب:</b> {len(owned)} لقب کسب کرده‌ای."]
        try:
            disp = await tsvc.display_title(session, player.tg_user_id)
            if disp:
                parts.append(f"• لقبِ فعال: <b>{disp}</b>")
        except Exception:
            pass
        return parts
    except Exception:
        return []


async def _brief_alliance(session, player) -> list:
    try:
        from app.services import alliance_service as al
        mem = await al.get_membership(session, player.tg_user_id)
        if mem is None:
            return ["🤝 <b>اتحادیه:</b> هنوز عضوِ هیچ اتحادیه‌ای نیستی."]
        alliance = await al.get_alliance(session, mem.alliance_id)
        name = getattr(alliance, "name", None) or getattr(alliance, "tag", "?")
        count = await al.member_count(session, mem.alliance_id)
        return [f"🤝 <b>اتحادیه:</b> عضوِ «{name}» ({count} عضو)."]
    except Exception:
        return []


async def _brief_bank(session, player) -> list:
    try:
        from app.services import worldbank_service as wb
        net = await wb.net_worth_value(session, player.tg_user_id)
        parts = [f"🏦 <b>بانکِ مافیایی:</b> ارزشِ خالص ≈ <b>{int(net):,}</b>"]
        try:
            acc = await wb.get_account(session, player.tg_user_id)
            debt = wb.loan_balance(acc)
            if debt:
                parts.append(f"• ⚠️ وامِ بازپرداخت‌نشده: <b>{int(debt):,}</b>")
        except Exception:
            pass
        return parts
    except Exception:
        return []


async def _brief_news(session) -> list:
    try:
        from app.services.game_digest import build_game_digest
        from app.data import news as ndata

        text, n = await build_game_digest(session, hours=24, mark_published=False)
        bullets = [ln for ln in (text or "").splitlines() if ln.strip().startswith("• ")][:5]
        if bullets:
            return ["📰 <b>اخبار زنده:</b>"] + bullets
        items = []
        try:
            from app.services import news_service
            items = await news_service.recent_news(session, limit=3)
        except Exception:
            items = []
        if not items:
            return ["📰 <b>اخبار:</b> هنوز رویداد مهمی ثبت نشده — با جنگ و القاب پر می‌شود."]
        parts = ["📰 <b>تازه‌ترین اخبار:</b>"]
        for it in items:
            parts.append("• " + ndata.format_item(it.category, it.text))
        return parts
    except Exception:
        return []


async def build_private_report(session, assistant, player) -> str:
    """🆕 v1.7.5 — گزارش کامل پویا (نه متن خشک ثابت)."""
    try:
        from app.services import assistant_brain as brain

        core = await brain.full_dynamic_report(session, player.tg_user_id)
    except Exception:
        core = None

    estates, factories = await _gather_state(session, player.tg_user_id)
    level = int(getattr(assistant, "upgrade_level", 1) or 1)
    info = upgrade_info(level)
    feats = unlocked_features(level)
    if core:
        lines = [core, "", "— — —", ""]
    else:
        lines = [
            f"🤖 <b>گزارشِ {assistant.name}</b> — <i>{info['name']} (سطح {level})</i>",
            f"💵 موجودی: <b>{player.cash:,}</b> دلار | 🎚️ سطح: <b>{player.level}</b>",
            _xp_line(player),
            f"🏛️ عمارت‌ها: <b>{len(estates)}</b> | 🏭 کارخانه‌ها: <b>{len(factories)}</b>",
            "",
        ]
    _lines = await _gather_lines(session, factories)
    lines.append("🆕 <b>تازه‌های v1.7.8:</b> مسکونی ۶ طبقه + تبدیل ۳به۱، ساخت‌وساز زمان‌دار (۱ تا ۲۴ ساعت)، سقف تولید روزانهٔ مواد، ابرکارخانهٔ دون برای ثروت زیر ۳۰۰ میلیارد، گاوصندوق بانک، غنیمت جنگ ۱۴–۴۲٪")
    lines.append("")
    reminders = build_reminders(assistant, player, estates, factories, _lines)
    if reminders:
        lines.append("⏰ <b>کارهای عقب‌مانده:</b>")
        lines.extend(reminders)
    else:
        lines.append("✅ فعلاً کارِ عقب‌مانده‌ای نداری. آفرین!")

    seg_map = {
        "war": _brief_war,
        "titles": _brief_titles,
        "alliance": _brief_alliance,
        "bank": _brief_bank,
    }
    for key in ("war", "titles", "alliance", "bank"):
        if key in feats:
            seg = await seg_map[key](session, player)
            if seg:
                lines.append("")
                lines.extend(seg)
    if "news" in feats:
        seg = await _brief_news(session)
        if seg:
            lines.append("")
            lines.extend(seg)

    nxt = next_upgrade(level)
    if nxt is not None:
        locked = "، ".join(feature_label(k) for k in nxt["unlocks"])
        lines.append("")
        lines.append(
            f"🔒 برای بازکردنِ {locked} دستیار را به «{nxt['name']}» ارتقا بده ({nxt['cost']:,}$)."
        )

    tips = build_tips(assistant, player)
    if tips:
        lines.append("")
        lines.extend(tips)
    return "\n".join(lines)


async def build_public_report(session, assistant, player) -> str:
    """گزارشِ عمومی (بی‌خطر برای گروه) — بدونِ جزئیاتِ حساس مثلِ موجودی."""
    estates, factories = await _gather_state(session, player.tg_user_id)
    block = progression_for(player.level)
    return "\n".join([
        f"📋 <b>گزارشِ روزانه — {assistant.name}</b>",
        f"🎚️ درجه: <b>{block['title']}</b> (سطح {player.level})",
        # Stage 27: public report also shows the XP bar (no sensitive data)
        _xp_line(player),
        f"🏛️ عمارت‌ها: <b>{len(estates)}</b> | 🏭 کارخانه‌ها: <b>{len(factories)}</b>",
        "",
        "برای گزارشِ کامل و محرمانه، دکمه‌ی زیر را بزن تا در ربات برایت بفرستم. 🔐",
    ])


# ---------- 🆕 v1.7.5 ابزارهای پویای دستیار ----------
async def _assist_live(callback: CallbackQuery, kind: str):
    if not await ensure_owner(callback):
        return
    async with async_session() as session:
        player = await get_player(session, callback.from_user.id)
        assistant = await get_assistant(session, callback.from_user.id)
        if player is None or assistant is None:
            await callback.answer("اول دستیار را بخر.", show_alert=True)
            return
        from app.services import assistant_brain as brain

        if kind == "pulse":
            text = await brain.pulse_text(session, player.tg_user_id)
        elif kind == "ops":
            text = await brain.opportunities_text(session, player.tg_user_id)
        elif kind == "war":
            text = await brain.war_readiness_text(session, player.tg_user_id)
        elif kind == "mission":
            text = await brain.daily_mission_text(session, player.tg_user_id)
        elif kind == "radar":
            text = await brain.field_radar_text(session, player.tg_user_id)
        else:
            text = await build_private_report(session, assistant, player)
    await safe_edit(callback.message, text, live_actions_menu(callback.from_user.id))
    await callback.answer()


@router.callback_query(F.data.startswith("assistant:pulse"))
async def assist_pulse_cb(callback: CallbackQuery):
    await _assist_live(callback, "pulse")


@router.callback_query(F.data.startswith("assistant:ops"))
async def assist_ops_cb(callback: CallbackQuery):
    await _assist_live(callback, "ops")


@router.callback_query(F.data.startswith("assistant:war"))
async def assist_war_cb(callback: CallbackQuery):
    await _assist_live(callback, "war")


@router.callback_query(F.data.startswith("assistant:mission"))
async def assist_mission_cb(callback: CallbackQuery):
    await _assist_live(callback, "mission")


@router.callback_query(F.data.startswith("assistant:radar"))
async def assist_radar_cb(callback: CallbackQuery):
    await _assist_live(callback, "radar")


# ---------- گزارش/یادآوری در ربات ----------
@router.callback_query(F.data.startswith("assistant:report"))
async def report_cb(callback: CallbackQuery):
    if not await ensure_owner(callback):
        return
    async with async_session() as session:
        player = await get_player(session, callback.from_user.id)
        assistant = await get_assistant(session, callback.from_user.id)
        if player is None or assistant is None:
            await callback.answer("اول دستیار را بخر.", show_alert=True)
            return
        text = await build_private_report(session, assistant, player)
    await safe_edit(callback.message, text, live_actions_menu(callback.from_user.id))
    await callback.answer()


@router.callback_query(F.data.startswith("assistant:reminders"))
async def reminders_cb(callback: CallbackQuery):
    if not await ensure_owner(callback):
        return
    async with async_session() as session:
        player = await get_player(session, callback.from_user.id)
        assistant = await get_assistant(session, callback.from_user.id)
        if player is None or assistant is None:
            await callback.answer("اول دستیار را بخر.", show_alert=True)
            return
        estates, factories = await _gather_state(session, player.tg_user_id)
        _lines = await _gather_lines(session, factories)
    reminders = build_reminders(assistant, player, estates, factories, _lines)
    tips = build_tips(assistant, player)
    lines = [f"⏰ <b>کارهای عقب‌مانده — {assistant.name}</b>", ""]
    if reminders:
        lines.extend(reminders)
    else:
        lines.append("✅ همه‌چیز مرتب است؛ کارِ عقب‌مانده‌ای نداری.")
    if tips:
        lines.append("")
        lines.extend(tips)
    await safe_edit(callback.message, "\n".join(lines), panel_menu(callback.from_user.id))
    await callback.answer()


# ---------- گزارش در گروه (عمومی / محرمانه) ----------
@router.callback_query(F.data.startswith("assistant:pubreport"))
async def pubreport_cb(callback: CallbackQuery):
    if not await ensure_owner(callback):
        return
    async with async_session() as session:
        player = await get_player(session, callback.from_user.id)
        assistant = await get_assistant(session, callback.from_user.id)
        if player is None or assistant is None:
            await callback.answer("دستیاری پیدا نشد.", show_alert=True)
            return
        text = await build_public_report(session, assistant, player)
    await safe_edit(callback.message, text, group_menu(callback.from_user.id))
    await callback.answer()


@router.callback_query(F.data.startswith("assistant:privreport"))
async def privreport_cb(callback: CallbackQuery):
    if not await ensure_owner(callback):
        return
    async with async_session() as session:
        player = await get_player(session, callback.from_user.id)
        assistant = await get_assistant(session, callback.from_user.id)
        if player is None or assistant is None:
            await callback.answer("دستیاری پیدا نشد.", show_alert=True)
            return
        text = await build_private_report(session, assistant, player)
    try:
        await callback.bot.send_message(
            callback.from_user.id,
            text,
            reply_markup=panel_menu(callback.from_user.id),
        )
        await callback.answer("گزارشِ محرمانه در ربات برایت ارسال شد ✉️", show_alert=True)
    except TelegramForbiddenError:
        await callback.answer(
            "اول ربات را در چتِ خصوصی /start کن تا بتوانم پیام بفرستم.",
            show_alert=True,
        )


# ---------- صدا زدن در گروه (فیلترِ سفارشی) ----------
class AssistantNameFilter(BaseFilter):
    """وقتی کاربر نامِ دستیارِ خودش را در گروه بنویسد True می‌شود."""

    async def __call__(self, message: Message) -> bool:
        if message.chat.type not in ("group", "supergroup"):
            return False
        if not message.text or message.from_user is None:
            return False
        async with async_session() as session:
            assistant = await get_assistant(session, message.from_user.id)
        if assistant is None:
            return False
        return assistant.name.lower() in message.text.lower()


@router.message(AssistantNameFilter())
async def assistant_called_in_group(message: Message):
    async with async_session() as session:
        assistant = await get_assistant(session, message.from_user.id)
        player = await get_player(session, message.from_user.id)
    if assistant is None or player is None:
        return
    caller = message.from_user.first_name or "رفیق"
    text = (
        f"🤵 <b>{assistant.name}</b> در خدمتِ توام، {caller}.\n"
        "گزارشِ روزانه را همین‌جا ببین یا گزارشِ محرمانه را در ربات بگیر:"
    )
    markup = group_menu(message.from_user.id)
    if assistant.photo_file_id:
        await message.reply_photo(assistant.photo_file_id, caption=text, reply_markup=markup)
    else:
        await message.reply(text, reply_markup=markup)

# ---------- بچ ۵: دستیار دومِ اشتراک طلایی ----------
async def _second_panel(session, uid):
    second=await get_second_assistant(session, uid)
    if not await _second_allowed(session, uid):
        return None, "🔒 این گزینه مخصوص کاربرانِ دارای اشتراکِ طلایی است؛ برای فعال‌سازی ابتدا اشتراک تهیه کنید.", assistant2_buy_menu(uid)
    if second is None:
        return None, "🧩 <b>دستیار دوم</b>\nدستیار دوم فقط در پاسخ به یک پیام و با دستورِ شخصی تو جواب می‌دهد.", assistant2_buy_menu(uid)
    commands=(await session.execute(select(SecondAssistantCommand).where(SecondAssistantCommand.owner_id == uid))).scalars().all()
    configured=bool(commands or (second.trigger_text and second.reply_text))
    text=(f"🧩 <b>{second.name}</b> — دستیار دوم\n"
          f"تعداد دستورهای تنظیم‌شده: <b>{len(commands) + (1 if second.trigger_text and second.reply_text and not commands else 0)}</b>\n\n"
          "در گروه فعال‌سازی کن، سپس فقط با ریپلای به پیام دستیار دستورها را بنویس.")
    return second, text, assistant2_menu(uid, configured)

@router.callback_query(F.data.startswith("assistant:home"))
async def assistants_home_cb(callback):
    if not await ensure_owner(callback): return
    async with async_session() as session: second=await get_second_assistant(session, callback.from_user.id)
    await safe_edit(callback.message, "🤖 <b>دستیاران</b>", assistants_home_menu(callback.from_user.id, bool(second))); await callback.answer()

@router.callback_query(F.data.startswith("assistant2:hub"))
async def assistant2_hub(callback):
    if not await ensure_owner(callback): return
    async with async_session() as session: _, text, markup=await _second_panel(session, callback.from_user.id)
    await safe_edit(callback.message, text, markup); await callback.answer()

@router.callback_query(F.data.startswith("assistant2:buy"))
async def assistant2_buy(callback):
    if not await ensure_owner(callback): return
    uid=callback.from_user.id
    async with async_session() as session:
        if not await _second_allowed(session, uid):
            await callback.answer("این گزینه مخصوص کاربرانِ دارای اشتراکِ طلایی است؛ برای فعال‌سازی ابتدا اشتراک تهیه کنید.", show_alert=True); return
        second=await get_second_assistant(session, uid)
        if second is None:
            second=SecondAssistant(tg_user_id=uid); session.add(second); await session.flush()
        if callback.message.chat.type in ("group", "supergroup"):
            existing=await session.get(SecondAssistantChat, uid)
            if existing is None:
                existing=SecondAssistantChat(owner_id=uid, chat_id=callback.message.chat.id, message_id=callback.message.message_id, active=True); session.add(existing)
            else:
                existing.chat_id=callback.message.chat.id; existing.message_id=callback.message.message_id; existing.active=True
            await session.commit()
            text=(f"🧩 <b>{second.name}</b> فعال شد.\n"
                  "روی همین پیام ریپلای کن و هر تعداد از دستورهای تعریف‌شده را در یک پیام بنویس؛ پاسخ همه در یک پیام می‌آید.")
            await safe_edit(callback.message, text, assistant2_chat_menu(uid)); await callback.answer("چت با دستیار دوم فعال شد."); return
        await session.commit(); _, text, markup=await _second_panel(session, uid)
    await safe_edit(callback.message, text, markup); await callback.answer("دستیار دوم فعال شد. برای شروع چت گروهی، در گروه «منو» را بزن.")

@router.callback_query(F.data.startswith("assistant2:name"))
async def assistant2_name(callback, state):
    if not await ensure_owner(callback): return
    await state.set_state(SecondAssistantEdit.name); await safe_edit(callback.message, "نام دستیار دوم را بفرست (حداکثر ۲۰ نویسه)." + CANCEL_HINT, None); await callback.answer()

@router.message(SecondAssistantEdit.name, F.chat.type == "private")
async def assistant2_name_save(message, state):
    if await handle_cancel_word(message, state): return
    name=clean_name(message.text or "")
    if name is None: await message.answer("نام معتبر بفرست."); return
    async with async_session() as session:
        second=await get_second_assistant(session, message.from_user.id)
        if second is None: await state.clear(); return
        second.name=name; await session.commit(); _, text, markup=await _second_panel(session, message.from_user.id)
    await state.clear(); await message.answer(text, reply_markup=markup)

@router.callback_query(F.data.startswith("assistant2:command"))
async def assistant2_command(callback, state):
    if not await ensure_owner(callback): return
    await state.set_state(SecondAssistantEdit.trigger); await safe_edit(callback.message, "دستور دستیار دوم را بفرست." + CANCEL_HINT, None); await callback.answer()

@router.message(SecondAssistantEdit.trigger, F.chat.type == "private")
async def assistant2_trigger_save(message, state):
    if await handle_cancel_word(message, state): return
    text=(message.text or "").strip()
    if not text: await message.answer("دستور نمی‌تواند خالی باشد."); return
    await state.update_data(second_trigger=text); await state.set_state(SecondAssistantEdit.reply); await message.answer("حالا پاسخ دلخواه را بفرست." + CANCEL_HINT)

@router.message(SecondAssistantEdit.reply, F.chat.type == "private")
async def assistant2_reply_save(message, state):
    if await handle_cancel_word(message, state): return
    reply=(message.text or "").strip(); data=await state.get_data()
    if not reply: await message.answer("پاسخ نمی‌تواند خالی باشد."); return
    async with async_session() as session:
        second=await get_second_assistant(session, message.from_user.id)
        if second is None: await state.clear(); return
        trigger=data.get("second_trigger")
        # هر بار یک دستور/جواب جدید افزوده می‌شود؛ بنابراین چند دستور در یک پیام پشتیبانی می‌شود.
        session.add(SecondAssistantCommand(owner_id=message.from_user.id, trigger_text=trigger, reply_text=reply))
        if not second.trigger_text: second.trigger_text=trigger; second.reply_text=reply
        await session.commit(); _, text, markup=await _second_panel(session, message.from_user.id)
    await state.clear(); await message.answer(text, reply_markup=markup)

@router.callback_query(F.data.startswith("assistant2:help"))
async def assistant2_help(callback):
    if not await ensure_owner(callback): return
    await callback.answer(); await safe_edit(callback.message, "📘 <b>راهنمای دستیار دوم</b>\nدر گروه از «منو» → «دستیاران» → «دستیار دوم» → «فعال‌سازی» استفاده کن. سپس روی آخرین پیام دستیار ریپلای کن. تا زمان زدن «پایان چت با دستیار دوم»، هر پیام ریپلای‌شده بررسی می‌شود. اگر چند دستور تعریف‌شده را در یک پیام بنویسی، همه پاسخ‌های مربوط را در یک پیام می‌گیری.", assistant2_menu(callback.from_user.id, True))

@router.message(F.reply_to_message, F.text)
async def second_assistant_reply(message):
    # فقط در چت فعال و با ریپلای به آخرین پیامِ دستیار دوم پاسخ می‌دهد.
    # 🐞 رفعِ باگِ بزرگ: این هندلر فیلترِ (F.reply_to_message, F.text) دارد، یعنی
    # هر پیامِ متنیِ ریپلای‌شده را می‌گیرد. اگر فقط return کند، aiogram آپدیت را
    # «رسیدگی‌شده» می‌داند و روترهای بعدی (مثلاً انتقال، مخاطبین، جنگ)
    # دیگر اجرا نمی‌شوند. پس حتماً باید SkipHandler پرتاب شود.
    if message.chat.type not in ("group", "supergroup") or not message.reply_to_message:
        raise SkipHandler
    async with async_session() as session:
        chats=(await session.execute(select(SecondAssistantChat).where(
            SecondAssistantChat.chat_id == message.chat.id,
            SecondAssistantChat.message_id == message.reply_to_message.message_id,
            SecondAssistantChat.active == True,
        ))).scalars().all()
        answers=[]; owner_ids=[]
        for chat in chats:
            if not await _second_allowed(session, chat.owner_id):
                chat.active=False; continue
            second=await get_second_assistant(session, chat.owner_id)
            commands=(await session.execute(select(SecondAssistantCommand).where(SecondAssistantCommand.owner_id == chat.owner_id))).scalars().all()
            if not commands and second and second.trigger_text and second.reply_text:
                commands=[second]
            matched=[]
            for command in commands:
                if command.trigger_text and command.trigger_text.lower() in (message.text or "").lower():
                    matched.append(command.reply_text)
            if matched:
                label=second.name if second else "دستیار دوم"
                answers.append(f"🧩 <b>{label}</b>:\n" + "\n".join(f"• {x}" for x in matched))
                owner_ids.append(chat.owner_id)
        await session.commit()
    if not answers:
        raise SkipHandler   # 🐞 هیچ دستورِ دستیاری نخورد → پیام را به روترهای بعدی تحویل بده
    # محدودیت سفارشی برای طول دستور/پاسخ حذف شده است. اگر پاسخ‌های چند دستور
    # از سقف فنی یک پیام تلگرام عبور کنند، بدون از دست‌رفتن متن در چند پیام ارسال می‌شوند.
    full_answer = "\n\n".join(answers)
    chunks = []
    while full_answer:
        if len(full_answer) <= 4000:
            chunks.append(full_answer)
            break
        cut = full_answer.rfind("\n", 0, 4000)
        if cut < 1:
            cut = 4000
        chunks.append(full_answer[:cut])
        full_answer = full_answer[cut:].lstrip("\n")
    sent = None
    for index, chunk in enumerate(chunks):
        sent = await message.reply(
            chunk,
            reply_markup=assistant2_chat_menu(owner_ids[0]) if index == len(chunks) - 1 else None,
        )
    async with async_session() as session:
        for owner_id in owner_ids:
            chat=await session.get(SecondAssistantChat, owner_id)
            if chat and chat.chat_id == message.chat.id: chat.message_id=sent.message_id
        await session.commit()

@router.callback_query(F.data.startswith("assistant2:end"))
async def assistant2_end_chat(callback):
    if not await ensure_owner(callback): return
    async with async_session() as session:
        chat=await session.get(SecondAssistantChat, callback.from_user.id)
        if chat and chat.chat_id == callback.message.chat.id:
            chat.active=False; await session.commit()
    await safe_edit(callback.message, "🛑 چت با دستیار دوم پایان یافت. برای شروع دوباره، در گروه «منو» → «دستیاران» → «دستیار دوم» را بزن.", None)
    await callback.answer("چت پایان یافت.")


@router.callback_query(F.data.startswith("assistant2:photo"))
async def assistant2_photo(callback, state):
    if not await ensure_owner(callback): return
    async with async_session() as session:
        from app.services.restrictions import blocked
        if await blocked(session, callback.from_user.id, "photo"):
            await callback.answer("عکس‌گذاری شما توسط ادمین محدود شده است.", show_alert=True); return
    await state.set_state(SecondAssistantEdit.photo)
    await safe_edit(callback.message, "یک عکس برای دستیار دوم بفرست؛ یا «انصراف» را بنویس.", None)
    await callback.answer()

@router.message(SecondAssistantEdit.photo, F.photo)
async def assistant2_photo_save(message, state):
    async with async_session() as session:
        from app.services.restrictions import blocked
        if await blocked(session, message.from_user.id, "photo"):
            await state.clear(); await message.answer("عکس‌گذاری شما توسط ادمین محدود شده است."); return
        second=await get_second_assistant(session, message.from_user.id)
        if second is None:
            await state.clear(); return
        second.photo_file_id=message.photo[-1].file_id; await session.commit(); _, text, markup=await _second_panel(session, message.from_user.id)
    await state.clear(); await message.answer(text, reply_markup=markup)

@router.message(SecondAssistantEdit.photo, F.chat.type == "private")
async def assistant2_photo_invalid(message, state):
    if await handle_cancel_word(message, state): return
    await message.answer("لطفاً عکس بفرست یا «انصراف» را بنویس.")
