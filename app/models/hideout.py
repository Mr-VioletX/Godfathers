from datetime import datetime

from sqlalchemy import BigInteger, Integer, String, DateTime, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class Hideout(Base):
    """پایگاه هر بازیکن. این ردیف فقط وقتی ساخته می‌شود که بازیکن پایگاه بخرد."""
    __tablename__ = "hideouts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tg_user_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)

    base_type: Mapped[str] = mapped_column(String(32))  # نوعِ پایگاهِ خریداری‌شده

    # هر ستون = سطحِ ویژگیِ امضای یک تیر (۰ تا ۵)
    security_level: Mapped[int] = mapped_column(Integer, default=0)    # 🥷 مخفی‌کاری (Covo)
    safehouse_level: Mapped[int] = mapped_column(Integer, default=0)   # 💤 بازیابی (Rifugio)
    vault_level: Mapped[int] = mapped_column(Integer, default=0)       # 💰 خزانه (Quartiere)
    authority_level: Mapped[int] = mapped_column(Integer, default=0)   # 👑 اقتدار (تیرِ ۴ / پایگاهِ تخصصی)

    # 🆕 مرحله ۲۶: کدام پایگاهِ تخصصیِ تیرِ ۴ ساخته شده (= عمارتی که اجازهِ ساختش را می‌دهد)
    # (کلیدِ یکی از ESTATES؛ همیشه همزمان با رسیدن به تیرِ ۴ مقداردهی می‌شود)
    final_variant: Mapped[str | None] = mapped_column(String(32), nullable=True, default=None)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


async def get_hideout(session: AsyncSession, tg_user_id: int):
    """پایگاه بازیکن را برمی‌گرداند؛ اگر هنوز پایگاهی نخریده باشد، None."""
    result = await session.execute(
        select(Hideout).where(Hideout.tg_user_id == tg_user_id)
    )
    return result.scalar_one_or_none()


async def buy_base(session: AsyncSession, tg_user_id: int, base_type: str) -> "Hideout":
    """یک پایگاهِ تازه از نوعِ مشخص برای بازیکن می‌سازد (commit در جای فراخوانی)."""
    hideout = Hideout(tg_user_id=tg_user_id, base_type=base_type)
    session.add(hideout)
    await session.flush()  # تا id ساخته شود
    return hideout