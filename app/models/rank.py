# -*- coding: utf-8 -*-
"""🆕 مرحله ۴۶ (بچ ۳) — جدولِ وضعیتِ رنکینگِ هر بازیکن (کاپ، لیگ، سپر).

این جدول توسطِ create_all به‌صورتِ خودکار ساخته می‌شود (مهاجرتِ دستی لازم نیست).
"""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class RankState(Base):
    __tablename__ = "rank_states"

    owner_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    cups: Mapped[int] = mapped_column(Integer, default=0)
    best_cups: Mapped[int] = mapped_column(Integer, default=0)
    league: Mapped[int] = mapped_column(Integer, default=0)          # آخرین لیگِ ثبت‌شده
    best_league: Mapped[int] = mapped_column(Integer, default=0)
    # سپرِ ۱ روزه‌ی ورود به لیگِ تازه
    shield_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    wins: Mapped[int] = mapped_column(Integer, default=0)
    losses: Mapped[int] = mapped_column(Integer, default=0)
    defenses_won: Mapped[int] = mapped_column(Integer, default=0)
    defenses_lost: Mapped[int] = mapped_column(Integer, default=0)
    last_ranked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
