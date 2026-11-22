# -*- coding: utf-8 -*-
"""🆕 بچ ۴ — سرویسِ شهرسازِ جدید (تک‌شهری).

تمامِ منطقِ خریدِ شهر، ساخت/ارتقا/تبدیلِ ساختمان، انبار، مالیات،
تولیدِ مصالح، رشدِ جمعیت و جمع‌آوریِ درآمد اینجاست.

APIِ سازگار برای سرویس‌های وابسته (war/ranking/worldbank/sports/spy):
  city_hourly_income, total_population, city_count, city_value, active_city, city_name
"""
from __future__ import annotations

from datetime import datetime, timedelta
import json

from sqlalchemy import select

from app.data import mafia_city as C
from app.data import city_mayor as MY
from app.models.mafia_city import CityBuildQueue, MafiaBuilding, MafiaCity
from app.models.player import Player
from app.models.admin import GameNumberSetting
from app.models.estate import Estate
from app.models.professional import OwnedProfessional
from app.data.estates import ESTATES
from app.data.professionals import PROFESSIONALS
from app.data.economy import MAX_PROF_LEVEL


# ---------------------------------------------------------------------------
# خواندن/ساختن
# ---------------------------------------------------------------------------
async def get_city(session, uid: int) -> MafiaCity | None:
    res = await session.execute(
        select(MafiaCity).where(MafiaCity.tg_user_id == int(uid))
    )
    return res.scalar_one_or_none()


async def _buildings(session, city_id: int) -> dict[str, int]:
    res = await session.execute(
        select(MafiaBuilding).where(MafiaBuilding.city_id == int(city_id))
    )
    return {b.btype: int(b.qty) for b in res.scalars().all()}


async def settle_city_builds(session, city: MafiaCity) -> list[str]:
    """ساخت‌هایی که زمانشان رسیده را نهایی می‌کند (v1.7.8.3)."""
    now = datetime.utcnow()
    rows = (await session.execute(
        select(CityBuildQueue).where(
            CityBuildQueue.city_id == int(city.id),
            CityBuildQueue.ready_at <= now,
        )
    )).scalars().all()
    done: list[str] = []
    for q in rows:
        if q.kind == "warehouse":
            city.warehouse_level = int(city.warehouse_level or 1) + 1
            done.append("🏪 انبار شهر")
        elif q.kind == "upgrade":
            row = await _get_row(session, city.id, q.btype)
            if row:
                row.qty = int(row.qty) + max(1, int(q.qty or 1))
            done.append("⬆️ " + C.building_name(q.btype))
        else:
            row = await _get_row(session, city.id, q.btype)
            add = max(1, int(q.qty or 1))
            if row:
                row.qty = int(row.qty) + add
            else:
                session.add(MafiaBuilding(city_id=city.id, btype=q.btype, qty=add))
            label = C.building_name(q.btype)
            done.append(f"{label} ×{add:,}" if add > 1 else label)
        await session.delete(q)
    if done:
        await session.flush()
    return done


async def pending_builds(session, city_id: int):
    """ساخت‌های در جریان (مرتب بر اساس نزدیک‌ترین پایان)."""
    rows = (await session.execute(
        select(CityBuildQueue)
        .where(CityBuildQueue.city_id == int(city_id))
        .order_by(CityBuildQueue.ready_at)
    )).scalars().all()
    return rows


async def _discounted_cost(session, uid: int, cost: int) -> tuple[int, int]:
    """تخفیف اشتراک روی هزینه ساخت — خروجی: (قیمت نهایی, درصد)."""
    try:
        from app.services import bonus_breakdown as _bb
        d = await _bb.discount_breakdown(session, uid, int(cost))
        return int(d.get("final", cost)), int(d.get("disc_pct", 0) or 0)
    except Exception:
        return int(cost), 0


async def _get_row(session, city_id: int, btype: str) -> MafiaBuilding | None:
    res = await session.execute(
        select(MafiaBuilding).where(
            MafiaBuilding.city_id == int(city_id),
            MafiaBuilding.btype == btype,
        )
    )
    return res.scalar_one_or_none()


async def _player(session, uid: int) -> Player | None:
    res = await session.execute(
        select(Player).where(Player.tg_user_id == int(uid))
    )
    return res.scalar_one_or_none()


def _resources(city: MafiaCity) -> dict[str, int]:
    """منابع متنوع؛ موجودی قدیمی مصالح در نخستین استفاده به سنگ منتقل می‌شود."""
    try:
        raw = json.loads(city.resources_json or "{}")
    except (TypeError, ValueError):
        raw = {}
    data = {key: max(0, int(raw.get(key, 0) or 0)) for key in C.RESOURCE_ORDER}
    legacy = int(city.materials or 0)
    if legacy:
        data["stone"] += legacy
        city.materials = 0
        city.resources_json = json.dumps(data, ensure_ascii=False)
    return data


def _set_resources(city, resources: dict) -> None:
    import json as _json
    data = {str(k): int(v or 0) for k, v in (resources or {}).items() if int(v or 0) != 0}
    city.resources_json = _json.dumps(data, ensure_ascii=False)


def _save_resources(city: MafiaCity, resources: dict[str, int]) -> None:
    city.resources_json = json.dumps({key: max(0, int(resources.get(key, 0) or 0)) for key in C.RESOURCE_ORDER}, ensure_ascii=False)


async def buy_resource(session, uid: int, resource: str, qty: int) -> tuple[bool, str]:
    city = await get_city(session, uid)
    if not city:
        return False, "اول باید یک شهر بخری."
    if resource not in C.RESOURCES or int(qty) <= 0:
        return False, "نوع یا مقدار منبع نامعتبر است."
    await tick(session, city)
    resources = _resources(city)
    qty = int(qty)
    cap = C.warehouse_capacity(city.warehouse_level)
    free = cap - C.resource_total(resources)
    if qty > free:
        return False, f"فضای کافی در انبار نداری؛ فقط {max(0, free):,} واحد فضا مانده است."
    price = C.resource_price(resource) * qty
    player = await _player(session, uid)
    if not player or int(player.cash or 0) < price:
        return False, f"پول کافی نداری؛ هزینه: {price:,} 💵"
    player.cash = int(player.cash) - price
    resources[resource] += qty
    _save_resources(city, resources)
    await session.commit()
    return True, f"✅ {qty:,} واحد {C.resource_name(resource)} به انبار شهر اضافه شد. (−{price:,} 💵)"


