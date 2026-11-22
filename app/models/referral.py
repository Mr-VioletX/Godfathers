from datetime import datetime, date
from sqlalchemy import BigInteger, Date, DateTime, Integer, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from app.database.base import Base
class Referral(Base):
    __tablename__ = "referrals"
    invited_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    referrer_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
class ReferralBonusDay(Base):
    __tablename__ = "referral_bonus_days"
    id: Mapped[int] = mapped_column(primary_key=True)
    referrer_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    active_date: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    pct: Mapped[int] = mapped_column(Integer, nullable=False)
    invited_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    __table_args__ = (UniqueConstraint("referrer_id", "active_date", "invited_id", name="uq_ref_bonus"),)

class PendingReferral(Base):
    """دعوتِ در انتظار — v1.7.9

    payload لینک دعوت قبل از ثبت‌نام اینجا می‌ماند تا با بلاکِ جوین اجباری
    یا پاک شدنِ state گم نشود؛ بعد از ساختِ شخصیت مصرف و پاک می‌شود.
    """
    __tablename__ = "pending_referrals"
    tg_user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    referrer_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
