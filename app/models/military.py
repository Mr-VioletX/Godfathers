# -*- coding: utf-8 -*-
"""مرحله ۱۹ — مدلِ ارتشِ بازیکن.

هر ردیف = یک پشته‌ی نیرو از یک نوع، متعلق به یک مالک.
سطحِ ارتقا/آموزش (upgrade_level) روی «همه‌ی» واحدهای همان نوع اثر می‌گذارد.
جدا از جدولِ players نگه داشته شده است.
"""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class MilitaryUnit(Base):
    __tablename__ = "military_units"
    __table_args__ = (
        UniqueConstraint("owner_id", "unit_key", name="uq_military_owner_unit"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_id: Mapped[int] = mapped_column(BigInteger, index=True)
    unit_key: Mapped[str] = mapped_column(String(32), index=True)
    count: Mapped[int] = mapped_column(Integer, default=0)
    upgrade_level: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class MilitaryTrainingQueue(Base):
    """🆕 مرحله ۴۵ — صفِ پرورشِ نیرو.

    هر ردیف = یک بچِ در‌حالِ ساخت؛ پس از ready_at به ارتش می‌پیوندد.
    create_all خودش این جدولِ جدید را می‌سازد (مهاجرتِ دستی لازم نیست).
    """
    __tablename__ = "military_training_queue"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_id: Mapped[int] = mapped_column(BigInteger, index=True)
    unit_key: Mapped[str] = mapped_column(String(32), index=True)
    qty: Mapped[int] = mapped_column(Integer, default=0)
    # مبلغی که هنگام ثبت صف پرداخت شده؛ برای بازگرداندن دقیق هزینه در لغو صف غیرفعال.
    paid_cost: Mapped[int] = mapped_column(BigInteger, default=0)
    original_qty: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    ready_at: Mapped[datetime] = mapped_column(DateTime, index=True)


class MilitaryUpgradeQueue(Base):
    """صف ارتقای زمانی هر نوع نیرو."""
    __tablename__ = "military_upgrade_queue"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_id: Mapped[int] = mapped_column(BigInteger, index=True)
    unit_key: Mapped[str] = mapped_column(String(32), index=True)
    target_level: Mapped[int] = mapped_column(Integer, default=1)
    started_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    ready_at: Mapped[datetime] = mapped_column(DateTime, index=True)


class MilitaryBarracks(Base):
    __tablename__ = "military_barracks"
    owner_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    level: Mapped[int] = mapped_column(Integer, default=1)
    upgrading_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
