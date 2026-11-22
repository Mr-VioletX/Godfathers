# -*- coding: utf-8 -*-
"""🆕 v1.8.3.0 — ذخیره‌ی پک ایموجیِ فعال (تعویض از ادمین‌مود، بدونِ تغییرِ کد).

جدولِ تک‌ردیفه: پکِ فعال + نگاشتِ کاملِ آن (JSON). با create_all ساخته می‌شود؛
به جدول‌های قدیمی هیچ ستونی اضافه نمی‌شود (بدونِ مهاجرت).
"""
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class EmojiPackSetting(Base):
    """پک ایموجیِ سفارشیِ فعال — همیشه یک ردیف با id=1."""
    __tablename__ = "emoji_pack_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)  # همیشه ۱
    pack_name: Mapped[str] = mapped_column(String(64), default="")
    mapping_json: Mapped[str] = mapped_column(Text, default="{}")   # {emoji: custom_emoji_id}
    emoji_count: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
