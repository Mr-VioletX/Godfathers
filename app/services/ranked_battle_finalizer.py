# -*- coding: utf-8 -*-
"""🆕 v1.7.6.4 — بستنِ خودکارِ نبردهای رنکینگ + خبردادن به دو طرف.

باگِ قدیم (گزارش‌شده):
    نبردهای رنکینگ در پس‌زمینه بسته می‌شدند، ردیفِ مجروحانِ
    بیمارستان هم ساخته می‌شد، اما هیچ پیامی به هیچ‌کدام از دو طرف
    نمی‌رفت. پس کاربر نمی‌فهمید نبردش تمام شده، نمی‌دانست برده یا
    باخته، و مهم‌تر از همه خبر نداشت که مهلتِ ۲۴ ساعتهٔ درمانِ
    نیروهایش شروع شده — تا می‌فهمید، نیروها مرده بودند.

حالا:
    پس از بستنِ هر نبرد، گزارشِ پایانِ جنگ (شاملِ بخشِ بیمارستان و
    هزینهٔ درمان) به خودِ مهاجم و مدافع پیام خصوصی می‌شود.

نکتهٔ سازگاری: پارامترِ bot اختیاری است، پس فراخوانی‌های قدیمی که آن را
نمی‌دهند (مثلاً پنلِ ادمین) دقیقاً مثلِ قبل کار می‌کنند — فقط پیام نمی‌فرستند.
"""
import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.live_battle import LiveBattle
from app.services import battle_live

log = logging.getLogger(__name__)

_HEADER = "🏁 <b>نبردِ رنکینگ تمام شد</b>\n\n"


async def _dm(bot, uid, text):
    """ارسالِ ایمنِ پیام — هر خطایی بلعیده می‌شود."""
    if bot is None or not uid or not text:
        return False
    try:
        await bot.send_message(int(uid), _HEADER + str(text))
        return True
    except Exception:
        return False


async def finalize_finished_ranked_battles(
    session: AsyncSession,
    *,
    now: datetime | None = None,
    limit: int = 50,
    bot=None,
) -> int:
    """نبردهای رنکینگِ تمام‌شده را می‌بندد.

    اگر bot داده شود، گزارشِ پایانِ جنگ به هر دو طرف پیام می‌شود.
    خروجی: تعدادِ نبردِ بسته‌شده.
    """
    now = now or datetime.utcnow()
    rows = (
        await session.execute(
            select(LiveBattle)
            .where(
                LiveBattle.mode == "ranked",
                LiveBattle.finalized == 0,
                LiveBattle.ends_at <= now,
            )
            .order_by(LiveBattle.id)
            .limit(limit)
        )
    ).scalars().all()

    n = 0
    for row in rows:
        # شناسه‌ها را پیش از finalize بردار، چون finalize خودش commit می‌کند.
        att_id = int(getattr(row, "attacker_id", 0) or 0)
        def_id = int(getattr(row, "defender_id", 0) or 0)
        try:
            result = await battle_live.finalize(session, row, now)
        except Exception as exc:
            log.exception("ranked finalize failed for battle %s: %s", getattr(row, "id", "?"), exc)
            continue
        n += 1

        # 🆕 v1.7.6.4 — خبردادن به دو طرف (شاملِ مجروحان و مهلتِ درمان)
        if bot is None or not isinstance(result, dict):
            continue
        if result.get("already"):
            continue
        await _dm(bot, att_id, result.get("attacker"))
        await _dm(bot, def_id, result.get("defender"))

    return n
