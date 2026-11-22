# -*- coding: utf-8 -*-
"""مهاجرتِ مرحله ۳۱ — دو ستونِ تازه.

چه چیزی اضافه می‌شود؟
  • cities.origin            — founded (خرید/تأسیس) یا captured (تصرف در جنگ)
  • captured_cities.city_id  — پیوندِ شهرِ تصرفی به ردیفِ واقعیِ cities

همچنین برای شهرهایی که پیش از این مرحله تصرف شده بودند (و هیچ ردیفی در cities
نداشتند) یک ردیفِ شهرِ کامل ساخته می‌شود تا در منوی «شهرها» دیده شوند و
قابلِ ارتقا/مالیات/درآمد/فروش باشند.

اجرا (یک‌بار، روی هاست یا لپ‌تاپ):
    python migrate_stage31.py
اجرای چندباره بی‌خطر است (idempotent).
"""
import os
import sqlite3
import sys

BASE = os.path.dirname(os.path.abspath(__file__))

_GEOS = ("plain", "coastal", "mountain", "desert", "island")


def _geo_for_key(key: str) -> str:
    return _GEOS[sum(ord(ch) for ch in str(key)) % len(_GEOS)]


def find_db() -> str:
    for name in ("godfather.db", "app.db", "database.db"):
        p = os.path.join(BASE, name)
        if os.path.exists(p):
            return p
    raise SystemExit("❌ فایلِ دیتابیس پیدا نشد. این اسکریپت را کنارِ godfather.db اجرا کن.")


def columns(cur, table: str) -> set:
    try:
        cur.execute(f"PRAGMA table_info({table})")
    except sqlite3.Error:
        return set()
    return {row[1] for row in cur.fetchall()}


def table_exists(cur, table: str) -> bool:
    cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
    )
    return cur.fetchone() is not None


def main() -> int:
    db = find_db()
    print(f"📂 دیتابیس: {db}")
    con = sqlite3.connect(db)
    cur = con.cursor()

    # --- ۱) cities.origin ---
    if not table_exists(cur, "cities"):
        print("⚠️ جدول cities وجود ندارد — رد شد (با اجرای ربات خودبه‌خود ساخته می‌شود).")
    elif "origin" in columns(cur, "cities"):
        print("✅ cities.origin از قبل وجود دارد.")
    else:
        cur.execute(
            "ALTER TABLE cities ADD COLUMN origin VARCHAR(16) DEFAULT 'founded'"
        )
        cur.execute("UPDATE cities SET origin='founded' WHERE origin IS NULL")
        print("🆕 cities.origin اضافه شد.")

    # --- ۲) captured_cities.city_id ---
    if not table_exists(cur, "captured_cities"):
        print("⚠️ جدول captured_cities وجود ندارد — رد شد.")
        con.commit()
        con.close()
        return 0
    if "city_id" in columns(cur, "captured_cities"):
        print("✅ captured_cities.city_id از قبل وجود دارد.")
    else:
        cur.execute("ALTER TABLE captured_cities ADD COLUMN city_id INTEGER")
        print("🆕 captured_cities.city_id اضافه شد.")

    # --- ۳) ساختِ ردیفِ cities برای شهرهای تصرفیِ قدیمی ---
    if not table_exists(cur, "cities"):
        con.commit()
        con.close()
        return 0

    cur.execute(
        "SELECT id, owner_id, city_key, name, population FROM captured_cities "
        "WHERE city_id IS NULL"
    )
    pending = cur.fetchall()
    made = 0
    city_cols = columns(cur, "cities")
    for row_id, owner_id, city_key, name, population in pending:
        # اگر قبلاً شهری با همین نام و مالک ساخته شده، فقط وصلش کن
        cur.execute(
            "SELECT id FROM cities WHERE tg_user_id=? AND name=? LIMIT 1",
            (owner_id, name),
        )
        found = cur.fetchone()
        if found:
            cur.execute(
                "UPDATE captured_cities SET city_id=? WHERE id=?", (found[0], row_id)
            )
            if "origin" in city_cols:
                cur.execute(
                    "UPDATE cities SET origin='captured' WHERE id=?", (found[0],)
                )
            continue

        fields = [
            "tg_user_id",
            "name",
            "geo_type",
            "population",
            "satisfaction",
            "tax_rate",
            "independent",
            "is_active",
            "purchase_price",
        ]
        values = [
            owner_id,
            name,
            _geo_for_key(city_key),
            int(population or 0),
            45,
            10,
            0,
            0,
            0,
        ]
        if "origin" in city_cols:
            fields.append("origin")
            values.append("captured")
        placeholders = ",".join("?" for _ in fields)
        cur.execute(
            f"INSERT INTO cities ({','.join(fields)}) VALUES ({placeholders})",
            values,
        )
        cur.execute(
            "UPDATE captured_cities SET city_id=? WHERE id=?",
            (cur.lastrowid, row_id),
        )
        made += 1

    con.commit()
    con.close()
    print(f"🏙️ شهرِ تصرفیِ مهاجرت‌داده‌شده: {made}")
    print("✅ مهاجرتِ مرحله ۳۱ تمام شد.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
