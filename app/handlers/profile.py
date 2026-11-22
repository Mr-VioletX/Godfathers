from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select

from app.database.engine import async_session
from app.data import leveling
from app.data.profile import ANNOUNCE_IDLE_CHOICES, dump_json, idle_label, load_announce, load_privacy
from app.data.titles import (
    get_title_by_name,
    gender_ok,
    is_gender_locked,
    validate_name,
)
from app.keyboards.privacy_menu import announce_groups_menu, announce_idle_menu, announce_menu, privacy_menu
from app.keyboards.profile_menu import (
    gender_inline_menu,
    photo_edit_menu,
    profile_menu,
)
from app.models.group_membership import GroupMembership
from app.models.player import Player
from app.states import ProfileStates
from app.utils.ui import CANCEL_HINT, ensure_owner, handle_cancel_word, safe_edit, split_owner

router = Router()

GENDER_LABELS = {"male": "👔 مرد (The Don)", "female": "👗 زن (La Donna)"}
ONLY_BOT = "این کار فقط داخل خودِ ربات ممکن است."


# Stage 27: online announcement is limited to players with an active title
NO_TITLE_ANNOUNCE = (
    "📣 اعلامِ آنلاین فقط برای بازیکنانی فعال است که یک لقبِ فعال دارند.\n"
    "اول از بخشِ لقب‌ها یک لقب بگیر و فعالش کن."
)


async def _announce_allowed(callback: CallbackQuery) -> bool:
    """فقط دارنده‌ی لقبِ فعال می‌تواند اعلامِ آنلاین داشته باشد."""
    try:
        from app.services import titles as _titles
        async with async_session() as session:
            title = await _titles.display_title(session, callback.from_user.id)
            # v1.7.8.19 — معیار با میان‌برِ اعلام (tracking) یکی شد: هر لقبِ فعال
            # (کسب‌شده یا سفارشی) کافی است. قبلاً اشتراکِ فعال هم جداگانه اجباری
            # بود و دارندگانِ لقبِ کسب‌شده بدونِ اشتراک اشتباهی پیامِ «اول لقب
            # فعال کن» می‌گرفتند. نکته: برای لقبِ سفارشی، خودِ display_title
            # اشتراکِ فعال را لازم می‌داند، پس آن قانون همچنان حفظ است.
            if title:
                return True
    except Exception:
        pass
    await callback.answer(NO_TITLE_ANNOUNCE, show_alert=True)
    return False


async def get_player(session, tg_user_id: int) -> Player | None:
    result = await session.execute(
        select(Player).where(Player.tg_user_id == tg_user_id)
    )
    return result.scalar_one_or_none()


def _only_private(callback: CallbackQuery) -> bool:
    return callback.message.chat.type == "private"


def render_profile(player: Player, private: bool, active_title: str | None = None) -> str:
    """🆕 مرحله ۳۰ — active_title = لقبِ فعالِ کاربر از بخشِ القاب."""
    privacy = load_privacy(player.privacy_settings)
    lines = [f"<b>👤 پروفایل {player.name}</b>"]
    shown_title = active_title or player.custom_title
    if shown_title and (private or privacy.get("title", True)):
        _t = get_title_by_name(shown_title)
        if _t:
            lines.append(f"🎖️ لقب: {shown_title} [{_t['rarity']}]")
            if private and _t.get("effect"):
                lines.append(f"🎁 اثر: {_t['effect']}")
        else:
            lines.append(f"🎖️ لقب: {shown_title}")
    if player.gender:
        lines.append(f"⚧ جنسیت: {GENDER_LABELS.get(player.gender, player.gender)}")
    if private or privacy.get("level", True):
        # Stage 27: show level + XP bar + remaining XP needed for the next level
        lines.append(f"⭐ سطح: {player.level}")
        lines.append(leveling.progress_line(player))
    if private or privacy.get("cash", True):
        lines.append(f"💰 موجودی: {player.cash:,}")
    if private and player.is_premium:
        lines.append("💎 کاربر اشتراکی")
    if not private and any(not v for v in privacy.values()):
        lines.append("\n<i>بعضی اطلاعات طبق حریم خصوصی مخفی است.</i>")
    return "\n".join(lines)


