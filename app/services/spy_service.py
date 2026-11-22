# app/services/spy_service.py
"""توابعِ مشترکِ جاسوسی که هم هندلرها و هم تیکر (حلقهٔ پس‌زمینه)
از آن‌ها استفاده می‌کنند: محاسبهٔ درآمدِ روزانه، جمع‌آوریِ اطلاعات،
و تبدیلِ آیدی/یوزرنیم به کاربرِ هدف.
"""
from __future__ import annotations

from sqlalchemy import func, select

from app.data.economy import INCOME_PER_SUB_PER_HOUR, effective_subs
from app.data.estates import aggregate_effects
from app.models.mafia_city import MafiaCity  # 🆕 بچ ۴ — شهرسازِ جدید
from app.models.contact import Contact
from app.models.estate import Estate
from app.models.factory import Factory
from app.models.player import Player
from app.models.professional import OwnedProfessional


def _military_keys() -> set:
    """کلیدِ حرفه‌ای‌هایِ گروهِ نظامی را از کاتالوگ می‌خواند."""
    try:
        from app.data.professionals import PROFESSIONALS
        return {k for k, v in PROFESSIONALS.items() if v.get("group") == "military"}
    except Exception:
        return {"bodyguard", "mercenary", "sniper", "enforcer"}


_MILITARY_PREFIXES = _military_keys()


async def get_player(session, tg_user_id: int) -> Player | None:
    result = await session.execute(select(Player).where(Player.tg_user_id == tg_user_id))
    return result.scalar_one_or_none()


async def daily_income(session, tg_user_id: int) -> int:
    """درآمدِ روزانهٔ تخمینی = مجموعِ زیردستانِ حرفه‌ای‌ها × نرخِ ساعتی × ۲۴."""
    profs = (await session.execute(
        select(OwnedProfessional).where(OwnedProfessional.tg_user_id == tg_user_id)
    )).scalars().all()
    subs = sum(effective_subs(p) for p in profs)
    return int(subs * INCOME_PER_SUB_PER_HOUR * 24)


async def _count(session, model, tg_user_id: int) -> int:
    return int((await session.execute(
        select(func.count()).select_from(model).where(model.tg_user_id == tg_user_id)
    )).scalar() or 0)


async def estate_power(session, tg_user_id: int) -> int:
    """قدرتِ تقریبی بر اساسِ افکتِ حمله/دفاعِ عمارت‌ها + تعدادِ نیروی نظامی."""
    estates = (await session.execute(
        select(Estate).where(Estate.tg_user_id == tg_user_id)
    )).scalars().all()
    totals = aggregate_effects([(e.role_key, e.level) for e in estates])
    combat = totals.get("attack_pct", 0.0) + totals.get("defense_pct", 0.0)
    return int(combat * 100) + len(estates) * 5


async def military_count(session, tg_user_id: int) -> int:
    """تعداد کل نیروهای نظامی واقعی (ارتش) + حرفه‌ای نظامی."""
    total = 0
    try:
        from app.services import military_service

        stacks = await military_service.army_stacks(session, tg_user_id)
        total += sum(int(c or 0) for _k, c, _lv in stacks)
    except Exception:
        pass
    profs = (await session.execute(
        select(OwnedProfessional).where(OwnedProfessional.tg_user_id == tg_user_id)
    )).scalars().all()
    total += sum(1 for p in profs if p.prof_key in _MILITARY_PREFIXES)
    return int(total)


async def army_composition(session, tg_user_id: int) -> dict:
    """🆕 v1.7.5 — ترکیب نیروهای نظامی هدف (بر اساس دسته + نمونه واحدها)."""
    from app.data import military as MD

    try:
        from app.services import military_service

        stacks = await military_service.army_stacks(session, tg_user_id)
    except Exception:
        stacks = []
    by_cat: dict[str, int] = {}
    top: list[tuple[int, str, int, int]] = []  # power, name, count, level
    total = 0
    power = 0
    for key, count, level in stacks:
        u = MD.get_unit(key) or {}
        c = int(count or 0)
        if c <= 0:
            continue
        cat = u.get("cat") or "unknown"
        by_cat[cat] = by_cat.get(cat, 0) + c
        total += c
        pw = int(MD.unit_power(key, c, int(level or 0)))
        power += pw
        top.append((pw, u.get("name", key), c, int(level or 0)))
    top.sort(reverse=True)
    return {
        "total": total,
        "power": power,
        "by_cat": by_cat,
        "top": top[:6],
    }


