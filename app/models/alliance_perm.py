# -*- coding: utf-8 -*-
"""🆕 مرحله ۳۰ — دسترسی‌هایِ معاونِ اتحادیه.

رئیسِ اتحادیه می‌تواند به معاون‌ها دسترسیِ جداگانه بدهد (درخواست‌ها، ارتقا،
جنگ، تنطیمات، نقش‌ها، صندوق). هر ردیف = یک دسترسیِ فعال برای یک عضو.

جدولِ تازه است؛ create_all خودش می‌سازد و هیچ مهاجرتِ دستی لازم ندارد.
"""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class AlliancePermission(Base):
    __tablename__ = "alliance_permissions"
    __table_args__ = (
        UniqueConstraint(
            "alliance_id", "player_id", "perm_key", name="uq_alliance_perm"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    alliance_id: Mapped[int] = mapped_column(Integer, index=True)
    player_id: Mapped[int] = mapped_column(BigInteger, index=True)
    perm_key: Mapped[str] = mapped_column(String(32))
    granted_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