# ---------------------------------------------------------------------------
# خریدِ شهر
# ---------------------------------------------------------------------------
async def found_city(session, uid: int, name: str | None = None) -> tuple[bool, str]:
    """خرید/تأسیسِ شهر (پیش‌نیاز: لول ۳۹ و ۲۵۰M)."""
    existing = await get_city(session, uid)
    if existing:
        return False, "تو قبلاً یک شهر داری."
    player = await _player(session, uid)
    if not player:
        return False, "پروفایلِ بازیکن پیدا نشد."
    if int(player.level) < C.CITY_MIN_LEVEL:
        return False, f"برای خریدِ شهر باید حداقل لول {C.CITY_MIN_LEVEL} باشی."
    estates = (await session.execute(select(Estate).where(Estate.tg_user_id == int(uid)))).scalars().all()
    estate_keys = {row.role_key for row in estates}
    missing_estates = set(ESTATES) - estate_keys
    if missing_estates:
        return False, f"ابتدا باید همه عمارت‌ها را بسازی ({len(missing_estates)} عمارت باقی مانده)."
    pros = (await session.execute(select(OwnedProfessional).where(OwnedProfessional.tg_user_id == int(uid)))).scalars().all()
    pros_by_key = {row.prof_key: row for row in pros}
    missing_pros = [key for key in PROFESSIONALS if key not in pros_by_key or int(pros_by_key[key].level) < MAX_PROF_LEVEL]
    if missing_pros:
        return False, f"ابتدا همه حرفه‌ای‌ها را به حداکثر سطح برسان ({len(missing_pros)} حرفه‌ای باقی مانده)."
    if int(player.cash) < C.CITY_COST:
        return False, f"پولِ کافی نداری. هزینه‌ی خریدِ شهر: {C.CITY_COST:,} 💵"
    player.cash = int(player.cash) - C.CITY_COST
    now = datetime.utcnow()
    # Population is a city value, never the 4^N professional workforce.
    base_population = C.STARTING_POPULATION
    city = MafiaCity(
        tg_user_id=int(uid),
        name=(name or "شهرِ من")[:64],
        population=base_population,
        base_population=base_population,
        satisfaction=C.SAT_BASE,
        tax_rate=C.TAX_NEUTRAL,
        purchase_price=C.CITY_COST,
        warehouse_level=1,
        materials=0,
        founded_at=now,
        last_income_at=now,
        last_prod_at=now,
        last_grow_at=now,
    )
    session.add(city)
    await session.flush()
    # در تأسیس، یک واحد از خدمات پایه و تعدادی خانه برای جمعیت پایه ساخته می‌شود.
    initial = ("road", "power", "water", "school", "clinic", "police", "fire", "farm", "bank", "park", "cinema", "factory", "quarry")
    for btype in initial:
        if C.get_building(btype):
            session.add(MafiaBuilding(city_id=city.id, btype=btype, qty=1))
    houses = C.starting_house_count()
    session.add(MafiaBuilding(city_id=city.id, btype="small_house", qty=houses))
    await session.commit()
    return True, f"🏙️ شهرِ «{city.name}» تأسیس شد! جمعیت پایه: {base_population:,} نفر. (−{C.CITY_COST:,} 💵)"


async def _normalize_city_population_seed(session, city: MafiaCity, counts: dict[str, int]) -> bool:
    """Repair old 41M-style seeds once and preserve construction above the seed."""
    old_base = int(city.base_population or 0)
    old_population = int(city.population or 0)
    new_base, new_population, changed = C.normalize_population_seed(old_base, old_population)
    if not changed:
        return False
    city.base_population = new_base
    city.population = new_population
    if old_base > C.STARTING_POPULATION:
        row = await _get_row(session, city.id, "small_house")
        old_seed_houses = C.legacy_starter_house_count(old_base)
        if row is not None and int(row.qty or 0) >= old_seed_houses:
            earned_houses = int(row.qty or 0) - old_seed_houses
            row.qty = C.starting_house_count() + earned_houses
            counts["small_house"] = int(row.qty)
    if old_population <= 0:
        initial = ("road", "power", "water", "school", "clinic", "bank", "park", "factory", "quarry")
        for btype in initial:
            if btype not in counts and C.get_building(btype):
                session.add(MafiaBuilding(city_id=city.id, btype=btype, qty=1))
                counts[btype] = 1
        if not int(counts.get("small_house", 0)):
            qty = C.starting_house_count()
            session.add(MafiaBuilding(city_id=city.id, btype="small_house", qty=qty))
            counts["small_house"] = qty
    await session.flush()
    return True


