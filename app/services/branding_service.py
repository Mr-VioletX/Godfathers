# -*- coding: utf-8 -*-
"""سرویسِ برندسازی — ساخت/ارتقا/کمپینِ تبلیغاتی (v1.7.6 کول‌داونِ مستقل)."""
from __future__ import annotations

import json
from datetime import datetime, timedelta

from sqlalchemy import select

from app.data import branding as B
from app.models.branding import Brand
from app.models.player import Player


async def reputation_income_cap_pct(session) -> int:
    """سقف ٪ بونس شهرت برند — فقط از GameNumberSetting با کلید اختصاصی.

    با city.hourly_income_cap و military.barracks_max_capacity تداخل ندارد.
    """
    try:
        from app.models.admin import GameNumberSetting
        row = await session.get(GameNumberSetting, B.BRAND_REP_CAP_KEY)
        if row is not None and row.value is not None and str(row.value).strip() != "":
            v = int(float(str(row.value).strip()))
            return max(0, min(500, v))  # محافظ: 0..500٪
    except Exception:
        pass
    return int(B.BRAND_REP_CAP_DEFAULT)


async def reputation_bonus_pct(session, reputation: int) -> int:
    cap = await reputation_income_cap_pct(session)
    return int(B.reputation_income_bonus_pct(int(reputation or 0), cap_pct=cap))


async def brand_bonus_hint(session, reputation: int) -> str:
    cap = await reputation_income_cap_pct(session)
    return B.brand_income_bonus_hint(int(reputation or 0), cap_pct=cap)


def _load_cds(brand) -> dict:
    """کول‌داونِ هر کمپین را از ستونِ JSON می‌خواند."""
    raw = getattr(brand, "campaign_cooldowns", None)
    if not raw:
        return {}
    if isinstance(raw, dict):
        return dict(raw)
    try:
        data = json.loads(raw)
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _save_cds(brand, cds: dict) -> None:
    """کول‌داونِ کمپین‌ها را در ستونِ JSON ذخیره می‌کند."""
    try:
        brand.campaign_cooldowns = json.dumps(cds or {}, ensure_ascii=False)
    except Exception:
        brand.campaign_cooldowns = "{}"


