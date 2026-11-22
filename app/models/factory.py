from datetime import datetime

from sqlalchemy import BigInteger, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class Factory(Base):
    """کارخانه (پوسته). از مرحله ۱۵ چندمحصولی شده است:
    محصولاتِ بازشده و انبار/تولیدِ هرکدام در جدولِ factory_products نگه‌داری می‌شود.
    """
    __tablename__ = "factories"

    id: Mapped[int] = mapped_column(primary_key=True)
    tg_user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    # محصولِ اولیه (کارخانه با این ساخته شده)؛ دسته‌ی کارخانه از روی همین تعیین می‌شود
    product_key: Mapped[str] = mapped_column(String(32))
    # 🐞 مرحله ۳۰: رفعِ TypeError — این دو ستون قبلاً فقط با migrate_stage28.py به خودِ
    # دیتابیس اضافه شده بودند ولی هیچ‌وقت به این کلاسِ مدل افزوده نشده بودند، پس
    # SQLAlchemy مقدارهای factory_key= و title= را رد می‌کرد و دکمه‌ی «ساختِ کارخانه» می‌شکست.
    factory_key: Mapped[str | None] = mapped_column(String(32), nullable=True, default="")  # نوعِ یکتای کارخانه (۵ کارخانه‌ی مرحله ۲۸)
    title: Mapped[str | None] = mapped_column(String(64), nullable=True)  # نامِ اختیاریِ کارخانه
    # سطحِ قدیمی (سازگاری با نسخه‌های پیشین؛ دیگر مستقیماً استفاده نمی‌شود)
    level: Mapped[int] = mapped_column(default=1)
    # وضعیت/انبارِ قدیمی (legacy) — از مرحله ۱۵ به factory_products منتقل شد
    status: Mapped[str] = mapped_column(String(16), default="idle")
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    stock: Mapped[int] = mapped_column(default=0)
    # 🆕 مرحله ۱۵ — چهار مسیرِ ارتقا
    capacity_level: Mapped[int] = mapped_column(default=1)   # 📦 ظرفیتِ انبارِ کارخانه
    speed_level: Mapped[int] = mapped_column(default=1)      # ⚡ سرعتِ تولید
    expansion_level: Mapped[int] = mapped_column(default=1)  # 🏗️ گسترش (تنوعِ محصول)
    line_level: Mapped[int] = mapped_column(default=1)       # 🧵 خطِ تولیدِ همزمان
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class FactoryProduct(Base):
    """هر ردیف = یک محصولِ باز‌شده در یک کارخانه (انبار + وضعیتِ تولیدِ مستقل)."""
    __tablename__ = "factory_products"

    id: Mapped[int] = mapped_column(primary_key=True)
    factory_id: Mapped[int] = mapped_column(index=True)
    product_key: Mapped[str] = mapped_column(String(32))
    stock: Mapped[int] = mapped_column(default=0)
    # idle (بی‌کار) یا producing (در حالِ تولید)
    status: Mapped[str] = mapped_column(String(16), default="idle")
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # 🐞 مرحله ۳۰: همان رفعِ TypeError برایِ FactoryProduct (percent= و pending_units=)
    percent: Mapped[int] = mapped_column(default=50)          # درصدِ انتخابیِ حجمِ خالیِ انبار برایِ تولید
    pending_units: Mapped[int] = mapped_column(default=0)     # تعدادِ واحدِ در حالِ تولید
    # 🆕 v1.7.8.18 — خطِ تولیدِ دومِ همین محصول (هر محصول ۲ خطِ مستقل دارد).
    # ستون‌های بالا = خطِ ۱ و ستون‌های زیر = خطِ ۲؛ nullable هستند تا دیتابیس‌های
    # قدیمی بدونِ دستکاری کار کنند.
    status2: Mapped[str | None] = mapped_column(String(16), nullable=True, default="idle")
    started_at2: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    percent2: Mapped[int | None] = mapped_column(nullable=True, default=100)
    pending_units2: Mapped[int | None] = mapped_column(nullable=True, default=0)
    # 🆕 v1.7.8.17 — انبارِ اختصاصیِ همین محصول (۱۰ سطح: ۵٬۰۰۰ ← ۱۵٬۰۰۰ واحد)
    capacity_level: Mapped[int] = mapped_column(default=1)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class FactoryQueueItem(Base):
    """🆕 v1.7.8.17 — صفِ ساختِ کارخانه.

    اگر کاربر بخواهد بیش از حجمِ انبارِ یک محصول تولید کند، سفارشش
    در صف می‌نشیند و به‌محضِ خالی‌شدنِ جا (فروش یا انتقال به انبارِ
    اصلی) خودکار شروع می‌شود.

    هزینهٔ موادِ اولیه همان لحظهٔ ثبت در صف کسر می‌شود (paid_cost) و اگر
    سفارش حذف شود ۱۰۰٪ برمی‌گردد.
    """
    __tablename__ = "factory_queue"

    id: Mapped[int] = mapped_column(primary_key=True)
    factory_id: Mapped[int] = mapped_column(index=True)
    fp_id: Mapped[int] = mapped_column(index=True)
    product_key: Mapped[str] = mapped_column(String(32))
    units: Mapped[int] = mapped_column(default=0)
    percent: Mapped[int] = mapped_column(default=100)
    paid_cost: Mapped[int] = mapped_column(BigInteger, default=0)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
