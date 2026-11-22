from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class Assistant(Base):
    __tablename__ = "assistants"

    # هر کاربر فقط یک دستیار دارد → tg_user_id کلیدِ اصلی
    tg_user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(32), default="کنسیلیری")
    photo_file_id: Mapped[str | None] = mapped_column(String(256), nullable=True)

    # 🆕 مرحله ۲۰: سطحِ ارتقایِ دستیار (۱..۴).
    # هر سطح، بخش‌هایِ بیشتری را برای گزارش‌دادن باز می‌کند.
    upgrade_level: Mapped[int] = mapped_column(Integer, default=1)

    # تنظیماتِ یادآوری (از بخشِ ویرایشِ دستیار روشن/خاموش می‌شوند)
    notify_salary: Mapped[bool] = mapped_column(Boolean, default=True)
    notify_production: Mapped[bool] = mapped_column(Boolean, default=True)
    notify_income: Mapped[bool] = mapped_column(Boolean, default=True)
    notify_tips: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class SecondAssistant(Base):
    """دستیار دومِ اشتراکی؛ فرمان و پاسخ فقط با ریپلای اجرا می‌شود."""
    __tablename__ = "second_assistants"
    tg_user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(32), default="مشاور")
    photo_file_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    trigger_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    reply_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class SecondAssistantCommand(Base):
    __tablename__ = "second_assistant_commands"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_id: Mapped[int] = mapped_column(BigInteger, index=True)
    trigger_text: Mapped[str] = mapped_column(Text, index=True)
    reply_text: Mapped[str] = mapped_column(Text)

class SecondAssistantChat(Base):
    __tablename__ = "second_assistant_chats"
    owner_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, index=True)
    message_id: Mapped[int] = mapped_column(Integer)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
