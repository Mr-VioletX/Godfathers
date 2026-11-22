# -*- coding: utf-8 -*-
"""مدلِ مرحله ۱۹.۲ — حسابِ بانکِ جهانیِ بازیکن."""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class BankAccount(Base):
    __tablename__ = "bank_accounts"

    owner_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    deposit: Mapped[int] = mapped_column(BigInteger, default=0)
    deposit_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    loan_principal: Mapped[int] = mapped_column(BigInteger, default=0)
    # v1.7.7.6 گاوصندوق
    safebox_level: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    safebox_balance: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")
    loan_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