async def active_title_of(session, uid: int) -> str | None:
    """🆕 مرحله ۳۰ — لقبِ فعالِ کاربر."""
    try:
        from app.services import titles as _titles
        return await _titles.display_title(session, uid)
    except Exception:
        return None


async def profile_text(uid: int, player: Player, private: bool) -> str:
    """🆕 مرحله ۳۰ — متنِ پروفایل همراه با لقبِ فعال."""
    async with async_session() as session:
        title = await active_title_of(session, uid)
    return render_profile(player, private, title)


# ---------- تغییر نام ----------
@router.callback_query(F.data.startswith("profile:edit_name"))
async def edit_name(callback: CallbackQuery, state: FSMContext) -> None:
    if not await ensure_owner(callback):
        return
    if not _only_private(callback):
        await callback.answer(ONLY_BOT, show_alert=True)
        return
    await state.set_state(ProfileStates.editing_name)
    await callback.message.answer(
        "نام جدیدت را بفرست:" + CANCEL_HINT,
    )
    await callback.answer()


@router.message(ProfileStates.editing_name)
async def save_name(message: Message, state: FSMContext) -> None:
    if await handle_cancel_word(message, state):
        return
    # 🆕 مرحله ۱۱ — اعتبارسنجیِ ضدباگِ نام (کلماتِ رزرو، لینک، طول و …)
    ok, result = validate_name(message.text or "")
    if not ok:
        await message.answer(f"❌ {result}\nدوباره بفرست:")
        return
    new_name = result[:64]
    async with async_session() as session:
        player = await get_player(session, message.from_user.id)
        player.name = new_name
        await session.commit()
    await state.clear()
    await message.answer(f"✅ نامت شد: {new_name}\nبرای دیدن پروفایل بنویس «پروفایل».")


# ---------- تغییر عکس ----------
@router.callback_query(F.data.startswith("profile:edit_photo"))
async def edit_photo(callback: CallbackQuery, state: FSMContext) -> None:
    if not await ensure_owner(callback):
        return
    if not _only_private(callback):
        await callback.answer(ONLY_BOT, show_alert=True)
        return
    async with async_session() as session:
        from app.services.restrictions import blocked
        if await blocked(session, callback.from_user.id, "photo"):
            await callback.answer("عکس‌گذاری شما توسط ادمین محدود شده است.", show_alert=True)
            return
        player = await get_player(session, callback.from_user.id)
    has_photo = bool(player and player.photo_file_id)
    await state.set_state(ProfileStates.editing_photo)
    await callback.message.answer(
        "یک عکس بفرست تا عکس پروفایلت شود:"
        + ("\nیا با دکمه‌ی «🗑️ حذفِ عکس» عکسِ فعلی را بردار." if has_photo else ""),
        reply_markup=photo_edit_menu(callback.from_user.id, has_photo),
    )
    await callback.answer()


@router.message(ProfileStates.editing_photo, F.photo)
async def save_photo(message: Message, state: FSMContext) -> None:
    file_id = message.photo[-1].file_id
    async with async_session() as session:
        from app.services.restrictions import blocked
        if await blocked(session, message.from_user.id, "photo"):
            await state.clear(); await message.answer("عکس‌گذاری شما توسط ادمین محدود شده است."); return
        player = await get_player(session, message.from_user.id)
        player.photo_file_id = file_id
        await session.commit()
    await state.clear()
    await message.answer(
        "✅ عکس پروفایلت ذخیره شد.\n"
        "می‌توانی از «🔒 حریم خصوصی» تعیین کنی در گروه نمایش داده شود یا نه."
    )


@router.message(ProfileStates.editing_photo)
async def save_photo_invalid(message: Message, state: FSMContext) -> None:
    # 🆕 مرحله ۲۹: دکمهِ «✖️ انصراف» حذف شده؛ اگر کاربر به‌جایِ عکس، واژهِ «انصراف»
    # بفرسته باشد، همینجا لغو می‌شود.
    if await handle_cancel_word(message, state):
        return
    await message.reply("لطفاً یک «عکس» بفرست (نه متن)، یا بنویس «انصراف».")


