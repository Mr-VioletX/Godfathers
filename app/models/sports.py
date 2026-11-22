# -*- coding: utf-8 -*-
"""مدل‌هایِ سیستمِ ورزشی (مرحله ۱۴).

سه جدولِ جدید:
  • SportsTeam   — تیمِ فوتبال/بسکتبال (با برندسازی و آمارِ لیگ)
  • RacingBrand  — برندِ خودروسازیِ F1/موتور (با راننده/لاستیک/تیمِ فنی)
  • SportsMatch  — تاریخچه‌ی مسابقات (برای اعلانِ قهرمانِ روزانه)

create_all فقط جدول‌های جدید را می‌سازد؛ نیازی به پاک‌کردنِ دیتابیس نیست.
"""
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class SportsTeam(Base):
    """یک تیمِ فوتبال یا بسکتبالِ متعلق به یک بازیکن."""
    __tablename__ = "sports_teams"

    id: Mapped[int] = mapped_column(primary_key=True)
    tg_user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    sport: Mapped[str] = mapped_column(String(16))          # football/basketball

    # --- برندسازی / نام‌گذاری ---
    name: Mapped[str] = mapped_column(String(64))           # نامِ باشگاه
    color: Mapped[str | None] = mapped_column(String(32), nullable=True)   # رنگِ پیراهن (اسکین)
    slogan: Mapped[str | None] = mapped_column(String(128), nullable=True)  # شعار
    stadium_name: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # --- زیرساخت و قدرت ---
    stadium_level: Mapped[int] = mapped_column(Integer, default=1)
    coach_level: Mapped[int] = mapped_column(Integer, default=1)
    avg_player_level: Mapped[int] = mapped_column(Integer, default=10)
    budget: Mapped[int] = mapped_column(BigInteger, default=0)

    # --- لیگ ---
    division: Mapped[int] = mapped_column(Integer, default=2)   # 1 یا 2
    # in_league: ثبت‌نامِ تیم برای لیگِ حذفیِ هفتگیِ همین رشته (هر هفته دوباره False می‌شود؛
    # با دکمه‌ی «🏆 ثبت‌نامِ لیگ» و پرداختِ LEAGUE_ENTRY_FEE دوباره True می‌شود).
    in_league: Mapped[bool] = mapped_column(Boolean, default=False)
    wins: Mapped[int] = mapped_column(Integer, default=0)
    draws: Mapped[int] = mapped_column(Integer, default=0)
    losses: Mapped[int] = mapped_column(Integer, default=0)
    points: Mapped[int] = mapped_column(Integer, default=0)
    goals_for: Mapped[int] = mapped_column(Integer, default=0)
    goals_against: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class RacingBrand(Base):
    """یک برندِ خودروسازی/موتورِ متعلق به یک بازیکن."""
    __tablename__ = "racing_brands"

    id: Mapped[int] = mapped_column(primary_key=True)
    tg_user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    sport: Mapped[str] = mapped_column(String(16))          # f1/moto

    # --- برندسازی ---
    name: Mapped[str] = mapped_column(String(64))           # نامِ برند
    color: Mapped[str | None] = mapped_column(String(32), nullable=True)   # رنگِ ماشین
    race_team_name: Mapped[str | None] = mapped_column(String(64), nullable=True)  # نامِ تیمِ مسابقه
    track_name: Mapped[str | None] = mapped_column(String(64), nullable=True)      # نامِ پیست

    # --- اجزای فنی ---
    brand_level: Mapped[int] = mapped_column(Integer, default=1)   # برندِ خودروسازی
    tire_level: Mapped[int] = mapped_column(Integer, default=1)    # کارخانه‌ی لاستیک
    tech_level: Mapped[int] = mapped_column(Integer, default=1)    # تیمِ فنی (۸ نفر)
    driver_skill: Mapped[int] = mapped_column(Integer, default=0)  # مهارتِ راننده (۰..۱۰۰)
    track_count: Mapped[int] = mapped_column(Integer, default=1)   # تعدادِ پیست

    # --- مسابقات ---
    wins: Mapped[int] = mapped_column(Integer, default=0)
    losses: Mapped[int] = mapped_column(Integer, default=0)
    points: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class SportsMatch(Base):
    """تاریخچه‌ی یک مسابقه (برای اعلانِ قهرمانِ روزانه و تاریخچه)."""
    __tablename__ = "sports_matches"

    id: Mapped[int] = mapped_column(primary_key=True)
    tg_user_id: Mapped[int] = mapped_column(BigInteger, index=True)   # صاحبِ تیمِ A (بازیکن)
    sport: Mapped[str] = mapped_column(String(16))

    team_a_name: Mapped[str] = mapped_column(String(64))
    team_b_name: Mapped[str] = mapped_column(String(64))
    opponent_user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)  # None = حریفِ ربات

    score_a: Mapped[int] = mapped_column(Integer, default=0)
    score_b: Mapped[int] = mapped_column(Integer, default=0)
    result: Mapped[str] = mapped_column(String(8))   # A/B/draw
    events: Mapped[str | None] = mapped_column(String(256), nullable=True)  # کلیدهای کارت‌های رویداد (CSV)
    prize: Mapped[int] = mapped_column(BigInteger, default=0)
    star_player: Mapped[str | None] = mapped_column(String(64), nullable=True)

    played_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
