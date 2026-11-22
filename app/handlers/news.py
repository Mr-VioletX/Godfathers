# -*- coding: utf-8 -*-
"""هندلرِ «اخبارِ روزانه» (مرحله ۲۰).

نمایشِ تازه‌ترین اخبار و پیش‌نمایشِ خلاصه‌ی امروز؛ انتشارِ خودکار در news_ticker.
"""
from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.types import CallbackQuery, Message

from app.database.engine import async_session
from app.data import news as N
from app.services import news_service
from app.keyboards.news_menu import news_home_menu, news_back_menu
from app.keyboards.main_menu import BTN_NEWS, WORD_NEWS
from app.utils.ui import ensure_owner, safe_edit

router = Router()


async def _home_text() -> str:
    return "\n".join([
        "📰 <b>اخبارِ روزانه‌ی بازی</b>",
        "",
        f"هر شب ساعتِ <b>{N.POST_HOUR:02d}:{N.POST_MINUTE:02d}</b> به وقتِ تهران، خلاصه‌یِ مهم‌ترین رویدادهای بازی منتشر می‌شود:",
        "⚔️ نتیجه‌ی جنگ‌ها • 🏷️ کسبِ القابِ ویژه • 🤝 اتحادیه‌ها • 💰 اقتصاد",
        "",
        "🔔 دارندگانِ اشتراکِ نقره‌ای/طلایی یا دستیارِ سطح ۴، خلاصه را خصوصی هم دریافت می‌کنند.",
    ])


@router.message(StateFilter(None), F.text.in_({BTN_NEWS, WORD_NEWS}))   # 🔄 مرحله ۲۱.۱ — تطبیقِ دقیق
async def news_button(message: Message):
    await message.answer(await _home_text(), reply_markup=news_home_menu(message.from_user.id))


@router.callback_query(F.data.startswith("menu:news"))
async def news_menu_cb(callback: CallbackQuery):
    if not await ensure_owner(callback):
        return
    await safe_edit(callback.message, await _home_text(), news_home_menu(callback.from_user.id))
    await callback.answer()


@router.callback_query(F.data.startswith("news:latest"))
async def news_latest_cb(callback: CallbackQuery):
    if not await ensure_owner(callback):
        return
    async with async_session() as session:
        # 🆕 v1.7.5 — اگر news_items خالی بود، از جنگ‌های زنده پر کن
        try:
            from app.services.game_digest import collect_live_events

            live = await collect_live_events(session, hours=48, limit=12)
        except Exception:
            live = []
        items = await news_service.recent_news(session, limit=10)
    if live:
        lines = ["📰 <b>تازه‌ترین رویدادهای بازی:</b>", ""]
        lines += ["• " + N.format_item(it.get("category"), it.get("text", "")) for it in live[:10]]
        text = "\n".join(lines)
    elif not items:
        text = (
            "📰 فعلاً خبرِ ذخیره‌شده‌ای نیست.\n"
            "با انجام جنگ، کسب لقب و رویدادهای مهم اینجا پر می‌شود."
        )
    else:
        lines = ["📰 <b>تازه‌ترین اخبار:</b>", ""]
        lines += ["• " + N.format_item(it.category, it.text) for it in items]
        text = "\n".join(lines)
    await safe_edit(callback.message, text, news_back_menu(callback.from_user.id))
    await callback.answer()


@router.callback_query(F.data.startswith("news:digest"))
async def news_digest_cb(callback: CallbackQuery):
    if not await ensure_owner(callback):
        return
    async with async_session() as session:
        # 🆕 v1.7.5 — خلاصه زنده (جنگ‌ها + اخبار ثبت‌شده)
        try:
            from app.services.game_digest import build_game_digest

            text, _ = await build_game_digest(session, hours=24, mark_published=False)
        except Exception:
            text, _ = await news_service.compile_daily_digest(session, mark_published=False)
    await safe_edit(callback.message, text, news_back_menu(callback.from_user.id))
    await callback.answer()


@router.callback_query(F.data.startswith("news:dg:"))
async def news_digest_page_cb(callback: CallbackQuery):
    """پیمایشِ صفحه‌های خلاصه‌ی روزانه (پیامِ کانال/خصوصی) — بدونِ محدودیتِ مالک (v1.7.9.1)."""
    parts = (callback.data or "").split(":")
    try:
        post_id = int(parts[2])
        page = int(parts[3])
    except (IndexError, ValueError):
        await callback.answer()
        return
    import json as _json

    from app.keyboards.news_menu import news_digest_menu
    from app.models.news import NewsDigestPost
    async with async_session() as session:
        post = await session.get(NewsDigestPost, post_id)
    try:
        pages = _json.loads(post.pages_json) if post else []
    except Exception:
        pages = []
    if not pages or page < 0 or page >= len(pages):
        await callback.answer("این خلاصه منقضی شده است.", show_alert=True)
        return
    await safe_edit(callback.message, pages[page], news_digest_menu(post_id, page, len(pages)))
    await callback.answer()
