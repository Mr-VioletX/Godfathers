# -*- coding: utf-8 -*-
"""مدل‌های مرحله ۱۷ — جنگِ شخصی، سپر/حالتِ ایمن، تصرفِ شهر و کشور.

همه‌ی جدول‌ها جدا از جدولِ players نگه داشته شده‌اند تا نیازی به تغییرِ ستون‌های بازیکن نباشد.
"""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class WarState(Base):
    """وضعیتِ جنگیِ هر بازیکن: سپر (مصونیت) و زمانِ آخرین حمله."""
    __tablename__ = "war_states"

    tg_user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    # تا این زمان کسی نمی‌تواند به این بازیکن حمله کند (سپر/حالتِ ایمن)
    shield_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # آخرین باری که خودِ این بازیکن حمله کرده (کول‌داونِ مهاجم)
    last_attack_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Battle(Base):
    """یک نبردِ ثبت‌شده بینِ دو بازیکن (برای قفلِ غنیمت و تاریخچه)."""
    __tablename__ = "battles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    attacker_id: Mapped[int] = mapped_column(BigInteger, index=True)
    defender_id: Mapped[int] = mapped_column(BigInteger, index=True)
    winner_id: Mapped[int] = mapped_column(BigInteger, index=True)
    loser_id: Mapped[int] = mapped_column(BigInteger, index=True)
    # مقادیرِ مالیِ نتیجه
    loot_pct: Mapped[int] = mapped_column(Integer, default=0)
    amount: Mapped[int] = mapped_column(BigInteger, default=0)   # غنیمت یا غرامت
    # تا این زمان مهاجم نمی‌تواند دوباره به همین هدف حمله کند (قفلِ غنیمت)
    loot_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    attacker_won: Mapped[bool] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


# 🆕 بچ ۴ — کلاس‌های CapturedCity / Country / CountryWar / CountryWarState حذف شدند
# (سیستمِ تصرفِ شهر و جنگِ کشورِ قدیمی بازنشسته شد؛ جدول‌هایِ countries/
# country_wars/country_war_states/captured_cities دیگر ساخته و استفاده نمی‌شوند.)
