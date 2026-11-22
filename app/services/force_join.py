# -*- coding: utf-8 -*-
"""عضویت اجباری در کانال‌ها — v1.7.7.3"""
from __future__ import annotations

import json
import time
from typing import Any

from app.services.admin_service import get_setting, set_setting

SETTING_ENABLED = "force_join_enabled"
SETTING_CHANNELS = "force_join_channels"

# 🔇 v1.7.8.13 — داخلِ گروه هیچ پیامی فرستاده نمی‌شود؛ پیامِ کاربر فقط نادیده گرفته می‌شود.
GROUP_SILENT = True

# هر کاربر در گروه حداکثر هر ۳۰ دقیقه یک بار هشدار بگیرد
GROUP_NUDGE_COOLDOWN_SEC = 30 * 60
_group_nudge_at: dict[int, float] = {}

# 🐞 v1.7.8.13 — کشِ عضویت. قبلاً هر پیامِ گروه به‌ازای هر کانال یک
# get_chat_member به تلگرام می‌زد (اسپمِ API و ریسکِ خطای 429).
MEMBER_CACHE_OK_SEC = 300     # عضوِ همهٔ کانال‌ها → ۵ دقیقه کش
MEMBER_CACHE_MISS_SEC = 60    # هنوز عضو نیست → ۱ دقیقه کش
MEMBER_CACHE_DEGRADED_SEC = 30  # خطای سمتِ ربات/تلگرام → کشِ کوتاه
_member_cache: dict[int, tuple[float, bool, list]] = {}


def invalidate_user(user_id) -> None:
    """کشِ عضویتِ یک کاربر را پاک می‌کند (مثلاً بعد از «✅ عضو شدم»)."""
    try:
        _member_cache.pop(int(user_id), None)
    except Exception:
        pass


def invalidate_all() -> None:
    """کشِ همه را پاک می‌کند (بعد از تغییرِ لیستِ کانال‌ها یا روشن/خاموش شدن)."""
    _member_cache.clear()


async def is_enabled(session) -> bool:
    return (await get_setting(session, SETTING_ENABLED)) == "1"


async def set_enabled(session, enabled: bool, commit: bool = True) -> None:
    await set_setting(session, SETTING_ENABLED, "1" if enabled else "0", commit=commit)
    invalidate_all()


def _norm_channel(item: dict) -> dict[str, Any] | None:
    if not isinstance(item, dict):
        return None
    try:
        cid = int(item.get("id"))
    except Exception:
        return None
    mode = str(item.get("link_mode") or "auto").lower()
    if mode not in ("public", "private", "auto"):
        mode = "auto"
    un = item.get("username")
    inv = item.get("invite_link")
    return {
        "id": cid,
        "title": str(item.get("title") or cid)[:128],
        "username": (str(un).lstrip("@") if un else None),
        "invite_link": (str(inv).strip() if inv else None),
        "link_mode": mode,
    }


async def list_channels(session) -> list[dict[str, Any]]:
    raw = await get_setting(session, SETTING_CHANNELS)
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except Exception:
        return []
    if not isinstance(data, list):
        return []
    out = []
    for item in data:
        ch = _norm_channel(item)
        if ch:
            out.append(ch)
    return out


async def get_channel(session, chat_id: int) -> dict[str, Any] | None:
    cid = int(chat_id)
    for ch in await list_channels(session):
        if int(ch["id"]) == cid:
            return ch
    return None


async def save_channels(session, channels: list[dict], commit: bool = True) -> None:
    clean = []
    for c in channels:
        ch = _norm_channel(c)
        if ch:
            clean.append(ch)
    await set_setting(
        session,
        SETTING_CHANNELS,
        json.dumps(clean, ensure_ascii=False),
        commit=commit,
    )
    # 🐞 v1.7.8.13 — لیستِ کانال‌ها عوض شد → کشِ عضویت دیگر معتبر نیست.
    invalidate_all()


