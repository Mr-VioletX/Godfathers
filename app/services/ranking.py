# -*- coding: utf-8 -*-
"""سرویسِ رتبه‌بندی و لیدربورد (مرحله ۱۳.۵).

شش دسته‌ی رتبه‌بندیِ سراسری (کلِ سرور):
  • power  ⚡ قدرت          — 🆕 مرحله ۳۰: فقط قدرتِ نظامی — نیروهای ارتش ×
                              سطحِ آپدیتِ آنها + ساختمان‌های رزمیِ عمارت + نیروهایِ
                              استخدامی + جاسوس + شهر. پول دیگر هیچ اثری ندارد چون
                              در دسته‌ی «ثروت» حساب می‌شود.
  • wealth 💰 ثروت          — موجودیِ نقدی
  • level  🏆 لِوِل          — سطح (سپس XP)
  • income 📈 درآمدِ روزانه  — تخمینِ درآمدِ روزانه از زیردستان
  • spy    🕵️ جاسوسیِ موفق  — شمارنده‌ی جاسوسیِ موفق از PlayerStats
  • brand  🏷️ برند          — 🆕 مرحله ۳۰: اعتبارِ برندِ بازیکن

محاسبه‌ها به‌صورتِ «دسته‌ای» (batch) انجام می‌شوند: به‌جای یک کوئری در ازای هر
بازیکن، همه‌ی ردیف‌ها یک‌بار خوانده و در حافظه گروه‌بندی می‌شوند.

همچنین القابِ «پویا»ی صدرِ قدرت (زئوس / بانوی والهالا) بر اساسِ نفرِ اولِ
جدولِ قدرت به‌صورتِ خودکار جابه‌جا می‌شوند.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.economy import INCOME_PER_SUB_PER_HOUR, effective_subs
from app.data import military as MD            # 🆕 مرحله ۳۰
from app.data.estates import aggregate_effects
from app.models.branding import Brand          # 🆕 مرحله ۳۰
from app.models.mafia_city import MafiaBuilding, MafiaCity  # 🆕 بچ ۴ — شهرسازِ جدید
from app.data import mafia_city as MC
from app.models.military import MilitaryUnit   # 🆕 مرحله ۳۰
from app.models.estate import Estate
from app.models.factory import Factory
from app.models.player import Player
from app.models.professional import OwnedProfessional
from app.models.spy import Spy
from app.models.title import PlayerStats, PlayerTitle, TitleClaim, TitleProfile
from app.models.worldbank import BankAccount

PAGE_SIZE = 10

# --- ضرایبِ فرمولِ قدرت (در یک‌جا تا بالانس آسان باشد) ---
W_LEVEL = 30
W_MILITARY = 60
W_SPY_LEVEL = 24
W_CITY = 120
W_FACTORY = 10            # اقتصادی — دیگر در فرمولِ قدرت وارد نمی‌شود
CASH_PER_POWER = 20_000   # منسوخ (🆕 مرحله ۳۰): پول دیگر در قدرت اثر ندارد
HOURLY_INCOME_PER_POWER = 10_000  # 🆕 هر ۱۰٬۰۰۰$ درآمدِ ساعتی = ۱ قدرت
# 🆕 مرحله ۴۶ (بچ ۳) — هم‌راستا با war_service
INCOME_POWER_SHARE = 0.20
DAILY_INCOME_PER_POWER = 50_000

# 🆕 مرحله ۳۰ — قدرت = قدرتِ نظامی
W_ARMY = 1                # قدرتِ ارتش (نوعِ نیرو × تعداد × سطحِ آپدیت)
W_ESTATE_COMBAT = 2       # ارزشِ رزمیِ عمارت (حمله/دفاع)
W_MIL_BUILDING = 30       # هر سطحِ ساختمانِ رزمیِ عمارت

# القابِ پویا‌ی صدرِ قدرت (بر اساسِ جنسیتِ نفرِ اول)
DYNAMIC_POWER_TITLES = {"male": "zeus", "female": "lady_of_valhalla"}


@dataclass
class RankEntry:
    tg_user_id: int
    name: str
    value: int


# --- دسته‌ها: (code, label, unit, نمایش‌دهنده‌ی مقدار) ---
CATEGORIES = [
    ("power", "⚡ قدرت", ""),
    ("war", "⚔️ جنگ", "کاپ"),
    ("ranked_wins", "🏅 برد جنگ", "برد"),
    ("wealth", "💰 ثروت", "$"),
    ("level", "🏆 لِوِل", ""),
    ("income", "📈 درآمدِ روزانه", "$"),
    ("spy", "🕵️ جاسوسیِ موفق", ""),
    ("brand", "🏷️ برند", ""),   # 🆕 مرحله ۳۰
    ("city", "🏙️ شهر", "نفر"),
    ("sports", "⚽ ورزش (امتیاز هفتگی لیگ)", "امتیاز"),   # 🆕 v1.7.9.6
]
CATEGORY_CODES = {c[0] for c in CATEGORIES}
CATEGORY_LABEL = {c[0]: c[1] for c in CATEGORIES}
_CATEGORY_UNIT = {c[0]: c[2] for c in CATEGORIES}


def format_value(cat: str, value: int) -> str:
    unit = _CATEGORY_UNIT.get(cat, "")
    if unit == "$":
        return f"{value:,}$"
    return f"{value:,}"


async def _military_keys() -> set:
    try:
        from app.data.professionals import PROFESSIONALS
        return {k for k, v in PROFESSIONALS.items() if v.get("group") == "military"}
    except Exception:
        return {"bodyguard", "mercenary", "sniper", "enforcer"}


async def compute_all(session: AsyncSession) -> dict[str, list[RankEntry]]:
    """همه‌ی دسته‌ها را یک‌جا حساب می‌کند و برای هر دسته فهرستِ مرتب (نزولی) می‌دهد."""
    players = (await session.execute(select(Player))).scalars().all()
    if not players:
        return {code: [] for code in CATEGORY_CODES}

    names = {p.tg_user_id: (p.name or "بی‌نام") for p in players}
    uids = list(names.keys())

    # --- بارگذاریِ دسته‌ایِ همه‌ی جدول‌های موردنیاز ---
    profs = (await session.execute(select(OwnedProfessional))).scalars().all()
    estates = (await session.execute(select(Estate))).scalars().all()
    spies = (await session.execute(select(Spy))).scalars().all()
    city_rows = (await session.execute(select(MafiaCity))).scalars().all()
    mbuild_rows = (await session.execute(select(MafiaBuilding))).scalars().all()
    factories = (await session.execute(select(Factory.tg_user_id))).all()
    stats_rows = (await session.execute(select(PlayerStats))).scalars().all()
    # 🆕 مرحله ۳۰ — نیروهای ارتش (برای قدرت) و برندها (برای دسته‌ی برند)
    units = (await session.execute(select(MilitaryUnit))).scalars().all()
    brand_rows = (await session.execute(select(Brand))).scalars().all()
    try:
        from app.models.rank import RankState
        rank_rows = (await session.execute(select(RankState))).scalars().all()
    except Exception:
        rank_rows = []
    try:
        bank_rows = (await session.execute(select(BankAccount))).scalars().all()
    except Exception:
        bank_rows = []


    try:
        from app.models.football_standing import FootballStanding
        standings = (await session.execute(select(FootballStanding))).scalars().all()
    except Exception:
        standings = []

    military = await _military_keys()

    subs_by_user: dict[int, int] = defaultdict(int)
    military_by_user: dict[int, int] = defaultdict(int)
    for op in profs:
        subs_by_user[op.tg_user_id] += effective_subs(op)
        if op.prof_key in military:
            military_by_user[op.tg_user_id] += 1

    estates_by_user: dict[int, list] = defaultdict(list)
    for e in estates:
        estates_by_user[e.tg_user_id].append((e.role_key, e.level))

    spy_levels_by_user: dict[int, int] = defaultdict(int)
    for s in spies:
        spy_levels_by_user[s.owner_id] += int(s.level or 0)

    # 🆕 بچ ۴ — ساختمان‌هایِ شهرِ جدید، گروه‌بندی بر اساسِ city_id
    counts_by_city: dict[int, dict] = defaultdict(dict)
    for mb in mbuild_rows:
        counts_by_city[mb.city_id][mb.btype] = int(mb.qty or 0)

    city_count: dict[int, int] = defaultdict(int)
    city_income_by_user: dict[int, int] = defaultdict(int)
    for c in city_rows:
        city_count[c.tg_user_id] += 1
        try:
            counts = counts_by_city.get(c.id, {})
            city_income_by_user[c.tg_user_id] += int(MC.income_rate_per_hour(
                counts, int(c.tax_rate or 0),
                int(c.population or 0), int(c.satisfaction or 0)))
        except Exception:
            pass
    # 🆕 بچ ۴ — کشور حذف شد؛ درآمدِ کشور دیگر وجود ندارد
    country_income_by_user: dict[int, int] = defaultdict(int)
    factory_count: dict[int, int] = defaultdict(int)
    for (uid,) in factories:
        factory_count[uid] += 1

    # 🆕 مرحله ۳۰ — قدرتِ ارتش: هر نیرو × تعداد × ضریبِ سطحِ آپدیت
    army_by_user: dict[int, int] = defaultdict(int)
    for u in units:
        try:
            army_by_user[u.owner_id] += int(MD.unit_power(
                u.unit_key, int(u.count or 0), int(u.upgrade_level or 1)
            ))
        except Exception:
            army_by_user[u.owner_id] += int(u.count or 0)

    # 🆕 مرحله ۳۰ — اعتبارِ برندِ هر بازیکن (دسته‌ی «برند»)
    brand_by_user: dict[int, int] = defaultdict(int)
    for br in brand_rows:
        brand_by_user[getattr(br, "owner_id")] += int(br.reputation or 0)

    cups_by_user: dict[int, int] = defaultdict(int)
    ranked_wins_by_user: dict[int, int] = defaultdict(int)
    for rr in rank_rows:
        uid = int(getattr(rr, "owner_id", 0) or 0)
        cups_by_user[uid] = int(getattr(rr, "cups", 0) or 0)
        ranked_wins_by_user[uid] = int(getattr(rr, "wins", 0) or 0)

    spy_success_by_user = {st.tg_user_id: int(st.spy_success or 0) for st in stats_rows}
    deposits_by_user = {a.owner_id: int(a.deposit or 0) for a in bank_rows}
    cash_by_user = {p.tg_user_id: int(p.cash or 0) + deposits_by_user.get(p.tg_user_id, 0) for p in players}
    level_by_user = {p.tg_user_id: int(p.level or 0) for p in players}
    xp_by_user = {p.tg_user_id: int(p.xp or 0) for p in players}
    sports_by_user = {s.owner_id: int(s.weekly_points or 0) for s in standings}   # 🆕 v1.7.9.6

    def estate_combat(uid: int) -> int:
        totals = aggregate_effects(estates_by_user.get(uid, []))
        combat = totals.get("attack_pct", 0.0) + totals.get("defense_pct", 0.0)
        return int(combat * 100) + len(estates_by_user.get(uid, [])) * 5

    def military_buildings(uid: int) -> int:
        """🆕 مرحله ۳۰ — مجموعِ سطحِ ساختمان‌هایِ رزمیِ عمارت."""
        total = 0
        for role_key, level in estates_by_user.get(uid, []):
            try:
                eff = aggregate_effects([(role_key, level)])
            except Exception:
                continue
            if eff.get("attack_pct", 0.0) or eff.get("defense_pct", 0.0):
                total += int(level or 1)
        return total

    def hourly_income_of(uid: int) -> int:
        return int(
            subs_by_user.get(uid, 0) * INCOME_PER_SUB_PER_HOUR
            + city_income_by_user.get(uid, 0)
            + country_income_by_user.get(uid, 0)
        )

    def power_of(uid: int) -> int:
        """🆕 مرحله ۳۰ — قدرت فقط نظامی است؛ پول هیچ نقشی ندارد."""
        # 🆕 مرحله ۴۶ — همان فرمولِ war_service:
        #   ارتش + عمارتِ نظامی + لول + درصدی از درآمدِ روزانه
        daily = hourly_income_of(uid) * 24
        return (
            army_by_user.get(uid, 0) * W_ARMY
            + military_buildings(uid) * W_MIL_BUILDING
            + estate_combat(uid) * W_ESTATE_COMBAT
            + level_by_user.get(uid, 0) * W_LEVEL
            + int(daily * INCOME_POWER_SHARE) // DAILY_INCOME_PER_POWER
        )

    def income_of(uid: int) -> int:
        return int(hourly_income_of(uid) * 24)

    raw = {
        "power": [(uid, power_of(uid)) for uid in uids],
        "war": [(uid, cups_by_user.get(uid, 0)) for uid in uids],
        "ranked_wins": [(uid, ranked_wins_by_user.get(uid, 0)) for uid in uids],
        "wealth": [(uid, cash_by_user.get(uid, 0)) for uid in uids],
        # لِوِل: کلیدِ مرتب‌سازی سطح*۱۰۰۰+XP اما مقدارِ نمایشی خودِ سطح است
        "level": [(uid, level_by_user.get(uid, 0) * 1000 + min(999, xp_by_user.get(uid, 0)))
                  for uid in uids],
        "income": [(uid, income_of(uid)) for uid in uids],
        "spy": [(uid, spy_success_by_user.get(uid, 0)) for uid in uids],
        # 🆕 مرحله ۳۰ — دسته‌ی برند
        "brand": [(uid, brand_by_user.get(uid, 0)) for uid in uids],
        "city": [(uid, sum(int(c.population or 0) for c in city_rows if c.tg_user_id == uid)) for uid in uids],
        "sports": [(uid, sports_by_user.get(uid, 0)) for uid in uids],   # 🆕 v1.7.9.6
    }

    result: dict[str, list[RankEntry]] = {}
    for cat, pairs in raw.items():
        pairs.sort(key=lambda t: t[1], reverse=True)
        if cat == "level":
            result[cat] = [
                RankEntry(uid, names[uid], level_by_user.get(uid, 0)) for uid, _ in pairs
            ]
        else:
            result[cat] = [RankEntry(uid, names[uid], val) for uid, val in pairs]
    return result


def page_slice(entries: list[RankEntry], page: int) -> tuple[list[RankEntry], int, int]:
    """(بخشِ صفحه، شماره‌ی صفحه‌ی نرمال‌شده، تعدادِ کلِ صفحات) را برمی‌گرداند."""
    total = max(1, (len(entries) + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(0, min(page, total - 1))
    start = page * PAGE_SIZE
    return entries[start:start + PAGE_SIZE], page, total


def find_rank(entries: list[RankEntry], uid: int) -> tuple[int, int] | None:
    """(رتبه‌ی ۱-پایه، مقدار) بازیکن را در فهرست پیدا می‌کند یا None."""
    for i, e in enumerate(entries):
        if e.tg_user_id == uid:
            return i + 1, e.value
    return None


# ---------------------------------------------------------------------------
# القابِ پویا‌ی صدرِ قدرت (زئوس / بانوی والهالا)
# ---------------------------------------------------------------------------
async def _player_gender(session: AsyncSession, uid: int) -> str | None:
    return await session.scalar(select(Player.gender).where(Player.tg_user_id == uid))


async def _strip_dynamic_title(session: AsyncSession, key: str) -> None:
    """لقبِ پویا را از هر دارنده‌ی قبلی برمی‌دارد (چون فقط نفرِ اول باید داشته باشد)."""
    rows = (await session.execute(
        select(PlayerTitle).where(PlayerTitle.title_key == key)
    )).scalars().all()
    # ⚡ مرحله ۲۸ (سرعت): پروفایل‌ها یک‌جا خوانده می‌شوند (حذفِ N+1)
    uids = [row.tg_user_id for row in rows]
    profiles = {}
    if uids:
        profiles = {
            pr.tg_user_id: pr
            for pr in (await session.execute(
                select(TitleProfile).where(TitleProfile.tg_user_id.in_(uids))
            )).scalars().all()
        }
    for row in rows:
        pr = profiles.get(row.tg_user_id)
        if pr and pr.active_title_key == key:
            pr.active_kind = None
            pr.active_title_key = None
        await session.delete(row)
    claim = await session.get(TitleClaim, key)
    if claim:
        await session.delete(claim)
    await session.flush()


async def _set_flags_top_power(session: AsyncSession, leader_uid: int | None) -> None:
    """پرچمِ is_top_power را فقط برای نفرِ اول روشن و برای بقیه خاموش می‌کند."""
    rows = (await session.execute(select(PlayerStats))).scalars().all()
    for st in rows:
        want = leader_uid is not None and st.tg_user_id == leader_uid
        if bool(st.is_top_power) != want:
            st.is_top_power = want
    await session.flush()


async def assign_dynamic_power_titles(
    session: AsyncSession, ranking: dict[str, list[RankEntry]] | None = None
) -> dict | None:
    """لقبِ صدرِ قدرت را به نفرِ اولِ جدولِ قدرت می‌دهد و در صورتِ تغییرِ صدرنشین
    آن را جابه‌جا می‌کند. خروجی: اطلاعاتِ تغییر یا None اگر تغییری نبود.
    """
    if ranking is None:
        ranking = await compute_all(session)
    power = ranking.get("power", [])
    leader = next((e for e in power if e.value > 0), None)
    leader_uid = leader.tg_user_id if leader else None

    await _set_flags_top_power(session, leader_uid)

    if leader_uid is None:
        return None
    gender = await _player_gender(session, leader_uid)
    key = DYNAMIC_POWER_TITLES.get(gender or "")
    if key is None:
        return None  # جنسیتِ نامشخص → لقبِ جنسیتی داده نمی‌شود

    current = await session.get(TitleClaim, key)
    if current is not None and current.tg_user_id == leader_uid:
        return None  # صدرنشین همان قبلی است — تغییری لازم نیست

    # صدرنشین عوض شده → هر دو لقبِ پویا را پاک و به نفرِ اول بده
    for k in DYNAMIC_POWER_TITLES.values():
        await _strip_dynamic_title(session, k)
    session.add(TitleClaim(title_key=key, tg_user_id=leader_uid))
    session.add(PlayerTitle(tg_user_id=leader_uid, title_key=key))
    await session.flush()
    return {"key": key, "uid": leader_uid, "name": leader.name}
