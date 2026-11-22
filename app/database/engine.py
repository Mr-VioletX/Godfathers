# app/database/engine.py
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import settings   # مثلاً: "sqlite+aiosqlite:///godfather.db"
from app.database.base import Base


# ⚠️ همه‌ی مدل‌ها باید اینجا import شوند تا Base.metadata از وجودشان باخبر شود
# و create_all جدول‌هایشان را بسازد. (import برای side-effect است، نه استفاده‌ی مستقیم.)
from app.models import (  # noqa: F401
    player,
    estate,
    professional,
    hideout,
    factory,   # 🆕 مرحله ۹
    market,    # 🆕 مرحله ۹
    assistant,
    mafia_city,  # 🆕 مرحله ۴۶ (بچ ۴) — شهرسازِ جدید (جایگزینِ city/country)
    spy,       # 🆕 مرحله ۱۳
    contact,   # 🆕 مرحله ۱۳
    chat,      # 🆕 مرحله ۱۳.۶
    sports,    # 🆕 مرحله ۱۴
    warehouse, # 🆕 مرحله ۱۵
    player_stats,  # 🆕 مرحله ۱۵.۵ — آمار و منبعِ XP
    transfer,      # 🆕 مرحله ۱۶ — لاگِ انتقالِ دارایی
    war,           # 🆕 مرحله ۱۷ — جنگ/شهر/کشور
    alliance,      # 🆕 مرحله ۱۸ — اتحادیه‌ها + جنگِ کشورها
    military,        # 🆕 مرحله ۱۹ — سیستمِ نظامی
    branding,        # 🆕 مرحله ۱۹.۱ — برندسازی
    worldbank,       # 🆕 مرحله ۱۹.۲ — بانکِ جهانی
    subscription,    # 🆕 مرحله ۲۰ — اشتراکِ ۴ سطحی
    news,            # 🆕 مرحله ۲۰ — اخبار
    purchase,        # 🆕 مرحله ۲۰ — تاریخچه
    admin,           # 🆕 مرحله ۲۱ — ادمین/تنظیمات/لاگ
    alliance_perm,
    activity,   # 🆕 مرحله ۳۰ — دسترسی‌های معاونِ اتحادیه
    live_battle,     # 🆕 مرحله ۴۶ — نبردِ زنده‌ی ۱۵ دقیقه‌ای
    rank,            # 🆕 مرحله ۴۶ (بچ ۳) — کاپ/لیگِ رنکینگ
    title,           # 🆕 مرحله ۴۶ (بچ ۵) — فصل/تأییدِ القاب
    operation_lock,  # 🆕 قفل پایدار عملیات اقتصادی
    referral,        # 🆕 سیستم لینک دعوت
    hospital,        # 🆕 v1.7.6.3 — بیمارستانِ دستی (مجروحانِ هر نبرد)
    alliance_war,    # 🆕 v1.7.9.1 — ارتش/جنگِ زنده‌ی اتحادیه
    football,        # 🆕 v1.7.9.2 — فوتبال منیجر
    football_standing, # 🆕 v1.7.9.6 — آمار لیگ
    football_market,   # 🆕 v1.7.9.7 — بازار نقل‌وانتقال
    football_friday,   # 🆕 v1.7.9.9 — لیگ جمعهٔ رسمی
    football_live,     # 🆕 v1.7.10.0 — بازی زندهٔ ۱۰ دقیقه‌ای
    football_ucl,      # 🆕 v1.7.10.0 — لیگ قهرمانان دوشنبه
    football_tactics,  # 🆕 v1.8.1.0 — ترکیب و تاکتیک (F6)
    dark_world,       # 🆕 v1.8.3.0 — دنیای سیاه و رنک داخلی
)

