# -*- coding: utf-8 -*-
"""🆕 مرحله ۴۶ — نبردِ زنده‌ی ۱۵ دقیقه‌ای.

هر ردیف = یک نبردِ در جریان بینِ دو بازیکن. نتیجه از همان لحظه‌ی شروع محاسبه و در
plan_json ذخیره می‌شود، اما اثرش (تلفات/غنیمت) فقط در پایانِ ۱۵ دقیقه اعمال می‌شود؛
در این فاصله کاربر با دکمه‌ی «🔄 بروزرسانی» فازهای تازه را می‌بیند.

create_all خودش این جدولِ جدید را می‌سازد (مهاجرتِ دستی لازم نیست).
"""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class LiveBattle(Base):
    __tablename__ = "live_battles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    attacker_id: Mapped[int] = mapped_column(BigInteger, index=True)
    defender_id: Mapped[int] = mapped_column(BigInteger, index=True)
    mode: Mapped[str] = mapped_column(String(16), default="classic")
    started_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    ends_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    plan_json: Mapped[str] = mapped_column(Text, default="{}")
    finalized: Mapped[int] = mapped_column(Integer, default=0)
    notified: Mapped[int] = mapped_column(Integer, default=0)
