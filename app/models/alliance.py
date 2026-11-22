# -*- coding: utf-8 -*-
"""مدل‌های اتحادیه (مرحله ۱۸).

جدول‌های جدید:
  • alliances              — خودِ اتحادیه (آیدی، نام، رئیس، سطح، صندوق، تنظیمات)
  • alliance_members       — اعضا و نقش‌ها (leader/deputy/member)
  • alliance_join_requests — درخواست‌های عضویتِ در انتظار
  • alliance_wars          — تاریخچه‌ی جنگِ اتحادیه‌ها
  • alliance_war_votes     — جلسه‌ی رأی‌گیریِ حمله
  • alliance_war_ballots   — رأیِ تک‌تکِ اعضا
همه جدا از جدولِ players نگه داشته شده‌اند.
"""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class Alliance(Base):
    __tablename__ = "alliances"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tag: Mapped[str] = mapped_column(String(24), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(64))
    leader_id: Mapped[int] = mapped_column(BigInteger, index=True)

    level: Mapped[int] = mapped_column(Integer, default=1)
    mil_level: Mapped[int] = mapped_column(Integer, default=0)
    treasury: Mapped[int] = mapped_column(BigInteger, default=0)

    sub_pct: Mapped[int] = mapped_column(Integer, default=5)
    sub_days: Mapped[int] = mapped_column(Integer, default=7)
    min_power: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class AllianceMember(Base):
    __tablename__ = "alliance_members"
    __table_args__ = (
        UniqueConstraint("player_id", name="uq_alliance_member_player"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    alliance_id: Mapped[int] = mapped_column(Integer, index=True)
    player_id: Mapped[int] = mapped_column(BigInteger, index=True)
    role: Mapped[str] = mapped_column(String(16), default="member")
    contributed: Mapped[int] = mapped_column(BigInteger, default=0)
    joined_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class AllianceJoinRequest(Base):
    __tablename__ = "alliance_join_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    alliance_id: Mapped[int] = mapped_column(Integer, index=True)
    player_id: Mapped[int] = mapped_column(BigInteger, index=True)
    status: Mapped[str] = mapped_column(String(16), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class AllianceWar(Base):
    __tablename__ = "alliance_wars"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    attacker_id: Mapped[int] = mapped_column(Integer, index=True)   # alliance id
    defender_id: Mapped[int] = mapped_column(Integer, index=True)   # alliance id
    winner_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    loser_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    amount: Mapped[int] = mapped_column(BigInteger, default=0)
    attacker_won: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class AllianceWarVote(Base):
    """یک جلسه‌ی رأی‌گیریِ حمله به اتحادیه‌ی دیگر."""
    __tablename__ = "alliance_war_votes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    alliance_id: Mapped[int] = mapped_column(Integer, index=True)   # اتحادیه‌ی مهاجم
    target_id: Mapped[int] = mapped_column(Integer)                 # اتحادیه‌ی هدف
    initiator_id: Mapped[int] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(String(16), default="voting")  # voting|resolved|failed
    deadline: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class AllianceWarBallot(Base):
    __tablename__ = "alliance_war_ballots"
    __table_args__ = (
        UniqueConstraint("vote_id", "voter_id", name="uq_ballot_vote_voter"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    vote_id: Mapped[int] = mapped_column(Integer, index=True)
    voter_id: Mapped[int] = mapped_column(BigInteger)
    choice: Mapped[int] = mapped_column(Integer, default=0)   # 1 = موافق / 0 = مخالف
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