# ---------------------------------------------------------------------------
# به‌روزرسانیِ زمانی (درآمد، تولیدِ مصالح، رشدِ جمعیت)
# ---------------------------------------------------------------------------
async def tick(session, city: MafiaCity) -> dict:
    """اعمالِ گذرِ زمان: تولیدِ مصالح + رشدِ جمعیت. درآمد جداگانه جمع می‌شود."""
    now = datetime.utcnow()
    await settle_city_builds(session, city)
    counts = await _buildings(session, city.id)
    # Repair legacy professional-subordinate seed and ancient zero rows.
    await _normalize_city_population_seed(session, city, counts)
    # رضایت روزانه بر اساس نیازهای واقعی شهر محاسبه می‌شود؛ کف مصنوعی ۵۰ ندارد.
    city.satisfaction = C.satisfaction_of(counts, city.tax_rate, city.population)
    # v1.7.6.5 -- a hired mayor manages the city better
    city.satisfaction = _apply_mayor_sat(city, city.satisfaction)
    # اگر نیازها برآورده نشوند و رضایت زیر ۷۵ بیاید، شهروندان مهاجرت می‌کنند تا
    # جمعیت با زیرساخت موجود متناسب شود. جمعیت پایه هرگز کم نمی‌شود.
    if int(city.satisfaction) < C.GROWTH_MIN_SATISFACTION:
        sustainable = C.supported_population(counts, int(city.base_population or 0))
        if int(city.population) > sustainable:
            # افت تدریجی تا رسیدن به ظرفیت پایدار؛ هر بار بررسی حداقل ۵٪ فاصله کم می‌شود.
            leave = max(1, int((int(city.population) - sustainable) * 0.05))
            city.population = max(sustainable, int(city.population) - leave)
            city.satisfaction = C.satisfaction_of(counts, city.tax_rate, city.population)

    # --- تولیدِ منابع متنوع ---
    resources = _resources(city)
    if city.last_prod_at:
        hours = min(C.MAX_OFFLINE_HOURS, C.hours_between(city.last_prod_at, now))
        production = C.resource_production_per_hour(counts)
        cap = C.warehouse_capacity(city.warehouse_level)
        free = max(0, cap - C.resource_total(resources))
        # v1.7.8.5 — سقف تولید روزانه: هر واحد صنعتی حداکثر ۱٬۰۰۰ واحد در روز
        today = now.strftime("%Y-%m-%d")
        try:
            prod_today = json.loads(city.prod_today_json or "{}") if str(getattr(city, "prod_day", "") or "") == today else {}
            if not isinstance(prod_today, dict):
                prod_today = {}
        except Exception:
            prod_today = {}
        units_by_resource: dict[str, int] = {}
        for _ik, _info in C.INDUSTRY.items():
            _pr = _info.get("produce_resource")
            if _pr:
                units_by_resource[_pr] = units_by_resource.get(_pr, 0) + int(counts.get(_ik, 0))
        # v1.7.8.5 — سقف تجمیعی برای کاربران با بیش از ۴۰ واحد صنعتی (ادمین)
        total_units = sum(int(counts.get(_ik, 0)) for _ik in C.INDUSTRY)
        agg_cap = int(C.get_prod_agg_cap()) if total_units > int(C.PROD_AGG_MIN_UNITS) else 0
        total_today = int(prod_today.get("__total__", 0) or 0)
        for key in C.RESOURCE_ORDER:
            made = int(production.get(key, 0) * hours)
            daily_cap = int(C.get_prod_daily_cap()) * int(units_by_resource.get(key, 0))
            already = int(prod_today.get(key, 0) or 0)
            allowed = max(0, daily_cap - already)
            add = min(free, max(0, min(made, allowed)))
            if agg_cap:
                add = min(add, max(0, agg_cap - total_today))
            if add:
                resources[key] += add
                prod_today[key] = already + add
                total_today += add
                free -= add
            if free <= 0 or (agg_cap and total_today >= agg_cap):
                break
        prod_today["__total__"] = total_today
        city.prod_day = today
        city.prod_today_json = json.dumps(prod_today, ensure_ascii=False)
    _save_resources(city, resources)
    city.last_prod_at = now

    # --- چرخهٔ سالانهٔ بازی: هر ۳ روز واقعی = یک سال ---
    # جمعیت فقط در مرز سال رشد می‌کند. اگر رضایت زیر ۷۵ باشد، رشد متوقف است؛
    # اگر زیرساخت کم باشد، مهاجرتِ بالا انجام شده و تا سال بعد شهر پایدار می‌ماند.
    if city.last_grow_at:
        years = int(C.game_years_elapsed(city.last_grow_at, now))
        if years > 0:
            cap = C.supported_population(counts, int(city.base_population or 0))
            if int(city.satisfaction) >= C.GROWTH_MIN_SATISFACTION and int(city.population) < cap:
                # رشد محافظه‌کارانه، محدود به ظرفیت خدمات/مسکن و سقف ۲۵ میلیون.
                city.population = min(cap, C.grow_population(city.population, cap, city.satisfaction, years))
            # فقط پس از پایان سال بازی، مبنای سال بعد صفر می‌شود.
            city.last_grow_at = now
    else:
        city.last_grow_at = now
    # v1.7.6.5 -- charge the mayor salary once per game year
    await _charge_mayor_salary(session, city, now)
    return counts


async def collect_income(session, uid: int) -> tuple[bool, str]:
    """جمع‌آوریِ درآمدِ انباشته‌ی شهر و واریز به موجودی."""
    city = await get_city(session, uid)
    if not city:
        return False, "اول باید یک شهر بخری."
    counts = await tick(session, city)
    now = datetime.utcnow()
    hours = min(C.MAX_OFFLINE_HOURS, C.hours_between(city.last_income_at or now, now))
    rate = await effective_income_rate(session, counts, city.tax_rate, city.population, city.satisfaction)
    try:
        from app.services import referral_service
        rate = rate * (1 + (await referral_service.bonus_pct(session, uid)) / 100)
    except Exception:
        pass
    # v1.7.8.19 — بونس قلمروی القاب (territory_pct) روی درآمد شهر اعمال می‌شود
    try:
        from app.services import title_effects
        rate = rate * await title_effects.multiplier(session, uid, "territory_pct")
    except Exception:
        pass
    # مبلغ پایه قبل از بونس اشتراک/رویداد
    base_amount = int(rate * hours)
    from app.services.bonus_breakdown import income_breakdown, append_note
    br = await income_breakdown(session, uid, base_amount)
    amount = int(br["total"])
    city.last_income_at = now
    if amount <= 0:
        await session.commit()
        return False, "فعلاً درآمدی برای جمع‌آوری نیست."
    player = await _player(session, uid)
    player.cash = int(player.cash) + amount
    await session.commit()
    msg = f"💰 {amount:,} دلار درآمدِ شهر جمع‌آوری شد."
    return True, append_note(msg, br.get("note") or "")


# ---------------------------------------------------------------------------
# ساخت / ارتقا / تبدیل
# ---------------------------------------------------------------------------
async def _spend(session, uid: int, city: MafiaCity, cost: int, needs: dict[str, int]) -> tuple[bool, str]:
    player = await _player(session, uid)
    if not player or int(player.cash or 0) < cost:
        return False, f"پولِ کافی نداری (نیاز: {cost:,} 💵)."
    resources = _resources(city)
    missing = {key: amount - int(resources.get(key, 0)) for key, amount in needs.items() if int(resources.get(key, 0)) < amount}
    if missing:
        return False, "منابع کافی نداری: " + C.requirements_text(missing)
    player.cash = int(player.cash) - cost
    for key, amount in needs.items():
        resources[key] = int(resources.get(key, 0)) - int(amount)
    _save_resources(city, resources)
    return True, "ok"


def build_quote(btype: str, amount: int) -> dict:
    """Compatibility wrapper around the dependency-free exact quote."""
    return C.batch_build_quote(btype, amount)