async def owner_capture_reduction(session, owner_id: int) -> float:
    """کاهشِ احتمالِ دستگیری (واحدِ درصد) از عمارت‌های جاسوسیِ صاحب.

    Ombra (spy_pct) و Senato (risk_pct) هر دو احتمالِ دستگیری را پایین می‌آورند.
    """
    estates = (await session.execute(
        select(Estate).where(Estate.tg_user_id == owner_id)
    )).scalars().all()
    totals = aggregate_effects([(e.role_key, e.level) for e in estates])
    base = totals.get("spy_pct", 0.0) * 30 + totals.get("risk_pct", 0.0) * 50
    # 🆕 مرحله ۳۰ — لقب‌هایِ جاسوسی هم دستگیری را کم می‌کنند
    try:
        from app.services import title_effects
        base += (await title_effects.pct(session, owner_id, "spy_pct")) * 0.5
    except Exception:
        pass
    return base


async def owner_accuracy_bonus(session, owner_id: int) -> float:
    """افزایشِ دقتِ گزارش (کسری) از عمارتِ Ombra."""
    estates = (await session.execute(
        select(Estate).where(Estate.tg_user_id == owner_id)
    )).scalars().all()
    totals = aggregate_effects([(e.role_key, e.level) for e in estates])
    acc = totals.get("spy_pct", 0.0)
    # 🆕 مرحله ۳۰ — دقّتِ گزارش با لقب‌هایِ جاسوسی بالا می‌رود
    try:
        from app.services import title_effects
        acc += (await title_effects.pct(session, owner_id, "spy_pct")) / 100.0
    except Exception:
        pass
    return acc


async def gather_intel(session, target_id: int) -> dict:
    """اطلاعاتِ خامِ یک هدف را جمع می‌کند."""
    player = await get_player(session, target_id)
    cities = (await session.execute(
        select(MafiaCity).where(MafiaCity.tg_user_id == target_id)
    )).scalars().all()
    active_city = cities[0] if cities else None
    # قدرت رزمی واقعی اگر ممکن باشد
    combat = 0
    try:
        from app.services import war_service

        combat = int(await war_service.compute_combat_power(session, target_id))
    except Exception:
        combat = await estate_power(session, target_id)
    army = await army_composition(session, target_id)
    return {
        "name": player.name if player else str(target_id),
        "level": int(getattr(player, "level", 1) or 1) if player else 1,
        "country": active_city.name if active_city else "—",
        "cities": len(cities),
        "cash": player.cash if player else 0,
        "daily_income": await daily_income(session, target_id),
        "estates": await _count(session, Estate, target_id),
        "factories": await _count(session, Factory, target_id),
        "power": combat,
        "weapons": int(army.get("total") or 0),
        "army_power": int(army.get("power") or 0),
        "army_by_cat": dict(army.get("by_cat") or {}),
        "army_top": list(army.get("top") or []),
    }


def _fuzz(value: int, accuracy: float) -> str:
    """عدد را برحسبِ دقت دقیق یا بازه‌ای نشان می‌دهد."""
    if accuracy >= 0.99 or value == 0:
        return f"{value:,}"
    spread = int(abs(value) * (1 - accuracy))
    lo = max(0, value - spread)
    hi = value + spread
    return f"~{lo:,} تا {hi:,}"


