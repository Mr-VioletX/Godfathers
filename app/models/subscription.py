# -*- coding: utf-8 -*-
"""مدلِ «اشتراکِ ۴ سطحی» (مرحله ۲۰).

یک جدولِ جدید، جدا از players — نیازی به تغییرِ ستون‌های بازیکن نیست.
create_all فقط این جدولِ جدید را می‌سازد.
"""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class Subscription(Base):
    """اشتراکِ فعلیِ هر بازیکن.

    tier یکی از کلیدهای TIER_ORDER در app/data/subscription.py است.
    اگر expires_at گذشته باشد، سطحِ موثر دوباره free در نظر گرفته می‌شود.
    activated_at = لحظه‌ی آخرین فعال‌سازی.
    """
    __tablename__ = "subscriptions"

    tg_user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    tier: Mapped[str] = mapped_column(String(16), default="free")
    activated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    def is_active(self, now: datetime | None = None) -> bool:
        now = now or datetime.utcnow()
        return self.expires_at is not None and self.expires_at > now
