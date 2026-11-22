# app/services/chat_service.py
"""سرویسِ کمکیِ چت‌مود (مرحله ۱۳.۶).

شاملِ تشخیصِ آنلاین/آفلاین، بررسیِ بلاک، مدیریتِ جلسه، ثبتِ پیام،
و ساختِ آرشیوِ ZIP+HTML و ذخیره در چنلِ خصوصی.
"""
import html
import logging
import os
import shutil
import tempfile
import zipfile
from datetime import datetime, timedelta

from aiogram import Bot
from aiogram.types import FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import func, or_, select

from app.config import settings
from app.database.engine import async_session
from app.models.chat import (
    BlockedUser,
    ChatMessage,
    ChatRequest,
    ChatSession,
    OfflineMessage,
)
from app.models.player import Player

log = logging.getLogger(__name__)

ONLINE_THRESHOLD = timedelta(minutes=5)   # فعال طیِ ۵ دقیقه‌ی اخیر = آنلاین
REQUEST_TTL = timedelta(minutes=5)        # مهلتِ درخواستِ چت
ALLOWED_MEDIA = {"photo", "voice", "video_note"}

# مجموعه‌یِ درون‌حافظه‌ایِ ادمین‌هایِ فعال (فعال‌سازیِ اولیه‌یِ حالتِ ادمین)
ADMIN_ACTIVE: set[int] = set()


async def get_player(session, uid: int) -> Player | None:
    return (await session.execute(
        select(Player).where(Player.tg_user_id == uid)
    )).scalar_one_or_none()


def is_online(player: Player | None, now: datetime | None = None) -> bool:
    if player is None or player.last_seen is None:
        return False
    now = now or datetime.utcnow()
    return (now - player.last_seen) <= ONLINE_THRESHOLD


async def is_blocked(session, blocker_id: int, blocked_id: int) -> bool:
    """آیا blocker_id کاربرِ blocked_id را بلاک کرده است؟"""
    row = (await session.execute(
        select(BlockedUser.id).where(
            BlockedUser.owner_id == blocker_id,
            BlockedUser.blocked_id == blocked_id,
        )
    )).first()
    return row is not None


async def block_user(session, owner_id: int, blocked_id: int) -> None:
    if not await is_blocked(session, owner_id, blocked_id):
        session.add(BlockedUser(owner_id=owner_id, blocked_id=blocked_id))
        await session.commit()


async def get_active_session(session, uid: int) -> ChatSession | None:
    return (await session.execute(
        select(ChatSession).where(
            ChatSession.active.is_(True),
            or_(ChatSession.user_a == uid, ChatSession.user_b == uid),
        )
    )).scalars().first()


def other_user(sess: ChatSession, uid: int) -> int:
    return sess.user_b if sess.user_a == uid else sess.user_a


async def record_message(session, session_id: int, from_id: int, kind: str,
                         text: str | None = None, file_id: str | None = None,
                         channel_msg_id: int | None = None) -> None:
    session.add(ChatMessage(
        session_id=session_id, from_id=from_id, kind=kind,
        text=text, file_id=file_id, channel_msg_id=channel_msg_id,
    ))


async def notify_unread_on_start(message) -> None:
    """هنگامِ /start: اگر پیامِ خوانده‌نشده یا درخواستِ معلق بود، اطلاع بده."""
    uid = message.from_user.id
    async with async_session() as session:
        n_off = (await session.execute(
            select(func.count()).select_from(OfflineMessage).where(
                OfflineMessage.to_id == uid, OfflineMessage.is_read.is_(False)
            )
        )).scalar() or 0
        n_req = (await session.execute(
            select(func.count()).select_from(ChatRequest).where(
                ChatRequest.target_id == uid, ChatRequest.status == "pending"
            )
        )).scalar() or 0
    if n_off or n_req:
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="📨 نمایش", callback_data=f"chat:unread:{uid}")
        ]])
        await message.answer(
            f"📨 تو <b>{n_off}</b> پیامِ خوانده‌نشده و <b>{n_req}</b> درخواستِ چت داری.",
            reply_markup=kb,
        )


