# -*- coding: utf-8 -*-
"""مهاجرتِ مرحلهٔ ۷۷ — گاوصندوقِ بانکِ مافیایی (v1.7.8.0)

دو ستونِ تازه روی جدولِ bank_accounts می‌سازد:
    safebox_level    INTEGER  DEFAULT 0
    safebox_balance  BIGINT   DEFAULT 0

چرا لازم است: create_all فقط جدولِ نبوده را می‌سازد و هرگز به جدولِ
موجود ستون اضافه نمی‌کند. پس دیتابیسی که قبل از گاوصندوق ساخته شده
این دو ستون را ندارد و هر بار که بانک خوانده شود خطا می‌دهد.

اجرا:
    cd ~/godfather_bot
    python migrate_stage77_safebox.py

این اسکریپت ایمن است — چند بار اجرایش هیچ ضرری ندارد.
"""
import asyncio

from app.database.engine import engine, init_models

TABLE = "bank_accounts"
COLUMNS = (
    ("safebox_level", "INTEGER"),
    ("safebox_balance", "BIGINT"),
)


async def _columns_of(conn, is_sqlite: bool) -> set:
    if is_sqlite:
        rows = (await conn.exec_driver_sql("PRAGMA table_info(%s)" % TABLE)).fetchall()
        return {r[1] for r in rows}
    rows = (await conn.exec_driver_sql(
        "SELECT column_name FROM information_schema.columns WHERE table_name = '%s'" % TABLE
    )).fetchall()
    return {r[0] for r in rows}


async def main() -> None:
    # init_models خودش جدول‌های نبوده را می‌سازد و مهاجرت‌های داخلی را هم می‌زند.
    await init_models()
    print("✅ init_models اجرا شد")

    is_sqlite = engine.url.get_backend_name().startswith("sqlite")
    print("   بک‌اند: %s" % engine.url.get_backend_name())

    async with engine.begin() as conn:
        cols = await _columns_of(conn, is_sqlite)
        if not cols:
            print("⚠️  جدول %s پیدا نشد — init_models باید آن را ساخته باشد." % TABLE)
            return

        for name, sqltype in COLUMNS:
            if name in cols:
                print("   • %-16s از قبل وجود داشت" % name)
                continue
            if is_sqlite:
                sql = "ALTER TABLE %s ADD COLUMN %s %s DEFAULT 0" % (TABLE, name, sqltype)
            else:
                sql = "ALTER TABLE %s ADD COLUMN IF NOT EXISTS %s %s DEFAULT 0" % (
                    TABLE, name, sqltype)
            await conn.exec_driver_sql(sql)
            print("   • %-16s اضافه شد" % name)

        # ردیف‌های قدیمی ممکن است NULL باشند؛ صفرشان می‌کنیم؛ در غیر این صورت
        # محاسبهٔ قابلِ غارت بودن روی None خطا می‌دهد.
        for name, _t in COLUMNS:
            await conn.exec_driver_sql(
                "UPDATE %s SET %s = 0 WHERE %s IS NULL" % (TABLE, name, name)
            )
        print("   • مقادیرِ NULL به صفر تبدیل شد")

        final = await _columns_of(conn, is_sqlite)
        missing = [n for n, _t in COLUMNS if n not in final]
        rows = (await conn.exec_driver_sql("SELECT COUNT(*) FROM %s" % TABLE)).fetchall()
        count = int(rows[0][0]) if rows else 0

    if missing:
        print("\n❌ ناقص ماند: %r" % missing)
        raise SystemExit(1)
    print("\n✅ مهاجرتِ گاوصندوق کامل شد — %d حسابِ بانکی آماده است" % count)


if __name__ == "__main__":
    asyncio.run(main())
