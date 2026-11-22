# -*- coding: utf-8 -*-
"""مهاجرتِ مرحله ۲۱ — سیستمِ ادمین/ادمین‌مود.

جدول‌های جدید (توسطِ create_all ساخته می‌شوند):
    - admins          (ادمین‌ها: نقش، دسترسی‌ها، رمز، اجبارِ تغییرِ رمز)
    - admin_settings  (تنظیمات؛ مثلِ کانالِ گزارش)
    - admin_audit     (لاگِ کارهای ادمین)

ستون‌های جدید (با ALTER اضافه می‌شوند):
    - players.banned  BOOLEAN DEFAULT 0   (کاربرِ محدود/بن‌شده)

سپس ادمینِ اصلی (از روی MAIN_ADMIN_ID) seed می‌شود.

اجرا:
    python migrate_stage21.py
"""
import asyncio

from app.database.engine import async_session, engine, init_models


async def _column_exists(conn, table: str, column: str) -> bool:
    res = await conn.exec_driver_sql(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in res.fetchall())


async def _add_column(conn, table: str, column: str, ddl: str) -> None:
    if await _column_exists(conn, table, column):
        print(f"ℹ️  ستونِ {table}.{column} از قبل وجود دارد — رد شد.")
        return
    await conn.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")
    print(f"✅ ستونِ {table}.{column} اضافه شد.")


async def main() -> None:
    # 1) جدول‌های جدید (admins / admin_settings / admin_audit) و بقیه را بساز
    await init_models()
    print("✅ جدول‌های admins / admin_settings / admin_audit ساخته شدند (اگر نبودند).")

    # 2) ستونِ banned روی players
    async with engine.begin() as conn:
        await _add_column(conn, "players", "banned", "BOOLEAN DEFAULT 0")

    # 3) seed ادمینِ اصلی (از روی MAIN_ADMIN_ID)
    from app.services import admin_service
    async with async_session() as session:
        row = await admin_service.ensure_seed_main_admin(session)
        if row is not None:
            print(f"✅ ادمینِ اصلی seed شد (uid={row.tg_user_id}).")
        else:
            print("ℹ️  MAIN_ADMIN_ID تعریف نشده — seedِ ادمینِ اصلی رد شد.")

    print("🎉 مهاجرتِ مرحله ۲۱ کامل شد.")


if __name__ == "__main__":
    asyncio.run(main())
