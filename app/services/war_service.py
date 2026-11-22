# -*- coding: utf-8 -*-
"""سرویسِ جنگ — محاسبه‌ی قدرتِ رزمی، درآمدِ روزانه، جمعیت، و ابزارهای سپر/کول‌داون.

این‌جا تنها جایی است که داده‌ی بازیکن از چند جدول جمع می‌شود؛ منطقِ خالص در app/data/war.py است.
"""
from datetime import datetime, timedelta

from sqlalchemy import func, select

from app.data import war as W
from app.data.economy import INCOME_PER_SUB_PER_HOUR, effective_subs
from app.data.estates import aggregate_effects
from app.data.professionals import PROFESSIONALS
from app.services import mafia_city_service as CS  # 🆕 بچ ۴ — شهرسازِ جدید
from app.models.estate import Estate
from app.models.player import Player
from app.models.professional import OwnedProfessional
from app.models.spy import Spy
from app.models.war import Battle, WarState

# --- وزن‌های قدرتِ رزمی (هم‌راستا با services/ranking اما با تأکیدِ نظامی) ---
W_LEVEL = 30
W_MILITARY = 60
W_SPY_LEVEL = 24
W_CITY = 120
W_CAPTURED = 90
HOURLY_INCOME_PER_POWER = 10_000
# 🆕 مرحله ۴۶ — وزنِ تازه‌ی فرمولِ قدرت
W_ESTATE_COMBAT = 250          # هر ۱٪ حمله/دفاعِ عمارت‌های نظامی
INCOME_POWER_SHARE = 0.20      # فقط ۲۰٪ درآمدِ روزانه در قدرت دخیل است
DAILY_INCOME_PER_POWER = 50_000   # 🆕 هر ۱۰٬۰۰۰$ درآمدِ ساعتی = ۱ قدرت (شاملِ زیردستان + شهر + کشور)

# کلیدهای حرفه‌ایِ نظامی (با fallback اگر گروه تعریف نشده باشد)
try:
    MILITARY_KEYS = {k for k, v in PROFESSIONALS.items() if v.get("group") == "military"}
except Exception:  # pragma: no cover
    MILITARY_KEYS = set()
if not MILITARY_KEYS:
    MILITARY_KEYS = {"bodyguard", "mercenary", "sniper", "enforcer"}


async def _scalar(session, stmt, default=0):
    res = await session.execute(stmt)
    val = res.scalar()
    return val if val is not None else default


def power_formula_help() -> str:
    """توضیحِ فرمولِ تازه‌ی قدرت برای راهنما."""
    return (
        "💥 <b>فرمولِ قدرتِ رزمی</b>\n"
        "• 🫡 نیروهای نظامی (تعداد × لولِ ارتقا) — ستونِ اصلی\n"
        "• 🏰 عمارت‌های نظامی (درصدِ حمله/دفاع)\n"
        "• 👑 ویژگی‌های مثبتِ القاب (ضریبِ نهایی)\n"
        "• 💰 درصدی از درآمدِ روزانه\n"
        f"• 🎚️ لولِ بازیکن (هر لول = {W_LEVEL} قدرت)\n\n"
        "⚠️ جاسوس، حرفه‌ای‌ها و شهر دیگر قدرتِ رزمی نمی‌دهند.\n"
        "⚠️ ارتشِ تک‌بُعدی ریسکِ واقعی دارد: حریف از نقطه‌ضعفت می‌زند."
    )
async def _city_country_hourly_income(session, uid: int) -> int:
    """درآمدِ ساعتیِ شهر (برایِ فرمولِ قدرت). 🆕 بچ ۴: از شهرسازِ جدید."""
    try:
        return int(await CS.city_hourly_income(session, uid))
    except Exception:
        return 0