# ---------- حذفِ عکسِ پروفایل ----------
@router.callback_query(F.data.startswith("profile:photo_delete"))
async def delete_photo(callback: CallbackQuery, state: FSMContext) -> None:
    if not await ensure_owner(callback):
        return
    await state.clear()
    async with async_session() as session:
        player = await get_player(session, callback.from_user.id)
        if player is None:
            await callback.answer("❌ ابتدا /start را بزن.", show_alert=True)
            return
        if not player.photo_file_id:
            await callback.answer("عکسی برای حذف وجود ندارد.", show_alert=True)
            return
        player.photo_file_id = None
        await session.commit()
        text = await profile_text(player.tg_user_id, player, _only_private(callback))
    await safe_edit(callback.message, text, profile_menu(callback.from_user.id))
    await callback.answer("🗑️ عکسِ پروفایل حذف شد.")


# ---------- انصراف از ویرایش (پاک‌کردنِ وضعیتِ FSM) ----------
@router.callback_query(F.data.startswith("profile:cancel"))
async def cancel_edit(callback: CallbackQuery, state: FSMContext) -> None:
    if not await ensure_owner(callback):
        return
    await state.clear()
    async with async_session() as session:
        player = await get_player(session, callback.from_user.id)
    text = await profile_text(player.tg_user_id, player, _only_private(callback))
    await safe_edit(callback.message, text, profile_menu(callback.from_user.id))
    await callback.answer("لغو شد")


