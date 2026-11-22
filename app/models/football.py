# -*- coding: utf-8 -*-
"""v1.7.9.2 — مدل‌های فوتبال منیجر (مرحله ۷۹).

جدول‌های تازه (create_all خودکار می‌سازد؛ به جدول‌های قدیمیِ ورزش دست نمی‌خورد):
  • football_clubs        — باشگاهِ هر کاربر (سرمربی/استادیوم/طرفدار/سوشال/کمپ)
  • football_player_cards — کارتِ بازیکنِ متعلق به باشگاه (با کد پیگیری)
  • football_matches      — تاریخچه‌ی مسابقات (دوستانه/لیگ/UCL در فازهای بعدی)
"""
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class FootballClub(Base):
    """باشگاهِ فوتبالِ یک کاربر."""
    __tablename__ = "football_clubs"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(64), unique=True)
    icon: Mapped[str] = mapped_column(String(8), default="⚽")

    # سرمربی
    coach_style: Mapped[str] = mapped_column(String(16), default="possession")  # full_attack/full_defense/possession/counter
    coach_level: Mapped[int] = mapped_column(Integer, default=1)
    coach_stars: Mapped[int] = mapped_column(Integer, default=1)               # 1..5

    # زیرساخت
    stadium_capacity: Mapped[int] = mapped_column(BigInteger, default=12_500)
    stadium_level: Mapped[int] = mapped_column(Integer, default=0)
    fans: Mapped[int] = mapped_column(BigInteger, default=2_000)
    social_followers: Mapped[int] = mapped_column(BigInteger, default=0)
    training_camps: Mapped[int] = mapped_column(Integer, default=0)            # 0..3

    # تاکتیک
    formation_start: Mapped[str] = mapped_column(String(8), default="4-3-3")
    formation_winning: Mapped[str] = mapped_column(String(8), default="5-3-2")
    formation_losing: Mapped[str] = mapped_column(String(8), default="4-2-4")

    league_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class FootballPlayerCard(Base):
    """کارتِ یک بازیکنِ متعلق به یک باشگاه — با کد پیگیری‌ی یکتا."""
    __tablename__ = "football_player_cards"

    id: Mapped[int] = mapped_column(primary_key=True)
    club_id: Mapped[int] = mapped_column(BigInteger, index=True)          # باشگاهی که بازیکن در آن است
    owner_id: Mapped[int] = mapped_column(BigInteger, index=True)         # کاربرِ مالک
    template_key: Mapped[str] = mapped_column(String(16), index=True)     # کلید کاتالوگ
    name: Mapped[str] = mapped_column(String(64))
    pos: Mapped[str] = mapped_column(String(8))                           # GK/DEF/MID/FWD
    tier: Mapped[str] = mapped_column(String(16))                         # common/rare/epic/legend/mythic
    base_power: Mapped[int] = mapped_column(Integer, default=100)
    training_bonus: Mapped[int] = mapped_column(Integer, default=0)
    form_pct: Mapped[int] = mapped_column(Integer, default=100)           # 90..110 ↔ form 0.90..1.10
    fatigue: Mapped[int] = mapped_column(Integer, default=0)              # 0..100
    injured_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    is_starter: Mapped[bool] = mapped_column(Boolean, default=False)
    tracking_code: Mapped[str] = mapped_column(String(16), unique=True)   # کد پیگیری
    acquired_via: Mapped[str] = mapped_column(String(16), default="starter")  # starter/shop/admin/trade
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class FootballMatch(Base):
    """یک مسابقه‌ی ثبت‌شده (دوستانه در F1؛ لیگ/UCL در فازهای بعدی)."""
    __tablename__ = "football_matches"

    id: Mapped[int] = mapped_column(primary_key=True)
    home_club_id: Mapped[int] = mapped_column(BigInteger, index=True)
    away_club_id: Mapped[int] = mapped_column(BigInteger, index=True, default=0)  # 0 = حریف بات
    home_goals: Mapped[int] = mapped_column(Integer, default=0)
    away_goals: Mapped[int] = mapped_column(Integer, default=0)
    mode: Mapped[str] = mapped_column(String(16), default="friendly")     # friendly/league/ucl
    report: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)

class FootballClubState(Base):
    """وضعیت‌های روزانه/هفتگی باشگاه (جدول تازه v1.7.9.4 — بدون مهاجرت)."""
    __tablename__ = "football_club_state"

    club_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    coach_xp_json: Mapped[str] = mapped_column(Text, default="{}")       # {style: xp}
    style_change_week: Mapped[str] = mapped_column(String(16), default="")  # هفته‌ی آخرین تعویض رایگان
    social_date: Mapped[str] = mapped_column(String(12), default="")     # تاریخ امروزِ پست‌ها
    social_count: Mapped[int] = mapped_column(Integer, default=0)
    train_date: Mapped[str] = mapped_column(String(12), default="")
    train_count: Mapped[int] = mapped_column(Integer, default=0)
    milestones_json: Mapped[str] = mapped_column(Text, default="[]")     # مایلستون‌های دریافت‌شده
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class FootballCoachPurchase(Base):
    """خرید سرمربی ۵⭐ با پول واقعی (v1.7.9.5) — درخواست/تأیید ادمین/رسید."""
    __tablename__ = "football_coach_purchases"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(BigInteger, index=True)
    coach_key: Mapped[str] = mapped_column(String(32))
    coach_name: Mapped[str] = mapped_column(String(64), default="")
    price: Mapped[int] = mapped_column(BigInteger, default=0)
    tracking_code: Mapped[str] = mapped_column(String(16), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    receipt_file_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    decided_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
