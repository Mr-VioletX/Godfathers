# -*- coding: utf-8 -*-
"""v1.7.9.6 — مدل‌های بازار نقل‌وانتقال فوتبال (مرحله ۷۹ — فاز F3).

جدول‌های تازه (بدون مهاجرت):
  • football_unique_owners — مالکِ هر بازیکنِ تک‌نسخه‌ای (real money)
  • football_market_sales  — فروش/مزایده‌ی بازیکنِ تک (دو ساعت مزایده + صف پرداخت ۳۰ دقیقه)
"""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class FootballUniqueOwner(Base):
    """مالکِ فعلیِ یک بازیکنِ تک‌نسخه‌ای (template_key یکتا)."""
    __tablename__ = "football_unique_owners"

    template_key: Mapped[str] = mapped_column(String(16), primary_key=True)
    owner_id: Mapped[int] = mapped_column(BigInteger, index=True)
    card_id: Mapped[int] = mapped_column(BigInteger, default=0)          # کارتِ ساخته‌شده در باشگاه مالک
    price_paid: Mapped[int] = mapped_column(BigInteger, default=0)       # تومان
    tracking_code: Mapped[str] = mapped_column(String(16), default="")
    acquired_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class FootballMarketSale(Base):
    """فروش/مزایده‌ی یک بازیکنِ تک‌نسخه‌ای.

    جریان: auction (۲ ساعت، اطلاعیه به همه + پیشنهاد بالاتر) ← awaiting_admin ←
    awaiting_payment (نفرِ جلو با ۳۰ دقیقه) ← receipt_check ← done.
    اگر پرداخت/رسید رد شد → نفر بعدی با ۳۰ دقیقه؛ اگر هیچ‌کس نماند → ادمین برای امروز لغو می‌کند.
    """
    __tablename__ = "football_market_sales"

    id: Mapped[int] = mapped_column(primary_key=True)
    template_key: Mapped[str] = mapped_column(String(16), index=True)
    player_name: Mapped[str] = mapped_column(String(64), default="")
    status: Mapped[str] = mapped_column(String(20), default="auction", index=True)
    # auction / awaiting_admin / awaiting_payment / receipt_check / done / cancelled
    highest_bid: Mapped[int] = mapped_column(BigInteger, default=0)      # تومان
    highest_bidder: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    queue_json: Mapped[str] = mapped_column(Text, default="[]")          # [{uid, bid}] مرتب‌شده نزولی
    current_candidate: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    auction_ends_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    payment_deadline: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    receipt_file_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    tracking_code: Mapped[str] = mapped_column(String(16), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
