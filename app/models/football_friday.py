# -*- coding: utf-8 -*-
"""v1.7.9.9 — لیگ جمعهٔ رسمی فوتبال (F4): مدل‌های فصل/ثبت‌نام/فیکسچر.

ساختار (تأیید امیر): دوری رفت‌وبرگشت، هر هفته جمعه (ثبت‌نام تا پنجشنبه) —
جایزه: دلار بازی + XP سرمربی + طرفدار. جدول‌های تازه، بدون مهاجرت.
"""
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class FootballLeagueSeason(Base):
    """یک فصل هفتگی لیگ جمعه."""
    __tablename__ = "football_league_seasons"

    id: Mapped[int] = mapped_column(primary_key=True)
    week_key: Mapped[str] = mapped_column(String(12), index=True)      # هفته‌ی ISO (تهران)
    status: Mapped[str] = mapped_column(String(16), default="registration", index=True)  # registration/fixtures/done
    team_count: Mapped[int] = mapped_column(Integer, default=0)
    champion_club_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class FootballLeagueEntry(Base):
    """ثبت‌نامِ یک باشگاه در یک فصل + جدول داخلی فصل."""
    __tablename__ = "football_league_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    season_id: Mapped[int] = mapped_column(BigInteger, index=True)
    club_id: Mapped[int] = mapped_column(BigInteger, index=True)
    owner_id: Mapped[int] = mapped_column(BigInteger, default=0)
    club_name: Mapped[str] = mapped_column(String(64), default="")
    seed_pot: Mapped[int] = mapped_column(Integer, default=2)          # 0/1/2 سیدبندی
    played: Mapped[int] = mapped_column(Integer, default=0)
    wins: Mapped[int] = mapped_column(Integer, default=0)
    draws: Mapped[int] = mapped_column(Integer, default=0)
    losses: Mapped[int] = mapped_column(Integer, default=0)
    goals_for: Mapped[int] = mapped_column(Integer, default=0)
    goals_against: Mapped[int] = mapped_column(Integer, default=0)
    points: Mapped[int] = mapped_column(Integer, default=0)


class FootballLeagueFixture(Base):
    """یک بازیِ برنامه‌ریزی‌شده در فصل."""
    __tablename__ = "football_league_fixtures"

    id: Mapped[int] = mapped_column(primary_key=True)
    season_id: Mapped[int] = mapped_column(BigInteger, index=True)
    round_no: Mapped[int] = mapped_column(Integer, default=0)
    home_club_id: Mapped[int] = mapped_column(BigInteger)
    away_club_id: Mapped[int] = mapped_column(BigInteger)
    home_goals: Mapped[int] = mapped_column(Integer, default=0)
    away_goals: Mapped[int] = mapped_column(Integer, default=0)
    played: Mapped[bool] = mapped_column(Boolean, default=False)
    home_name: Mapped[str] = mapped_column(String(64), default="")
    away_name: Mapped[str] = mapped_column(String(64), default="")