async def build_plan(session, uid: int, btype: str, amount: int) -> tuple[bool, str, dict]:
    """Validate a whole batch and return an exact preview without spending."""
    normalized = C.normalize_build_amount(amount)
    if normalized is None:
        return False, f"تعداد ساخت باید بین {C.BATCH_BUILD_MIN:,} تا {C.BATCH_BUILD_MAX:,} باشد.", {}
    building = C.get_building(btype)
    if not building:
        return False, "ساختمان نامعتبر است.", {}
    city = await get_city(session, uid)
    player = await _player(session, uid)
    if not city or not player:
        return False, "اول باید یک شهر بخری.", {}

    await tick(session, city)
    counts = await _buildings(session, city.id)
    pending_rows = await pending_builds(session, city.id)
    pending_qty = sum(
        max(1, int(row.qty or 1))
        for row in pending_rows
        if row.kind == "build" and row.btype == btype
    )
    owned = int(counts.get(btype, 0))
    issues: list[str] = []

    required = building.get("requires") or ()
    if isinstance(required, str):
        required = (required,)
    missing_buildings = [req for req in required if int(counts.get(req, 0)) <= 0]
    if missing_buildings:
        issues.append("پیش‌نیاز ناقص: " + "، ".join(C.building_name(req) for req in missing_buildings))

    category = C.category_of(btype)
    cap = None
    if category == "welfare" and building.get("max_abs"):
        cap = C.welfare_cap(btype, city.population)
        available = max(0, int(cap) - owned - pending_qty)
        if normalized > available:
            issues.append(f"فقط {available:,} واحد تا سقف مجاز {cap:,} جا مانده است.")
    if category == "housing" and int(city.population or 0) >= C.POP_CAP:
        issues.append("جمعیت شهر به سقف ۲۵ میلیون رسیده و خانه‌سازی قفل است.")

    quote = build_quote(btype, normalized)
    discounted_cash, discount_pct = await _discounted_cost(session, uid, int(quote["cash"]))
    stock = _resources(city)
    missing_resources = {
        key: needed - int(stock.get(key, 0))
        for key, needed in quote["resources"].items()
        if int(stock.get(key, 0)) < needed
    }
    if int(player.cash or 0) < discounted_cash:
        issues.append(f"کمبود پول: {discounted_cash - int(player.cash or 0):,} 💵")
    if missing_resources:
        issues.append("کمبود منابع: " + C.requirements_text(missing_resources))

    plan = {
        **quote,
        "cash_before_discount": int(quote["cash"]),
        "cash": int(discounted_cash),
        "discount_pct": int(discount_pct),
        "owned": owned,
        "pending": pending_qty,
        "after_ready": owned + pending_qty + normalized,
        "cap": cap,
        "stock": stock,
        "issues": issues,
    }
    return not issues, "\n".join(issues) if issues else "ok", plan


def build_plan_text(plan: dict, ready: bool) -> str:
    if not plan:
        return "پیش‌فاکتور ساخت در دسترس نیست."
    raw = int(plan.get("cash_before_discount", 0))
    final = int(plan.get("cash", 0))
    discount = int(plan.get("discount_pct", 0))
    cost_text = f"{raw:,} → <b>{final:,}</b>"
    if discount:
        cost_text += f" (تخفیف {discount}٪)"
    lines = [
        "🧾 <b>پیش‌فاکتور ساخت‌وساز</b>", "",
        f"🏗️ ساختمان: <b>{C.building_name(plan['btype'])}</b>",
        f"🔢 تعداد: <b>{int(plan['amount']):,}</b>",
        f"📊 موجود / در صف / پس از تکمیل: {int(plan['owned']):,} / {int(plan['pending']):,} / <b>{int(plan['after_ready']):,}</b>",
        f"💵 هزینه: {cost_text}",
        f"📦 منابع: {C.requirements_text(plan.get('resources') or {})}",
        f"⏱️ زمان دسته: <b>{C.fmt_duration(int(plan.get('seconds', 0)))}</b> (ساخت هم‌زمان)",
    ]
    if plan.get("cap") is not None:
        lines.append(f"🚧 سقف این ساختمان: {int(plan['cap']):,}")
    lines += ["", "✅ آمادهٔ تأیید و پرداخت است." if ready else "⚠️ این درخواست فعلاً قابل اجرا نیست:"]
    if not ready:
        lines.extend(f"• {issue}" for issue in plan.get("issues") or ["شرایط ساخت کامل نیست."])
    return "\n".join(lines)


async def build_many(session, uid: int, btype: str, amount: int) -> tuple[bool, str]:
    """Pay once and enqueue one atomic queue row carrying N simultaneous units."""
    ready, message, plan = await build_plan(session, uid, btype, amount)
    if not ready:
        return False, message
    city = await get_city(session, uid)
    ok, spend_message = await _spend(session, uid, city, int(plan["cash"]), dict(plan["resources"]))
    if not ok:
        return False, spend_message
    now = datetime.utcnow()
    session.add(CityBuildQueue(
        city_id=city.id,
        btype=btype,
        kind="build",
        qty=int(plan["amount"]),
        started_at=now,
        ready_at=now + timedelta(seconds=int(plan["seconds"])),
    ))
    await session.commit()
    note = f" با تخفیف {int(plan['discount_pct'])}٪" if int(plan["discount_pct"]) else ""
    return True, (
        f"✅ ساخت {int(plan['amount']):,} واحد «{C.building_name(btype)}»{note} شروع شد. "
        f"همه در {C.fmt_duration(int(plan['seconds']))} آماده می‌شوند."
    )


async def build(session, uid: int, btype: str) -> tuple[bool, str]:
    """Backward-compatible one-unit build through the atomic batch engine."""
    return await build_many(session, uid, btype, 1)

async def upgrade(session, uid: int, btype: str) -> tuple[bool, str]:
    """ارتقایِ سطحِ زیرساخت/صنعت."""
    city = await get_city(session, uid)
    if not city:
        return False, "اول باید یک شهر بخری."
    cat = C.category_of(btype)
    if cat not in ("infra", "industry"):
        return False, "این ساختمان سطح‌محور نیست."
    row = await _get_row(session, city.id, btype)
    if not row:
        return False, "اول باید بسازیش."
    if int(row.qty) >= C.max_level_of(btype):
        return False, "به بالاترین سطح رسیده."
    await tick(session, city)
    cost = C.upgrade_cost(btype, int(row.qty))
    cost, disc = await _discounted_cost(session, uid, cost)
    ok, msg = await _spend(session, uid, city, cost, C.material_requirements(btype))
    if not ok:
        return False, msg
    now = datetime.utcnow()
    sec = C.build_seconds_for_cost(cost)
    session.add(CityBuildQueue(
        city_id=city.id, btype=btype, kind="upgrade", qty=1,
        started_at=now, ready_at=now + timedelta(seconds=sec),
    ))
    await session.commit()
    note = f" (با تخفیف اشتراک −{disc}٪)" if disc else ""
    txt = f"🏗️ ارتقای «{C.building_name(btype)}» به سطح {int(row.qty) + 1} شروع شد{note}." + chr(10)
    txt += f"⏱️ آماده می‌شود در: <b>{C.fmt_duration(sec)}</b>"
    return True, txt


