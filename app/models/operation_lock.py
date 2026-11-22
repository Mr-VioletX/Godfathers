# -*- coding: utf-8 -*-
"""قفل پایدار عملیات اقتصادی؛ برای جلوگیری از اجرای هم‌زمان یک کاربر."""
from datetime import datetime
from sqlalchemy import BigInteger, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column
from app.database.base import Base

class EconomicOperationLock(Base):
    __tablename__ = "economic_operation_locks"
    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    operation_id: Mapped[str] = mapped_column(String(128), nullable=False)
    locked_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

class ProcessedOperation(Base):
    __tablename__ = "processed_operations"
    operation_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
