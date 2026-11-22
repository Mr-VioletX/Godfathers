# -*- coding: utf-8 -*-
"""مهاجرتِ مرحله ۲۸ — کارخانه‌های یکتا + تولیدِ درصدی.

ستون‌های جدید:
    - factories.factory_key        VARCHAR(32)  (نوعِ یکتای کارخانه)
    - factories.title              VARCHAR(64)  (نامِ اختیاری)
    - factory_products.percent     INTEGER      (درصدِ انتخابیِ حجمِ خالی)
    - factory_products.pending_units INTEGER    (تعدادِ واحدِ درِ حالِ تولید)

پس از افزودنِ ستون‌ها، داده‌ی قدیمی بازسازی می‌شود:
    • factory_key از روی product_key حدس می‌زند.
    • اگر کاربر چند کارخانه‌ی هم‌نوع داشته باشد، نوعِ تکراری به نوعِ آزادِ دیگر منتقل می‌شود
      (تا قانونِ «از هر کارخانه فقط یکی» رعایت شود) و اگر جایی نماند، دست نمی‌خورد.

اجرا:
    python3 migrate_stage28.py
"""
import asyncio

from app.database.engine import engine, init_models
from app.data import factories as FAC


async def _column_exists(conn, table: str, column: str) -> bool:
    res = await conn.exec_driver_sql(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in res.fetchall())


async def _table_exists(conn, table: str) -> bool:
    res = await conn.exec_driver_sql(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
    )
    return res.fetchone() is not None


async def _add_column(conn, table: str, column: str, ddl: str) -> None:
    if not await _table_exists(conn, table):
        print(f"ℹ️  جدولِ {table} وجود ندارد — رد شد.")
        return
    if await _column_exists(conn, table, column):
        print(f"ℹ️  ستونِ {table}.{column} از قبل وجود دارد — رد شد.")
        return
    await conn.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")
    print(f"✅ ستونِ {table}.{column} اضافه شد.")


async def _backfill_factory_keys(conn) -> None:
    """نوعِ کارخانه‌های قدیمی را پُر و یکتا می‌کند."""
    if not await _table_exists(conn, "factories"):
        return
    res = await conn.exec_driver_sql(
        "SELECT id, tg_user_id, product_key, COALESCE(factory_key, '') FROM factories ORDER BY tg_user_id, id"
    )
    rows = res.fetchall()
    used: dict[int, set] = {}
    fixed = 0
    for fid, uid, product_key, fkey in rows:
        taken = used.setdefault(uid, set())
        key = fkey if fkey in FAC.FACTORY_TYPES else (FAC.factory_of_product(product_key) or "")
        if not key or key in taken:
            free = [k for k in FAC.FACTORY_ORDER if k not in taken]
            key = free[0] if free else key
        if not key:
            continue
        taken.add(key)
        if key != fkey:
            await conn.exec_driver_sql(
                "UPDATE factories SET factory_key = ? WHERE id = ?", (key, fid)
            )
            fixed += 1
    print(f"✅ نوعِ {fixed} کارخانه‌ی قدیمی تعیین/اصلاح شد.")


async def _fix_products(conn) -> None:
    """محصولاتِ نامرتبط با نوعِ کارخانه را به محصولِ معادلِ همان کارخانه نگاشت می‌کند."""
    if not await _table_exists(conn, "factory_products"):
        return
    res = await conn.exec_driver_sql(
        "SELECT fp.id, fp.factory_id, fp.product_key, f.factory_key "
        "FROM factory_products fp JOIN factories f ON f.id = fp.factory_id ORDER BY fp.id"
    )
    rows = res.fetchall()
    per_factory: dict[int, set] = {}
    moved = 0
    for fp_id, factory_id, product_key, factory_key in rows:
        allowed = FAC.products_for_factory(factory_key or "")
        if not allowed:
            continue
        have = per_factory.setdefault(factory_id, set())
        key = product_key
        if key not in allowed or key in have:
            free = [k for k in allowed if k not in have]
            if not free:
                await conn.exec_driver_sql("DELETE FROM factory_products WHERE id = ?", (fp_id,))
                continue
            key = free[0]
        if key != product_key:
            await conn.exec_driver_sql(
                "UPDATE factory_products SET product_key = ? WHERE id = ?", (key, fp_id)
            )
            moved += 1
        have.add(key)
    print(f"✅ {moved} محصولِ قدیمی به کارخانه‌ی مربوطِ خودش نگاشت شد.")


async def main() -> None:
    await init_models()
    print("✅ مدل‌ها بررسی/ساخته شدند.")

    async with engine.begin() as conn:
        await _add_column(conn, "factories", "factory_key", "VARCHAR(32) DEFAULT ''")
        await _add_column(conn, "factories", "title", "VARCHAR(64)")
        await _add_column(conn, "factory_products", "percent", "INTEGER DEFAULT 50")
        await _add_column(conn, "factory_products", "pending_units", "INTEGER DEFAULT 0")
        await _backfill_factory_keys(conn)
        await _fix_products(conn)
        # 🆕 سازه‌های کشور (جدول توسط init_models ساخته می‌شود)
        await conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_country_buildings_owner "
            "ON country_buildings (owner_id)"
        )

    print("🎉 مهاجرتِ مرحله ۲۸ کامل شد.")


if __name__ == "__main__":
    asyncio.run(main())
