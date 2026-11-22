# -*- coding: utf-8 -*-
"""پلِ همگام‌سازیِ آمارِ واقعی → PlayerStats (مرحله ۲۰).

هدف: بازطراحیِ شرطِ القاب بر اساسِ منطقِ واقعی — برخی شمارنده‌های PlayerStats
از جدول‌هایِ واقعیِ بازی (ارتش، جنگ، شهر، کشور) محاسبه و همگام می‌شوند
تا ارزیابیِ القاب با داده‌ی درست انجام شود.

همه‌ی منابع دفاعی (try/except) خوانده می‌شوند تا نبودِ هر مدل/سرویس باعثِ خطا نشود.
"""
from __future__ import annotations


async def _safe_army_power(session, uid: int) -> int | None:
    try:
        from app.services import military_service
        val = await military_service.army_power(session, uid)
        return int(val)
    except Exception:
        return None


async def sync_player_stats(session, uid: int) -> None:
    """شمارنده‌هایِ مشتق‌پذیر را روی PlayerStats همگام می‌کند (بدونِ commit)."""
    try:
        from app.services.titles import _get_or_create_stats
    except Exception:
        return
    try:
        st = await _get_or_create_stats(session, uid)
    except Exception:
        return

    # ⚔️ قدرتِ نظامی — تنها شمارنده‌ی القابی که باید زنده محاسبه شود
    if hasattr(st, "military_power"):
        power = await _safe_army_power(session, uid)
        if power is not None:
            st.military_power = power

    # 🆕 v1.7.8.19 — active_days هم زنده محاسبه شود تا baseline هفتگیِ القابِ
    # تک (مثل کرونوس/جاودانه) درست کار کند.
    try:
        if hasattr(st, "active_days"):
            from datetime import datetime as _dt
            from app.models.player import Player as _Pl
            _created = await session.scalar(
                __import__("sqlalchemy").select(_Pl.created_at).where(_Pl.tg_user_id == uid)
            )
            if _created is not None:
                st.active_days = max(0, (_dt.utcnow() - _created).days)
    except Exception:
        pass

    try:
        await session.flush()
    except Exception:
        pass


async def sync_and_evaluate(session, uid: int) -> list:
    """اول آمار را همگام، سپس القاب را ارزیابی می‌کند؛ فهرستِ القابِ جدید."""
    await sync_player_stats(session, uid)
    try:
        from app.services.titles import evaluate_titles
        return await evaluate_titles(session, uid)
    except Exception:
        return []
