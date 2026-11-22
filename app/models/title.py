# -*- coding: utf-8 -*-
"""مدل‌های سیستمِ القاب (مرحله ۱۱).

چهار جدولِ جدید:
  • PlayerStats  — شمارنده‌های دستاورد (مراحلِ بعدی این‌ها را زیاد می‌کنند)
  • PlayerTitle  — القابِ کسب‌شده‌ی هر بازیکن
  • TitleClaim   — دارنده‌ی فعلیِ هر لقبِ تک/یونیک (برای first-claim)
  • TitleProfile — لقبِ فعال + وضعیتِ اشتراک + لقبِ سفارشی

نیازی به پاک‌کردنِ دیتابیس نیست؛ create_all فقط جدول‌های جدید را می‌سازد.
"""
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class PlayerStats(Base):
    """شمارنده‌های دستاورد — مرجعِ شرطِ القاب.

    هر سیستم (جنگ، جاسوسی، شهر، ...) در مراحلِ بعدی فقط فیلدِ مربوطه را
    زیاد می‌کند و تابعِ evaluate_titles را صدا می‌زند. همه پیش‌فرض ۰.
    """
    __tablename__ = "player_stats"

    tg_user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    # 🔗 مرحله ۱۵.۵ — شمارنده‌های دزدی/زندان (اده‌شده به همین جدول تا دو تعریفِ متناقض برای یک جدول وجود نداشته باشد)
    xp_total: Mapped[int] = mapped_column(BigInteger, default=0)      # کلِ XP کسب‌شده در طولِ بازی
    thefts_done: Mapped[int] = mapped_column(Integer, default=0)      # دزدی‌های موفق
    thefts_caught: Mapped[int] = mapped_column(Integer, default=0)    # دفعاتِ دستگیری
    times_jailed: Mapped[int] = mapped_column(Integer, default=0)     # دفعاتِ تحملِ زندان
    bribes_paid: Mapped[int] = mapped_column(Integer, default=0)      # کلِ باج‌های پرداختی
    total_loot: Mapped[int] = mapped_column(BigInteger, default=0)    # مجموعِ قنیمتِ دزدی

    # جاسوسی و خرابکاری
    spy_success: Mapped[int] = mapped_column(Integer, default=0)
    sabotage_success: Mapped[int] = mapped_column(Integer, default=0)
    spy_tech_built: Mapped[int] = mapped_column(Integer, default=0)   # درصدِ درختِ فناوری

    # نبرد و جنگ
    battle_wins: Mapped[int] = mapped_column(Integer, default=0)
    mafia_wins: Mapped[int] = mapped_column(Integer, default=0)
    country_wars_won: Mapped[int] = mapped_column(Integer, default=0)
    win_streak: Mapped[int] = mapped_column(Integer, default=0)
    country_win_streak: Mapped[int] = mapped_column(Integer, default=0)
    battles_without_loss: Mapped[int] = mapped_column(Integer, default=0)
    consecutive_defense_wins: Mapped[int] = mapped_column(Integer, default=0)
    defenses_won: Mapped[int] = mapped_column(Integer, default=0)
    attacks_success: Mapped[int] = mapped_column(Integer, default=0)
    enemies_defeated: Mapped[int] = mapped_column(Integer, default=0)
    enemy_bases_destroyed: Mapped[int] = mapped_column(Integer, default=0)
    rival_bosses_killed: Mapped[int] = mapped_column(Integer, default=0)
    rival_gangs_destroyed: Mapped[int] = mapped_column(Integer, default=0)
    revenge_wins: Mapped[int] = mapped_column(Integer, default=0)
    war_assists: Mapped[int] = mapped_column(Integer, default=0)

    # قلمرو و اقتصاد
    cities_controlled: Mapped[int] = mapped_column(Integer, default=0)
    cities_captured: Mapped[int] = mapped_column(Integer, default=0)
    countries_founded: Mapped[int] = mapped_column(Integer, default=0)
    countries_conquered: Mapped[int] = mapped_column(Integer, default=0)
    companies: Mapped[int] = mapped_column(Integer, default=0)
    org_members: Mapped[int] = mapped_column(Integer, default=0)
    city_economy_pct: Mapped[int] = mapped_column(Integer, default=0)
    map_control_pct: Mapped[int] = mapped_column(Integer, default=0)
    military_power: Mapped[int] = mapped_column(Integer, default=0)   # 🆕 مرحله ۲۰ — قدرتِ نظامی (برای شرطِ القاب)

    # زمان/دوام و رتبه
    active_days: Mapped[int] = mapped_column(Integer, default=0)
    achievements_pct: Mapped[int] = mapped_column(Integer, default=0)
    satisfaction_days_90: Mapped[int] = mapped_column(Integer, default=0)
    power_rank1_days: Mapped[int] = mapped_column(Integer, default=0)
    female_rank: Mapped[int] = mapped_column(Integer, default=0)      # 0 = بدونِ رتبه
    female_legendary_titles: Mapped[int] = mapped_column(Integer, default=0)

    # پرچم‌های رویدادی (برای القابِ special)
    is_top_military: Mapped[bool] = mapped_column(Boolean, default=False)
    is_top_power: Mapped[bool] = mapped_column(Boolean, default=False)
    leads_biggest_gang: Mapped[bool] = mapped_column(Boolean, default=False)
    all_ports_controlled: Mapped[bool] = mapped_column(Boolean, default=False)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())  # 🔗 مرحله ۱۵.۵