async def convert_housing(session, uid: int, btype: str) -> tuple[bool, str]:
    """تبدیلِ ۵ واحدِ یک رده به ۱ واحدِ رده‌ی بالاتر."""
    city = await get_city(session, uid)
    if not city:
        return False, "اول باید یک شهر بخری."
    info = C.get_building(btype)
    if not info:
        return False, "ساختمان نامعتبر است."
    nxt = info.get("next")
    if not nxt:
        return False, "این ساختمان گزینه تبدیل به رده بالاتر ندارد."
    row = await _get_row(session, city.id, btype)
    if not row or int(row.qty) < C.CONVERT_RATIO:
        return False, f"حداقل {C.CONVERT_RATIO} واحدِ «{C.building_name(btype)}» لازم است."
    row.qty = int(row.qty) - C.CONVERT_RATIO
    up = await _get_row(session, city.id, nxt)
    if up:
        up.qty = int(up.qty) + 1
    else:
        session.add(MafiaBuilding(city_id=city.id, btype=nxt, qty=1))
    await session.commit()
    return True, f"♻️ {C.CONVERT_RATIO} «{C.building_name(btype)}» → ۱ «{C.building_name(nxt)}»."


async def upgrade_warehouse(session, uid: int) -> tuple[bool, str]:
    city = await get_city(session, uid)
    if not city:
        return False, "اول باید یک شهر بخری."
    if int(city.warehouse_level) >= C.WAREHOUSE_MAX_LEVEL:
        return False, "انبار در بالاترین سطح است."
    cost = C.warehouse_upgrade_cost(int(city.warehouse_level))
    cost, disc = await _discounted_cost(session, uid, cost)
    ok, msg = await _spend(session, uid, city, cost, {})
    if not ok:
        return False, msg
    now = datetime.utcnow()
    sec = C.build_seconds_for_cost(cost)
    session.add(CityBuildQueue(
        city_id=city.id, btype="warehouse", kind="warehouse", qty=1,
        started_at=now, ready_at=now + timedelta(seconds=sec),
    ))
    await session.commit()
    note = f" (با تخفیف اشتراک −{disc}٪)" if disc else ""
    txt = f"🏗️ ارتقای انبار به سطح {int(city.warehouse_level) + 1} شروع شد{note}." + chr(10)
    txt += f"⏱️ {C.fmt_duration(sec)} — ظرفیت جدید: "
    txt += f"{C.warehouse_capacity(int(city.warehouse_level) + 1):,} {C.MATERIAL_LABEL}"
    return True, txt


async def set_tax(session, uid: int, rate: int) -> tuple[bool, str]:
    city = await get_city(session, uid)
    if not city:
        return False, "اول باید یک شهر بخری."
    rate = max(C.TAX_MIN, min(C.TAX_MAX, int(rate)))
    await tick(session, city)
    city.tax_rate = rate
    city.satisfaction = C.satisfaction_of(await _buildings(session, city.id), rate, city.population)
    city.satisfaction = _apply_mayor_sat(city, city.satisfaction)
    await session.commit()
    return True, f"🧾 نرخِ مالیات روی {rate}٪ تنظیم شد."


async def rename_city(session, uid: int, name: str) -> tuple[bool, str]:
    city = await get_city(session, uid)
    if not city:
        return False, "اول باید یک شهر بخری."
    city.name = (name or city.name)[:64]
    await session.commit()
    return True, f"✏️ نامِ شهر به «{city.name}» تغییر یافت."


# ---------------------------------------------------------------------------
# APIِ سازگار برای سرویس‌های وابسته
# ---------------------------------------------------------------------------

async def refresh_city_balance_settings(session) -> dict:
    """ضریب‌های اقتصاد شهر را از GameNumberSetting بخوان و کش runtime را به‌روز کن."""
    cost = C.DEFAULT_COST_MULT
    inc_div = C.DEFAULT_INCOME_DIV
    res_m = C.DEFAULT_RESOURCE_PRICE_MULT
    lvl_m = C.DEFAULT_LEVEL_MULT
    try:
        row = await session.get(GameNumberSetting, C.CITY_COST_MULT_KEY)
        if row and row.value not in (None, ""):
            cost = float(str(row.value).strip())
    except Exception:
        pass
    try:
        row = await session.get(GameNumberSetting, C.CITY_INCOME_DIV_KEY)
        if row and row.value not in (None, ""):
            inc_div = float(str(row.value).strip())
    except Exception:
        pass
    try:
        row = await session.get(GameNumberSetting, C.CITY_RESOURCE_PRICE_MULT_KEY)
        if row and row.value not in (None, ""):
            res_m = float(str(row.value).strip())
    except Exception:
        pass
    try:
        row = await session.get(GameNumberSetting, C.CITY_LEVEL_MULT_KEY)
        if row and row.value not in (None, ""):
            lvl_m = float(str(row.value).strip())
    except Exception:
        pass
    try:
        row = await session.get(GameNumberSetting, C.PROD_DAILY_CAP_KEY)
        if row and row.value not in (None, ""):
            C.set_prod_daily_cap(float(str(row.value).strip()))
    except Exception:
        pass
    try:
        row = await session.get(GameNumberSetting, C.PROD_AGG_CAP_KEY)
        if row and row.value not in (None, ""):
            C.set_prod_agg_cap(float(str(row.value).strip()))
    except Exception:
        pass
    C.set_runtime_balance(cost_mult=cost, income_div=inc_div, resource_price_mult=res_m, level_mult=lvl_m)

    return C.balance_snapshot()


async def save_city_balance_setting(session, key: str, value: float, admin_id: int | None = None) -> dict:
    """یک ضریب را ذخیره و کش را رفرش کن."""
    allowed = {
        C.CITY_COST_MULT_KEY,
        C.CITY_INCOME_DIV_KEY,
        C.CITY_RESOURCE_PRICE_MULT_KEY,
        C.CITY_LEVEL_MULT_KEY,
    }
    if key not in allowed:
        raise ValueError("invalid key")
    val = float(value)
    if key == C.CITY_INCOME_DIV_KEY:
        val = max(0.01, val)
    elif key == C.CITY_LEVEL_MULT_KEY:
        val = max(1.0, val)
    else:
        val = max(0.01, val)
    row = await session.get(GameNumberSetting, key)
    labels = {
        C.CITY_COST_MULT_KEY: "ضریب هزینه ساخت شهر",
        C.CITY_INCOME_DIV_KEY: "مقسوم‌علیه درآمد لول‌دار شهر",
        C.CITY_RESOURCE_PRICE_MULT_KEY: "ضریب قیمت منابع شهر",
        C.CITY_LEVEL_MULT_KEY: "ضریب سقف لول شهر",
    }
    if row is None:
        row = GameNumberSetting(key=key, value=str(val), label=labels.get(key), updated_by=admin_id)
        session.add(row)
    else:
        row.value = str(val)
        row.label = labels.get(key)
        if admin_id is not None:
            row.updated_by = admin_id
    await session.commit()
    return await refresh_city_balance_settings(session)

