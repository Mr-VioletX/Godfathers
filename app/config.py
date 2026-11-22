# app/config.py
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _parse_ids(raw) -> list[int]:
    """
    پارسِ لیستِ شناسه‌های عددی از مقدارِ خام.
    اجازه می‌دهد ADMIN_IDS در .env به‌صورتِ رشته‌ی جداشده با کاما/فاصله/سمی‌کولن
    (مثلاً ADMIN_IDS=123456789,987654321) یا حتی فرمتِ JSON مانند [1, 2] نوشته شود.
    """
    if raw is None or raw == "":
        return []
    if isinstance(raw, int):
        return [raw]
    if isinstance(raw, (list, tuple)):
        return [int(x) for x in raw]
    if isinstance(raw, str):
        s = raw.strip().strip("[]")
        if not s:
            return []
        parts = s.replace(";", ",").replace(" ", ",").split(",")
        return [int(p) for p in parts if p.strip()]
    return []


class Settings(BaseSettings):
    bot_token: str
    database_url: str = "sqlite+aiosqlite:///godfather.db"

    @field_validator("archive_channel_id", "creator_id", "news_channel_id", mode="before")
    @classmethod
    def _empty_str_to_none(cls, v):
        """اگر مقدار در .env خالی گذارده شود (مثلاً ARCHIVE_CHANNEL_ID=)، به‌جای خطای تبدیل‌نشدن به int، None در نظر گرفته می‌شود (اختیاریِ واقعی)."""
        if isinstance(v, str) and v.strip() == "":
            return None
        return v

    # 🆕 مرحله ۱۱ — شناسه‌های عددیِ ادمین‌ها (برای /give_title و /take_title)
    # در .env به‌صورتِ:  ADMIN_IDS=123456789,987654321
    #
    # ⚠️ رفعِ باگِ ریشه‌ای: این فیلد عمداً str تعریف شده، نه list[int].
    # اگر نوعِ فیلد list[int] باشد، pydantic-settings پیش از رسیدنِ مقدار به هر
    # ولیدیتورِ سفارشی، خودش تلاش می‌کند مقدارِ .env را با json.loads دیکد کند؛
    # چون "123456789,987654321" یک JSON معتبر نیست، همان‌جا با
    # SettingsError شکست می‌خورد (حتی پیش از اجرای هر ولیدیتور). با نگه‌داشتنِ
    # نوعِ str، این مرحله‌ی JSON کاملاً دور زده می‌شود و پارس‌کردن را خودمان
    # در _parse_ids انجام می‌دهیم.
    admin_ids_raw: str = Field(default="", validation_alias="ADMIN_IDS")

    # 🆕 مرحله ۱۳.۶ — تنظیماتِ چت‌مود و حالتِ ادمین
    archive_channel_id: int | None = None   # چنلِ خصوصیِ آرشیوِ چت‌ها
    admin_password: str | None = None       # رمزِ فعال‌سازیِ حالتِ ادمین
    creator_id: int | None = None           # آیدیِ عددیِ سازنده‌ی ربات

    # 🆕 مرحله ۲۰ — چنلِ اخبارِ روزانه (اختیاری)؛ اگر تنظیم شود، دایجستِ شبانه آنجا منتشر می‌شود
    news_channel_id: int | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",   # ← متغیرهای اضافه‌ی .env را نادیده بگیر
    )

    @property
    def admin_ids(self) -> list[int]:
        return _parse_ids(self.admin_ids_raw)


settings = Settings()

# سازگاری با راهنمای مرحله ۱۱: هندلرِ ادمین از `from app.config import ADMIN_IDS` استفاده می‌کند
ADMIN_IDS = settings.admin_ids

# 🆕 مرحله ۱۳.۶ — ادمینِ اصلی (سازنده یا اولین ادمین)
MAIN_ADMIN_ID = settings.creator_id or (settings.admin_ids[0] if settings.admin_ids else None)
