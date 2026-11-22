# -*- coding: utf-8 -*-
"""v1.7.10.0 — لیگ قهرمانان (UCL) دوشنبه‌ها: گروهی + حذفی، بازی‌های زندهٔ ۱۰ دقیقه‌ای.

ساختار (سند A12): دوشنبه‌ها، گروهی + حذفی، رفت‌وبرگشت. بازی‌ها زنده و قابل‌تماشا.
"""
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class FootballUclSeason(Base):
    """یک دورهٔ UCL (دو هفته)."""
    __tablename__ = "football_ucl_seasons"

    id: Mapped[int] = mapped_column(primary_key=True)
    period_key: Mapped[str] = mapped_column(String(16), index=True)    # دوره (هفتهٔ ISO زوج)
    status: Mapped[str] = mapped_column(String(16), default="registration", index=True)  # registration/groups/knockout/done
    team_count: Mapped[int] = mapped_column(Integer, default=0)
    champion_club_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class FootballUclEntry(Base):
    """ثبت‌نام یک باشگاه در UCL + آمار گروه."""
    __tablename__ = "football_ucl_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    season_id: Mapped[int] = mapped_column(BigInteger, index=True)
    club_id: Mapped[int] = mapped_column(BigInteger, index=True)
    owner_id: Mapped[int] = mapped_column(BigInteger, default=0)
    club_name: Mapped[str] = mapped_column(String(64), default="")
    group_no: Mapped[int] = mapped_column(Integer, default=0)          # شمارهٔ گروه
    played: Mapped[int] = mapped_column(Integer, default=0)
    wins: Mapped[int] = mapped_column(Integer, default=0)
    draws: Mapped[int] = mapped_column(Integer, default=0)
    losses: Mapped[int] = mapped_column(Integer, default=0)
    goals_for: Mapped[int] = mapped_column(Integer, default=0)
    goals_against: Mapped[int] = mapped_column(Integer, default=0)
    points: Mapped[int] = mapped_column(Integer, default=0)
    advanced: Mapped[bool] = mapped_column(Boolean, default=False)     # به حذفی رسید


class FootballUclFixture(Base):
    """یک بازیِ UCL (گروهی یا حذفی)."""
    __tablename__ = "football_ucl_fixtures"

    id: Mapped[int] = mapped_column(primary_key=True)
    season_id: Mapped[int] = mapped_column(BigInteger, index=True)
    stage: Mapped[str] = mapped_column(String(12), default="group")   # group / r16 / qf / sf / final
    home_club_id: Mapped[int] = mapped_column(BigInteger)
    away_club_id: Mapped[int] = mapped_column(BigInteger)
    home_goals: Mapped[int] = mapped_column(Integer, default=0)
    away_goals: Mapped[int] = mapped_column(Integer, default=0)
    played: Mapped[bool] = mapped_column(Boolean, default=False)
    home_name: Mapped[str] = mapped_column(String(64), default="")
    away_name: Mapped[str] = mapped_column(String(64), default="")
