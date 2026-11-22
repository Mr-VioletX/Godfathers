# -*- coding: utf-8 -*-
"""v1.7.9.6 — آمار لیگ فوتبال (جدول واقعی) — برای جدول لیگ + رنکینگ ورزش (امتیاز هفتگی).

هر باشگاه: بازی/برد/مساوی/باخت/گل‌زده/گل‌خورده/امتیاز + امتیاز هفتگی (برای رنکینگ).
بدون مهاجرت — جدول تازه با create_all ساخته می‌شود.
"""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class FootballStanding(Base):
    """ردیف جدول لیگ برای یک باشگاه."""
    __tablename__ = "football_standings"

    club_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    owner_id: Mapped[int] = mapped_column(BigInteger, index=True)
    club_name: Mapped[str] = mapped_column(String(64), default="")
    played: Mapped[int] = mapped_column(Integer, default=0)
    wins: Mapped[int] = mapped_column(Integer, default=0)
    draws: Mapped[int] = mapped_column(Integer, default=0)
    losses: Mapped[int] = mapped_column(Integer, default=0)
    goals_for: Mapped[int] = mapped_column(Integer, default=0)
    goals_against: Mapped[int] = mapped_column(Integer, default=0)
    points: Mapped[int] = mapped_column(Integer, default=0)
    weekly_points: Mapped[int] = mapped_column(Integer, default=0)   # برای رنکینگ ورزش
    week_key: Mapped[str] = mapped_column(String(12), default="")    # هفته‌ی ISO
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
