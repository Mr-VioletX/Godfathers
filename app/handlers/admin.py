# -*- coding: utf-8 -*-
"""هندلرِ سیستمِ ادمین / ادمین‌مود (مرحله ۲۱ — بخشِ نهایی).

ویژگی‌ها:
  • ورود/خروج فقط متنی (بدونِ دکمه): «ادمین مود» / «خروج از حالتِ ادمین مود»
  • فقط برایِ ادمینِ اصلی و ادمین‌هایِ منتصب واکنش می‌دهد (بقیه بی‌پاسخ)
  • ورود با رمز؛ اولین ورودِ ادمینِ منتصب → اجبارِ تغییرِ رمز
  • پنلِ پویا: هر ادمین فقط دکمه‌یِ بخش‌هایِ مجازِ خودرا می‌بیند
"""
import json
import logging

from aiogram import F, Router
from aiogram.filters import BaseFilter, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import func, select

from app.data import admin as A
from app.data import events as EV
from app.data import leveling
from app.data import subscription as S
from app.data import titles as TDATA
from app.database.engine import async_session
from app.keyboards.admin_menu import (
    admin_admins_kb,
    admin_broadcast_confirm_kb,
    admin_broadcast_kb,
    admin_channel_kb,
    admin_force_join_kb,
    admin_force_join_channel_kb,
    admin_events_kb,
    admin_exit_confirm_kb,
    admin_home_kb,
    admin_news_kb,
    admin_reports_kb,
    admin_sub_kb,
    admin_titles_kb,
    admin_tools_kb,
    admin_users_kb,
    admin_economy_kb,
    admin_level_xp_kb,
    admin_news_broadcast_kb,
    admin_assistants_kb,
    admin_assistant_user_kb,
    back_kb,
    cancel_kb,
    perms_picker_kb,
    admin_game_settings_kb,
    admin_activity_kb,
    sub_price_tier_kb,
    sub_receipts_kb,
    sub_requests_kb,
    sports_reset_confirm_kb,
    spam_reports_kb,
    sub_tier_kb,
    tools_reset_confirm_kb,
    tools_delete_confirm_kb,
    rank_visibility_kb,
    backup_admin_kb,
    user_card_kb,
    users_list_kb,
    USERS_PER_PAGE,
    titled_user_actions_kb,
    titled_users_kb,
    admin_numbers_kb,
    admin_control_kb,
    admin_control_scope_kb,
    admin_control_sections_kb,
    referral_admin_kb,
    admin_tools_resets_kb,
    admin_tools_settings_kb,
    admin_city_balance_kb,
    admin_worldbank_kb,
)
from app.keyboards.main_menu import main_menu
from app.models.player import Player
from app.models.admin import SpamReport, GameRestriction, GameNumberSetting
from app.models.title import PlayerTitle, TitleProfile, TitleApproval
from app.services import admin_service as adm
from app.services import event_service
from app.services import news_service, subscription_service
from app.services import titles as titles_svc
from app.services import military_service
from app.states import AdminStates
# 🐞 v1.7.6.3 — with_owner و safe_answer در سطحِ ماژول import نشده بودند، اما در
#   ۱۰ نقطه — از جمله کلِ بخشِ «منتظر پرداخت/رسید» — استفاده می‌شدند.
#   نتیجه NameError خامی بود که هندلر را پیش از callback.answer می‌کشت؛ پس
#   تلگرام هیچ پاسخی نمی‌گرفت و دکمه عملاً «هیچ کاری نمی‌کرد».
#   این ریشهٔ اصلیِ خرابیِ بخشِ پرداخت/رسید بود.
from app.utils.ui import (
    CANCEL_HINT,
    ensure_owner,
    handle_cancel_word,
    safe_answer,
    safe_edit,
    split_owner,
    with_owner,
)

log = logging.getLogger(__name__)
router = Router(name="admin")

# 🆕 اصلاحِ باگ: ادمین‌مود فقط باید داخلِ چتِ خصوصیِ ربات کار کند و در گروه
# به‌هیچ‌عنوان واکنش نشان ندهد (نه با متن، نه با دکمه). این فیلترِ سطحِ روتر
# جلوی همه‌ی هندلرهای پایین را در گروه/سوپرگروه/کانال می‌گیرد.
router.message.filter(F.chat.type == "private")
router.callback_query.filter(F.message.chat.type == "private")

# message_id پنلِ ادمینِ هر کاربر (برای پاک‌کردن هنگامِ خروج)
PANEL_MSG: dict[int, int] = {}


def _norm(text: str | None) -> str:
    return (text or "").strip()


# --------------------------- فیلترِ متنی ---------------------------
class TextIn(BaseFilter):
    """مطابقتِ دقیقِ متن با مجموعه‌ای از کلمات (ورود/خروج/راهنما)."""

    def __init__(self, words: set[str]):
        self.words = words

    async def __call__(self, message: Message) -> bool:
        return bool(message.text) and _norm(message.text) in self.words


# --------------------------- کمکی‌هایِ پارس ---------------------------
def _parse_int(text: str | None) -> int | None:
    t = _norm(text)
    if t.lstrip("-+").isdigit():
        try:
            return int(t)
        except ValueError:
            return None
    return None


async def _guard_admin(message: Message, state: FSMContext):
    """بررسی‌یِ اینکه کاربر هنوز ادمینِ فعال و درِ حالتِ ادمین است. خروجی: admin یا None."""
    uid = message.from_user.id
    if not await adm.is_in_admin_mode(uid):
        await state.clear()
        return None
    async with async_session() as session:
        admin = await adm.get_admin(session, uid)
    if admin is None:
        await state.clear()
        await adm.exit_admin_mode(uid)
    return admin


# ---------------------------------------------------------------------------
# متنِ پنل + ارسال/به‌روزرسانی
# ---------------------------------------------------------------------------
def _panel_text(admin, note: str = "") -> str:
    is_main = admin.role == "main"
    title = "👑 <b>پنلِ ادمینِ اصلی (خدایِ بازی)</b>" if is_main else "🛡️ <b>پنلِ ادمین</b>"
    lines = [title, ""]
    if not is_main:
        perms = adm.perms_of(admin)
        if perms:
            lines.append("دسترسی‌هایِ فعال: " + "، ".join(A.PERMISSIONS[k]["label"] for k in perms))
        else:
            lines.append("فعلاً هیچ دسترسیِ فعالی نداری.")
    else:
        lines.append("دسترسیِ کامل به همه‌یِ بخش‌ها.")
    lines.append("")
    lines.append("یک بخش را انتخاب کن 👇")
    if note:
        lines += ["", note]
    return "\n".join(lines)


async def _send_panel(message: Message, uid: int, admin, note: str = "") -> None:
    kb = admin_home_kb(uid, adm.perms_of(admin), admin.role == "main")
    old = PANEL_MSG.get(uid)
    if old:
        try:
            await message.bot.delete_message(message.chat.id, old)
        except Exception:
            pass
    sent = await message.answer(_panel_text(admin, note), reply_markup=kb)
    PANEL_MSG[uid] = sent.message_id


async def _refresh_panel(callback: CallbackQuery, admin, note: str = "") -> None:
    kb = admin_home_kb(callback.from_user.id, adm.perms_of(admin), admin.role == "main")
    await safe_edit(callback.message, _panel_text(admin, note), kb)
    PANEL_MSG[callback.from_user.id] = callback.message.message_id


async def _cb_admin(callback: CallbackQuery):
    """بررسیِ مالکیت + ادمینِ فعالِ در حالتِ ادمین. خروجی: admin یا None."""
    if not await ensure_owner(callback):
        return None
    uid = callback.from_user.id
    if not await adm.is_in_admin_mode(uid):
        await callback.answer("⛔ دیگر درِ حالتِ ادمین نیستی.", show_alert=True)
        return None
    async with async_session() as session:
        admin = await adm.get_admin(session, uid)
    if admin is None:
        await adm.exit_admin_mode(uid)
        await callback.answer("⛔ دسترسیِ ادمینِ تو لغو شده است.", show_alert=True)
        return None
    return admin


def _with_subs(markup, owner_id: int, key: str, admin):
    """🆕 v1.7.8.15 — دکمه‌ی زیرمنوهایِ مجاز را به منویِ والد می‌چسباند.

    خانه‌ی پنل شلوغ شده بود؛ حالا بخش‌هایِ فرعی داخلِ منویِ مرتبطِ
    خودشان نشان داده می‌شوند و فقط برایِ ادمینی که دسترسی‌اش را دارد ظاهر می‌شوند.
    ردیفِ «بازگشت» همیشه آخرین ردیف می‌ماند.
    """
    if markup is None:
        return markup
    kids = [c for c in A.children_of(key) if _require(admin, c)]
    if not kids:
        return markup
    rows = [list(r) for r in (markup.inline_keyboard or [])]
    tail = rows.pop() if rows else None
    for i in range(0, len(kids), 2):
        rows.append([
            InlineKeyboardButton(
                text=f"{A.PERMISSIONS[c]['emoji']} {A.PERMISSIONS[c]['label']}",
                callback_data=with_owner(f"adm:sec:{c}", owner_id),
            )
            for c in kids[i:i + 2]
        ])
    if tail is not None:
        rows.append(tail)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _require(admin, perm_key: str) -> bool:
    return adm.has_permission(admin, perm_key)


# ===========================================================================
# 🆕 مرحله ۲۹ — رفعِ باگِ اعطایِ دسترسی به ادمین‌هایِ فرعی
# ریشه‌ی مشکل: انتخابِ دسترسی‌ها فقط در FSM نگه داشته می‌شد؛
# با هر پیامِ دیگر یا تایم‌اوت، state پاک می‌شد و ذخیره‌ی دسترسی‌ها خطا می‌داد.
# راه‌حل: انتخابِ موقت در جدولِ admin_settings هم ذخیره می‌شود.
# ===========================================================================
_PPERM_PREFIX = "pperm"


async def _pperm_load(uid: int) -> dict | None:
    async with async_session() as session:
        raw = await adm.get_setting(session, f"{_PPERM_PREFIX}:{uid}")
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None


async def _pperm_save(uid: int, target, selected, action: str) -> None:
    payload = json.dumps(
        {"target": target, "selected": list(selected or []), "action": action},
        ensure_ascii=False,
    )
    async with async_session() as session:
        await adm.set_setting(session, f"{_PPERM_PREFIX}:{uid}", payload)


async def _pperm_clear(uid: int) -> None:
    async with async_session() as session:
        await adm.set_setting(session, f"{_PPERM_PREFIX}:{uid}", "")


async def _pperm_state(event, state) -> tuple:
    """(target, selected, action) — اول از دیتابیس، وگرنه از FSM."""
    uid = event.from_user.id
    rec = await _pperm_load(uid)
    if rec and rec.get("target"):
        return (
            int(rec["target"]),
            [k for k in (rec.get("selected") or []) if A.is_valid_perm(k)],
            rec.get("action") or "add",
        )
    data = await state.get_data()
    target = data.get("target")
    return (
        int(target) if target else None,
        list(data.get("selected", [])),
        data.get("admin_action", "add"),
    )


async def _guard_perm(message: Message, state: FSMContext, perm_key: str):
    """🆕 مرحله ۲۷ (رفعِ باگِ سطحِ دسترسیِ ادمینِ فرعی) — علاوه بر بودن در حالتِ ادمین،
    در هر مرحله‌یِ فرم هم دسترسیِ لازم دوباره از دیتابیس خوانده می‌شود؛ پس اگر ادمینِ اصلی
    درِ میانهٔ کار دسترسی را پس بگیرد، همان‌جا جلویِ ادامهٔ کار گرفته می‌شود."""
    admin = await _guard_admin(message, state)
    if admin is None:
        return None
    if not adm.has_permission(admin, perm_key):
        await state.clear()
        await message.answer(A.denied_text(perm_key))
        return None
    return admin


# ---------------------------------------------------------------------------
# ورود به حالتِ ادمین (کلمه‌یِ متنی)
# ---------------------------------------------------------------------------
@router.message(TextIn(A.ENTER_WORDS))
async def enter_admin(message: Message, state: FSMContext):
    uid = message.from_user.id
    async with async_session() as session:
        await adm.ensure_seed_main_admin(session)
        admin = await adm.get_admin(session, uid)
    if admin is None:
        return  # کاربرِ عادی/عزل‌شده → هیچ واکنشی (ضدِ سوءاستفاده)
    if await adm.is_in_admin_mode(uid):
        await state.clear()
        await _send_panel(message, uid, admin)
        return
    await state.clear()
    if admin.password_hash is None:
        await state.set_state(AdminStates.waiting_new_password)
        await message.answer(
            "🔐 اولین ورود. یک رمزِ جدید برایِ حالتِ ادمین تعیین کن (حداقل ۴ کاراکتر):\n"
            "⚠️ رمز باید فقط با حروف/اعدادِ انگلیسی باشد (فارسی مجاز نیست تا خطا پیش نیاید).\n"
            "↩️ در صورتِ پشیمونی می‌تونی کلمه‌ی «انصراف» را بفرستی."
        )
        return
    await state.set_state(AdminStates.waiting_login_password)
    await message.answer(
        "🔐 رمزِ ورود به حالتِ ادمین را بفرست:\n"
        "↩️ در صورتِ پشیمونی می‌تونی کلمه‌ی «انصراف» را بفرستی."
    )


@router.message(StateFilter(AdminStates.waiting_login_password))
async def login_password(message: Message, state: FSMContext):
    uid = message.from_user.id
    pw = _norm(message.text)
    if pw in A.CANCEL_WORDS:
        await state.clear()
        try:
            await message.delete()
        except Exception:
            pass
        await message.answer("↩️ ورود به حالتِ ادمین لغو شد.")
        return
    async with async_session() as session:
        admin = await adm.get_admin(session, uid)
        if admin is None:
            await state.clear()
            return
        ok = await adm.verify_login(session, uid, pw)
        must_change = admin.must_change_password
    try:
        await message.delete()   # پاک‌کردنِ رمز (امنیت)
    except Exception:
        pass
    if not ok:
        await message.answer("⛔ رمز نادرست است. دوباره بفرست (یا «خروج از حالتِ ادمین مود»).")
        return
    if must_change:
        await state.set_state(AdminStates.waiting_new_password)
        await message.answer("🔑 ورود موفق. این اولین ورودِ توست؛ یک رمزِ جدید تعیین کن:")
        return
    await _finalize_enter(message, state, uid)


@router.message(StateFilter(AdminStates.waiting_new_password))
async def new_password(message: Message, state: FSMContext):
    uid = message.from_user.id
    if _norm(message.text) in A.CANCEL_WORDS:
        await state.clear()
        try:
            await message.delete()
        except Exception:
            pass
        await message.answer("↩️ تعیینِ رمزِ جدید لغو شد. هر زمان خواستی دوباره «ادمین مود» را بفرست.")
        return
    ok, res = A.password_ok(message.text)
    try:
        await message.delete()
    except Exception:
        pass
    if not ok:
        await message.answer(f"⚠ {res}\nدوباره بفرست:")
        return
    async with async_session() as session:
        admin = await adm.get_admin(session, uid)
        if admin is None:
            await state.clear()
            return
        await adm.set_password(session, uid, res)
        await adm.audit(session, uid, "change_password")
    await message.answer("✅ رمزِ جدید ذخیره شد.")
    await _finalize_enter(message, state, uid)


async def _finalize_enter(message: Message, state: FSMContext, uid: int) -> None:
    await state.clear()
    await adm.enter_admin_mode(uid)
    async with async_session() as session:
        admin = await adm.get_admin(session, uid)
        await adm.audit(session, uid, "enter_admin_mode")
    await _send_panel(message, uid, admin, note="✅ واردِ حالتِ ادمین شدی.")


# ---------------------------------------------------------------------------
# 🆕 تغییرِ خودخواسته‌یِ رمز (هر زمان، از داخلِ پنل) + همگام‌سازی از فایلِ .env
# ---------------------------------------------------------------------------
@router.callback_query(F.data.startswith("adm:pw:change"))
async def pw_change_cb(callback: CallbackQuery, state: FSMContext):
    admin = await _cb_admin(callback)
    if admin is None:
        return
    await state.set_state(AdminStates.self_change_password)
    await safe_edit(
        callback.message,
        (
            "🔑 رمزِ جدیدت را بفرست (حداقل ۴ کاراکتر، بدونِ فاصله):\n"
            "⚠️ رمز باید فقط با حروف/اعدادِ انگلیسی باشد (فارسی مجاز نیست).\n"
            "↩️ در صورتِ پشیمونی می‌تونی کلمه‌ی «انصراف» را بفرستی یا دکمه‌ی پایین را بزنی."
        ),
        cancel_kb(callback.from_user.id),
    )
    await callback.answer()


@router.message(StateFilter(AdminStates.self_change_password))
async def self_change_password(message: Message, state: FSMContext):
    uid = message.from_user.id
    admin = await _guard_admin(message, state)
    if admin is None:
        return
    if _norm(message.text) in A.CANCEL_WORDS:
        await state.clear()
        try:
            await message.delete()
        except Exception:
            pass
        await _send_panel(message, uid, admin, note="↩️ تغییرِ رمز لغ�� شد.")
        return
    ok, res = A.password_ok(message.text)
    try:
        await message.delete()
    except Exception:
        pass
    if not ok:
        await message.answer(f"⚠ {res}\nدوباره بفرست:")
        return
    async with async_session() as session:
        await adm.set_password(session, uid, res)
        await adm.audit(session, uid, "change_password")
        admin = await adm.get_admin(session, uid)
    await state.clear()
    await _send_panel(message, uid, admin, note="✅ رمزِ ورودت تغییر کرد.")


@router.message(TextIn(A.SYNC_PW_WORDS))
async def sync_pw_from_env(message: Message):
    """🆕 فقط ادمینِ اصلی: بازنشانیِ رمز از مقدارِ ADMIN_PASSWORD در فایلِ .env."""
    uid = message.from_user.id
    if not await adm.is_in_admin_mode(uid):
        return
    async with async_session() as session:
        admin = await adm.get_admin(session, uid)
        if admin is None or admin.role != "main":
            return
        ok, note = await adm.sync_password_from_env(session, uid)
        if ok:
            await adm.audit(session, uid, "sync_password_from_env")
    await message.answer(note)


# ---------------------------------------------------------------------------
# خروج از حالتِ ادمین
# ---------------------------------------------------------------------------
# 🆕 مرحله ۲۷ — خروج از حالتِ ادمین دومرحله‌ای شد: چه با کلمه‌ی متنی و چه با دکمه،
# اول تأیید گرفته می‌شود تا ادمین اتفاقی از پنل خارج نشود.
EXIT_CONFIRM_TEXT = (
    "🚪 <b>خروج از حالتِ ادمین</b>\n\n"
    "مطمئنی می‌خواهی خارج شوی؟ پس از خروج، دیگر دسترسیِ ویژه‌ای نداری و برایِ بازگشت باید "
    "دوباره با کلمه‌ی «ادمین مود» و رمزت وارد شوی."
)


@router.message(TextIn(A.EXIT_WORDS))
async def exit_admin_word(message: Message, state: FSMContext):
    uid = message.from_user.id
    if not await adm.is_in_admin_mode(uid):
        return
    await state.clear()
    await message.answer(EXIT_CONFIRM_TEXT, reply_markup=admin_exit_confirm_kb(uid))


async def _do_exit(message: Message, state: FSMContext, uid: int) -> None:
    await state.clear()
    await adm.exit_admin_mode(uid)
    old = PANEL_MSG.pop(uid, None)
    if old:
        try:
            await message.bot.delete_message(message.chat.id, old)
        except Exception:
            pass
    async with async_session() as session:
        await adm.audit(session, uid, "exit_admin_mode")
    await message.answer(
        "🚪 از حالتِ ادمین خارج شدی. دیگر دسترسیِ ویژه‌ای نداری.",
        reply_markup=main_menu(),
    )


@router.callback_query(F.data.startswith("adm:exitok"))
async def exit_admin_confirmed_cb(callback: CallbackQuery, state: FSMContext):
    """🆕 مرحله ۲۷ — تأییدِ نهاییِ خروج از حالتِ ادمین."""
    if not await ensure_owner(callback):
        return
    uid = callback.from_user.id
    try:
        await callback.message.delete()
    except Exception:
        pass
    PANEL_MSG.pop(uid, None)
    await _do_exit(callback.message, state, uid)
    await callback.answer("خارج شدی.")


@router.callback_query(F.data.startswith("adm:exit"))
async def exit_admin_cb(callback: CallbackQuery, state: FSMContext):
    """🆕 مرحله ۲۷ — این دکمه دیگر فوری خارج نمی‌کند؛ اول تأیید می‌گیرد."""
    admin = await _cb_admin(callback)
    if admin is None:
        return
    await state.clear()
    await safe_edit(callback.message, EXIT_CONFIRM_TEXT, admin_exit_confirm_kb(callback.from_user.id))
    await callback.answer()


@router.callback_query(F.data.startswith("adm:cancel"))
async def cancel_cb(callback: CallbackQuery, state: FSMContext):
    admin = await _cb_admin(callback)
    if admin is None:
        return
    await state.clear()
    await _refresh_panel(callback, admin, note="✖ لغو شد.")
    await callback.answer()


# ---------------------------------------------------------------------------
# راهنماها (فقط در حالتِ ادمین)
# ---------------------------------------------------------------------------
@router.message(TextIn(A.HELP_MAIN_WORDS))
async def help_main(message: Message):
    uid = message.from_user.id
    if not await adm.is_in_admin_mode(uid):
        return
    async with async_session() as session:
        admin = await adm.get_admin(session, uid)
    if admin is None or admin.role != "main":
        return  # «راهنمای ادمین اصلی» فقط برایِ ادمینِ اصلی
    await message.answer(A.help_text(is_main=True, perms=A.PERMISSION_ORDER))


@router.message(TextIn(A.HELP_ADMIN_WORDS))
async def help_admin(message: Message):
    uid = message.from_user.id
    if not await adm.is_in_admin_mode(uid):
        return
    async with async_session() as session:
        admin = await adm.get_admin(session, uid)
    if admin is None:
        return
    is_main = admin.role == "main"
    await message.answer(A.help_text(is_main=is_main, perms=adm.perms_of(admin)))


@router.callback_query(F.data.startswith("adm:guide"))
async def guide_cb(callback: CallbackQuery):
    admin = await _cb_admin(callback)
    if admin is None:
        return
    is_main = admin.role == "main"
    await callback.message.answer(A.help_text(is_main=is_main, perms=adm.perms_of(admin)))
    await callback.answer()


# ---------------------------------------------------------------------------
# خانه‌یِ پنل
# ---------------------------------------------------------------------------
@router.callback_query(F.data.startswith("adm:home"))
async def home_cb(callback: CallbackQuery, state: FSMContext):
    admin = await _cb_admin(callback)
    if admin is None:
        return
    await state.clear()
    await _refresh_panel(callback, admin)
    await callback.answer()


# ---------------------------------------------------------------------------
# ورود به بخش‌ها
# ---------------------------------------------------------------------------
@router.callback_query(F.data.startswith("adm:sec:"))
async def section_cb(callback: CallbackQuery, state: FSMContext):
    admin = await _cb_admin(callback)
    if admin is None:
        return
    await state.clear()
    base, _ = split_owner(callback.data)
    key = base.split("adm:sec:", 1)[1]
    uid = callback.from_user.id
    p = A.PERMISSIONS.get(key)
    if p is None:
        await callback.answer("⛔ دسترسی نداری.", show_alert=True)
        return
    header = f"{p['emoji']} <b>{p['label']}</b>\n{p['desc']}"
    if not _require(admin, key):
        # 🆕 v1.7.8.15 — ادمینی که فقط به یک زیرمنو دسترسی دارد (مثلاً «جوینِ
        # اجباری» بدونِ «کانال») باید از راهِ والد به آن برسد؛ در این حالت
        # فقط دکمه‌ی همان زیرمنوها را می‌بیند، نه کنترل‌هایِ خودِ والد را.
        if not [c for c in A.children_of(key) if _require(admin, c)]:
            await callback.answer("⛔ دسترسی نداری.", show_alert=True)
            return
        await safe_edit(
            callback.message,
            header + "\n\n\U0001F511 \u0641\u0642\u0637 \u0632\u06cc\u0631\u0628\u062e\u0634\u200c\u0647\u0627\u06cc\u0650 \u0632\u06cc\u0631 \u0628\u0631\u0627\u06cc\u0650 \u062a\u0648 \u0628\u0627\u0632 \u0627\u0633\u062a.",
            _with_subs(back_kb(uid), uid, key, admin),
        )
        await callback.answer()
        return
    if key == "users":
        # 🐞 v1.7.8.14 — قبلاً هر سه گزینه هاردکد False بود، پس دکمه‌هایِ
        # اقتصاد / سطح / ثروتِ گروهی داخلِ «مدیریتِ کاربران» هرگز ظاهر
        # نمی‌شدند — حتی برای ادمینِ اصلی. حالا به دسترسیِ واقعی وصل شد.
        await safe_edit(callback.message, header, admin_users_kb(uid))
    elif key == "bulk_wealth":
        await safe_edit(callback.message, header, admin_economy_kb(uid))
    elif key == "economy":
        await safe_edit(callback.message, header + "\n\nثروت شامل پول نقد و سپرده بانک است.", _with_subs(admin_economy_kb(uid), uid, "economy", admin))
    elif key == "bulk_levels":
        await safe_edit(callback.message, header, admin_level_xp_kb(uid))
    elif key == "news":
        await safe_edit(callback.message, header, admin_news_broadcast_kb(uid, _require(admin, "news"), _require(admin, "broadcast")))
    elif key == "reports":
        await safe_edit(callback.message, header + "\n\nگزارش‌های چت‌مود و تنظیم کانال گزارش.", _with_subs(admin_reports_kb(uid), uid, "reports", admin))
    elif key == "assistants":
        async with async_session() as session:
            first_on=str(await adm.get_setting(session,"assistant_first_enabled") or "1") != "0"
            second_on=str(await adm.get_setting(session,"assistant_second_enabled") or "1") != "0"
        await safe_edit(callback.message, header, admin_assistants_kb(uid, first_on, second_on))
    elif key == "subscriptions":
        is_main = admin.role == "main"
        async with async_session() as session:
            notify_main_on = await adm.main_notify_on_purchase(session)
            has_sales_admin = bool(await adm.get_sales_admin_id(session))
        await safe_edit(callback.message, header, admin_sub_kb(uid, is_main, notify_main_on, has_sales_admin))
    elif key == "titles":
        await safe_edit(callback.message, header, admin_titles_kb(uid))
    elif key == "reports":
        await safe_edit(callback.message, header, _with_subs(admin_reports_kb(uid), uid, "reports", admin))
    elif key == "news":
        await _show_news(callback, uid, admin)
    elif key == "broadcast":
        await safe_edit(callback.message, header, admin_broadcast_kb(uid))
    elif key == "stats":
        await _show_stats(callback, uid, admin)
    elif key == "events":
        await _show_events(callback, uid)
    elif key == "tools":
        await safe_edit(
            callback.message,
            header + "\n\n⚠️ این ابزارها روی دیتایِ واقعیِ بازیکن‌ها اثر می‌گذارند؛ با دقت استفاده کن.",
            _with_subs(admin_tools_kb(uid), uid, "tools", admin),
        )
    elif key == "worldbank":
        async with async_session() as session:
            text = await _bank_panel_text(session)
        await safe_edit(
            callback.message,
            text,
            admin_worldbank_kb(uid, _require(admin, "economy")),
        )
    # 🆕 v1.7.8.14 — بخش‌هایی که تا حالا فقط از درونِ «ابزارهایِ ویژه»
    # قابلِ دسترسی بودند و حالا دکمهٔ مستقلِ خودشان را دارند.
    elif key == "force_join":
        await _show_force_join(callback, uid)
    elif key == "sections_control":
        await safe_edit(callback.message, header, admin_control_kb(uid))
    elif key == "game_settings":
        await safe_edit(callback.message, header, admin_game_settings_kb(uid))
    elif key == "ranking_ctrl":
        await _rankvis_panel(callback, admin)
    elif key == "referral":
        await _referral_panel(callback, admin)
    elif key == "activity":
        await safe_edit(callback.message, header, admin_activity_kb(uid))
    elif key == "backup":
        await _backup_panel(callback)
    elif key == "channel":
        await _show_channel(callback, uid, admin)
    elif key == "admins":
        await safe_edit(callback.message, header, admin_admins_kb(uid))
    await callback.answer()


# ---------------------------------------------------------------------------
# مدیریتِ کاربران
# ---------------------------------------------------------------------------
_USER_ACTIONS = {
    "find": ("🔍 یوزرآیدیِ کاربر را بفرست:", None),
    "ban": ("🚫 یوزرآیدیِ کاربری که می‌خواهی محدود (بن) کنی:", None),
    "unban": ("✅ یوزرآیدیِ کاربری که می‌خواهی رفعِ محدودیت کنی:", None),
    "wealth": ("🎯 اول یوزرآیدیِ کاربر را بفرست:", "economy"),
    "wealthadd": ("➕ اول یوزرآیدیِ کاربر را بفرست:", "economy"),
    "wealthsub": ("➖ اول یوزرآیدیِ کاربر را بفرست:", "economy"),
    "wealthreset": ("♻️ اول یوزرآیدیِ کاربر را بفرست:", "economy"),
    "level": ("🎯 اول یوزرآیدیِ کاربر را بفرست:", "economy"),
    "leveladd": ("➕ اول یوزرآیدیِ کاربر را بفرست:", "economy"),
    "levelsub": ("➖ اول یوزرآیدیِ کاربر را بفرست:", "economy"),
    "levelreset": ("♻️ یوزرآیدی کاربر برای ریست لول و XP را بفرست:", "bulk_levels"),
    "xp": ("✨ اول یوزرآیدیِ کاربر را بفرست:", "economy"),
}


@router.callback_query(
    F.data.startswith("adm:u:") & ~F.data.startswith("adm:u:titled")
)
async def user_action_cb(callback: CallbackQuery, state: FSMContext):
    # 🐞 مرحله ۷۱ — استثنا از بدنه به دکوراتور منتقل شد، وگرنه دکمه‌های
    # «کاربرانِ لقب‌دار» (adm:u:titled: و adm:u:titledcard:) هرگز اجرا نمی‌شدند.
    admin = await _cb_admin(callback)
    if admin is None:
        return
    base, owner = split_owner(callback.data)
    action = base.split("adm:u:", 1)[1]
    # 🆕 مرحله ۲۷ — هر اکشن دقیقاً دسترسیِ خودش را می‌خواهد:
    # جستجو/بن/رفعِبن ← users ، پول/لول/XP ← economy (قبلاً برایِ همه‌ی اکشن‌ها users لازم بود
    # و همین باعث می‌شد ادمینِ فقط‌اقتصادی نتواند پول/لول/XP را تغییر دهد).
    need = "economy" if action in ("wealth", "wealthadd", "wealthsub", "wealthreset", "level", "leveladd", "levelsub", "levelreset", "xp") else "users"
    if not _require(admin, need):
        await callback.answer(A.denied_text(need), show_alert=True)
        return
    prompt, _ = _USER_ACTIONS.get(action, ("یوزرآیدی را بفرست:", None))
    await state.set_state(AdminStates.users_wait_uid)
    await state.update_data(action=action)
    await safe_edit(callback.message, prompt, cancel_kb(owner))
    await callback.answer()


@router.message(StateFilter(AdminStates.users_wait_uid))
async def users_uid(message: Message, state: FSMContext):
    data0 = await state.get_data()
    need0 = "economy" if data0.get("action") in ("wealth", "wealthadd", "wealthsub", "wealthreset", "level", "leveladd", "levelsub", "levelreset", "xp") else "users"
    admin = await _guard_perm(message, state, need0)
    if admin is None:
        return
    if await handle_cancel_word(message, state):
        return
    target = _parse_int(message.text)
    if target is None:
        await message.answer("⚠ یوزرآیدی باید عدد باشد. دوباره بفرست:")
        return
    data = await state.get_data()
    action = data.get("action")
    async with async_session() as session:
        player = (await session.execute(
            select(Player).where(Player.tg_user_id == target)
        )).scalar_one_or_none()
        if player is None:
            await state.clear()
            await message.answer("⚠ کاربری با این یوزرآیدی در بازی پیدا نشد.")
            await _send_panel(message, message.from_user.id, admin)
            return
        if action == "find":
            await state.clear()
            await message.answer(_player_card(player))
            await _send_panel(message, message.from_user.id, admin)
            return
        if action in ("ban", "unban"):
            player.banned = (action == "ban")
            await adm.audit(session, message.from_user.id, action, target_id=target, commit=False)
            await session.commit()
            if action == "ban":
                adm.BANNED_IDS.add(target)
            else:
                adm.BANNED_IDS.discard(target)
            await state.clear()
            verb = "محدود (بن)" if action == "ban" else "رفعِ محدودیت"
            await message.answer(f"✅ کاربر <code>{target}</code> {verb} شد.")
            await _send_panel(message, message.from_user.id, admin)
            return
    # cash/level/xp → مرحله‌یِ مقدار
    await state.update_data(target=target)
    nxt = {
        "wealth": (AdminStates.users_wait_cash, "🎯 لولِ ثروت جدید را بفرست:"),
        "wealthadd": (AdminStates.users_wait_cash, "➕ مقدار افزایش ثروت را بفرست:"),
        "wealthsub": (AdminStates.users_wait_cash, "➖ مقدار کاهش ثروت را بفرست:"),
        "wealthreset": (AdminStates.users_wait_cash, "♻️ برای تایید ریست دارایی، عدد 0 را بفرست:"),
        "level": (AdminStates.users_wait_level, f"🎯 لولِ فعلی: <b>{player.level}</b>\nلول جدید را بفرست (۱ تا {leveling.MAX_LEVEL}):"),
        "leveladd": (AdminStates.users_wait_level, f"➕ لولِ فعلی: <b>{player.level}</b>\nمقدار افزایش را بفرست:"),
        "levelsub": (AdminStates.users_wait_level, f"➖ لولِ فعلی: <b>{player.level}</b>\nمقدار کاهش را بفرست:"),
        "levelreset": (AdminStates.users_wait_level, "♻️ برای تایید ریست لول و XP، عدد 1 را بفرست:"),
        "xp": (AdminStates.users_wait_xp, f"✨ XP فعلی: <b>{player.xp}</b>\nXP جدید را بفرست:"),
    }[action]
    await state.set_state(nxt[0])
    await message.answer(nxt[1])


@router.message(StateFilter(AdminStates.users_wait_cash))
async def users_wealth(message: Message, state: FSMContext):
    admin=await _guard_perm(message,state,"economy")
    if admin is None or await handle_cancel_word(message,state): return
    amount=_parse_int(message.text)
    if amount is None or amount < 0: await message.answer("⚠ عدد نامنفی بفرست:"); return
    data=await state.get_data(); target=data.get("target"); action=data.get("action","wealth")
    from app.models.worldbank import BankAccount
    async with async_session() as session:
        player=(await session.execute(select(Player).where(Player.tg_user_id==target))).scalar_one_or_none()
        if not player: await state.clear(); await message.answer("⚠ کاربر پیدا نشد."); return
        acc=await session.get(BankAccount,target); deposit=int(acc.deposit or 0) if acc else 0; old=int(player.cash or 0)+deposit
        new=0 if action=="wealthreset" else (amount if action=="wealth" else (old+amount if action=="wealthadd" else max(0,old-amount)))
        # Keep the result in cash and clear the deposit: total wealth is exact and never negative.
        player.cash=new
        if acc: acc.deposit=0
        op={"wealth":"set_wealth","wealthadd":"add_wealth","wealthsub":"sub_wealth","wealthreset":"reset_wealth"}[action]
        await adm.audit(session,message.from_user.id,op,target_id=target,detail=f"{old}->{new}; deposit_cleared={deposit}",commit=False); await session.commit()
    await state.clear(); label={"wealth":"تعیین","wealthadd":"افزایش","wealthsub":"کاهش","wealthreset":"ریست"}[action]
    await message.answer(f"✅ {label} ثروت کاربر <code>{target}</code>: <b>{old:,}</b> ← <b>{new:,}</b>")
    await _send_panel(message,message.from_user.id,admin)


@router.message(StateFilter(AdminStates.users_wait_level))
async def users_level(message: Message, state: FSMContext):
    admin = await _guard_perm(message, state, "economy")
    if admin is None or await handle_cancel_word(message, state): return
    amount = _parse_int(message.text)
    if amount is None or amount < 1:
        await message.answer("⚠ یک عدد مثبت بفرست:"); return
    data = await state.get_data(); target=data.get("target"); action=data.get("action", "level")
    async with async_session() as session:
        player=(await session.execute(select(Player).where(Player.tg_user_id == target))).scalar_one_or_none()
        if player is None:
            await state.clear(); await message.answer("⚠ کاربر پیدا نشد."); return
        old=int(player.level or 1)
        if action == "levelreset": new_level=1; player.xp=0
        elif action == "leveladd": new_level=min(leveling.MAX_LEVEL, old + amount)
        elif action == "levelsub": new_level=max(1, old - amount)
        else:
            if amount > leveling.MAX_LEVEL:
                await message.answer(f"⚠ لول باید بین ۱ تا {leveling.MAX_LEVEL} باشد:"); return
            new_level=amount; player.xp=0
        player.level=new_level
        op={"level":"set_level", "leveladd":"add_level", "levelsub":"sub_level", "levelreset":"reset_level_xp"}[action]
        await adm.audit(session,message.from_user.id,op,target_id=target,detail=f"{old}->{new_level}",commit=False)
        await session.commit()
    await state.clear()
    label={"level":"تعیین", "leveladd":"افزایش", "levelsub":"کاهش", "levelreset":"ریست"}[action]
    await message.answer(f"✅ {label} لول کاربر <code>{target}</code>: <b>{old}</b> ← <b>{new_level}</b>")
    await _send_panel(message,message.from_user.id,admin)


