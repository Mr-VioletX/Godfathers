from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class OwnedProfessional(Base):
    """یک حرفه‌ایِ استخدام‌شده توسط بازیکن."""
    __tablename__ = "owned_professionals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tg_user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    prof_key: Mapped[str] = mapped_column(String(32))  # کلیدِ حرفه‌ای از کاتالوگ
    level: Mapped[int] = mapped_column(Integer, default=1)

    # اگر در اسلاتِ یک عمارت فعال باشد، id آن عمارت این‌جاست؛ وگرنه None
    assigned_estate_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # ستون‌های آماده برای مرحله ۷ (زیردستان و حقوق) — الان استفاده نمی‌شوند
    subordinates: Mapped[int] = mapped_column(Integer, default=0)
    last_paid: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())