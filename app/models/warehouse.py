from datetime import datetime

from sqlalchemy import BigInteger, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class MainWarehouse(Base):
    """انبارِ اصلیِ کاربر (مرحله ۱۵). پیش‌نیاز: داشتنِ ۳ کارخانه."""
    __tablename__ = "main_warehouses"

    id: Mapped[int] = mapped_column(primary_key=True)
    tg_user_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    level: Mapped[int] = mapped_column(default=1)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class WarehouseStock(Base):
    """موجودیِ هر ماده/محصول در انبارِ اصلی."""
    __tablename__ = "warehouse_stocks"

    id: Mapped[int] = mapped_column(primary_key=True)
    warehouse_id: Mapped[int] = mapped_column(index=True)
    product_key: Mapped[str] = mapped_column(String(32))
    qty: Mapped[int] = mapped_column(default=0)
