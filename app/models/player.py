from datetime import datetime

from sqlalchemy import BigInteger, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class Player(Base):
    __tablename__ = "players"

    id: Mapped[int] = mapped_column(primary_key=True)
    tg_user_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(64))
    gender: Mapped[str | None] = mapped_column(String(16), nullable=True)

    level: Mapped[int] = mapped_column(default=1)
    xp: Mapped[int] = mapped_column(default=0)
    cash: Mapped[int] = mapped_column(BigInteger, default=1000)
    fatigue: Mapped[int] = mapped_column(default=0)

    last_theft_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # --- مرحله ۵: پروفایل، حریم خصوصی و اعلام آنلاین ---
    photo_file_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    custom_title: Mapped[str | None] = mapped_column(String(64), nullable=True)
    privacy_settings: Mapped[str | None] = mapped_column(String(512), nullable=True)
    announce_settings: Mapped[str | None] = mapped_column(String(512), nullable=True)
    last_announce_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # --- صفحه ۵.۵: اشتراک و القاب به‌دست‌آمده ---
    is_premium: Mapped[bool] = mapped_column(default=False)
    earned_titles: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    # --- مرحله ۱۳: یوزرنیم (برای هدف‌گیری جاسوسی) + جریمهٔ مرگِ جاسوس ---
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    spy_penalty_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    spy_penalty_to: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    spy_penalty_last_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # --- مرحله ۱۳.۶: آخرین فعالیت (تشخیصِ آنلاین/آفلاین برای چت‌مود) ---
    last_seen: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    
    # --- مرحله ۱۶: زندان، شمارنده‌ی باج، و لِوِلِ کول‌داونِ کاپولا ---
    jail_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    jail_forced: Mapped[bool] = mapped_column(default=False)   # زندانِ اجباری (پرداخت غیرفعال)
    # 🆕 مرحله ۲۱: محدودیت/بنِ کاربر توسطِ ادمین (ربات به پیام‌هایِ این کاربر پاسخ نمی‌دهد)
    banned: Mapped[bool] = mapped_column(default=False)
    bribe_count: Mapped[int] = mapped_column(default=0)          # تعدادِ باج‌های پرداختی (در ۱۱مین دستگیری، اجباری)
    kapatolo_cd_level: Mapped[int] = mapped_column(default=0)    # لِوِلِ بخشِ کول‌داونِ کاپولا (۰..۲۰)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())