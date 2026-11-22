#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""تعمیرِ کاربرانی که قبلاً دچارِ باگ‌های نظامی / حقوق شده‌اند (مرحله ۶۸).

این اسکریپت مستقیماً روی فایلِ SQLite کار می‌کند و هیچ وابستگی‌ای به
سایر پکیج‌ها ندارد (پس خطای ModuleNotFoundError: sqlalchemy نمی‌دهد).

چه چیزهایی را درست می‌کند:
  1) لولِ نامعتبرِ نیروها (upgrade_level = 0 یا NULL)  →  ۱
     این همان ردپایی است که «ریستِ نظامیِ قدیم» باقی گذاشته.
  2) زمانِ صفِ پرورش را با نرخِ جدیدِ نصف‌شده دوباره می‌سازد
     (باگِ «۹۰۲ کماندو = ۱۰۵ ساعت ولی ۸۴۰۰ تا = ۲۰ ساعت»).
  3) زمانِ صفِ ارتقا را هم نصف می‌کند.
  4) مبدأِ حقوقِ حرفه‌ای‌ها را پر می‌کند (دکمهٔ پرداختِ حقوق که کار نمی‌کرد).
  5) کلیدِ نیروهای ناشناخته (مثلاً ballistic به‌جای ballistic_missile) را گزارش/تصحیح می‌کند.

طرزِ استفاده:
    python3 fix_stage68_military_repair.py --dry-run      # فقط گزارش، بدون تغییر
    python3 fix_stage68_military_repair.py --apply        # اعمالِ تغییرات (با بک‌آپِ خودکار)

بازگرداندنِ دستیِ لولِ نیروهای یک کاربر (وقتی لولش پاک شده):
    python3 fix_stage68_military_repair.py --set-all-levels 8459726639 3 --apply
    python3 fix_stage68_military_repair.py --set-level 8459726639 commando 5 --apply

