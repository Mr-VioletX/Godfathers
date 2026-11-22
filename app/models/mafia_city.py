# -*- coding: utf-8 -*-
"""🆕 بچ ۴ — مدلِ شهرسازِ جدید (تک‌شهری).

دو جدولِ تازه (مستقل از جدول‌های قدیمیِ cities/city_buildings که در بچ ۴ رفاند و بازنشسته شدند):
  • MafiaCity     — دقیقاً یک شهر برای هر بازیکن
  • MafiaBuilding — ساختمان‌های شهر (qty = تعداد برای مسکونی/رفاهی، سطح برای زیرساخت/صنعت)

create_all فقط جدولِ تازه را می‌سازد؛ نیازی به دست‌کاریِ دیتابیس نیست.
"""
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Integer,
    Text,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class MafiaCity(Base):
    """شهرِ یکتای هر بازیکن."""
    __tablename__ = "mafia_cities"
    __table_args__ = (
        UniqueConstraint("tg_user_id", name="uq_mafia_city_owner"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    tg_user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    name: Mapped[str] = mapped_column(String(64), default="شهرِ من")

    population: Mapped[int] = mapped_column(BigInteger, default=0)
    base_population: Mapped[int] = mapped_column(BigInteger, default=0)
    satisfaction: Mapped[int] = mapped_column(Integer, default=60)   # ۰..۱۰۰
    tax_rate: Mapped[int] = mapped_column(Integer, default=15)       # ۰..۳۰

    purchase_price: Mapped[int] = mapped_column(BigInteger, default=0)
    warehouse_level: Mapped[int] = mapped_column(Integer, default=1)
    materials: Mapped[int] = mapped_column(BigInteger, default=0)     # موجودی قدیمی برای انتقال خودکار
    resources_json: Mapped[str] = mapped_column(Text, default="{}")  # موجودی منابع متنوع شهر
    # v1.7.8.5 — سقف تولید روزانهٔ مواد (هر واحد صنعتی ≤ ۱٬۰۰۰ واحد/روز)
    prod_day: Mapped[str] = mapped_column(String(10), default="")
    prod_today_json: Mapped[str] = mapped_column(Text, default="{}")

    founded_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    last_income_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_prod_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_grow_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # v1.7.6.5 -- hired mayor who relays citizen messages during the year
    mayor_key: Mapped[str | None] = mapped_column(String(16), nullable=True)
    mayor_hired_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_mayor_msg_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    mayor_paid_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class MafiaBuilding(Base):
    """یک نوع ساختمان در شهر (یک ردیف به‌ازای هر btype)."""
    __tablename__ = "mafia_buildings"
    __table_args__ = (
        UniqueConstraint("city_id", "btype", name="uq_mafia_building_city_btype"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    city_id: Mapped[int] = mapped_column(
        ForeignKey("mafia_cities.id", ondelete="CASCADE"), index=True
    )
    btype: Mapped[str] = mapped_column(String(32))
    qty: Mapped[int] = mapped_column(Integer, default=1)   # تعداد (مسکونی/رفاهی) یا سطح (زیرساخت/صنعت)


class CityBuildQueue(Base):
    """v1.7.8.3 — صف ساخت‌وسازِ زمان‌دار (۱ تا ۲۴ ساعت)."""
    __tablename__ = "city_build_queue"

    id: Mapped[int] = mapped_column(primary_key=True)
    city_id: Mapped[int] = mapped_column(
        ForeignKey("mafia_cities.id", ondelete="CASCADE"), index=True
    )
    btype: Mapped[str] = mapped_column(String(32))
    kind: Mapped[str] = mapped_column(String(16), default="build")  # build | upgrade | warehouse
    qty: Mapped[int] = mapped_column(Integer, default=1)
    started_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    ready_at: Mapped[datetime] = mapped_column(DateTime)
