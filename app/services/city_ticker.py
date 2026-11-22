"""پردازش روزانه شهرها؛ قابل فراخوانی از polling و cron."""
import asyncio
import logging
from datetime import datetime
from sqlalchemy import select
from app.database.engine import async_session
from app.models.mafia_city import MafiaCity
from app.services.mafia_city_service import tick
log = logging.getLogger(__name__)
CITY_TICK_SECONDS = 3600


async def city_tick_once():
    try:
        async with async_session() as session:
            cities = (await session.execute(select(MafiaCity))).scalars().all()
            for city in cities:
                # v1.7.6.5 — tick(session, city) دو ورودی دارد. قبلاً سه تا پاس می‌شد
                # و TypeError در except پایین بلعیده می‌شد — یعنی رشدِ جمعیت
                # هرگز خودکار اجرا نمی‌شد.
                await tick(session, city)
            await session.commit()
    except Exception as exc:
        log.exception("city_tick_once failed: %s", exc)


async def city_ticker_loop():
    while True:
        await asyncio.sleep(CITY_TICK_SECONDS)
        await city_tick_once()


# ---------------------------------------------------------------------------
# v1.7.6.5 — پیامِ مردم در طولِ سال، فقط اگر شهردار استخدام شده باشد.
# فاصلهٔ گزارش‌ها به ردهٔ شهردار بستگی دارد (۱ تا ۴ بار در هر سالِ بازی).
# ---------------------------------------------------------------------------
async def maybe_mayor_demands(bot) -> int:
    from app.data import city_mayor as MY
    from app.data import mafia_city as C
    from app.models.group_membership import GroupMembership
    from app.models.player import Player
    from app.services import mafia_city_service as CS

    sent = 0
    now = datetime.utcnow()
    async with async_session() as session:
        cities = list((await session.execute(select(MafiaCity))).scalars().all())
        for city in cities:
            uid = int(city.tg_user_id)
            key = getattr(city, "mayor_key", None)
            if not key:
                # شهرداری استخدام نشده — صدای مردم به بازیکن نمی‌رسد.
                continue
            every = MY.report_interval_hours(key, C.GAME_YEAR_REAL_DAYS)
            if every <= 0:
                continue
            last = (
                getattr(city, "last_mayor_msg_at", None)
                or getattr(city, "mayor_hired_at", None)
            )
            if last is not None:
                try:
                    if (now - last).total_seconds() < every * 3600.0:
                        continue
                except Exception:
                    pass
            try:
                counts = await CS._buildings(session, city.id)
            except Exception:
                counts = {}
            try:
                body = CS.mayor_report_body(city, counts)
            except Exception:
                log.exception("mayor_report_body failed for city %s", city.id)
                continue
            try:
                await bot.send_message(uid, body)
                sent += 1
            except Exception:
                pass
            try:
                pl = (
                    await session.execute(select(Player).where(Player.tg_user_id == uid))
                ).scalar_one_or_none()
                who = (getattr(pl, "name", None) if pl else None) or str(uid)
                g = (
                    await session.execute(
                        select(GroupMembership).where(GroupMembership.tg_user_id == uid)
                    )
                ).scalars().first()
                if g is not None:
                    tag = '<a href="tg://user?id=%d">%s</a>' % (uid, who)
                    await bot.send_message(int(g.chat_id), body + "\n\n👤 " + tag)
                    sent += 1
            except Exception:
                pass
            city.last_mayor_msg_at = now
        try:
            await session.commit()
        except Exception:
            pass
    return sent