async def add_channel(
    session,
    chat_id: int,
    title=None,
    username=None,
    invite_link=None,
    link_mode: str | None = None,
    commit=True,
):
    channels = await list_channels(session)
    mode = (link_mode or "auto").lower()
    if mode not in ("public", "private", "auto"):
        mode = "auto"
    for c in channels:
        if int(c["id"]) == int(chat_id):
            if title:
                c["title"] = str(title)[:128]
            if username:
                c["username"] = str(username).lstrip("@")
            if invite_link:
                c["invite_link"] = str(invite_link).strip()
            if link_mode:
                c["link_mode"] = mode
            # auto: public if username else private
            if c.get("link_mode") == "auto":
                c["link_mode"] = "public" if c.get("username") else "private"
            await save_channels(session, channels, commit=commit)
            return True, "کانال به‌روز شد."
    if mode == "auto":
        mode = "public" if username else "private"
    channels.append(
        {
            "id": int(chat_id),
            "title": (str(title) if title else str(chat_id))[:128],
            "username": (str(username).lstrip("@") if username else None),
            "invite_link": (str(invite_link).strip() if invite_link else None),
            "link_mode": mode,
        }
    )
    await save_channels(session, channels, commit=commit)
    return True, "کانال اضافه شد."


async def update_channel(session, chat_id: int, **fields) -> bool:
    channels = await list_channels(session)
    found = False
    for c in channels:
        if int(c["id"]) != int(chat_id):
            continue
        found = True
        if "title" in fields and fields["title"] is not None:
            c["title"] = str(fields["title"])[:128]
        if "username" in fields:
            un = fields["username"]
            c["username"] = (str(un).lstrip("@") if un else None)
        if "invite_link" in fields:
            inv = fields["invite_link"]
            c["invite_link"] = (str(inv).strip() if inv else None)
        if "link_mode" in fields and fields["link_mode"] is not None:
            mode = str(fields["link_mode"]).lower()
            if mode in ("public", "private", "auto"):
                c["link_mode"] = mode
        break
    if not found:
        return False
    await save_channels(session, channels, commit=fields.get("commit", True))
    return True


async def set_link_mode(session, chat_id: int, mode: str, commit: bool = True) -> bool:
    mode = str(mode).lower()
    if mode not in ("public", "private"):
        return False
    return await update_channel(session, chat_id, link_mode=mode, commit=commit)


async def remove_channel(session, chat_id: int, commit: bool = True) -> bool:
    channels = await list_channels(session)
    new = [c for c in channels if int(c["id"]) != int(chat_id)]
    if len(new) == len(channels):
        return False
    await save_channels(session, new, commit=commit)
    return True


def channel_link(ch: dict) -> str | None:
    """لینک عضویت بر اساس حالت عمومی/خصوصی."""
    mode = str(ch.get("link_mode") or "auto").lower()
    un = ch.get("username")
    inv = ch.get("invite_link")
    if mode == "public":
        if un:
            return "https://t.me/" + str(un).lstrip("@")
        # fallback
        return str(inv) if inv else None
    if mode == "private":
        if inv:
            return str(inv)
        if un:
            return "https://t.me/" + str(un).lstrip("@")
        return None
    # auto
    if un:
        return "https://t.me/" + str(un).lstrip("@")
    if inv:
        return str(inv)
    return None


def link_mode_label(ch: dict) -> str:
    mode = str(ch.get("link_mode") or "auto").lower()
    if mode == "public":
        return "🌐 عمومی"
    if mode == "private":
        return "🔐 خصوصی"
    return "⚙️ خودکار"


def _is_user_side_error(err: Exception) -> bool:
    """خطا یعنی «خودِ کاربر عضو نیست» یا یعنی «ربات به کانال دسترسی ندارد»؟

    🐞 v1.7.8.13 — قبلاً هر خطایی (قطعیِ شبکه، 429، ادمین‌نبودنِ ربات،
    حذفِ کانال) به‌معنیِ «عضو نیست» گرفته می‌شد و همهٔ بازیکن‌ها از کلِ
    ربات قفل می‌شدند. حالا فقط خطاهای مربوط به خودِ کاربر قفل می‌کنند.
    """
    msg = str(err or "").lower()
    return any(
        k in msg
        for k in ("user not found", "user_not_participant", "participant_id_invalid")
    )