async def compute_combat_power(session, uid: int) -> int:
    """🆕 مرحله ۴۶ — فرمولِ تازه‌ی قدرتِ رزمی.

    قدرت فقط از چهار منبع می‌آید:
      ۱) نیروهای نظامی (اصلی‌ترین سهم)
      ۲) عمارت‌های نظامی (درصدِ حمله/دفاع)
      ۳) ویژگی‌های مثبتِ القاب
      ۴) درصدی از درآمدِ روزانه
      ۵) لولِ بازیکن (🆕 بچ ۳ — دوباره به فرمول بازگشت)
    جاسوس، حرفه‌ای‌ها و شهر/کشور دیگر در قدرت حساب نمی‌شوند.
    """
    res = await session.execute(select(Player).where(Player.tg_user_id == uid))
    player = res.scalar_one_or_none()
    if player is None:
        return 0

    # ۲) عمارت‌های نظامی — فقط اثرِ حمله/دفاع (عمارتِ غیرنظامی قدرت نمی‌دهد)
    res = await session.execute(select(Estate).where(Estate.tg_user_id == uid))
    estates = list(res.scalars().all())
    totals = aggregate_effects([(e.role_key, e.level) for e in estates])
    estate_combat = int((totals.get("attack_pct", 0) + totals.get("defense_pct", 0)) * W_ESTATE_COMBAT)

    # ۱) ارتشِ نظامی
    military_power = 0
    try:
        from app.services import military_service
        military_power = await military_service.army_power(session, uid)
    except Exception:
        military_power = 0

    # ۴) درصدی از درآمدِ روزانه
    try:
        income = await daily_income(session, uid)
    except Exception:
        income = 0
    income_power = int(max(0, int(income)) * INCOME_POWER_SHARE) // DAILY_INCOME_PER_POWER

    # ۵) لولِ بازیکن — 🆕 بچ ۳: دوباره به فرمولِ قدرت برگشت
    level_power = max(1, int(getattr(player, "level", 1) or 1)) * W_LEVEL

    power = int(military_power) + estate_combat + income_power + level_power

    # ۳) ویژگی‌های مثبتِ القاب
    try:
        from app.services import title_effects
        power = int(power * await title_effects.combat_multiplier(session, uid))
    except Exception:
        pass
    return max(1, int(power))
async def daily_income(session, uid: int) -> int:
    """تخمینِ درآمدِ روزانه‌ی بازیکن از رویِ زیردستانِ حرفه‌ای‌ها."""
    res = await session.execute(select(OwnedProfessional).where(OwnedProfessional.tg_user_id == uid))
    profs = list(res.scalars().all())
    subs = 0
    for op in profs:
        try:
            subs += int(effective_subs(op))
        except Exception:
            subs += int(getattr(op, "subordinates", 0) or 0)
    hourly = subs * INCOME_PER_SUB_PER_HOUR + await _city_country_hourly_income(session, uid)
    return int(hourly * 24)


async def total_population(session, uid: int) -> int:
    """جمعیتِ شهرِ بازیکن. 🆕 بچ ۴: تک‌شهری."""
    try:
        return int(await CS.total_population(session, uid))
    except Exception:
        return 0


async def city_count_total(session, uid: int) -> int:
    """تعدادِ شهر (۰ یا ۱). 🆕 بچ ۴: تک‌شهری."""
    try:
        return int(await CS.city_count(session, uid))
    except Exception:
        return 0


async def get_or_create_war_state(session, uid: int) -> WarState:
    st = await session.get(WarState, uid)
    if st is None:
        st = WarState(tg_user_id=uid)
        session.add(st)
        await session.flush()
    return st


def is_shielded(state: WarState | None, now: datetime | None = None) -> bool:
    now = now or datetime.utcnow()
    return bool(state and state.shield_until and state.shield_until > now)


def shield_days_left(state: WarState | None, now: datetime | None = None) -> int:
    now = now or datetime.utcnow()
    if not (state and state.shield_until and state.shield_until > now):
        return 0
    return max(1, (state.shield_until - now).days + 1)


def attack_cooldown_left_min(state: WarState | None, now: datetime | None = None) -> int:
    """دقیقه‌ی باقی‌مانده از کول‌داونِ حمله‌ی مهاجم (۰ = آماده)."""
    now = now or datetime.utcnow()
    if not (state and state.last_attack_at):
        return 0
    ready_at = state.last_attack_at + timedelta(hours=W.ATTACK_COOLDOWN_HOURS)
    if ready_at <= now:
        return 0
    return max(1, int((ready_at - now).total_seconds() // 60))


async def active_loot_lock(session, attacker_id: int, defender_id: int, now: datetime | None = None) -> Battle | None:
    """اگر مهاجم در دوره‌ی قفلِ غنیمتِ همین هدف باشد، رکوردِ فعال را برمی‌گرداند."""
    now = now or datetime.utcnow()
    res = await session.execute(
        select(Battle)
        .where(
            Battle.attacker_id == attacker_id,
            Battle.defender_id == defender_id,
            Battle.loot_until.is_not(None),
            Battle.loot_until > now,
        )
        .order_by(Battle.id.desc())
    )
    return res.scalars().first()
