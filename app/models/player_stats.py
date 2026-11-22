# -*- coding: utf-8 -*-
"""مرحله ۱۵.۵ — آمارِ انباشته‌ی بازیکن (منبعِ XP و شمارنده‌های بازی).

❗️ رفعِ ایراد: قبلاً یک کلاسِ PlayerStats جدا اینجا با __tablename__ = "player_stats"
تعریف می‌شد که با کلاسِ PlayerStats در app/models/title.py (همان جدول) تقابل دارد
و باعثِ خطایِ SQLAlchemy می‌شد:
  "Table 'player_stats' is already defined for this MetaData instance."
اینجا فقط همان کلاسِ کانونی (title.py) را دوباره ایمپورت می‌کنیم تا همه‌جا
(مثلاً app/handlers/theft.py) بدونِ تعویضِ کد همان کلاس را بگیرند. فیلدهایِ دزدی/زندان
(xp_total, thefts_done, thefts_caught, times_jailed, bribes_paid, total_loot, created_at) الان
درونِ همان کلاسِ PlayerStats در title.py قرار دارند.
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.title import PlayerStats

__all__ = ["PlayerStats", "get_or_create_stats"]


async def get_or_create_stats(session: AsyncSession, tg_user_id: int) -> "PlayerStats":
    """آمارِ بازیکن را برمی‌گرداند؛ اگر نبود می‌سازد (commit در جایِ فراخوانی)."""
    row = await session.scalar(
        select(PlayerStats).where(PlayerStats.tg_user_id == tg_user_id)
    )
    if row is None:
        row = PlayerStats(tg_user_id=tg_user_id)
        session.add(row)
        await session.flush()
    return row