@router.message(StateFilter(AdminStates.users_wait_xp))
async def users_xp(message: Message, state: FSMContext):
    admin = await _guard_perm(message, state, "economy")
    if admin is None:
        return
    if await handle_cancel_word(message, state):
        return
    val = _parse_int(message.text)
    if val is None or val < 0:
        await message.answer("⚠ XP باید عددِ نامنفی باشد. دوباره:")
        return
    data = await state.get_data()
    target = data.get("target")
    async with async_session() as session:
        player = (await session.execute(
            select(Player).where(Player.tg_user_id == target)
        )).scalar_one_or_none()
        if player is None:
            await state.clear()
            await message.answer("⚠ کاربر پیدا نشد.")
            return
        old = player.xp
        player.xp = val
        await adm.audit(session, message.from_user.id, "set_xp", target_id=target,
                        detail=f"{old}->{val}", commit=False)
        await session.commit()
    await state.clear()
    await message.answer(f"✅ XP کاربر <code>{target}</code> به <b>{val}</b> تغییر کرد.")
    await _send_panel(message, message.from_user.id, admin)


def _player_card(p: Player) -> str:
    status = "🚫 محدود (بن)" if getattr(p, "banned", False) else "✅ فعال"
    return "\n".join([
        "👤 <b>پروفایلِ کاربر</b>",
        f"🆔 آیدی: <code>{p.tg_user_id}</code>",
        f"📛 نام: {p.name}",
        f"🔗 یوزرنیم: @{p.username}" if p.username else "🔗 یوزرنیم: —",
        f"🆙 لول: {p.level} — ✨ XP: {p.xp}",
        f"💰 پول: {p.cash:,}",
        f"💎 پریمیوم: {'بله' if p.is_premium else 'خیر'}",
        f"⛔ وضعیت: {status}",
    ])


# ---------------------------------------------------------------------------
# اشتراک
# ---------------------------------------------------------------------------
@router.callback_query(F.data.startswith("adm:sub:on"))
async def sub_on_cb(callback: CallbackQuery, state: FSMContext):
    admin = await _cb_admin(callback)
    if admin is None:
        return
    if not _require(admin, "subscriptions"):
        await callback.answer("⛔ دسترسی نداری.", show_alert=True)
        return
    _, owner = split_owner(callback.data)
    await safe_edit(callback.message, "💎 سطحِ اشتراک را انتخاب کن:", sub_tier_kb(owner))
    await callback.answer()


@router.callback_query(F.data.startswith("adm:sub:tier:"))
async def sub_tier_cb(callback: CallbackQuery, state: FSMContext):
    admin = await _cb_admin(callback)
    if admin is None:
        return
    if not _require(admin, "subscriptions"):
        await callback.answer("⛔ دسترسی نداری.", show_alert=True)
        return
    base, owner = split_owner(callback.data)
    tier = base.split("adm:sub:tier:", 1)[1]
    await state.set_state(AdminStates.sub_wait_uid)
    await state.update_data(sub_action="on", tier=tier)
    await safe_edit(
        callback.message,
        f"💎 سطح: <b>{S.get_tier(tier)['name']}</b>\nیوزرآیدیِ کاربر را بفرست (خودِ تو یا یک ادمین):",
        cancel_kb(owner),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("adm:sub:off"))
async def sub_off_cb(callback: CallbackQuery, state: FSMContext):
    admin = await _cb_admin(callback)
    if admin is None:
        return
    if not _require(admin, "subscriptions"):
        await callback.answer("⛔ دسترسی نداری.", show_alert=True)
        return
    _, owner = split_owner(callback.data)
    await state.set_state(AdminStates.sub_wait_uid)
    await state.update_data(sub_action="off")
    await safe_edit(callback.message, "⚪ یوزرآیدیِ کاربری که می‌خواهی اشتراکش غیرفعال شود را بفرست:", cancel_kb(owner))
    await callback.answer()


@router.message(StateFilter(AdminStates.sub_wait_uid))
async def sub_uid(message: Message, state: FSMContext):
    admin = await _guard_admin(message, state)
    if admin is None:
        return
    if await handle_cancel_word(message, state):
        return
    target = _parse_int(message.text)
    if target is None:
        await message.answer("⚠ یوزرآیدی باید عدد باشد. دوباره:")
        return
    data = await state.get_data()
    sub_action = data.get("sub_action")
    async with async_session() as session:
        if sub_action == "on":
            tier = data.get("tier", "bronze")
            ok, msg = await subscription_service.activate_tier(session, target, tier, commit=False)
            await adm.audit(session, message.from_user.id, "sub_activate", target_id=target, detail=tier, commit=False)
            await session.commit()
            text = (f"✅ {msg}\nکاربر: <code>{target}</code>") if ok else f"⚠ {msg}"
        else:
            await subscription_service.deactivate(session, target, commit=False)
            await adm.audit(session, message.from_user.id, "sub_deactivate", target_id=target, commit=False)
            await session.commit()
            text = f"⚪ اشتراکِ کاربر <code>{target}</code> غیرفعال شد."
    await state.clear()
    await message.answer(text)
    await _send_panel(message, message.from_user.id, admin)


# ---------------------------------------------------------------------------
# 🆕 مرحله ۲۱.۱ — درخواست‌ها/تاریخچه/پیگیری/قیمت‌گذاری/ادمینِ فروش
# ---------------------------------------------------------------------------

@router.callback_query(F.data.startswith("adm:sub:paymethod"))
async def sub_paymethod_cb(callback: CallbackQuery, state: FSMContext):
    admin = await _cb_admin(callback)
    if admin is None: return
    if not _require(admin, "subscriptions"):
        await callback.answer("⛔ دسترسی نداری.", show_alert=True); return
    _, owner = split_owner(callback.data)
    await state.set_state(AdminStates.sub_wait_priceval)  # reuse free text state carefully
    await state.update_data(sub_paymethod=1)
    async with async_session() as session:
        cur = await subscription_service.get_payment_method(session)
    await safe_edit(
        callback.message,
        "🏦 <b>روش پرداخت اشتراک</b>\n\n"
        f"فعلی:\n<code>{cur or 'تنظیم نشده'}</code>\n\n"
        "متن روش پرداخت را بفرست (مثلاً شماره کارت، شبا، توضیحات).",
        cancel_kb(owner),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("adm:sub:preok:"))
async def sub_preok_cb(callback: CallbackQuery):
    admin = await _cb_admin(callback)
    if admin is None: return
    if not _require(admin, "subscriptions"):
        await callback.answer("⛔ دسترسی نداری.", show_alert=True); return
    base, owner = split_owner(callback.data)
    code = base.split("adm:sub:preok:", 1)[1]
    async with async_session() as session:
        ok, msg, rec = await subscription_service.mark_approved_for_payment(session, code, callback.from_user.id, commit=False)
        if ok and rec is not None:
            await adm.audit(session, callback.from_user.id, "sub_preapprove", target_id=rec.tg_user_id, detail=code, commit=False)
        await session.commit()
    if ok and rec is not None:
        try:
            pay = rec.payment_info or ""
            await callback.bot.send_message(
                int(rec.tg_user_id),
                "✅ درخواست اشتراکت تأیید اولیه شد.\n"
                "از بخش «اشتراک» → «درخواست‌های تأییدشده و پرداخت» مبلغ را بپرداز و رسید بفرست.\n\n"
                f"📌 روش پرداخت:\n<code>{pay}</code>",
            )
        except Exception:
            pass
    await safe_answer(callback, msg, show_alert=True)
    # refresh list
    await sub_reqs_cb(callback.model_copy(update={"data": with_owner("adm:sub:reqs", owner)}))


@router.callback_query(F.data.startswith("adm:sub:awaitpay"))
async def sub_awaitpay_cb(callback: CallbackQuery):
    admin = await _cb_admin(callback)
    if admin is None: return
    if not _require(admin, "subscriptions"):
        await callback.answer("⛔ دسترسی نداری.", show_alert=True); return
    _, owner = split_owner(callback.data)
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    async with async_session() as session:
        rows = await subscription_service.get_awaiting_payment_all(session)
    b = InlineKeyboardBuilder()
    lines = ["💳 <b>منتظر پرداخت / رسید</b>", ""]
    if not rows:
        # 🆕 v1.7.6.3 — پیامِ روشنِ «وجود ندارد» به‌جای «موردی نیست»
        lines.append("🚫 <b>وجود ندارد</b>")
        lines.append(
            "هیچ کاربری در انتظارِ پرداخت یا رسید نیست.\n"
            "وقتی یک درخواست را از «📥 درخواست‌هایِ خرید» با «✅ تأیید برای پرداخت» "
            "آزاد کنی، همانجا اینجا ظاهر می‌شود."
        )
    for r in rows:
        tier = S.get_tier(r.tier)
        has_r = "🧾 رسید دارد" if r.receipt_file_id else "⏳ بدون رسید"
        lines.append(
            f"{tier['emoji']} {tier['name']} — {r.amount:,}$\n"
            f"👤 <code>{r.tg_user_id}</code> • 🧩 <code>{r.tracking_code}</code>\n{has_r}"
        )
        if r.receipt_file_id:
            b.button(text=f"👁 رسید {r.tracking_code}", callback_data=with_owner(f"adm:sub:seerec:{r.tracking_code}", owner))
            b.button(text=f"⚡ فعال‌سازی {r.tracking_code}", callback_data=with_owner(f"adm:sub:finalok:{r.tracking_code}", owner))
        b.button(text=f"🚫 رد {r.tracking_code}", callback_data=with_owner(f"adm:sub:reject:{r.tracking_code}", owner))
    if rows:
        lines.append("🧾 برای دیدن و تأییدِ رسیدها از «🧾 رسیدهای ارسال‌شده» هم می‌توانی استفاده کنی.")
    b.button(text="🧾 رسیدهای ارسال‌شده", callback_data=with_owner("adm:sub:receipts", owner))
    b.button(text="🔄 بروزرسانی", callback_data=with_owner("adm:sub:awaitpay", owner))
    b.button(text="⬅️ بازگشت", callback_data=with_owner("adm:sec:subscriptions", owner)); b.adjust(1)
    await safe_edit(callback.message, "\n\n".join(lines), b.as_markup()); await safe_answer(callback)


# --------------------- 🆕 v1.7.6.3 — رسیدهای ارسال‌شده ---------------------
@router.callback_query(F.data.startswith("adm:sub:receipts"))
async def sub_receipts_cb(callback: CallbackQuery):
    """🆕 بخشِ تازه: کسانی که رسید فرستاده‌اند.

    قبلاً هیچ جایی نبود که ادمین فهرستِ رسیدها را ببیند: فهرستِ
    «منتظر پرداخت/رسید» فقط ردیف‌های awaiting_payment را می‌آورد، ولی
    attach_receipt وضعیت را عوض نمی‌کند — پس رسیدی که در حالتِ pending
    می‌رسید عملاً گم می‌شد. اینجا هر رسیدِ بی‌تکلیف دیده می‌شود و
    همانجا می‌شود اشتراک را فعال کرد.
    """
    admin = await _cb_admin(callback)
    if admin is None:
        return
    if not _require(admin, "subscriptions"):
        await safe_answer(callback, "⛔ دسترسی نداری.", show_alert=True)
        return
    _, owner = split_owner(callback.data)
    async with async_session() as session:
        rows = await subscription_service.get_receipts_pending(session)
    lines = ["🧾 <b>رسیدهای ارسال‌شده</b>", ""]
    if not rows:
        lines.append("🚫 <b>وجود ندارد</b>")
        lines.append("هیچ کاربری رسیدِ در انتظارِ بررسی ندارد.")
    else:
        lines.append(f"👥 <b>{len(rows)}</b> رسیدِ در انتظارِ بررسی:")
        for r in rows:
            tier = S.get_tier(r.tier)
            date = r.created_at.strftime("%Y/%m/%d %H:%M") if r.created_at else "—"
            kind = "🖼 عکس" if r.receipt_type == "photo" else "📄 فایل"
            status_fa = _SUB_STATUS_FA.get(str(r.status), str(r.status))
            lines.append(
                f"{tier['emoji']} {tier['name']} — {int(r.amount or 0):,}$\n"
                f"👤 <code>{r.tg_user_id}</code> • 🧩 <code>{r.tracking_code}</code>\n"
                f"📅 {date} • {kind} • {status_fa}"
            )
        lines.append("اول «👁 مشاهده» را بزن تا رسید برایت فرستاده شود، بعد تأیید یا رد کن.")
    await safe_edit(callback.message, "\n\n".join(lines), sub_receipts_kb(owner, rows))
    await safe_answer(callback)


@router.callback_query(F.data.startswith("adm:sub:recok:"))
async def sub_recok_cb(callback: CallbackQuery):
    """🆕 v1.7.6.3 — تأییدِ رسید و فعال‌سازیِ اشتراک از همان فهرست."""
    admin = await _cb_admin(callback)
    if admin is None:
        return
    if not _require(admin, "subscriptions"):
        await safe_answer(callback, "⛔ دسترسی نداری.", show_alert=True)
        return
    base, owner = split_owner(callback.data)
    code = base.split("adm:sub:recok:", 1)[1]
    async with async_session() as session:
        ok, msg, rec = await subscription_service.finalize_after_receipt(
            session, code, callback.from_user.id, commit=False
        )
        if ok and rec is not None:
            await adm.audit(
                session, callback.from_user.id, "sub_activate_receipt",
                target_id=rec.tg_user_id, detail=code, commit=False,
            )
        await session.commit()
        target_uid = int(rec.tg_user_id) if rec is not None else None
    if ok and target_uid:
        try:
            await callback.bot.send_message(
                target_uid,
                "🎉 رسیدت تأیید شد و اشتراکت فعال شد!\n"
                f"🧩 کدِ سفارش: <code>{code}</code>\n\n{msg}",
            )
        except Exception:
            pass
    await safe_answer(callback, msg, show_alert=True)
    await sub_receipts_cb(callback.model_copy(update={"data": with_owner("adm:sub:receipts", owner)}))


@router.callback_query(F.data.startswith("adm:sub:recno:"))
async def sub_recno_cb(callback: CallbackQuery):
    """🆕 v1.7.6.3 — ردِ رسید؛ بعدش به همین فهرست برمی‌گ��دیم."""
    admin = await _cb_admin(callback)
    if admin is None:
        return
    if not _require(admin, "subscriptions"):
        await safe_answer(callback, "⛔ دسترسی نداری.", show_alert=True)
        return
    base, owner = split_owner(callback.data)
    code = base.split("adm:sub:recno:", 1)[1]
    async with async_session() as session:
        ok, msg, rec = await subscription_service.reject_request(
            session, code, callback.from_user.id,
            note="رسید تأیید نشد", commit=False,
        )
        if ok and rec is not None:
            await adm.audit(
                session, callback.from_user.id, "sub_reject_request",
                target_id=rec.tg_user_id, detail=code, commit=False,
            )
        await session.commit()
        target_uid = int(rec.tg_user_id) if rec is not None else None
    if ok and target_uid:
        try:
            await callback.bot.send_message(
                target_uid,
                f"🚫 رسیدِ سفارشِ <code>{code}</code> تأیید نشد.\n"
                "اگر فکر می‌کنی اشتباهی شده، رسیدِ درست را دوباره بفرست.",
            )
        except Exception:
            pass
    await safe_answer(callback, msg, show_alert=True)
    await sub_receipts_cb(callback.model_copy(update={"data": with_owner("adm:sub:receipts", owner)}))


@router.callback_query(F.data.startswith("adm:sub:seerec:"))
async def sub_seerec_cb(callback: CallbackQuery):
    admin = await _cb_admin(callback)
    if admin is None: return
    if not _require(admin, "subscriptions"):
        await callback.answer("⛔", show_alert=True); return
    base, _ = split_owner(callback.data)
    code = base.split("adm:sub:seerec:", 1)[1]
    async with async_session() as session:
        rec = await subscription_service.get_purchase_by_code(session, code)
    if rec is None or not rec.receipt_file_id:
        await callback.answer("رسید نیست", show_alert=True); return
    try:
        if rec.receipt_type == "photo":
            await callback.message.answer_photo(rec.receipt_file_id, caption=f"🧾 رسید {code}")
        else:
            await callback.message.answer_document(rec.receipt_file_id, caption=f"🧾 رسید {code}")
    except Exception:
        await callback.answer("خطا در ارسال رسید", show_alert=True); return
    await callback.answer()


@router.callback_query(F.data.startswith("adm:sub:finalok:"))
async def sub_finalok_cb(callback: CallbackQuery):
    admin = await _cb_admin(callback)
    if admin is None: return
    if not _require(admin, "subscriptions"):
        await callback.answer("⛔", show_alert=True); return
    base, owner = split_owner(callback.data)
    code = base.split("adm:sub:finalok:", 1)[1]
    async with async_session() as session:
        ok, msg, rec = await subscription_service.finalize_after_receipt(session, code, callback.from_user.id, commit=False)
        if ok and rec is not None:
            await adm.audit(session, callback.from_user.id, "sub_activate_receipt", target_id=rec.tg_user_id, detail=code, commit=False)
        await session.commit()
    if ok and rec is not None:
        try:
            await callback.bot.send_message(int(rec.tg_user_id), f"🎉 {msg}")
        except Exception:
            pass
    await safe_answer(callback, msg, show_alert=True)
    await sub_awaitpay_cb(callback.model_copy(update={"data": with_owner("adm:sub:awaitpay", owner)}))


@router.callback_query(F.data.startswith("adm:sub:reqs"))
async def sub_reqs_cb(callback: CallbackQuery):
    admin = await _cb_admin(callback)
    if admin is None:
        return
    if not _require(admin, "subscriptions"):
        await callback.answer("⛔ دسترسی نداری.", show_alert=True)
        return
    _, owner = split_owner(callback.data)
    async with async_session() as session:
        reqs = await subscription_service.get_pending_requests(session)
    if not reqs:
        # 🆕 v1.7.6.3 — پیامِ روشنِ «وجود ندارد»
        text = (
            "📥 <b>درخواست‌های خرید</b>\n\n"
            "🚫 <b>وجود ندارد</b>\n"
            "هیچ درخواستِ خریدی در انتظارِ بررسی نیست."
        )
    else:
        lines = ["📥 <b>درخواست‌های درِ انتظار</b>", ""]
        for r in reqs:
            tier = S.get_tier(r.tier)
            date = r.created_at.strftime("%Y/%m/%d %H:%M") if r.created_at else "—"
            has_receipt = "🧾 رسید دارد" if r.receipt_file_id else "⚠ بدونِ رسید"
            lines.append(
                f"{tier['emoji']} {tier['name']} — {r.amount:,}$\n"
                f"👤 <code>{r.tg_user_id}</code> • 🧩 <code>{r.tracking_code}</code>\n"
                f"📅 {date} • {has_receipt}"
            )
        text = "\n\n".join(lines)
    await safe_edit(callback.message, text, sub_requests_kb(owner, reqs))
    await safe_answer(callback)


@router.callback_query(F.data.startswith("adm:sub:allhist"))
async def sub_allhist_cb(callback: CallbackQuery):
    admin = await _cb_admin(callback)
    if admin is None:
        return
    if not _require(admin, "subscriptions"):
        await callback.answer("⛔ دسترسی نداری.", show_alert=True)
        return
    _, owner = split_owner(callback.data)
    async with async_session() as session:
        rows = await subscription_service.get_recent_purchases(session)
    if not rows:
        text = "📜 <b>تاریخچه‌ی کاملِ خریدها</b>\n\nهنوز خریدی ثبت نشده."
    else:
        lines = ["📜 <b>تاریخچه‌ی کاملِ خریدها</b>", ""]
        for r in rows:
            tier = S.get_tier(r.tier)
            status = _SUB_STATUS_FA.get(r.status, r.status)
            date = r.created_at.strftime("%Y/%m/%d") if r.created_at else "—"
            lines.append(
                f"{tier['emoji']} {tier['name']} — {status}\n"
                f"👤 <code>{r.tg_user_id}</code> • 🧩 <code>{r.tracking_code}</code> • 📅 {date}"
            )
        text = "\n\n".join(lines)
    await safe_edit(callback.message, text, back_kb(owner))
    await callback.answer()


@router.callback_query(F.data.startswith("adm:sub:track"))
async def sub_track_cb(callback: CallbackQuery, state: FSMContext):
    admin = await _cb_admin(callback)
    if admin is None:
        return
    if not _require(admin, "subscriptions"):
        await callback.answer("⛔ دسترسی نداری.", show_alert=True)
        return
    _, owner = split_owner(callback.data)
    await state.set_state(AdminStates.sub_wait_trackcode)
    await safe_edit(callback.message, "🔎 کدِ پیگیری را بفرست:", cancel_kb(owner))
    await callback.answer()


@router.message(StateFilter(AdminStates.sub_wait_trackcode))
async def sub_trackcode(message: Message, state: FSMContext):
    admin = await _guard_admin(message, state)
    if admin is None:
        return
    if await handle_cancel_word(message, state):
        return
    code = _norm(message.text)
    await state.clear()
    async with async_session() as session:
        rec = await subscription_service.get_purchase_by_code(session, code)
    if rec is None:
        await message.answer("⚠ کدِ پیگیری پیدا نشد.")
        await _send_panel(message, message.from_user.id, admin)
        return
    tier = S.get_tier(rec.tier)
    status = _SUB_STATUS_FA.get(rec.status, rec.status)
    date = rec.created_at.strftime("%Y/%m/%d %H:%M") if rec.created_at else "—"
    lines = [
        "🧾 <b>مستنداتِ خرید</b>",
        f"{tier['emoji']} سطح: <b>{tier['name']}</b> — {rec.amount:,}$",
        f"👤 کاربر: <code>{rec.tg_user_id}</code>",
        f"🧩 کد: <code>{rec.tracking_code}</code>",
        f"📊 وضعیت: {status}",
        f"📅 تاریخ: {date}",
    ]
    if rec.handled_by:
        lines.append(f"🧑‍💼 رسیدگی: <code>{rec.handled_by}</code>")
    await message.answer("\n".join(lines))
    if rec.receipt_file_id:
        try:
            if rec.receipt_type == "photo":
                await message.answer_photo(rec.receipt_file_id, caption="🧾 رسیدِ پرداخت")
            else:
                await message.answer_document(rec.receipt_file_id, caption="🧾 رسیدِ پرداخت")
        except Exception:
            await message.answer("⚠ ارسالِ رسید با خطا مواجه شد.")
    else:
        await message.answer("ℹ️ هنوز رسیدی برای این درخواست ثبت نشده.")
    await _send_panel(message, message.from_user.id, admin)


@router.callback_query(
    F.data.startswith("adm:sub:price") & ~F.data.startswith("adm:sub:pricetier:")
)
async def sub_price_cb(callback: CallbackQuery):
    # 🐞 مرحله ۷۱ — ریشه‌ی باگِ «قیمت‌گذاریِ اشتراک کار نمی‌کند»:
    #   فیلترِ startswith("adm:sub:price") هر دو دکمه را می‌گرفت و با return زودهنگام،
    #   aiogram آپدیت را «رسیدگی‌شده» می‌دانست و انتشار را متوقف می‌کرد؛ پس هندلرِ
    #   adm:sub:pricetier: هرگز اجرا نمی‌شد. حالا استثنا در خودِ دکوراتور اعمال می‌شود.
    admin = await _cb_admin(callback)
    if admin is None or admin.role != "main":
        await callback.answer("⛔ فقط ادمینِ اص��ی.", show_alert=True)
        return
    _, owner = split_owner(callback.data)
    async with async_session() as session:
        effective = await subscription_service.effective_tiers(session)
    await safe_edit(callback.message, "💰 سطحی را برای قیمت‌گذاری انتخاب کن:", sub_price_tier_kb(owner, effective))
    await callback.answer()


@router.callback_query(F.data.startswith("adm:sub:pricetier:"))
async def sub_pricetier_cb(callback: CallbackQuery, state: FSMContext):
    admin = await _cb_admin(callback)
    if admin is None or admin.role != "main":
        await callback.answer("⛔ فقط ادمینِ اصلی.", show_alert=True)
        return
    base, owner = split_owner(callback.data)
    tier = base.split("adm:sub:pricetier:", 1)[1]
    await state.set_state(AdminStates.sub_wait_priceval)
    await state.update_data(price_tier=tier)
    await safe_edit(
        callback.message,
        f"💰 سطح: <b>{S.get_tier(tier)['name']}</b>\nقیمتِ جدید را به‌صورتِ عدد بفرست:",
        cancel_kb(owner),
    )
    await callback.answer()


@router.message(StateFilter(AdminStates.sub_wait_priceval))
async def sub_priceval(message: Message, state: FSMContext):
    admin = await _guard_admin(message, state)
    if admin is None:
        return
    if await handle_cancel_word(message, state):
        return
    data = await state.get_data()
    if data.get("sub_paymethod"):
        txt = (message.text or "").strip()
        if not txt:
            await message.answer("متن روش پرداخت را بفرست."); return
        async with async_session() as session:
            await subscription_service.set_payment_method(session, txt, commit=False)
            await adm.audit(session, message.from_user.id, "sub_payment_method", detail=txt[:80], commit=False)
            await session.commit()
        await state.clear()
        await message.answer("✅ روش پرداخت ذخیره شد.")
        await _send_panel(message, message.from_user.id, admin)
        return
    val = _parse_int(message.text)
    if val is None or val < 0:
        await message.answer("⚠ عددِ نامنفی بفرست. دوباره:")
        return
    tier = data.get("price_tier")
    async with async_session() as session:
        await subscription_service.set_price_override(session, tier, val, commit=False)
        await adm.audit(session, message.from_user.id, "sub_price_override", detail=f"{tier}={val}", commit=False)
        await session.commit()
    await state.clear()
    await message.answer(f"✅ قیمتِ سطحِ <b>{S.get_tier(tier)['name']}</b> به <b>{val:,}$</b> تنظیم شد.")
    await _send_panel(message, message.from_user.id, admin)


@router.callback_query(F.data.startswith("adm:sub:salesadmin"))
async def sub_salesadmin_cb(callback: CallbackQuery, state: FSMContext):
    admin = await _cb_admin(callback)
    if admin is None or admin.role != "main":
        await callback.answer("⛔ فقط ادمینِ اصلی.", show_alert=True)
        return
    _, owner = split_owner(callback.data)
    await state.set_state(AdminStates.sub_wait_salesadmin_uid)
    await safe_edit(
        callback.message,
        "👤 یوزرآیدیِ ادمینِ فروش را بفرست (برای حذف، عدد 0 را بفرست):",
        cancel_kb(owner),
    )
    await callback.answer()


@router.message(StateFilter(AdminStates.sub_wait_salesadmin_uid))
async def sub_salesadmin_uid(message: Message, state: FSMContext):
    admin = await _guard_admin(message, state)
    if admin is None:
        return
    if await handle_cancel_word(message, state):
        return
    val = _parse_int(message.text)
    if val is None:
        await message.answer("⚠ عدد بفرست. دوباره:")
        return
    async with async_session() as session:
        if val == 0:
            await adm.set_sales_admin_id(session, None, commit=False)
            text = "✅ ادمینِ فروش حذف شد."
        else:
            await adm.set_sales_admin_id(session, val, commit=False)
            text = f"✅ ادمینِ فروش روی <code>{val}</code> تنظیم شد."
        await adm.audit(session, message.from_user.id, "set_sales_admin", target_id=(val or None), commit=False)
        await session.commit()
    await state.clear()
    await message.answer(text)
    await _send_panel(message, message.from_user.id, admin)


@router.callback_query(F.data.startswith("adm:sub:notifytoggle"))
async def sub_notifytoggle_cb(callback: CallbackQuery):
    admin = await _cb_admin(callback)
    if admin is None or admin.role != "main":
        await callback.answer("⛔ فقط ادمینِ اصلی.", show_alert=True)
        return
    _, owner = split_owner(callback.data)
    async with async_session() as session:
        cur = await adm.main_notify_on_purchase(session)
        await adm.set_main_notify_on_purchase(session, not cur, commit=False)
        await adm.audit(session, callback.from_user.id, "sub_notify_toggle", detail=str(not cur), commit=False)
        await session.commit()
        notify_main_on = not cur
        has_sales_admin = bool(await adm.get_sales_admin_id(session))
    p = A.PERMISSIONS["subscriptions"]
    header = f"{p['emoji']} <b>{p['label']}</b>\n{p['desc']}"
    await safe_edit(callback.message, header, admin_sub_kb(owner, True, notify_main_on, has_sales_admin))
    await callback.answer("وضعیت تنظیم شد ✅")


@router.callback_query(F.data.startswith("adm:sub:approve:"))
async def sub_approve_cb(callback: CallbackQuery):
    admin = await _cb_admin(callback)
    if admin is None:
        return
    if not _require(admin, "subscriptions"):
        await callback.answer("⛔ دسترسی نداری.", show_alert=True)
        return
    base, owner = split_owner(callback.data)
    code = base.split("adm:sub:approve:", 1)[1]
    async with async_session() as session:
        ok, msg, rec = await subscription_service.approve_request(session, code, callback.from_user.id, commit=False)
        await adm.audit(session, callback.from_user.id, "sub_approve_request", target_id=(rec.tg_user_id if rec else None), detail=code, commit=False)
        await session.commit()
        target_uid = rec.tg_user_id if rec else None
    if ok and target_uid:
        try:
            await callback.bot.send_message(target_uid, f"✅ درخواستِ اشتراکِ تو تأیید و فعال شد! 🧩 <code>{code}</code>")
        except Exception:
            pass
    await callback.answer(msg, show_alert=True)
    reqs_reqs = None
    async with async_session() as session:
        reqs_reqs = await subscription_service.get_pending_requests(session)
    await safe_edit(callback.message, "📥 <b>درخواست‌های درِ انتظار</b>", sub_requests_kb(owner, reqs_reqs))


@router.callback_query(F.data.startswith("adm:sub:reject:"))
async def sub_reject_cb(callback: CallbackQuery):
    admin = await _cb_admin(callback)
    if admin is None:
        return
    if not _require(admin, "subscriptions"):
        await callback.answer("⛔ دسترسی نداری.", show_alert=True)
        return
    base, owner = split_owner(callback.data)
    code = base.split("adm:sub:reject:", 1)[1]
    async with async_session() as session:
        # 🆕 v1.7.6.3 — وضعیتِ پیش از رد را نگه می‌داریم تا بدانیم به کدام
        #   فهرست برگردیم. قبلاً همیشه فهرستِ «درخواست‌های در انتظار»
        #   را نشان می‌داد؛ پس اگر ادمین از «منتظر پرداخت/رسید» رد می‌کرد،
        #   به فهرستِ اشتباهی پرت می‌شد و خیال می‌کرد دکمه کار نکرده.
        before_rec = await subscription_service.get_purchase_by_code(session, code)
        prev_status = str(before_rec.status) if before_rec is not None else "pending"
        ok, msg, rec = await subscription_service.reject_request(session, code, callback.from_user.id, commit=False)
        await adm.audit(session, callback.from_user.id, "sub_reject_request", target_id=(rec.tg_user_id if rec else None), detail=code, commit=False)
        await session.commit()
        target_uid = rec.tg_user_id if rec else None
    if ok and target_uid:
        try:
            await callback.bot.send_message(target_uid, f"🚫 درخواستِ اشتراکِ تو رد شد. 🧩 <code>{code}</code>")
        except Exception:
            pass
    await safe_answer(callback, msg, show_alert=True)
    if prev_status == "awaiting_payment":
        await sub_awaitpay_cb(callback.model_copy(update={"data": with_owner("adm:sub:awaitpay", owner)}))
        return
    async with async_session() as session:
        reqs_reqs = await subscription_service.get_pending_requests(session)
    await safe_edit(callback.message, "📥 <b>درخواست‌های در انتظار</b>", sub_requests_kb(owner, reqs_reqs))


_SUB_STATUS_FA = {
    # 🆕 v1.7.6.3 — این کلید جا افتاده بود و وضعیتِ خامِ انگلیسی نشان داده می‌شد
    "awaiting_payment": "💳 منتظرِ پرداخت/رسید",
    "pending": "⏳ درِ انتظار",
    "active": "✅ فعال‌شده",
    "failed": "❌ ناموفق",
    "canceled": "🚫 لفو‌شده",
    "expired": "⌛ منقضی",
}


# ---------------------------------------------------------------------------
# القاب
# ---------------------------------------------------------------------------

@router.callback_query(F.data.startswith("adm:t:inspect"))
async def title_inspect_cb(callback: CallbackQuery, state: FSMContext):
    admin = await _cb_admin(callback)
    if admin is None:
        return
    if not _require(admin, "titles"):
        await callback.answer("⛔ دسترسی نداری.", show_alert=True)
        return
    _, owner = split_owner(callback.data)
    await state.set_state(AdminStates.title_wait_inspect_uid)
    await safe_edit(callback.message, "🔎 یوزرآیدیِ کاربری که می‌خواهی القابش را بررسی کنی بفرست:", cancel_kb(owner))
    await callback.answer()


@router.message(StateFilter(AdminStates.title_wait_inspect_uid))
async def title_inspect_uid(message: Message, state: FSMContext):
    admin = await _guard_admin(message, state)
    if admin is None:
        return
    if await handle_cancel_word(message, state):
        return
    target = _parse_int(message.text)
    if target is None:
        await message.answer("⚠ یوزرآیدی باید عدد باشد. دوباره:")
        return
    async with async_session() as session:
        player = await session.scalar(select(Player).where(Player.tg_user_id == target))
        profile = await session.get(TitleProfile, target)
        rows = (await session.execute(
            select(PlayerTitle).where(PlayerTitle.tg_user_id == target).order_by(PlayerTitle.granted_at.desc())
        )).scalars().all()
    if player is None and not rows and profile is None:
        await message.answer("⚠ برای این آیدی بازیکن/لقبی پیدا نشد.")
        return
    name = (player.name if player else None) or "—"
    active = "—"
    if profile:
        if profile.active_kind == "custom" and profile.custom_title:
            active = f"دلخواه: {profile.custom_title}"
        elif profile.active_title_key:
            tt = TDATA.get_title(profile.active_title_key)
            active = (tt or {}).get("name") or profile.active_title_key
    lines = [
        f"🔎 <b>بررسیِ القاب کاربر</b>",
        f"👤 نام: <b>{name}</b>",
        f"🆔 آیدی: <code>{target}</code>",
        f"🎯 لقبِ فعال: <b>{active}</b>",
        f"📦 تعدادِ القاب: <b>{len(rows)}</b>",
        "",
    ]
    if profile and profile.custom_title:
        lines.append(f"🏷️ لقبِ دلخواه: <b>{profile.custom_title}</b>")
    if rows:
        lines.append("🎖️ <b>آخرین القاب:</b>")
        for r in rows[:40]:
            tt = TDATA.get_title(r.title_key)
            title_name = (tt or {}).get("name") or r.title_key
            lines.append(f"• {title_name} <code>{r.title_key}</code>")
    else:
        lines.append("هنوز لقبِ کسب‌شده‌ای ثبت نشده است.")
    await state.clear()
    await message.answer("\n".join(lines))
    await _send_panel(message, message.from_user.id, admin)

@router.callback_query(F.data.startswith("adm:t:custom"))
async def title_custom_cb(callback: CallbackQuery, state: FSMContext):
    admin = await _cb_admin(callback)
    if admin is None:
        return
    if not _require(admin, "titles"):
        await callback.answer("⛔ دسترسی نداری.", show_alert=True)
        return
    base, owner = split_owner(callback.data)
    parts = base.split(":")
    await state.set_state(AdminStates.title_wait_uid)
    await state.update_data(title_action="custom")
    if len(parts) >= 4 and parts[3].isdigit():
        await state.update_data(target=int(parts[3]))
        await state.set_state(AdminStates.title_wait_custom)
        await safe_edit(callback.message, "📝 متنِ لقبِ جدید را بفرست:", cancel_kb(owner))
    else:
        await safe_edit(callback.message, "🏷️ یوزرآیدیِ کاربری که می‌خواهی لقبِ دلخواه بدهی را بفرست:", cancel_kb(owner))
    await callback.answer()


@router.callback_query(F.data.startswith("adm:t:clear"))
async def title_clear_cb(callback: CallbackQuery, state: FSMContext):
    admin = await _cb_admin(callback)
    if admin is None:
        return
    if not _require(admin, "titles"):
        await callback.answer("⛔ دسترسی نداری.", show_alert=True)
        return
    base, owner = split_owner(callback.data)
    parts = base.split(":")
    await state.set_state(AdminStates.title_wait_uid)
    await state.update_data(title_action="clear")
    if len(parts) >= 4 and parts[3].isdigit():
        target = int(parts[3])
        async with async_session() as session:
            await titles_svc.clear_active_title(session, target)
            await adm.audit(session, callback.from_user.id, "title_clear", target_id=target, commit=False)
            await session.commit()
        await state.clear()
        await safe_edit(callback.message, f"✅ لقبِ فعالِ کاربر <code>{target}</code> حذف شد.", back_kb(owner))
    else:
        await safe_edit(callback.message, "��� یوزرآیدیِ کاربری که می‌خواهی لقبِ دلخواهش حذف شود را بفرست:", cancel_kb(owner))
    await callback.answer()


@router.message(StateFilter(AdminStates.title_wait_uid))
async def title_uid(message: Message, state: FSMContext):
    admin = await _guard_admin(message, state)
    if admin is None:
        return
    if await handle_cancel_word(message, state):
        return
    target = _parse_int(message.text)
    if target is None:
        await message.answer("⚠ یوزرآیدی باید عدد باشد. دوباره:")
        return
    data = await state.get_data()
    if data.get("title_action") == "clear":
        async with async_session() as session:
            await titles_svc.clear_active_title(session, target)
            await adm.audit(session, message.from_user.id, "title_clear", target_id=target, commit=False)
            await session.commit()
        await state.clear()
        await message.answer(f"✅ لقبِ فعالِ کاربر <code>{target}</code> حذف شد.")
        await _send_panel(message, message.from_user.id, admin)
        return
    await state.update_data(target=target)
    await state.set_state(AdminStates.title_wait_custom)
    await message.answer("📝 متنِ لقبِ دلخواه را بفرست:")


@router.message(StateFilter(AdminStates.title_wait_custom))
async def title_custom_save(message: Message, state: FSMContext):
    admin = await _guard_admin(message, state)
    if admin is None:
        return
    if await handle_cancel_word(message, state):
        return
    data = await state.get_data()
    target = data.get("target")
    async with async_session() as session:
        ok, res = await titles_svc.set_custom_title(session, target, message.text or "", force=True)
        if ok:
            await adm.audit(session, message.from_user.id, "title_custom", target_id=target, detail=res, commit=False)
        await session.commit()
    if not ok:
        await message.answer(f"⚠ {res}\nدوباره بفرست:")
        return
    await state.clear()
    await message.answer(f"✅ لقبِ دلخواهِ کاربر <code>{target}</code> ثبت شد: <b>{res}</b>")
    await _send_panel(message, message.from_user.id, admin)


