# -*- coding: utf-8 -*-
"""🆕 v1.7.2 — بکاپ دیتابیس SQLite برای ادمین."""
from __future__ import annotations

import logging
import shutil
import tempfile
import time
from datetime import datetime
from pathlib import Path

from aiogram.types import FSInputFile

from app.database.engine import async_session
from app.services import admin_service as adm

log = logging.getLogger(__name__)

_BASE = Path(__file__).resolve().parents[2]


def resolve_db_path() -> Path:
    """مسیر فایل .db را از database_url یا پیش‌فرض پیدا می‌کند."""
    try:
        from app.config import settings
        url = str(getattr(settings, "database_url", "") or "")
    except Exception:
        url = ""
    if "sqlite" in url and "///" in url:
        raw = url.split("///", 1)[1]
        p = Path(raw)
        if not p.is_absolute():
            p = _BASE / p
        return p
    for name in ("godfather.db", "bot.db", "database.db"):
        cand = _BASE / name
        if cand.exists():
            return cand
    return _BASE / "godfather.db"


def make_backup_copy() -> tuple[Path, str]:
    """کپی امن از دیتابیس با نام زمان‌دار."""
    src = resolve_db_path()
    if not src.exists():
        raise FileNotFoundError(f"DB not found: {src}")
    stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    fname = f"godfather_backup_{stamp}.db"
    tmp_dir = Path(tempfile.mkdtemp(prefix="gf_backup_"))
    dst = tmp_dir / fname
    try:
        import sqlite3
        with sqlite3.connect(str(src)) as con:
            with sqlite3.connect(str(dst)) as bck:
                con.backup(bck)
    except Exception:
        shutil.copy2(src, dst)
    return dst, fname


async def send_backup(bot, *, to_chat_ids: list[int], caption: str | None = None) -> tuple[bool, str]:
    """بکاپ می‌گیرد و به لیست چت‌ها می‌فرستد."""
    try:
        path, fname = make_backup_copy()
    except Exception as e:
        return False, f"⚠ ساخت بکاپ ناموفق: {e}"
    cap = caption or f"📦 بکاپ دیتابیس — {fname}"
    ok_any = False
    errors = []
    try:
        for chat_id in to_chat_ids:
            if not chat_id:
                continue
            try:
                await bot.send_document(
                    int(chat_id),
                    FSInputFile(str(path), filename=fname),
                    caption=cap,
                )
                ok_any = True
            except Exception as e:
                errors.append(f"{chat_id}: {e}")
                log.warning("backup send failed to %s: %s", chat_id, e)
    finally:
        try:
            shutil.rmtree(path.parent, ignore_errors=True)
        except Exception:
            pass
    if ok_any:
        async with async_session() as session:
            await adm.mark_backup_done(session, time.time(), commit=True)
        msg = "✅ بکاپ ارسال شد."
        if errors:
            msg += "\n⚠ برخی مقصدها خطا دادند: " + "; ".join(errors[:3])
        return True, msg
    return False, "⚠ ارسال بکاپ ناموفق بود: " + ("; ".join(errors) if errors else "مقصدی نبود")


async def maybe_auto_backup(bot) -> None:
    """اگر فاصله زمانی سررسید شده باشد، بکاپ خودکار به کانال می‌فرستد."""
    async with async_session() as session:
        cfg = await adm.get_backup_settings(session)
    hours = int(cfg.get("interval_hours") or 0)
    ch = cfg.get("channel_id")
    if hours <= 0 or not ch:
        return
    last = float(cfg.get("last_ts") or 0)
    now = time.time()
    if last and (now - last) < hours * 3600:
        return
    ok, msg = await send_backup(
        bot,
        to_chat_ids=[int(ch)],
        caption=(
            f"🗂️ بکاپ خودکار دیتابیس (هر {hours} ساعت)\n"
            f"{datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"
        ),
    )
    if ok:
        log.info("auto backup ok: %s", msg)
    else:
        log.warning("auto backup failed: %s", msg)
