# -*- coding: utf-8 -*-
"""مرحله ۱۶ — لاگِ انتقالِ دارایی بین کاربران (برای سقفِ روزانه و تاریخچه)."""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, String, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class AssetTransfer(Base):
    __tablename__ = "asset_transfers"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    from_user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    to_user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    kind: Mapped[str] = mapped_column(String(16), default="cash")   # cash (فعلاً فقط پول)
    amount: Mapped[int] = mapped_column(BigInteger, default=0)      # مبلغِ ناخالصِ برداشته‌شده از فرستنده
    fee: Mapped[int] = mapped_column(BigInteger, default=0)         # کارمزد (۲٪)
    received: Mapped[int] = mapped_column(BigInteger, default=0)    # مبلغِ خالصِ رسیده به گیرنده

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


async def sent_today(session: AsyncSession, from_user_id: int, day_start: datetime) -> int:
    """مجموعِ مبلغِ ناخالصِ ارسال‌شده توسطِ کاربر از ابتدایِ امروز (UTC)."""
    rows = (await session.execute(
        select(AssetTransfer.amount).where(
            AssetTransfer.from_user_id == from_user_id,
            AssetTransfer.created_at >= day_start,
        )
    )).scalars().all()
    return sum(int(a or 0) for a in rows)