# ---------------------------------------------------------------------------
# لقبِ دلخواهِ خودِ ادمین (برایِ همه‌یِ ادمین‌ها باز است)
# ---------------------------------------------------------------------------
@router.callback_query(F.data.startswith("adm:mytitle"))
async def mytitle_cb(callback: CallbackQuery, state: FSMContext):
    admin = await _cb_admin(callback)
    if admin is None:
        return
    _, owner = split_owner(callback.data)
    await state.set_state(AdminStates.title_wait_custom)
    await state.update_data(target=callback.from_user.id)
    await safe_edit(callback.message, "🏷️ متنِ لقبِ دلخواهِ خودرا بفرست (برایِ ادمین‌ها بدونِ نیاز به اشتراک):", cancel_kb(owner))
    await callback.answer()


# ---------------------------------------------------------------------------
# اخبار + همگانی
# ---------------------------------------------------------------------------
@router.callback_query(F.data.startswith("adm:news:add"))
async def news_add_cb(callback: CallbackQuery, state: FSMContext):
    admin = await _cb_admin(callback)
    if admin is None:
        return
    if not _require(admin, "news"):
        await callback.answer("⛔ دسترسی نداری.", show_alert=True)
        return
    _, owner = split_owner(callback.data)
    await state.set_state(AdminStates.news_wait_text)
    await safe_edit(callback.message, "📝 متنِ خبر را بفرست (در دایجستِ بعدی منتشر می‌شود):", cancel_kb(owner))
    await callback.answer()


@router.message(StateFilter(AdminStates.news_wait_text))
async def news_text(message: Message, state: FSMContext):
    admin = await _guard_admin(message, state)
    if admin is None:
        return
    if await handle_cancel_word(message, state):
        return
    text = _norm(message.text)
    if not text:
        await message.answer("⚠ متن خالی است. دوباره:")
        return
    async with async_session() as session:
        await news_service.add_news(session, "admin", text, actor_id=message.from_user.id)
        await adm.audit(session, message.from_user.id, "news_add", detail=text[:64])
    await state.clear()
    await message.answer("✅ خبر ثبت شد.")
    await _send_panel(message, message.from_user.id, admin)


@router.callback_query(F.data.startswith("adm:news:digest"))
async def news_digest_cb(callback: CallbackQuery):
    admin = await _cb_admin(callback)
    if admin is None:
        return
    if not _require(admin, "news"):
        await callback.answer("⛔ دسترسی نداری.", show_alert=True)
        return
    async with async_session() as session:
        text, n = await news_service.compile_daily_digest(session, mark_published=True)
        await adm.audit(session, callback.from_user.id, "news_digest", detail=str(n))
    await callback.answer(f"✅ {n} خبر منتشر شد.", show_alert=True)
    _, owner = split_owner(callback.data)
    await safe_edit(callback.message, text or "خبری برای انتشار نبود.", back_kb(owner))


@router.callback_query(F.data.startswith("adm:bc:new"))
async def bc_new_cb(callback: CallbackQuery, state: FSMContext):
    admin = await _cb_admin(callback)
    if admin is None:
        return
    if not _require(admin, "broadcast"):
        await callback.answer("⛔ دسترسی نداری.", show_alert=True)
        return
    _, owner = split_owner(callback.data)
    await state.set_state(AdminStates.broadcast_wait_text)
    await safe_edit(callback.message, "📢 متنِ پیامِ همگانی را بفرست (برای همه‌یِ کاربرا�� ارسال می‌شود):", cancel_kb(owner))
    await callback.answer()


@router.message(StateFilter(AdminStates.broadcast_wait_text))
async def bc_text(message: Message, state: FSMContext):
    """🆕 به‌جایِ ارسالِ فوری، متن را ذخیره و پیش‌نمایش نشان می‌دهد تا ادمین بتواند
    قبل از ارس����لِ نهایی آن را ویرایش کند."""
    admin = await _guard_admin(message, state)
    if admin is None:
        return
    if await handle_cancel_word(message, state):
        return
    text = message.text or ""
    if not _norm(text):
        await message.answer("⚠ متن خالی است. دوباره:")
        return
    await state.update_data(bc_text=text)
    await state.set_state(AdminStates.broadcast_confirm)
    uid = message.from_user.id
    await message.answer(
        "📢 <b>پیش‌نمایشِ پیامِ همگانی:</b>\n\n" + text +
        "\n\n———\nاین پیام برایِ همه‌ی کاربرانِ ثبت‌شده ارسال خواهد شد.\n"
        "می‌تونی همین الان بفرستیش، یا قبل از ارسال دوباره ویرایشش کنی.",
        reply_markup=admin_broadcast_confirm_kb(uid),
    )


@router.callback_query(F.data.startswith("adm:bc:edit"))
async def bc_edit_cb(callback: CallbackQuery, state: FSMContext):
    """🆕 ویرایشِ متنِ اطلاعیه/پیامِ همگانی قبل از ارسالِ نهایی."""
    admin = await _cb_admin(callback)
    if admin is None:
        return
    if not _require(admin, "broadcast"):
        await callback.answer("⛔ دسترسی نداری.", show_alert=True)
        return
    _, owner = split_owner(callback.data)
    await state.set_state(AdminStates.broadcast_wait_text)
    await safe_edit(callback.message, "✏️ متنِ جدیدِ پیامِ همگانی را بفرست:", cancel_kb(owner))
    await callback.answer()


@router.callback_query(F.data.startswith("adm:bc:send"))
async def bc_send_cb(callback: CallbackQuery, state: FSMContext):
    """🆕 ارسالِ نهایی پس از تأییدِ پیش‌نمایش."""
    admin = await _cb_admin(callback)
    if admin is None:
        return
    if not _require(admin, "broadcast"):
        await callback.answer("⛔ دسترسی نداری.", show_alert=True)
        return
    data = await state.get_data()
    text = data.get("bc_text")
    if not text:
        await callback.answer("⚠ متنی برایِ ارسال ثبت نشده؛ دوباره از اول بنویس.", show_alert=True)
        return
    await state.clear()
    async with async_session() as session:
        ids = (await session.execute(select(Player.tg_user_id))).scalars().all()
    sent = 0
    failed = 0
    for pid in ids:
        try:
            await callback.bot.send_message(pid, text)
            sent += 1
        except Exception:
            failed += 1
    async with async_session() as session:
        await adm.audit(session, callback.from_user.id, "broadcast", detail=f"sent={sent},failed={failed}")
    await callback.answer("✅ ارسال شد.", show_alert=True)
    await callback.message.answer(f"✅ پیامِ همگانی ارسال شد.\n📤 موفق: {sent} — ❌ ناموفق: {failed}")
    await _send_panel(callback.message, callback.from_user.id, admin)


# ---------------------------------------------------------------------------
# گزارش‌هایِ چت‌مود
# ---------------------------------------------------------------------------
@router.callback_query(F.data.startswith("adm:rep:open"))
async def rep_open_cb(callback: CallbackQuery):
    admin = await _cb_admin(callback)
    if admin is None:
        return
    if not _require(admin, "reports"):
        await callback.answer("⛔ دسترسی نداری.", show_alert=True)
        return
    from app.models.chat import ChatReport
    async with async_session() as session:
        rows = (await session.execute(
            select(ChatReport).where(ChatReport.status == "open").order_by(ChatReport.created_at.desc()).limit(15)
        )).scalars().all()
    if not rows:
        text = "🚨 گزارشِ بازی وجود ندارد."
    else:
        lines = ["🚨 <b>گزارش‌هایِ باز (شکایات):</b>", ""]
        for r in rows:
            ts = r.created_at.strftime("%Y-%m-%d %H:%M") if r.created_at else ""
            lines.append(f"• شاکی <code>{r.reporter_id}</code> ← متهم <code>{r.reported_id}</code>\n  🗒 {r.reason or '—'} ({ts})")
        text = "\n".join(lines)
    _, owner = split_owner(callback.data)
    await safe_edit(callback.message, text, back_kb(owner))
    await callback.answer()


@router.callback_query(F.data.startswith("adm:rep:sessions"))
async def rep_sessions_cb(callback: CallbackQuery):
    admin = await _cb_admin(callback)
    if admin is None:
        return
    if not _require(admin, "reports"):
        await callback.answer("⛔ دسترسی ندا��ی.", show_alert=True)
        return
    from app.models.chat import ChatSession
    async with async_session() as session:
        rows = (await session.execute(
            select(ChatSession).order_by(ChatSession.started_at.desc()).limit(12)
        )).scalars().all()
        ch_id = await adm.get_report_channel_id(session)
    if not rows:
        text = "🗂 جلسه‌یِ چتی ثبت نشده است."
    else:
        lines = ["🗂 <b>آخرین جلساتِ چت:</b>", ""]
        for s in rows:
            st = "🟢 فعال" if s.active else "⚪ پایان‌یافته"
            arch = f" — 🗃 آرشیو #{s.archive_msg_id}" if s.archive_msg_id else ""
            lines.append(f"• #{s.id}: <code>{s.user_a}</code> ↔ <code>{s.user_b}</code> {st}{arch}")
        note = "\n\n📁 فایل‌هایِ کاملِ هر جلسه در کانالِ گزارش موجود است." if ch_id else "\n\n⚠ کانالِ گزارش تنظیم نشده — فایل‌ها ارسال نمی‌شوند."
        text = "\n".join(lines) + note
    _, owner = split_owner(callback.data)
    await safe_edit(callback.message, text, back_kb(owner))
    await callback.answer()


# ---------------- گزارش اسپم / تایید لقب / نهایی‌سازی جنگ ----------------
@router.callback_query(F.data.startswith("adm:rep:spam"))
async def rep_spam_cb(callback: CallbackQuery):
    admin=await _cb_admin(callback)
    if admin is None: return
    if not _require(admin,"reports"):
        await callback.answer("⛔ دسترسی نداری.", show_alert=True); return
    _, owner=split_owner(callback.data)
    async with async_session() as session:
        rows=(await session.execute(select(SpamReport).order_by(SpamReport.created_at.desc()).limit(20))).scalars().all()
    if not rows: text="🚨 گزارش اسپمی ثبت نشده."
    else:
        lines=["🚨 <b>آخرین گزارش‌های اسپم</b>",""]
        for r in rows:
            ts=r.created_at.strftime("%Y-%m-%d %H:%M") if r.created_at else ""
            lines.append(f"#{r.id} | <code>{r.tg_user_id}</code> | {r.kind} | {r.count} بار | {ts}\n{r.action or '—'}")
        text="\n".join(lines)
    await safe_edit(callback.message,text,back_kb(owner)); await callback.answer()

@router.callback_query(F.data.startswith("adm:titleapprovals"))
async def title_approvals_cb(callback: CallbackQuery):
    admin=await _cb_admin(callback)
    if admin is None: return
    if admin.role != "main" and not _require(admin,"titles"):
        await callback.answer("⛔ دسترسی نداری.", show_alert=True); return
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from app.data import titles as TDATA2
    _, owner=split_owner(callback.data)
    async with async_session() as session:
        rows=(await session.execute(select(TitleApproval).where(TitleApproval.status=="pending").order_by(TitleApproval.requested_at.asc()).limit(20))).scalars().all()
    b=InlineKeyboardBuilder(); lines=["🎖️ <b>صف تایید لقب</b>",""]
    if not rows: lines.append("درخواستی در صف نیست.")
    for r in rows:
        t=TDATA2.get_title(r.title_key) or {"name":r.title_key}
        lines.append(f"#{r.id} | <code>{r.tg_user_id}</code> → {t['name']} ({r.source})")
        b.button(text=f"✅ تایید #{r.id}", callback_data=with_owner(f"adm:titleapproval:ok:{r.id}", owner))
        b.button(text=f"❌ رد #{r.id}", callback_data=with_owner(f"adm:titleapproval:no:{r.id}", owner))
    b.button(text="⬅️ بازگشت", callback_data=with_owner("adm:sec:titles", owner)); b.adjust(2)
    await safe_edit(callback.message,"\n".join(lines),b.as_markup()); await callback.answer()

@router.callback_query(F.data.startswith("adm:titleapproval:"))
async def title_approval_decide_cb(callback: CallbackQuery):
    admin=await _cb_admin(callback)
    if admin is None: return
    if admin.role != "main" and not _require(admin,"titles"):
        await callback.answer("⛔ دسترسی نداری.", show_alert=True); return
    base, owner=split_owner(callback.data); _,_,decision,rid=base.split(":")
    from datetime import datetime
    async with async_session() as session:
        rec=await session.get(TitleApproval,int(rid))
        if not rec or rec.status!="pending":
            await callback.answer("این درخواست دیگر فعال نیست.", show_alert=True); return
        target_uid = int(rec.tg_user_id)
        title_key = rec.title_key
        if decision=="ok":
            ok,msg=await titles_svc.admin_grant_title(session,rec.tg_user_id,rec.title_key,reassign_unique=True)
            rec.status="approved" if ok else "rejected"; note=f"تایید شد: {msg}" if ok else f"⚠ {msg}"
        else:
            ok=False; rec.status="rejected"; note="رد شد"; msg=""
        rec.reviewed_by=callback.from_user.id; rec.reviewed_at=datetime.utcnow(); await session.commit()
    if decision=="ok" and ok:
        try:
            from app.services import title_hook
            t = TDATA.get_title(title_key) if 'TDATA' in dir() else None
            try:
                from app.data import titles as _TD
                t = _TD.get_title(title_key)
            except Exception:
                t = {"name": msg or title_key, "key": title_key}
            text = title_hook.congrats_text([t] if t else [])
            if text:
                await callback.bot.send_message(target_uid, text)
            async with async_session() as session2:
                await title_hook.announce_titles(session2, target_uid, [t] if t else [])
        except Exception:
            pass
    await callback.answer(note, show_alert=True)
    await title_approvals_cb(callback.model_copy(update={"data": with_owner("adm:titleapprovals", owner)}))

@router.callback_query(F.data.startswith("adm:rankfinalize"))
async def admin_rank_finalize_cb(callback: CallbackQuery):
    admin=await _cb_admin(callback)
    if admin is None: return
    if not (admin.role=="main" or _require(admin,"economy") or _require(admin,"users")):
        await callback.answer("⛔ دسترسی نداری.", show_alert=True); return
    from app.services.ranked_battle_finalizer import finalize_finished_ranked_battles
    _, owner=split_owner(callback.data)
    async with async_session() as session:
        n=await finalize_finished_ranked_battles(session,limit=500); await session.commit()
    await safe_edit(callback.message,(f"✅ <b>{n}</b> جنگ رنکینگ نهایی شد." if n else "✅ جنگ نهایی‌نشده‌ای پیدا نشد."),back_kb(owner)); await callback.answer()


# ---------------------------------------------------------------------------
# کانالِ گزارش (فقط ادمینِ اصلی)
# ---------------------------------------------------------------------------
async def _show_channel(callback: CallbackQuery, uid: int, admin=None) -> None:
    async with async_session() as session:
        ch_id = await adm.get_report_channel_id(session)
        ch_title = await adm.get_report_channel_title(session)
    if ch_id:
        text = (
            "📡 <b>کانالِ گزارش</b>\n\n"
            f"کانالِ فعلی: <b>{ch_title or '—'}</b>\nآیدی: <code>{ch_id}</code>\n\n"
            "فایل‌هایِ هر چت‌مود (ZIP + اسکرین‌شات) به این کانال ارسال می‌شود."
        )
    else:
        text = (
            "📡 <b>کانالِ گزارش</b>\n\n"
            "هنوز کانالی تنظیم نشده است.\n\n"
            "️⚠ فقط یک کانالِ مجاز وجود دارد و تنها توسطِ ادمینِ اصلی انتخاب می‌شود."
        )
    kb = admin_channel_kb(uid, bool(ch_id))
    if admin is not None:
        kb = _with_subs(kb, uid, "channel", admin)
    await safe_edit(callback.message, text, kb)


async def _show_news(callback: CallbackQuery, uid: int, admin) -> None:
    is_main = admin.role == "main"
    ch_id = None
    ch_title = None
    if is_main:
        async with async_session() as session:
            ch_id = await adm.get_news_channel_id(session)
            ch_title = await adm.get_news_channel_title(session)
    lines = ["📰 <b>مدیریتِ اخبار</b>", A.PERMISSIONS["news"]["desc"], ""]
    if is_main:
        if ch_id:
            lines.append(f"کانالِ اخ��ا��ِ فعلی: <b>{ch_title or '—'}</b> (<code>{ch_id}</code>)")
        else:
            lines.append("هنوز کانالی برایِ اخبارِ روزانه تنظیم نشده — در این حالت (اگر باشد) از NEWS_CHANNEL_ID در .env استفاده می‌شود.")
    text = "\n".join(lines)
    await safe_edit(callback.message, text, admin_news_kb(uid, is_main, bool(ch_id)))


@router.callback_query(F.data.startswith("adm:ch:set"))
async def ch_set_cb(callback: CallbackQuery, state: FSMContext):
    admin = await _cb_admin(callback)
    if admin is None:
        return
    if admin.role != "main":
        await callback.answer("⛔ فقط ادمینِ اصلی.", show_alert=True)
        return
    _, owner = split_owner(callback.data)
    await state.set_state(AdminStates.channel_wait_ref)
    await safe_edit(
        callback.message,
        (
            "📡 <b>معرفیِ کانالِ گزارش</b>\n\n"
            "۱) ربات را در کانالِ خصوصیِ خودت عضو و ادمین کن.\n"
            "۲) یکی از روش‌هایِ زیر را بفرست:\n"
            "   • یک پیام را از داخلِ کانال به ربات فوروارد کن (بهترین روش)\n"
            "   • یا آیدیِ عددیِ کانال (مانندِ <code>-1001234567890</code>)\n"
            "   • یا لینکِ پیامِ کانال (t.me/c/...)"
        ),
        cancel_kb(owner),
    )
    await callback.answer()


@router.message(StateFilter(AdminStates.channel_wait_ref))
async def channel_ref(message: Message, state: FSMContext):
    admin = await _guard_admin(message, state)
    if admin is None:
        return
    if await handle_cancel_word(message, state):
        return
    if admin.role != "main":
        await state.clear()
        return
    chat_id = None
    title = None
    if message.forward_from_chat is not None:
        chat_id = message.forward_from_chat.id
        title = message.forward_from_chat.title
    else:
        chat_id = adm.parse_channel_id_from_text(message.text)
    if chat_id is None:
        await message.answer(
            "⚠ نتوانستم کانال را تشخیص دهم. بهتر است یک پیام را از داخلِ کانال فوروارد کنی.\nدوباره امتحان کن:"
        )
        return
    # اعتبارسنجی: ربات باید ادمینِ کانال ����اشد
    try:
        chat = await message.bot.get_chat(chat_id)
        title = title or chat.title
        me = await message.bot.get_me()
        member = await message.bot.get_chat_member(chat_id, me.id)
        if member.status not in ("administrator", "creator"):
            await message.answer("⚠ ربات ادمینِ این کانال نیست. اول ربات را ادمین کن و دوباره امتحان کن.")
            return
    except Exception as e:
        log.warning("channel validation failed: %s", e)
        await message.answer(
            "⚠ دسترسی به کانال ممکن نشد. مطمئن شو ربات درِ کانال عضو و ادمین است، سپس دوباره امتحان کن."
        )
        return
    async with async_session() as session:
        await adm.set_report_channel(session, chat_id, title, commit=False)
        await adm.audit(session, message.from_user.id, "set_report_channel", target_id=chat_id, detail=title, commit=False)
        await session.commit()
    await state.clear()
    await message.answer(f"✅ کانالِ گزارش تنظیم شد: <b>{title or chat_id}</b>")
    await _send_panel(message, message.from_user.id, admin)


@router.callback_query(F.data.startswith("adm:ch:remove"))
async def ch_remove_cb(callback: CallbackQuery):
    admin = await _cb_admin(callback)
    if admin is None:
        return
    if admin.role != "main":
        await callback.answer("⛔ فقط ادمینِ اصلی.", show_alert=True)
        return
    async with async_session() as session:
        await adm.clear_report_channel(session, commit=False)
        await adm.audit(session, callback.from_user.id, "clear_report_channel", commit=False)
        await session.commit()
    await callback.answer("🗑 کانالِ گزارش حذف شد.", show_alert=True)
    await _show_channel(callback, callback.from_user.id)


@router.callback_query(F.data.startswith("adm:ch:test"))
async def ch_test_cb(callback: CallbackQuery):
    admin = await _cb_admin(callback)
    if admin is None:
        return
    if admin.role != "main":
        await callback.answer("⛔ فقط ادمینِ اصلی.", show_alert=True)
        return
    async with async_session() as session:
        ch_id = await adm.get_report_channel_id(session)
    if not ch_id:
        await callback.answer("⚠ کانالی تنظیم نشده.", show_alert=True)
        return
    try:
        await callback.bot.send_message(ch_id, "✅ تستِ کانالِ گزارش — ربات به این کانال دسترسی دارد.")
        await callback.answer("✅ پیامِ تست ارسال شد.", show_alert=True)
    except Exception:
        await callback.answer("⚠ ارسال ناموفق بود. دسترسیِ ربات را بررسی کن.", show_alert=True)


# ---------------------------------------------------------------------------
# کانالِ اخبارِ روزانه (فقط ادمینِ اصلی)
# ---------------------------------------------------------------------------
@router.callback_query(F.data.startswith("adm:nc:set"))
async def nc_set_cb(callback: CallbackQuery, state: FSMContext):
    admin = await _cb_admin(callback)
    if admin is None:
        return
    if admin.role != "main":
        await callback.answer("⛔ فقط ادمینِ اصلی.", show_alert=True)
        return
    _, owner = split_owner(callback.data)
    await state.set_state(AdminStates.news_channel_wait_ref)
    await safe_edit(
        callback.message,
        (
            "📡 <b>معرفیِ کانالِ اخبارِ روزانه</b>\n\n"
            "۱) ربات را در کانالِ خصوصیِ خودت عضو و ادمین کن.\n"
            "۲) یکی از روش‌هایِ زیر را بفرست:\n"
            "   • یک پیام را از داخلِ کانال به ربات فوروارد کن (بهترین روش)\n"
            "   • یا آیدیِ عددیِ کانال (مانندِ <code>-1001234567890</code>)\n"
            "   • یا لینکِ پیامِ کانال (t.me/c/...)"
        ),
        cancel_kb(owner),
    )
    await callback.answer()


@router.message(StateFilter(AdminStates.news_channel_wait_ref))
async def news_channel_ref(message: Message, state: FSMContext):
    admin = await _guard_admin(message, state)
    if admin is None:
        return
    if await handle_cancel_word(message, state):
        return
    if admin.role != "main":
        await state.clear()
        return
    chat_id = None
    title = None
    if message.forward_from_chat is not None:
        chat_id = message.forward_from_chat.id
        title = message.forward_from_chat.title
    else:
        chat_id = adm.parse_channel_id_from_text(message.text)
    if chat_id is None:
        await message.answer(
            "⚠ نتوانستم کانال را تشخیص دهم. بهتر است یک پیام را از داخلِ کانال فوروارد کنی.\nدوباره امتحان کن:"
        )
        return
    try:
        chat = await message.bot.get_chat(chat_id)
        title = title or chat.title
        me = await message.bot.get_me()
        member = await message.bot.get_chat_member(chat_id, me.id)
        if member.status not in ("administrator", "creator"):
            await message.answer("⚠ ربات ادمینِ این کانال نیست. اول ربات را ادمین کن و دوباره امتحان کن.")
            return
    except Exception as e:
        log.warning("news channel validation failed: %s", e)
        await message.answer(
            "⚠ دسترسی به کانال ممکن نشد. مطمئن شو ربات درِ کانال عضو و ادمین است، سپس دوباره امتحان کن."
        )
        return
    async with async_session() as session:
        await adm.set_news_channel(session, chat_id, title, commit=False)
        await adm.audit(session, message.from_user.id, "set_news_channel", target_id=chat_id, detail=title, commit=False)
        await session.commit()
    await state.clear()
    await message.answer(f"✅ کانالِ اخب��ر تنظیم شد: <b>{title or chat_id}</b>")
    await _send_panel(message, message.from_user.id, admin)


@router.callback_query(F.data.startswith("adm:nc:remove"))
async def nc_remove_cb(callback: CallbackQuery):
    admin = await _cb_admin(callback)
    if admin is None:
        return
    if admin.role != "main":
        await callback.answer("⛔ فقط ادمینِ اصلی.", show_alert=True)
        return
    async with async_session() as session:
        await adm.clear_news_channel(session, commit=False)
        await adm.audit(session, callback.from_user.id, "clear_news_channel", commit=False)
        await session.commit()
    await callback.answer("🗑 کانالِ اخبار حذف شد.", show_alert=True)
    await _show_news(callback, callback.from_user.id, admin)


@router.callback_query(F.data.startswith("adm:nc:test"))
async def nc_test_cb(callback: CallbackQuery):
    admin = await _cb_admin(callback)
    if admin is None:
        return
    if admin.role != "main":
        await callback.answer("⛔ فقط ادمینِ اصلی.", show_alert=True)
        return
    async with async_session() as session:
        ch_id = await adm.get_news_channel_id(session)
    if not ch_id:
        await callback.answer("⚠ کانالی تنظیم نشده.", show_alert=True)
        return
    try:
        await callback.bot.send_message(ch_id, "✅ تستِ کانالِ اخبار — ربات به این کانال دسترسی دارد.")
        await callback.answer("✅ پیامِ تست ارسال شد.", show_alert=True)
    except Exception:
        await callback.answer("⚠ ارسال ناموفق بود. دسترسیِ ربات را بررسی کن.", show_alert=True)


# ---------------------------------------------------------------------------
# آمار
# ---------------------------------------------------------------------------
async def _show_stats(callback: CallbackQuery, uid: int, admin=None) -> None:
    from app.models.subscription import Subscription
    from app.models.war import Battle
    from app.models.purchase import PurchaseHistory
    from datetime import datetime, timedelta
    async with async_session() as session:
        n_players = (await session.execute(select(func.count()).select_from(Player))).scalar() or 0
        n_banned = (await session.execute(select(func.count()).select_from(Player).where(Player.banned.is_(True)))).scalar() or 0
        n_subs = (await session.execute(select(func.count()).select_from(Subscription).where(Subscription.tier != "free"))).scalar() or 0
        n_admins = len(await adm.list_admins(session))
        n_active_24 = (await session.execute(select(func.count()).select_from(Player).where(Player.last_seen >= datetime.utcnow() - timedelta(hours=24)))).scalar() or 0
        n_battles = (await session.execute(select(func.count()).select_from(Battle))).scalar() or 0
        money_spent = (await session.execute(select(func.coalesce(func.sum(PurchaseHistory.amount), 0)).where(PurchaseHistory.status == "active"))).scalar() or 0
    text = "\n".join([
        "📊 <b>آمارِ بازی</b>",
        "",
        f"👥 کلِ کاربران: <b>{n_players:,}</b>",
        f"🟢 کاربران فعال ۲۴ ساعت: <b>{n_active_24:,}</b>",
        f"🚫 کاربرانِ محدود: <b>{n_banned:,}</b>",
        f"⚔️ تعداد جنگ‌های ثبت‌شده: <b>{n_battles:,}</b>",
        f"💸 مبلغ خرج‌شده در اشتراک‌ها: <b>{int(money_spent):,}$</b>",
        f"💎 اشتراک‌هایِ فعال: <b>{n_subs:,}</b>",
        f"👑 تعدادِ ادمین‌ها: <b>{n_admins}</b>",
    ])
    _, owner = split_owner(callback.data)
    kb = back_kb(owner)
    if admin is not None:
        kb = _with_subs(kb, owner, "stats", admin)
    await safe_edit(callback.message, text, kb)


# ---------------------------------------------------------------------------
# مدیریتِ ادمین‌ها (فقط ادمینِ اصلی)
# ---------------------------------------------------------------------------
@router.callback_query(F.data.startswith("adm:a:list"))
async def admins_list_cb(callback: CallbackQuery):
    admin = await _cb_admin(callback)
    if admin is None:
        return
    if admin.role != "main":
        await callback.answer("⛔ فقط ادمینِ اصلی.", show_alert=True)
        return
    async with async_session() as session:
        admins = await adm.list_admins(session)
    lines = ["📋 <b>فهرستِ ادمین‌ها:</b>", ""]
    for a in admins:
        role = "👑 اصلی" if a.role == "main" else "🛡️ فرعی"
        st = "" if a.active else " (غیرفعال)"
        perms = "همه" if a.role == "main" else ("، ".join(A.PERMISSIONS[k]["label"] for k in adm.perms_of(a)) or "—")
        lines.append(f"• {role} <code>{a.tg_user_id}</code>{st}\n  🔑 {perms}")
    _, owner = split_owner(callback.data)
    await safe_edit(callback.message, "\n".join(lines), back_kb(owner))
    await callback.answer()


@router.callback_query(F.data.startswith("adm:a:add"))
async def admins_add_cb(callback: CallbackQuery, state: FSMContext):
    admin = await _cb_admin(callback)
    if admin is None:
        return
    if admin.role != "main":
        await callback.answer("⛔ فقط ادمینِ اصلی.", show_alert=True)
        return
    _, owner = split_owner(callback.data)
    await state.set_state(AdminStates.admins_wait_uid)
    await state.update_data(admin_action="add", selected=[])
    await safe_edit(callback.message, "➕ یوزرآیدیِ ادمینِ جدید را بفرست:", cancel_kb(owner))
    await callback.answer()


@router.callback_query(F.data.startswith("adm:a:edit"))
async def admins_edit_cb(callback: CallbackQuery, state: FSMContext):
    admin = await _cb_admin(callback)
    if admin is None:
        return
    if admin.role != "main":
        await callback.answer("⛔ فقط ادمینِ اصلی.", show_alert=True)
        return
    _, owner = split_owner(callback.data)
    await state.set_state(AdminStates.admins_wait_uid)
    await state.update_data(admin_action="edit")
    await safe_edit(callback.message, "🛠 یوزرآیدیِ ادمینی که می‌خواهی دسترسی‌هایش را ویرایش کنی را بفرست:", cancel_kb(owner))
    await callback.answer()


@router.callback_query(F.data.startswith("adm:a:revoke"))
async def admins_revoke_cb(callback: CallbackQuery, state: FSMContext):
    admin = await _cb_admin(callback)
    if admin is None:
        return
    if admin.role != "main":
        await callback.answer("⛔ فقط ادمینِ اصلی.", show_alert=True)
        return
    _, owner = split_owner(callback.data)
    await state.set_state(AdminStates.admins_wait_revoke)
    await safe_edit(callback.message, "❌ یوزرآیدیِ ادمینی که می‌خواهی عزل کنی را بفرست:", cancel_kb(owner))
    await callback.answer()


@router.message(StateFilter(AdminStates.admins_wait_revoke))
async def admins_revoke_uid(message: Message, state: FSMContext):
    admin = await _guard_admin(message, state)
    if admin is None or admin.role != "main":
        await state.clear()
        return
    if await handle_cancel_word(message, state):
        return
    target = _parse_int(message.text)
    if target is None:
        await message.answer("⚠ یوزرآیدی باید عدد باشد. دوباره:")
        return
    async with async_session() as session:
        ok = await adm.revoke_admin(session, target, by=message.from_user.id, commit=False)
        if ok:
            await adm.audit(session, message.from_user.id, "revoke_admin", target_id=target, commit=False)
        await session.commit()
    await state.clear()
    if ok:
        await message.answer(f"✅ ادمین <code>{target}</code> عزل شد. ����سترسی‌هایش پاک شد و دیگر به کلمه‌یِ ادمین‌مود پاسخ نمی‌دهد.")
    else:
        await message.answer("⚠ یا ادمین نبود یا ادمینِ اصلی است (قابلِ عزل نیست).")
    await _send_panel(message, message.from_user.id, admin)


@router.message(StateFilter(AdminStates.admins_wait_uid))
async def admins_uid(message: Message, state: FSMContext):
    admin = await _guard_admin(message, state)
    if admin is None or admin.role != "main":
        await state.clear()
        return
    if await handle_cancel_word(message, state):
        return
    target = _parse_int(message.text)
    if target is None:
        await message.answer("⚠ یوزرآیدی باید عدد باشد. دوباره:")
        return
    data = await state.get_data()
    action = data.get("admin_action", "add")
    if target == adm.MAIN_ADMIN_ID:
        await state.clear()
        await message.answer("⚠ این یوزرآیدی متعلق به ادمینِ اصلی است.")
        await _send_panel(message, message.from_user.id, admin)
        return
    # بارگذاریِ دسترسی‌هایِ فعلی (برایِ edit)
    selected: list[str] = []
    if action == "edit":
        async with async_session() as session:
            existing = await adm.get_admin_any(session, target)
        if existing is None or existing.role == "main":
            await state.clear()
            await message.answer("⚠ این کاربر ادمینِ فرعی نیست.")
            await _send_panel(message, message.from_user.id, admin)
            return
        selected = adm.perms_of(existing)
    await state.update_data(target=target, selected=selected)
    await _pperm_save(message.from_user.id, target, selected, action)
    await state.set_state(AdminStates.admins_wait_editperms)
    verb = "ویرایش" if action == "edit" else "انتصاب"
    await message.answer(
        f"🔑 دسترسی‌هایِ ادمین <code>{target}</code> را انتخاب کن ({verb}):",
        reply_markup=perms_picker_kb(message.from_user.id, selected),
    )


@router.callback_query(F.data.startswith("adm:perm:toggle:"))
async def perm_toggle_cb(callback: CallbackQuery, state: FSMContext):
    admin = await _cb_admin(callback)
    if admin is None or admin.role != "main":
        return
    base, owner = split_owner(callback.data)
    key = base.split("adm:perm:toggle:", 1)[1]
    target, selected, action = await _pperm_state(callback, state)
    selected = list(selected)
    if not A.is_valid_perm(key):
        await callback.answer("⚠ این دسترسی نامعتبر است.", show_alert=True)
        return
    if key in selected:
        selected.remove(key)
        toast = f"⬜ {A.perm_label(key)} برداشته شد"
    elif key not in A.GRANTABLE:
        await callback.answer(
            "⛔ این دسترسی مخصوصِ ادمینِ اصلی است و قابلِ واگذاری نیست.",
            show_alert=True,
        )
        return
    else:
        selected.append(key)
        toast = f"✅ {A.perm_label(key)} انتخاب شد"
    await state.update_data(selected=selected)
    if target is not None:
        await _pperm_save(callback.from_user.id, target, selected, action)
    try:
        await callback.message.edit_reply_markup(
            reply_markup=perms_picker_kb(owner or callback.from_user.id, selected)
        )
    except Exception:
        pass
    await callback.answer(toast)


@router.callback_query(F.data.startswith("adm:perm:save"))
async def perm_save_cb(callback: CallbackQuery, state: FSMContext):
    admin = await _cb_admin(callback)
    if admin is None or admin.role != "main":
        return
    target, selected, action = await _pperm_state(callback, state)
    selected = list(selected)
    if target is None:
        await callback.answer(
            "⚠ انتخابِ دسترسی‌ها منقضی شده. از منوی ادمین‌ها دوباره شروع کن.",
            show_alert=True,
        )
        return
    if action == "edit":
        async with async_session() as session:
            await adm.update_permissions(session, target, selected, commit=False)
            await adm.audit(session, callback.from_user.id, "edit_perms", target_id=target, detail=",".join(selected), commit=False)
            await session.commit()
        await state.clear()
        await _pperm_clear(callback.from_user.id)
        await callback.answer("✅ دسترسی‌ها به‌روز شد.", show_alert=True)
        await _refresh_panel(callback, admin, note=f"✅ دسترسی‌هایِ ادمین <code>{target}</code> به‌روز شد.")
        return
    # add → رمزِ اولیه بگیر
    await state.update_data(selected=selected)
    await state.set_state(AdminStates.admins_wait_initpw)
    _, owner = split_owner(callback.data)
    suggestion = A.generate_initial_password()
    await state.update_data(suggestion=suggestion)
    await safe_edit(
        callback.message,
        (
            f"🔐 یک رمزِ اولیه برایِ ادمینِ جدید بفرست، یا «پیشنهاد» را بفرست تا این رمز انتخاب شود:\n"
            f"💡 پیشنهاد: <code>{suggestion}</code>\n\n"
            "ادمینِ جدید با این رمز برایِ اولین بار وارد می‌شود و سپس مجبور است رمزش را عوض کند."
        ),
        cancel_kb(owner),
    )
    await callback.answer()


@router.message(StateFilter(AdminStates.admins_wait_initpw))
async def admins_initpw(message: Message, state: FSMContext):
    admin = await _guard_admin(message, state)
    if admin is None or admin.role != "main":
        await state.clear()
        return
    data = await state.get_data()
    raw = _norm(message.text)
    if raw in A.CANCEL_WORDS:
        await state.clear()
        await _send_panel(message, message.from_user.id, admin, note="↩️ انتصابِ ادمینِ جدید لغو شد.")
        return
    if raw == "پیشنهاد":
        raw = data.get("suggestion") or A.generate_initial_password()
    ok, res = A.password_ok(raw)
    if not ok:
        await message.answer(f"⚠ {res}\nدوباره بفرست (یا «پیشنهاد»):")
        return
    target, selected, _action = await _pperm_state(message, state)
    selected = list(selected)
    if target is None:
        await state.clear()
        await message.answer(
            "⚠ اطلاعاتِ انتصاب منقضی شده. از منوی ادمین‌ها دوباره شروع کن."
        )
        return
    async with async_session() as session:
        await adm.assign_admin(session, target, selected, res, assigned_by=message.from_user.id, commit=False)
        await adm.audit(session, message.from_user.id, "assign_admin", target_id=target, detail=",".join(selected), commit=False)
        await session.commit()
    await state.clear()
    await _pperm_clear(message.from_user.id)
    perms_txt = "، ".join(A.PERMISSIONS[k]["label"] for k in selected) or "—"
    await message.answer(
        f"✅ ادمینِ جدید منتصب شد.\n"
        f"🆔 آیدی: <code>{target}</code>\n"
        f"🔑 دسترسی‌ها: {perms_txt}\n"
        f"🔐 رمزِ اولیه: <code>{res}</code>\n\n"
        "این رمز را به ادمینِ جدید بده؛ با «ادمین مود» وارد می‌شود و در اولین ورود باید رمزش را عوض کند."
    )
    await _send_panel(message, message.from_user.id, admin)