گزینهٔ اختیاری: --db /path/to/godfather.db
"""
import argparse
import os
import shutil
import sqlite3
import sys
import warnings
from datetime import datetime, timedelta

warnings.filterwarnings("ignore", category=DeprecationWarning)


def utcnow() -> datetime:
    return datetime.now()

# --------------------------------------------------------------------------
# جدولِ زمانِ جدید (دقیقاً همانی که در app/data/military.py هست)
# --------------------------------------------------------------------------
TRAIN_SECONDS_BY_UNIT = {
    "militia": 75, "rifleman": 110, "commando": 210,
    "pistol": 60, "rifle": 105, "rpg": 180,
    "apc": 375, "tank": 525, "heavy_tank": 750,
    "aa_gun": 275, "sam": 450,
    "rocket": 550, "ballistic_missile": 825,
    "fighter": 700, "jet": 1000,
    "bomber": 850, "stealth_bomber": 1250,
}
TRAIN_DEFAULT_PER_UNIT = 150
TRAIN_MIN_SECONDS = 30
TRAIN_MAX_SECONDS = 365 * 24 * 60 * 60

# کلیدهایِ قدیمی/غلط که در دیتابیس دیده شده‌اند → کلیدِ درست
UNIT_KEY_ALIASES = {
    "ballistic": "ballistic_missile",
    "missile": "rocket",
    "aa": "aa_gun",
    "heavytank": "heavy_tank",
    "stealth": "stealth_bomber",
}


def per_unit_seconds(unit_key: str) -> int:
    return int(TRAIN_SECONDS_BY_UNIT.get(unit_key, TRAIN_DEFAULT_PER_UNIT))


def train_total_seconds(unit_key: str, qty: int) -> int:
    total = per_unit_seconds(unit_key) * max(1, int(qty or 1))
    return int(max(TRAIN_MIN_SECONDS, min(TRAIN_MAX_SECONDS, total)))


def upgrade_total_seconds(qty: int, target_level: int) -> int:
    total = max(300, int(qty or 1) * 20 * (2 * max(1, int(target_level or 1))))
    return min(36 * 60 * 60, total)


# --------------------------------------------------------------------------
# کمکی‌ها
# --------------------------------------------------------------------------
def find_db(explicit=None) -> str:
    if explicit:
        if not os.path.exists(explicit):
            sys.exit("❌ فایلِ دیتابیس پیدا نشد: %s" % explicit)
        return explicit
    here = os.path.dirname(os.path.abspath(__file__))
    for cand in (
        os.path.join(here, "godfather.db"),
        os.path.join(here, "data", "godfather.db"),
        "godfather.db",
    ):
        if os.path.exists(cand):
            return cand
    sys.exit("❌ godfather.db پیدا نشد. با --db مسیر را بده.")


def parse_dt(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip().replace("T", " ").replace("Z", "")
    if "." in text:
        text = text.split(".", 1)[0]
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def fmt(seconds: float) -> str:
    seconds = int(max(0, seconds))
    h, rem = divmod(seconds, 3600)
    return "%dh %02dm" % (h, rem // 60)


def table_exists(cur, name) -> bool:
    cur.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,))
    return cur.fetchone() is not None


# --------------------------------------------------------------------------
# تعمیرها
# --------------------------------------------------------------------------
def repair_unit_keys(cur, apply_changes, log):
    if not table_exists(cur, "military_units"):
        return
    cur.execute("SELECT DISTINCT unit_key FROM military_units")
    keys = [r[0] for r in cur.fetchall()]
    unknown = [k for k in keys if k not in TRAIN_SECONDS_BY_UNIT]
    if not unknown:
        log("  ✓ همهٔ کلیدِ نیروها معتبرند.")
        return
    for bad in unknown:
        good = UNIT_KEY_ALIASES.get(bad)
        if not good:
            log("  ⚠ کلیدِ ناشناخته و بدونِ معادل: %r (دست‌نخورده ماند)" % bad)
            continue
        log("  → کلیدِ %r → %r" % (bad, good))
        if not apply_changes:
            continue
        # اگر ردیفِ درست از قبل وجود دارد، ادغام کن؛ وگرنه تغییرِ نام.
        cur.execute("SELECT owner_id, count, upgrade_level FROM military_units WHERE unit_key=?", (bad,))
        for owner_id, cnt, lvl in cur.fetchall():
            cur.execute(
                "SELECT id, count, upgrade_level FROM military_units WHERE owner_id=? AND unit_key=?",
                (owner_id, good),
            )
            row = cur.fetchone()
            if row:
                cur.execute(
                    "UPDATE military_units SET count=?, upgrade_level=? WHERE id=?",
                    (int(row[1] or 0) + int(cnt or 0), max(int(row[2] or 1), int(lvl or 1)), row[0]),
                )
                cur.execute("DELETE FROM military_units WHERE owner_id=? AND unit_key=?", (owner_id, bad))
            else:
                cur.execute(
                    "UPDATE military_units SET unit_key=? WHERE owner_id=? AND unit_key=?",
                    (good, owner_id, bad),
                )
        for tbl in ("military_training_queue", "military_upgrade_queue"):
            if table_exists(cur, tbl):
                cur.execute("UPDATE %s SET unit_key=? WHERE unit_key=?" % tbl, (good, bad))


def repair_levels(cur, apply_changes, log):
    """لولِ ۰ یا NULL یعنی ردپایِ ریستِ قدیمی — حداقل باید ۱ باشد."""
    if not table_exists(cur, "military_units"):
        return
    cur.execute(
        "SELECT owner_id, COUNT(*) FROM military_units "
        "WHERE upgrade_level IS NULL OR upgrade_level < 1 GROUP BY owner_id"
    )
    rows = cur.fetchall()
    if not rows:
        log("  ✓ هیچ لولِ نامعتبری وجود ندارد.")
        return
    total = 0
    for owner_id, n in rows:
        log("  → کاربر %s : %d نوع نیرو با لولِ نامعتبر → لول ۱" % (owner_id, n))
        total += n
    if apply_changes:
        cur.execute(
            "UPDATE military_units SET upgrade_level = 1 "
            "WHERE upgrade_level IS NULL OR upgrade_level < 1"
        )
    log("  مجموع: %d ردیف" % total)


def repair_training_queue(cur, apply_changes, log, allow_increase=False):
    if not table_exists(cur, "military_training_queue"):
        return
    now = utcnow()
    cur.execute("SELECT id, owner_id, unit_key, qty, started_at, ready_at FROM military_training_queue")
    rows = cur.fetchall()
    if not rows:
        log("  ✓ صفِ پرورش خالی است.")
        return
    fixed = 0
    for rid, owner_id, unit_key, qty, started_at, ready_at in rows:
        qty = max(1, int(qty or 1))
        started = parse_dt(started_at)
        ready = parse_dt(ready_at)
        # صفِ غیرفعال (پارک‌شده در آیندهٔ دور) را دست نمی‌زنیم
        if started and started > now + timedelta(days=365):
            continue
        if started is None:
            started = now
        want = train_total_seconds(unit_key, qty)
        new_ready = started + timedelta(seconds=want)
        have = (ready - started).total_seconds() if ready else None
        if have is not None and abs(have - want) <= 60:
            continue
        # پیش‌فرض: هیچ‌کس بدتر از قبل نمی‌شود — فقط کوتاه می‌کنیم.
        if have is not None and want > have and not allow_increase:
            continue
        log(
            "  → #%s کاربر %s | %s ×%d : %s → %s"
            % (rid, owner_id, unit_key, qty, fmt(have or 0), fmt(want))
        )
        fixed += 1
        if apply_changes:
            cur.execute(
                "UPDATE military_training_queue SET started_at=?, ready_at=? WHERE id=?",
                (started.strftime("%Y-%m-%d %H:%M:%S"), new_ready.strftime("%Y-%m-%d %H:%M:%S"), rid),
            )
    log("  مجموع: %d ردیفِ صف بازمحاسبه شد." % fixed)


def repair_upgrade_queue(cur, apply_changes, log):
    if not table_exists(cur, "military_upgrade_queue"):
        return
    now = utcnow()
    cur.execute("SELECT id, owner_id, unit_key, target_level, started_at, ready_at FROM military_upgrade_queue")
    rows = cur.fetchall()
    if not rows:
        log("  ✓ صفِ ارتقا خالی است.")
        return
    fixed = 0
    for rid, owner_id, unit_key, target_level, started_at, ready_at in rows:
        started = parse_dt(started_at) or now
        ready = parse_dt(ready_at)
        cur.execute(
            "SELECT count FROM military_units WHERE owner_id=? AND unit_key=?", (owner_id, unit_key)
        )
        row = cur.fetchone()
        qty = max(1, int((row[0] if row else 1) or 1))
        want = upgrade_total_seconds(qty, target_level)
        have = (ready - started).total_seconds() if ready else None
        if have is not None and have <= want + 60:
            continue
        new_ready = started + timedelta(seconds=want)
        log(
            "  → #%s کاربر %s | %s → لول %s : %s → %s"
            % (rid, owner_id, unit_key, target_level, fmt(have or 0), fmt(want))
        )
        fixed += 1
        if apply_changes:
            cur.execute(
                "UPDATE military_upgrade_queue SET ready_at=? WHERE id=?",
                (new_ready.strftime("%Y-%m-%d %H:%M:%S"), rid),
            )
    log("  مجموع: %d ردیفِ ارتقا نصف شد." % fixed)


def repair_salary_anchor(cur, apply_changes, log):
    if not table_exists(cur, "owned_professionals"):
        return
    now = utcnow().strftime("%Y-%m-%d %H:%M:%S")
    cur.execute("SELECT COUNT(*) FROM owned_professionals WHERE created_at IS NULL")
    missing_created = cur.fetchone()[0]
    cur.execute(
        "SELECT COUNT(*) FROM owned_professionals WHERE last_paid IS NULL AND created_at IS NULL"
    )
    broken = cur.fetchone()[0]
    log("  created_at خالی: %d  |  بدونِ هیچ مبدأِ حقوق: %d" % (missing_created, broken))
    if broken == 0 and missing_created == 0:
        log("  ✓ مبدأِ حقوقِ همهٔ حرفه‌ای‌ها سالم است.")
        return
    if apply_changes:
        cur.execute("UPDATE owned_professionals SET created_at=? WHERE created_at IS NULL", (now,))
        cur.execute(
            "UPDATE owned_professionals SET last_paid=created_at "
            "WHERE last_paid IS NULL AND created_at IS NOT NULL"
        )
    log("  → مبدأِ حقوق پر شد (دکمهٔ پرداختِ حقوق دوباره کار می‌کند).")


def set_levels(cur, apply_changes, log, owner_id, unit_key, level):
    level = max(1, int(level))
    if unit_key:
        cur.execute(
            "SELECT COUNT(*) FROM military_units WHERE owner_id=? AND unit_key=?",
            (owner_id, unit_key),
        )
        if cur.fetchone()[0] == 0:
            log("  ⚠ کاربر %s هیچ ردیفی از %r ندارد." % (owner_id, unit_key))
            return
        log("  → کاربر %s | %s → لول %d" % (owner_id, unit_key, level))
        if apply_changes:
            cur.execute(
                "UPDATE military_units SET upgrade_level=? WHERE owner_id=? AND unit_key=?",
                (level, owner_id, unit_key),
            )
    else:
        cur.execute("SELECT COUNT(*) FROM military_units WHERE owner_id=?", (owner_id,))
        n = cur.fetchone()[0]
        log("  → کاربر %s | همهٔ %d نوع نیرو → لول %d" % (owner_id, n, level))
        if apply_changes:
            cur.execute(
                "UPDATE military_units SET upgrade_level=? WHERE owner_id=?", (level, owner_id)
            )


def report(cur, log):
    log("")
    log("📊 وضعیتِ فعلی پس از بررسی")
    log("-" * 62)
    if table_exists(cur, "military_units"):
        cur.execute(
            "SELECT owner_id, COUNT(*), SUM(count), MIN(upgrade_level), MAX(upgrade_level) "
            "FROM military_units GROUP BY owner_id ORDER BY SUM(count) DESC"
        )
        log("%-16s %6s %10s %8s %8s" % ("user", "types", "units", "minLvl", "maxLvl"))
        for owner_id, types, units, mn, mx in cur.fetchall():
            log("%-16s %6s %10s %8s %8s" % (owner_id, types, units or 0, mn, mx))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=None)
    ap.add_argument("--apply", action="store_true", help="اعمالِ تغییرات")
    ap.add_argument("--dry-run", action="store_true", help="فقط گزارش")
    ap.add_argument("--set-all-levels", nargs=2, metavar=("UID", "LEVEL"))
    ap.add_argument("--set-level", nargs=3, metavar=("UID", "UNIT", "LEVEL"))
    ap.add_argument(
        "--allow-increase",
        action="store_true",
        help="اجازه بده زمانِ صفِ بعضی ردیف‌ها بیشتر هم بشود (پیش‌فرض: فقط کوتاه‌تر)",
    )
    args = ap.parse_args()

    apply_changes = bool(args.apply) and not args.dry_run
    db_path = find_db(args.db)

    def log(msg=""):
        print(msg)

    log("🗃  دیتابیس: %s" % db_path)
    log("⚙️  حالت: %s" % ("اعمالِ تغییرات" if apply_changes else "DRY-RUN (بدون تغییر)"))
    log("=" * 62)

    if apply_changes:
        backup = "%s.bak-%s" % (db_path, datetime.now().strftime("%Y%m%d-%H%M%S"))
        shutil.copy2(db_path, backup)
        log("💾 بک‌آپ ساخته شد: %s" % backup)
        log("")

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    try:
        if args.set_all_levels:
            log("🏷  بازگرداندنِ دستیِ لول‌ها")
            set_levels(cur, apply_changes, log, int(args.set_all_levels[0]), None, int(args.set_all_levels[1]))
        elif args.set_level:
            log("🏷  بازگرداندنِ دستیِ لول")
            set_levels(cur, apply_changes, log, int(args.set_level[0]), args.set_level[1], int(args.set_level[2]))
        else:
            log("1️⃣  کلیدِ نیروهای ناشناخته")
            repair_unit_keys(cur, apply_changes, log)
            log("")
            log("2️⃣  لولِ نامعتبرِ نیروها (ردپایِ ریستِ قدیمی)")
            repair_levels(cur, apply_changes, log)
            log("")
            log("3️⃣  بازمحاسبهٔ صفِ پرورش با نرخِ نصف‌شده")
            repair_training_queue(cur, apply_changes, log, allow_increase=args.allow_increase)
            log("")
            log("4️⃣  نصف‌کردنِ صفِ ارتقا")
            repair_upgrade_queue(cur, apply_changes, log)
            log("")
            log("5️⃣  مبدأِ پرداختِ حقوق")
            repair_salary_anchor(cur, apply_changes, log)
            report(cur, log)

        if apply_changes:
            conn.commit()
            log("")
            log("✅ تغییرات ذخیره شد.")
        else:
            conn.rollback()
            log("")
            log("ℹ️  چیزی ذخیره نشد. برای اعمال، دوباره با --apply اجرا کن.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
