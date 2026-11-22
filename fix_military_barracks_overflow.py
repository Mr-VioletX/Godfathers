# -*- coding: utf-8 -*-
"""اصلاح ظرفیت سربازخانه و صف‌های گیرکرده.

کارهایی که انجام می‌دهد:
1) برای هر کاربر، اگر نیروهای فعال + صف‌های پرورش از ظرفیت سربازخانه بیشتر باشد،
   لول سربازخانه را تا حد لازم بالا می‌برد؛ بدون حذف نیرو و بدون حذف صف.
2) اگر حتی سقف فعلی تنظیمات هم کافی نباشد، مقدار تنظیم عددی
   military.barracks_max_capacity را تا مقدار لازم بالا می‌برد.
3) صف‌های پرورش را دوباره زمان‌بندی می‌کند تا صف‌های گیرکرده/متوقف‌شده راه بیفتند.
"""
import asyncio
from sqlalchemy import select

from app.database.engine import async_session, init_models
from app.data import military as M
from app.models.admin import GameNumberSetting
from app.models.military import MilitaryBarracks, MilitaryTrainingQueue, MilitaryUnit
from app.models.player import Player
from app.services import military_service

SETTING_KEY = "military.barracks_max_capacity"


def needed_level_for_capacity(needed: int, max_cap: int) -> int:
    levels = M.barracks_levels(max_cap)
    for lvl in range(1, levels + 1):
        if M.barracks_capacity(lvl, max_cap) >= needed:
            return lvl
    return levels


async def main():
    await init_models()
    changed_users = 0
    raised_global_cap = False
    async with async_session() as session:
        players = (await session.execute(select(Player.tg_user_id))).scalars().all()
        # اول مقدار سقف فعلی را بخوانیم.
        max_cap = await military_service.barracks_max_capacity(session)
        # اگر دیتای فعلی از سقف بیشتر باشد، سقف را به نزدیک‌ترین ۱۰هزار بالاتر ببریم.
        max_needed = 0
        for uid in players:
            active_total = sum(int(u.count or 0) for u in (await session.execute(
                select(MilitaryUnit).where(MilitaryUnit.owner_id == uid)
            )).scalars().all())
            queued_total = sum(int(q.qty or 0) for q in (await session.execute(
                select(MilitaryTrainingQueue).where(MilitaryTrainingQueue.owner_id == uid)
            )).scalars().all())
            max_needed = max(max_needed, active_total + queued_total)
        if max_needed > max_cap:
            new_cap = ((max_needed + 9999) // 10000) * 10000
            rec = await session.get(GameNumberSetting, SETTING_KEY)
            if rec is None:
                rec = GameNumberSetting(key=SETTING_KEY, value=str(new_cap), label="سقف ظرفیت سربازخانه")
                session.add(rec)
            else:
                rec.value = str(new_cap)
            max_cap = new_cap
            raised_global_cap = True
            await session.flush()

        for uid in players:
            active_total = sum(int(u.count or 0) for u in (await session.execute(
                select(MilitaryUnit).where(MilitaryUnit.owner_id == uid)
            )).scalars().all())
            queued_total = sum(int(q.qty or 0) for q in (await session.execute(
                select(MilitaryTrainingQueue).where(MilitaryTrainingQueue.owner_id == uid)
            )).scalars().all())
            needed = active_total + queued_total
            b = await military_service.get_barracks(session, uid)
            current_cap = M.barracks_capacity(int(b.level or 1), max_cap)
            if needed > current_cap:
                old = int(b.level or 1)
                b.level = max(old, needed_level_for_capacity(needed, max_cap))
                b.upgrading_until = None
                changed_users += 1
            # زمان‌بندی صف‌ها را در هر حالت مرتب کن تا صف‌های آینده/متوقف درست شوند.
            await military_service.schedule_training_queues(session, uid)
        await session.commit()
    print(f"✅ military barracks fixed. changed_users={changed_users}, raised_global_cap={raised_global_cap}, max_needed={max_needed}")


if __name__ == "__main__":
    asyncio.run(main())
