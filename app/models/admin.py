# -*- coding: utf-8 -*-
"""مدل‌های سیستمِ ادمین (مرحله ۲۱ — بخشِ نهایی).

شامل:
  • AdminUser        — ادمین‌ها (اصلی/فرعی) + دسترسی‌ها + رمز
  • AdminSetting     — تنظیماتِ سراسری (مثلاً کانالِ گزارش) به‌صورتِ key/value
  • AdminAudit       — لاگِ کارهایِ مدیریتی (چه کسی چه کاری کرد)

دسترسی‌ها در ستونِ permissions به‌صورتِ JSON (لیستی از کلیدها) ذخیره می‌شوند؛
ادمینِ اصلی (role="main") همیشه همه‌ی دسترسی‌ها را دارد.
"""
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class AdminUser(Base):
    __tablename__ = "admins"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tg_user_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    # "main" = ادمینِ اصلی (خدایِ بازی) | "admin" = ادمینِ فرعی
    role: Mapped[str] = mapped_column(String(16), default="admin")
    # JSON list از کلیدِ دسترسی‌ها (برای main نادیده گرفته می‌شود)
    permissions: Mapped[str | None] = mapped_column(Text, nullable=True, default="[]")
    # هشِ رمز (sha256 با salt)؛ فرمت: "<salt>$<hash>"
    password_hash: Mapped[str | None] = mapped_column(String(160), nullable=True)
    # در اولین ورود باید رمز را عوض کند
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=True)
    # فعال/غیرفعال (عزل = active=False؛ به کلمه‌ی ادمین‌مود پاسخ نمی‌دهد)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    # 🆕 مرحله ۲۲.۱ — درِ حالتِ ادمین (پایدار در دیتابیس تا با ری‌استارتِ ربات/پسنجر خارج نشود؛
    # فقط با زدنِ «خروج از حالتِ ادمین مود» یا عزل‌شدن، False می‌شود)
    session_active: Mapped[bool] = mapped_column(Boolean, default=False)
    # نامی که ادمینِ اصلی هنگامِ انتصاب ثبت می‌کند (اختیاری)
    label: Mapped[str | None] = mapped_column(String(64), nullable=True)
    assigned_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class AdminSetting(Base):
    """تنظیماتِ سراسری key/value (مثلاً report_channel_id, report_channel_title)."""
    __tablename__ = "admin_settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class AdminAudit(Base):
    """لاگِ کارهایِ مدیریتی برای ردگیری و پاسخگویی."""
    __tablename__ = "admin_audit"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    admin_id: Mapped[int] = mapped_column(BigInteger, index=True)
    action: Mapped[str] = mapped_column(String(64))
    target_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class SpamReport(Base):
    """گزارش‌های اسپم/تکرار اکشن برای نمایش در ادمین‌مود."""
    __tablename__ = "spam_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tg_user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    user_label: Mapped[str | None] = mapped_column(String(128), nullable=True)
    chat_label: Mapped[str | None] = mapped_column(String(128), nullable=True)
    kind: Mapped[str] = mapped_column(String(24), default="event")
    action: Mapped[str | None] = mapped_column(Text, nullable=True)
    count: Mapped[int] = mapped_column(Integer, default=0)
    window_seconds: Mapped[int] = mapped_column(Integer, default=30)
    status: Mapped[str] = mapped_column(String(16), default="new", index=True)  # new | read | sent
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class GameRestriction(Base):
    """محدودیت کنترلی ادمین روی بخش‌های بازی برای همه یا یک کاربر خاص."""
    __tablename__ = "game_restrictions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    section: Mapped[str] = mapped_column(String(64), index=True)
    tg_user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class GameNumberSetting(Base):
    """تنظیم عددی قابل تغییر از پنل ادمین؛ برای هزینه‌ها/ضرایب/سقف‌ها."""
    __tablename__ = "game_number_settings"
    key: Mapped[str] = mapped_column(String(96), primary_key=True)
    value: Mapped[str] = mapped_column(String(64))
    label: Mapped[str | None] = mapped_column(String(128), nullable=True)
    updated_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
