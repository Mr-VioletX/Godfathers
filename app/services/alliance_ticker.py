# -*- coding: utf-8 -*-
"""v1.7.9.1 — تیکرِ اتحادیه.

هر ۱۵ دقیقه (Polling/VPS) یا از cron_ticks.py (هاستِ اشتراکی):
  ۱) نبردهای زنده‌ی تمام‌شده‌ی اتحادیه نهایی می‌شوند (کسی لازم نیست دکمه بزند)
  ۲) تولیدِ خودکارِ روزانه‌ی سربازخانه (با نگهبانِ تاریخ — فقط یک‌بار در روز برای هر اتحادیه)
  ۳) کسرِ اشتراکِ عضویت طبقِ تنظیمِ رئیس (sub_pct٪ هر sub_days روز) + اطلاع به عضو
"""
from __future__ import annotations

import asyncio
import logging

from sqlalchemy import select

from app.database.engine import async_session

log = logging.getLogger(__name__)

TICK_SECONDS = 15 * 60


async def alliance_tick_once(bot) -> None:
    from app.models.alliance import Alliance
    from app.services import alliance_battle as AB
    from app.services import alliance_military_service as AMS

    async with async_session() as session:
        try:
            await AB.sweep_finalize_finished(session)
        except Exception as e:
            log.warning("alliance battle sweep failed: %s", e)
        alliances = list((await session.execute(select(Alliance))).scalars().all())
        for al in alliances:
            # تولیدِ خودکار (روزانه، با نگهبانِ داخلی)
            try:
                res = await AMS.auto_produce_alliance(session, al)
            except Exception as e:
                log.warning("auto produce failed for alliance %s: %s", al.id, e)
                res = {}
            if res.get("built") and bot is not None:
                try:
                    lines = "\n".join("• " + x for x in (res.get("lines") or []))
                    await bot.send_message(
                        int(al.leader_id),
                        f"🤖 <b>تولیدِ خودکارِ ارتشِ «{al.name}»</b>\n{lines}\n"
                        f"💰 هزینه: {int(res.get('spent') or 0):,}$ از صندوق",
                    )
                except Exception:
                    pass
            # کسرِ اشتراکِ عضویت (هر sub_days روز، با نگهبانِ داخلی)
            try:
                fee = await AMS.charge_membership_fee(session, al)
            except Exception as e:
                log.warning("membership fee failed for alliance %s: %s", al.id, e)
                fee = {}
            if fee.get("charged") and bot is not None:
                for uid, amount in fee.get("notify") or []:
                    try:
                        await bot.send_message(
                            int(uid),
                            f"💳 هزینه‌ی اشتراکِ اتحادیه‌ی «{al.name}»: مبلغِ <b>{amount:,}$</b> "
                            f"بابتِ عضویت ({al.sub_pct}٪ هر {al.sub_days} روز) از حسابت کسر شد و به صندوقِ اتحادیه رفت.",
                        )
                    except Exception:
                        continue
                try:
                    await bot.send_message(
                        int(al.leader_id),
                        f"💰 اشتراکِ عضویتِ «{al.name}»: مجموعاً <b>{int(fee.get('charged') or 0):,}$</b> "
                        f"از {int(fee.get('members') or 0)} عضو به صندوق واریز شد.",
                    )
                except Exception:
                    pass
        try:
            await session.commit()
        except Exception:
            pass


async def alliance_tick_loop(bot) -> None:
    """حلقه‌ی Polling/VPS — روی هاستِ اشتراکی به‌جای آن cron_ticks.py صدا می‌زند."""
    while True:
        try:
            await alliance_tick_once(bot)
        except Exception as e:
            log.exception("alliance_tick_loop error: %s", e)
        await asyncio.sleep(TICK_SECONDS)
