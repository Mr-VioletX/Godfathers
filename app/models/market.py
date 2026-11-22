from datetime import datetime

from sqlalchemy import DateTime, Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class MarketPrice(Base):
    __tablename__ = "market_prices"

    # کلیدِ محصول = شناسه‌ی ردیف (هر محصول یک ردیف)
    product_key: Mapped[str] = mapped_column(String(32), primary_key=True)
    price: Mapped[float] = mapped_column(Float)
    # تاریخچه‌ی قیمت به‌صورتِ JSON (لیستِ اعداد) — برای نمودار
    history: Mapped[str] = mapped_column(Text, default="[]")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)