def format_intel(intel: dict, accuracy: float) -> str:
    """گزارشِ خوانا — با دقتِ پایین مقادیر تقریبی می‌شوند.

    🆕 v1.7.5: ترکیب نیروهای نظامی هدف هم گزارش می‌شود.
    """
    from app.data import military as MD

    tag = "🎛️ دقیق" if accuracy >= 0.99 else f"🎛️ دقت: {accuracy * 100:.0f}٪ (تقریبی)"
    lines = [
        f"🔍 <b>گزارشِ جاسوسی — {intel['name']}</b>",
        f"{tag}",
        "",
        f"🎚️ سطح بازیکن: <b>{int(intel.get('level') or 1)}</b>",
        f"🏳️ کشور/شهر: <b>{intel['country']}</b> ({intel['cities']} شهر)",
        f"🏗️ ساختمان‌ها: {_fuzz(intel['estates'], accuracy)} عمارت ، {_fuzz(intel['factories'], accuracy)} کارخانه",
        f"💰 موجودی: {_fuzz(intel['cash'], accuracy)}$",
        f"📈 درآمدِ روزانه: {_fuzz(intel['daily_income'], accuracy)}$",
        f"⚔️ قدرتِ رزمی: {_fuzz(int(intel.get('power') or 0), accuracy)}",
        f"🪖 شمارِ نیرو: {_fuzz(int(intel.get('weapons') or 0), accuracy)}"
        + (f" | 💥 قدرت ارتش ≈ {_fuzz(int(intel.get('army_power') or 0), accuracy)}" if intel.get("army_power") else ""),
    ]

    by_cat = intel.get("army_by_cat") or {}
    if by_cat:
        lines.append("")
        lines.append("🧭 <b>ترکیب نیروها (برآورد):</b>")
        # مرتب بر اساس تعداد
        ordered = sorted(by_cat.items(), key=lambda kv: int(kv[1] or 0), reverse=True)
        for cat, cnt in ordered:
            label = MD.CATEGORY_LABELS.get(cat, cat)
            lines.append(f"• {label}: {_fuzz(int(cnt or 0), accuracy)}")

    top = intel.get("army_top") or []
    if top:
        lines.append("")
        lines.append("📌 <b>مهم‌ترین واحدها:</b>")
        # با دقت پایین، جزئیات کمتر
        show_n = 6 if accuracy >= 0.85 else (4 if accuracy >= 0.55 else 2)
        for _pw, name, count, level in top[:show_n]:
            lvl = f" ⚙️{level}" if int(level or 0) > 0 else ""
            if accuracy >= 0.99:
                lines.append(f"• {name}: {int(count):,}عدد{lvl}")
            else:
                lines.append(f"• {name}: {_fuzz(int(count), accuracy)}{lvl}")
        if accuracy < 0.55:
            lines.append("<i>دقت پایین — جزئیات ترکیب محدود است. جاسوس را ارتقا بده.</i>")
    elif int(intel.get("weapons") or 0) <= 0:
        lines.append("")
        lines.append("🪖 هدف عملاً بدون ارتش فعال دیده شد.")

    return "\n".join(lines)


async def resolve_target(session, owner_id: int, raw: str) -> tuple[int | None, str | None]:
    """(target_id, error) — از روی آیدیِ عددی یا یوزرنیم."""
    raw = (raw or "").strip()
    if not raw:
        return None, "ورودی خالی است."
    target_id: int | None = None

    if raw.lstrip("-").isdigit():
        target_id = int(raw)
    else:
        uname = raw.lstrip("@").lower()
        # اول در اشخاصِ اضافه‌شده
        c = (await session.execute(
            select(Contact).where(
                Contact.owner_id == owner_id,
                func.lower(Contact.username) == uname,
            )
        )).scalar_one_or_none()
        if c:
            target_id = c.contact_id
        else:
            # سپس در جدولِ بازیکنان
            p = (await session.execute(
                select(Player).where(func.lower(Player.username) == uname)
            )).scalar_one_or_none()
            if p:
                target_id = p.tg_user_id

    if target_id is None:
        return None, "کاربری پیدا نشد. با ریپلایِ «افزودن» او را به مخاطبین اضافه کن."
    if target_id == owner_id:
        return None, "نمی‌توانی جاسوس را رویِ خودت اعزام کنی!"
    target_player = await get_player(session, target_id)
    if target_player is None:
        return None, "این کاربر هنوز در بازی ثبت‌نام نکرده (باید /start زده باشد)."
    return target_id, None