class PlayerTitle(Base):
    """هر لقبی که یک بازیکن کسب کرده."""
    __tablename__ = "player_titles"

    id: Mapped[int] = mapped_column(primary_key=True)
    tg_user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    title_key: Mapped[str] = mapped_column(String(64), index=True)
    granted_at: Mapped[datetime] = mapped_column(server_default=func.now())


class TitleClaim(Base):
    """دارنده‌ی فعلیِ هر لقبِ تک/یونیک (فقط یک نفر)."""
    __tablename__ = "title_claims"

    title_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    tg_user_id: Mapped[int] = mapped_column(BigInteger)
    claimed_at: Mapped[datetime] = mapped_column(server_default=func.now())


class TitleProfile(Base):
    """لقبِ فعالِ بازیکن + وضعیتِ اشتراک + لقبِ سفارشی."""
    __tablename__ = "title_profiles"

    tg_user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    # active_kind: None | "earned" | "custom"
    active_kind: Mapped[str | None] = mapped_column(String(16), nullable=True)
    active_title_key: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # اشتراک (لقبِ سفارشی)
    custom_title: Mapped[str | None] = mapped_column(String(48), nullable=True)
    sub_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    def subscription_active(self, now: datetime | None = None) -> bool:
        now = now or datetime.utcnow()
        return self.sub_expires_at is not None and self.sub_expires_at > now


class TitleSeason(Base):
    """تنظیمات فصل تازه‌ی القاب؛ با create_all ساخته می‌شود."""
    __tablename__ = "title_seasons"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    unique_week_started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    migration_done: Mapped[bool] = mapped_column(Boolean, default=False)

class TitleApproval(Base):
    """هر اعطای لقب باید پیش از ثبت، به تایید ادمین اصلی برسد."""
    __tablename__ = "title_approvals"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tg_user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    title_key: Mapped[str] = mapped_column(String(64), index=True)
    source: Mapped[str] = mapped_column(String(32), default="auto")
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reviewed_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

class TitleWeekBaseline(Base):
    """اسنپ‌شات آمار برای مسابقه‌ی هفتگیِ لقب‌های تک."""
    __tablename__ = "title_week_baselines"
    tg_user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    week_started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    stats_json: Mapped[str] = mapped_column(Text, default="{}")