async def hourly_income_cap(session) -> int:
    row = await session.get(GameNumberSetting, "city.hourly_income_cap")
    try:
        return max(0, int(float(row.value))) if row and row.value is not None else C.CITY_HOURLY_INCOME_CAP
    except (TypeError, ValueError):
        return C.CITY_HOURLY_INCOME_CAP


async def effective_income_rate(session, counts, tax_rate: int, population: int, satisfaction: int) -> int:
    return min(await hourly_income_cap(session), C.income_rate_per_hour(counts, tax_rate, population, satisfaction))


async def city_hourly_income(session, uid: int) -> int:
    """درآمدِ ساعتیِ شهر (جایگزینِ _city_country_hourly_incomeِ قدیم)."""
    city = await get_city(session, uid)
    if not city:
        return 0
    counts = await _buildings(session, city.id)
    sat = C.satisfaction_of(counts, city.tax_rate, city.population)
    rate = await effective_income_rate(session, counts, city.tax_rate, city.population, sat)
    # v1.7.8.19 — بونس قلمروی القاب در نمایش درآمد ساعتی هم لحاظ شود
    try:
        from app.services import title_effects
        rate = int(rate * await title_effects.multiplier(session, uid, "territory_pct"))
    except Exception:
        pass
    return rate


async def daily_income(session, uid: int) -> int:
    return int(await city_hourly_income(session, uid)) * 24


async def total_population(session, uid: int) -> int:
    city = await get_city(session, uid)
    return int(city.population) if city else 0


async def city_count(session, uid: int) -> int:
    """۰ یا ۱ (تک‌شهری)."""
    return 1 if await get_city(session, uid) else 0


async def city_value(session, uid: int) -> int:
    """ارزشِ تقریبیِ شهر (برای worldbank/رتبه‌بندی)."""
    city = await get_city(session, uid)
    if not city:
        return 0
    counts = await _buildings(session, city.id)
    value = int(city.purchase_price or 0)
    for btype, qty in counts.items():
        value += C.build_cost(btype) * int(qty)
    value += int(city.population) * 20      # ارزشِ سرانه‌ی جمعیت
    return value


async def active_city(session, uid: int) -> MafiaCity | None:
    """شهرِ فعالِ بازیکن (برای sports/fan context)."""
    return await get_city(session, uid)


async def city_name(session, uid: int) -> str | None:
    city = await get_city(session, uid)
    return city.name if city else None


# ---------------------------------------------------------------------------
# متنِ وضعیتِ شهر (برای هندلر)
# ---------------------------------------------------------------------------
async def city_detail_text(session, uid: int, detail: str) -> str:
    city = await get_city(session, uid)
    if not city:
        return "اول باید یک شهر بخری."
    counts = await tick(session, city)
    await session.commit()
    if detail == "needs":
        needs = C.citizen_needs(counts, city.population)
        return ("👥 <b>نیازها و رضایت شهروندان</b>\n"
                f"😊 رضایت: {city.satisfaction}٪\n"
                f"👥 جمعیت: {int(city.population):,}\n"
                f"🏗️ جمعیت قابل پشتیبانی: {C.supported_population(counts, int(city.base_population or 0)):,}\n\n"
                + ("⚠️ نیازهای برآورده‌نشده:\n• " + "\n• ".join(C.citizen_needs(counts, city.population)) if needs else "✅ نیازهای اصلی شهروندان تأمین است."))
    if detail == "services":
        util = C.utility_report(counts, city.population)
        items = [f"{C.UTILITY_LABEL[u]}: {util[u]['produce']:,}/{util[u]['need']:,}" for u in C.UTILITIES]
        for key in ("road", "hospital", "clinic", "school", "university", "bank", "park", "amusement", "police", "fire"):
            if C.get_building(key): items.append(f"{C.building_name(key)}: {int(counts.get(key, 0))}")
        return "🏗️ <b>زیرساخت و خدمات شهر</b>\n\n" + "\n".join(items)
    if detail == "production":
        capacity = C.city_production_capacity(counts); consumed = C.city_production_consumption(counts)
        lines = [f"{key}: تولید {capacity[key]:,} | مصرف {consumed[key]:,} | مازاد {capacity[key]-consumed[key]:,}" for key in capacity]
        return "🏭 <b>توان تولید و مصرف صنایع</b>\n(توان‌ها قابل برداشت نیستند و در ساختمان‌های وابسته مصرف می‌شوند.)\n\n" + "\n".join(lines)
    return await status_text(session, uid)


async def status_text(session, uid: int) -> str:
    city = await get_city(session, uid)
    if not city:
        return ("🏙️ هنوز شهری نداری.\n"
                f"برای خرید شهر به لول {C.CITY_MIN_LEVEL} و {C.CITY_COST:,} 💵 نیاز داری.")
    counts = await tick(session, city)
    await session.commit()
    rate = await effective_income_rate(session, counts, city.tax_rate, city.population, city.satisfaction)
    try:
        _parts = C.income_breakdown_parts(counts, city.tax_rate, int(city.population or 0), int(city.satisfaction or 0))
        tax_part, com_part = int(_parts["tax"]), int(_parts["commerce"])
    except Exception:
        tax_part, com_part = int(rate), 0
    founded = getattr(city, "founded_at", None) or city.last_grow_at
    try:
        cal_txt = C.game_calendar_text(founded) + "\n"
    except Exception:
        cal_txt = ""
    try:
        blocker = C.growth_blocker(
            counts, int(city.population or 0), int(city.satisfaction or 0), int(city.base_population or 0)
        )
        if blocker is None:
            grow_line = f"🌱 رشد: <b>فعال</b> (رضایت ≥ {C.GROWTH_MIN_SATISFACTION}٪ + ظرفیت)"
        elif blocker == "satisfaction":
            grow_line = f"🌱 رشد: <b>متوقف</b> — رضایت زیر {C.GROWTH_MIN_SATISFACTION}٪"
        elif blocker == "housing":
            grow_line = "🌱 رشد: <b>متوقف</b> — کمبود مسکن/خانه"
        else:
            grow_line = f"🌱 رشد: <b>متوقف</b> — ظرفیت خدمات ({blocker})"
    except Exception:
        grow_line = f"🌱 رشد: نیاز به رضایت ≥ {C.GROWTH_MIN_SATISFACTION}٪ + خانه و ظرفیت"
    cap = C.supported_population(counts, int(city.base_population or 0))
    return (
        f"🏙️ <b>شهر «{city.name}»</b>\n"
        + cal_txt
        + f"👥 جمعیت: {int(city.population):,} / ظرفیت {cap:,} نفر\n"
        + f"😊 رضایت: {city.satisfaction}٪ | 🧾 مالیات: {city.tax_rate}٪\n"
        + f"{grow_line}\n"
        + f"💰 درآمد ساعتی: {rate:,} 💵\n"
        + f"📦 انبار: {C.resource_total(_resources(city)):,}/{C.warehouse_capacity(city.warehouse_level):,}\n\n"
        + "جزئیات نیازها، خدمات و توان صنایع را از دکمه‌های زیر ببین."
    )