# ===========================================================================
# 🆕 مرحله ۲۷ — رویدادهایِ بونس (بونسِ XP و بونسِ پول برایِ اونتِ دلخواهِ ادمین)
# ===========================================================================
async def _show_events(callback: CallbackQuery, owner_id: int) -> None:
    async with async_session() as session:
        st = await event_service.load_bonus(session)
    await safe_edit(
        callback.message,
        EV.status_text(st),
        admin_events_kb(owner_id, st.xp_active, st.money_active),
    )


@router.callback_query(F.data.startswith("adm:ev:off:"))
async def ev_off_cb(callback: CallbackQuery, state: FSMContext):
    """خاموش‌کردنِ یک بونس (XP یا پول)."""
    admin = await _cb_admin(callback)
    if admin is None:
        return
    if not _require(admin, "events"):
        await callback.answer(A.denied_text("events"), show_alert=True)
        return
    base, owner = split_owner(callback.data)
    kind = base.split("adm:ev:off:", 1)[1]
    if kind not in EV.KINDS:
        await callback.answer("❗ نوعِ رویداد نامعتبر است.", show_alert=True)
        return
    async with async_session() as session:
        await event_service.set_bonus(session, kind, active=False, commit=False)
        await adm.audit(session, callback.from_user.id, "event_off", detail=kind, commit=False)
        await session.commit()
    await _show_events(callback, owner)
    await callback.answer(f"🔴 بونسِ {EV.kind_label(kind)} خاموش شد.")


@router.callback_query(F.data.startswith("adm:ev:on:"))
async def ev_on_cb(callback: CallbackQuery, state: FSMContext):
    """شروعِ مراحلِ فعال‌کردن: اول ضریب، بعد مد��."""
    admin = await _cb_admin(callback)
    if admin is None:
        return
    if not _require(admin, "events"):
        await callback.answer(A.denied_text("events"), show_alert=True)
        return
    base, owner = split_owner(callback.data)
    kind = base.split("adm:ev:on:", 1)[1]
    if kind not in EV.KINDS:
        await callback.answer("❗ نوعِ رویداد نامعتبر است.", show_alert=True)
        return
    await state.set_state(AdminStates.event_wait_mult)
    await state.update_data(ev_kind=kind)
    await safe_edit(
        callback.message,
        f"✨ <b>فعال‌کردنِ بونسِ {EV.kind_label(kind)}</b>\n\n"
        f"ضریبِ رویداد را بفرست (مثلاً <code>2</code> یا <code>x3</code> یا <code>1.5</code>).\n"
        f"مجاز: از {EV.MIN_MULT:g} تا {EV.MAX_MULT:g}",
        cancel_kb(owner),
    )
    await callback.answer()


@router.message(StateFilter(AdminStates.event_wait_mult))
async def ev_mult_msg(message: Message, state: FSMContext):
    admin = await _guard_perm(message, state, "events")
    if admin is None:
        return
    if await handle_cancel_word(message, state):
        return
    ok, val = EV.parse_multiplier(message.text)
    if not ok:
        await message.answer(str(val))
        return
    await state.update_data(ev_mult=float(val))
    await state.set_state(AdminStates.event_wait_hours)
    await message.answer(
        "⏱ مدتِ رویداد را به <b>ساعت</b> ب��رست (مثلاً <code>12</code> یا <code>48</code>).\n"
        "اگر می‌خواهی تا وقتی خودت خاموشش کنی روشن بماند، بنویس: <code>نامحدود</code>"
    )


@router.message(StateFilter(AdminStates.event_wait_hours))
async def ev_hours_msg(message: Message, state: FSMContext):
    admin = await _guard_perm(message, state, "events")
    if admin is None:
        return
    if await handle_cancel_word(message, state):
        return
    ok, hours = EV.parse_hours(message.text)
    if not ok:
        await message.answer(str(hours))
        return
    data = await state.get_data()
    kind = data.get("ev_kind")
    mult = float(data.get("ev_mult") or 1.0)
    if kind not in EV.KINDS:
        await state.clear()
        await message.answer("⚠ فرایند معتبر نبود؛ از پنل دوباره شروع کن.")
        return
    async with async_session() as session:
        st = await event_service.set_bonus(
            session, kind, active=True, mult=mult, hours=int(hours), commit=False
        )
        await adm.audit(
            session, message.from_user.id, "event_on",
            detail=f"{kind} x{mult:g} {int(hours)}h", commit=False,
        )
        await session.commit()
    await state.clear()
    uids = []
    async with async_session() as session2:
        uids = list((await session2.execute(select(Player.tg_user_id))).scalars().all())
    await message.answer("✅ رویداد فعال شد.\n\n" + EV.status_text(st))
    banner = "🎉 <b>بونس فعال شد!</b>\n\n" + EV.status_text(st)
    sent = 0
    for uid in uids:
        try:
            await message.bot.send_message(int(uid), banner); sent += 1
        except Exception:
            pass
    await message.answer(f"📣 اعلام بونس برای {sent} کاربر ارسال شد.")
    await _send_panel(message, message.from_user.id, admin)


@router.callback_query(F.data.startswith("adm:ev:title"))
async def ev_title_cb(callback: CallbackQuery, state: FSMContext):
    admin = await _cb_admin(callback)
    if admin is None:
        return
    if not _require(admin, "events"):
        await callback.answer(A.denied_text("events"), show_alert=True)
        return
    _, owner = split_owner(callback.data)
    await state.set_state(AdminStates.event_wait_title)
    await safe_edit(
        callback.message,
        "🏷 نامِ اونت را بفرست (مثلاً <code>شبِ پدرخوانده‌ها</code>).\n"
        "این نام در بنرِ رویداد به بازیکن‌ها نشان داده می‌شود. برایِ حذفِ نام بنویس: <code>-</code>",
        cancel_kb(owner),
    )
    await callback.answer()


@router.message(StateFilter(AdminStates.event_wait_title))
async def ev_title_msg(message: Message, state: FSMContext):
    admin = await _guard_perm(message, state, "events")
    if admin is None:
        return
    if await handle_cancel_word(message, state):
        return
    raw = (message.text or "").strip()
    title = "" if raw in {"-", "—"} else raw
    async with async_session() as session:
        st = await event_service.set_title(session, title, commit=False)
        await adm.audit(session, message.from_user.id, "event_title", detail=title, commit=False)
        await session.commit()
    await state.clear()
    await message.answer("✅ نامِ اونت ذخیره شد.\n\n" + EV.status_text(st))
    await _send_panel(message, message.from_user.id, admin)


@router.callback_query(F.data.startswith("adm:ev:clear"))
async def ev_clear_cb(callback: CallbackQuery, state: FSMContext):
    admin = await _cb_admin(callback)
    if admin is None:
        return
    if not _require(admin, "events"):
        await callback.answer(A.denied_text("events"), show_alert=True)
        return
    _, owner = split_owner(callback.data)
    async with async_session() as session:
        await event_service.clear_all(session, commit=False)
        await adm.audit(session, callback.from_user.id, "event_clear", commit=False)
        await session.commit()
    await _show_events(callback, owner)
    await callback.answer("🧹 همه‌ی رویدادها پایان یافت.")


@router.callback_query(F.data.startswith("adm:ev:announce"))
async def ev_announce_cb(callback: CallbackQuery, state: FSMContext):
    """اعلامِ رویدادِ فعال به همه‌ی بازیکن‌ها."""
    admin = await _cb_admin(callback)
    if admin is None:
        return
    if not _require(admin, "events"):
        await callback.answer(A.denied_text("events"), show_alert=True)
        return
    _, owner = split_owner(callback.data)
    async with async_session() as session:
        st = await event_service.load_bonus(session)
        uids = (await session.execute(select(Player.tg_user_id))).scalars().all()
    if not st.any_active():
        await callback.answer("⚠ هیچ رویدادی فعال نیست.", show_alert=True)
        return
    text = EV.player_banner() + "\n\n🎮 تا پایانِ اونت فرصت داری؛ برو سراغِ کار!"
    sent = 0
    for target in uids:
        try:
            await callback.bot.send_message(target, text)
            sent += 1
        except Exception:
            continue
    async with async_session() as session:
        await adm.audit(session, callback.from_user.id, "event_announce", detail=str(sent))
    await _show_events(callback, owner)
    await callback.answer(f"📣 به {sent} بازیکن اعلام شد.", show_alert=True)


# ===========================================================================
# 🆕 مرحله ۲۷ — ابزارهایِ ویژه: هدیهِ همگانی و ریستِ کاملِ یک کاربر
# (فقط ادمینِ اصلی — دسترسیِ tools در MAIN_ONLY است)
# ===========================================================================
@router.callback_query(F.data.startswith("adm:tl:gift:"))
async def tl_gift_cb(callback: CallbackQuery, state: FSMContext):
    admin = await _cb_admin(callback)
    if admin is None:
        return
    _perm = "economy" if (callback.data or "").split(":")[3] == "cash" else "bulk_levels"
    if not _require(admin, _perm):
        await callback.answer(A.denied_text(_perm), show_alert=True)
        return
    base, owner = split_owner(callback.data)
    kind = base.split("adm:tl:gift:", 1)[1]
    if kind not in ("cash", "xp"):
        await callback.answer("❗ نوعِ هدیه نامعتبر است.", show_alert=True)
        return
    label = "💰 پول" if kind == "cash" else "✨ XP"
    await state.set_state(AdminStates.tools_wait_gift_amount)
    await state.update_data(gift_kind=kind)
    await safe_edit(
        callback.message,
        f"🎁 <b>هدیهِ همگانی — {label}</b>\n\n"
        "مقدارِ هدیه برایِ هر بازیکن را بفرست (عددِ مثبت).",
        cancel_kb(owner),
    )
    await callback.answer()


@router.message(StateFilter(AdminStates.tools_wait_gift_amount))
async def tl_gift_msg(message: Message, state: FSMContext):
    admin = await _guard_perm(message, state, "economy" if (await state.get_data()).get("gift_kind", "cash") == "cash" else "bulk_levels")
    if admin is None:
        return
    if await handle_cancel_word(message, state):
        return
    amount = _parse_int(message.text)
    if amount is None or amount <= 0:
        await message.answer("⚠ عددِ مثبت بفرست:")
        return
    data = await state.get_data()
    kind = data.get("gift_kind") or "cash"
    async with async_session() as session:
        n = await adm.gift_all_players(session, kind, amount, commit=False)
        await adm.audit(
            session, message.from_user.id, "gift_all",
            detail=f"{kind} {amount} -> {n}", commit=False,
        )
        await session.commit()
    await state.clear()
    unit = "$" if kind == "cash" else " XP"
    await message.answer(f"🎁 به <b>{n}</b> بازیکن مبلغِ <b>{amount:,}{unit}</b> هدیه داده شد.")
    await _send_panel(message, message.from_user.id, admin)


# ===========================================================================
# 🆕 مرحله ۳۰ — هدیه به یک کاربرِ خاص (پول/XP) و هدیهِ لقب
# ===========================================================================
@router.callback_query(F.data.startswith("adm:tl:gift1:"))
async def tl_gift_one_cb(callback: CallbackQuery, state: FSMContext):
    admin = await _cb_admin(callback)
    if admin is None:
        return
    _perm = "economy" if (callback.data or "").split(":")[3] == "cash" else "bulk_levels"
    if not _require(admin, _perm):
        await callback.answer(A.denied_text(_perm), show_alert=True)
        return
    base, owner = split_owner(callback.data)
    kind = base.split("adm:tl:gift1:", 1)[1]
    if kind not in ("cash", "xp"):
        await callback.answer("❗ نوعِ هدیه نامعتبر است.", show_alert=True)
        return
    label = "💰 پول" if kind == "cash" else "✨ XP"
    await state.set_state(AdminStates.tools_wait_gift_uid)
    await state.update_data(gift_kind=kind)
    await safe_edit(
        callback.message,
        f"�� <b>هدیه به یک کاربر — {label}</b>\n\n"
        "یوزرآیدیِ کاربرِ هدف را بفرست (فقط عدد).",
        cancel_kb(owner),
    )
    await callback.answer()


@router.message(StateFilter(AdminStates.tools_wait_gift_uid))
async def tl_gift_one_uid_msg(message: Message, state: FSMContext):
    admin = await _guard_perm(message, state, "economy" if (await state.get_data()).get("gift_kind", "cash") == "cash" else "bulk_levels")
    if admin is None:
        return
    if await handle_cancel_word(message, state):
        return
    uid = _parse_int(message.text)
    if uid is None or uid <= 0:
        await message.answer("⚠ یوزرآیدیِ عددی بفرست:")
        return
    await state.update_data(gift_uid=uid)
    await state.set_state(AdminStates.tools_wait_gift_one)
    data = await state.get_data()
    unit = "دلار" if (data.get("gift_kind") or "cash") == "cash" else "XP"
    await message.answer(f"💵 مقدارِ هدیه به {unit} را بفرست (عددِ مثبت):")


@router.message(StateFilter(AdminStates.tools_wait_gift_one))
async def tl_gift_one_amount_msg(message: Message, state: FSMContext):
    admin = await _guard_perm(message, state, "economy" if (await state.get_data()).get("gift_kind", "cash") == "cash" else "bulk_levels")
    if admin is None:
        return
    if await handle_cancel_word(message, state):
        return
    amount = _parse_int(message.text)
    if amount is None or amount <= 0:
        await message.answer("⚠ عددِ مثبت بفرست:")
        return
    data = await state.get_data()
    kind = data.get("gift_kind") or "cash"
    uid = int(data.get("gift_uid") or 0)
    async with async_session() as session:
        ok, text = await adm.gift_one_player(session, uid, kind, amount, commit=False)
        if ok:
            await adm.audit(
                session, message.from_user.id, "gift_one",
                target_id=uid, detail=f"{kind} {amount}", commit=False,
            )
        await session.commit()
    await state.clear()
    await message.answer(text)
    if ok:
        unit = "دلار" if kind == "cash" else "XP"
        try:
            await message.bot.send_message(
                uid, f"🎁 از طرفِ مدیریتِ بازی مقدارِ <b>{amount:,}</b> {unit} به تو هدیه داده شد!"
            )
        except Exception:
            pass
    await _send_panel(message, message.from_user.id, admin)



@router.callback_query(F.data.startswith("adm:tl:evaltitles"))
async def tools_eval_titles_all(callback: CallbackQuery):
    admin = await _cb_admin(callback)
    if admin is None:
        return
    if admin.role != "main" and not _require(admin, "titles"):
        await callback.answer(A.denied_text("titles"), show_alert=True)
        return
    total, granted = 0, 0
    async with async_session() as session:
        ids = (await session.execute(select(Player.tg_user_id))).scalars().all()
        from app.services import title_hook
        for uid in ids:
            total += 1
            newly = await title_hook.check(session, int(uid), force=True)
            granted += len(newly or [])
        await adm.audit(session, callback.from_user.id, "eval_titles_all", detail=f"players={total}, granted={granted}", commit=False)
        await session.commit()
    await callback.answer(f"✅ {total} کاربر بررسی شد؛ {granted} لقب تازه ثبت شد.", show_alert=True)


@router.callback_query(F.data.startswith("adm:tl:milreport"))
async def tools_military_report_start(callback: CallbackQuery, state: FSMContext):
    admin = await _cb_admin(callback)
    if admin is None:
        return
    if admin.role != "main" and not _require(admin, "stats"):
        await callback.answer("⛔ دسترسی نداری.", show_alert=True)
        return
    _, owner = split_owner(callback.data)
    await state.set_state(AdminStates.tools_wait_military_uid)
    await safe_edit(callback.message, "🪖 آیدی عددی کاربر را برای گزارش نظامی بفرست:", cancel_kb(owner))
    await callback.answer()


@router.message(StateFilter(AdminStates.tools_wait_military_uid))
async def tools_military_report_uid(message: Message, state: FSMContext):
    admin = await _guard_admin(message, state)
    if admin is None:
        return
    if await handle_cancel_word(message, state):
        return
    target = _parse_int(message.text)
    if target is None:
        await message.answer("⚠ آیدی باید عدد باشد. دوباره:")
        return
    async with async_session() as session:
        player = await session.scalar(select(Player).where(Player.tg_user_id == target))
        units = await military_service.get_units(session, target)
        power = await military_service.army_power(session, target)
    name = (player.name if player else None) or "—"
    lines = [f"🪖 <b>گزارش نظامی کاربر</b>", f"👤 {name}", f"🆔 <code>{target}</code>", f"💥 قدرت ارتش: <b>{power:,}</b>", ""]
    rows = military_service.army_summary_lines(units)
    lines += rows if rows else ["نیروی نظامی ثبت نشده است."]
    await state.clear()
    await message.answer("\n".join(lines))
    await _send_panel(message, message.from_user.id, admin)

@router.callback_query(F.data.startswith("adm:tl:gifttitle"))
async def tl_gift_title_cb(callback: CallbackQuery, state: FSMContext):
    admin = await _cb_admin(callback)
    if admin is None:
        return
    if admin.role != "main" and not _require(admin, "titles"):
        await callback.answer(A.denied_text("titles"), show_alert=True)
        return
    _, owner = split_owner(callback.data)
    await state.set_state(AdminStates.tools_wait_title_uid)
    await safe_edit(
        callback.message,
        "🎖️ <b>هدیهِ لقب به کاربر</b>\n\n"
        "یوزرآیدیِ کاربرِ هدف را بفرست (فقط عدد).",
        cancel_kb(owner),
    )
    await callback.answer()


@router.message(StateFilter(AdminStates.tools_wait_title_uid))
async def tl_gift_title_uid_msg(message: Message, state: FSMContext):
    admin = await _guard_perm(message, state, "titles")
    if admin is None:
        return
    if await handle_cancel_word(message, state):
        return
    uid = _parse_int(message.text)
    if uid is None or uid <= 0:
        await message.answer("⚠ یوزرآیدیِ عددی بفرست:")
        return
    await state.update_data(title_uid=uid)
    await state.set_state(AdminStates.tools_wait_title_key)
    await message.answer(
        "🏷️ کلیدِ انگلیسی یا نامِ فارسیِ لقب را بفرست.\n\n"
        "نمونه:\n" + adm.title_suggestions()
    )


@router.message(StateFilter(AdminStates.tools_wait_title_key))
async def tl_gift_title_key_msg(message: Message, state: FSMContext):
    admin = await _guard_perm(message, state, "titles")
    if admin is None:
        return
    if await handle_cancel_word(message, state):
        return
    t = adm.find_title(message.text)
    if t is None:
        await message.answer("⚠ لقبی با این کلید/نام پیدا نشد. دوباره بفرست:")
        return
    data = await state.get_data()
    uid = int(data.get("title_uid") or 0)
    # بچ ۵: حتی درخواستِ ادمین فرعی هم مستقیماً لقب نمی‌دهد؛ نخست به صف ادمین اصلی می‌رود.
    from app.services import title_season
    async with async_session() as session:
        queued = await title_season.queue(session, uid, t["key"], source="manual")
        if queued:
            await adm.audit(session, message.from_user.id, "title_approval_requested", target_id=uid, detail=t["key"], commit=False)
        await session.commit()
    await state.clear()
    await message.answer("✅ درخواستِ اعطای لقب برای تأیید ادمین اصلی ثبت شد." if queued else "⚠ این لقب از قبل در صفِ تأیید است.")
    await _send_panel(message, message.from_user.id, admin)


@router.callback_query(F.data.startswith("adm:tl:resetok:"))
async def tl_reset_ok_cb(callback: CallbackQuery, state: FSMContext):
    """تأییدِ نهاییِ ریستِ کاملِ یک کاربر."""
    admin = await _cb_admin(callback)
    if admin is None:
        return
    if not _require(admin, "tools"):
        await callback.answer(A.denied_text("tools"), show_alert=True)
        return
    base, owner = split_owner(callback.data)
    target = _parse_int(base.split("adm:tl:resetok:", 1)[1])
    if target is None:
        await callback.answer("❗ یوزرآیدی نامعتبر است.", show_alert=True)
        return
    async with async_session() as session:
        ok, text = await adm.reset_player(session, target, commit=False)
        if ok:
            await adm.audit(session, callback.from_user.id, "reset_player", target_id=target, commit=False)
        await session.commit()
    await state.clear()
    await safe_edit(callback.message, text, admin_tools_kb(owner))
    await callback.answer("♻️ انجام شد." if ok else "⚠ کاربر پیدا نشد.", show_alert=True)


@router.callback_query(F.data.startswith("adm:tl:reset"))
async def tl_reset_cb(callback: CallbackQuery, state: FSMContext):
    admin = await _cb_admin(callback)
    if admin is None:
        return
    if not _require(admin, "tools"):
        await callback.answer(A.denied_text("tools"), show_alert=True)
        return
    _, owner = split_owner(callback.data)
    await state.set_state(AdminStates.tools_wait_reset_uid)
    await safe_edit(
        callback.message,
        "♻️ <b>ریستِ کاملِ یک کاربر</b>\n\n"
        "یوزرآیدیِ کاربر را بفرست. همه‌ی دارایی‌ها، پایگاه، عمارت، کارخانه، انبار، نیروها،"
        " لقب‌ها و سطحِ او پاک می‌شود و از صفر شروع می‌کند.",
        cancel_kb(owner),
    )
    await callback.answer()


@router.message(StateFilter(AdminStates.tools_wait_reset_uid))
async def tl_reset_uid_msg(message: Message, state: FSMContext):
    admin = await _guard_perm(message, state, "tools")
    if admin is None:
        return
    if await handle_cancel_word(message, state):
        return
    target = _parse_int(message.text)
    if target is None:
        await message.answer("⚠ یوزرآیدی باید عدد باشد. دوباره بفرست:")
        return
    async with async_session() as session:
        pl = (await session.execute(
            select(Player).where(Player.tg_user_id == target)
        )).scalar_one_or_none()
    if pl is None:
        await message.answer("⚠ کاربری با این یوزرآیدی در بازی نیست. یکی دیگر بفرست:")
        return
    await state.set_state(AdminStates.tools_confirm_reset)
    await state.update_data(reset_uid=target)
    await message.answer(
        f"⚠️ مطمئنی می‌خواهی کاربرِ زیر را کاملاً ریست کنی؟ این کار برگشت‌ناپذیر است.\n\n"
        f"🆔 <code>{target}</code>\n"
        f"🆙 لول: {pl.level} — 💰 پول: {int(pl.cash or 0):,}$",
        reply_markup=tools_reset_confirm_kb(message.from_user.id, target),
    )


# 🆕 پچ: ریستِ رنکینگِ مسابقات (تیم‌هایِ ورزشی و برندهایِ مسابقه‌ای)
@router.callback_query(
    F.data.startswith("adm:tl:sportreset") & ~F.data.startswith("adm:tl:sportresetok")
)
async def tl_sportreset_cb(callback: CallbackQuery, state: FSMContext):
    # 🐞 مرحله ۷۱ — همان الگوی اشتباه: دکمه‌ی تأییدِ ریست بی‌اثر می‌شد.
    admin = await _cb_admin(callback)
    if admin is None:
        return
    if not _require(admin, "tools"):
        await callback.answer(A.denied_text("tools"), show_alert=True)
        return
    _, owner = split_owner(callback.data)
    await safe_edit(
        callback.message,
        "🏆 <b>ریستِ رنکینگِ مسابقات</b>\n\n"
        "آمارِ برد/باخت/تساوی/امتیاز/گلِ همه‌ی تیم‌هایِ ورزشی و بر��د��ایِ مسابقه‌ای صفر می‌شود."
        " این کار برگشت‌ناپذیر است.",
        sports_reset_confirm_kb(owner),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("adm:tl:sportresetok"))
async def tl_sportreset_ok_cb(callback: CallbackQuery, state: FSMContext):
    admin = await _cb_admin(callback)
    if admin is None:
        return
    if not _require(admin, "tools"):
        await callback.answer(A.denied_text("tools"), show_alert=True)
        return
    _, owner = split_owner(callback.data)
    async with async_session() as session:
        n_teams, n_brands = await adm.reset_sports_rankings(session, commit=False)
        await adm.audit(
            session, callback.from_user.id, "reset_sports_rankings",
            detail=f"teams={n_teams} brands={n_brands}", commit=False,
        )
        await session.commit()
    await safe_edit(
        callback.message,
        f"✅ رنکینگِ مسابقات ریست شد.\nتیم‌ها: {n_teams} — برندهایِ مسابقه‌ای: {n_brands}",
        admin_tools_kb(owner),
    )
    await callback.answer("🏆 انجام شد.", show_alert=True)


# 🆕 دکمه‌های ریستِ محدودیت (مسابقات / تصرفِ شهر / فروشِ شهر)
@router.callback_query(F.data.startswith("adm:tl:racereset"))
async def tl_racereset_cb(callback: CallbackQuery):
    admin = await _cb_admin(callback)
    if admin is None:
        return
    if not _require(admin, "tools"):
        await callback.answer(A.denied_text("tools"), show_alert=True)
        return
    async with async_session() as session:
        n = await adm.reset_race_limit_today(session, commit=False)
        await adm.audit(session, callback.from_user.id, "reset_race_limit", detail=str(n), commit=False)
        await session.commit()
    await callback.answer(f"🏁 محدودیتِ مسابقاتِ امروز برای همه ریست شد ({n} رکورد).", show_alert=True)


@router.callback_query(F.data.startswith("adm:tl:capreset"))
async def tl_capreset_cb(callback: CallbackQuery):
    admin = await _cb_admin(callback)
    if admin is None:
        return
    if not _require(admin, "tools"):
        await callback.answer(A.denied_text("tools"), show_alert=True)
        return
    # 🆕 بچ ۴ — سیستمِ تصرفِ شهر و محدو��یت‌هایش بازنشسته شد.
    await callback.answer("🏰 سیستمِ تصرفِ شهر حذف شده است.", show_alert=True)


@router.callback_query(F.data.startswith("adm:tl:sellreset"))
async def tl_sellreset_cb(callback: CallbackQuery):
    admin = await _cb_admin(callback)
    if admin is None:
        return
    if not _require(admin, "tools"):
        await callback.answer(A.denied_text("tools"), show_alert=True)
        return
    # 🆕 بچ ۴ — سیستمِ فروشِ شهرِ قدیمی بازنشسته شد.
    await callback.answer("🏷️ سیستمِ فروشِ شهرِ قدیمی حذف شده است.", show_alert=True)



# ===========================================================================
# 🆕 مرحله ۲۹ — لیستِ کاربران (۱۰تایی، جستجو، رفتن به صفحه)
# ===========================================================================
def _ul_parse(base: str) -> tuple[int, str | None]:
    rest = base.split("adm:ul:", 1)[1] if "adm:ul:" in base else ""
    if not rest:
        return 0, None
    parts = rest.split(":", 1)
    try:
        page = int(parts[0])
    except Exception:
        page = 0
    query = parts[1] if len(parts) > 1 and parts[1].strip() else None
    return max(0, page), query


def _ul_line(i: int, p) -> str:
    uname = f" — @{p.username}" if getattr(p, "username", None) else ""
    ban = " 🚫" if getattr(p, "banned", False) else ""
    nm = p.name or "—"
    return f"{i}. {nm} — <code>{p.tg_user_id}</code> — 🆓{p.level}{uname}{ban}"


