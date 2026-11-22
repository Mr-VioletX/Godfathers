# -*- coding: utf-8 -*-
"""🆕 بچ ۴ — مهاجرتِ یک‌باره‌ی رفاندِ سیستمِ شهر/کشورِ قدیمی.

وقتی سیستمِ قدیمیِ شهر/کشور/جنگِ بین‌الملل حذف شد، بازیکنانی که
قبلاً برای خرید/ساختِ شهر و سازه‌های کشور پول داده بودند باید پولِ
سرمایه‌گذاری‌شان برگردد (تصمیمِ کاربر: رفاندِ نقدی).

این ماژول کاملاً خودبسنده است (جدولِ قدیمی را با SQLِ خام می‌خواند و
هزینه‌های قدیمی در خودِ فایل پخته شده) تا پس از حذفِ فایل‌هایِ
قدیمی هم روی هاست درست کار کند. فقط یک‌بار اجرا می‌شود (مارکر).
"""
from __future__ import annotations

import logging

from sqlalchemy import text

log = logging.getLogger(__name__)

# --- هزینه‌ی ساختِ ساختمان‌های شهرِ قدیمی (پخته‌شده از data/cities.pyِ قدیم) ---
_OLD_CITY_BUILD = {
    "school": 200_000, "university": 600_000, "hospital": 400_000, "park": 150_000,
    "police": 300_000, "fire": 250_000, "power": 500_000, "water": 450_000,
    "gas": 450_000, "fuel": 550_000, "road": 350_000, "housing": 600_000,
    "cityhall": 750_000, "culture": 300_000,
    "port": 800_000, "shipyard": 950_000, "fishmarket": 350_000, "lighthouse": 450_000,
    "promenade": 325_000, "mine": 850_000, "quarry": 550_000, "hydro": 750_000,
    "cablecar": 475_000, "skiresort": 650_000, "farm": 500_000, "silo": 400_000,
    "railhub": 800_000, "stadium": 700_000, "windfarm": 650_000, "oilwell": 1_000_000,
    "solar": 700_000, "desal": 750_000, "casino": 900_000, "caravan": 450_000,
    "resort": 1_000_000, "marina": 600_000, "airstrip": 950_000, "divecenter": 425_000,
    "tidalplant": 800_000,
}

# --- هزینه‌ی ساختِ سازه‌های کشورِ قدیمی (پخته‌شده از data/country.pyِ قدیم) ---
_OLD_COUNTRY_BUILD = {
    "iron_mine": 9_000_000, "coal_mine": 12_000_000, "gold_mine": 25_000_000,
    "oil_field": 30_000_000, "gem_mine": 40_000_000, "trade_port": 15_000_000,
    "fish_port": 8_000_000, "oil_terminal": 28_000_000, "naval_base": 32_000_000,
    "free_zone": 36_000_000, "parliament": 20_000_000, "academy": 24_000_000,
    "central_bank": 45_000_000, "army_hq": 38_000_000, "spy_agency": 34_000_000,
    "monument": 18_000_000,
}


def _city_building_investment(btype: str, level: int) -> int:
    """مجموعِ ساخت + ارتقاها (فرمولِ قدیم: upgrade = build*0.8*level)."""
    base = int(_OLD_CITY_BUILD.get(btype, 0))
    total = base
    for i in range(1, max(1, int(level or 1))):
        total += int(base * 0.8 * i)
    return total


def _country_building_investment(bkey: str, level: int) -> int:
    """مجموعِ ساخت + ارتقاها (فرمولِ قدیم: upgrade = build*(0.55+0.15*level))."""
    base = int(_OLD_COUNTRY_BUILD.get(bkey, 0))
    total = base
    for i in range(1, max(1, int(level or 1))):
        total += int(base * (0.55 + 0.15 * i))
    return total


async def _table_exists(session, name: str) -> bool:
    try:
        row = await session.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name=:t"),
            {"t": name},
        )
        return row.first() is not None
    except Exception:
        # دیتابیسِ غیرِ sqlite — تلاش می‌کنیم و در صورتِ خطا رد می‌شویم
        try:
            await session.execute(text(f"SELECT 1 FROM {name} LIMIT 1"))
            return True
        except Exception:
            return False


async def _already_done(session) -> bool:
    await session.execute(text(
        "CREATE TABLE IF NOT EXISTS mafia_refund_log (id INTEGER PRIMARY KEY, done_at TEXT)"
    ))
    row = await session.execute(text("SELECT id FROM mafia_refund_log LIMIT 1"))
    return row.first() is not None


async def _mark_done(session, total_refunded: int, players: int) -> None:
    await session.execute(text(
        "INSERT INTO mafia_refund_log (done_at) VALUES (datetime('now'))"
    ))


async def refund_and_cleanup_old_city_system(session) -> dict:
    """رفاندِ نقدیِ سرمایه‌ی شهر/کشورِ قدیمی + پاکسازیِ ردیف‌ها. یک‌باره."""
    try:
        if await _already_done(session):
            return {"status": "skipped", "refunded": 0, "players": 0}
    except Exception as e:  # pragma: no cover
        log.warning("refund guard failed: %s", e)
        return {"status": "error", "refunded": 0, "players": 0}

    refunds: dict[int, int] = {}

    # ---- شهرهای قدیمی (خرید + ساختمان‌ها) ----
    if await _table_exists(session, "cities"):
        rows = await session.execute(text(
            "SELECT id, tg_user_id, purchase_price FROM cities"
        ))
        city_owner: dict[int, int] = {}
        for cid, uid, price in rows.all():
            city_owner[int(cid)] = int(uid)
            refunds[int(uid)] = refunds.get(int(uid), 0) + int(price or 0)
        if city_owner and await _table_exists(session, "city_buildings"):
            brows = await session.execute(text(
                "SELECT city_id, btype, level FROM city_buildings"
            ))
            for city_id, btype, level in brows.all():
                uid = city_owner.get(int(city_id))
                if uid is None:
                    continue
                refunds[uid] = refunds.get(uid, 0) + _city_building_investment(str(btype), int(level or 1))

    # ---- سازه‌های کشورِ قدیمی ----
    if await _table_exists(session, "country_buildings"):
        crows = await session.execute(text(
            "SELECT owner_id, bkey, level FROM country_buildings"
        ))
        for owner_id, bkey, level in crows.all():
            uid = int(owner_id)
            refunds[uid] = refunds.get(uid, 0) + _country_building_investment(str(bkey), int(level or 1))

    # ---- واریزِ رفاند به موجودیِ بازیکنان ----
    total = 0
    players = 0
    for uid, amount in refunds.items():
        if amount <= 0:
            continue
        res = await session.execute(
            text("UPDATE players SET cash = COALESCE(cash,0) + :amt WHERE tg_user_id = :uid"),
            {"amt": int(amount), "uid": int(uid)},
        )
        if (res.rowcount or 0) > 0:
            total += int(amount)
            players += 1

    # ---- پاکسازیِ جدول‌های قدیمی (دیگر استفاده نمی‌شوند) ----
    for tbl in ("city_buildings", "cities", "city_action_logs",
                "country_buildings", "captured_cities"):
        if await _table_exists(session, tbl):
            try:
                await session.execute(text(f"DELETE FROM {tbl}"))
            except Exception as e:  # pragma: no cover
                log.warning("cleanup %s failed: %s", tbl, e)

    await _mark_done(session, total, players)
    await session.commit()
    log.info("City refund migration done: %s$ to %s players", total, players)
    return {"status": "done", "refunded": total, "players": players}
