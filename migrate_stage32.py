# -*- coding: utf-8 -*-
"""Stage 32 migration: index for fsm_states + safety net.

در مرحلهٔ 32، جدول fsm_states که از مرحلهٔ 30 وجود دارد اکنون روی هر دو نسخه (هاست/معمولی)
از یک انبار پایدار استفاده می‌شود (قبلاً فقط روی هاست فعال بود). این اسکریپت فقط
یک ایندکسِ جدید روی ستونِ updated_at اضافه می‌کند تا خواندن/پاکسازیِ وضعیت‌های منقضی
سریع‌تر شود. خودِ fsm_storage.py هم همین ایندکس را لازی می‌سازد، پس اجرای این اسکریپت اختیاری
است و فقط برای یکسانی با تمام مراحلِ قبلی است.

usage:  python3 migrate_stage32.py
"""
import asyncio

from app.database.engine import engine, init_models


SQL = (
    """
    CREATE TABLE IF NOT EXISTS fsm_states (
        key TEXT PRIMARY KEY,
        state TEXT,
        data TEXT,
        updated_at TEXT
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_fsm_states_updated ON fsm_states (updated_at)",
)


async def main() -> None:
    from sqlalchemy import text

    await init_models()
    async with engine.begin() as conn:
        for stmt in SQL:
            await conn.execute(text(stmt))
    print("stage 32 migration done")


if __name__ == "__main__":
    asyncio.run(main())