# ---------- تغییر جنسیت (پروفایل) ----------
@router.callback_query(F.data.startswith("profile:edit_gender"))
async def edit_gender(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    if not _only_private(callback):
        await callback.answer(ONLY_BOT, show_alert=True)
        return
    await safe_edit(
        callback.message,
        "⚧ جنسیتت را انتخاب کن:",
        gender_inline_menu(callback.from_user.id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("setgender:"))
async def set_gender(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    base, _ = split_owner(callback.data)
    gender = base.split(":")[1]
    async with async_session() as session:
        player = await get_player(session, callback.from_user.id)
        player.gender = gender
        # 🆕 مرحله ۱۱ — اگر لقبِ فعال مخصوصِ جنسیتِ دیگر بود، برداشته شود
        if player.custom_title:
            _t = get_title_by_name(player.custom_title)
            if _t and is_gender_locked(_t) and not gender_ok(_t, gender):
                player.custom_title = None
        await session.commit()
        text = await profile_text(player.tg_user_id, player, True)
    await safe_edit(callback.message, text, profile_menu(callback.from_user.id))
    await callback.answer("✅ ثبت شد")


# ---------- حریم خصوصی ----------
@router.callback_query(F.data.startswith("profile:privacy"))
async def open_privacy(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    async with async_session() as session:
        player = await get_player(session, callback.from_user.id)
    settings = load_privacy(player.privacy_settings)
    await safe_edit(
        callback.message,
        "🔒 <b>حریم خصوصی</b>\nانتخاب کن چه چیزی در گروه دیده شود:",
        privacy_menu(settings, callback.from_user.id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("privacy:toggle:"))
async def toggle_privacy(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    base, _ = split_owner(callback.data)
    key = base.split(":")[2]
    async with async_session() as session:
        player = await get_player(session, callback.from_user.id)
        settings = load_privacy(player.privacy_settings)
        settings[key] = not settings.get(key, True)
        player.privacy_settings = dump_json(settings)
        await session.commit()
    await safe_edit(
        callback.message,
        "🔒 <b>حریم خصوصی</b>\nانتخاب کن چه چیزی در گروه دیده شود:",
        privacy_menu(settings, callback.from_user.id),
    )
    await callback.answer("به‌روزرسانی شد")


@router.callback_query(F.data.startswith("profile:referral"))
async def referral_link(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback): return
    if not _only_private(callback):
        await callback.answer(ONLY_BOT, show_alert=True); return
    from app.handlers.start import BOT_USERNAME
    from app.services import referral_service as refs
    async with async_session() as session:
        total = await refs.referral_count(session, callback.from_user.id)
        cfg = await refs.get_config(session)
        today_bonus = await refs.bonus_pct(session, callback.from_user.id)
    lines=["🔗 <b>لینک دعوت من</b>", ("<code>https://t.me/" + BOT_USERNAME + "?start=ref_" + str(callback.from_user.id) + "</code>"), "", f"👥 دعوت موفق: <b>{total}</b>"]
    if cfg["cash_on"]: lines.append(f"💰 پاداش فعال: {cfg['cash_amount']:,}$ برای هر دعوت موفق")
    if cfg["bonus_on"]: lines.append(f"📈 بونس فعال امروز: +{today_bonus}٪ درآمد (هر دعوت یک روز؛ حداکثر ۲ دعوت در روز)")
    if not cfg["cash_on"] and not cfg["bonus_on"]: lines.append("فعلاً ادمین پاداش دعوت را فعال نکرده است.")
    await safe_edit(callback.message,"\n".join(lines),profile_menu(callback.from_user.id)); await callback.answer()

# ---------- اعلام آنلاین (منوی اصلی + زیرمنوی فاصله و گروه‌ها) ----------
# 🆕 v1.7.8.19 — ساعت‌ها به «فاصلهٔ اعلام» و گروه‌ها به «گروه‌ها» منتقل شدند؛
# هندلرهای announce:idle / announce:ingroup اضافه شدند (قبلاً نبودند و دکمه‌ها هنگ می‌کردند).
async def _get_groups(session, tg_user_id: int) -> list[tuple[int, str | None]]:
    result = await session.execute(
        select(GroupMembership).where(GroupMembership.tg_user_id == tg_user_id)
    )
    return [(m.chat_id, m.chat_title) for m in result.scalars().all()]


ANNOUNCE_MAIN_TEXT = (
    "📣 <b>اعلام آنلاین</b>\n"
    "کلید اصلی را روشن کن؛ وقتی مدتی غیرفعال باشی و دوباره چیزی بنویسی، آنلاین‌شدنت اعلام می‌شود.\n"
    "فاصلهٔ اعلام و گروه‌ها را از دکمه‌های زیر تنظیم کن:"
)
ANNOUNCE_IDLE_TEXT = (
    "⏱️ <b>فاصلهٔ اعلام</b>\n"
    "اگر به‌اندازهٔ این بازه غیرفعال باشی، با اولین پیامت (در ربات یا گروه) اعلامِ آنلاین فرستاده می‌شود.\n"
    "بازهٔ دلخواه را انتخاب کن:"
)
ANNOUNCE_GROUPS_TEXT = (
    "👥 <b>گروه‌ها</b>\n"
    "انتخاب کن اعلامِ آنلاین در کدام گروه‌ها فرستاده شود و آیا فعالیتِ درونِ گروه هم اعلام بسازد:"
)


async def _announce_home(callback: CallbackQuery) -> None:
    async with async_session() as session:
        player = await get_player(session, callback.from_user.id)
    settings = load_announce(player.announce_settings)
    await safe_edit(callback.message, ANNOUNCE_MAIN_TEXT, announce_menu(settings, callback.from_user.id))


@router.callback_query(F.data.startswith("profile:announce"))
async def open_announce(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    if not await _announce_allowed(callback):
        return
    await _announce_home(callback)
    await callback.answer()


@router.callback_query(F.data.startswith("announce:home"))
async def announce_home_cb(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    await _announce_home(callback)
    await callback.answer()


@router.callback_query(F.data.startswith("announce:toggle"))
async def toggle_announce(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    if not await _announce_allowed(callback):
        return
    async with async_session() as session:
        player = await get_player(session, callback.from_user.id)
        settings = load_announce(player.announce_settings)
        settings["enabled"] = not settings.get("enabled", True)
        player.announce_settings = dump_json(settings)
        await session.commit()
    await _announce_home(callback)
    await callback.answer("به‌روزرسانی شد")


# ⚠️ ترتیب مهم: announce:idle:set: باید پیش از announce:idle ثبت شود
@router.callback_query(F.data.startswith("announce:idle:set:"))
async def announce_idle_set(callback: CallbackQuery) -> None:
    """🆕 v1.7.8.19 — تنظیم فاصلهٔ اعلام (قبلاً هندلر نداشت و دکمه هنگ می‌کرد)."""
    if not await ensure_owner(callback):
        return
    base, _ = split_owner(callback.data)
    try:
        minutes = int(base.rsplit(":", 1)[1])
    except (ValueError, IndexError):
        await callback.answer("⚠ مقدار نامعتبر است.", show_alert=True)
        return
    if minutes not in ANNOUNCE_IDLE_CHOICES:
        await callback.answer("⚠ مقدار نامعتبر است.", show_alert=True)
        return
    async with async_session() as session:
        player = await get_player(session, callback.from_user.id)
        settings = load_announce(player.announce_settings)
        settings["idle_minutes"] = minutes
        player.announce_settings = dump_json(settings)
        await session.commit()
    await safe_edit(callback.message, ANNOUNCE_IDLE_TEXT, announce_idle_menu(settings, callback.from_user.id))
    await callback.answer(f"✅ فاصلهٔ اعلام: {idle_label(minutes)}")


@router.callback_query(F.data.startswith("announce:idle"))
async def announce_idle_open(callback: CallbackQuery) -> None:
    """زیرمنوی فاصلهٔ اعلام (ساعت‌ها)."""
    if not await ensure_owner(callback):
        return
    async with async_session() as session:
        player = await get_player(session, callback.from_user.id)
    settings = load_announce(player.announce_settings)
    await safe_edit(callback.message, ANNOUNCE_IDLE_TEXT, announce_idle_menu(settings, callback.from_user.id))
    await callback.answer()


@router.callback_query(F.data.startswith("announce:groups"))
async def announce_groups_open(callback: CallbackQuery) -> None:
    """زیرمنوی گروه‌ها."""
    if not await ensure_owner(callback):
        return
    async with async_session() as session:
        player = await get_player(session, callback.from_user.id)
        groups = await _get_groups(session, callback.from_user.id)
    settings = load_announce(player.announce_settings)
    await safe_edit(callback.message, ANNOUNCE_GROUPS_TEXT, announce_groups_menu(settings, groups, callback.from_user.id))
    await callback.answer()


@router.callback_query(F.data.startswith("announce:ingroup"))
async def toggle_announce_ingroup(callback: CallbackQuery) -> None:
    """🆕 v1.7.8.19 — روشن/خاموش‌کردن «فعالیت در گروه» (قبلاً هندلر نداشت و هنگ می‌کرد)."""
    if not await ensure_owner(callback):
        return
    async with async_session() as session:
        player = await get_player(session, callback.from_user.id)
        settings = load_announce(player.announce_settings)
        settings["in_group"] = not settings.get("in_group", True)
        player.announce_settings = dump_json(settings)
        await session.commit()
        groups = await _get_groups(session, callback.from_user.id)
    await safe_edit(callback.message, ANNOUNCE_GROUPS_TEXT, announce_groups_menu(settings, groups, callback.from_user.id))
    await callback.answer("به‌روزرسانی شد")


@router.callback_query(F.data.startswith("announce:group:"))
async def toggle_announce_group(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    base, _ = split_owner(callback.data)
    chat_id = base.split(":")[2]  # رشته می‌ماند تا کلید JSON باشد
    async with async_session() as session:
        player = await get_player(session, callback.from_user.id)
        settings = load_announce(player.announce_settings)
        group_prefs = settings.setdefault("groups", {})
        group_prefs[chat_id] = not group_prefs.get(chat_id, True)
        player.announce_settings = dump_json(settings)
        await session.commit()
        groups = await _get_groups(session, callback.from_user.id)
    await safe_edit(callback.message, ANNOUNCE_GROUPS_TEXT, announce_groups_menu(settings, groups, callback.from_user.id))
    await callback.answer("به‌روزرسانی شد")


@router.callback_query(F.data.startswith("announce:noop"))
async def announce_noop(callback: CallbackQuery) -> None:
    await callback.answer(
        "هنوز عضو هیچ گروهی نیستی. اول ربات را به گروه اضافه کن و آنجا پیام بده.",
        show_alert=True,
    )


# ---------- بازگشت به منوی پروفایل ----------
@router.callback_query(F.data.startswith("profile:back"))
async def profile_back(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    async with async_session() as session:
        player = await get_player(session, callback.from_user.id)
    text = await profile_text(player.tg_user_id, player, _only_private(callback))
    await safe_edit(callback.message, text, profile_menu(callback.from_user.id))
    await callback.answer()