def _parse_ts(value) -> datetime | None:
    """رشته‌ی ISO (یا datetime) را به datetime بی‌تایم‌زون تبدیل می‌کند."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        try:
            dt = datetime.fromisoformat(str(value))
        except Exception:
            return None
    if dt.tzinfo is not None:
        dt = dt.replace(tzinfo=None)
    return dt


async def get_brand(session, uid: int):
    """Load brand; auto-add missing campaign_cooldowns column if needed."""
    try:
        return await session.get(Brand, uid)
    except Exception as e:
        if "campaign_cooldowns" not in str(e):
            raise
        try:
            await session.rollback()
        except Exception:
            pass
        try:
            from sqlalchemy import text as _text
            await session.execute(_text("ALTER TABLE brands ADD COLUMN campaign_cooldowns TEXT DEFAULT '{}'"))
            await session.commit()
        except Exception:
            try:
                await session.rollback()
            except Exception:
                pass
        return await session.get(Brand, uid)

def campaign_ready_at(brand: Brand | None, key: str) -> datetime | None:
    """زمانِ آماده‌شدنِ دوبارهٔ یک کمپین خاص."""
    if brand is None:
        return None
    camp = B.get_campaign(key)
    if not camp:
        return None
    cds = _load_cds(brand)
    last = _parse_ts(cds.get(key))
    # سازگاری با نسخه‌های قبلی که فقط last_campaign_at داشتند
    if last is None and brand.last_campaign_at is not None and len(cds) == 0:
        last = brand.last_campaign_at
    if last is None:
        return None
    return last + timedelta(hours=int(camp["cooldown_h"]))


def campaign_cooldown_left_min(brand: Brand | None, key: str, now: datetime | None = None) -> int:
    now = now or datetime.utcnow()
    ready = campaign_ready_at(brand, key)
    if ready is None or ready <= now:
        return 0
    return max(0, int((ready - now).total_seconds() // 60))


async def create_brand(session, uid: int, name: str) -> tuple[bool, str]:
    player = (await session.execute(select(Player).where(Player.tg_user_id == uid))).scalar_one_or_none()
    if player is None:
        return False, "اول /start را بزن."
    if int(player.level or 1) < B.BRAND_UNLOCK_LEVEL:
        return False, f"🔒 برندسازی از سطحِ {B.BRAND_UNLOCK_LEVEL} باز می‌شود."
    if await get_brand(session, uid) is not None:
        return False, "تو قبلاً یک برند داری."
    if int(player.cash or 0) < B.BRAND_FOUND_COST:
        return False, f"💸 پولت کافی نیست. هزینه‌ی ثبتِ برند: {B.BRAND_FOUND_COST:,}$"
    name = (name or "").strip()[:48]
    if not name:
        return False, "نامِ معتبر بفرست."
    player.cash = int(player.cash or 0) - B.BRAND_FOUND_COST
    session.add(Brand(owner_id=uid, name=name, level=1, reputation=0, campaign_cooldowns="{}"))
    try:
        from app.data import leveling as _lv
        _lv.add_xp(player, 250, source="brand_found")
    except Exception:
        pass
    await session.flush()
    return True, f"🎉 برندِ <b>{name}</b> ثبت شد!"


async def upgrade_brand(session, uid: int) -> tuple[bool, str]:
    brand = await get_brand(session, uid)
    if brand is None:
        return False, "اول یک برند بساز."
    if not B.can_upgrade(int(brand.level)):
        return False, "⭐ برندت به بیشینه‌ی سطح رسیده."
    player = (await session.execute(select(Player).where(Player.tg_user_id == uid))).scalar_one_or_none()
    cost = B.upgrade_cost(int(brand.level))
    if player is None or int(player.cash or 0) < cost:
        return False, f"💸 پولت کافی نیست. هزینه‌ی ارتقا: {cost:,}$"
    player.cash = int(player.cash or 0) - cost
    brand.level = int(brand.level) + 1
    try:
        from app.data import leveling as _lv
        _lv.add_xp(player, (40 + 20 * int(brand.level)) // 2, source="brand_upgrade")
    except Exception:
        pass
    await session.flush()
    _cap = await reputation_income_cap_pct(session)

    tot = B.reputation_income_bonus_pct(int(brand.reputation or 0), cap_pct=_cap)
    return True, (
        f"⬆️ برندت به سطح {brand.level} رسید — بونوسِ درآمد: +{tot}٪ "
        f"(فقط شهرت — سقف از تنظیم ادمین)"
    )


async def run_campaign(session, uid: int, key: str) -> tuple[bool, str]:
    brand = await get_brand(session, uid)
    if brand is None:
        return False, "اول یک برند بساز."
    camp = B.get_campaign(key)
    if not camp:
        return False, "کمپینِ نامعتبر."
    now = datetime.utcnow()
    left = campaign_cooldown_left_min(brand, key, now)
    if left > 0:
        hrs, mins = divmod(left, 60)
        wait = f"{hrs}س و {mins}د" if hrs else f"{mins} دقیقه"
        return False, f"⏳ کول‌داونِ «{camp['name']}» هنوز تمام نشده. {wait} دیگر تلاش کن. بقیهٔ تبلیغ‌ها آزادند."
    player = (await session.execute(select(Player).where(Player.tg_user_id == uid))).scalar_one_or_none()
    if player is None or int(player.cash or 0) < camp["cost"]:
        return False, f"💸 پولت کافی نیست. هزینه‌ی کمپین: {camp['cost']:,}$"
    player.cash = int(player.cash or 0) - camp["cost"]
    brand.reputation = int(brand.reputation or 0) + camp["rep"]
    # فقط همین کمپین قفل می‌شود
    cds = _load_cds(brand)
    cds[key] = now.isoformat()
    _save_cds(brand, cds)
    brand.last_campaign_at = now  # سازگاری عقب‌رو
    try:
        from app.data import leveling as _lv
        _lv.add_xp(player, min(150, max(8, camp["cost"] // 6000)), source="brand_campaign")
    except Exception:
        pass
    await session.flush()
    _cap = await reputation_income_cap_pct(session)

    tot = B.reputation_income_bonus_pct(int(brand.reputation or 0), cap_pct=_cap)
    return True, (
        f"📣 کمپینِ {camp['name']} اجرا شد!\n"
        f"⭐ +{camp['rep']} شهرت — شهرتِ کل: {brand.reputation:,}\n"
        f"🏷️ رده: {B.tier_for(int(brand.reputation))}\n"
        f"📈 بونوسِ درآمدِ برند: +{tot}٪\n"
        f"⏳ کول‌داونِ همین تبلیغ: {camp['cooldown_h']} ساعت (سایر تبلیغ‌ها آزاد)"
    )


async def brand_prestige(session, uid: int) -> int:
    brand = await get_brand(session, uid)
    if brand is None:
        return 0
    return B.prestige_value(int(brand.level), int(brand.reputation))