async def buildings_summary(session, uid: int) -> dict[str, int]:
    city = await get_city(session, uid)
    if not city:
        return {}
    await settle_city_builds(session, city)
    return await _buildings(session, city.id)

async def get_player(session, uid: int) -> Player | None:
    """بازیکن را با شناسهٔ تلگرام برمی‌گرداند."""
    res = await session.execute(select(Player).where(Player.tg_user_id == int(uid)))
    return res.scalar_one_or_none()


async def sell_resource(session, uid: int, resource_key: str, amount: int) -> tuple[bool, str]:
    """فروش منابع انبار شهر با ۵۰٪ قیمت خرید لحظه‌ای (v1.7.7)."""
    city = await get_city(session, uid)
    player = await get_player(session, uid)
    if not city or not player or resource_key not in C.RESOURCES or int(amount) <= 0:
        return False, "درخواست فروش نامعتبر است."
    stock = _resources(city)
    amount = int(amount)
    if int(stock.get(resource_key, 0)) < amount:
        return False, "موجودی این منبع در انبار کافی نیست."
    unit = max(1, int(C.resource_sell_price(resource_key)))
    stock[resource_key] -= amount
    _save_resources(city, stock)
    player.cash += unit * amount
    await session.commit()
    return True, f"✅ {amount:,} واحد {C.resource_name(resource_key)} به مبلغ {unit * amount:,}$ فروخته شد."



# ---------------------------------------------------------------------------
# v1.7.6.5 -- استخدامِ شهردار و گزارشِ مردم
# ---------------------------------------------------------------------------
async def mayor_of(session, uid: int):
    """کلیدِ شهردارِ استخدام‌شده یا None."""
    city = await get_city(session, uid)
    if not city:
        return None
    return getattr(city, "mayor_key", None) or None


async def hire_mayor(session, uid: int, key: str) -> tuple[bool, str]:
    """استخدامِ شهردار؛ هزینهٔ یک‌باره از موجودی کم می‌شود."""
    city = await get_city(session, uid)
    if not city:
        return False, "اول باید یک شهر بخری."
    info = MY.get_mayor(key)
    if not info:
        return False, "این ردهٔ شهردار وجود ندارد."
    current = getattr(city, "mayor_key", None)
    if current == key:
        return False, "همین شهردار الان سرِ کار است."
    cost = int(MY.hire_cost(key))
    ok, msg = await _spend(session, uid, city, cost, {})
    if not ok:
        return False, msg
    now = datetime.utcnow()
    city.mayor_key = str(key)
    city.mayor_hired_at = now
    city.last_mayor_msg_at = now
    city.mayor_paid_at = now
    await session.commit()
    return True, (
        "🏛️ <b>%s</b> استخدام شد.\n"
        "💰 هزینهٔ استخدام: <b>%s$</b>\n"
        "🧾 حقوقِ سالانه: <b>%s$</b>\n"
        "📨 گزارش در هر سالِ بازی: <b>%d</b>\n"
        "😊 افزایشِ رضایت: <b>+%d٪</b>"
        % (
            info["name"],
            "{:,}".format(cost),
            "{:,}".format(int(info["salary"])),
            int(info["reports"]),
            int(info["sat_bonus"]),
        )
    )


async def fire_mayor(session, uid: int) -> tuple[bool, str]:
    """اخراجِ شهردار؛ هیچ مبلغی باز نمی‌گردد."""
    city = await get_city(session, uid)
    if not city:
        return False, "اول باید یک شهر بخری."
    key = getattr(city, "mayor_key", None)
    if not key:
        return False, "شهرداری استخدام نشده است."
    name = MY.mayor_name(key)
    city.mayor_key = None
    city.mayor_hired_at = None
    city.last_mayor_msg_at = None
    city.mayor_paid_at = None
    await session.commit()
    return True, "👋 <b>%s</b> اخراج شد. دیگر گزارشی از مردم نمی‌رسد." % name


async def mayor_panel_text(session, uid: int) -> str:
    """متنِ پنلِ شهرداری."""
    city = await get_city(session, uid)
    if not city:
        return "اول باید یک شهر بخری."
    key = getattr(city, "mayor_key", None)
    if not key:
        return MY.options_text() + "\n\n⚪ الان شهرداری نداری؛ مردم صدایشان به تو نمی‌رسد."
    info = MY.get_mayor(key) or {}
    counts = await _buildings(session, city.id)
    nxt = mayor_next_report_text(city)
    lines = [
        "🏛️ <b>شهرداریِ %s</b>" % (city.name or "شهر"),
        "",
        "👤 شهردار: <b>%s</b>" % info.get("name", key),
        "🧾 حقوقِ سالانه: <b>%s$</b>" % "{:,}".format(int(MY.salary(key))),
        "📨 گزارش در سال: <b>%d</b>" % int(MY.reports_per_year(key)),
        "😊 افزایشِ رضایت: <b>+%d٪</b>" % int(MY.sat_bonus(key)),
        "⏳ گزارشِ بعدی: <b>%s</b>" % nxt,
        "",
        "📊 <b>وضعیتِ امروزِ شهر</b>",
        "😊 رضایت: <b>%d٪</b>" % int(city.satisfaction or 0),
        "👥 جمعیت: <b>%s</b>" % "{:,}".format(int(city.population or 0)),
    ]
    lines.append(citizen_report_text(counts, city))
    return "\n".join(lines)


