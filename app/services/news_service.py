# -*- coding: utf-8 -*-
"""سرویسِ «اخبارِ روزانه» (مرحله ۲۰).

ثبت، خواندن و تهیه‌ی خلاصه‌یِ روزانه‌ی اخبار.
دیگر سرویس‌ها (جنگ، القاب، اتحادیه) می‌توانند add_news را صدا بزنند.
"""
from datetime import datetime, timedelta

from sqlalchemy import select, desc

from app.models.news import NewsItem
from app.data import news as N


async def add_news(
    session,
    category: str,
    text: str,
    importance: int | None = None,
    actor_id: int | None = None,
    commit: bool = True,
) -> NewsItem:
    """یک خبرِ جدید ثبت می‌کند."""
    if category not in N.CATEGORIES:
        category = N.DEFAULT_CATEGORY
    if importance is None:
        importance = N.default_importance(category)
    item = NewsItem(
        category=category,
        text=text[:500],
        importance=importance,
        actor_id=actor_id,
        published=False,
    )
    session.add(item)
    if commit:
        await session.commit()
    else:
        await session.flush()
    return item


async def recent_news(session, limit: int = 10) -> list:
    """تازه‌ترین اخبار (نزولی بر اساسِ زمان)."""
    result = await session.execute(
        select(NewsItem).order_by(desc(NewsItem.created_at)).limit(limit)
    )
    return list(result.scalars().all())


async def items_since(session, since: datetime, only_unpublished: bool = False) -> list:
    """اخبارِ ثبت‌شده از یک زمان به بعد."""
    stmt = select(NewsItem).where(NewsItem.created_at >= since)
    if only_unpublished:
        stmt = stmt.where(NewsItem.published == False)  # noqa: E712
    stmt = stmt.order_by(desc(NewsItem.importance), desc(NewsItem.created_at))
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def compile_daily_digest(session, mark_published: bool = True) -> tuple[str, int]:
    """خلاصه‌یِ ۲۴ ساعتِ گذشته را می‌سازد و (اختیاری) آیتم‌ها را published می‌کند.

    خروجی: (متنِ خلاصه، تعدادِ آیتم).
    🆕 v1.7.5: اگر news_items خالی باشد، از جنگ‌های زنده digest ساخته می‌شود.
    """
    since = datetime.utcnow() - timedelta(hours=N.DIGEST_LOOKBACK_HOURS)
    items = await items_since(session, since, only_unpublished=True)
    if items:
        text = N.compile_digest(items)
        if mark_published:
            for it in items:
                it.published = True
            await session.commit()
        return text, len(items)
    # fallback زنده
    try:
        from app.services.game_digest import build_game_digest

        return await build_game_digest(session, hours=N.DIGEST_LOOKBACK_HOURS, mark_published=False)
    except Exception:
        text = N.compile_digest([])
        return text, 0
