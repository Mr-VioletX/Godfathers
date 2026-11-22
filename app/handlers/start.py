from aiogram import F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    ReplyKeyboardRemove,
)
from sqlalchemy import select

from app.database.engine import async_session
from app.keyboards.gender import gender_keyboard
from app.keyboards.main_menu import main_menu
from app.models.player import Player
from app.states import Registration
from app.services import chat_service

router = Router()

BOT_USERNAME = "GDF_Gamebot"  # بدونِ @ — اگر یوزرنیمِ رباتت فرق دارد همین را عوض کن
TITLES = {"male": "The Don 🤵", "female": "La Donna 👰"}


def _pm_button() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(
                text="🤖 شروع در چت خصوصی",
                url=("https://t.me/" + BOT_USERNAME + "?start=go"),
            )
        ]]
    )


def _extract_referral_id(text: str | None, command: CommandObject | None, self_id: int) -> int | None:
    """استخراج امن ref_XXXX از deep-link /start."""
    candidates: list[str] = []
    if command is not None and getattr(command, "args", None):
        candidates.append(str(command.args).strip())
    raw = (text or "").strip()
    if raw:
        parts = raw.split()
        if len(parts) >= 2:
            candidates.append(parts[-1].strip())
        candidates.append(raw)

    for item in candidates:
        if not item:
            continue
        token = item
        if "start=" in token:
            token = token.split("start=", 1)[1]
        token = token.split("&", 1)[0].strip()
        if token.startswith("ref_"):
            token = token[4:]
        try:
            cand = int(token)
        except ValueError:
            continue
        if cand > 0 and cand != int(self_id):
            return cand
    return None


@router.message(CommandStart(), F.chat.type == "private")
@router.message(F.text.in_({"شروع", "شروع ربات"}), F.chat.type == "private")
async def cmd_start(message: Message, state: FSMContext, command: CommandObject | None = None):
    async with async_session() as session:
        result = await session.execute(
            select(Player).where(Player.tg_user_id == message.from_user.id)
        )
        player = result.scalar_one_or_none()

    if player is None:
        referral_id = _extract_referral_id(message.text, command, message.from_user.id)
        # v1.7.9 — اگر payload نبود، از صفِ انتظارِ دیتابیس بخوان؛ شاید لینک
        # پشتِ دیوارِ جوین اجباری ذخیره شده باشد.
        if not referral_id:
            try:
                from app.services import referral_service as refs
                async with async_session() as session:
                    referral_id = await refs.peek_pending(session, message.from_user.id)
            except Exception:
                referral_id = None
        await state.set_state(Registration.choosing_gender)
        invite_note = "🆓 ورود آزاد (بدون لینک دعوت).\n\n"
        if referral_id:
            # v1.7.9 — ذخیره‌ی پایدار در دیتابیس تا با پاک شدنِ state گم نشود
            try:
                from app.services import referral_service as refs
                async with async_session() as session:
                    await refs.stash_pending(session, message.from_user.id, int(referral_id))
            except Exception:
                pass
            await state.update_data(referral_id=int(referral_id))
            inviter_name = str(referral_id)
            try:
                async with async_session() as session:
                    inv = (
                        await session.execute(
                            select(Player).where(Player.tg_user_id == int(referral_id))
                        )
                    ).scalar_one_or_none()
                    if inv is not None:
                        inviter_name = inv.name or str(referral_id)
            except Exception:
                pass
            invite_note = (
                f"🤝 شما توسط <b>{inviter_name}</b> دعوت شده‌اید.\n"
                f"پس از ساخت شخصیت، دعوت ثبت می‌شود.\n\n"
            )
        else:
            await state.update_data(referral_id=None)
        await message.answer(
            invite_note
            + "🎩 به دنیای تاریک «گادفادر» خوش آمدی!\n\n"
            "قبل از شروع، شخصیت خود را انتخاب کن:",
            reply_markup=gender_keyboard(),
        )
    else:
        # v1.7.9 — کاربر قبلاً ثبت‌نام کرده؛ صفِ انتظارِ احتمالی‌اش پاک شود
        try:
            from app.services import referral_service as refs
            async with async_session() as session:
                await refs.pop_pending(session, message.from_user.id)
        except Exception:
            pass
        ref_try = _extract_referral_id(message.text, command, message.from_user.id)
        extra = ""
        if ref_try:
            extra = "\n\nℹ️ قبلاً ثبت‌نام کرده‌ای؛ لینک دعوت فقط برای عضو جدید کار می‌کند."
        await message.answer(
            f"👋 خوش برگشتی <b>{player.name}</b>!" + extra, reply_markup=main_menu()
        )
        await chat_service.notify_unread_on_start(message)


