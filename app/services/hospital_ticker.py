# -*- coding: utf-8 -*-
"""🆕 v1.7.6.3 — تیکرِ بیمارستان ـ 🆕 v1.7.6.4 — صفِ درمان.

دو کار انجام می‌دهد:

  ۱) ردیف‌هایی که مهلتِ ۲۴ ساعتهٔ پرداختشان تمام شده را «dead»
     می‌کند و یک بار به صاحبش خبر می‌دهد که نیروهایش مردند.

  ۲) 🆕 v1.7.6.4 — ردیف‌هایی که زمانِ درمانشان (۲ تا ۸ ساعت) تمام
     شده را «healed» می‌کند، نیروها را به ارتش برمی‌گرداند و خبر می‌دهد.

⚠️ روی هاستِ اشتراکی (passenger/webhook) این لوپ همیشه زنده نیست؛ به همین
دلیل hospital_service.list_wards هنگامِ بازکردنِ بیمارستان هم هر دو
جاروب را انجام می‌دهد. پس حتی اگر تیکر اجرا نشود، هم قانونِ ۲۴ ساعت
و هم پایانِ درمان دقیقاً اعمال می‌شود — فقط پیامِ اطلاع‌رسانی دیرتر می‌رسد.
"""
import asyncio
import logging
from datetime import datetime

from sqlalchemy import select

from app.database.engine import async_session
from app.models.hospital import HospitalWard
from app.services import hospital_service as HS

log = logging.getLogger(__name__)

HOSPITAL_TICK_SECONDS = 600  # هر ۱۰ دقیقه


async def hospital_tick_once(bot=None) -> int:
    """مهلت‌گذشته‌ها را می‌کِشد و درمان‌شده‌ها را تحویل می‌دهد.

    خروجی: تعدادِ پیامِ فرستاده‌شده.
    """
    sent = 0
    try:
        async with async_session() as session:
            now = datetime.utcnow()

            # ---------- ۱) مهلتِ پرداخت تمام شد → مرگ ----------
            await HS.sweep_expired(session, now=now)
            dead_rows = (
                await session.execute(
                    select(HospitalWard)
                    .where(
                        HospitalWard.status == "dead",
                        HospitalWard.notified_dead == 0,
                    )
                    .order_by(HospitalWard.id)
                    .limit(200)
                )
            ).scalars().all()
            for ward in dead_rows:
                ward.notified_dead = 1
                if bot is None:
                    continue
                try:
                    await bot.send_message(int(ward.owner_id), HS.dead_notice(ward))
                    sent += 1
                except Exception:
                    pass

            # ---------- ۲) 🆕 زمانِ درمان تمام شد → تحویلِ نیرو ----------
            await HS.complete_healing(session, now=now)
            healed_rows = (
                await session.execute(
                    select(HospitalWard)
                    .where(
                        HospitalWard.status == "healed",
                        HospitalWard.notified_healed == 0,
                    )
                    .order_by(HospitalWard.id)
                    .limit(200)
                )
            ).scalars().all()
            for ward in healed_rows:
                ward.notified_healed = 1
                if bot is None:
                    continue
                try:
                    await bot.send_message(int(ward.owner_id), HS.healed_notice(ward))
                    sent += 1
                except Exception:
                    pass

            await session.commit()
    except Exception as exc:
        log.exception("hospital_tick_once failed: %s", exc)
    return sent


async def hospital_ticker_loop(bot=None):
    while True:
        await asyncio.sleep(HOSPITAL_TICK_SECONDS)
        await hospital_tick_once(bot)