# موتورِ async دیتابیس
# Stage 27 (performance): keep connections warm and recycled so button clicks stay fast.
_engine_kwargs: dict = {"echo": False, "pool_pre_ping": True}
_is_sqlite = settings.database_url.startswith("sqlite")
if _is_sqlite:
    # 🆕 فیکسِ بحرانی: بدونِ محدودسازیِ pool، هر session یک اتصالِ aiosqlite تازه می‌سازد
    # و aiosqlite برای هر اتصال یک تردِ سیستم‌عامل جدید باز می‌کند. زیرِ بارِ همزمان
    # (چند کاربر/چند کلیک هم‌زمان)، تعدادِ تردها از سقفِ حسابِ هاست (nproc/LVE) رد می‌شود
    # و با خطای "RuntimeError: can't start new thread" کرش می‌کند -- همان علتِ اصلیِ
    # کندی/تایم‌اوتِ دکمه‌ها و قطعیِ پاسخ. با pool_size/max_overflow مشخص، تعدادِ محدودی
    # اتصال (و درنتیجه ترد) دوباره استفاده می‌شود به‌جایِ ساختنِ بی‌رویه‌ی اتصالِ تازه.
    from sqlalchemy.pool import AsyncAdaptedQueuePool

    _engine_kwargs.update(
        poolclass=AsyncAdaptedQueuePool,
        pool_size=5,
        max_overflow=5,
        pool_timeout=30,
        pool_recycle=1800,
        # aiosqlite همچنان به این timeout برای جلوگیری از "database is locked" نیاز دارد
        connect_args={"timeout": 30},
    )
else:
    _engine_kwargs.update(
        pool_size=10,
        max_overflow=20,
        pool_recycle=1800,
    )

engine = create_async_engine(settings.database_url, **_engine_kwargs)


if _is_sqlite:
    # Stage 27 (performance): WAL + relaxed sync make reads/writes far faster under
    # concurrent players, and a busy timeout prevents lock waits from freezing buttons.
    from sqlalchemy import event as _sa_event

    @_sa_event.listens_for(engine.sync_engine, "connect")
    def _sqlite_fast_pragmas(dbapi_connection, _record):  # noqa: ANN001
        try:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA temp_store=MEMORY")
            cursor.execute("PRAGMA cache_size=-16000")   # ~16MB page cache
            cursor.execute("PRAGMA busy_timeout=30000")
            cursor.close()
        except Exception:
            # never let a pragma failure break the connection
            pass

