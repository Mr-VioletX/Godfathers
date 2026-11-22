# app/models/spy.py
"""مدلِ جاسوس (مرحله ۱۳).

هر ردیف = یک جاسوسِ متعلق به یک کاربر. مقادیرِ محاسباتی (درآمد،
احتمالِ دستگیری، زمانِ چرخه، غرامت) ذخیره نمی‌شوند بلکه از روی `level`
در `app/data/espionage.py` حساب می‌شوند تا بالانس در یک جا قابلِ تغییر باشد.
"""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class Spy(Base):
    __tablename__ = "spies"
    __table_args__ = (
        # هر کاربر در هر اسلات فقط یک جاسوس دارد
        UniqueConstraint("owner_id", "slot", name="uq_spy_owner_slot"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_id: Mapped[int] = mapped_column(BigInteger, index=True)   # tg_user_id صاحب
    slot: Mapped[int] = mapped_column(Integer)                      # ۱..۵
    level: Mapped[int] = mapped_column(Integer, default=1)

    # وضعیت: idle | active | captured | dead
    status: Mapped[str] = mapped_column(String(16), default="idle")
    target_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    deployed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    next_report_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    captured_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_intel: Mapped[str | None] = mapped_column(String(2048), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
