# app/models/contact.py
"""مدلِ «اشخاصِ اضافه‌شده» (Contacts) — مرحله ۱۳.

بلوکِ مشترکِ انتخابِ هدف/گیرنده برای جاسوسی، انتقالِ دارایی و جنگ.
کاربر در گروه روی پیامِ شخص ریپلای می‌کند و «افزودن» می‌فرستد.
"""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class Contact(Base):
    __tablename__ = "contacts"
    __table_args__ = (
        UniqueConstraint("owner_id", "contact_id", name="uq_contact_owner_target"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_id: Mapped[int] = mapped_column(BigInteger, index=True)     # صاحبِ دفترچه
    contact_id: Mapped[int] = mapped_column(BigInteger, index=True)   # tg_user_id شخصِ افزوده‌شده
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    display_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    added_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