# کارخانه‌ی ساختِ session
# استفاده: `async with async_session() as session:`
async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def init_models() -> None:
    """جدول‌هایی که هنوز وجود ندارند را می‌سازد (جدول‌های موجود دست‌نخورده می‌مانند)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # create_all ستون جدید را به جدول موجود اضافه نمی‌کند؛ مبلغ پرداختی صف‌های نظامی
        # برای بازگردانی دقیق هزینهٔ لغو، روی دیتابیس‌های قبلی هم اضافه می‌شود.
        if _is_sqlite:
            cols = (await conn.exec_driver_sql("PRAGMA table_info(military_training_queue)")).fetchall()
            mtq_col_names = {row[1] for row in cols}
            if "paid_cost" not in mtq_col_names:
                await conn.exec_driver_sql(
                    "ALTER TABLE military_training_queue ADD COLUMN paid_cost BIGINT NOT NULL DEFAULT 0"
                )
            # v1.7.6.5 -- mayor columns on mafia_cities
            _mc = {row[1] for row in (await conn.exec_driver_sql(
                "PRAGMA table_info(mafia_cities)"
            )).fetchall()}
            for _col, _decl in (("mayor_key", "VARCHAR(16)"),
                                ("mayor_hired_at", "TIMESTAMP"),
                                ("last_mayor_msg_at", "TIMESTAMP"),
                                ("mayor_paid_at", "TIMESTAMP"),
                                ("prod_day", "VARCHAR(10)"),
                                ("prod_today_json", "TEXT")):
                if _col not in _mc:
                    await conn.exec_driver_sql(
                        "ALTER TABLE mafia_cities ADD COLUMN %s %s" % (_col, _decl)
                    )
            city_cols = (await conn.exec_driver_sql("PRAGMA table_info(mafia_cities)")).fetchall()
            city_col_names = {row[1] for row in city_cols}
            if "resources_json" not in city_col_names:
                await conn.exec_driver_sql("ALTER TABLE mafia_cities ADD COLUMN resources_json TEXT NOT NULL DEFAULT '{}'")
            if "base_population" not in city_col_names:
                await conn.exec_driver_sql("ALTER TABLE mafia_cities ADD COLUMN base_population BIGINT NOT NULL DEFAULT 0")
            if "original_qty" not in mtq_col_names:
                await conn.exec_driver_sql("ALTER TABLE military_training_queue ADD COLUMN original_qty INTEGER NOT NULL DEFAULT 0")

            # v1.7.6.2 schema patches — create_all does not add columns to existing tables
            brand_cols = {row[1] for row in (await conn.exec_driver_sql("PRAGMA table_info(brands)")).fetchall()}
            if brand_cols and "campaign_cooldowns" not in brand_cols:
                await conn.exec_driver_sql("ALTER TABLE brands ADD COLUMN campaign_cooldowns TEXT DEFAULT '{}'")
            purch_cols = {row[1] for row in (await conn.exec_driver_sql("PRAGMA table_info(purchases)")).fetchall()}
            if purch_cols and "payment_info" not in purch_cols:
                await conn.exec_driver_sql("ALTER TABLE purchases ADD COLUMN payment_info TEXT")
            if purch_cols and "approved_for_pay" not in purch_cols:
                await conn.exec_driver_sql("ALTER TABLE purchases ADD COLUMN approved_for_pay INTEGER DEFAULT 0")

            # v1.7.6.4 schema patches -- hospital heal queue
            hosp_cols = {row[1] for row in (await conn.exec_driver_sql("PRAGMA table_info(hospital_wards)")).fetchall()}
            if hosp_cols and "heal_until" not in hosp_cols:
                await conn.exec_driver_sql("ALTER TABLE hospital_wards ADD COLUMN heal_until DATETIME")
            if hosp_cols and "heal_hours" not in hosp_cols:
                await conn.exec_driver_sql("ALTER TABLE hospital_wards ADD COLUMN heal_hours INTEGER DEFAULT 0")
            if hosp_cols and "base_loss_count" not in hosp_cols:
                await conn.exec_driver_sql("ALTER TABLE hospital_wards ADD COLUMN base_loss_count INTEGER DEFAULT 0")
            if hosp_cols and "notified_healed" not in hosp_cols:
                await conn.exec_driver_sql("ALTER TABLE hospital_wards ADD COLUMN notified_healed INTEGER DEFAULT 0")

            # v1.7.7.9 — گاوصندوق بانک (ستون‌ها روی جدول موجود)
            try:
                _ba = {row[1] for row in (await conn.exec_driver_sql("PRAGMA table_info(bank_accounts)")).fetchall()}
                if _ba and "safebox_level" not in _ba:
                    await conn.exec_driver_sql("ALTER TABLE bank_accounts ADD COLUMN safebox_level INTEGER DEFAULT 0")
                if _ba and "safebox_balance" not in _ba:
                    await conn.exec_driver_sql("ALTER TABLE bank_accounts ADD COLUMN safebox_balance BIGINT DEFAULT 0")
            except Exception:
                pass

            # v1.7.8.17 — انبارِ اختصاصیِ هر محصول (کارخانه و برند)
            for _tbl in ("factory_products", "brand_products"):
                try:
                    _pc = {row[1] for row in (await conn.exec_driver_sql(
                        "PRAGMA table_info(%s)" % _tbl
                    )).fetchall()}
                    if _pc and "capacity_level" not in _pc:
                        await conn.exec_driver_sql(
                            "ALTER TABLE %s ADD COLUMN capacity_level INTEGER NOT NULL DEFAULT 1" % _tbl
                        )
                    # v1.7.8.18 — خطِ تولیدِ دومِ هر محصول (کارخانه و برند)
                    if _pc:
                        for _col, _decl in (("status2", "VARCHAR(16) DEFAULT 'idle'"),
                                            ("started_at2", "DATETIME"),
                                            ("percent2", "INTEGER DEFAULT 100"),
                                            ("pending_units2", "INTEGER DEFAULT 0")):
                            if _col not in _pc:
                                await conn.exec_driver_sql(
                                    "ALTER TABLE %s ADD COLUMN %s %s" % (_tbl, _col, _decl)
                                )
                except Exception:
                    pass
        else:
            await conn.exec_driver_sql(
                "ALTER TABLE military_training_queue ADD COLUMN IF NOT EXISTS paid_cost BIGINT NOT NULL DEFAULT 0"
            )
            await conn.exec_driver_sql("ALTER TABLE mafia_cities ADD COLUMN IF NOT EXISTS resources_json TEXT NOT NULL DEFAULT '{}'")
            await conn.exec_driver_sql("ALTER TABLE mafia_cities ADD COLUMN IF NOT EXISTS base_population BIGINT NOT NULL DEFAULT 0")
            try:
                await conn.exec_driver_sql("ALTER TABLE brands ADD COLUMN IF NOT EXISTS campaign_cooldowns TEXT DEFAULT '{}'")
            except Exception:
                pass
            try:
                await conn.exec_driver_sql("ALTER TABLE purchases ADD COLUMN IF NOT EXISTS payment_info TEXT")
            except Exception:
                pass
            try:
                await conn.exec_driver_sql("ALTER TABLE purchases ADD COLUMN IF NOT EXISTS approved_for_pay INTEGER DEFAULT 0")
            except Exception:
                pass
            # v1.7.6.4 schema patches -- hospital heal queue
            # v1.7.6.5 -- mayor columns on mafia_cities
            for _mcol, _mtype in (("mayor_key", "VARCHAR(16)"),
                                  ("mayor_hired_at", "TIMESTAMP"),
                                  ("last_mayor_msg_at", "TIMESTAMP"),
                                  ("mayor_paid_at", "TIMESTAMP"),
                                  ("prod_day", "VARCHAR(10)"),
                                  ("prod_today_json", "TEXT")):
                try:
                    await conn.exec_driver_sql(
                        "ALTER TABLE mafia_cities ADD COLUMN IF NOT EXISTS %s %s"
                        % (_mcol, _mtype)
                    )
                except Exception:
                    pass
            for _hcol, _htype in (
                ("heal_until", "TIMESTAMP"),
                ("heal_hours", "INTEGER DEFAULT 0"),
                ("base_loss_count", "INTEGER DEFAULT 0"),
                ("notified_healed", "INTEGER DEFAULT 0"),
            ):
                try:
                    await conn.exec_driver_sql(
                        f"ALTER TABLE hospital_wards ADD COLUMN IF NOT EXISTS {_hcol} {_htype}"
                    )
                except Exception:
                    pass

            # v1.7.7.9 — گاوصندوق بانک
            try:
                await conn.exec_driver_sql("ALTER TABLE bank_accounts ADD COLUMN IF NOT EXISTS safebox_level INTEGER DEFAULT 0")
            except Exception:
                pass
            try:
                await conn.exec_driver_sql("ALTER TABLE bank_accounts ADD COLUMN IF NOT EXISTS safebox_balance BIGINT DEFAULT 0")
            except Exception:
                pass
            # v1.7.8.17 — انبارِ اختصاصیِ هر محصول (کارخانه و برند)
            for _tbl in ("factory_products", "brand_products"):
                try:
                    await conn.exec_driver_sql(
                        "ALTER TABLE %s ADD COLUMN IF NOT EXISTS capacity_level INTEGER NOT NULL DEFAULT 1" % _tbl
                    )
                except Exception:
                    pass
                # v1.7.8.18 — خطِ تولیدِ دومِ هر محصول (کارخانه و برند)
                for _col, _decl in (("status2", "VARCHAR(16) DEFAULT 'idle'"),
                                    ("started_at2", "TIMESTAMP"),
                                    ("percent2", "INTEGER DEFAULT 100"),
                                    ("pending_units2", "INTEGER DEFAULT 0")):
                    try:
                        await conn.exec_driver_sql(
                            "ALTER TABLE %s ADD COLUMN IF NOT EXISTS %s %s" % (_tbl, _col, _decl)
                        )
                    except Exception:
                        pass

            # حذف سقف‌های سفارشی متن برای دستور و پاسخ دستیار دوم در دیتابیس‌های قبلی.
            for table, column in (
                ("second_assistants", "trigger_text"),
                ("second_assistants", "reply_text"),
                ("second_assistant_commands", "trigger_text"),
                ("second_assistant_commands", "reply_text"),
            ):
                await conn.exec_driver_sql(
                    f"ALTER TABLE {table} ALTER COLUMN {column} TYPE TEXT"
                )


