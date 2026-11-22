# -*- coding: utf-8 -*-
"""هوکِ مرکزیِ ارزیابیِ القاب — v1.7.6: فقط صف تأیید، بدون تبریکِ زودهنگام."""
from __future__ import annotations

import time

_LAST: dict[int, float] = {}
_THROTTLE = 120.0


def _due(uid: int) -> bool:
    now = time.time()
    last = _LAST.get(uid, 0.0)
    if now - last < _THROTTLE:
        return False
    _LAST[uid] = now
    return True


async def check(session, uid: int, force: bool = False) -> list:
    """ارزیابی؛ خروجی = لقب‌هایی که تازه‌وارد صف تأیید شدند (هنوز اعطا نشده)."""
    uid = int(uid or 0)
    if uid <= 0:
        return []
    if not force and not _due(uid):
        return []
    try:
        from sqlalchemy import select
        from app.models.player import Player
        if await session.scalar(select(Player.tg_user_id).where(Player.tg_user_id == uid)) is None:
            return []
    except Exception:
        return []
    newly: list = []
    try:
        from app.services.stats_bridge import sync_and_evaluate
        newly = list(await sync_and_evaluate(session, uid) or [])
        await session.commit()
    except Exception:
        try:
            await session.rollback()
        except Exception:
            pass
        newly = []
    try:
        from app.data import titles as title_data
        from app.services import title_season
        for winner_uid, title_key in await title_season.weekly_unique_candidates(session, title_data.TITLES):
            if await title_season.queue(session, winner_uid, title_key, source="weekly_unique"):
                item = title_data.get_title(title_key)
                if winner_uid == uid and item:
                    newly.append(item)
        await session.commit()
    except Exception:
        pass
    # مهم: هیچ congrats / announce اینجا نیست — فقط بعد از approve ادمین
    return newly


async def announce_titles(session, uid: int, newly: list) -> None:
    """فقط پس از تأیید ادمین صدا زده شود."""
    if not newly:
        return
    try:
        from app.services import news_service
    except Exception:
        return
    name = None
    try:
        from sqlalchemy import select
        from app.models.player import Player
        pl = await session.scalar(select(Player).where(Player.tg_user_id == uid))
        if pl is not None:
            uname = (getattr(pl, "username", None) or "").strip()
            base = (getattr(pl, "name", None) or "").strip() or (f"@{uname}" if uname else None)
            name = f"{base} (<code>{uid}</code>)" if base else f"کاربر <code>{uid}</code>"
    except Exception:
        name = None
    who = name or "یکی از اعضای خانواده"
    added = False
    for t in newly:
        title_name = t.get("name") if isinstance(t, dict) else None
        if not title_name:
            continue
        try:
            await news_service.add_news(
                session,
                category="title",
                text=f"🎖️ {who} لقبِ «{title_name}» را کسب کرد.",
                actor_id=uid,
                commit=False,
            )
            added = True
        except Exception:
            continue
    if added:
        try:
            await session.commit()
        except Exception:
            try:
                await session.rollback()
            except Exception:
                pass


def congrats_text(newly: list) -> str:
    if not newly:
        return ""
    rows = []
    for t in newly:
        bonus = t.get("bonus") or {}
        extra = "، ".join(f"+{v}٪ {k.replace('_pct', '')}" for k, v in bonus.items())
        rows.append(f"🎖️ <b>{t['name']}</b>" + (f" ({extra})" if extra else ""))
    head = "🎉 <b>لقبِ تازه گرفتی!</b>" if len(rows) == 1 else "🎉 <b>لقب‌هایِ تازه گرفتی!</b>"
    return head + "\n" + "\n".join(rows) + "\n\n💡 از بخشِ «القاب» می‌توانی فعالش کنی."


def queued_text(newly: list) -> str:
    if not newly:
        return ""
    rows = [f"• {t.get('name')}" for t in newly if isinstance(t, dict) and t.get("name")]
    return "📝 درخواست لقب در صف تأیید ادمین:\n" + "\n".join(rows) + "\n\n⏳ تا تأیید، لقب فعال نیست."