async def check_user(bot, session, user_id: int, use_cache: bool = True):
    uid = int(user_id)
    now = time.time()
    if use_cache:
        hit = _member_cache.get(uid)
        if hit and hit[0] > now:
            return hit[1], list(hit[2])

    if not await is_enabled(session):
        _member_cache[uid] = (now + MEMBER_CACHE_OK_SEC, True, [])
        return True, []
    channels = await list_channels(session)
    if not channels:
        _member_cache[uid] = (now + MEMBER_CACHE_OK_SEC, True, [])
        return True, []

    missing: list = []
    degraded = False  # خطای سمتِ ربات/تلگرام → کاربر را قفل نکن
    for ch in channels:
        cid = int(ch["id"])
        try:
            member = await bot.get_chat_member(cid, uid)
            status = str(getattr(getattr(member, "status", None), "value", getattr(member, "status", "")) or "").lower()
            if status in ("left", "kicked"):
                missing.append(ch)
        except Exception as e:
            if _is_user_side_error(e):
                missing.append(ch)
            else:
                degraded = True

    ok = (len(missing) == 0)
    if degraded:
        ttl = MEMBER_CACHE_DEGRADED_SEC
    else:
        ttl = MEMBER_CACHE_OK_SEC if ok else MEMBER_CACHE_MISS_SEC
    _member_cache[uid] = (now + ttl, ok, list(missing))
    return ok, missing


async def is_game_player(session, user_id: int) -> bool:
    """فقط بازیکن ثبت‌شده در بازی — نه هر عضو گروه."""
    try:
        from sqlalchemy import select
        from app.models.player import Player

        row = await session.scalar(
            select(Player.tg_user_id).where(Player.tg_user_id == int(user_id)).limit(1)
        )
        return row is not None
    except Exception:
        return False


def can_nudge_in_group(user_id: int) -> bool:
    now = time.time()
    last = _group_nudge_at.get(int(user_id), 0.0)
    return (now - last) >= GROUP_NUDGE_COOLDOWN_SEC


def mark_group_nudge(user_id: int) -> None:
    _group_nudge_at[int(user_id)] = time.time()


def try_nudge_in_group(user_id: int) -> bool:
    """چک و ثبتِ کول‌داون در یک قدمِ اتمیک.

    🐞 v1.7.8.13 — قبلاً اول can_nudge_in_group() چک می‌شد، بعد await ارسالِ
    پیام انجام می‌شد و تازه بعدش mark_group_nudge() صدا زده می‌شد.
    چون بینِ «چک» و «ثبت» یک await وجود داشت، پیام‌های پشتِ‌همِ کاربر
    همگی از شرط رد می‌شدند و محدودیتِ ۳۰ دقیقه عملاً بی‌اثر می‌شد → اسپم.
    همچنین اگر ارسال خطا می‌داد، ثبت انجام نمی‌شد و هر پیامِ بعدی دوباره
    تلاش می‌کرد. حالا اول جا رزرو می‌شود، بعد ارسال.
    """
    now = time.time()
    uid = int(user_id)
    last = _group_nudge_at.get(uid, 0.0)
    if (now - last) < GROUP_NUDGE_COOLDOWN_SEC:
        return False
    _group_nudge_at[uid] = now
    return True


def missing_text(missing: list[dict]) -> str:
    """پیام داخل ربات — فقط اسم کانال؛ لینک فقط روی دکمه."""
    lines = [
        "🔒 <b>عضویت اجباری</b>",
        "",
        "برای استفاده از ربات باید اول در کانال‌های زیر عضو شوی:",
        "",
    ]
    for i, ch in enumerate(missing, 1):
        title = ch.get("title") or ch.get("id")
        lines.append(f"{i}) <b>{title}</b>")
    lines += ["", "از دکمه‌های زیر عضو شو، بعد «✅ عضو شدم» را بزن."]
    return "\n".join(lines)


def group_nudge_text() -> str:
    """پیام کوتاه گروه — بدون لینک کانال."""
    return (
        "🔒 برای ادامه بازی باید اول عضویت اجباری را داخل <b>ربات</b> فعال کنی.\n"
        "به پیوی ربات سر بزن و عضو کانال‌ها شو."
    )


def join_keyboard(missing: list[dict]):
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    kb = InlineKeyboardBuilder()
    for ch in missing:
        link = channel_link(ch)
        title = str(ch.get("title") or "کانال")[:40]
        if link:
            kb.button(text=f"📢 {title}", url=link)
    kb.button(text="✅ عضو شدم — بررسی دوباره", callback_data="fj:recheck")
    kb.adjust(1)
    return kb.as_markup()
