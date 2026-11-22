# -*- coding: utf-8 -*-
"""🆕 v1.7.6.3 — بیمارستانِ دستی ـ 🆕 v1.7.6.4 — صفِ درمانِ زمان‌دار.

هر ردیف = مجروحانِ یک نبرد برای یک بازیکن.

درمان دیگر خودکار نیست: کاربر باید خودش واردِ
«نظامی ← 🏥 بیمارستان / تعمیر» شود و هزینهٔ همان ردیف را بپردازد.

اگر در چند جنگ شرکت کرده باشد، برای هر جنگ یک ردیفِ جداگانه با
مهلتِ جداگانه ساخته می‌شود.

اگر تا مهلتِ ۲۴ ساعته پرداخت نکند، ردیف به وضعیت «dead» می‌رود و
نیروها برای همیشه از دست می‌روند.

🆕 v1.7.6.4 — پس از پرداخت، ردیف در جا درمان نمی‌شود؛ واردِ وضعیت
«healing» می‌شود و پس از heal_hours ساعت (۲ تا ۸) نیروها برمی‌گردند.

create_all خودش این جدول را می‌سازد؛ ولی ستونِ تازه را به جدولِ موجود
اضافه نمی‌کند — مهاجرتِ ستون‌های v1.7.6.4 در app/database/engine.py انجام می‌شود.
"""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class HospitalWard(Base):
    __tablename__ = "hospital_wards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_id: Mapped[int] = mapped_column(BigInteger, index=True)
    # شناسهٔ نبردی که این مجروحان از آن آمده‌اند (برای جلوگیری از تکرار)
    battle_id: Mapped[int | None] = mapped_column(Integer, index=True, nullable=True)
    mode: Mapped[str] = mapped_column(String(16), default="classic")
    opponent_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # {"militia": 12, "tank": 3, ...}
    units_json: Mapped[str] = mapped_column(Text, default="{}")
    unit_count: Mapped[int] = mapped_column(Integer, default=0)
    cost: Mapped[int] = mapped_column(BigInteger, default=0)
    # wounded | healing | healed | dead
    status: Mapped[str] = mapped_column(String(16), default="wounded", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # آیا پیامِ «نیروهایت مردند» فرستاده شده؟
    notified_dead: Mapped[int] = mapped_column(Integer, default=0)

    # ---------------- 🆕 v1.7.6.4 — صفِ درمانِ زمان‌دار ----------------
    # لحظهٔ پایانِ درمان (پس از پرداخت پر می‌شود)
    heal_until: Mapped[datetime | None] = mapped_column(DateTime, index=True, nullable=True)
    # مدتِ درمانِ این ردیف (ساعت) — تصادفی ۲ تا ۸
    heal_hours: Mapped[int] = mapped_column(Integer, default=0)
    # تلفاتِ پایهٔ قابلِ درمان — برای شفافیتِ «از X تا، Y مجروح = Z٪»
    base_loss_count: Mapped[int] = mapped_column(Integer, default=0)
    # آیا پیامِ «درمان تمام شد» فرستاده شده؟
    notified_healed: Mapped[int] = mapped_column(Integer, default=0)
