# app/handlers/chat.py
"""چت‌مود (مرحله ۱۳.۶) — چتِ درون‌رباتیِ کاربر با کاربر.

امکانات:
  • درخواستِ چت با مهلتِ ۵ دقیقه (تأیید/رد)
  • تشخیصِ آنلاین/آفلاین (last_seen) + پیامِ آفلاین
  • relay متن/عکس/ویس/ویدیو‌مسیج (آهنگ/فیلم ممنوع)
  • بلاک، گزارش به ادمینِ اصلی، آرشیوِ ZIP+HTML در چنلِ خصوصی
  • فعال‌سازیِ اولیه‌یِ حالتِ ادمین

⚠️ این روتر باید پیش از menu/misc ثبت شود تا relayِ چتِ فعال زودتر عمل کند.
"""
from datetime import datetime, timedelta

from aiogram import Bot, F, Router
from aiogram.filters import BaseFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import delete, select

from app.config import ADMIN_IDS, MAIN_ADMIN_ID, settings
from app.database.engine import async_session
from app.keyboards.chat_menu import (
    blocked_menu,
    chat_active_kb,
    chat_home_menu,
    contacts_pick_menu,
    offline_leave_menu,
    offline_reply_menu,
    request_decision_menu,
    request_history_menu,
    request_sent_menu,
)
from app.keyboards.main_menu import main_menu
from app.models.chat import (
    BlockedUser,
    ChatMessage,
    ChatReport,
    ChatRequest,
    ChatSession,
    OfflineMessage,
)
from app.models.contact import Contact
from app.services import chat_service, spy_service
from app.states import ChatStates
from app.utils.ui import CANCEL_HINT, ensure_owner, handle_cancel_word, safe_show, split_owner

router = Router()

BTN_CHAT = "📡 خطِ محرمانه"
OPEN_WORDS = {"چت مود", "چت‌مود", BTN_CHAT}
END_WORDS = {"پایان چت", "پایان‌چت", "⏹️ پایان چت", "⏹️ پایانِ چت‌مود"}
BTN_REPORT = "🚨 گزارش"
BTN_BLOCK = "🚫 بلاک کاربر"

PRIV = F.chat.type == "private"


# --------------------------- فیلترِ چتِ فعال ---------------------------
class InActiveChat(BaseFilter):
    """فقط زمانی True که کاربر در یک جلسه‌ی چتِ فعال باشد (private)."""

    async def __call__(self, message: Message, state: FSMContext | None = None) -> bool:
        if message.chat.type != "private" or not message.from_user:
            return False
        # 🐞 مرحله ۳۰ — اگر کاربر در میانه‌ی یک ورودی باشد (نامِ اتحادیه/برند/…)،
        # متنِ او متعلق به همان بخش است و نباید توسطِ رله‌ی چت‌مود بلعیده شود.
        if state is not None:
            try:
                if await state.get_state():
                    return False
            except Exception:
                pass
        async with async_session() as session:
            sess = await chat_service.get_active_session(session, message.from_user.id)
        return sess is not None


async def _contacts_of(uid: int) -> list:
    async with async_session() as session:
        return (await session.execute(
            select(Contact).where(Contact.owner_id == uid).order_by(Contact.added_at.desc())
        )).scalars().all()


# =========================== بازکردنِ منو ===========================
@router.message(F.text.in_(OPEN_WORDS), PRIV)
async def open_chat_home(message: Message) -> None:
    await message.answer(
        "📡 <b>خطِ محرمانه</b>\nیکی را انتخاب کن:",
        reply_markup=chat_home_menu(message.from_user.id),
    )


# =========================== پایان/گزارش/بلاک (دکمه‌یِ متنی) ==========
@router.message(F.text.in_(END_WORDS), PRIV)
async def end_chat_text(message: Message, bot: Bot) -> None:
    await _do_end(message, bot, message.from_user.id)


