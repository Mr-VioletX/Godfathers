# app/models/chat.py
"""مدل‌هایِ چت‌مود (مرحله ۱۳.۶).

شاملِ درخواستِ چت، جلسه‌ی چت، پیامِ آفلاین، کاربرانِ بلاک‌شده، گزارش و آرشیوِ پیام‌ها.
"""
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class ChatRequest(Base):
    __tablename__ = "chat_requests"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    requester_id: Mapped[int] = mapped_column(BigInteger, index=True)
    target_id: Mapped[int] = mapped_column(BigInteger, index=True)
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending|accepted|rejected|expired
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class ChatSession(Base):
    __tablename__ = "chat_sessions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_a: Mapped[int] = mapped_column(BigInteger, index=True)
    user_b: Mapped[int] = mapped_column(BigInteger, index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    archive_msg_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)  # id فایلِ ZIP در چنلِ آرشیو


class OfflineMessage(Base):
    __tablename__ = "offline_messages"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    from_id: Mapped[int] = mapped_column(BigInteger, index=True)
    to_id: Mapped[int] = mapped_column(BigInteger, index=True)
    text: Mapped[str] = mapped_column(Text)              # فقط متن (بدونِ عکس)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class BlockedUser(Base):
    __tablename__ = "blocked_users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_id: Mapped[int] = mapped_column(BigInteger, index=True)    # بلاک‌کننده
    blocked_id: Mapped[int] = mapped_column(BigInteger, index=True)  # بلاک‌شده
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ChatReport(Base):
    __tablename__ = "chat_reports"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    reporter_id: Mapped[int] = mapped_column(BigInteger, index=True)
    reported_id: Mapped[int] = mapped_column(BigInteger, index=True)
    reason: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="open")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ChatMessage(Base):
    """آرشیوِ پیام‌هایِ چت (ارجاع به چنلِ ذخیره‌سازی)."""
    __tablename__ = "chat_messages"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(Integer, index=True)
    from_id: Mapped[int] = mapped_column(BigInteger)
    kind: Mapped[str] = mapped_column(String(16))          # text|photo|voice|video_note
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    channel_msg_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
