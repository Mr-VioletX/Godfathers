# -*- coding: utf-8 -*-
"""v1.7.9.1 — مدل‌های ارتش و جنگِ زنده‌ی اتحادیه.

همه‌ی جدول‌ها تازه‌اند تا create_all بدونِ مهاجرتِ دستی بسازدشان؛ به جدول‌های
قدیمیِ اتحادیه/بازیکن هیچ ستونی اضافه نمی‌شود.
"""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class AllianceBarracks(Base):
    """سربازخانه‌ی اتحادیه: سطح، تنظیماتِ تولیدِ خودکار و آخرین اجرای روزانه."""
    __tablename__ = "alliance_barracks"

    alliance_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    level: Mapped[int] = mapped_column(Integer, default=1)
    auto_enabled: Mapped[int] = mapped_column(Integer, default=0)
    auto_min_json: Mapped[str] = mapped_column(Text, default="{}")   # {unit_key: حداقل}
    last_auto_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class AllianceUnitStack(Base):
    """پشته‌ی نیروهای اتحادیه — هر ردیف: یک نوع واحد با تعداد و سطح."""
    __tablename__ = "alliance_unit_stacks"
    __table_args__ = (
        UniqueConstraint("alliance_id", "unit_key", name="uq_alliance_stack"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    alliance_id: Mapped[int] = mapped_column(Integer, index=True)
    unit_key: Mapped[str] = mapped_column(String(24))
    count: Mapped[int] = mapped_column(BigInteger, default=0)
    level: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class AllianceTrainQueue(Base):
    """صفِ تولید (اسکادرانی) — با رسیدن به ready_at به پشته اضافه می‌شود."""
    __tablename__ = "alliance_train_queue"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    alliance_id: Mapped[int] = mapped_column(Integer, index=True)
    unit_key: Mapped[str] = mapped_column(String(24))
    squads: Mapped[int] = mapped_column(Integer, default=1)
    units: Mapped[int] = mapped_column(BigInteger, default=0)
    ready_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class AllianceWarState(Base):
    """وضعیتِ جنگیِ اتحادیه: سپر/مصونیت و کول‌داونِ حمله (مثل WarState بازیکن)."""
    __tablename__ = "alliance_war_states"

    alliance_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    shield_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_attack_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class AllianceBattle(Base):
    """نبردِ زنده‌ی ۱۵ دقیقه‌ای بینِ دو اتحادیه (مثل LiveBattle)."""
    __tablename__ = "alliance_battles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    attacker_id: Mapped[int] = mapped_column(Integer, index=True)   # alliance id
    defender_id: Mapped[int] = mapped_column(Integer, index=True)   # alliance id
    mode: Mapped[str] = mapped_column(String(16), default="alliance")
    started_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    ends_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    plan_json: Mapped[str] = mapped_column(Text, default="{}")
    # تا این زمان مهاجم نمی‌تواند دوباره به همین اتحادیه حمله کند (قفلِ غنیمت)
    loot_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finalized: Mapped[int] = mapped_column(Integer, default=0)
    notified: Mapped[int] = mapped_column(Integer, default=0)


class AllianceWard(Base):
    """ردیفِ مجروحانِ اتحادیه (بیمارستان) — ۲۴ ساعت مهلتِ درمان از صندوق."""
    __tablename__ = "alliance_wards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    alliance_id: Mapped[int] = mapped_column(Integer, index=True)
    battle_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    opponent_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    units_json: Mapped[str] = mapped_column(Text, default="{}")     # {unit_key: count}
    unit_count: Mapped[int] = mapped_column(BigInteger, default=0)
    cost: Mapped[int] = mapped_column(BigInteger, default=0)
    status: Mapped[str] = mapped_column(String(16), default="wounded")  # wounded|healed|dead
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class AllianceRankRow(Base):
    """رنکینگِ جدای اتحادیه‌ها — کاپ و کارنامه‌ی جنگ."""
    __tablename__ = "alliance_ranks"

    alliance_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cups: Mapped[int] = mapped_column(Integer, default=0, index=True)
    wins: Mapped[int] = mapped_column(Integer, default=0)
    losses: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class AllianceFeeState(Base):
    """آخرین کسرِ اشتراکِ عضویت از اعضا (طبقِ تنظیمِ رئیس: sub_pct هر sub_days روز)."""
    __tablename__ = "alliance_fee_states"

    alliance_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    last_charge_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
