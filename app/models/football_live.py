# -*- coding: utf-8 -*-
"""v1.7.10.0 — موتور بازی زنده‌ی فوتبال (۱۰ دقیقه‌ای، گزارش زنده‌ی قابل بروزرسانی).

هر بازی ۱۰ دقیقهٔ واقعی = ۹۰ دقیقهٔ بازی. رویدادهای گل از قبل (پوآسون) ساخته می‌شوند و
با پیشروش زمان به‌تدریج در گزارش زنده ظاهر می‌شوند (مثل گزارش زنده‌ی جنگ).
"""
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class FootballLiveMatch(Base):
    """یک بازی زنده (دوستانه/لیگ/UCL)."""
    __tablename__ = "football_live_matches"

    id: Mapped[int] = mapped_column(primary_key=True)
    home_club_id: Mapped[int] = mapped_column(BigInteger, index=True)
    away_club_id: Mapped[int] = mapped_column(BigInteger, index=True, default=0)  # 0 = بات
    home_name: Mapped[str] = mapped_column(String(64), default="")
    away_name: Mapped[str] = mapped_column(String(64), default="")
    home_goals: Mapped[int] = mapped_column(Integer, default=0)
    away_goals: Mapped[int] = mapped_column(Integer, default=0)
    events_json: Mapped[str] = mapped_column(Text, default="[]")      # [{minute, side, scorer}]
    revealed: Mapped[int] = mapped_column(Integer, default=0)          # چند رویداد تا حالا نشان داده شده
    mode: Mapped[str] = mapped_column(String(16), default="friendly", index=True)  # friendly/league/ucl
    season_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)      # برای لیگ/UCL
    fixture_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    status: Mapped[str] = mapped_column(String(12), default="live", index=True)  # live/done
    started_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