# ---------------------------------------------------------------------------
# آرشیوِ چت: ZIP (متن + رسانه‌ها به‌ترتیب + HTML) → چنلِ خصوصی
# ---------------------------------------------------------------------------
def _html_bubble(who: str, ts: str, body: str, media_file: str | None, kind: str | None) -> str:
    media_html = ""
    if media_file:
        if kind == "photo":
            media_html = f'<img src="media/{media_file}" style="max-width:260px;border-radius:8px;">'
        elif kind == "voice":
            media_html = f'<audio controls src="media/{media_file}"></audio>'
        elif kind == "video_note":
            media_html = f'<video controls width="260" src="media/{media_file}"></video>'
    return (
        '<div class="msg">'
        f'<div class="meta"><b>{html.escape(who)}</b> <span>{html.escape(ts)}</span></div>'
        f'<div class="body">{body}</div>'
        f'{media_html}'
        '</div>'
    )


def _html_page(sess: ChatSession, names: dict, items: list) -> str:
    a = html.escape(names.get(sess.user_a, str(sess.user_a)))
    b = html.escape(names.get(sess.user_b, str(sess.user_b)))
    body = "\n".join(items)
    return (
        '<!DOCTYPE html><html lang="fa" dir="rtl"><head><meta charset="utf-8">'
        f'<title>آرشیوِ چت #{sess.id}</title>'
        '<style>body{font-family:Tahoma,sans-serif;background:#e5ddd5;padding:16px;}'
        '.msg{background:#fff;border-radius:8px;padding:8px 12px;margin:8px 0;max-width:70%;}'
        '.meta{font-size:12px;color:#888;margin-bottom:4px;}'
        '.body{white-space:pre-wrap;font-size:14px;color:#111;}'
        'h2{color:#075e54;}</style></head><body>'
        f'<h2>آرشیوِ چت #{sess.id} — {a} ↔ {b}</h2>'
        f'{body}'
        '</body></html>'
    )


async def store_archive(bot: Bot, sess: ChatSession, messages: list, names: dict) -> int | None:
    """یک ZIP شاملِ transcript.txt + رسانه‌های به‌ترتیب + chat.html می‌سازد
    و در چنلِ آرشیو می‌فرستد. خروجی: message_id فایلِ آرشیو یا None.
    """
    if not settings.archive_channel_id:
        return None
    tmpdir = tempfile.mkdtemp(prefix="chat_")
    try:
        transcript_lines: list[str] = []
        media_files: list[str] = []
        html_items: list[str] = []
        seq = 0
        for m in messages:
            ts = m.created_at.strftime("%Y-%m-%d %H:%M:%S") if m.created_at else ""
            who = names.get(m.from_id, str(m.from_id))
            if m.kind == "text":
                transcript_lines.append(f"[{ts}] {who}: {m.text or ''}")
                html_items.append(_html_bubble(who, ts, html.escape(m.text or ""), None, None))
            else:
                seq += 1
                ext = {"voice": "ogg", "video_note": "mp4", "photo": "jpg"}.get(m.kind, "bin")
                fname = f"{seq:03d}_{m.kind}.{ext}"
                ok = False
                if m.file_id:
                    try:
                        await bot.download(m.file_id, destination=os.path.join(tmpdir, fname))
                        media_files.append(fname)
                        ok = True
                    except Exception as e:
                        log.warning("archive download failed: %s", e)
                transcript_lines.append(f"[{ts}] {who}: <{m.kind}: {fname if ok else 'دانلود نشد'}>")
                html_items.append(_html_bubble(who, ts, f"[{m.kind}]", fname if ok else None, m.kind))

        with open(os.path.join(tmpdir, "transcript.txt"), "w", encoding="utf-8") as f:
            f.write("\n".join(transcript_lines))
        with open(os.path.join(tmpdir, "chat.html"), "w", encoding="utf-8") as f:
            f.write(_html_page(sess, names, html_items))

        zip_path = os.path.join(tmpdir, f"chat_session_{sess.id}.zip")
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(os.path.join(tmpdir, "transcript.txt"), "transcript.txt")
            zf.write(os.path.join(tmpdir, "chat.html"), "chat.html")
            for fn in media_files:
                zf.write(os.path.join(tmpdir, fn), f"media/{fn}")

        a = names.get(sess.user_a, str(sess.user_a))
        b = names.get(sess.user_b, str(sess.user_b))
        caption = f"🗂️ آرشیوِ چت #{sess.id}\n{a} ↔ {b}"
        sent = await bot.send_document(settings.archive_channel_id, FSInputFile(zip_path), caption=caption)
        return sent.message_id
    except Exception as e:
        log.exception("store_archive failed: %s", e)
        return None
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