@router.message(CommandStart(), F.chat.type.in_({"group", "supergroup"}))
async def cmd_start_in_group(message: Message):
    await message.reply(
        "👋 برای ساختِ شخصیت و ثبت‌نام باید وارد چتِ خصوصیِ ربات شوی.\n"
        "روی دکمه‌ی زیر بزن و آنجا /start را بزن 👇",
        reply_markup=_pm_button(),
    )


@router.callback_query(
    Registration.choosing_gender,
    F.data.startswith("gender:"),
    F.message.chat.type == "private",
)
async def choose_gender(callback: CallbackQuery, state: FSMContext):
    gender = callback.data.split(":")[1]
    form_data = await state.get_data()
    referral_id = form_data.get("referral_id")
    try:
        referral_id = int(referral_id) if referral_id else None
    except (TypeError, ValueError):
        referral_id = None
    # v1.7.9 — اگر state خالی بود (پاک شدن/ریستارت)، از صفِ انتظارِ دیتابیس بخوان
    if not referral_id:
        try:
            from app.services import referral_service as refs
            async with async_session() as session:
                referral_id = await refs.peek_pending(session, callback.from_user.id)
        except Exception:
            referral_id = None
    reward = None
    async with async_session() as session:
        result = await session.execute(
            select(Player).where(Player.tg_user_id == callback.from_user.id)
        )
        player = result.scalar_one_or_none()
        if player is None:
            player = Player(
                tg_user_id=callback.from_user.id,
                name=callback.from_user.full_name,
                gender=gender,
            )
            session.add(player)
            await session.flush()
            from app.services import referral_service as refs
            if referral_id:
                reward = await refs.reward_new_player(
                    session, referral_id, callback.from_user.id
                )
            # v1.7.9 — دعوتِ در انتظار (اگر هست) مصرف شد؛ پاکش کن
            await refs.pop_pending(session, callback.from_user.id, commit=False)
            await session.commit()
        cash = player.cash

    await state.clear()
    await callback.message.edit_text(
        f"✅ شخصیت تو ساخته شد!\n\n"
        f"🎩 لقب: <b>{TITLES.get(gender, gender)}</b>\n"
        f"💵 موجودی اولیه: <b>{cash:,}</b> دلار"
    )

    # v1.7.2 — پیام موفقیت برای هر دو طرف
    if reward and reward.get("ok"):
        from app.services import referral_service as refs
        try:
            await callback.bot.send_message(
                int(reward["referrer_id"]), refs.inviter_success_text(reward)
            )
        except Exception:
            pass
        try:
            await callback.message.answer(refs.invitee_success_text(reward))
        except Exception:
            pass

    await callback.message.answer(
        "از منوی زیر ادامه بده 👇\nبرای منوی شیشه‌ای در گروه بنویس «منو».",
        reply_markup=main_menu(),
    )
    await callback.answer("✅ ثبت شد")


@router.message(Command("clearkb"), F.chat.type.in_({"group", "supergroup"}))
async def clear_group_keyboard(message: Message):
    await message.reply(
        "✅ کیبوردِ ربات از این گروه پاک شد.",
        reply_markup=ReplyKeyboardRemove(),
    )
