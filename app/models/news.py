# -*- coding: utf-8 -*-
"""مدلِ «اخبارِ روزانه» (مرحله ۲۰).

یک جدولِ جدید: news_items — رویدادهای مهمِ بازی در اینجا ثبت می‌شوند و
هر شب ساعتِ ۲۰:۰۰ به وقتِ تهران به‌صورتِ خلاصه منتشر می‌شوند.
"""
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class NewsItem(Base):
    """یک خبرِ ثبت‌شده."""
    __tablename__ = "news_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    category: Mapped[str] = mapped_column(String(16), default="event", index=True)
    importance: Mapped[int] = mapped_column(Integer, default=1)   # ۱..۳
    text: Mapped[str] = mapped_column(String(512))
    actor_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    # آیا در خلاصه‌ی شب منتشر شده است؟ (برای جلوگیری از تکرار)
    published: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), index=True
    )


class NewsDigestPost(Base):
    """خلاصه‌ی روزانه‌ی منتشرشده با صفحه‌های از پیش‌ساخته‌شده — پیمایش با ◀️ ▶️ (v1.7.9.1)."""
    __tablename__ = "news_digest_posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pages_json: Mapped[str] = mapped_column(Text, default="[]")
    item_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
