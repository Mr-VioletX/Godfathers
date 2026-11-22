# -*- coding: utf-8 -*-
from __future__ import annotations
from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message

# هم‌تراز با CONTROL_SECTIONS ادمین و منوی اصلی بازی
SECTION_PREFIXES = {
    "theft": ("menu:theft", "theft:"),
    "base": ("menu:base", "base:"),
    "estate": ("menu:estate", "est:", "estate:"),
    "factory": ("menu:market", "menu:factory", "fp:", "factory", "market:"),
    "warehouse": ("menu:warehouse", "wh:"),
    "city": ("menu:city", "city:"),
    "war": ("menu:war", "war:", "country:", "capture:"),
    "military": ("menu:military", "mil:"),
    "bank": ("menu:worldbank", "menu:bank", "bank:", "wb:"),
    "brand": ("menu:branding", "brd:", "brand:"),
    "sports": ("menu:sports", "sports:"),
    "alliance": ("menu:alliance", "al:", "alliance:"),
    "spy": ("menu:spy", "spy:"),
    "transfer": ("transfer:",),
    "assistant": ("menu:assistant", "assistant:", "assistant2:"),
    "titles": ("menu:titles", "titles:"),
    "subscription": ("menu:sub", "sub:"),
    "news": ("menu:news", "news:"),
    "ranking": ("menu:ranking", "rank:"),
    "chat": ("menu:chat", "chat:", "cm:"),
    "photo": ("profile:edit_photo", "assistant:edit:photo", "assistant2:photo"),
}

TEXT_SECTIONS = {
    "theft": ("دزدی",),
    "base": ("پایگاه",),
    "estate": ("عمارت",),
    "factory": ("بازار", "کارخانه"),
    "warehouse": ("انبار",),
    "city": ("شهر",),
    "war": ("جنگ",),
    "military": ("نظامی",),
    "bank": ("بانک",),
    "brand": ("برند", "هولدینگ"),
    "sports": ("ورزش",),
    "alliance": ("اتحادیه",),
    "spy": ("جاسوس", "جاسوسی"),
    "transfer": ("انتقال",),
    "assistant": ("دستیار",),
    "titles": ("القاب",),
    "subscription": ("اشتراک",),
    "news": ("اخبار",),
    "ranking": ("رنکینگ",),
    "chat": ("چت مود", "خطِ محرمانه"),
}


def _section_for_event(event):
    if isinstance(event, CallbackQuery):
        data = event.data or ""
        if data.startswith("adm:") or data.startswith("fj:"):
            return None
        for sec, prefs in SECTION_PREFIXES.items():
            if any(data.startswith(p) for p in prefs):
                return sec
    if isinstance(event, Message):
        txt = event.text or ""
        for sec, needles in TEXT_SECTIONS.items():
            if any(n in txt for n in needles):
                return sec
    return None


class AdminControlMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data: dict):
        sec = _section_for_event(event)
        user = getattr(event, "from_user", None)
        if sec and user:
            try:
                from sqlalchemy import select, or_
                from app.database.engine import async_session
                from app.models.admin import GameRestriction
                async with async_session() as session:
                    rule = await session.scalar(select(GameRestriction).where(
                        GameRestriction.active == True,
                        GameRestriction.section == sec,
                        or_(GameRestriction.tg_user_id == None, GameRestriction.tg_user_id == int(user.id))
                    ).order_by(GameRestriction.tg_user_id.desc(), GameRestriction.id.desc()))
                if rule is not None:
                    # 🆕 v1.7.9.6 — بای‌پس تست‌کننده برای بخش‌های خاموشِ سراسری
                    _bypass = False
                    if rule.tg_user_id is None:
                        try:
                            from app.services.restrictions import is_tester
                            _bypass = await is_tester(session, int(user.id))
                        except Exception:
                            _bypass = False
                    if not _bypass:
                        reason = ("\nعلت: " + str(rule.reason)) if rule.reason else ""
                        msg = "⛔ این بخش فعلاً توسط ادمین محدود شده است." + reason
                        if isinstance(event, CallbackQuery):
                            await event.answer(msg, show_alert=True)
                        else:
                            await event.answer(msg)
                        return
            except Exception:
                pass
        return await handler(event, data)
