# -*- coding: utf-8 -*-
"""مهاجرتِ مرحله ۲۶ — نام‌گذاریِ پایگاهِ لولِ نهایی (Villa) بر اساسِ عمارتِ هدف.

ستونِ جدید:
    - hideouts.final_variant  VARCHAR(32) NULL   (کلیدِ عمارتی که این ویلا برایش ساخته می‌شود)

اجرا:
    python3 migrate_stage26.py
"""
import asyncio

from app.database.engine import engine, init_models


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
    await init_models()
    print("✅ مدل‌ها بررسی/ساخته شدند.")

    async with engine.begin() as conn:
        await _add_column(conn, "hideouts", "final_variant", "VARCHAR(32)")

    print("🎉 مهاجرتِ مرحله ۲۶ کامل شد.")


if __name__ == "__main__":
    asyncio.run(main())
