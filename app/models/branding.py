# -*- coding: utf-8 -*-
"""مدل‌های برندسازی.

• Brand           — مرحله ۱۹.۱ (نام، سطح، شهرت، کمپین)
• BrandCompany    — شرکت‌های برند
• BrandProduct    — محصولِ بازشده‌ی هر شرکت
• HoldingUnit     — واحدهای هولدینگ
"""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class Brand(Base):
    __tablename__ = "brands"

    owner_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(64))
    level: Mapped[int] = mapped_column(Integer, default=1)
    reputation: Mapped[int] = mapped_column(BigInteger, default=0)
    last_campaign_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # v1.7.6 — کول‌داون جدا برای هر نوع تبلیغ (JSON: {campaign_key: iso_ts})
    campaign_cooldowns: Mapped[str | None] = mapped_column(Text, nullable=True, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class BrandCompany(Base):
    """هر شرکتِ برندی یکتاست: هر کلید فقط یک‌بار برای هر مالک."""

    __tablename__ = "brand_companies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_id: Mapped[int] = mapped_column(BigInteger, index=True)
    company_key: Mapped[str] = mapped_column(String(32))
    title: Mapped[str | None] = mapped_column(String(64), nullable=True)
    level: Mapped[int] = mapped_column(Integer, default=1)
    capacity_level: Mapped[int] = mapped_column(Integer, default=1)
    speed_level: Mapped[int] = mapped_column(Integer, default=1)
    expansion_level: Mapped[int] = mapped_column(Integer, default=1)
    line_level: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class BrandProduct(Base):
    """یک محصولِ بازشده در یک شرکتِ برندی."""

    __tablename__ = "brand_products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(Integer, index=True)
    product_key: Mapped[str] = mapped_column(String(32))
    stock: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(16), default="idle")
    percent: Mapped[int] = mapped_column(Integer, default=50)
    pending_units: Mapped[int] = mapped_column(Integer, default=0)
    # 🆕 v1.7.8.18 — خطِ تولیدِ دومِ همین محصول (هر محصول ۲ خطِ مستقل دارد)
    status2: Mapped[str | None] = mapped_column(String(16), nullable=True, default="idle")
    started_at2: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    percent2: Mapped[int | None] = mapped_column(Integer, nullable=True, default=100)
    pending_units2: Mapped[int | None] = mapped_column(Integer, nullable=True, default=0)
    # 🆕 v1.7.8.17 — انبارِ اختصاصیِ همین محصول (۱۰ سطح: ۵٬۰۰۰ ← ۱۵٬۰۰۰ واحد)
    capacity_level: Mapped[int] = mapped_column(Integer, default=1)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class BrandQueueItem(Base):
    """🆕 v1.7.8.17 — صفِ ساختِ شرکتِ برند (دقیقاً مانندِ کارخانه).

    هزینهٔ مواد هنگامِ ثبت در صف کسر می‌شود و با حذفِ سفارش کامل برمی‌گردد.
    """

    __tablename__ = "brand_queue"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(Integer, index=True)
    bp_id: Mapped[int] = mapped_column(Integer, index=True)
    product_key: Mapped[str] = mapped_column(String(32))
    units: Mapped[int] = mapped_column(Integer, default=0)
    percent: Mapped[int] = mapped_column(Integer, default=100)
    paid_cost: Mapped[int] = mapped_column(BigInteger, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class HoldingUnit(Base):
    """یک واحدِ هولدینگِ تفریحی — درآمدِ خودکار و مسیرهای ارتقا."""

    __tablename__ = "holding_units"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_id: Mapped[int] = mapped_column(BigInteger, index=True)
    unit_key: Mapped[str] = mapped_column(String(32))
    title: Mapped[str | None] = mapped_column(String(64), nullable=True)
    tracks: Mapped[str] = mapped_column(Text, default="{}")
    last_collected_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
