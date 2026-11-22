# -*- coding: utf-8 -*-
"""v1.8.1.0 — F6: ترکیب و تاکتیک فوتبال (مدل). جدول تازه — بدون مهاجرت.

هر باشگاه یک تاکتیک دارد (تهاجمی/متعادل/دفاعی) + اتو‌تاکتیک (تغییر خودکار وسط بازی زنده).
"""
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class FootballTactic(Base):
    """تاکتیکِ یک باشگاه."""
    __tablename__ = "football_tactics"

    club_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    tactic: Mapped[str] = mapped_column(String(16), default="balanced")   # offensive/balanced/defensive
    auto_enabled: Mapped[bool] = mapped_column(Boolean, default=False)    # اتو‌تاکتیک
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