@router.message(F.text == BTN_REPORT, PRIV)
async def report_btn(message: Message, state: FSMContext) -> None:
    async with async_session() as session:
        sess = await chat_service.get_active_session(session, message.from_user.id)
    if not sess:
        await message.answer("🚨 فقط در حینِ چت می‌توانی گزارش بدهی.")
        return
    other = chat_service.other_user(sess, message.from_user.id)
    await state.set_state(ChatStates.reporting)
    await state.update_data(reported_id=other)
    await message.answer(
        "🚨 دلیلِ گزارش را بنویس (توهین/رفتارِ نامناسب و ...)." + CANCEL_HINT,
    )


@router.message(F.text == BTN_BLOCK, PRIV)
async def block_btn(message: Message, bot: Bot) -> None:
    async with async_session() as session:
        sess = await chat_service.get_active_session(session, message.from_user.id)
        if not sess:
            await message.answer("🚫 فقط در حینِ چت می‌توانی بلاک کنی.")
            return
        other = chat_service.other_user(sess, message.from_user.id)
        await chat_service.block_user(session, message.from_user.id, other)
    await message.answer("🚫 کاربر بلاک شد و چت پایان یافت.")
    await _do_end(message, bot, message.from_user.id)


# =========================== کال‌بک‌ها ===========================
@router.callback_query(F.data.startswith("chat:menu"))
async def cb_menu(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    await safe_show(callback.message, "📡 <b>خطِ محرمانه</b>", chat_home_menu(callback.from_user.id))
    await callback.answer()


@router.callback_query(F.data.startswith("chat:start"))
async def cb_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not await ensure_owner(callback):
        return
    contacts = await _contacts_of(callback.from_user.id)
    await state.set_state(ChatStates.choosing_target)
    await safe_show(
        callback.message,
        "💬 <b>با کی می‌خواهی چت کنی؟</b>\nیوزرنیم یا آیدیِ عددی بفرست، یا از مخاطبین انتخاب کن:",
        contacts_pick_menu(contacts, callback.from_user.id, 0),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("chat:pgt:"))
async def cb_pgt(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    base, _ = split_owner(callback.data)
    page = int(base.split(":")[2])
    contacts = await _contacts_of(callback.from_user.id)
    await safe_show(
        callback.message,
        "💬 <b>با کی می‌خواهی چت کنی؟</b>",
        contacts_pick_menu(contacts, callback.from_user.id, page),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("chat:pick:"))
async def cb_pick(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    if not await ensure_owner(callback):
        return
    base, _ = split_owner(callback.data)
    target_id = int(base.split(":")[2])
    await state.clear()
    await callback.answer()
    await _initiate_chat(callback.message, bot, callback.from_user.id, target_id)


@router.callback_query(F.data.startswith("chat:accept:"))
async def cb_accept(callback: CallbackQuery, bot: Bot) -> None:
    if not await ensure_owner(callback):
        return
    base, _ = split_owner(callback.data)
    requester_id = int(base.split(":")[2])
    target_id = callback.from_user.id
    async with async_session() as session:
        req = (await session.execute(
            select(ChatRequest).where(
                ChatRequest.requester_id == requester_id,
                ChatRequest.target_id == target_id,
                ChatRequest.status == "pending",
            ).order_by(ChatRequest.id.desc())
        )).scalars().first()
        if not req:
            await callback.answer("این درخواست دیگر معتبر نیست.", show_alert=True)
            return
        if req.expires_at and req.expires_at < datetime.utcnow():
            req.status = "expired"
            await session.commit()
            await callback.answer("این درخواست منقضی شده.", show_alert=True)
            return
        if await chat_service.is_blocked(session, target_id, requester_id):
            await callback.answer("این کاربر در لیستِ بلاکِ توست.", show_alert=True)
            return
        if await chat_service.get_active_session(session, target_id) or \
                await chat_service.get_active_session(session, requester_id):
            await callback.answer("یکی از طرفین هم‌اکنون در یک چتِ فعال است.", show_alert=True)
            return
        req.status = "accepted"
        sess = ChatSession(user_a=requester_id, user_b=target_id, active=True)
        session.add(sess)
        await session.commit()
    await safe_show(callback.message, "✅ چت شروع شد.", None)
    await callback.message.answer(
        "✅ چت شروع شد. برایِ پایان بنویس «پایان چت».",
        reply_markup=chat_active_kb(),
    )
    try:
        await bot.send_message(
            requester_id,
            "✅ درخواستت پذیرفته شد! چت شروع شد.\nبرایِ پایان بنویس «پایان چت».",
            reply_markup=chat_active_kb(),
        )
    except Exception:
        pass
    await callback.answer()


@router.callback_query(F.data.startswith("chat:reject:"))
async def cb_reject(callback: CallbackQuery, bot: Bot) -> None:
    if not await ensure_owner(callback):
        return
    base, _ = split_owner(callback.data)
    requester_id = int(base.split(":")[2])
    target_id = callback.from_user.id
    async with async_session() as session:
        req = (await session.execute(
            select(ChatRequest).where(
                ChatRequest.requester_id == requester_id,
                ChatRequest.target_id == target_id,
                ChatRequest.status == "pending",
            ).order_by(ChatRequest.id.desc())
        )).scalars().first()
        if req:
            req.status = "rejected"
            await session.commit()
    await safe_show(callback.message, "❌ درخواستِ چت رد شد.", None)
    try:
        await bot.send_message(requester_id, "❌ درخواستِ چتِ تو رد شد.")
    except Exception:
        pass
    await callback.answer()


@router.callback_query(F.data.startswith("chat:leavemsg:"))
async def cb_leavemsg(callback: CallbackQuery, state: FSMContext) -> None:
    if not await ensure_owner(callback):
        return
    base, _ = split_owner(callback.data)
    target_id = int(base.split(":")[2])
    await state.set_state(ChatStates.offline_message)
    await state.update_data(offline_to=target_id)
    await callback.message.answer(
        "✍️ پیامت را بنویس (فقط متن؛ ارسالِ عکس مجاز نیست)." + CANCEL_HINT,
    )
    await callback.answer()


@router.callback_query(F.data.startswith("chat:unread"))
async def cb_unread(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    await _show_unread(callback.message, callback.from_user.id)
    await callback.answer()


@router.callback_query(F.data.startswith("chat:reqhistory"))
async def cb_reqhistory(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    await _show_request_history(callback.message, callback.from_user.id)
    await callback.answer()


@router.callback_query(F.data.startswith("chat:cancelreq:"))
async def cb_cancel_request(callback: CallbackQuery, bot: Bot) -> None:
    if not await ensure_owner(callback):
        return
    base, _ = split_owner(callback.data)
    target_id = int(base.split(":")[2])
    requester_id = callback.from_user.id
    async with async_session() as session:
        req = (await session.execute(
            select(ChatRequest).where(
                ChatRequest.requester_id == requester_id,
                ChatRequest.target_id == target_id,
                ChatRequest.status == "pending",
            ).order_by(ChatRequest.id.desc())
        )).scalars().first()
        if not req:
            await callback.answer("این درخواست دیگر معتبر نیست (شاید قبلاً پاسخ داده شده).", show_alert=True)
            return
        req.status = "cancelled"
        await session.commit()
    await safe_show(callback.message, "🚫 درخواستِ چتت لغو شد.", None)
    try:
        await bot.send_message(target_id, "🚫 طرفِ مقابل درخواستِ چتِ خودش را پس گرفت.")
    except Exception:
        pass
    await callback.answer("لغو شد.")


@router.callback_query(F.data.startswith("chat:blocked"))
async def cb_blocked(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    async with async_session() as session:
        blocked = (await session.execute(
            select(BlockedUser).where(BlockedUser.owner_id == callback.from_user.id)
        )).scalars().all()
    lines = ["🚫 <b>کاربرانِ بلاک‌شده</b>", ""]
    if blocked:
        lines += [f"• <code>{b.blocked_id}</code>" for b in blocked]
    else:
        lines.append("لیست خالی است.")
    await safe_show(callback.message, "\n".join(lines), blocked_menu(blocked, callback.from_user.id))
    await callback.answer()


@router.callback_query(F.data.startswith("chat:unblock:"))
async def cb_unblock(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    base, _ = split_owner(callback.data)
    blocked_id = int(base.split(":")[2])
    async with async_session() as session:
        await session.execute(delete(BlockedUser).where(
            BlockedUser.owner_id == callback.from_user.id,
            BlockedUser.blocked_id == blocked_id,
        ))
        await session.commit()
        blocked = (await session.execute(
            select(BlockedUser).where(BlockedUser.owner_id == callback.from_user.id)
        )).scalars().all()
    lines = ["🚫 <b>کاربرانِ بلاک‌شده</b>", ""]
    lines += [f"• <code>{b.blocked_id}</code>" for b in blocked] or ["لیست خالی است."]
    await safe_show(callback.message, "\n".join(lines), blocked_menu(blocked, callback.from_user.id))
    await callback.answer("♻️ رفعِ بلاک شد.")


@router.callback_query(F.data.startswith("chat:end"))
async def cb_end(callback: CallbackQuery, bot: Bot) -> None:
    if not await ensure_owner(callback):
        return
    await callback.answer()
    await _do_end(callback.message, bot, callback.from_user.id)


# =========================== دریافتِ ورودی (FSM) ===========================
@router.message(ChatStates.choosing_target, PRIV)
async def receive_target(message: Message, state: FSMContext, bot: Bot) -> None:
    await state.clear()
    async with async_session() as session:
        target_id, err = await spy_service.resolve_target(session, message.from_user.id, message.text or "")
    if err:
        await message.answer(f"❌ {err}")
        return
    await _initiate_chat(message, bot, message.from_user.id, target_id)


@router.message(ChatStates.offline_message, PRIV)
async def receive_offline(message: Message, state: FSMContext, bot: Bot) -> None:
    if await handle_cancel_word(message, state):
        return
    data = await state.get_data()
    await state.clear()
    to_id = data.get("offline_to")
    if not to_id:
        await message.answer("دوباره تلاش کن.")
        return
    if not message.text:
        await message.answer("❌ فقط پیامِ متنی مجاز است.")
        return
    async with async_session() as session:
        if await chat_service.is_blocked(session, to_id, message.from_user.id):
            await message.answer("❌ امکانِ ارسال به این کاربر نیست.")
            return
        session.add(OfflineMessage(from_id=message.from_user.id, to_id=to_id, text=message.text))
        await session.commit()
    await message.answer("✅ پیامت ذخیره شد؛ وقتی مخاطب آنلاین شد آن را می‌بیند.")
    try:
        await bot.send_message(
            to_id,
            "📨 یک پیامِ خوانده‌نشده داری. از «📡 خطِ محرمانه ← پیام‌های خوانده‌نشده» ببین.",
        )
    except Exception:
        pass


@router.message(ChatStates.reporting, PRIV)
async def receive_report(message: Message, state: FSMContext, bot: Bot) -> None:
    if await handle_cancel_word(message, state):
        return
    data = await state.get_data()
    await state.clear()
    reported_id = data.get("reported_id")
    reason = message.text or "(بدونِ متن)"
    async with async_session() as session:
        session.add(ChatReport(reporter_id=message.from_user.id, reported_id=reported_id, reason=reason))
        await session.commit()
    await message.answer("🚨 گزارشت برایِ ادمینِ اصلی ارسال شد. ممنون.")
    if MAIN_ADMIN_ID:
        try:
            await bot.send_message(
                MAIN_ADMIN_ID,
                f"🚨 <b>گزارشِ جدید</b>\nاز: <code>{message.from_user.id}</code>\n"
                f"علیه: <code>{reported_id}</code>\nدلیل: {reason}",
            )
        except Exception:
            pass


# =========================== منطقِ مشترک ===========================
async def _initiate_chat(message: Message, bot: Bot, requester_id: int, target_id: int) -> None:
    if target_id == requester_id:
        await message.answer("❌ نمی‌توانی با خودت چت کنی.")
        return
    async with async_session() as session:
        if await chat_service.is_blocked(session, target_id, requester_id):
            await message.answer("⛔ امکانِ ارسالِ درخواست به این کاربر نیست.")
            return
        if await chat_service.get_active_session(session, requester_id):
            await message.answer("تو همین‌الان در یک چتِ فعال هستی. اول «پایان چت» بزن.")
            return
        target = await chat_service.get_player(session, target_id)
        requester = await chat_service.get_player(session, requester_id)
        if not target:
            await message.answer("❌ این کاربر در بازی ثبت نشده.")
            return
        online = chat_service.is_online(target)
        req = ChatRequest(
            requester_id=requester_id, target_id=target_id, status="pending",
            expires_at=datetime.utcnow() + chat_service.REQUEST_TTL,
        )
        session.add(req)
        await session.commit()
        r_name = requester.name if requester else str(requester_id)
        r_photo = requester.photo_file_id if requester else None

    # 🆕 مرحله ۲۱.۱: اعلامیه‌یِ درخواستِ چت همیشه به‌صورتِ پیامِ درون‌رباتی با دکمه‌یِ
    # «تأیید و شروعِ چت / رد» برایِ هدف ارسال می‌شود — چه آنلاین باشد چه نه؛
    # تلگرام پیام را هروقت هدف ربات را باز کند تحویل می‌دهد.
    caption = f"💬 <b>{r_name}</b> درخواستِ چت با شما را دارد.\n⏳ مهلت: ۵ دقیقه"
    kb = request_decision_menu(requester_id, target_id)
    delivered = True
    try:
        if r_photo:
            await bot.send_photo(target_id, r_photo, caption=caption, reply_markup=kb)
        else:
            await bot.send_message(target_id, caption, reply_markup=kb)
    except Exception:
        delivered = False

    if not online:
        note = (
            "😴 مخاطب فعلاً در بازی آنلاین نیست؛ ولی اعلامیه‌یِ درخواستِ چت (با دکمه‌یِ تأیید/رد) "
            "برایش در ربات ارسال شد و تا ۵ دقیقه معتبر است.\n"
            "می‌توانی برایش یک پیامِ آفلاین هم بگذاری، یا از ارسالِ درخواست انصراف بدهی."
            if delivered else
            "⚠️ ارسالِ اعلامیه به این کاربر ممکن نشد (شاید ربات را استارت نکرده).\n"
            "می‌توانی برایش یک پیامِ آفلاین بگذاری یا از درخواست انصراف بدهی."
        )
        await message.answer(note, reply_markup=offline_leave_menu(target_id, requester_id))
        return
    await message.answer(
        "📨 درخواستِ چت ارسال شد. تا ۵ دقیقه منتظرِ پاسخ می‌مانیم.",
        reply_markup=request_sent_menu(target_id, requester_id),
    )


async def _show_request_history(message: Message, uid: int) -> None:
    """🆕 مرحله ۲۱.۱: درخواست‌هایِ چتِ یک‌هفته‌یِ اخیر (برایِ چک‌کردنِ درخواست‌هایِ دیده‌نشده)."""
    since = datetime.utcnow() - timedelta(days=7)
    status_fa = {
        "pending": "⏳ در انتظارِ پاسخ",
        "accepted": "✅ پذیرفته شد",
        "rejected": "❌ ردّ شد",
        "expired": "⌛ منقضی شد (دیده نشد)",
        "cancelled": "🚫 توسطِ فرستنده لغو شد",
    }
    async with async_session() as session:
        reqs = (await session.execute(
            select(ChatRequest).where(
                ChatRequest.target_id == uid,
                ChatRequest.created_at >= since,
            ).order_by(ChatRequest.created_at.desc())
        )).scalars().all()
        lines = ["📜 <b>درخواست‌هایِ چتِ یک‌هفته‌یِ اخیر</b>", ""]
        entries = []
        if not reqs:
            lines.append("درخواستی در این بازه ثبت نشده.")
        else:
            for r in reqs[:30]:
                sender = await chat_service.get_player(session, r.requester_id)
                name = sender.name if sender else str(r.requester_id)
                ts = r.created_at.strftime("%Y-%m-%d %H:%M") if r.created_at else ""
                lines.append(f"• {ts} — <b>{name}</b>: {status_fa.get(r.status, r.status)}")
                if r.status in ("pending", "expired", "rejected"):
                    entries.append({"requester_id": r.requester_id, "name": name})
    await safe_show(message, "\n".join(lines), request_history_menu(entries, uid))


async def _show_unread(message: Message, uid: int) -> None:
    shown = False
    async with async_session() as session:
        offs = (await session.execute(
            select(OfflineMessage).where(
                OfflineMessage.to_id == uid, OfflineMessage.is_read.is_(False)
            ).order_by(OfflineMessage.created_at)
        )).scalars().all()
        for o in offs:
            sender = await chat_service.get_player(session, o.from_id)
            name = sender.name if sender else str(o.from_id)
            await message.answer(
                f"📨 پیام از <b>{name}</b>:\n{o.text}",
                reply_markup=offline_reply_menu(o.from_id, uid),
            )
            o.is_read = True
            shown = True
        reqs = (await session.execute(
            select(ChatRequest).where(
                ChatRequest.target_id == uid, ChatRequest.status == "pending"
            )
        )).scalars().all()
        now = datetime.utcnow()
        pending = []
        for r in reqs:
            if r.expires_at and r.expires_at < now:
                r.status = "expired"
                continue
            pending.append(r.requester_id)
        await session.commit()
        for requester_id in pending:
            sender = await chat_service.get_player(session, requester_id)
            name = sender.name if sender else str(requester_id)
            await message.answer(
                f"💬 <b>{name}</b> درخواستِ چت دارد.",
                reply_markup=request_decision_menu(requester_id, uid),
            )
            shown = True
    if not shown:
        await message.answer("📭 پیامِ خوانده‌نشده‌ای نداری.")


async def _do_end(message: Message, bot: Bot, uid: int) -> None:
    async with async_session() as session:
        sess = await chat_service.get_active_session(session, uid)
        if not sess:
            await message.answer("در حالِ حاضر چتِ فعالی نداری.", reply_markup=main_menu())
            return
        other = chat_service.other_user(sess, uid)
        sess.active = False
        sess.ended_at = datetime.utcnow()
        await session.commit()
        msgs = (await session.execute(
            select(ChatMessage).where(ChatMessage.session_id == sess.id).order_by(ChatMessage.id)
        )).scalars().all()
        names = {}
        for pid in (sess.user_a, sess.user_b):
            p = await chat_service.get_player(session, pid)
            names[pid] = p.name if p else str(pid)
        try:
            archive_id = await chat_service.store_archive(bot, sess, msgs, names)
            if archive_id:
                sess.archive_msg_id = archive_id
                await session.commit()
        except Exception:
            pass
    await message.answer("⏹️ چت پایان یافت.", reply_markup=main_menu())
    try:
        await bot.send_message(other, "⏹️ طرفِ مقابل چت را پایان داد.", reply_markup=main_menu())
    except Exception:
        pass


# =========================== relayِ پیام‌هایِ چتِ فعال ===========================
async def _relay_media(message: Message, bot: Bot, kind: str, file_id: str) -> None:
    async with async_session() as session:
        sess = await chat_service.get_active_session(session, message.from_user.id)
        if not sess:
            return
        other = chat_service.other_user(sess, message.from_user.id)
        if await chat_service.is_blocked(session, other, message.from_user.id):
            await message.answer("⛔ این کاربر تو را بلاک کرده؛ ارسال نشد.")
            return
        await chat_service.record_message(session, sess.id, message.from_user.id, kind, file_id=file_id)
        await session.commit()
    try:
        if kind == "photo":
            await bot.send_photo(other, file_id)
        elif kind == "voice":
            await bot.send_voice(other, file_id)
        elif kind == "video_note":
            await bot.send_video_note(other, file_id)
    except Exception:
        await message.answer("⚠️ ارسال ممکن نشد.")


@router.message(InActiveChat(), F.photo)
async def relay_photo(message: Message, bot: Bot) -> None:
    await _relay_media(message, bot, "photo", message.photo[-1].file_id)


@router.message(InActiveChat(), F.voice)
async def relay_voice(message: Message, bot: Bot) -> None:
    await _relay_media(message, bot, "voice", message.voice.file_id)


@router.message(InActiveChat(), F.video_note)
async def relay_video_note(message: Message, bot: Bot) -> None:
    await _relay_media(message, bot, "video_note", message.video_note.file_id)


@router.message(InActiveChat(), F.text, ~F.text.startswith("/"))
async def relay_text(message: Message, bot: Bot) -> None:
    async with async_session() as session:
        sess = await chat_service.get_active_session(session, message.from_user.id)
        if not sess:
            return
        other = chat_service.other_user(sess, message.from_user.id)
        if await chat_service.is_blocked(session, other, message.from_user.id):
            await message.answer("⛔ این کاربر تو را بلاک کرده؛ پیام ارسال نشد.")
            return
        await chat_service.record_message(session, sess.id, message.from_user.id, "text", text=message.text)
        await session.commit()
    try:
        await bot.send_message(other, f"💬 {message.text}")
    except Exception:
        await message.answer("⚠️ ارسالِ پیام ممکن نشد (شاید طرف ربات را بسته).")


@router.message(InActiveChat())
async def relay_reject(message: Message) -> None:
    await message.answer("❌ فقط متن، عکس، ویس و ویدیو‌مسیج در چت مجاز است (آهنگ/فیلم مجاز نیست).")


# =========================== حالتِ ادمین (فعال‌سازیِ اولیه) ===========================
@router.message(F.text == "ادمین مود", PRIV)
async def admin_mode(message: Message, state: FSMContext) -> None:
    uid = message.from_user.id
    if uid not in ADMIN_IDS and uid != (settings.creator_id or -1):
        return  # مخفی: برایِ غیرِ ادمین نادیده گرفته می‌شود
    if not settings.admin_password:
        await message.answer("⚙️ رمزِ ادمین (ADMIN_PASSWORD) در تنظیمات تعریف نشده.")
        return
    await state.set_state(ChatStates.admin_password)
    await message.answer(
        "🔐 رمزِ ادمین را وارد کن:" + CANCEL_HINT,
    )


@router.message(ChatStates.admin_password, PRIV)
async def admin_password(message: Message, state: FSMContext) -> None:
    if await handle_cancel_word(message, state):
        return
    await state.clear()
    uid = message.from_user.id
    ok = (
        message.text == settings.admin_password
        and (settings.creator_id is None or uid == settings.creator_id)
        and (uid in ADMIN_IDS or uid == settings.creator_id)
    )
    if ok:
        chat_service.ADMIN_ACTIVE.add(uid)
        await message.answer("✅ حالتِ ادمین فعال شد. (پنلِ کامل در مرحله‌ی پایانی طراحی می‌شود)")
    else:
        await message.answer("❌ رمز یا شناسه نادرست است.")


@router.message(F.text == "دیدن گزارش‌ها", PRIV)
async def view_reports(message: Message) -> None:
    uid = message.from_user.id
    if uid != MAIN_ADMIN_ID or uid not in chat_service.ADMIN_ACTIVE:
        return
    async with async_session() as session:
        reports = (await session.execute(
            select(ChatReport).where(ChatReport.status == "open").order_by(ChatReport.created_at.desc())
        )).scalars().all()
    if not reports:
        await message.answer("📭 گزارشِ بازی نیست.")
        return
    lines = ["🚨 <b>گزارش‌ها</b>", ""]
    for r in reports[:30]:
        lines.append(f"#{r.id} — از <code>{r.reporter_id}</code> علیه <code>{r.reported_id}</code>: {r.reason}")
    await message.answer("\n".join(lines))