async def _ul_fetch(query: str | None, page: int):
    async with async_session() as session:
        stmt = select(Player)
        cnt = select(func.count()).select_from(Player)
        if query:
            like = f"%{query}%"
            stmt = stmt.where(Player.name.like(like))
            cnt = cnt.where(Player.name.like(like))
        total = int((await session.execute(cnt)).scalar() or 0)
        pages = max(1, (total + USERS_PER_PAGE - 1) // USERS_PER_PAGE)
        page = max(0, min(page, pages - 1))
        rows = (await session.execute(
            stmt.order_by(Player.level.desc(), Player.id)
            .offset(page * USERS_PER_PAGE)
            .limit(USERS_PER_PAGE)
        )).scalars().all()
    return rows, page, pages, total


def _ul_text(rows, page: int, pages: int, total: int, query: str | None) -> str:
    lines = ["📜 <b>لیستِ کاربران</b>"]
    if query:
        lines.append(f"🔎 جستجو: <b>{query}</b>")
    lines += [
        f"👥 تعدادِ کل: <b>{total:,}</b> کاربر",
        f"📖 صفحه‌ی <b>{page + 1}</b> از <b>{pages}</b> (هر صفحه {USERS_PER_PAGE} کاربر)",
        "",
    ]
    if rows:
        for i, p in enumerate(rows, start=page * USERS_PER_PAGE + 1):
            lines.append(_ul_line(i, p))
    else:
        lines.append("— کاربری پیدا نشد —")
    lines += ["", "روی هر کاربر بزن تا پروفایلِ کاملش را ببینی."]
    return "\n".join(lines)


@router.callback_query(F.data.startswith("adm:ul:"))
async def users_list_cb(callback: CallbackQuery, state: FSMContext):
    admin = await _cb_admin(callback)
    if admin is None:
        return
    if not _require(admin, "users"):
        await callback.answer(A.denied_text("users"), show_alert=True)
        return
    await state.clear()
    base, owner = split_owner(callback.data)
    page, query = _ul_parse(base)
    rows, page, pages, total = await _ul_fetch(query, page)
    await safe_edit(
        callback.message,
        _ul_text(rows, page, pages, total, query),
        users_list_kb(callback.from_user.id, rows, page, pages, query),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("adm:up:"))
async def users_list_card_cb(callback: CallbackQuery):
    admin = await _cb_admin(callback)
    if admin is None:
        return
    if not _require(admin, "users"):
        await callback.answer(A.denied_text("users"), show_alert=True)
        return
    base, owner = split_owner(callback.data)
    try:
        target = int(base.split("adm:up:", 1)[1])
    except Exception:
        await callback.answer("⚠ آیدیِ نامعتبر.", show_alert=True)
        return
    async with async_session() as session:
        player = (await session.execute(
            select(Player).where(Player.tg_user_id == target)
        )).scalar_one_or_none()
    if player is None:
        await callback.answer("⚠ کاربر پیدا نشد.", show_alert=True)
        return
    await safe_edit(callback.message, _player_card(player), user_card_kb(callback.from_user.id))
    await callback.answer()


@router.callback_query(F.data.startswith("adm:uls"))
async def users_list_search_cb(callback: CallbackQuery, state: FSMContext):
    admin = await _cb_admin(callback)
    if admin is None:
        return
    if not _require(admin, "users"):
        await callback.answer(A.denied_text("users"), show_alert=True)
        return
    _, owner = split_owner(callback.data)
    await state.set_state(AdminStates.users_list_search)
    await safe_edit(
        callback.message,
        "🔎 بخشی از نامِ کاربر را بفرست (یا عددِ آیدیِ کاربری):",
        cancel_kb(owner or callback.from_user.id),
    )
    await callback.answer()


@router.message(StateFilter(AdminStates.users_list_search))
async def users_list_search_msg(message: Message, state: FSMContext):
    admin = await _guard_perm(message, state, "users")
    if admin is None:
        return
    if await handle_cancel_word(message, state):
        return
    await state.clear()
    raw = (message.text or "").strip()
    if not raw:
        await message.answer("⚠ متنِ جستجو خالی بود.")
        return
    if raw.isdigit():
        async with async_session() as session:
            player = (await session.execute(
                select(Player).where(Player.tg_user_id == int(raw))
            )).scalar_one_or_none()
        if player is not None:
            await message.answer(_player_card(player), reply_markup=user_card_kb(message.from_user.id))
            return
    rows, page, pages, total = await _ul_fetch(raw, 0)
    await message.answer(
        _ul_text(rows, page, pages, total, raw),
        reply_markup=users_list_kb(message.from_user.id, rows, page, pages, raw),
    )


@router.callback_query(F.data.startswith("adm:ulg"))
async def users_list_goto_cb(callback: CallbackQuery, state: FSMContext):
    admin = await _cb_admin(callback)
    if admin is None:
        return
    if not _require(admin, "users"):
        await callback.answer(A.denied_text("users"), show_alert=True)
        return
    base, owner = split_owner(callback.data)
    rest = base.split("adm:ulg", 1)[1].lstrip(":")
    await state.set_state(AdminStates.users_list_goto)
    await state.update_data(ul_query=rest or None)
    await safe_edit(
        callback.message,
        "🔢 شماره‌ی صفحه‌ای که می‌خواهی بروی را بفرست (مثلاً 3):",
        cancel_kb(owner or callback.from_user.id),
    )
    await callback.answer()


@router.message(StateFilter(AdminStates.users_list_goto))
async def users_list_goto_msg(message: Message, state: FSMContext):
    admin = await _guard_perm(message, state, "users")
    if admin is None:
        return
    if await handle_cancel_word(message, state):
        return
    data = await state.get_data()
    query = data.get("ul_query")
    await state.clear()
    num = _parse_int(message.text)
    if num is None or num < 1:
        await message.answer("⚠ شماره‌ی صفحه باید عددِ معتبر باشد.")
        return
    rows, page, pages, total = await _ul_fetch(query, num - 1)
    await message.answer(
        _ul_text(rows, page, pages, total, query),
        reply_markup=users_list_kb(message.from_user.id, rows, page, pages, query),
    )



# ---------------------------------------------------------------------------
# کنترل بخش‌ها + کاربران لقب‌دار + تنظیم عددی
# ---------------------------------------------------------------------------
CONTROL_SECTIONS = {
    "theft": "دزدی",
    "base": "پایگاه",
    "estate": "عمارت",
    "factory": "کارخانه/بازار",
    "warehouse": "انبار اصلی",
    "city": "شهر",
    "war": "جنگ",
    "military": "نظامی",
    "bank": "بانک مافیایی",
    "brand": "برند/هولدینگ",
    "sports": "ورزش",
    "alliance": "اتحادیه",
    "spy": "جاسوسی",
    "transfer": "انتقال",
    "assistant": "دستیاران",
    "titles": "القاب",
    "subscription": "اشتراک",
    "news": "اخبار",
    "ranking": "رنکینگ",
    "chat": "چت/خط محرمانه",
    "photo": "عکس‌گذاری",
}

@router.callback_query(F.data.startswith("adm:ctrl:home"))
async def control_home(callback: CallbackQuery):
    admin = await _cb_admin(callback)
    if admin is None: return
    if not _require(admin, "sections_control"):
        await callback.answer("⛔ دسترسی نداری.", show_alert=True); return
    await safe_edit(callback.message, "🛑 <b>کنترل بخش‌های بازی</b>\nبرای توقف موقت باگ‌ها می‌توانی یک بخش را برای یک کاربر یا همه محدود کنی.", admin_control_kb(callback.from_user.id))
    await callback.answer()

# 🆕 کنترلِ دکمه‌ایِ خاموش‌کردنِ بخش‌ها (جایگزینِ تایپ‌کردنِ نامِ بخش)
CONTROL_ORDER = list(CONTROL_SECTIONS.items())


async def _ctrl_selected_uids(admin_uid: int) -> list[int]:
    async with async_session() as session:
        raw = await adm.get_setting(session, f"ctrlsel:{admin_uid}")
    if not raw:
        return []
    try:
        return [int(x) for x in json.loads(raw)]
    except Exception:
        return []


async def _ctrl_restricted_set(scope: str, admin_uid: int) -> set:
    """کلیدِ بخش‌هایی که هم‌اکنون خاموش (محدودیتِ فعال) دارند."""
    async with async_session() as session:
        if scope == "all":
            rows = (await session.execute(
                select(GameRestriction.section).where(
                    GameRestriction.active == True,
                    GameRestriction.tg_user_id.is_(None),
                )
            )).scalars().all()
            return set(rows)
        uids = await _ctrl_selected_uids(admin_uid)
        if not uids:
            return set()
        rows = (await session.execute(
            select(GameRestriction.section).where(
                GameRestriction.active == True,
                GameRestriction.tg_user_id.in_(uids),
            )
        )).scalars().all()
        return set(rows)


def _ctrl_menu_text(scope: str, uids: list) -> str:
    if scope == "all":
        who = "🌐 برای <b>همه‌ی کاربران</b>"
    else:
        who = "👤 برای: " + ("، ".join(f"<code>{u}</code>" for u in uids) if uids else "—")
    return (
        "🛑 <b>خاموش‌کردنِ بخش‌های بازی</b>\n"
        f"{who}\n\n"
        "روی هر بخش بزن تا خاموش/روشن شود.\n"
        "✅ = فعال (روشن) — 🚫 = خاموش (محدود)"
    )


@router.callback_query(F.data.startswith("adm:ctrl:add"))
async def control_add(callback: CallbackQuery, state: FSMContext):
    admin = await _cb_admin(callback)
    if admin is None: return
    if not _require(admin, "sections_control"):
        await callback.answer("⛔ دسترسی نداری.", show_alert=True); return
    await state.clear()
    await safe_edit(callback.message, "🛑 <b>خاموش‌کردنِ بخش‌ها</b>\n\nاول انتخاب کن این محدودیت برای چه کسانی باشد:", admin_control_scope_kb(callback.from_user.id))
    await callback.answer()


@router.callback_query(F.data.startswith("adm:ctrl:scope:all"))
async def control_scope_all(callback: CallbackQuery, state: FSMContext):
    admin = await _cb_admin(callback)
    if admin is None: return
    if not _require(admin, "sections_control"):
        await callback.answer("⛔ دسترسی نداری.", show_alert=True); return
    await state.clear()
    restricted = await _ctrl_restricted_set("all", callback.from_user.id)
    await safe_edit(callback.message, _ctrl_menu_text("all", []), admin_control_sections_kb(callback.from_user.id, CONTROL_ORDER, restricted, "all"))
    await callback.answer()


@router.callback_query(F.data.startswith("adm:ctrl:scope:sel"))
async def control_scope_sel(callback: CallbackQuery, state: FSMContext):
    admin = await _cb_admin(callback)
    if admin is None: return
    if not _require(admin, "sections_control"):
        await callback.answer("⛔ دسترسی نداری.", show_alert=True); return
    await state.set_state(AdminStates.control_wait_user)
    await safe_edit(callback.message, "👤 آیدیِ عددیِ کاربران را بفرست (می‌توانی چند نفر را با فاصله یا کاما جدا کنی):", cancel_kb(callback.from_user.id))
    await callback.answer()


@router.message(StateFilter(AdminStates.control_wait_user))
async def control_user_msg(message: Message, state: FSMContext):
    admin = await _guard_perm(message, state, "users")
    if admin is None: return
    if await handle_cancel_word(message, state): return
    raw = (message.text or "").replace("،", " ").replace(",", " ")
    uids = []
    for tok in raw.split():
        v = _parse_int(tok)
        if v is not None:
            uids.append(v)
    if not uids:
        await message.answer("⚠ حداقل ی�� آیدیِ عددیِ معتبر بفرست:"); return
    uids = sorted(set(uids))
    async with async_session() as session:
        await adm.set_setting(session, f"ctrlsel:{message.from_user.id}", json.dumps(uids), commit=True)
    await state.clear()
    restricted = await _ctrl_restricted_set("sel", message.from_user.id)
    await message.answer(_ctrl_menu_text("sel", uids), reply_markup=admin_control_sections_kb(message.from_user.id, CONTROL_ORDER, restricted, "sel"))


@router.callback_query(F.data.startswith("adm:ctrl:tog:"))
async def control_toggle(callback: CallbackQuery):
    admin = await _cb_admin(callback)
    if admin is None: return
    if not _require(admin, "sections_control"):
        await callback.answer("⛔ دسترسی نداری.", show_alert=True); return
    base, _ = split_owner(callback.data)
    parts = base.split(":")  # adm ctrl tog <scope> <section>
    scope = parts[3]; section = parts[4]
    if section not in CONTROL_SECTIONS:
        await callback.answer("بخش نامعتبر.", show_alert=True); return
    label = CONTROL_SECTIONS[section]
    if scope == "all":
        targets = [None]; uids_disp = []
    else:
        uids = await _ctrl_selected_uids(callback.from_user.id)
        if not uids:
            await callback.answer("⚠ ابتدا ک��ربران را انتخاب کن.", show_alert=True); return
        targets = uids; uids_disp = uids
    async with async_session() as session:
        cond = [GameRestriction.active == True, GameRestriction.section == section]
        if scope == "all":
            cond.append(GameRestriction.tg_user_id.is_(None))
        else:
            cond.append(GameRestriction.tg_user_id.in_(targets))
        existing = (await session.execute(select(GameRestriction).where(*cond))).scalars().all()
        if existing:
            for r in existing:
                r.active = False
            turned_off = False
        else:
            for t in targets:
                session.add(GameRestriction(section=section, tg_user_id=t, reason="admin-mode toggle", created_by=callback.from_user.id))
            turned_off = True
        await adm.audit(session, callback.from_user.id, "control_toggle", detail=f"{section} {'off' if turned_off else 'on'} {scope}", commit=False)
        await session.commit()
    restricted = await _ctrl_restricted_set(scope, callback.from_user.id)
    await safe_edit(callback.message, _ctrl_menu_text(scope, uids_disp), admin_control_sections_kb(callback.from_user.id, CONTROL_ORDER, restricted, scope))
    await callback.answer(("🚫 خاموش شد: " if turned_off else "✅ روشن شد: ") + label)


@router.callback_query(F.data.startswith("adm:ctrl:list"))
async def control_list(callback: CallbackQuery):
    admin = await _cb_admin(callback)
    if admin is None: return
    if not _require(admin, "sections_control"):
        await callback.answer("⛔ دسترسی نداری.", show_alert=True); return
    async with async_session() as session:
        rows=(await session.execute(select(GameRestriction).where(GameRestriction.active==True).order_by(GameRestriction.id.desc()).limit(30))).scalars().all()
    text="📋 <b>محدودیت‌های فعال</b>\n\n" + ("\n".join(f"#{r.id} {CONTROL_SECTIONS.get(r.section,r.section)} — {'همه' if r.tg_user_id is None else r.tg_user_id} — {r.reason or '—'}" for r in rows) if rows else "موردی نیست.")
    await safe_edit(callback.message, text, admin_control_kb(callback.from_user.id)); await callback.answer()

@router.callback_query(F.data.startswith("adm:ctrl:clearall"))
async def control_clearall(callback: CallbackQuery):
    admin = await _cb_admin(callback)
    if admin is None: return
    if not _require(admin, "sections_control"):
        await callback.answer("⛔ دسترسی نداری.", show_alert=True); return
    async with async_session() as session:
        rows=(await session.execute(select(GameRestriction).where(GameRestriction.active==True))).scalars().all()
        for r in rows: r.active=False
        await session.commit()
    await callback.answer("✅ همه محدودیت‌ها غیرفعال شد.", show_alert=True)
    await control_home(callback)

@router.callback_query(F.data.startswith("adm:u:titled:"))
async def titled_users_cb(callback: CallbackQuery):
    admin = await _cb_admin(callback)
    if admin is None: return
    if not _require(admin, "users"):
        await callback.answer("⛔ دسترسی نداری.", show_alert=True); return
    base,_=split_owner(callback.data); page=int(base.split(":")[3] or 0)
    async with async_session() as session:
        q=select(Player.tg_user_id, Player.name, func.count(PlayerTitle.id)).join(PlayerTitle, PlayerTitle.tg_user_id==Player.tg_user_id).group_by(Player.tg_user_id).order_by(func.count(PlayerTitle.id).desc())
        allrows=(await session.execute(q)).all()
    per=10; pages=max(1,(len(allrows)+per-1)//per); page=max(0,min(page,pages-1)); rows=allrows[page*per:(page+1)*per]
    text="🎖️ <b>کاربران لقب‌دار</b>\n\n" + ("\n".join(f"• {name or uid} — <code>{uid}</code> — {cnt} لقب" for uid,name,cnt in rows) if rows else "موردی نیست.")
    await safe_edit(callback.message, text, titled_users_kb(callback.from_user.id, rows, page, pages)); await callback.answer()

@router.callback_query(F.data.startswith("adm:u:titledcard:"))
async def titled_user_card_cb(callback: CallbackQuery):
    admin = await _cb_admin(callback)
    if admin is None: return
    if not _require(admin, "users"):
        await callback.answer("⛔ دسترسی نداری.", show_alert=True); return
    base,_=split_owner(callback.data); parts=base.split(":"); uid=int(parts[3]); page=int(parts[4])
    async with async_session() as session:
        player=await session.scalar(select(Player).where(Player.tg_user_id==uid)); rows=(await session.execute(select(PlayerTitle).where(PlayerTitle.tg_user_id==uid).order_by(PlayerTitle.granted_at.desc()).limit(30))).scalars().all()
    lines=[f"🎖️ <b>کاربر لقب‌دار</b>", f"👤 {getattr(player,'name',None) or '—'}", f"🆔 <code>{uid}</code>", ""]
    for r in rows:
        tt=TDATA.get_title(r.title_key); lines.append(f"• {(tt or {}).get('name') or r.title_key} <code>{r.title_key}</code>")
    await safe_edit(callback.message, "\n".join(lines), titled_user_actions_kb(callback.from_user.id, uid, page)); await callback.answer()

@router.callback_query(F.data.startswith("adm:theft:arrest"))
async def theft_arrest_toggle(callback: CallbackQuery):
    """🆕 مرحله ۶۷ — کلیدِ سراسری‌ِ روشن/خاموش‌ِ دستگیری در دزدی."""
    admin = await _cb_admin(callback)
    if admin is None:
        return
    if not _require(admin, "game_settings"):
        await callback.answer("⛔ دسترسی نداری.", show_alert=True)
        return
    async with async_session() as session:
        row = await session.get(GameNumberSetting, "theft.arrest_enabled")
        currently_on = True
        if row is not None and row.value is not None:
            currently_on = str(row.value).strip().lower() not in ("0", "false", "off", "no")
        new_on = not currently_on
        if row is None:
            row = GameNumberSetting(key="theft.arrest_enabled", value="1" if new_on else "0")
            session.add(row)
        else:
            row.value = "1" if new_on else "0"
        row.label = "دستگیری در دزدی (۱=روشن / ۰=خاموش)"
        row.updated_by = callback.from_user.id
        await session.commit()
    label = "🟢 روشن" if new_on else "🔴 خاموش"
    await safe_edit(
        callback.message,
        "🚔 <b>سیستمِ دستگیری در دزدی</b>\n\n"
        f"وضعیتِ فعلی: <b>{label}</b>\n\n"
        "در حالتِ خاموش، هیچ بازیکنی حینِ دزدی دستگیر و زندانی نمی‌شود.\n"
        "با زدنِ دوبارهٔ همین دکمه، وضعیت برعکس می‌شود.",
        admin_tools_settings_kb(callback.from_user.id),
    )
    await callback.answer(f"دستگیری {label}", show_alert=True)


@router.callback_query(F.data.startswith("adm:mil:barracks_cap"))
async def barracks_cap_admin(callback: CallbackQuery, state: FSMContext):
    admin=await _cb_admin(callback)
    if admin is None: return
    if not _require(admin, "game_settings"):
        await callback.answer("⛔ دسترسی نداری.", show_alert=True); return
    async with async_session() as session:
        row=await session.get(GameNumberSetting, "military.barracks_max_capacity")
        current=int(float(row.value)) if row and row.value else 2_000_000
    await state.update_data(num_key="military.barracks_max_capacity")
    await state.set_state(AdminStates.numbers_wait_value)
    await safe_edit(callback.message, f"🪖 <b>سقف ظرفیت سربازخانه</b>\nمقدار فعلی: <b>{current:,}</b> نیرو\nمقدار جدید را بفرست (حداقل ۲٬۰۰۰٬۰۰۰):", cancel_kb(callback.from_user.id))
    await callback.answer()


@router.callback_query(F.data.startswith("adm:city:income_cap"))
async def city_income_cap_admin(callback: CallbackQuery, state: FSMContext):
    admin=await _cb_admin(callback)
    if admin is None: return
    if not _require(admin, "game_settings"):
        await callback.answer("⛔ دسترسی نداری.", show_alert=True); return
    async with async_session() as session:
        row=await session.get(GameNumberSetting, "city.hourly_income_cap")
        current=int(float(row.value)) if row and row.value else 30_000_000
    await state.update_data(num_key="city.hourly_income_cap")
    await state.set_state(AdminStates.numbers_wait_value)
    await safe_edit(callback.message, f"🏙️ <b>سقف درآمد ساعتی شهر</b>\nمقدار فعلی: <b>{current:,}$</b>\nمقدار جدید را بفرست:", cancel_kb(callback.from_user.id))
    await callback.answer()




# ---------------------------------------------------------------------------
# 📐 ضریب‌های اقتصاد شهر (هزینه / درآمد / منابع) — v1.7.7.5
# ---------------------------------------------------------------------------
async def _city_balance_text(session) -> str:
    from app.services import mafia_city_service as MCS
    from app.data import mafia_city as Cdata
    snap = await MCS.refresh_city_balance_settings(session)
    return (
        "📐 <b>ضریب‌های اقتصاد شهر</b>\n\n"
        "این ضریب‌ها روی مقادیر پایه اعمال می‌شوند (بدون نیاز به ری‌استارت).\n\n"
        f"🏗️ <b>ضریب هزینه ساخت</b>: ×{snap['cost_mult']:g}\n"
        f"   کلید: <code>{Cdata.CITY_COST_MULT_KEY}</code>\n"
        f"   پیش‌فرض: ×{Cdata.DEFAULT_COST_MULT:g}\n\n"
        f"💰 <b>مقسوم‌علیه درآمد لول‌دار</b>: ÷{snap['income_div']:g}\n"
        f"   (هرچه بزرگ‌تر = درآمد کمتر؛ ۲ = نصف)\n"
        f"   کلید: <code>{Cdata.CITY_INCOME_DIV_KEY}</code>\n"
        f"   پیش‌فرض: ÷{Cdata.DEFAULT_INCOME_DIV:g}\n\n"
        f"📦 <b>ضریب قیمت منابع</b>: ×{snap['resource_price_mult']:g}\n"
        f"   کلید: <code>{Cdata.CITY_RESOURCE_PRICE_MULT_KEY}</code>\n"
        f"   پیش‌فرض: ×{Cdata.DEFAULT_RESOURCE_PRICE_MULT:g}\n\n"
        "روی هر مورد بزن و عدد جدید را بفرست."
    )


@router.callback_query(F.data.startswith("adm:city:balance"))
async def city_balance_home(callback: CallbackQuery, state: FSMContext):
    admin = await _cb_admin(callback)
    if admin is None:
        return
    if not _require(admin, "game_settings"):
        await callback.answer("⛔ دسترسی نداری.", show_alert=True)
        return
    await state.clear()
    from app.services import mafia_city_service as MCS
    async with async_session() as session:
        text = await _city_balance_text(session)
    _, owner = split_owner(callback.data)
    owner = owner or callback.from_user.id
    await safe_edit(callback.message, text, admin_city_balance_kb(owner))
    await callback.answer()


@router.callback_query(F.data.startswith("adm:city:bal:"))
async def city_balance_set_cb(callback: CallbackQuery, state: FSMContext):
    admin = await _cb_admin(callback)
    if admin is None:
        return
    if not _require(admin, "economy"):
        await callback.answer("⛔ دسترسی نداری.", show_alert=True)
        return
    from app.data import mafia_city as Cdata
    from app.services import mafia_city_service as MCS
    base, owner = split_owner(callback.data)
    # adm:city:bal:cost|income|res
    kind = base.rsplit(":", 1)[-1]
    key_map = {
        "cost": (Cdata.CITY_COST_MULT_KEY, "ضریب هزینه ساخت", "مثلاً 25 یعنی هزینه‌ها ۲۵ برابر پایه"),
        "income": (Cdata.CITY_INCOME_DIV_KEY, "مقسوم‌علیه درآمد لول‌دار", "مثلاً 2 یعنی درآمد نصف پایه؛ 1 = بدون کاهش"),
        "res": (Cdata.CITY_RESOURCE_PRICE_MULT_KEY, "ضریب قیمت منابع", "مثلاً 50 یعنی قیمت خرید منابع ۵۰ برابر پایه"),
    }
    if kind not in key_map:
        await callback.answer("گزینه نامعتبر", show_alert=True)
        return
    key, title, hint = key_map[kind]
    async with async_session() as session:
        snap = await MCS.refresh_city_balance_settings(session)
    cur = {
        "cost": snap["cost_mult"],
        "income": snap["income_div"],
        "res": snap["resource_price_mult"],
    }[kind]
    await state.set_state(AdminStates.numbers_wait_value)
    await state.update_data(num_key=key, city_bal_kind=kind)
    owner = owner or callback.from_user.id
    text = (
        f"📐 <b>{title}</b>\n\n"
        f"مقدار فعلی: <b>{cur:g}</b>\n"
        f"کلید: <code>{key}</code>\n\n"
        f"{hint}\n\n"
        "عدد جدید را بفرست (اعشار هم مجاز است، مثل 12.5)."
        + CANCEL_HINT
    )
    await safe_edit(callback.message, text, cancel_kb(owner))
    await callback.answer()


@router.callback_query(F.data.startswith("adm:brand:rep_cap"))
async def brand_rep_cap_admin(callback: CallbackQuery, state: FSMContext):
    """سقف ٪ بونس درآمد شهرت برند — مستقل از سقف شهر/سربازخانه."""
    admin = await _cb_admin(callback)
    if admin is None:
        return
    if not _require(admin, "game_settings"):
        await callback.answer("⛔ دسترسی نداری.", show_alert=True)
        return
    from app.data import branding as Bdata
    async with async_session() as session:
        row = await session.get(GameNumberSetting, Bdata.BRAND_REP_CAP_KEY)
        current = int(Bdata.BRAND_REP_CAP_DEFAULT)
        if row is not None and row.value is not None and str(row.value).strip() != "":
            try:
                current = int(float(str(row.value).strip()))
            except Exception:
                current = int(Bdata.BRAND_REP_CAP_DEFAULT)
    await state.update_data(num_key=Bdata.BRAND_REP_CAP_KEY)
    await state.set_state(AdminStates.numbers_wait_value)
    msg = (
        "🏷️ <b>سقف بونس شهرت برند</b>\n\n"
        f"کلید: <code>{Bdata.BRAND_REP_CAP_KEY}</code>\n"
        f"مقدار فعلی: <b>+{current}٪</b>\n\n"
        f"منطق: هر {Bdata.BRAND_REP_STEP:,} شهرت = +{Bdata.BRAND_REP_STEP_PCT}٪\n"
        "بونس فقط از <b>شهرت</b> است (سطح برند اثر ندارد).\n"
        "این سقف جدا از سقف درآمد شهر و ظرفیت سربازخانه است.\n\n"
        "مقدار جدید را به <b>درصد</b> بفرست (مثلاً 40 یا 60).\n"
        "0 = خاموش کردن بونس شهرت."
    )
    await safe_edit(callback.message, msg, cancel_kb(callback.from_user.id))
    await callback.answer()

@router.callback_query(F.data.startswith("adm:num:home"))
async def numbers_home(callback: CallbackQuery):
    admin=await _cb_admin(callback)
    if admin is None: return
    if not _require(admin, "game_settings"):
        await callback.answer("⛔ دسترسی نداری.", show_alert=True); return
    await safe_edit(callback.message, "🔢 <b>تنظیم عددی بازی</b>\nکلیدهای عددی را بدون تغییر کد ثبت کن. نمونه: <code>factory.raw_material_multiplier</code>", admin_numbers_kb(callback.from_user.id)); await callback.answer()

@router.callback_query(F.data.startswith("adm:num:set"))
async def numbers_set(callback: CallbackQuery, state: FSMContext):
    admin=await _cb_admin(callback)
    if admin is None: return
    if not _require(admin, "game_settings"):
        await callback.answer("⛔ دسترسی نداری.", show_alert=True); return
    await state.set_state(AdminStates.numbers_wait_key); await safe_edit(callback.message,"کلید تنظیم عددی را بفرست:", cancel_kb(callback.from_user.id)); await callback.answer()

@router.message(StateFilter(AdminStates.numbers_wait_key))
async def numbers_key_msg(message: Message, state: FSMContext):
    admin=await _guard_perm(message, state, "game_settings")
    if admin is None: return
    if await handle_cancel_word(message,state): return
    await state.update_data(num_key=(message.text or '').strip()); await state.set_state(AdminStates.numbers_wait_value); await message.answer("مقدار عددی جدید را بفرست:")

@router.message(StateFilter(AdminStates.numbers_wait_value))
async def numbers_value_msg(message: Message, state: FSMContext):
    admin=await _guard_perm(message, state, "game_settings")
    if admin is None: return
    if await handle_cancel_word(message,state): return
    val=(message.text or '').strip()
    try: float(val)
    except Exception:
        await message.answer("⚠ مقدار باید عددی باشد. دوباره:"); return
    data=await state.get_data(); key=data.get('num_key')
    async with async_session() as session:
        row=await session.get(GameNumberSetting,key)
        if row is None: session.add(GameNumberSetting(key=key,value=val,updated_by=message.from_user.id))
        else: row.value=val; row.updated_by=message.from_user.id
        await session.commit()
    await state.clear()
    # اگر ضریب اقتصاد شهر بود، کش runtime را فوری به‌روز کن
    extra = ""
    try:
        from app.data import mafia_city as _Cd
        from app.services import mafia_city_service as _MCS
        if key in {
            _Cd.CITY_COST_MULT_KEY,
            _Cd.CITY_INCOME_DIV_KEY,
            _Cd.CITY_RESOURCE_PRICE_MULT_KEY,
            _Cd.CITY_LEVEL_MULT_KEY,
            _Cd.PROD_DAILY_CAP_KEY,
            _Cd.PROD_AGG_CAP_KEY,
        }:
            async with async_session() as session:
                snap = await _MCS.refresh_city_balance_settings(session)
            extra = (
                f"\n\n📐 اقتصاد شهر الآن: "
                f"هزینه ×{snap['cost_mult']:g} | "
                f"درآمد ÷{snap['income_div']:g} | "
                f"منابع ×{snap['resource_price_mult']:g}"
            )
    except Exception:
        pass
    await message.answer(f"✅ تنظیم ثبت شد: <code>{key}</code> = <b>{val}</b>{extra}")
    await _send_panel(message, message.from_user.id, admin)

@router.callback_query(F.data.startswith("adm:num:list"))
async def numbers_list(callback: CallbackQuery):
    admin=await _cb_admin(callback)
    if admin is None: return
    if not _require(admin, "game_settings"):
        await callback.answer("⛔ دسترسی نداری.", show_alert=True); return
    async with async_session() as session:
        rows=(await session.execute(select(GameNumberSetting).order_by(GameNumberSetting.key))).scalars().all()
    text="📋 <b>تنظیمات عددی</b>\n\n" + ("\n".join(f"• <code>{r.key}</code> = <b>{r.value}</b>" for r in rows) if rows else "هنوز تنظیمی ثبت نشده.")
    await safe_edit(callback.message,text,admin_numbers_kb(callback.from_user.id)); await callback.answer()


# --------------------------- 🆕 مرحله ۴۶ — ریستِ نظامی (انتخابی یا همه) ---------------------------
@router.callback_query(F.data.startswith("adm:tl:milreset:"))
async def tl_milreset_cb(callback: CallbackQuery, state: FSMContext):
    admin = await _cb_admin(callback)
    if admin is None:
        return
    if not _require(admin, "tools"):
        await callback.answer(A.denied_text("tools"), show_alert=True)
        return
    from app.keyboards.admin_menu import military_reset_confirm_kb
    base, owner = split_owner(callback.data)
    scope = base.split(":")[3] if len(base.split(":")) > 3 else "all"
    if scope == "one":
        await state.set_state(AdminStates.tools_wait_military_reset_uid)
        await state.update_data(owner=owner)
        await safe_edit(
            callback.message,
            "⌨️ یوزرآیدیِ کاربری که می‌خواهی نیروهایش پاک شود را بفرست.\n"
            "🏷 لولِ ارتقای نیروها دست‌نخورده می‌ماند.",
            None,
        )
    else:
        await safe_edit(
            callback.message,
            "⚠️ <b>پاک‌سازیِ نیرویِ نظامیِ همه‌ی کاربران</b>\n\n"
            "فقط <b>تعدادِ نیروها</b> و صفِ پرورش صفر می‌شود.\n"
            "🏷 لولِ ارتقای نیروها دست‌نخورده می‌ماند. مطمئنی؟",
            military_reset_confirm_kb(owner, "all", 0),
        )
    await callback.answer()


@router.message(AdminStates.tools_wait_military_reset_uid)
async def tl_milreset_uid(message: Message, state: FSMContext):
    from app.keyboards.admin_menu import military_reset_confirm_kb
    data = await state.get_data()
    owner = int(data.get("owner") or message.from_user.id)
    target = _parse_int(message.text)
    if not target:
        await message.reply("❌ یوزرآیدی نامعتبر است.")
        return
    await state.clear()
    await message.answer(
        f"⚠️ نیروهایِ کاربرِ <code>{target}</code> پاک شود؟\n\n"
        "فقط <b>تعدادِ نیروها</b> و صفِ پرورش صفر می‌شود.\n"
        "🏷 لولِ ارتقای نیروها دست‌نخورده می‌ماند.",
        reply_markup=military_reset_confirm_kb(owner, "one", int(target)),
    )


@router.callback_query(F.data.startswith("adm:tl:milresetok:"))
async def tl_milresetok_cb(callback: CallbackQuery):
    admin = await _cb_admin(callback)
    if admin is None:
        return
    if not _require(admin, "tools"):
        await callback.answer(A.denied_text("tools"), show_alert=True)
        return
    # 🆕 مرحله ۶۸ — ریستِ نظامی فقط تعدادِ نیروها را صفر می‌کند.
    # قبلاً ردیفِ MilitaryUnit حذف می‌شد و با آن لولِ ارتقا هم به ۱ برمی‌گشت.
    # حالا ردیف باقی می‌ماند و فقط count = 0 می‌شود؛ پس upgrade_level دست‌نخورده می‌ماند.
    from sqlalchemy import delete as _delete, update as _update
    from app.models.military import MilitaryTrainingQueue, MilitaryUnit
    base, owner = split_owner(callback.data)
    parts = base.split(":")
    scope = parts[3] if len(parts) > 3 else "all"
    target = int(parts[4]) if len(parts) > 4 and parts[4].lstrip("-").isdigit() else 0
    async with async_session() as session:
        if scope == "one" and target:
            await session.execute(
                _update(MilitaryUnit).where(MilitaryUnit.owner_id == target).values(count=0)
            )
            await session.execute(_delete(MilitaryTrainingQueue).where(MilitaryTrainingQueue.owner_id == target))
            detail = f"military units cleared for {target} (levels kept)"
            done = f"✅ نیروهایِ کاربرِ {target} پاک شد.\n🏷 لولِ ارتقای نیروها دست‌نخورده ماند."
        else:
            await session.execute(_update(MilitaryUnit).values(count=0))
            await session.execute(_delete(MilitaryTrainingQueue))
            detail = "military units cleared for all users (levels kept)"
            done = "✅ نیروهایِ همه‌ی کاربران پاک شد.\n🏷 لولِ ارتقای نیروها دست‌نخورده ماند."
        try:
            await adm.audit(session, callback.from_user.id, "military_reset", detail=detail, commit=False)
        except Exception:
            pass
        await session.commit()
    await safe_edit(callback.message, done, admin_tools_kb(owner))
    await callback.answer(done, show_alert=True)


# ---------------------------------------------------------------------------
# 🆕 مرحله ۷۱ — تکمیلِ فوریِ صف‌های یک کاربر (ساختِ درجا)
# ---------------------------------------------------------------------------
@router.callback_query(F.data.startswith("adm:tl:qflush"))
async def tl_qflush_cb(callback: CallbackQuery, state: FSMContext):
    """🆕 مرحله ۷۱ — سه صفِ زمان‌دارِ یک کاربر را در جا تمام می‌کند."""
    admin = await _cb_admin(callback)
    if admin is None:
        return
    if not _require(admin, "tools"):
        await callback.answer(A.denied_text("tools"), show_alert=True)
        return
    _, owner = split_owner(callback.data)
    await state.set_state(AdminStates.tools_wait_qflush_uid)
    await state.update_data(owner=owner)
    await safe_edit(
        callback.message,
        "⚡️ <b>تکمیلِ فوریِ صف‌های یک کاربر</b>\n\n"
        "یوزرآیدیِ کاربر را بفرست. هر سه موردِ زیر بی‌درنگ تمام می‌شوند:\n"
        "• 🪖 صفِ پرورشِ نیرو — نیروها فوری به ارتش می‌پیوندند\n"
        "• ⬆️ صفِ ارتقایِ نیرو — لولِ هدف فوری اعمال می‌شود\n"
        "• 🏗️ ارتقایِ سربازخانه — یک لول فوری بالا می‌رود\n\n"
        "💰 هیچ پولی کم یا برگردانده نمی‌شود؛ فقط زمانِ انتطار صفر می‌شود.\n"
        "🏷 لولِ ارتقای نیروها دست‌نخورده می‌ماند.\n\n"
        "✖️ برای انصراف، همینجا بنویس: انصراف",
        None,
    )
    await callback.answer()


@router.message(AdminStates.tools_wait_qflush_uid)
async def tl_qflush_uid(message: Message, state: FSMContext):
    admin = await _guard_admin(message, state)
    if admin is None:
        return
    if await handle_cancel_word(message, state):
        return
    target = _parse_int(message.text)
    if not target:
        await message.reply("❌ یوزرآیدی نامعتبر است. دوباره بفرست یا بنویس: انصراف")
        return
    data = await state.get_data()
    owner = int(data.get("owner") or message.from_user.id)
    await state.clear()
    target = int(target)

    from datetime import datetime as _dt
    from datetime import timedelta as _td

    from app.models.military import (
        MilitaryBarracks,
        MilitaryTrainingQueue,
        MilitaryUpgradeQueue,
    )
    from app.services import military_service as _ms

    now = _dt.utcnow()
    past = now - _td(seconds=5)
    long_past = now - _td(days=3650)

    # ۱) همه‌ی ردیف‌های صف را «از قبل تمام‌شده» علامت می‌زنیم.
    async with async_session() as session:
        rows_t = (
            await session.execute(
                select(MilitaryTrainingQueue).where(MilitaryTrainingQueue.owner_id == target)
            )
        ).scalars().all()
        rows_u = (
            await session.execute(
                select(MilitaryUpgradeQueue).where(MilitaryUpgradeQueue.owner_id == target)
            )
        ).scalars().all()
        n_train_rows = len(rows_t)
        n_train_units = sum(int(r.qty or 0) for r in rows_t)
        n_upg_rows = len(rows_u)
        bar = await session.get(MilitaryBarracks, target)
        barracks_flushed = bool(bar is not None and bar.upgrading_until is not None)
        for r in rows_t:
            r.started_at = long_past
            r.ready_at = past
        for q in rows_u:
            q.started_at = past
            q.ready_at = past
        if barracks_flushed and bar is not None:
            bar.upgrading_until = past
        await session.commit()

    if not (n_train_rows or n_upg_rows or barracks_flushed):
        await message.answer(
            f"ℹ️ کاربرِ <code>{target}</code> هیچ صفِ بازی ندارد — نه پرورشِ نیرو، "
            "نه ارتقای نیرو و نه ارتقای سربازخانه."
        )
        await _send_panel(message, message.from_user.id, admin)
        return

    # ۲) ترتیب مهم است: اول سربازخانه (تا ظرفیت بالا برود)، بعد تحویلِ نیروها.
    delivered = 0
    upgraded = 0
    left_units = 0
    capacity = 0
    active_total = 0
    try:
        async with async_session() as session:
            await _ms.barracks_status(session, target)
            await session.commit()
            delivered = await _ms.settle_training(session, target, commit=True)
            upgraded = await _ms.settle_upgrades(session, target)
            left_units = sum(
                int(r.qty or 0)
                for r in (
                    await session.execute(
                        select(MilitaryTrainingQueue).where(
                            MilitaryTrainingQueue.owner_id == target
                        )
                    )
                ).scalars().all()
            )
            _b, _mx, _lv, capacity = await _ms.barracks_status(session, target)
            active_total = sum(int(x.count or 0) for x in await _ms.get_units(session, target))
            await session.commit()
    except Exception as exc:  # noqa: BLE001
        logging.exception("qflush failed for %s", target)
        await message.answer(f"❌ تکمیلِ صف‌ها ناقص ماند: <code>{exc}</code>")
        await _send_panel(message, message.from_user.id, admin)
        return

    lines = [
        "⚡️ <b>صف‌های کاربر در جا تکمیل شد</b>",
        f"🆔 <code>{target}</code>",
        "",
        f"🪖 صفِ پرورش: {n_train_rows:,} بچ ({n_train_units:,} نیرو)",
        f"✅ تحویل‌شده به ارتش: <b>{delivered:,}</b> نیرو",
        f"⬆️ ارتقایِ نیرو: {upgraded:,} مورد اعمال شد",
        f"🏗️ ارتقایِ سربازخانه: {'✅ تمام شد' if barracks_flushed else '— در جریان نبود'}",
        f"📊 ارتشِ فعلی: {active_total:,}/{int(capacity):,}",
    ]
    if left_units:
        lines += [
            "",
            f"⚠️ <b>{left_units:,}</b> نیرو در صف ماند چون ظرفیتِ سربازخانه پر شد.",
            "💡 اول سقفِ ظرفیت یا لولِ سربازخانه را بالا ببر، بعد دوباره این دکمه را بزن.",
        ]
    async with async_session() as session:
        try:
            await adm.audit(
                session,
                message.from_user.id,
                "queue_flush",
                detail=(
                    f"{target}: rows={n_train_rows} units={n_train_units} "
                    f"delivered={delivered} upgrades={upgraded} "
                    f"barracks={int(barracks_flushed)} left={left_units}"
                ),
                commit=False,
            )
            await session.commit()
        except Exception:
            pass
    await message.answer("\n".join(lines), reply_markup=admin_tools_kb(owner))


# ---------------------------------------------------------------------------
# 🆕 مرحله ۷۱ — نگهبانِ وضعیت‌های دکمه‌محورِ ادمین
# ---------------------------------------------------------------------------
# این سه وضعیت فقط با دکمه جلو می‌روند و هیچ message-handler نداشتند؛ پس اگر
# ادمین در این مرحله متن می‌نوشت، وضعیت باز می‌ماند و پنل «گیر» می‌کرد.
@router.message(
    StateFilter(
        AdminStates.broadcast_confirm,
        AdminStates.admins_wait_editperms,
        AdminStates.tools_confirm_reset,
    )
)
async def admin_button_only_state_hint(message: Message, state: FSMContext):
    if await handle_cancel_word(message, state):
        return
    await message.reply(
        "🔘 این مرحله فقط با دکمه‌های همان پیام جلو می‌رود.\n"
        "✖️ برای خروج بنویس: انصراف"
    )


# ---------------------------------------------------------------------------
# بچ ۵ — صف تایید اعطای لقب و اعلان همگانی
# ---------------------------------------------------------------------------
def _title_queue_kb(owner_id: int, rows):
    b = InlineKeyboardBuilder()
    for row in rows:
        b.button(text=f"✅ تایید #{row.id}", callback_data=with_owner(f"adm:tl:titleapprove:{row.id}", owner_id))
        b.button(text=f"✖ رد #{row.id}", callback_data=with_owner(f"adm:tl:titlereject:{row.id}", owner_id))
    b.button(text="⬅️ بازگشت", callback_data=with_owner("adm:sec:tools", owner_id))
    b.adjust(*([2] * len(rows)), 1)
    return b.as_markup()

@router.callback_query(F.data.startswith("adm:tl:titlequeue"))
async def title_queue_cb(callback: CallbackQuery):
    admin = await _cb_admin(callback)
    if admin is None: return
    if admin.role != "main":
        await callback.answer("⛔ فقط ادمین اصلی می‌تواند صفِ لقب‌ها را ببیند.", show_alert=True); return
    _, owner = split_owner(callback.data)
    async with async_session() as session:
        rows = await titles_svc.pending_approvals(session)
    if not rows:
        await safe_edit(callback.message, "✅ هیچ درخواستِ لقبِ منتظری وجود ندارد.", back_kb(owner))
    else:
        lines=["🎖️ <b>صفِ تأییدِ لقب‌ها</b>", ""]
        for row in rows:
            title=(TDATA.get_title(row.title_key) or {}).get("name", row.title_key)
            lines.append(f"#{row.id} — <b>{title}</b> برای <code>{row.tg_user_id}</code> ({row.source})")
        await safe_edit(callback.message, "\n".join(lines), _title_queue_kb(owner, rows))
    await callback.answer()

async def _broadcast_title_grant(bot, uid: int, title_name: str):
    # اطلاعیه‌ی داخل ربات برای همه‌ی بازیکنانِ ثبت‌شده؛ خطای یک کاربر مانع بقیه نمی‌شود.
    async with async_session() as session:
        player = await session.scalar(select(Player).where(Player.tg_user_id == uid))
        winner = (getattr(player, "name", None) or f"کاربر {uid}")
        recipients = (await session.execute(select(Player.tg_user_id))).scalars().all()
    text = f"🎖️ <b>اعطای لقب</b>\n{winner} لقبِ <b>«{title_name}»</b> را کسب کرد!"
    for recipient in recipients:
        try: await bot.send_message(int(recipient), text)
        except Exception: pass

@router.callback_query(F.data.startswith("adm:tl:titleapprove:"))
async def title_approve_cb(callback: CallbackQuery):
    admin = await _cb_admin(callback)
    if admin is None: return
    if admin.role != "main":
        await callback.answer("⛔ فقط ادمین اصلی.", show_alert=True); return
    base, _ = split_owner(callback.data)
    try: approval_id=int(base.rsplit(":", 1)[1])
    except ValueError:
        await callback.answer("شناسه نامعتبر است.", show_alert=True); return
    async with async_session() as session:
        row = await session.get(__import__("app.models.title", fromlist=["TitleApproval"]).TitleApproval, approval_id)
        title_name=((TDATA.get_title(row.title_key) or {}).get("name", row.title_key)) if row else ""
        ok, msg, target = await titles_svc.approve_title(session, approval_id, callback.from_user.id)
        if ok: await adm.audit(session, callback.from_user.id, "title_approved", target_id=target, detail=title_name, commit=False)
        await session.commit()
    if ok:
        await _broadcast_title_grant(callback.bot, int(target), title_name)
        await callback.answer("✅ لقب تایید و اطلاعیه همگانی ارسال شد.", show_alert=True)
    else: await callback.answer("⚠ " + msg, show_alert=True)

@router.callback_query(F.data.startswith("adm:tl:titlereject:"))
async def title_reject_cb(callback: CallbackQuery):
    admin = await _cb_admin(callback)
    if admin is None: return
    if admin.role != "main":
        await callback.answer("⛔ فقط ادمین اصلی.", show_alert=True); return
    base, _ = split_owner(callback.data)
    try: approval_id=int(base.rsplit(":", 1)[1])
    except ValueError:
        await callback.answer("شناسه نامعتبر است.", show_alert=True); return
    async with async_session() as session:
        ok=await titles_svc.reject_title(session, approval_id, callback.from_user.id)
        if ok: await adm.audit(session, callback.from_user.id, "title_rejected", detail=str(approval_id), commit=False)
        await session.commit()
    await callback.answer("رد شد." if ok else "درخواست معتبر نیست.", show_alert=not ok)

# ---------- لینک دعوت و پاداش ----------
async def _referral_panel(callback, admin):
    from app.services import referral_service as refs
    async with async_session() as session: cfg=await refs.get_config(session)
    text=("🔗 <b>پاداش لینک دعوت</b>\n\n"
          f"💰 پاداش پولی: <b>{'فعال' if cfg['cash_on'] else 'خاموش'}</b> | {cfg['cash_amount']:,}$ برای هر دعوت موفق\n"
          f"📈 بونس درآمد: <b>{'فعال' if cfg['bonus_on'] else 'خاموش'}</b> | +{cfg['bonus_pct']}٪ برای هر دعوت\n\n"
          "بونس هر دعوت فقط یک روز فعال است؛ در هر روز حداکثر دو دعوت اثر می‌گیرد و دعوت‌های بیشتر خودکار برای روزهای بعد صف می‌شوند.")
    await safe_edit(callback.message,text,referral_admin_kb(callback.from_user.id,cfg))
@router.callback_query(F.data.startswith("adm:ref:home"))
async def ref_home(callback):
    admin=await _cb_admin(callback)
    if not admin or not _require(admin, "referral"): return
    await _referral_panel(callback,admin); await callback.answer()
@router.callback_query(F.data.startswith("adm:ref:cash:toggle")|F.data.startswith("adm:ref:bonus:toggle"))
async def ref_toggle(callback):
    admin=await _cb_admin(callback)
    if not admin or not _require(admin, "referral"): return
    from app.services import referral_service as refs
    key=refs.CASH_ON if "cash" in callback.data else refs.BONUS_ON
    async with async_session() as session:
        cur=str(await adm.get_setting(session,key) or "0")=="1"; await refs.set_config(session,key,0 if cur else 1); await adm.audit(session,callback.from_user.id,"referral_toggle",detail=f"{key}={not cur}",commit=False); await session.commit()
    await _referral_panel(callback,admin); await callback.answer("ثبت شد")
@router.callback_query(F.data.startswith("adm:ref:cash:amount")|F.data.startswith("adm:ref:bonus:amount"))
async def ref_amount_start(callback,state):
    admin=await _cb_admin(callback)
    if not admin or not _require(admin, "referral"): return
    is_cash="cash" in callback.data; await state.set_state(AdminStates.referral_wait_cash if is_cash else AdminStates.referral_wait_bonus); await callback.message.answer("مبلغ پاداش پولی را به‌صورت عدد مثبت بفرست:" if is_cash else "درصد بونس درآمد را به‌صورت عدد مثبت بفرست:"); await callback.answer()
@router.message(StateFilter(AdminStates.referral_wait_cash,AdminStates.referral_wait_bonus))
async def ref_amount_save(message,state):  # v1.7.8.14: گاردِ زیر به دسترسیِ referral وصل شد
    admin=await _guard_perm(message, state, "referral")
    if not admin or not _require(admin, "referral"): return
    val=_parse_int(message.text)
    if val is None or val<=0: await message.answer("عدد مثبت بفرست:"); return
    st=await state.get_state(); from app.services import referral_service as refs
    key=refs.CASH_AMOUNT if st==AdminStates.referral_wait_cash.state else refs.BONUS_PCT
    async with async_session() as session: await refs.set_config(session,key,val); await adm.audit(session,message.from_user.id,"referral_amount",detail=f"{key}={val}",commit=False); await session.commit()
    await state.clear(); await message.answer("✅ ذخیره شد."); await _send_panel(message,message.from_user.id,admin)



# ---------------------------------------------------------------------------
# فعالیت ۲۴ ساعت اخیر بازیکنان
# ---------------------------------------------------------------------------
@router.callback_query(F.data.startswith("adm:act:recent"))
async def activity_recent_cb(callback: CallbackQuery):
    admin = await _cb_admin(callback)
    if admin is None:
        return
    if not (admin.role == "main" or _require(admin, "activity") or _require(admin, "reports")):
        await callback.answer("⛔ دسترسی نداری.", show_alert=True)
        return
    from app.services import activity_service
    _, owner = split_owner(callback.data)
    async with async_session() as session:
        rows = await activity_service.top_recent_players(session, limit=25)
    lines = ["🕘 <b>فعالیت ۲۴ ساعت اخیر بازیکنان</b>", ""]
    if not rows:
        lines.append("در ۲۴ ساعت اخیر لاگی ثبت نشده است.")
    else:
        for tg, name, cnt, amount in rows:
            lines.append(f"• <code>{tg}</code> — {name} | {cnt} فعالیت | جمع مقدار: {int(amount or 0):,}")
        lines.append("\nبرای جزئیات یک نفر از دکمه «فعالیت کاربر با آیدی» استفاده کن.")
    await safe_edit(callback.message, "\n".join(lines), back_kb(owner))
    await callback.answer()


@router.callback_query(F.data.startswith("adm:act:user"))
async def activity_user_cb(callback: CallbackQuery, state: FSMContext):
    admin = await _cb_admin(callback)
    if admin is None:
        return
    if not (admin.role == "main" or _require(admin, "activity") or _require(admin, "reports")):
        await callback.answer("⛔ دسترسی نداری.", show_alert=True)
        return
    _, owner = split_owner(callback.data)
    await state.set_state(AdminStates.activity_wait_uid)
    await safe_edit(callback.message, "🔎 یوزرآیدی کاربر را برای دیدن فعالیت ۲۴ ساعت اخیر بفرست:", cancel_kb(owner))
    await callback.answer()


@router.message(StateFilter(AdminStates.activity_wait_uid))
async def activity_user_msg(message: Message, state: FSMContext):
    admin = await _guard_perm(message, state, "users")
    if admin is None and not await adm.get_admin(message.from_user.id):
        return
    if await handle_cancel_word(message, state):
        return
    uid = _parse_int(message.text)
    if uid is None:
        await message.answer("⚠ یوزرآیدی باید عدد باشد. دوباره بفرست:")
        return
    from app.services import activity_service
    async with async_session() as session:
        rows = await activity_service.recent_for_user(session, uid, limit=40)
    lines = [f"🔎 <b>فعالیت ۲۴ ساعت اخیر</b> — <code>{uid}</code>", ""]
    if not rows:
        lines.append("برای این کاربر لاگی در ۲۴ ساعت اخیر ثبت نشده است.")
    else:
        for r in rows:
            ts = r.created_at.strftime("%Y-%m-%d %H:%M") if r.created_at else ""
            delta = f" | مقدار: {int(r.amount or 0):,}" if int(r.amount or 0) else ""
            lines.append(f"• {ts} — {r.title}{delta}")
    await state.clear()
    await message.answer("\n".join(lines))
    admin_obj = await adm.get_admin(message.from_user.id)
    if admin_obj:
        await _send_panel(message, message.from_user.id, admin_obj)


# ---------- ابزارهای ویژه: زیرمنوهای منظم ----------
@router.callback_query(F.data.startswith("adm:tools:"))
async def tools_group_cb(callback: CallbackQuery):
    admin=await _cb_admin(callback)
    if admin is None or admin.role != "main":
        await callback.answer("⛔ فقط ادمین اصلی.", show_alert=True); return
    base,_=split_owner(callback.data); group=base.rsplit(":",1)[-1]
    maps={
        "resets":("♻️ <b>ریست و نگهداری</b>",admin_tools_resets_kb),
        "settings":("⚙️ <b>تنظیمات بازی</b>",admin_tools_settings_kb),
    }
    item=maps.get(group)
    if not item: await callback.answer("گزینه نامعتبر است.",show_alert=True); return
    await safe_edit(callback.message,item[0],item[1](callback.from_user.id)); await callback.answer()

@router.callback_query(F.data.regexp(r"^adm:bulk:level:[0-9]+$"))
async def bulk_level_start(callback: CallbackQuery, state: FSMContext):
    admin=await _cb_admin(callback)
    if admin is None or not _require(admin,"bulk_levels"):
        await callback.answer(A.denied_text("bulk_levels"),show_alert=True); return
    await state.set_state(AdminStates.bulk_level_value)
    await callback.message.answer("🆙 لول جدید برای <b>همه کاربران</b> را بفرست (۱ تا ۵۰). XP همه پس از تأیید صفر می‌شود.\nبرای لغو: «انصراف»")
    await callback.answer()

@router.message(StateFilter(AdminStates.bulk_level_value))
async def bulk_level_value(message: Message, state: FSMContext):
    admin=await _guard_perm(message,state,"bulk_levels")
    if admin is None or await handle_cancel_word(message,state): return
    val=_parse_int(message.text)
    if val is None or not 1 <= val <= leveling.MAX_LEVEL:
        await message.answer(f"⚠️ یک لول بین ۱ تا {leveling.MAX_LEVEL} بفرست:"); return
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    b=InlineKeyboardBuilder(); b.button(text="✅ تأیید تغییر لول همه",callback_data=with_owner(f"adm:bulk:level:ok:{val}",message.from_user.id)); b.button(text="✖ انصراف",callback_data=with_owner("adm:sec:bulk_levels",message.from_user.id)); b.adjust(1)
    await state.clear(); await message.answer(f"⚠️ همه کاربران به لول <b>{val}</b> می‌روند و XP فعلی‌شان صفر می‌شود. تأیید می‌کنی؟",reply_markup=b.as_markup())

@router.callback_query(F.data.startswith("adm:bulk:level:ok:"))
async def bulk_level_confirm(callback: CallbackQuery):
    admin=await _cb_admin(callback)
    if admin is None or not _require(admin,"bulk_levels"):
        await callback.answer(A.denied_text("bulk_levels"),show_alert=True); return
    base,_=split_owner(callback.data)
    try: val=int(base.rsplit(":",1)[-1])
    except ValueError: await callback.answer("مقدار نامعتبر است.",show_alert=True); return
    if not 1 <= val <= leveling.MAX_LEVEL: await callback.answer("لول نامعتبر است.",show_alert=True); return
    async with async_session() as session:
        players=(await session.execute(select(Player))).scalars().all()
        for pl in players: pl.level=val; pl.xp=0
        await adm.audit(session,callback.from_user.id,"bulk_set_level",detail=f"level={val}; players={len(players)}",commit=False)
        await session.commit(); count=len(players)
    await callback.answer(f"✅ لول {count} کاربر به {val} تغییر کرد.",show_alert=True)


# ---------- مدیریت گروهی لول (دسترسی مستقل برای ادمین فرعی) ----------
def _level_ids(text: str) -> list[int] | None:
    import re
    vals=[]
    for part in re.split(r"[,\s]+", (text or "").strip()):
        if not part: continue
        value=_parse_int(part)
        if value is None or value <= 0: return None
        if value not in vals: vals.append(value)
    return vals if 1 <= len(vals) <= 50 else None

@router.callback_query(F.data.startswith("adm:lv:batch:"))
async def level_batch_start(callback: CallbackQuery, state: FSMContext):
    admin=await _cb_admin(callback)
    if admin is None or not _require(admin,"bulk_levels"):
        await callback.answer(A.denied_text("bulk_levels"),show_alert=True); return
    base,_=split_owner(callback.data); mode=base.rsplit(":",1)[-1]
    if mode not in {"set","add","sub","reset"}: await callback.answer("گزینه نامعتبر است.",show_alert=True); return
    await state.set_state(AdminStates.level_batch_ids); await state.update_data(level_mode=mode)
    verb={"set":"تعیین لول", "add":"افزایش لول", "sub":"کاهش لول", "reset":"ریست لول و XP"}[mode]
    await callback.message.answer(f"👥 {verb} چند کاربر\nیوزرآیدی کاربران را با فاصله یا ویرگول بفرست (حداکثر ۵۰ نفر).\nبرای لغو: «انصراف»")
    await callback.answer()

@router.message(StateFilter(AdminStates.level_batch_ids))
async def level_batch_ids(message: Message, state: FSMContext):
    admin=await _guard_perm(message,state,"bulk_levels")
    if admin is None or await handle_cancel_word(message,state): return
    ids=_level_ids(message.text)
    if not ids:
        await message.answer("⚠ یوزرآیدی‌های معتبر را با فاصله یا ویرگول بفرست (۱ تا ۵۰ نفر):"); return
    await state.update_data(level_ids=ids); await state.set_state(AdminStates.level_batch_amount)
    mode=(await state.get_data()).get("level_mode")
    if mode == "reset":
        await state.update_data(level_amount=1); await state.set_state(AdminStates.level_batch_confirm)
        await message.answer("⚠️ ریست لول و XP برای این کاربران آماده است. برای اجرا فقط «تایید» بنویس."); return
    prompt="لول جدید" if mode=="set" else "مقدار تغییر"
    await message.answer(f"{prompt} را بین ۱ تا {leveling.MAX_LEVEL} بفرست:")

@router.message(StateFilter(AdminStates.level_batch_amount))
async def level_batch_amount(message: Message, state: FSMContext):
    admin=await _guard_perm(message,state,"bulk_levels")
    if admin is None or await handle_cancel_word(message,state): return
    amount=_parse_int(message.text)
    if amount is None or not 1 <= amount <= leveling.MAX_LEVEL:
        await message.answer(f"⚠ عددی بین ۱ تا {leveling.MAX_LEVEL} بفرست:"); return
    data=await state.get_data(); ids=data.get("level_ids",[]); mode=data.get("level_mode")
    await state.update_data(level_amount=amount); await state.set_state(AdminStates.level_batch_confirm)
    action={"set":"تعیین", "add":"افزایش", "sub":"کاهش", "reset":"ریست"}[mode]
    await message.answer(f"⚠️ {action} لول برای <b>{len(ids)}</b> کاربر آماده است. برای اجرای نهایی فقط بنویس «تایید».\nبرای لغو: «انصراف»")

@router.message(StateFilter(AdminStates.level_batch_confirm))
async def level_batch_confirm(message: Message, state: FSMContext):
    admin=await _guard_perm(message,state,"bulk_levels")
    if admin is None or await handle_cancel_word(message,state): return
    if (message.text or "").strip() not in {"تایید","تأیید"}:
        await message.answer("برای اجرای عملیات فقط «تایید» بنویس یا «انصراف» بده:"); return
    data=await state.get_data(); ids=data.get("level_ids",[]); amount=data.get("level_amount"); mode=data.get("level_mode")
    async with async_session() as session:
        players=(await session.execute(select(Player).where(Player.tg_user_id.in_(ids)))).scalars().all()
        for p in players:
            old=int(p.level or 1)
            p.level=1 if mode=="reset" else (amount if mode=="set" else (min(leveling.MAX_LEVEL,old+amount) if mode=="add" else max(1,old-amount)))
            if mode in {"set","reset"}: p.xp=0
        await adm.audit(session,message.from_user.id,f"batch_{mode}_level",detail=f"requested={len(ids)}; changed={len(players)}; value={amount}",commit=False)
        await session.commit(); changed=len(players)
    await state.clear(); await message.answer(f"✅ عملیات لول برای <b>{changed}</b> کاربر اجرا شد."); await _send_panel(message,message.from_user.id,admin)

@router.callback_query(F.data.startswith("adm:lv:all:"))
async def level_all_delta_start(callback: CallbackQuery, state: FSMContext):
    admin=await _cb_admin(callback)
    if admin is None or not _require(admin,"bulk_levels"):
        await callback.answer(A.denied_text("bulk_levels"),show_alert=True); return
    base,_=split_owner(callback.data); mode=base.rsplit(":",1)[-1]
    if mode not in {"add","sub","reset"}: await callback.answer("گزینه نامعتبر است.",show_alert=True); return
    await state.set_state(AdminStates.level_all_delta_amount); await state.update_data(level_mode=mode)
    await callback.message.answer("⚠️ ریست لول و XP همه کاربران آماده است. برای اجرا «تایید» بنویس." if mode=="reset" else f"{'➕' if mode=='add' else '➖'} مقدار {'افزایش' if mode=='add' else 'کاهش'} لول برای همه کاربران را بفرست (۱ تا {leveling.MAX_LEVEL}).\nبرای لغو: «انصراف»")
    await callback.answer()

@router.message(StateFilter(AdminStates.level_all_delta_amount))
async def level_all_delta_amount(message: Message, state: FSMContext):
    admin=await _guard_perm(message,state,"bulk_levels")
    if admin is None or await handle_cancel_word(message,state): return
    amount=_parse_int(message.text)
    if amount is None or not 1 <= amount <= leveling.MAX_LEVEL:
        await message.answer(f"⚠ عددی بین ۱ تا {leveling.MAX_LEVEL} بفرست:"); return
    mode=(await state.get_data()).get("level_mode"); await state.update_data(level_amount=amount); await state.set_state(AdminStates.level_all_delta_confirm)
    await message.answer(f"⚠️ {'افزایش' if mode=='add' else 'کاهش'} لول <b>همه کاربران</b> به مقدار <b>{amount}</b> آماده است. برای اجرای نهایی فقط بنویس «تایید».\nبرای لغو: «انصراف»")

@router.message(StateFilter(AdminStates.level_all_delta_confirm))
async def level_all_delta_confirm(message: Message, state: FSMContext):
    admin=await _guard_perm(message,state,"bulk_levels")
    if admin is None or await handle_cancel_word(message,state): return
    if (message.text or "").strip() not in {"تایید","تأیید"}:
        await message.answer("برای اجرای عملیات فقط «تایید» بنویس یا «انصراف» بده:"); return
    data=await state.get_data(); mode=data.get("level_mode"); amount=data.get("level_amount")
    async with async_session() as session:
        players=(await session.execute(select(Player))).scalars().all()
        for p in players:
            old=int(p.level or 1); p.level=min(leveling.MAX_LEVEL,old+amount) if mode=="add" else max(1,old-amount)
        await adm.audit(session,message.from_user.id,f"all_{mode}_level",detail=f"players={len(players)}; value={amount}",commit=False)
        await session.commit(); count=len(players)
    await state.clear(); await message.answer(f"✅ {'افزایش' if mode=='add' else 'کاهش'} لول برای <b>{count}</b> کاربر اجرا شد."); await _send_panel(message,message.from_user.id,admin)


# ---------- مدیریت گروهی ثروت: نقدینگی + سپردهٔ بانک ----------
async def _apply_wealth(session, players, mode: str, amount: int):
    from app.models.worldbank import BankAccount
    ids=[p.tg_user_id for p in players]
    accounts={a.owner_id:a for a in (await session.execute(select(BankAccount).where(BankAccount.owner_id.in_(ids)))).scalars().all()} if ids else {}
    for p in players:
        acc=accounts.get(p.tg_user_id); deposit=int(acc.deposit or 0) if acc else 0; old=int(p.cash or 0)+deposit
        new=0 if mode=="reset" else (amount if mode=="set" else (old+amount if mode=="add" else max(0,old-amount)))
        p.cash=new
        if acc: acc.deposit=0
    return len(players)

@router.callback_query(F.data.startswith("adm:wealth:batch:"))
async def wealth_batch_start(callback: CallbackQuery,state:FSMContext):
    admin=await _cb_admin(callback)
    if admin is None or not _require(admin,"bulk_wealth"): await callback.answer(A.denied_text("bulk_wealth"),show_alert=True); return
    base,_=split_owner(callback.data); mode=base.rsplit(":",1)[-1]
    if mode not in {"set","add","sub","reset"}: await callback.answer("گزینه نامعتبر است.",show_alert=True); return
    await state.set_state(AdminStates.wealth_batch_ids); await state.update_data(wealth_mode=mode)
    await callback.message.answer("👥 یوزرآیدی کاربران را با فاصله یا ویرگول بفرست (حداکثر ۵۰ نفر).\nثروت شامل پول نقد و سپردهٔ بانک است.\nبرای لغو: «انصراف»"); await callback.answer()

@router.message(StateFilter(AdminStates.wealth_batch_ids))
async def wealth_batch_ids(message:Message,state:FSMContext):
    admin=await _guard_perm(message,state,"bulk_wealth")
    if admin is None or await handle_cancel_word(message,state): return
    ids=_level_ids(message.text)
    if not ids: await message.answer("⚠ یوزرآیدی‌های معتبر را با فاصله یا ویرگول بفرست (۱ تا ۵۰ نفر):"); return
    await state.update_data(wealth_ids=ids); await state.set_state(AdminStates.wealth_batch_amount)
    mode=(await state.get_data()).get("wealth_mode");
    if mode=="reset": await state.update_data(wealth_amount=0); await state.set_state(AdminStates.wealth_batch_confirm); await message.answer("⚠️ ریست دارایی این کاربران آماده است. برای اجرا «تایید» بنویس."); return
    await message.answer("ثروت جدید را بفرست:" if mode=="set" else "مقدار تغییر ثروت را بفرست:")

@router.message(StateFilter(AdminStates.wealth_batch_amount))
async def wealth_batch_amount(message:Message,state:FSMContext):
    admin=await _guard_perm(message,state,"bulk_wealth")
    if admin is None or await handle_cancel_word(message,state): return
    amount=_parse_int(message.text)
    if amount is None or amount<0: await message.answer("⚠ عدد نامنفی بفرست:"); return
    data=await state.get_data(); await state.update_data(wealth_amount=amount); await state.set_state(AdminStates.wealth_batch_confirm)
    await message.answer(f"⚠️ عملیات ثروت برای <b>{len(data.get('wealth_ids',[]))}</b> کاربر آماده است. برای اجرا فقط «تایید» بنویس.\nبرای لغو: «انصراف»")

@router.message(StateFilter(AdminStates.wealth_batch_confirm))
async def wealth_batch_confirm(message:Message,state:FSMContext):
    admin=await _guard_perm(message,state,"bulk_wealth")
    if admin is None or await handle_cancel_word(message,state): return
    if (message.text or '').strip() not in {'تایید','تأیید'}: await message.answer("برای اجرا فقط «تایید» بنویس یا «انصراف» بده:"); return
    data=await state.get_data()
    async with async_session() as session:
        players=(await session.execute(select(Player).where(Player.tg_user_id.in_(data.get('wealth_ids',[]))))).scalars().all(); count=await _apply_wealth(session,players,data['wealth_mode'],data['wealth_amount'])
        await adm.audit(session,message.from_user.id,f"batch_{data['wealth_mode']}_wealth",detail=f"players={count}; value={data['wealth_amount']}",commit=False); await session.commit()
    await state.clear(); await message.answer(f"✅ عملیات ثروت برای <b>{count}</b> کاربر اجرا شد."); await _send_panel(message,message.from_user.id,admin)

@router.callback_query(F.data.startswith("adm:wealth:all:"))
async def wealth_all_start(callback:CallbackQuery,state:FSMContext):
    admin=await _cb_admin(callback)
    if admin is None or not _require(admin,"bulk_wealth"): await callback.answer(A.denied_text("bulk_wealth"),show_alert=True); return
    base,_=split_owner(callback.data); mode=base.rsplit(":",1)[-1]
    if mode not in {"set","add","sub","reset"}: await callback.answer("گزینه نامعتبر است.",show_alert=True); return
    await state.set_state(AdminStates.wealth_all_amount); await state.update_data(wealth_mode=mode)
    await callback.message.answer("ثروت جدید برای همه را بفرست:" if mode=="set" else "مقدار تغییر ثروت برای همه را بفرست:"); await callback.answer()

@router.message(StateFilter(AdminStates.wealth_all_amount))
async def wealth_all_amount(message:Message,state:FSMContext):
    admin=await _guard_perm(message,state,"bulk_wealth")
    if admin is None or await handle_cancel_word(message,state): return
    amount=_parse_int(message.text)
    if amount is None or amount<0: await message.answer("⚠ عدد نامنفی بفرست:"); return
    await state.update_data(wealth_amount=amount); await state.set_state(AdminStates.wealth_all_confirm)
    await message.answer("⚠️ عملیات ثروت برای <b>همه کاربران</b> آماده است. برای اجرا فقط «تایید» بنویس.\nبرای لغو: «انصراف»")

@router.message(StateFilter(AdminStates.wealth_all_confirm))
async def wealth_all_confirm(message:Message,state:FSMContext):
    admin=await _guard_perm(message,state,"bulk_wealth")
    if admin is None or await handle_cancel_word(message,state): return
    if (message.text or '').strip() not in {'تایید','تأیید'}: await message.answer("برای اجرا فقط «تایید» بنویس یا «انصراف» بده:"); return
    data=await state.get_data()
    async with async_session() as session:
        players=(await session.execute(select(Player))).scalars().all(); count=await _apply_wealth(session,players,data['wealth_mode'],data['wealth_amount'])
        await adm.audit(session,message.from_user.id,f"all_{data['wealth_mode']}_wealth",detail=f"players={count}; value={data['wealth_amount']}",commit=False); await session.commit()
    await state.clear(); await message.answer(f"✅ عملیات ثروت برای <b>{count}</b> کاربر اجرا شد."); await _send_panel(message,message.from_user.id,admin)


@router.callback_query(F.data.startswith("adm:lv:reset:"))
async def level_reset_start(callback: CallbackQuery, state: FSMContext):
    admin=await _cb_admin(callback)
    if admin is None or not _require(admin,"bulk_levels"): await callback.answer(A.denied_text("bulk_levels"),show_alert=True); return
    base,_=split_owner(callback.data); scope=base.rsplit(":",1)[-1]
    if scope=="one":
        await state.set_state(AdminStates.users_wait_uid); await state.update_data(action="levelreset")
        await callback.message.answer("یوزرآیدی کاربر برای ریست لول و XP را بفرست:")
    elif scope=="batch":
        await state.set_state(AdminStates.level_batch_ids); await state.update_data(level_mode="reset")
        await callback.message.answer("یوزرآیدی کاربران را با فاصله یا ویرگول بفرست (حداکثر ۵۰ نفر):")
    elif scope=="all":
        async with async_session() as session:
            players=(await session.execute(select(Player))).scalars().all()
            for x in players: x.level=1; x.xp=0
            await adm.audit(session,callback.from_user.id,"all_reset_level_xp",detail=f"players={len(players)}",commit=False); await session.commit(); count=len(players)
        await callback.answer(f"✅ لول و XP {count} کاربر ریست شد.",show_alert=True)
    await callback.answer()

@router.callback_query(F.data.startswith("adm:news:home"))
async def news_home_cb(callback: CallbackQuery):
    admin=await _cb_admin(callback)
    if admin is None or not _require(admin,"news"): return
    await _show_news(callback,callback.from_user.id,admin); await callback.answer()

@router.callback_query(F.data.startswith("adm:bc:home"))
async def broadcast_home_cb(callback: CallbackQuery):
    admin=await _cb_admin(callback)
    if admin is None or not _require(admin,"broadcast"): return
    await safe_edit(callback.message,"📢 <b>پیام همگانی</b>",admin_broadcast_kb(callback.from_user.id)); await callback.answer()


def _assistant_user_panel_text(target_id: int, enabled: bool) -> str:
    status = "✅ فعال" if enabled else "🚫 غیرفعال"
    return (
        "👤 <b>کنترل دستیار کاربر</b>\n"
        f"کاربر: <code>{target_id}</code>\n"
        f"وضعیت دستیار اول و دوم: <b>{status}</b>\n\n"
        "این کنترل فقط برای همین کاربر اعمال می‌شود."
    )


@router.callback_query(F.data == "adm:asst:user")
async def admin_assistant_user_start(callback: CallbackQuery, state: FSMContext):
    admin = await _cb_admin(callback)
    if admin is None or not _require(admin, "assistants"):
        await callback.answer(A.denied_text("assistants"), show_alert=True); return
    await state.set_state(AdminStates.assistant_user_wait)
    await safe_edit(callback.message, "👤 یوزرآیدی عددی کاربر را برای فعال/غیرفعال‌کردن دستیارها بفرست:", cancel_kb(callback.from_user.id))
    await callback.answer()


@router.message(StateFilter(AdminStates.assistant_user_wait))
async def admin_assistant_user_receive(message: Message, state: FSMContext):
    admin = await _guard_perm(message, state, "assistants")
    if admin is None: return
    if await handle_cancel_word(message, state): return
    target_id = _parse_int(message.text)
    if target_id is None:
        await message.answer("⚠️ یوزرآیدی عددی معتبر بفرست:"); return
    async with async_session() as session:
        player = (await session.execute(select(Player).where(Player.tg_user_id == target_id))).scalar_one_or_none()
        if player is None:
            await message.answer("⚠️ کاربری با این یوزرآیدی پیدا نشد."); return
        rule = await session.scalar(select(GameRestriction.id).where(
            GameRestriction.active == True,
            GameRestriction.section == "assistant",
            GameRestriction.tg_user_id == target_id,
        ))
    await state.clear()
    enabled = rule is None
    await message.answer(_assistant_user_panel_text(target_id, enabled), reply_markup=admin_assistant_user_kb(message.from_user.id, target_id, enabled))


@router.callback_query(F.data.startswith("adm:asst:usertog:"))
async def admin_assistant_user_toggle(callback: CallbackQuery):
    admin = await _cb_admin(callback)
    if admin is None or not _require(admin, "assistants"):
        await callback.answer(A.denied_text("assistants"), show_alert=True); return
    base, _ = split_owner(callback.data)
    target_id = _parse_int(base.rsplit(":", 1)[-1])
    if target_id is None:
        await callback.answer("کاربر نامعتبر است.", show_alert=True); return
    async with async_session() as session:
        player = (await session.execute(select(Player).where(Player.tg_user_id == target_id))).scalar_one_or_none()
        if player is None:
            await callback.answer("کاربر پیدا نشد.", show_alert=True); return
        rules = (await session.execute(select(GameRestriction).where(
            GameRestriction.active == True,
            GameRestriction.section == "assistant",
            GameRestriction.tg_user_id == target_id,
        ))).scalars().all()
        if rules:
            for rule in rules:
                rule.active = False
            enabled = True
        else:
            session.add(GameRestriction(section="assistant", tg_user_id=target_id, reason="admin assistant user toggle", created_by=callback.from_user.id))
            enabled = False
        await adm.audit(session, callback.from_user.id, "assistant_user_toggle", detail=f"uid={target_id} enabled={enabled}", commit=False)
        await session.commit()
    await safe_edit(callback.message, _assistant_user_panel_text(target_id, enabled), admin_assistant_user_kb(callback.from_user.id, target_id, enabled))
    await callback.answer("✅ دستیارهای کاربر فعال شدند." if enabled else "🚫 دستیارهای کاربر غیرفعال شدند.")


@router.callback_query(F.data.startswith("adm:asst:"))
async def admin_assistant_control(callback: CallbackQuery):
    admin=await _cb_admin(callback)
    if admin is None or not _require(admin,"assistants"):
        await callback.answer(A.denied_text("assistants"),show_alert=True); return
    base,_=split_owner(callback.data); which=base.rsplit(":",1)[-1]
    if which not in {"first","second"}: await callback.answer("گزینه نامعتبر است.",show_alert=True); return
    key="assistant_first_enabled" if which=="first" else "assistant_second_enabled"
    async with async_session() as session:
        current=str(await adm.get_setting(session,key) or "1") != "0"
        await adm.set_setting(session,key,"0" if current else "1",commit=False)
        await adm.audit(session,callback.from_user.id,"assistant_toggle",detail=f"{which}={not current}",commit=False); await session.commit()
    first_on = (not current) if which=="first" else str(await adm.get_setting(session,"assistant_first_enabled") or "1") != "0"
    second_on = (not current) if which=="second" else str(await adm.get_setting(session,"assistant_second_enabled") or "1") != "0"
    await safe_edit(callback.message,"🤖 <b>کنترل دستیارها</b>\nفعال/غیرفعال‌کردن، محدودیت سراسری را برای همه کاربران اعمال می‌کند.",admin_assistants_kb(callback.from_user.id,first_on,second_on)); await callback.answer("ثبت شد")


# ---------- ریست وام‌ها (اقتصاد) ----------
@router.callback_query(F.data.startswith("adm:loan:"))
async def loan_reset_start(callback: CallbackQuery, state: FSMContext):
    admin=await _cb_admin(callback)
    if admin is None or not _require(admin,"economy"): await callback.answer(A.denied_text("economy"),show_alert=True); return
    base,_=split_owner(callback.data); scope=base.rsplit(":",1)[-1]
    if scope=="all":
        await state.update_data(loan_scope="all",loan_targets=[]); await state.set_state(AdminStates.loan_reset_confirm)
        await callback.message.answer("⚠️ ریست وام همه کاربران آماده است. برای اجرا «تایید» بنویس.")
    else:
        await state.update_data(loan_scope=scope); await state.set_state(AdminStates.loan_reset_targets)
        await callback.message.answer("یوزرآیدی کاربر را بفرست:" if scope=="one" else "یوزرآیدی کاربران را با فاصله یا ویرگول بفرست (حداکثر ۵۰ نفر):")
    await callback.answer()

@router.message(StateFilter(AdminStates.loan_reset_targets))
async def loan_reset_targets(message: Message, state: FSMContext):
    admin=await _guard_perm(message,state,"economy")
    if admin is None or await handle_cancel_word(message,state): return
    data=await state.get_data(); scope=data.get("loan_scope")
    ids=[_parse_int(message.text)] if scope=="one" else _level_ids(message.text)
    if not ids or any(x is None or x<=0 for x in ids): await message.answer("⚠ یوزرآیدی معتبر بفرست:"); return
    await state.update_data(loan_targets=ids); await state.set_state(AdminStates.loan_reset_confirm)
    await message.answer(f"⚠️ ریست وام {len(ids)} کاربر آماده است. برای اجرا «تایید» بنویس.")

@router.message(StateFilter(AdminStates.loan_reset_confirm))
async def loan_reset_confirm(message: Message, state: FSMContext):
    admin=await _guard_perm(message,state,"economy")
    if admin is None or await handle_cancel_word(message,state): return
    if (message.text or '').strip() not in {'تایید','تأیید'}: await message.answer("برای اجرا «تایید» یا برای لغو «انصراف» بنویس."); return
    from app.models.worldbank import BankAccount
    data=await state.get_data()
    async with async_session() as session:
        q=select(BankAccount) if data.get('loan_scope')=='all' else select(BankAccount).where(BankAccount.owner_id.in_(data.get('loan_targets',[])))
        rows=(await session.execute(q)).scalars().all()
        for row in rows: row.loan_principal=0; row.loan_at=None
        await adm.audit(session,message.from_user.id,'reset_loans',detail=f"accounts={len(rows)}",commit=False); await session.commit(); count=len(rows)
    await state.clear(); await message.answer(f"✅ وام {count} حساب ریست شد."); await _send_panel(message,message.from_user.id,admin)

# ---------- تغییر لول نیروها (ابزار ویژه) ----------
@router.callback_query(F.data.startswith("adm:tl:millevel"))
async def military_level_start(callback: CallbackQuery, state: FSMContext):
    admin=await _cb_admin(callback)
    if admin is None or not _require(admin,'tools'): await callback.answer(A.denied_text('tools'),show_alert=True); return
    await state.set_state(AdminStates.tools_wait_military_level_uid); await callback.message.answer("یوزرآیدی کاربر را بفرست:"); await callback.answer()

@router.message(StateFilter(AdminStates.tools_wait_military_level_uid))
async def military_level_uid(message: Message,state:FSMContext):
    admin=await _guard_perm(message,state,'tools')
    if admin is None or await handle_cancel_word(message,state): return
    uid=_parse_int(message.text)
    if not uid or uid<=0: await message.answer("یوزرآیدی معتبر بفرست:"); return
    await state.update_data(mil_level_uid=uid); await state.set_state(AdminStates.tools_wait_military_level_value); await message.answer("لول جدید همه نیروهای این کاربر را بفرست (۰ تا ۲۰):")

@router.message(StateFilter(AdminStates.tools_wait_military_level_value))
async def military_level_value(message: Message,state:FSMContext):
    admin=await _guard_perm(message,state,'tools')
    if admin is None or await handle_cancel_word(message,state): return
    level=_parse_int(message.text); data=await state.get_data(); uid=data.get('mil_level_uid')
    if level is None or not 0<=level<=20: await message.answer("لول بین ۰ تا ۲۰ بفرست:"); return
    from app.models.military import MilitaryUnit, MilitaryUpgradeQueue
    async with async_session() as session:
        rows=(await session.execute(select(MilitaryUnit).where(MilitaryUnit.owner_id==uid))).scalars().all()
        for row in rows: row.upgrade_level=level
        await session.execute(__import__('sqlalchemy').delete(MilitaryUpgradeQueue).where(MilitaryUpgradeQueue.owner_id==uid))
        await adm.audit(session,message.from_user.id,'set_military_level',target_id=uid,detail=f"level={level}; units={len(rows)}",commit=False); await session.commit(); count=len(rows)
    await state.clear(); await message.answer(f"✅ لول {count} نوع نیروی کاربر به {level} تغییر کرد."); await _send_panel(message,message.from_user.id,admin)


# ============================================================================
# 🆕 v1.7.2 — حذف کامل کاربر / روشن‌خاموش رنکینگ / بکاپ دیتابیس
# ============================================================================
@router.callback_query(F.data.startswith("adm:tl:deleteok:"))
async def tl_delete_ok_cb(callback: CallbackQuery, state: FSMContext):
    admin = await _cb_admin(callback)
    if admin is None:
        return
    if not _require(admin, "tools"):
        await callback.answer(A.denied_text("tools"), show_alert=True)
        return
    base, owner = split_owner(callback.data)
    target = _parse_int(base.split("adm:tl:deleteok:", 1)[1])
    if target is None:
        await callback.answer("❗ یوزرآیدی نامعتبر است.", show_alert=True)
        return
    async with async_session() as session:
        ok, text = await adm.delete_player(session, target, commit=False)
        if ok:
            await adm.audit(session, callback.from_user.id, "delete_player", target_id=target, commit=False)
        await session.commit()
    await state.clear()
    await safe_edit(callback.message, text, admin_tools_resets_kb(owner))
    await callback.answer("🗑️ انجام شد." if ok else "⚠ کاربر پیدا نشد.", show_alert=True)


@router.callback_query(F.data.startswith("adm:tl:delete") & ~F.data.startswith("adm:tl:deleteok"))
async def tl_delete_cb(callback: CallbackQuery, state: FSMContext):
    admin = await _cb_admin(callback)
    if admin is None:
        return
    if not _require(admin, "tools"):
        await callback.answer(A.denied_text("tools"), show_alert=True)
        return
    _, owner = split_owner(callback.data)
    await state.set_state(AdminStates.tools_wait_delete_uid)
    await safe_edit(
        callback.message,
        "🗑️ <b>حذف کامل کاربر از دیتابیس</b>\n\n"
        "یوزرآیدی را بفرست. خودِ بازیکن + همه‌ی داده‌هایش (از جمله رکورد دعوت) پاک می‌شود\n"
        "تا بتواند دوباره با لینک دعوت /start بزند و بونس تست شود.\n\n"
        "⚠️ با «ریست کامل» فرق دارد: ریست بازیکن را نگه می‌دارد؛ حذف او را از DB برمی‌دارد.",
        cancel_kb(owner),
    )
    await callback.answer()


@router.message(StateFilter(AdminStates.tools_wait_delete_uid))
async def tl_delete_uid_msg(message: Message, state: FSMContext):
    admin = await _guard_perm(message, state, "tools")
    if admin is None:
        return
    if await handle_cancel_word(message, state):
        return
    target = _parse_int(message.text)
    if target is None:
        await message.answer("⚠ یوزرآیدی باید عدد باشد. دوباره بفرست:")
        return
    async with async_session() as session:
        pl = (await session.execute(select(Player).where(Player.tg_user_id == target))).scalar_one_or_none()
    if pl is None:
        await message.answer("⚠ کاربری با این یوزرآیدی در بازی نیست. یکی دیگر بفرست:")
        return
    await state.set_state(AdminStates.tools_confirm_delete)
    await state.update_data(delete_uid=target)
    await message.answer(
        f"⚠️ مطمئنی می‌خواهی کاربر زیر را <b>کاملاً از دیتابیس حذف</b> کنی؟\n"
        f"بعد از حذف می‌تواند دوباره ثبت‌نام/دعوت شود.\n\n"
        f"🆔 <code>{target}</code>\n"
        f"👤 {pl.name}\n"
        f"🆙 لول: {pl.level} — 💰 پول: {int(pl.cash or 0):,}$",
        reply_markup=tools_delete_confirm_kb(message.from_user.id, target),
    )


async def _rankvis_panel(callback, admin):
    from app.services import ranking as R
    async with async_session() as session:
        vis = await adm.get_rank_visibility(session)
    text = (
        "🏆 <b>روشن/خاموش گزینه‌های رنکینگ</b>\n\n"
        "هر گزینه‌ای که خاموش شود، در منوی رنکینگ بازیکن‌ها <b>اصلاً دیده نمی‌شود</b>.\n"
        "✅ = روشن | 🚫 = خاموش"
    )
    await safe_edit(callback.message, text, rank_visibility_kb(callback.from_user.id, vis, R.CATEGORIES))


@router.callback_query(F.data.startswith("adm:rankvis:home"))
async def rankvis_home(callback: CallbackQuery):
    admin = await _cb_admin(callback)
    if admin is None:
        return
    if not _require(admin, "ranking_ctrl"):
        await callback.answer(A.denied_text("ranking_ctrl"), show_alert=True)
        return
    await _rankvis_panel(callback, admin)
    await callback.answer()


@router.callback_query(F.data.startswith("adm:rankvis:tog:"))
async def rankvis_tog(callback: CallbackQuery):
    admin = await _cb_admin(callback)
    if admin is None:
        return
    if not _require(admin, "ranking_ctrl"):
        await callback.answer(A.denied_text("ranking_ctrl"), show_alert=True)
        return
    base, _ = split_owner(callback.data)
    code = base.split("adm:rankvis:tog:", 1)[1].strip()
    if not code:
        await callback.answer("نامعتبر", show_alert=True)
        return
    async with async_session() as session:
        vis = await adm.get_rank_visibility(session)
        cur = bool(vis.get(code, True))
        await adm.set_rank_visibility(session, code, not cur, commit=False)
        await adm.audit(session, callback.from_user.id, "rank_visibility", detail=f"{code}={not cur}", commit=False)
        await session.commit()
    await _rankvis_panel(callback, admin)
    await callback.answer("ثبت شد")


async def _backup_panel(callback):
    async with async_session() as session:
        cfg = await adm.get_backup_settings(session)
    ch = cfg.get("channel_id")
    title = cfg.get("channel_title") or ""
    hours = int(cfg.get("interval_hours") or 0)
    lines = [
        "💾 <b>بکاپ دیتابیس</b>\n",
        f"📡 کانال: <b>{title or ch or 'تنظیم نشده'}</b>",
        f"⏱️ فاصله خودکار: <b>{(str(hours) + ' ساعت') if hours > 0 else 'خاموش'}</b>",
        "",
        "• کانال را با فوروارد پیام / آیدی عددی تنظیم کن (ربات باید ادمین باشد).",
        "• بکاپ فوری هم به کانال و هم به همین چت ادمین با فرمت <code>.db</code> ارسال می‌شود.",
    ]
    await safe_edit(callback.message, "\n".join(lines), backup_admin_kb(callback.from_user.id, cfg))


@router.callback_query(F.data.startswith("adm:backup:home"))
async def backup_home(callback: CallbackQuery):
    admin = await _cb_admin(callback)
    if admin is None:
        return
    if not _require(admin, "backup"):
        await callback.answer(A.denied_text("backup"), show_alert=True)
        return
    await _backup_panel(callback)
    await callback.answer()


@router.callback_query(F.data.startswith("adm:backup:channel"))
async def backup_channel_cb(callback: CallbackQuery, state: FSMContext):
    admin = await _cb_admin(callback)
    if admin is None:
        return
    if not _require(admin, "backup"):
        await callback.answer(A.denied_text("backup"), show_alert=True)
        return
    _, owner = split_owner(callback.data)
    await state.set_state(AdminStates.backup_wait_channel)
    await safe_edit(
        callback.message,
        "📡 <b>تعیین کانال بکاپ</b>\n\n"
        "۱) ربات را ادمین کانال کن.\n"
        "۲) یکی از این‌ها را بفرست:\n"
        "   • فوروارد یک پیام از کانال\n"
        "   • آیدی عددی مثل <code>-1001234567890</code>\n"
        "   • لینک t.me/c/...",
        cancel_kb(owner),
    )
    await callback.answer()


@router.message(StateFilter(AdminStates.backup_wait_channel))
async def backup_channel_msg(message: Message, state: FSMContext):
    admin = await _guard_admin(message, state)
    if admin is None:
        return
    if await handle_cancel_word(message, state):
        return
    chat_id = None
    title = None
    if message.forward_from_chat is not None:
        chat_id = message.forward_from_chat.id
        title = message.forward_from_chat.title
    else:
        chat_id = adm.parse_channel_id_from_text(message.text)
    if chat_id is None:
        await message.answer("⚠ کانال تشخیص داده نشد. دوباره بفرست:")
        return
    try:
        chat = await message.bot.get_chat(chat_id)
        title = title or chat.title
        me = await message.bot.get_me()
        member = await message.bot.get_chat_member(chat_id, me.id)
        if member.status not in ("administrator", "creator"):
            await message.answer("⚠ ربات ادمین این کانال نیست.")
            return
    except Exception as e:
        log.warning("backup channel validation failed: %s", e)
        await message.answer("⚠ دسترسی به کانال ممکن نشد. ادمین بودن ربات را چک کن.")
        return
    async with async_session() as session:
        await adm.set_backup_channel(session, chat_id, title, commit=False)
        await adm.audit(session, message.from_user.id, "set_backup_channel", target_id=chat_id, detail=title, commit=False)
        await session.commit()
    await state.clear()
    await message.answer(f"✅ کانال بکاپ تنظیم شد: <b>{title or chat_id}</b>")
    # show panel again via fake callback-like edit not available; send keyboard
    async with async_session() as session:
        cfg = await adm.get_backup_settings(session)
    await message.answer("💾 پنل بکاپ:", reply_markup=backup_admin_kb(message.from_user.id, cfg))


@router.callback_query(F.data.startswith("adm:backup:chclear"))
async def backup_chclear(callback: CallbackQuery):
    admin = await _cb_admin(callback)
    if admin is None:
        return
    async with async_session() as session:
        await adm.clear_backup_channel(session, commit=False)
        await adm.audit(session, callback.from_user.id, "clear_backup_channel", commit=False)
        await session.commit()
    await _backup_panel(callback)
    await callback.answer("🗑 کانال بکاپ حذف شد.", show_alert=True)


@router.callback_query(F.data.startswith("adm:backup:hours"))
async def backup_hours_cb(callback: CallbackQuery, state: FSMContext):
    admin = await _cb_admin(callback)
    if admin is None:
        return
    _, owner = split_owner(callback.data)
    await state.set_state(AdminStates.backup_wait_hours)
    await safe_edit(
        callback.message,
        "⏱️ <b>فاصله بکاپ خودکار</b>\n\n"
        "تعداد ساعت را به‌صورت عدد بفرست (مثلاً 6 یا 24).\n"
        "عدد <b>0</b> = خاموش کردن بکاپ خودکار.",
        cancel_kb(owner),
    )
    await callback.answer()


@router.message(StateFilter(AdminStates.backup_wait_hours))
async def backup_hours_msg(message: Message, state: FSMContext):
    admin = await _guard_admin(message, state)
    if admin is None:
        return
    if await handle_cancel_word(message, state):
        return
    hours = _parse_int(message.text)
    if hours is None or hours < 0 or hours > 24 * 30:
        await message.answer("⚠ عدد ساعت معتبر بفرست (0 تا 720):")
        return
    async with async_session() as session:
        await adm.set_backup_interval_hours(session, hours, commit=False)
        await adm.audit(session, message.from_user.id, "set_backup_interval", detail=str(hours), commit=False)
        await session.commit()
        cfg = await adm.get_backup_settings(session)
    await state.clear()
    await message.answer(
        f"✅ فاصله بکاپ خودکار: {'خاموش' if hours == 0 else str(hours) + ' ساعت'}",
        reply_markup=backup_admin_kb(message.from_user.id, cfg),
    )


@router.callback_query(F.data.startswith("adm:backup:now"))
async def backup_now_cb(callback: CallbackQuery):
    admin = await _cb_admin(callback)
    if admin is None:
        return
    if not _require(admin, "backup"):
        await callback.answer(A.denied_text("backup"), show_alert=True)
        return
    await callback.answer("⏳ در حال ساخت بکاپ…")
    from app.services import backup_service
    async with async_session() as session:
        cfg = await adm.get_backup_settings(session)
    targets = [callback.from_user.id]
    ch = cfg.get("channel_id")
    if ch:
        targets.append(int(ch))
    ok, msg = await backup_service.send_backup(
        callback.bot,
        to_chat_ids=targets,
        caption="⚡️ بکاپ فوری دیتابیس (ادمین‌مود)",
    )
    async with async_session() as session:
        await adm.audit(session, callback.from_user.id, "backup_now", detail=msg[:200], commit=True)
    try:
        await callback.message.answer(msg)
    except Exception:
        pass


# ===========================================================================
# 🔒 جوین اجباری کانال‌ها (v1.7.7.3)
# ===========================================================================
def _fj_member_is_admin(status) -> bool:
    s = str(getattr(status, "value", status) or "").lower()
    return s in {"administrator", "creator"}


def _fj_extract_channel_ref(message: Message):
    chat_id = None
    title = None
    username = None
    invite_hint = None
    ffc = getattr(message, "forward_from_chat", None)
    if ffc is not None:
        try:
            chat_id = int(ffc.id)
        except Exception:
            chat_id = None
        title = getattr(ffc, "title", None)
        username = getattr(ffc, "username", None)
    if chat_id is None:
        origin = getattr(message, "forward_origin", None)
        if origin is not None:
            ch = getattr(origin, "chat", None)
            if ch is not None:
                try:
                    chat_id = int(ch.id)
                except Exception:
                    chat_id = None
                title = getattr(ch, "title", None) or title
                username = getattr(ch, "username", None) or username
    # 🐞 v1.7.8.13 — اگر کانال از روی «فوروارد» شناسایی شده، دیگر متنِ خودِ
    # پستِ فورواردشده را تفسیر نکن. قبلاً اگر متنِ پست داخلش لینکِ t.me یا
    # لینکِ دعوت داشت (که خیلی رایج است، مثلاً تبلیغ یا امضای کانال)،
    # همان لینک به‌عنوان یوزرنیم/لینکِ دعوتِ کانال ذخیره می‌شد و دکمهٔ
    # جوین کاربر را به کانالِ اشتباهی می‌برد.
    forwarded = chat_id is not None
    txt = (message.text or message.caption or "").strip()
    if txt and not forwarded:
        low = txt.lower()
        if "t.me/+" in low or "joinchat/" in low or "t.me/joinchat" in low:
            invite_hint = txt.split()[0] if txt.split() else txt
        chat_id = adm.parse_channel_id_from_text(txt)
        if txt.startswith("@"):
            username = txt.lstrip("@").split()[0]
        elif "t.me/" in low and invite_hint is None:
            part = txt.split("t.me/", 1)[-1].split("?")[0].strip("/")
            if part and not part.startswith("c/") and not part.startswith("+") and "joinchat" not in part:
                un = part.split("/")[0].lstrip("@")
                if un and not un.isdigit():
                    username = un
    return chat_id, title, username, invite_hint


async def _fj_send(target, text: str, kb=None) -> None:
    """همیشه پیام را برسان — اول ادیت، وگرنه پیام جدید."""
    msg = getattr(target, "message", None)
    if msg is None and hasattr(target, "answer") and hasattr(target, "chat"):
        msg = target
    if msg is not None:
        ok = False
        try:
            ok = await safe_edit(msg, text, kb)
        except Exception:
            ok = False
        if ok:
            return
        try:
            await msg.answer(text, reply_markup=kb, disable_web_page_preview=True)
            return
        except Exception:
            pass
    try:
        bot = getattr(target, "bot", None)
        uid = getattr(getattr(target, "from_user", None), "id", None)
        if bot and uid:
            await bot.send_message(uid, text, reply_markup=kb, disable_web_page_preview=True)
    except Exception:
        pass


async def _show_force_join(callback_or_msg, owner_id: int, edit: bool = True):
    from app.services import force_join as FJ
    async with async_session() as session:
        enabled = await FJ.is_enabled(session)
        channels = await FJ.list_channels(session)
    lines = ["🔒 <b>جوین اجباری کانال</b>", ""]
    lines.append("وضعیت: <b>" + ("🟢 روشن" if enabled else "⚪ خاموش") + "</b>")
    if not channels:
        lines.append("هنوز کانالی ثبت نشده.")
    else:
        lines.append(f"تعداد کانال: <b>{len(channels)}</b>")
        lines.append("روی هر کانال بزن تا عمومی/خصوصی/حذف را تنظیم کنی.")
        for i, ch in enumerate(channels, 1):
            mode = FJ.link_mode_label(ch)
            lines.append(f"{i}) <b>{ch.get('title') or ch.get('id')}</b> — {mode}")
            lines.append(f"   <code>{ch.get('id')}</code>")
    lines += [
        "",
        "کاربر غیرعضو تا عضویت از ربات استفاده نمی‌کند.",
        "در گروه فقط به بازیکن‌ها (هر ۳۰ دقیقه یک‌بار) یادآوری می‌شود.",
        "ربات باید در کانال��ها <b>ادمین</b> باشد.",
    ]
    text = "\n".join(lines)
    kb = admin_force_join_kb(owner_id, enabled, channels)
    await _fj_send(callback_or_msg, text, kb)


async def _show_force_join_channel(callback, owner_id: int, chat_id: int):
    from app.services import force_join as FJ
    async with async_session() as session:
        ch = await FJ.get_channel(session, chat_id)
    if not ch:
        try:
            await callback.answer("کانال پیدا نشد.", show_alert=True)
        except Exception:
            pass
        await _show_force_join(callback, owner_id)
        return
    link = FJ.channel_link(ch) or "—"
    lines = [
        "🔒 <b>تنظیم کانال جوین</b>",
        "",
        f"📢 <b>{ch.get('title') or ch.get('id')}</b>",
        f"ID: <code>{ch.get('id')}</code>",
        f"حالت لینک: <b>{FJ.link_mode_label(ch)}</b>",
    ]
    if ch.get("username"):
        lines.append(f"یوزرنیم: @{ch.get('username')}")
    lines.append(f"لینک دکمه: {link}")
    lines += [
        "",
        "🌐 عمومی = لینک t.me/username",
        "🔐 خصوصی = لینک دعوت (invite)",
        "می‌توانی لینک را دستی هم تنظیم کنی.",
    ]
    text = "\n".join(lines)
    kb = admin_force_join_channel_kb(owner_id, ch)
    await _fj_send(callback, text, kb)


@router.callback_query(F.data.startswith("adm:fj:home"))
async def fj_home_cb(callback: CallbackQuery, state: FSMContext):
    admin = await _cb_admin(callback)
    if admin is None:
        return
    if not _require(admin, "force_join"):
        await callback.answer("⛔ فقط ادمین اصلی.", show_alert=True)
        return
    await state.clear()
    _, owner = split_owner(callback.data)
    await _show_force_join(callback, owner or callback.from_user.id)
    await callback.answer()


@router.callback_query(F.data.startswith("adm:fj:on"))
async def fj_on_cb(callback: CallbackQuery):
    admin = await _cb_admin(callback)
    if admin is None:
        return
    if not _require(admin, "force_join"):
        await callback.answer("⛔ فقط ادمین اصلی.", show_alert=True)
        return
    from app.services import force_join as FJ
    async with async_session() as session:
        await FJ.set_enabled(session, True, commit=True)
    _, owner = split_owner(callback.data)
    await callback.answer("🟢 جوین اجباری روشن شد.", show_alert=True)
    await _show_force_join(callback, owner or callback.from_user.id)


@router.callback_query(F.data.startswith("adm:fj:off"))
async def fj_off_cb(callback: CallbackQuery):
    admin = await _cb_admin(callback)
    if admin is None:
        return
    if not _require(admin, "force_join"):
        await callback.answer("⛔ فقط ادمین اصلی.", show_alert=True)
        return
    from app.services import force_join as FJ
    async with async_session() as session:
        await FJ.set_enabled(session, False, commit=True)
    _, owner = split_owner(callback.data)
    await callback.answer("⚪ جوین اجباری خاموش شد.", show_alert=True)
    await _show_force_join(callback, owner or callback.from_user.id)


@router.callback_query(F.data.startswith("adm:fj:add"))
async def fj_add_cb(callback: CallbackQuery, state: FSMContext):
    admin = await _cb_admin(callback)
    if admin is None:
        return
    if not _require(admin, "force_join"):
        await callback.answer("⛔ فقط ادمین اصلی.", show_alert=True)
        return
    _, owner = split_owner(callback.data)
    owner = owner or callback.from_user.id
    await state.set_state(AdminStates.force_join_wait_ref)
    await state.update_data(fj_owner=int(owner))
    text = (
        "🔒 <b>افزودن کانال جوین اجباری</b>\n\n"
        "۱) ربات را در کانال <b>عضو و ادمین</b> کن.\n"
        "۲) یکی از این‌ها را <b>همین‌جا</b> بفرست:\n"
        "   • <b>فوروارد</b> یک پیام از داخل کانال (بهترین)\n"
        "   • آیدی <code>-100...</code>\n"
        "   • یوزرنیم <code>@channel</code> یا لینک عمومی\n"
        "   • بعداً از منوی همان کانال می‌توانی عمومی/خصوصی/لینک را تنظیم کنی\n\n"
        "⏳ منتظر پیام کانال هستم..."
        + CANCEL_HINT
    )
    # همیشه alert + پیام جدید تا ادمین متن را ببیند
    try:
        await callback.answer("کانال را فوروارد کن یا لینک/آیدی بفرست", show_alert=True)
    except Exception:
        pass
    try:
        await callback.message.answer(text, reply_markup=cancel_kb(owner), disable_web_page_preview=True)
    except Exception:
        try:
            await callback.bot.send_message(
                callback.from_user.id, text, reply_markup=cancel_kb(owner), disable_web_page_preview=True
            )
        except Exception:
            pass
    try:
        await safe_edit(callback.message, text, cancel_kb(owner))
    except Exception:
        pass


@router.message(StateFilter(AdminStates.force_join_wait_ref))
async def fj_add_ref(message: Message, state: FSMContext):
    admin = await _guard_admin(message, state)
    if admin is None:
        try:
            await message.answer("⛔ اول وارد ادمین‌مود شو، بعد کانال را بفرست.")
        except Exception:
            pass
        return
    if await handle_cancel_word(message, state):
        return
    if getattr(admin, "role", None) != "main":
        await state.clear()
        await message.answer("⛔ فقط ادمین اصلی.")
        return

    from app.services import force_join as FJ
    chat_id, title, username, invite_hint = _fj_extract_channel_ref(message)

    if chat_id is None and username:
        try:
            chat = await message.bot.get_chat("@" + str(username).lstrip("@"))
            chat_id = int(chat.id)
            title = title or getattr(chat, "title", None) or username
            username = getattr(chat, "username", None) or username
        except Exception as e:
            await message.answer(f"⚠ نتوانستم @{username} را پیدا کنم: {e}")
            return

    if chat_id is None:
        if invite_hint:
            await message.answer(
                "⚠ لینک دعوت به‌تنهایی کافی نیست.\n"
                "یک پیام از <b>داخل کانال</b> را فوروارد کن، بعد از منوی کانال لینک خصوصی را تنظیم کن."
            )
            return
        await message.answer(
            "⚠ کانال تشخیص داده نشد.\n"
            "بهترین روش: <b>فوروارد</b> یک پیام از داخل کانال."
        )
        return

    # 🐞 v1.7.8.13 — اگر این کانال قبلاً ثبت شده، لینک/حالتی که ادمین دستی
    # تنظیم کرده را دور نریز و هر بار یک لینکِ دعوتِ تازه نساز.
    async with async_session() as session:
        existing = await FJ.get_channel(session, int(chat_id))
    invite_link = invite_hint or (existing or {}).get("invite_link")
    try:
        chat = await message.bot.get_chat(chat_id)
        title = title or getattr(chat, "title", None)
        username = username or getattr(chat, "username", None)
        me = await message.bot.get_me()
        member = await message.bot.get_chat_member(chat_id, me.id)
        if not _fj_member_is_admin(getattr(member, "status", None)):
            await message.answer("⚠ ربات ادمین این کانال نیست. اول ادمین کن.")
            return
        if not invite_link:
            if username:
                invite_link = "https://t.me/" + str(username).lstrip("@")
            else:
                try:
                    inv = await message.bot.create_chat_invite_link(chat_id, name="force-join")
                    invite_link = getattr(inv, "invite_link", None)
                except Exception:
                    try:
                        inv = await message.bot.export_chat_invite_link(chat_id)
                        invite_link = inv if isinstance(inv, str) else getattr(inv, "invite_link", None)
                    except Exception:
                        invite_link = None
    except Exception as e:
        await message.answer(f"⚠ دسترسی به کانال ممکن نشد: <code>{e}</code>")
        return

    if existing and not invite_hint:
        link_mode = str(existing.get("link_mode") or "").lower() or ("public" if username else "private")
    else:
        link_mode = "public" if username else "private"
    async with async_session() as session:
        ok, msg = await FJ.add_channel(
            session,
            int(chat_id),
            title=title,
            username=username,
            invite_link=invite_link,
            link_mode=link_mode,
            commit=False,
        )
        try:
            await adm.audit(
                session,
                message.from_user.id,
                "force_join_add",
                target_id=int(chat_id),
                detail=str(title or chat_id)[:200],
                commit=False,
            )
        except Exception:
            pass
        await session.commit()

    await state.clear()
    mode_fa = "عمومی" if link_mode == "public" else "خصوصی"
    await message.answer(
        f"✅ {msg}\n"
        f"کانال: <b>{title or chat_id}</b>\n"
        f"ID: <code>{chat_id}</code>\n"
        f"حالت: <b>{mode_fa}</b>\n"
        "از لیست روی کانال بزن تا عمومی/خصوصی/لینک/حذف را تنظیم کنی."
    )
    await _show_force_join(message, message.from_user.id, edit=False)


@router.callback_query(F.data.startswith("adm:fj:ch:"))
async def fj_ch_menu_cb(callback: CallbackQuery, state: FSMContext):
    admin = await _cb_admin(callback)
    if admin is None:
        return
    if not _require(admin, "force_join"):
        await callback.answer("⛔ فقط ادمین اصلی.", show_alert=True)
        return
    await state.clear()
    base, owner = split_owner(callback.data)
    parts = base.split(":")
    try:
        cid = int(parts[3])
    except Exception:
        await callback.answer("شناسه نامعتبر", show_alert=True)
        return
    await _show_force_join_channel(callback, owner or callback.from_user.id, cid)
    await callback.answer()


@router.callback_query(F.data.startswith("adm:fj:mode:"))
async def fj_mode_cb(callback: CallbackQuery):
    admin = await _cb_admin(callback)
    if admin is None:
        return
    if not _require(admin, "force_join"):
        await callback.answer("⛔ فقط ادمین اصلی.", show_alert=True)
        return
    base, owner = split_owner(callback.data)
    parts = base.split(":")
    try:
        cid = int(parts[3])
        mode = parts[4]
    except Exception:
        await callback.answer("داده نامعتبر", show_alert=True)
        return
    from app.services import force_join as FJ
    async with async_session() as session:
        ok = await FJ.set_link_mode(session, cid, mode, commit=True)
    if not ok:
        await callback.answer("انجام نشد", show_alert=True)
        return
    await callback.answer("✅ حالت لینک ذخیره شد.")
    await _show_force_join_channel(callback, owner or callback.from_user.id, cid)


@router.callback_query(F.data.startswith("adm:fj:setlink:"))
async def fj_setlink_cb(callback: CallbackQuery, state: FSMContext):
    admin = await _cb_admin(callback)
    if admin is None:
        return
    if not _require(admin, "force_join"):
        await callback.answer("⛔ فقط ادمین اصلی.", show_alert=True)
        return
    base, owner = split_owner(callback.data)
    parts = base.split(":")
    try:
        cid = int(parts[3])
    except Exception:
        await callback.answer("شناسه نامعتبر", show_alert=True)
        return
    owner = owner or callback.from_user.id
    await state.set_state(AdminStates.force_join_wait_link)
    await state.update_data(fj_link_cid=int(cid), fj_owner=int(owner))
    text = (
        "🔗 <b>تنظیم لینک دعوت کانال</b>\n\n"
        "لینک عمومی (<code>https://t.me/username</code>) یا\n"
        "لینک خصوصی (<code>https://t.me/+....</code>) را بفرست.\n\n"
        f"کانال: <code>{cid}</code>"
        + CANCEL_HINT
    )
    try:
        await callback.answer("لینک را بفرست", show_alert=True)
    except Exception:
        pass
    try:
        await callback.message.answer(text, reply_markup=cancel_kb(owner), disable_web_page_preview=True)
    except Exception:
        await _fj_send(callback, text, cancel_kb(owner))


@router.message(StateFilter(AdminStates.force_join_wait_link))
async def fj_setlink_msg(message: Message, state: FSMContext):
    admin = await _guard_admin(message, state)
    if admin is None:
        return
    if await handle_cancel_word(message, state):
        return
    if getattr(admin, "role", None) != "main":
        await state.clear()
        return
    data = await state.get_data()
    cid = data.get("fj_link_cid")
    link = (message.text or "").strip()
    if not cid or not link or ("t.me/" not in link and not link.startswith("@")):
        await message.answer("⚠ یک لینک معتبر t.me بفرست.")
        return
    if link.startswith("@"):
        link = "https://t.me/" + link.lstrip("@")
    username = None
    mode = "private"
    if "t.me/+" not in link and "joinchat" not in link:
        part = link.split("t.me/", 1)[-1].split("?")[0].strip("/")
        if part and not part.startswith("c/"):
            username = part.split("/")[0].lstrip("@")
            mode = "public"
    from app.services import force_join as FJ
    async with async_session() as session:
        ok = await FJ.update_channel(
            session, int(cid), invite_link=link, username=username, link_mode=mode, commit=True
        )
    await state.clear()
    if not ok:
        await message.answer("⚠ کانال پیدا نشد.")
        return
    mode_fa = "عمومی" if mode == "public" else "خصوصی"
    await message.answer(f"✅ لینک ذخیره شد (حالت: {mode_fa}).")

    class _C:
        pass

    fake = _C()
    fake.message = message
    fake.from_user = message.from_user
    fake.bot = message.bot

    async def _ans(*a, **k):
        return None

    fake.answer = _ans
    await _show_force_join_channel(fake, message.from_user.id, int(cid))


@router.callback_query(F.data.startswith("adm:fj:del:"))
async def fj_del_cb(callback: CallbackQuery):
    admin = await _cb_admin(callback)
    if admin is None:
        return
    if not _require(admin, "force_join"):
        await callback.answer("⛔ فقط ادمین اصلی.", show_alert=True)
        return
    base, owner = split_owner(callback.data)
    parts = base.split(":")
    try:
        cid = int(parts[3])
    except Exception:
        await callback.answer("شناسه نامعتبر", show_alert=True)
        return
    from app.services import force_join as FJ
    async with async_session() as session:
        ok = await FJ.remove_channel(session, cid, commit=True)
    await callback.answer("🗑 حذف شد." if ok else "پیدا نشد.", show_alert=True)
    await _show_force_join(callback, owner or callback.from_user.id)



# ---------------------------------------------------------------------------
# 🆕 v1.7.8.2 — پنلِ بانک و گاوصندوق (کنترلِ اعداد از ادمین‌مود)
# ---------------------------------------------------------------------------
def _wb_key_of(kind: str):
    from app.data import worldbank as WBd
    return {
        "pct": WBd.BANK_SAFE_PCT_KEY,
        "cost1": WBd.SAFEBOX_COST_L1_KEY,
        "cost100": WBd.SAFEBOX_COST_L100_KEY,
        "cap1": WBd.SAFEBOX_CAP_L1_KEY,
        "cap100": WBd.SAFEBOX_CAP_L100_KEY,
    }.get(kind)


async def _bank_panel_text(session) -> str:
    from app.data import worldbank as WBd
    from app.services import worldbank_service as WBSv
    snap = await WBSv.refresh_bank_settings(session)
    return (
        "🏦 <b>کنترلِ بانک و گاوصندوق</b>\n\n"
        f"🛡 محافظتِ سپرده در جنگ: <b>{snap['safe_pct']}٪</b>\n"
        f"   غارت‌پذیر: {snap['lootable_pct']}٪ از سپردهٔ بیرونِ گاوصندوق\n"
        f"   پیش‌فرض: {WBd.DEFAULT_WAR_SAFE_PCT}٪\n\n"
        "💵 <b>هزینهٔ گاوصندوق</b>\n"
        f"   Lv1: <b>{snap['cost_l1']:,}$</b>\n"
        f"   Lv100: <b>{snap['cost_l100']:,}$</b>\n\n"
        "📦 <b>سقفِ گاوصندوق</b>\n"
        f"   Lv1: <b>{snap['cap_l1']:,}$</b>\n"
        f"   Lv100: <b>{snap['cap_l100']:,}$</b>\n\n"
        "یادآوری: موجودیِ خودِ گاوصندوق همیشه ۱۰۰٪ امن است؛ درصدِ بالا فقط روی سپردهٔ بیرونِ آن اثر دارد.\n\n"
        "روی هر مورد بزن و عددِ جدید را بفرست."
    )


async def _show_bank_panel(callback: CallbackQuery, owner: int, can_loan: bool) -> None:
    async with async_session() as session:
        text = await _bank_panel_text(session)
    await safe_edit(callback.message, text, admin_worldbank_kb(owner, can_loan))


@router.callback_query(F.data.startswith("adm:wb:reset"))
async def bank_reset_cb(callback: CallbackQuery, state: FSMContext):
    admin = await _cb_admin(callback)
    if admin is None:
        return
    if not _require(admin, "worldbank"):
        await callback.answer("⛔ دسترسی نداری.", show_alert=True)
        return
    await state.clear()
    from app.services import worldbank_service as WBSv
    _, owner = split_owner(callback.data)
    owner = owner or callback.from_user.id
    async with async_session() as session:
        await WBSv.reset_bank_settings(session, admin_id=callback.from_user.id)
    async with async_session() as session:
        try:
            await adm.audit(session, callback.from_user.id, "bank_settings_reset")
        except Exception:
            pass
    await _show_bank_panel(callback, owner, _require(admin, "economy"))
    await callback.answer("♻️ اعدادِ بانک به پیش‌فرض برگشت.")


@router.callback_query(F.data.startswith("adm:wb:"))
async def bank_set_cb(callback: CallbackQuery, state: FSMContext):
    admin = await _cb_admin(callback)
    if admin is None:
        return
    if not _require(admin, "worldbank"):
        await callback.answer("⛔ دسترسی نداری.", show_alert=True)
        return
    from app.data import worldbank as WBd
    from app.services import worldbank_service as WBSv
    base, owner = split_owner(callback.data)
    owner = owner or callback.from_user.id
    kind = base.rsplit(":", 1)[-1]
    key = _wb_key_of(kind)
    if not key:
        await callback.answer("گزینه نامعتبر", show_alert=True)
        return
    title, default, hint = WBd.BANK_SETTING_META[key]
    async with async_session() as session:
        snap = await WBSv.refresh_bank_settings(session)
    cur = {
        "pct": snap["safe_pct"],
        "cost1": snap["cost_l1"],
        "cost100": snap["cost_l100"],
        "cap1": snap["cap_l1"],
        "cap100": snap["cap_l100"],
    }[kind]
    await state.set_state(AdminStates.wb_wait_value)
    await state.update_data(wb_key=key, wb_kind=kind)
    text = (
        f"🏦 <b>{title}</b>\n\n"
        f"مقدار فعلی: <b>{int(cur):,}</b>\n"
        f"پیش‌فرض: {int(default):,}\n"
        f"کلید: <code>{key}</code>\n\n"
        f"{hint}\n\n"
        "عددِ جدید را بفرست (فقط عدد، بدون کاما و علامت)."
        + CANCEL_HINT
    )
    await safe_edit(callback.message, text, cancel_kb(owner))
    await callback.answer()


@router.message(StateFilter(AdminStates.wb_wait_value))
async def bank_value_msg(message: Message, state: FSMContext):
    admin = await _guard_perm(message, state, "worldbank")
    if admin is None:
        return
    if await handle_cancel_word(message, state):
        return
    raw = (message.text or "").strip().replace(",", "").replace("\u066c", "")
    try:
        val = float(raw)
    except (TypeError, ValueError):
        await message.answer("⚠ مقدار باید عددی باشد. دوباره بفرست:")
        return
    data = await state.get_data()
    key = data.get("wb_key")
    if not key:
        await state.clear()
        await message.answer("⚠ چیزی برای تغییر انتخاب نشده بود. از پنل دوباره شروع کن.")
        return
    from app.data import worldbank as WBd
    from app.services import worldbank_service as WBSv
    if key == WBd.BANK_SAFE_PCT_KEY and not (0 <= val <= 100):
        await message.answer("⚠ درصد باید بین ۰ تا ۱۰۰ باشد. دوباره بفرست:")
        return
    if key != WBd.BANK_SAFE_PCT_KEY and val < 1:
        await message.answer("⚠ این عدد باید دست‌کم ۱ باشد. دوباره بفرست:")
        return
    async with async_session() as session:
        snap = await WBSv.save_bank_setting(session, key, val, admin_id=message.from_user.id)
    async with async_session() as session:
        try:
            await adm.audit(session, message.from_user.id, "bank_setting:%s=%d" % (key, int(val)))
        except Exception:
            pass
    await state.clear()
    title = WBd.BANK_SETTING_META[key][0]
    await message.answer(
        f"✅ <b>{title}</b> روی <b>{int(val):,}</b> تنطیم شد.\n\n"
        f"🛡 محافظت سپرده: {snap['safe_pct']}٪ ـ غارت‌پذیر: {snap['lootable_pct']}٪"
    )
    await _send_panel(message, message.from_user.id, admin)

# --------------------------- 🏭 دسترسی ابرکارخانهٔ دون (v1.7.8.5) ---------------------------
@router.callback_query(F.data.startswith("adm:giga:home"))
async def giga_access_home(callback: CallbackQuery, state: FSMContext):
    admin = await _cb_admin(callback)
    if admin is None:
        return
    if not _require(admin, "game_settings"):
        await callback.answer("⛔ دسترسی نداری.", show_alert=True)
        return
    await state.set_state(AdminStates.giga_wait_uid)
    await safe_edit(callback.message, "🏭 <b>دسترسی ابرکارخانهٔ دون</b>" + chr(10) + chr(10) + "یوزرآیدیِ کاربر را بفرست:" + CANCEL_HINT, cancel_kb(callback.from_user.id))
    await callback.answer()


@router.message(StateFilter(AdminStates.giga_wait_uid))
async def giga_access_uid(message: Message, state: FSMContext):
    admin = await _guard_perm(message, state, "game_settings")
    if admin is None:
        return
    if await handle_cancel_word(message, state):
        return
    uid = _parse_int(message.text)
    if uid is None:
        await message.answer("⚠ یوزرآیدیِ عددی بفرست:")
        return
    await state.clear()
    async with async_session() as session:
        row = await session.get(GameNumberSetting, f"giga.access.{uid}")
        seen = await session.get(GameNumberSetting, f"giga.seen.{uid}")
        player = (await session.execute(select(Player).where(Player.tg_user_id == uid))).scalar_one_or_none()
        try:
            from app.services import worldbank_service as _WBS
            net = int((await _WBS.compute_net_worth(session, uid))["net_worth"])
        except Exception:
            net = 0
    mode = "پیش‌فرض" if row is None else ("✅ داده‌شده" if str(row.value).strip() == "1" else "🚫 گرفته‌شده")
    seen_txt = "بله" if (seen is not None and str(seen.value).strip() == "1") else "نه"
    name = (player.name or str(uid)) if player else str(uid)
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    b = InlineKeyboardBuilder()
    b.button(text="✅ دادن دسترسی", callback_data=with_owner(f"adm:giga:set:{uid}:1", message.from_user.id))
    b.button(text="🚫 گرفتن دسترسی", callback_data=with_owner(f"adm:giga:set:{uid}:0", message.from_user.id))
    b.button(text="♻️ حالت پیش‌فرض", callback_data=with_owner(f"adm:giga:set:{uid}:clear", message.from_user.id))
    b.button(text="↩️ بازگش��", callback_data=with_owner("adm:tools:settings", message.from_user.id))
    b.adjust(1)
    await message.answer(
        f"🏭 <b>دسترسی ابرکارخانهٔ دون</b>" + chr(10) + chr(10) +
        f"👤 کاربر: <b>{name}</b> (<code>{uid}</code>)" + chr(10) +
        f"💰 ثروتِ خالص: <b>{net:,}$</b>" + chr(10) +
        f"🔑 وضعیت: <b>{mode}</b>" + chr(10) +
        f"📌 باز کرده (زیر ۳۰۰ میلیارد): {seen_txt}",
        reply_markup=b.as_markup(),
    )


@router.callback_query(F.data.startswith("adm:giga:set:"))
async def giga_access_set(callback: CallbackQuery):
    admin = await _cb_admin(callback)
    if admin is None:
        return
    if not _require(admin, "game_settings"):
        await callback.answer("⛔ دسترسی نداری.", show_alert=True)
        return
    base, _owner = split_owner(callback.data)
    parts = base.split(":")
    try:
        uid = int(parts[3])
    except Exception:
        await callback.answer("نامعتبر", show_alert=True)
        return
    mode = parts[4] if len(parts) > 4 else "clear"
    async with async_session() as session:
        key = f"giga.access.{uid}"
        row = await session.get(GameNumberSetting, key)
        if mode == "clear":
            if row is not None:
                await session.delete(row)
        else:
            if row is None:
                row = GameNumberSetting(key=key, value=mode, label="دسترسی ابرکارخانه", updated_by=callback.from_user.id)
                session.add(row)
            else:
                row.value = mode
                row.updated_by = callback.from_user.id
        await session.commit()
    label = {"1": "✅ داده شد", "0": "🚫 گرفته شد", "clear": "♻️ به پیش‌فرض برگشت"}.get(mode, mode)
    await callback.answer(f"🏭 دسترسی کاربر {uid}: {label}", show_alert=True)


# --------------------------- 🏭 تولید و ساخت شهر (v1.7.8.5) ---------------------------
@router.callback_query(F.data.startswith("adm:cityprod:home"))
async def cityprod_home(callback: CallbackQuery, state: FSMContext):
    admin = await _cb_admin(callback)
    if admin is None:
        return
    if not _require(admin, "game_settings"):
        await callback.answer("⛔ دسترسی نداری.", show_alert=True)
        return
    from app.data import mafia_city as _Cd
    from app.services import mafia_city_service as _MCS
    async with async_session() as session:
        await _MCS.refresh_city_balance_settings(session)
    cap = _Cd.get_prod_daily_cap()
    from app.keyboards.admin_menu import admin_cityprod_kb
    text = (
        "🏭 <b>تولید و ساخت شهر</b>" + chr(10) + chr(10)
        + f"🔢 سقف تولید روزانهٔ هر واحد صنعتی: <b>{cap:,}</b> واحد/روز" + chr(10)
        + f"🏭 سقف تجمیعی (۴۰+ واحد صنعتی): <b>{_Cd.get_prod_agg_cap():,}</b> واحد/روز" + chr(10)
        + "⚡ تکمیل فوری: همهٔ ساخت‌وسازهای در جریانِ شهرِ یک کاربر را فوراً تمام می‌کند."
    )
    await safe_edit(callback.message, text, admin_cityprod_kb(callback.from_user.id))
    await callback.answer()


@router.callback_query(F.data.startswith("adm:cityprod:cap"))
async def cityprod_cap(callback: CallbackQuery, state: FSMContext):
    admin = await _cb_admin(callback)
    if admin is None:
        return
    if not _require(admin, "game_settings"):
        await callback.answer("⛔ دسترسی نداری.", show_alert=True)
        return
    from app.data import mafia_city as _Cd
    async with async_session() as session:
        row = await session.get(GameNumberSetting, _Cd.PROD_DAILY_CAP_KEY)
        cur = int(float(str(row.value))) if row and row.value else _Cd.DEFAULT_PROD_DAILY_CAP
    await state.update_data(num_key=_Cd.PROD_DAILY_CAP_KEY)
    await state.set_state(AdminStates.numbers_wait_value)
    await safe_edit(callback.message, f"🔢 <b>سقف تولید روزانهٔ هر واحد صنعتی</b>" + chr(10) + f"مقدار فعلی: <b>{cur:,}</b> واحد/روز" + chr(10) + "عدد جدید را بفرست:", cancel_kb(callback.from_user.id))
    await callback.answer()


@router.callback_query(F.data.startswith("adm:cityprod:aggcap"))
async def cityprod_aggcap(callback: CallbackQuery, state: FSMContext):
    admin = await _cb_admin(callback)
    if admin is None:
        return
    if not _require(admin, "game_settings"):
        await callback.answer("⛔ دسترسی نداری.", show_alert=True)
        return
    from app.data import mafia_city as _Cd
    async with async_session() as session:
        row = await session.get(GameNumberSetting, _Cd.PROD_AGG_CAP_KEY)
        cur = int(float(str(row.value))) if row and row.value else _Cd.DEFAULT_PROD_AGG_CAP
    await state.update_data(num_key=_Cd.PROD_AGG_CAP_KEY)
    await state.set_state(AdminStates.numbers_wait_value)
    await safe_edit(callback.message, f"🏭 <b>سقف تجمیعی تولید روزانه</b>" + chr(10) + f"برای کاربران با بیش از {int(_Cd.PROD_AGG_MIN_UNITS)} واحد صنعتی — مقدار فعلی: <b>{cur:,}</b> واحد/روز" + chr(10) + "عدد جدید را بفرست:", cancel_kb(callback.from_user.id))
    await callback.answer()


@router.callback_query(F.data.startswith("adm:cityprod:flush"))
async def cityprod_flush(callback: CallbackQuery, state: FSMContext):
    admin = await _cb_admin(callback)
    if admin is None:
        return
    if not _require(admin, "game_settings"):
        await callback.answer("⛔ دسترسی نداری.", show_alert=True)
        return
    await state.set_state(AdminStates.cityprod_wait_uid)
    await safe_edit(callback.message, "⚡ <b>تکمیل فوری ساخت‌وساز شهر</b>" + chr(10) + chr(10) + "یوزرآیدیِ کاربر را بفرست تا همهٔ ساخت‌های در جریانِ شهرش فوراً تکمیل شود:" + CANCEL_HINT, cancel_kb(callback.from_user.id))
    await callback.answer()


@router.message(StateFilter(AdminStates.cityprod_wait_uid))
async def cityprod_flush_uid(message: Message, state: FSMContext):
    admin = await _guard_perm(message, state, "game_settings")
    if admin is None:
        return
    if await handle_cancel_word(message, state):
        return
    uid = _parse_int(message.text)
    if uid is None:
        await message.answer("⚠ یوزرآیدیِ عددی بفرست:")
        return
    await state.clear()
    async with async_session() as session:
        from app.services import mafia_city_service as _MCS
        n = await _MCS.complete_all_builds(session, uid)
    await message.answer(f"✅ {n} ساخت/ارتقا برای کاربر <code>{uid}</code> فوراً تکمیل شد.")

# --------------------------- ⚽ v1.7.9.5 — خریدهای ورزشی (سرمربی) + تنظیم قیمت ---------------------------
@router.callback_query(F.data.startswith("adm:coachsales"))
async def coachsales_cb(callback: CallbackQuery, state: FSMContext):
    admin = await _cb_admin(callback)
    if admin is None:
        return
    if not _require(admin, "tools"):
        await callback.answer(A.denied_text("tools"), show_alert=True)
        return
    base, _ = split_owner(callback.data)
    parts = base.split(":")
    action = parts[2] if len(parts) >= 3 else "home"
    uid = callback.from_user.id
    from app.services import football_shop as FSHOP
    from app.data import football_coaches as FCOACH

    async with async_session() as session:
        # --- تأیید اولیه (منتظر پرداخت) ---
        if action == "ok" and len(parts) >= 4:
            rec = await FSHOP.get_purchase(session, parts[3])
            if rec is None or rec.status != FSHOP.STATUS_PENDING:
                await callback.answer("ردیف معتبر نیست یا قبلاً رسیدگی شده.", show_alert=True)
                return
            await FSHOP.set_status(session, rec, FSHOP.STATUS_AWAITING, uid)
            await session.commit()
            try:
                await callback.bot.send_message(int(rec.owner_id), f"✅ درخواست خرید <b>{rec.coach_name}</b> تأیید اولیه شد.\n💰 مبلغ {int(rec.price):,} تومان را پرداخت کن و رسید را از «🧾 خریدهای من» بفرست. کد: <code>{rec.tracking_code}</code>")
            except Exception:
                pass
            await callback.answer("تأیید شد — کاربر مطلع شد.")
            await coachsales_cb(callback.model_copy(update={"data": with_owner("adm:coachsales:home", uid)}), state)
            return
        # --- رد ---
        if action == "no" and len(parts) >= 4:
            rec = await FSHOP.get_purchase(session, parts[3])
            if rec is None:
                await callback.answer("ردیف پیدا نشد.", show_alert=True)
                return
            await FSHOP.set_status(session, rec, FSHOP.STATUS_REJECTED, uid)
            await session.commit()
            try:
                await callback.bot.send_message(int(rec.owner_id), f"❌ درخواست خرید <b>{rec.coach_name}</b> رد شد. کد: <code>{rec.tracking_code}</code>")
            except Exception:
                pass
            await callback.answer("رد شد.")
            await coachsales_cb(callback.model_copy(update={"data": with_owner("adm:coachsales:home", uid)}), state)
            return
        # --- تأیید رسید (اعمال سرمربی) ---
        if action == "paid" and len(parts) >= 4:
            rec = await FSHOP.get_purchase(session, parts[3])
            if rec is None or rec.status != FSHOP.STATUS_RECEIPT:
                await callback.answer("رسیدی برای تأیید نیست.", show_alert=True)
                return
            ok, club_name = await FSHOP.apply_coach(session, rec)
            await session.commit()
            if ok:
                try:
                    await callback.bot.send_message(int(rec.owner_id), f"🎉 سرمربی <b>{rec.coach_name}</b> (۵⭐) روی باشگاهِ «{club_name}» فعال شد! ضریب قدرت ×1.25")
                except Exception:
                    pass
                await callback.answer("✅ سرمربی اعمال شد.")
            else:
                await callback.answer(club_name, show_alert=True)
            await coachsales_cb(callback.model_copy(update={"data": with_owner("adm:coachsales:home", uid)}), state)
            return
        # --- لیست قیمت‌ها ---
        if action == "price":
            kb = InlineKeyboardBuilder()
            lines = ["💰 <b>تنظیم قیمت سرمربی‌ها</b> (تومان)", ""]
            for key in FCOACH.COACH_ORDER:
                c = FCOACH.get(key)
                price = await FSHOP.effective_price(session, key)
                kb.button(text=f"{c['name']} — {price:,}T", callback_data=with_owner(f"adm:coachsales:setp:{key}", uid))
            kb.button(text="⬅️ بازگشت", callback_data=with_owner("adm:coachsales:home", uid))
            kb.adjust(1)
            await safe_edit(callback.message, "\n".join(lines), kb.as_markup())
            await callback.answer()
            return
        # --- شروع تنظیم قیمت یک سرمربی ---
        if action == "setp" and len(parts) >= 4:
            key = parts[3]
            c = FCOACH.get(key)
            if c is None:
                await callback.answer("سرمربی نامعتبر.", show_alert=True)
                return
            await state.set_state(AdminStates.coach_price_wait)
            await state.update_data(coach_price_key=key)
            cur = await FSHOP.effective_price(session, key)
            await callback.message.answer(f"💰 قیمت جدید برای <b>{c['name']}</b> (فعلی: {cur:,} تومان) را به‌صورت عدد بفرست:\n{CANCEL_HINT}")
            await callback.answer()
            return

        # --- پنل اصلی ---
        pending = await FSHOP.pending_requests(session, FSHOP.STATUS_PENDING)
        receipts = await FSHOP.pending_requests(session, FSHOP.STATUS_RECEIPT)
        lines = [
            "⚽ <b>خریدهای ورزشی — سرمربی ۵⭐</b>", "",
            f"⏳ در انتظار تأیید: {len(pending)}  |  🧾 رسید برای تأیید: {len(receipts)}",
            "",
        ]
        kb = InlineKeyboardBuilder()
        for r in (pending + receipts)[:12]:
            tag = "🧾" if r.status == FSHOP.STATUS_RECEIPT else "⏳"
            lines.append(f"{tag} <b>{r.coach_name}</b> — {int(r.price):,}T — کاربر <code>{r.owner_id}</code> — <code>{r.tracking_code}</code>")
            if r.status == FSHOP.STATUS_PENDING:
                kb.button(text=f"✅ تأیید {r.coach_name}", callback_data=with_owner(f"adm:coachsales:ok:{r.tracking_code}", uid))
                kb.button(text=f"❌ رد", callback_data=with_owner(f"adm:coachsales:no:{r.tracking_code}", uid))
            elif r.status == FSHOP.STATUS_RECEIPT:
                kb.button(text=f"💰 تأیید رسید {r.coach_name}", callback_data=with_owner(f"adm:coachsales:paid:{r.tracking_code}", uid))
                if r.receipt_file_id:
                    try:
                        await callback.bot.send_photo(uid, r.receipt_file_id, caption=f"🧾 رسید {r.coach_name} — <code>{r.tracking_code}</code>")
                    except Exception:
                        pass
        if not (pending or receipts):
            lines.append("درخواستی در صف نیست. ✅")
        kb.button(text="💰 تنظیم قیمت سرمربی‌ها", callback_data=with_owner("adm:coachsales:price", uid))
        kb.button(text="⬅️ بازگشت به ابزارها", callback_data=with_owner("adm:sec:tools", uid))
        kb.adjust(1)
        await safe_edit(callback.message, "\n".join(lines), kb.as_markup())
        await callback.answer()


@router.message(AdminStates.coach_price_wait)
async def coach_price_recv(message: Message, state: FSMContext):
    if await handle_cancel_word(message, state):
        return
    admin = await _guard_perm(message, state, "tools")
    if admin is None:
        return
    raw = (message.text or "").strip().replace(",", "")
    if not raw.isdigit() or int(raw) < 0:
        await message.reply("فقط عددِ مثبت بفرست (قیمت به تومان).")
        return
    data = await state.get_data()
    key = str(data.get("coach_price_key") or "")
    from app.services import football_shop as FSHOP
    from app.data import football_coaches as FCOACH
    c = FCOACH.get(key)
    async with async_session() as session:
        await FSHOP.set_price_override(session, key, int(raw))
        await session.commit()
    await state.clear()
    await message.reply(f"✅ قیمت <b>{c['name'] if c else key}</b> روی {int(raw):,} تومان تنظیم شد.")

# --------------------------- 🧪 v1.7.9.6 — تست‌کنندگانِ بخش‌های خاموش ---------------------------
@router.callback_query(F.data.startswith("adm:ctrl:testers"))
async def ctrl_testers(callback: CallbackQuery, state: FSMContext):
    admin = await _cb_admin(callback)
    if admin is None:
        return
    if not _require(admin, "sections_control"):
        await callback.answer("⛔ دسترسی نداری.", show_alert=True)
        return
    base, _ = split_owner(callback.data)
    parts = base.split(":")
    sub = parts[3] if len(parts) >= 4 else "home"
    uid = callback.from_user.id
    import json as _json
    if sub == "del" and len(parts) >= 5:
        target = parts[4]
        async with async_session() as session:
            raw = await adm.get_setting(session, "ctrl:testers")
            try:
                lst = [int(x) for x in _json.loads(raw or "[]")]
            except Exception:
                lst = []
            lst = [x for x in lst if str(x) != str(target)]
            await adm.set_setting(session, "ctrl:testers", _json.dumps(lst), commit=True)
        await callback.answer("حذف شد.")
    elif sub == "add":
        await state.set_state(AdminStates.control_wait_testers)
        await callback.message.answer("🧪 آیدیِ عددیِ تست‌کننده‌ها را بفرست (چند نفر با فاصله/کاما):\n" + CANCEL_HINT)
        await callback.answer()
        return
    async with async_session() as session:
        raw = await adm.get_setting(session, "ctrl:testers")
        try:
            lst = [int(x) for x in _json.loads(raw or "[]")]
        except Exception:
            lst = []
    lines = [
        "🧪 <b>تست‌کنندگانِ بخش‌های خاموش</b>", "",
        "این کاربران حتی وقتی یک بخش برای همه خاموش است، می‌توانند آن را ببینند و تست کنند.", "",
    ]
    kb = InlineKeyboardBuilder()
    if lst:
        for u in lst:
            lines.append(f"• <code>{u}</code>")
            kb.button(text=f"🗑️ حذف {u}", callback_data=with_owner(f"adm:ctrl:testers:del:{u}", uid))
    else:
        lines.append("هنوز تست‌کننده‌ای نیست.")
    kb.button(text="➕ افزودن تست‌کننده", callback_data=with_owner("adm:ctrl:testers:add", uid))
    kb.button(text="⬅️ بازگشت", callback_data=with_owner("adm:ctrl:home", uid))
    kb.adjust(1)
    await safe_edit(callback.message, "\n".join(lines), kb.as_markup())
    await callback.answer()


@router.message(AdminStates.control_wait_testers)
async def ctrl_testers_add_msg(message: Message, state: FSMContext):
    admin = await _guard_perm(message, state, "sections_control")
    if admin is None:
        return
    if await handle_cancel_word(message, state):
        return
    raw = (message.text or "").replace("،", " ").replace(",", " ")
    uids = []
    for tok in raw.split():
        v = _parse_int(tok)
        if v is not None:
            uids.append(v)
    if not uids:
        await message.answer("⚠ حداقل یک آیدیِ عددیِ معتبر بفرست:")
        return
    import json as _json
    async with async_session() as session:
        cur = await adm.get_setting(session, "ctrl:testers")
        try:
            lst = [int(x) for x in _json.loads(cur or "[]")]
        except Exception:
            lst = []
        lst = sorted(set(lst) | set(uids))
        await adm.set_setting(session, "ctrl:testers", _json.dumps(lst), commit=True)
    await state.clear()
    await message.answer(f"✅ {len(uids)} تست‌کننده اضافه شد (مجموع: {len(lst)}).")

# --------------------------- ⚽ v1.7.9.7 — بازار بازیکنان (ادمین) ---------------------------
@router.callback_query(F.data.startswith("adm:pmarket"))
async def pmarket_cb(callback: CallbackQuery, state: FSMContext):
    admin = await _cb_admin(callback)
    if admin is None:
        return
    if not _require(admin, "tools"):
        await callback.answer(A.denied_text("tools"), show_alert=True)
        return
    base, _ = split_owner(callback.data)
    parts = base.split(":")
    action = parts[2] if len(parts) >= 3 else "home"
    uid = callback.from_user.id
    from app.services import football_market as FMKT
    from app.data import football_players as FP
    from app.models.football_market import FootballMarketSale

    async with async_session() as session:
        # جستجوی بازیکن برای تغییر قیمت
        if action == "search":
            await state.set_state(AdminStates.pmarket_wait_search)
            kb = InlineKeyboardBuilder()
            kb.button(text="✖ انصراف", callback_data=with_owner("adm:pmarket:price:0", uid))
            kb.adjust(1)
            await safe_edit(callback.message, "🔍 <b>جستجوی بازیکن</b>\n\nاسم (یا بخشی از اسم) بازیکن فوتبال را بفرست تا مشخصاتش بیاید و بتوانی قیمتش را تغییر بدهی:", kb.as_markup())
            await callback.answer()
            return
        # تأیید بالاترین پیشنهاد (auction تمام‌شده → awaiting_payment)
        if action == "ok" and len(parts) >= 4:
            sale = await session.get(FootballMarketSale, int(parts[3]))
            if sale is None or sale.status != "awaiting_admin":
                await callback.answer("ردیف معتبر نیست.", show_alert=True)
                return
            await FMKT.admin_approve(session, sale)
            await session.commit()
            try:
                await callback.bot.send_message(int(sale.current_candidate), f"✅ پیشنهادت برای <b>{sale.player_name}</b> تأیید شد — {FMKT.PAYMENT_MINUTES} دقیقه فرصت پرداخت {int(sale.highest_bid):,} تومان و ارسال رسید داری.")
            except Exception:
                pass
            await callback.answer("تأیید شد — نفر اول ۳۰ دقیقه مهلت پرداخت دارد.")
        # تأیید رسید → انتقال بازیکن
        elif action == "paid" and len(parts) >= 4:
            sale = await session.get(FootballMarketSale, int(parts[3]))
            if sale is None or sale.status != "receipt_check":
                await callback.answer("رسیدی برای تأیید نیست.", show_alert=True)
                return
            ok, club_name = await FMKT.admin_confirm_receipt(session, sale, int(sale.current_candidate))
            await session.commit()
            if ok:
                try:
                    await callback.bot.send_message(int(sale.current_candidate), f"🎉 بازیکن <b>{sale.player_name}</b> به باشگاهِ «{club_name}» پیوست!")
                except Exception:
                    pass
                await callback.answer("✅ بازیکن منتقل شد.")
            else:
                await callback.answer(club_name, show_alert=True)
        # رد رسید → نفر بعدی
        elif action == "no" and len(parts) >= 4:
            sale = await session.get(FootballMarketSale, int(parts[3]))
            if sale is None:
                await callback.answer("ردیف پیدا نشد.", show_alert=True)
                return
            await FMKT.admin_reject_receipt(session, sale, callback.bot)
            await session.commit()
            await callback.answer("رد شد — نفر بعدی فعال شد.")
        # لغو فروش برای امروز
        elif action == "cancel" and len(parts) >= 4:
            sale = await session.get(FootballMarketSale, int(parts[3]))
            if sale is None:
                await callback.answer("ردیف پیدا نشد.", show_alert=True)
                return
            await FMKT.admin_cancel_today(session, sale)
            await session.commit()
            await callback.answer("فروش برای امروز لغو شد.")
        # لیست قیمت‌ها برای ویرایش
        elif action == "price":
            page = int(parts[3]) if len(parts) >= 4 and parts[3].isdigit() else 0
            keys = list(FP.PLAYERS.keys())
            per = 8
            total = max(1, (len(keys) + per - 1) // per)
            page = max(0, min(page, total - 1))
            kb = InlineKeyboardBuilder()
            lines = ["💰 <b>تنظیم قیمت بازیکنان</b>", ""]
            for key in keys[page*per:(page+1)*per]:
                p = FP.get(key)
                price = await FMKT.effective_price(session, key)
                unit = "$" if p["currency"] == "game" else "T"
                kb.button(text=f"{p['name']} — {price:,}{unit}", callback_data=with_owner(f"adm:pmarket:setp:{key}", uid))
            if page > 0:
                kb.button(text="◀️", callback_data=with_owner(f"adm:pmarket:price:{page-1}", uid))
            if page < total - 1:
                kb.button(text="▶️", callback_data=with_owner(f"adm:pmarket:price:{page+1}", uid))
            kb.button(text="🔍 جستجوی بازیکن (با اسم)", callback_data=with_owner("adm:pmarket:search", uid))
            kb.button(text="⬅️ بازگشت", callback_data=with_owner("adm:pmarket:home", uid))
            kb.adjust(1)
            await safe_edit(callback.message, "\n".join(lines), kb.as_markup())
            await callback.answer()
            return
        # شروع تنظیم قیمت یک بازیکن
        elif action == "setp" and len(parts) >= 4:
            key = parts[3]
            p = FP.get(key)
            if p is None:
                await callback.answer("بازیکن نامعتبر.", show_alert=True)
                return
            await state.set_state(AdminStates.market_price_wait)
            await state.update_data(market_price_key=key)
            cur = await FMKT.effective_price(session, key)
            unit = "$ (دلار بازی)" if p["currency"] == "game" else "تومان"
            await callback.message.answer(f"💰 قیمت جدید برای <b>{p['name']}</b> (فعلی: {cur:,} {unit}) را بفرست:\n{CANCEL_HINT}")
            await callback.answer()
            return

        # پنل اصلی
        waiting_admin = list((await session.execute(__import__("sqlalchemy").select(FootballMarketSale).where(FootballMarketSale.status == "awaiting_admin"))).scalars().all())
        paying = list((await session.execute(__import__("sqlalchemy").select(FootballMarketSale).where(FootballMarketSale.status.in_(["awaiting_payment", "receipt_check"])))).scalars().all())
        lines = ["⚽ <b>بازار بازیکنان — مدیریت</b>", "",
                 f"⏳ منتظر تأیید ادمین: {len(waiting_admin)}  |  💳 در جریان پرداخت/رسید: {len(paying)}", ""]
        kb = InlineKeyboardBuilder()
        for s in waiting_admin[:8]:
            lines.append(f"⏳ <b>{s.player_name}</b> — بالاترین پیشنهاد {int(s.highest_bid):,} تومان (کاربر <code>{s.current_candidate}</code>)")
            kb.button(text=f"✅ تأیید {s.player_name}", callback_data=with_owner(f"adm:pmarket:ok:{s.id}", uid))
        for s in paying[:8]:
            tag = "🧾" if s.status == "receipt_check" else "💳"
            lines.append(f"{tag} <b>{s.player_name}</b> — {int(s.highest_bid):,} تومان (کاربر <code>{s.current_candidate}</code>)")
            if s.status == "receipt_check":
                kb.button(text=f"💰 تأیید رسید {s.player_name}", callback_data=with_owner(f"adm:pmarket:paid:{s.id}", uid))
                kb.button(text=f"❌ رد رسید", callback_data=with_owner(f"adm:pmarket:no:{s.id}", uid))
            kb.button(text=f"🚫 لغو فروش", callback_data=with_owner(f"adm:pmarket:cancel:{s.id}", uid))
        if not (waiting_admin or paying):
            lines.append("درخواستی در صف نیست. ✅")
        kb.button(text="💰 تنظیم قیمت بازیکنان", callback_data=with_owner("adm:pmarket:price:0", uid))
        kb.button(text="⬅️ بازگشت به ابزارها", callback_data=with_owner("adm:sec:tools", uid))
        kb.adjust(1)
        await safe_edit(callback.message, "\n".join(lines), kb.as_markup())
        await callback.answer()


@router.message(AdminStates.market_price_wait)
async def market_price_recv(message: Message, state: FSMContext):
    if await handle_cancel_word(message, state):
        return
    admin = await _guard_perm(message, state, "tools")
    if admin is None:
        return
    raw = (message.text or "").strip().replace(",", "")
    if not raw.isdigit() or int(raw) < 0:
        await message.reply("فقط عددِ مثبت بفرست (قیمت).")
        return
    data = await state.get_data()
    key = str(data.get("market_price_key") or "")
    from app.services import football_market as FMKT
    from app.data import football_players as FP
    p = FP.get(key)
    async with async_session() as session:
        await FMKT.set_price_override(session, key, int(raw))
        await session.commit()
    await state.clear()
    await message.reply(f"✅ قیمت <b>{p['name'] if p else key}</b> روی {int(raw):,} تنظیم شد.")

# --------------------------- ⚽ کنترل فوتبال (v1.8.1.0 — F6) ---------------------------
@router.callback_query(F.data.startswith("adm:fball"))
async def admin_fball_cb(callback: CallbackQuery, state: FSMContext):
    admin = await _cb_admin(callback)
    if admin is None:
        return
    if not _require(admin, "tools"):
        await callback.answer(A.denied_text("tools"), show_alert=True)
        return
    base, _ = split_owner(callback.data)
    parts = base.split(":")
    sub = parts[2] if len(parts) > 2 else "home"
    uid = callback.from_user.id

    if sub == "forceleague":
        from app.services import football_friday as FFRI
        async with async_session() as session:
            ok, msg = await FFRI.run_league(session, callback.bot)
            await session.commit()
        await callback.answer(msg, show_alert=True)
        return
    if sub == "forceucl":
        from app.services import football_ucl as FUCL
        async with async_session() as session:
            await FUCL.advance_ucl(session, callback.bot)
            await session.commit()
        await callback.answer("✅ UCL پیش رفت", show_alert=True)
        return

    from sqlalchemy import select as _sel, func as _f
    from aiogram.utils.keyboard import InlineKeyboardBuilder as _IKB
    from app.models.football import FootballClub, FootballPlayerCard
    from app.models.football_live import FootballLiveMatch
    async with async_session() as session:
        clubs = int((await session.execute(_sel(_f.count()).select_from(FootballClub))).scalar() or 0)
        players = int((await session.execute(_sel(_f.count()).select_from(FootballPlayerCard))).scalar() or 0)
        live = int((await session.execute(_sel(_f.count()).select_from(FootballLiveMatch).where(FootballLiveMatch.status == "live"))).scalar() or 0)
    lines = [
        "⚽ <b>کنترل فوتبال (ادمین)</b>",
        "",
        f"🏟️ باشگاه‌ها: {clubs}",
        f"🃏 کارت‌های بازیکن: {players:,}",
        f"🎮 بازی‌های زندهٔ در جریان: {live}",
    ]
    kb = _IKB()
    kb.button(text="▶️ اجرای فوری لیگ جمعه", callback_data=with_owner("adm:fball:forceleague", uid))
    kb.button(text="▶️ پیشبرد فوری UCL", callback_data=with_owner("adm:fball:forceucl", uid))
    kb.button(text="🧑‍✈️ خریدهای ورزشی", callback_data=with_owner("adm:coachsales:home", uid))
    kb.button(text="🛒 بازار بازیکنان", callback_data=with_owner("adm:pmarket:home", uid))
    kb.button(text="🎁 اهدا/گرفتن بازیکن از کاربر", callback_data=with_owner("adm:fbpm:start", uid))
    kb.button(text="⬅️ بازگشت به ابزارها", callback_data=with_owner("adm:sec:tools", uid))
    kb.adjust(1)
    await safe_edit(callback.message, "\n".join(lines), kb.as_markup())
    await callback.answer()

# --------------------------- ⚡ v1.8.2.1 — تکمیل فوری صف‌های اتحادیه (ادمین) ---------------------------
@router.callback_query(F.data.startswith("adm:allq:complete"))
async def allq_complete_cb(callback: CallbackQuery):
    admin = await _cb_admin(callback)
    if admin is None:
        return
    if not _require(admin, "tools"):
        await callback.answer(A.denied_text("tools"), show_alert=True)
        return
    from app.services import alliance_military_service as AMS
    async with async_session() as session:
        na, units = await AMS.admin_force_settle_all(session)
        await session.commit()
    await callback.answer(f"⚡ تکمیل شد — {na} اتحادیه، {units:,} واحد به سربازخانه‌ها اضافه شد.", show_alert=True)

# --------------------------- 🔍 v1.8.2.1 — جستجوی بازیکن برای تغییر قیمت ---------------------------
@router.message(AdminStates.pmarket_wait_search)
async def pmarket_search_recv(message: Message, state: FSMContext):
    if await handle_cancel_word(message, state):
        return
    admin = await _guard_perm(message, state, "tools")
    if admin is None:
        return
    q = (message.text or "").strip()
    if len(q) < 2:
        await message.reply("حداقل ۲ حرف از اسم بازیکن را بفرست.")
        return
    from app.data import football_players as FP
    uid = message.from_user.id
    matches = [(k, v) for k, v in FP.PLAYERS.items() if q.lower() in str(v.get("name", "")).lower()]
    await state.clear()
    if not matches:
        await message.reply(f"هیچ بازیکنی با «{q}» پیدا نشد.")
        return
    from app.services import football_market as FMKT
    kb = InlineKeyboardBuilder()
    lines = [f"🔍 <b>نتایج برای «{q}»</b> ({len(matches)})", ""]
    async with async_session() as session:
        for key, p in matches[:12]:
            price = await FMKT.effective_price(session, key)
            unit = "$" if p["currency"] == "game" else "T"
            lines.append(f"• <b>{p['name']}</b> — {p['pos']} | 💪{p['power']:,} | {price:,}{unit}")
            kb.button(text=f"✏️ {p['name']} — {price:,}{unit}", callback_data=with_owner(f"adm:pmarket:setp:{key}", uid))
    kb.button(text="⬅️ بازگشت به قیمت‌ها", callback_data=with_owner("adm:pmarket:price:0", uid))
    kb.adjust(1)
    await message.answer("\n".join(lines), reply_markup=kb.as_markup())


# --------------------------- 🎁 v1.8.2.1 — اهدا/گرفتن/انتقال بازیکن (ادمین) ---------------------------
def _fbpm_home_kb(uid):
    kb = InlineKeyboardBuilder()
    kb.button(text="➕ اهدا بازیکن به این کاربر", callback_data=with_owner("adm:fbpm:give", uid))
    kb.button(text="📋 بازیکن‌های کاربر (گرفتن/انتقال)", callback_data=with_owner("adm:fbpm:list", uid))
    kb.button(text="⬅️ بازگشت به فوتبال", callback_data=with_owner("adm:fball:home", uid))
    kb.adjust(1)
    return kb.as_markup()


@router.callback_query(F.data.startswith("adm:fbpm"))
async def fbpm_cb(callback: CallbackQuery, state: FSMContext):
    admin = await _cb_admin(callback)
    if admin is None:
        return
    if not _require(admin, "tools"):
        await callback.answer(A.denied_text("tools"), show_alert=True)
        return
    base, _ = split_owner(callback.data)
    parts = base.split(":")
    action = parts[2] if len(parts) >= 3 else "start"
    uid = callback.from_user.id
    from app.services import football_market as FMKT
    from app.data import football_players as FP

    if action == "start":
        await state.set_state(AdminStates.fball_pm_wait_uid)
        await safe_edit(callback.message, "🎁 <b>مدیریت بازیکن کاربر</b>\n\nیوزرآیدیِ کاربرِ هدف را بفرست:", _fbpm_home_kb(uid))
        await callback.answer()
        return

    data = await state.get_data()
    target = int(data.get("fbpm_uid") or 0)
    if not target:
        await callback.answer("اول یوزرآیدی کاربر را بده (از «اهدا/گرفتن بازیکن»).", show_alert=True)
        return

    if action == "give":
        await state.set_state(AdminStates.fball_give_wait_name)
        await safe_edit(callback.message, f"➕ <b>اهدا بازیکن</b> به <code>{target}</code>\n\nاسم بازیکن را بفرست:", _fbpm_home_kb(uid))
        await callback.answer()
        return

    if action == "list":
        async with async_session() as session:
            cards = await FMKT.purchase_history(session, target, limit=40)
        lines = [f"📋 <b>بازیکن‌های کاربر {target}</b> ({len(cards)})", ""]
        kb = InlineKeyboardBuilder()
        if not cards:
            lines.append("این کاربر بازیکنی ندارد.")
        for c in cards[:20]:
            lines.append(f"• <b>{c.name}</b> — {c.pos} | 💪{c.base_power:,} | <code>{c.tracking_code}</code>")
            kb.button(text=f"❌ گرفتن {c.name}", callback_data=with_owner(f"adm:fbpm:take:{c.id}", uid))
            kb.button(text=f"🔁 انتقال {c.name}", callback_data=with_owner(f"adm:fbpm:tr:{c.id}", uid))
        kb.button(text="⬅️ بازگشت", callback_data=with_owner("adm:fbpm:start", uid))
        kb.adjust(2)
        await safe_edit(callback.message, "\n".join(lines), kb.as_markup())
        await callback.answer()
        return

    if action == "take" and len(parts) >= 4:
        async with async_session() as session:
            ok, msg = await FMKT.admin_take_player(session, target, int(parts[3]))
            await session.commit()
        await callback.answer(msg, show_alert=True)
        return

    if action == "tr" and len(parts) >= 4:
        await state.update_data(fbpm_card=int(parts[3]))
        await state.set_state(AdminStates.fball_transfer_wait_uid)
        await safe_edit(callback.message, f"🔁 <b>انتقال بازیکن</b> از <code>{target}</code>\n\nیوزرآیدیِ کاربرِ <b>مقصد</b> را بفرست:", _fbpm_home_kb(uid))
        await callback.answer()
        return

    if action == "giveok" and len(parts) >= 4:
        async with async_session() as session:
            ok, msg = await FMKT.admin_give_player(session, target, parts[3], remove_from_shop=False)
            await session.commit()
        await callback.answer(msg, show_alert=True)
        return

    await callback.answer()


@router.message(AdminStates.fball_pm_wait_uid)
async def fbpm_uid_recv(message: Message, state: FSMContext):
    if await handle_cancel_word(message, state):
        return
    admin = await _guard_perm(message, state, "tools")
    if admin is None:
        return
    raw = (message.text or "").strip()
    if not raw.isdigit():
        await message.reply("یوزرآیدی باید عدد باشد.")
        return
    await state.update_data(fbpm_uid=int(raw))
    await state.set_state(None)
    await message.answer(f"✅ کاربر <code>{raw}</code> انتخاب شد. حالا یک عملیات را انتخاب کن:", reply_markup=_fbpm_home_kb(message.from_user.id))


@router.message(AdminStates.fball_give_wait_name)
async def fbpm_give_recv(message: Message, state: FSMContext):
    if await handle_cancel_word(message, state):
        return
    admin = await _guard_perm(message, state, "tools")
    if admin is None:
        return
    q = (message.text or "").strip()
    data = await state.get_data()
    target = int(data.get("fbpm_uid") or 0)
    from app.data import football_players as FP
    matches = [(k, v) for k, v in FP.PLAYERS.items() if q.lower() in str(v.get("name", "")).lower()]
    if not matches:
        await message.reply(f"بازیکنی با «{q}» پیدا نشد. دوباره بفرست یا انصراف بده.")
        return
    uid = message.from_user.id
    kb = InlineKeyboardBuilder()
    for key, p in matches[:12]:
        kb.button(text=f"➕ {p['name']} ({p['pos']} 💪{p['power']:,})", callback_data=with_owner(f"adm:fbpm:giveok:{key}", uid))
    kb.button(text="✖ انصراف", callback_data=with_owner("adm:fbpm:start", uid))
    kb.adjust(1)
    await state.set_state(None)
    await message.answer(f"➕ اهدا به <code>{target}</code> — بازیکن را انتخاب کن:", reply_markup=kb.as_markup())


@router.message(AdminStates.fball_transfer_wait_uid)
async def fbpm_transfer_recv(message: Message, state: FSMContext):
    if await handle_cancel_word(message, state):
        return
    admin = await _guard_perm(message, state, "tools")
    if admin is None:
        return
    raw = (message.text or "").strip()
    if not raw.isdigit():
        await message.reply("یوزرآیدی مقصد باید عدد باشد.")
        return
    data = await state.get_data()
    from_uid = int(data.get("fbpm_uid") or 0)
    card_id = int(data.get("fbpm_card") or 0)
    from app.services import football_market as FMKT
    async with async_session() as session:
        ok, res = await FMKT.transfer_player(session, from_uid, card_id, int(raw))
        await session.commit()
    await state.clear()
    await message.reply(f"✅ بازیکن <b>{res}</b> به کاربر <code>{raw}</code> منتقل شد." if ok else f"❌ {res}")
