# -*- coding: utf-8 -*-
"""مدلِ «تاریخچه‌ی خریدِ اشتراک» (مرحله ۲۰).

هر درخواست/خریدِ اشتراک یک ردیف اینجا دارد و یک «کدِ پیگیری»ِ یکتا می‌گیرد
که کاربر با آن می‌تواند خریدِ خود را پیگیری کند.
جدولِ جدید — create_all آن را می‌سازد.

status: pending (درخواست) / active (فعال‌شده) / failed (ناموفق) /
        canceled (لغو‌شده) / expired (منقضی)
جریانِ تأیید/پرداختِ ادمین‌محور در مرحله ۲۱ افزوده می‌شود.
"""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class PurchaseHistory(Base):
    __tablename__ = "purchases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tg_user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    tier: Mapped[str] = mapped_column(String(16))
    tracking_code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    amount: Mapped[int] = mapped_column(Integer, default=0)
    note: Mapped[str | None] = mapped_column(String(256), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), index=True
    )
    activated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # 🆕 مرحله ۲۱.۱ — رسید/مسندِ پرداخت که کاربر می‌تواند بفرستد (عکس/فایل)
    receipt_file_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    receipt_type: Mapped[str | None] = mapped_column(String(16), nullable=True)  # "photo" یا "document"
    # 🆕 مرحله ۲۱.۱ — یادداشتی از اینکه کدام ادمین درخواست را پردازش/رد کرد
    handled_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    # v1.7.6 — جریان امن پرداخت
    payment_info: Mapped[str | None] = mapped_column(String(512), nullable=True)  # متن روش پرداخت ادمین
    approved_for_pay: Mapped[int] = mapped_column(Integer, default=0)  # 1=تأیید اولیه، منتظر رسید/پرداخت