def mayor_next_report_text(city) -> str:
    """فاصلهٔ باقی‌مانده تا گزارشِ بعدیِ شهردار."""
    key = getattr(city, "mayor_key", None)
    if not key:
        return "—"
    every = MY.report_interval_hours(key, C.GAME_YEAR_REAL_DAYS)
    if every <= 0:
        return "—"
    last = getattr(city, "last_mayor_msg_at", None) or getattr(city, "mayor_hired_at", None)
    if not last:
        return "به‌زودی"
    try:
        passed = (datetime.utcnow() - last).total_seconds() / 3600.0
    except Exception:
        return "به‌زودی"
    left = every - passed
    if left <= 0:
        return "به‌زودی"
    hours = int(left)
    mins = int((left - hours) * 60)
    if hours <= 0:
        return "%d دقیقه" % max(1, mins)
    return "%d ساعت و %d دقیقه" % (hours, mins)


def citizen_report_text(counts, city) -> str:
    """خواستهٔ مردم با عمقی که ردهٔ شهردار اجازه می‌دهد."""
    key = getattr(city, "mayor_key", None)
    depth = MY.detail_level(key)
    if depth <= 0:
        return ""
    population = int(city.population or 0)
    sat = int(city.satisfaction or 0)
    out = [""]
    if depth >= 2:
        needs = C.citizen_needs(counts, population)
        if needs:
            out.append("⚠️ <b>خواستهٔ مردم</b>")
            for item in needs[:6]:
                out.append("• %s" % item)
        else:
            out.append("✅ مردم از خدماتِ فعلی راضی‌اند.")
    if depth >= 3:
        blocker = C.growth_blocker(
            counts, population, sat, int(getattr(city, "base_population", 0) or 0)
        )
        out.append("")
        out.append("📈 <b>تحلیلِ رشدِ جمعیت</b>")
        out.append(growth_blocker_text(blocker, counts, population))
    return "\n".join(out)


def growth_blocker_text(blocker, counts=None, population: int = 0) -> str:
    """ترجمهٔ فارسیِ دلیلِ توقفِ رشدِ جمعیت."""
    if blocker is None:
        return (
            "✅ همه‌چیز مرتب است — سرِ سالِ بعدِ بازی جمعیت زیاد می‌شود."
        )
    if blocker == "satisfaction":
        return (
            "⛔ رضایت زیرِ %d٪ است؛ تا بالا نرود جمعیت رشد نمی‌کند.\n"
            "   مالیات را کم کن یا پارک، مدرسه، درمانگاه و برق/آب بساز."
            % C.GROWTH_MIN_SATISFACTION
        )
    if blocker == "housing":
        return (
            "⛔ جایِ سکونت تمام شده — خانه، آپارتمان یا برجِ تازه بساز."
        )
    labels = {
        "electricity": "⚡ کمبودِ برق — نیروگاهِ تازه بساز.",
        "water": "💧 کمبودِ آب — تأسیساتِ آب بساز.",
        "road": "🛣️ جاده‌ها پرِ ترافیک است — جادهٔ تازه بساز.",
        "health": "🏥 کمبودِ درمان — درمانگاه یا بیمارستان بساز.",
        "education": "🏫 کمبودِ مدرسه — مدرسه یا دانشگاه بساز.",
        "leisure": "🎡 مردم تفریح می‌خواهند — پارک یا شهربازی بساز.",
        "finance": "🏦 خدماتِ بانکی کم است — بانکِ تازه بساز.",
    }
    return "⛔ " + labels.get(str(blocker), "یکی از خدماتِ شهر به سقف رسیده است.")


def mayor_report_body(city, counts) -> str:
    """متنِ پیامی که شهردار در طولِ سال می‌فرستد."""
    key = getattr(city, "mayor_key", None)
    info = MY.get_mayor(key) or {}
    sat = int(city.satisfaction or 0)
    population = int(city.population or 0)
    cname = getattr(city, "name", None) or "شهر"
    if sat >= 85:
        mood = "😊 مردم خوشحالند و از تو تعریف می‌کنند."
    elif sat >= C.GROWTH_MIN_SATISFACTION:
        mood = "🙂 مردم راضی‌اند؛ شهر در مسیرِ رشد است."
    elif sat >= 50:
        mood = "😐 مردم گله دارند و خدماتِ بهتر می‌خواهند."
    elif sat >= 30:
        mood = "😟 نارضایتی جدی است؛ مردم دارند مهاجرت می‌کنند."
    else:
        mood = "😡 شهر در بحران است! هر لحظه جمعیت کم می‌شود."
    lines = [
        "📢 <b>پیامِ مردمِ %s</b>" % cname,
        "🏛️ از طرفِ %s" % info.get("name", "شهردار"),
        "",
        mood,
        "😊 رضایت: <b>%d٪</b> · 👥 جمعیت: <b>%s</b>"
        % (sat, "{:,}".format(population)),
    ]
    body = citizen_report_text(counts, city)
    if body:
        lines.append(body)
    return "\n".join(lines)


def _apply_mayor_sat(city, sat) -> int:
    """v1.7.6.5 -- add the hired mayor bonus and clamp to the legal range."""
    bonus = MY.sat_bonus(getattr(city, "mayor_key", None))
    value = int(sat or 0)
    if not bonus:
        return value
    return max(C.SAT_MIN, min(C.SAT_MAX, value + int(bonus)))


async def _charge_mayor_salary(session, city, now=None) -> int:
    """v1.7.6.5 -- deduct the salary once per game year; fire on non-payment."""
    key = getattr(city, "mayor_key", None)
    if not key:
        return 0
    now = now or datetime.utcnow()
    last = getattr(city, "mayor_paid_at", None) or getattr(city, "mayor_hired_at", None)
    if last is None:
        city.mayor_paid_at = now
        return 0
    if int(C.game_years_elapsed(last, now)) <= 0:
        return 0
    salary = int(MY.salary(key))
    player = await _player(session, int(city.tg_user_id))
    if player is None:
        return 0
    if int(getattr(player, 'cash', 0) or 0) < salary:
        # cannot pay -> the mayor walks out
        city.mayor_key = None
        city.mayor_hired_at = None
        city.last_mayor_msg_at = None
        city.mayor_paid_at = None
        return -1
    player.cash = int(player.cash) - salary
    city.mayor_paid_at = now
    return salary


async def complete_all_builds(session, uid: int) -> int:
    """ادمین — تکمیل فوری همهٔ ساخت‌وسازهای در جریان شهرِ کاربر (v1.7.8.5)."""
    city = await get_city(session, uid)
    if not city:
        return 0
    rows = (await session.execute(
        select(CityBuildQueue).where(CityBuildQueue.city_id == int(city.id))
    )).scalars().all()
    now = datetime.utcnow()
    for q in rows:
        q.ready_at = now
    await session.flush()
    done = await settle_city_builds(session, city)
    await session.commit()
    return len(done)
