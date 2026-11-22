from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class Estate(Base):
    """یک عمارت متعلق به یک بازیکن (مثلاً Cupola)."""
    __tablename__ = "estates"
    __table_args__ = (
        # هر بازیکن از هر نوع عمارت فقط یکی می‌تواند داشته باشد
        UniqueConstraint("tg_user_id", "role_key", name="uq_user_estate"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tg_user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    role_key: Mapped[str] = mapped_column(String(32))  # نوعِ عمارت، مثل "cupola"
    level: Mapped[int] = mapped_column(Integer, default=1)
    last_collected_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())