# -*- coding: utf-8 -*-
"""🆕 v1.7.5 — مغز پویای دستیار اول (کنسیلیری).

به‌جای متن خشک/تکراری، از دادهٔ زنده گزارش می‌سازد:
  • نبض امپراتوری (وضعیت لحظه‌ای + لحن)
  • فرصت‌یاب (کارهای سودده همین الان)
  • آمادگی جنگ (قدرت، ارتش، نقاط ضعف)
  • مأموریت روزانه (۳ هدف کوتاه و قابل انجام)
  • رصد میدان (آخرین جنگ‌ها / اخبار زنده)
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta

from sqlalchemy import desc, func, select

# --- لحن‌های کوتاه (هر بار یکی) ---
GREETINGS = [
    "🎩 آماده‌ام، رئیس. نبض امپراتوری را چک کردم:",
    "🕶️ گزارش تازه از خیابان‌ها:",
    "📡 سیگنال‌ها اومد. بشنو:",
    "🧭 نقشه‌ی امروز رو برات چیدم:",
    "🔥 یه نگاه تند به وضعیتت:",
]
WIN_LINES = [
    "امروز دست بالا با توست — فشار رو کم نکن.",
    "امپراتوری نفس می‌کشه. همین ریتم رو نگه دار.",
    "خوب پیش می‌ری؛ فقط حواست به نقاط کور باشه.",
]
WARN_LINES = [
    "چند تا کار عقب‌مونده هست — اگر الان جمعش نکنی، رقیب جلو می‌زنه.",
    "زنگ خطر کوچیک روشن شده. قبل از جنگ این‌ها رو جمع کن.",
    "وضعیت بحرانی نیست، ولی تنبلی گرون تموم می‌شه.",
]
EMPTY_ARMY = [
    "ارتشت خلوت‌تر از کافهٔ نیمه‌شبِ پالرموست.",
    "بدون ارتش، حرف زدن از جنگ فقط بلوفه.",
]


def _pick(seq, seed: int | None = None):
    if not seq:
        return ""
    rng = random.Random(seed if seed is not None else datetime.utcnow().minute)
    return rng.choice(list(seq))


def _money(n: int) -> str:
    try:
        return f"{int(n):,}$"
    except Exception:
        return "0$"


async def _safe(coro, default=None):
    try:
        return await coro
    except Exception:
        return default


async def gather_snapshot(session, uid: int) -> dict:
    """یک اسنپ‌شات زنده از وضعیت بازیکن."""
    from app.models.player import Player
    from app.models.estate import Estate
    from app.models.factory import Factory
    from app.models.assistant import Assistant

    player = (await session.execute(select(Player).where(Player.tg_user_id == uid))).scalar_one_or_none()
    if player is None:
        res = await session.execute(select(Player).where(Player.tg_user_id == uid))
        player = res.scalar_one_or_none()
    assistant = await session.get(Assistant, uid)

    estates = list(
        (await session.execute(select(Estate).where(Estate.tg_user_id == uid))).scalars().all()
    )
    factories = list(
        (await session.execute(select(Factory).where(Factory.tg_user_id == uid))).scalars().all()
    )

    cash = int(getattr(player, "cash", 0) or 0) if player else 0
    level = int(getattr(player, "level", 1) or 1) if player else 1
    xp = int(getattr(player, "xp", 0) or 0) if player else 0

    # XP remaining
    xp_line = ""
    xp_left = 0
    try:
        from app.data import leveling as LV

        xp_line = LV.progress_line(player) if player else ""
        xp_left = int(LV.xp_remaining(player) or 0) if player else 0
    except Exception:
        pass

    # military
    army_total = 0
    army_power = 0
    army_cats: dict[str, int] = {}
    top_units = []
    try:
        from app.services import military_service
        from app.data import military as MD

        stacks = await military_service.army_stacks(session, uid)
        for k, c, lv in stacks:
            c = int(c or 0)
            if c <= 0:
                continue
            u = MD.get_unit(k) or {}
            cat = u.get("cat") or "?"
            army_cats[cat] = army_cats.get(cat, 0) + c
            army_total += c
            pw = int(MD.unit_power(k, c, int(lv or 0)))
            army_power += pw
            top_units.append((pw, u.get("name", k), c, int(lv or 0)))
        top_units.sort(reverse=True)
    except Exception:
        pass

    combat = 0
    try:
        from app.services import war_service

        combat = int(await war_service.compute_combat_power(session, uid))
    except Exception:
        combat = army_power

    # factory readiness (Factory + FactoryProduct)
    ready_lines = 0
    idle_factories = 0
    stock_lines = 0
    try:
        from app.models.factory import FactoryProduct

        for f in factories:
            prods = list(
                (
                    await session.execute(
                        select(FactoryProduct).where(FactoryProduct.factory_id == f.id)
                    )
                ).scalars().all()
            )
            if not prods:
                st = str(getattr(f, "status", "idle") or "idle")
                if st != "producing":
                    idle_factories += 1
                if int(getattr(f, "stock", 0) or 0) > 0:
                    stock_lines += 1
                # ready if finished producing
                ends = getattr(f, "ends_at", None) or getattr(f, "ready_at", None)
                if st == "producing" and ends and ends <= datetime.utcnow():
                    ready_lines += 1
                continue
            any_active = False
            for p in prods:
                st = str(getattr(p, "status", "idle") or "idle")
                if st == "producing":
                    any_active = True
                    ends = getattr(p, "ends_at", None) or getattr(p, "ready_at", None)
                    if ends and ends <= datetime.utcnow():
                        ready_lines += 1
                elif st in ("ready", "done", "finished"):
                    ready_lines += 1
                if int(getattr(p, "stock", 0) or 0) > 0:
                    stock_lines += 1
            if not any_active and all(
                str(getattr(p, "status", "idle") or "idle") == "idle" for p in prods
            ):
                idle_factories += 1
    except Exception:
        for f in factories:
            st = str(getattr(f, "status", "idle") or "idle")
            if st != "producing":
                idle_factories += 1
            if int(getattr(f, "stock", 0) or 0) > 0:
                stock_lines += 1

    # shield / war
    shield_on = False
    try:
        from app.models.war import WarState

        st = await session.get(WarState, uid)
        if st and getattr(st, "shield_until", None) and st.shield_until > datetime.utcnow():
            shield_on = True
    except Exception:
        pass

    # recent battles involving player
    recent_battles = []
    try:
        from app.models.live_battle import LiveBattle
        import json

        rows = list(
            (
                await session.execute(
                    select(LiveBattle)
                    .where(
                        (LiveBattle.attacker_id == uid) | (LiveBattle.defender_id == uid),
                        LiveBattle.started_at >= datetime.utcnow() - timedelta(hours=48),
                    )
                    .order_by(desc(LiveBattle.started_at))
                    .limit(5)
                )
            ).scalars().all()
        )
        for r in rows:
            try:
                plan = json.loads(r.plan_json or "{}")
            except Exception:
                plan = {}
            recent_battles.append({
                "mode": r.mode,
                "won": bool(plan.get("attacker_won")) if r.attacker_id == uid else (not bool(plan.get("attacker_won"))),
                "as_attacker": r.attacker_id == uid,
                "opp": plan.get("def_name") if r.attacker_id == uid else plan.get("att_name"),
                "loot": int(plan.get("loot") or 0),
                "finalized": int(r.finalized or 0),
            })
    except Exception:
        pass

    # brand production (v1.7.6)
    brand_ready = 0
    brand_producing = 0
    brand_stock = 0
    try:
        from app.models.branding import BrandCompany, BrandProduct
        from datetime import datetime as _dt
        cos = list((await session.execute(select(BrandCompany).where(BrandCompany.owner_id == uid))).scalars().all())
        for co in cos:
            bps = list((await session.execute(select(BrandProduct).where(BrandProduct.company_id == co.id))).scalars().all())
            for bp in bps:
                st = str(getattr(bp, "status", "idle") or "idle")
                if st == "producing":
                    brand_producing += 1
                    try:
                        from app.data import brands as BRD
                        started = getattr(bp, "started_at", None)
                        hrs = float(BRD.effective_produce_hours(bp.product_key, int(getattr(co, "speed_level", 1) or 1)))
                        if started is not None and (_dt.utcnow() - started).total_seconds() >= hrs * 3600:
                            brand_ready += 1
                    except Exception:
                        pass
                if int(getattr(bp, "stock", 0) or 0) > 0:
                    brand_stock += 1
                if st in ("ready", "done", "finished"):
                    brand_ready += 1
    except Exception:
        brand_ready = brand_producing = brand_stock = 0

    # ranking hint
    rank_hint = None
    try:
        from app.models.rank import RankState

        st = await session.get(RankState, uid)
        if st is None:
            # برخی نسخه‌ها کلید متفاوت دارند
            st = (
                await session.execute(select(RankState).where(RankState.tg_user_id == uid))
            ).scalar_one_or_none()
        if st is not None:
            rank_hint = int(getattr(st, "cups", 0) or 0)
    except Exception:
        rank_hint = None

    # city
    city_name = None
    try:
        from app.models.mafia_city import MafiaCity

        city = (
            await session.execute(select(MafiaCity).where(MafiaCity.tg_user_id == uid))
        ).scalar_one_or_none()
        if city:
            city_name = getattr(city, "name", None)
    except Exception:
        pass

    return {
        "uid": uid,
        "player": player,
        "assistant": assistant,
        "name": getattr(player, "name", None) or "رئیس",
        "cash": cash,
        "level": level,
        "xp": xp,
        "xp_line": xp_line,
        "xp_left": xp_left,
        "estates": len(estates),
        "factories": len(factories),
        "ready_lines": ready_lines,
        "brand_ready": brand_ready,
        "brand_producing": brand_producing,
        "brand_stock": brand_stock,
        "idle_factories": idle_factories,
        "stock_lines": stock_lines,
        "army_total": army_total,
        "army_power": army_power,
        "army_cats": army_cats,
        "top_units": top_units[:5],
        "combat": combat,
        "shield_on": shield_on,
        "recent_battles": recent_battles,
        "cups": rank_hint,
        "city_name": city_name,
        "assist_level": int(getattr(assistant, "upgrade_level", 1) or 1) if assistant else 0,
    }


def _weakness(cats: dict) -> str | None:
    from app.data import military as MD

    labels = []
    need = [("aa", "پدافند"), ("fighter", "هوایی"), ("tank", "زرهی"), ("soldier", "پیاده")]
    for cat, name in need:
        if int(cats.get(cat, 0) or 0) <= 0:
            labels.append(name)
    if not labels:
        return None
    return "، ".join(labels)


async def pulse_text(session, uid: int) -> str:
    """نبض امپراتوری — گزارش زنده و لحن‌دار."""
    s = await gather_snapshot(session, uid)
    seed = uid + datetime.utcnow().hour
    head = _pick(GREETINGS, seed)
    a_name = getattr(s.get("assistant"), "name", None) or "کنسیلیری"

    score = 0
    flags = []
    if s["ready_lines"]:
        flags.append(f"📦 {s['ready_lines']} خط تولید آماده‌ی جمع‌آوریه")
        score -= 1
    if s["idle_factories"]:
        flags.append(f"▶️ {s['idle_factories']} کارخانه خوابه — روشن کن")
        score -= 1
    if s["stock_lines"]:
        flags.append(f"💵 {s['stock_lines']} انبار پر — بفروش قبل از افت قیمت")
        score -= 0
    if s["army_total"] <= 0:
        flags.append(_pick(EMPTY_ARMY, seed))
        score -= 2
    if s["shield_on"]:
        flags.append("🛡️ سپر فعاله — فعلاً هدف سختی نیستی")
        score += 1
    if s["cash"] < 50_000:
        flags.append("💸 موجودی پایینه — یه دور دزدی/فروش لازم داری")
        score -= 1
    if s["combat"] >= 50_000:
        flags.append(f"⚔️ قدرت رزمی {s['combat']:,} — تو لیگ خود�� سنگینی")
        score += 1

    mood = _pick(WIN_LINES if score >= 0 else WARN_LINES, seed + 3)

    lines = [
        f"🤖 <b>{a_name}</b> — نبض امپراتوری",
        head,
        "",
        f"👤 {s['name']} | 🎚️ لول {s['level']} | 💵 {_money(s['cash'])}",
    ]
    if s["xp_line"]:
        lines.append(s["xp_line"])
    lines += [
        f"⚔️ قدرت: <b>{s['combat']:,}</b> | 🪖 نیرو: <b>{s['army_total']:,}</b> | 💥 ارتش: <b>{s['army_power']:,}</b>",
        f"🏛️ عمارت {s['estates']} | 🏭 کارخانه {s['factories']}"
        + (f" | 🏙️ {s['city_name']}" if s.get("city_name") else ""),
    ]
    if s.get("cups") is not None:
        lines.append(f"🏅 کاپ رنکینگ: <b>{int(s['cups']):,}</b>")
    lines.append("")
    lines.append(f"💬 <i>{mood}</i>")
    if flags:
        lines.append("")
        lines.append("🔔 <b>الان مهمه:</b>")
        for f in flags[:6]:
            lines.append(f"• {f}")
    else:
        lines.append("")
        lines.append("✅ خبر فوری نیست — می‌تونی توسعه یا شکار هدف بری.")

    # mini tip dynamic
    weak = _weakness(s["army_cats"])
    if weak:
        lines.append(f"⚠️ نقطه‌ضعف ارتش: <b>{weak}</b> — قبل از جنگ بعدی پرش کن.")
    if s["top_units"]:
        _pw, nm, c, lv = s["top_units"][0]
        lines.append(f"⭐ ستون ارتش: {nm} ×{c:,}" + (f" (لول {lv})" if lv else ""))

    lines.append("")
    lines.append("از دکمه‌ها: فرصت‌یاب • آمادگی جنگ • مأموریت روزانه • رصد میدان")
    return "\n".join(lines)


async def opportunities_text(session, uid: int) -> str:
    """فرصت‌های سودده همین الان — actionable."""
    s = await gather_snapshot(session, uid)
    a_name = getattr(s.get("assistant"), "name", None) or "کنسیلیری"
    ops = []

    if s["ready_lines"] > 0:
        ops.append((
            100,
            "📦 جمع‌آوری تولید",
            f"{s['ready_lines']} خط آماده‌ست. برو کارخانه → جمع‌آوری همه. پول خوابیده روی میز.",
        ))
    if s["idle_factories"] > 0:
        ops.append((
            90,
            "▶️ استارت تولید",
            f"{s['idle_factories']} کارخانه خاموشه. هر ساعت خاموشی = درآمد از دست‌رفته.",
        ))
    if s["stock_lines"] > 0:
        ops.append((
            85,
            "📈 فروش در اوج",
            f"{s['stock_lines']} موجودی انبار داری. نمودار بازار رو ببین و بفروش.",
        ))
    # v1.7.6 brand + hospital
    bp = int(s.get("brand_producing") or 0)
    brdy = int(s.get("brand_ready") or 0)
    bst = int(s.get("brand_stock") or 0)
    if brdy > 0 or bp > 0:
        ops.append((
            92,
            "🏭 برند: خط تولید",
            f"برند — فعال: {bp} | آماده: {brdy}. برو شرکت‌ها → جمع‌آوری/شروع تولید.",
        ))
    if bst > 0:
        ops.append((
            84,
            "📦 برند: موجودی",
            f"{bst} موجودی در شرکت برند داری. بفروش یا منتقل کن.",
        ))
    try:
        from app.services import battle_live as BL
        last = await BL.last_battle(session, uid)
        if last is not None and int(getattr(last, "finalized", 0) or 0):
            plan = BL.plan_of(last)
            hosp = plan.get("hospital") or {}
            if str(uid) not in hosp and int(uid) not in hosp:
                ops.append((
                    75,
                    "🏥 بیمارستان",
                    "جنگ اخیر تمام شده. از گزارش نبرد نیروهای انسانی تلف‌شده را درمان کن.",
                ))
    except Exception:
        pass

    if s["army_total"] < max(50, s["level"] * 5):
        ops.append((
            80,
            "🪖 تقویت ارتش",
            f"فقط {s['army_total']:,} نیرو داری. برای لول {s['level']} کمه — حداقل یک موج خرید بزن.",
        ))
    weak = _weakness(s["army_cats"])
    if weak:
        ops.append((
            78,
            "🧩 رفع نقطه‌ضعف",
            f"ارتشت {weak} نداره. تو جنگ هم‌رده همین حفره می‌کُشَدت.",
        ))
    if s["xp_left"] and s["xp_left"] < 500:
        ops.append((
            70,
            "⚡ لول‌آپ نزدیک",
            f"فقط {s['xp_left']:,} XP تا لول بعد. یه دزدی/مسابقه/ساخت کوچیک کار رو تموم می‌کنه.",
        ))
    if s["cash"] > 5_000_000 and s["estates"] < 3:
        ops.append((
            65,
            "🏛️ عمارت جدید",
            "پولت mobil هست. عمارت نقش‌دار بعدی درآمد ساعتی‌ت رو می‌ترکونه.",
        ))
    if not s["shield_on"] and s["combat"] > 0:
        ops.append((
            55,
            "🛡️ چک سپر",
            "سپر نداری. اگر تازه باختی یا هدفت، از بخش جنگ وضعیت مصونیت رو ببین.",
        ))
    if s.get("cups") is not None and int(s["cups"] or 0) < 30:
        ops.append((
            60,
            "🏅 جنگ رنکینگ",
            f"کاپ‌ت {int(s['cups'])} است. یه برد رنکینگ تمیز لیگت رو جابه‌جا می‌کنه.",
        ))

    ops.sort(key=lambda x: x[0], reverse=True)
    lines = [
        f"🎯 <b>{a_name} — فرصت‌یاب</b>",
        "همین الان چه کاری بیشترین بازده رو داره؟",
        "",
    ]
    if not ops:
        lines.append("✨ فرصت فوریِ واضحی نیست. برو توسعه بلندمدت: ارتقای نیرو، شهر، برند.")
    else:
        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣"]
        for i, (_sc, title, body) in enumerate(ops[:6]):
            m = medals[i] if i < len(medals) else "•"
            lines.append(f"{m} <b>{title}</b>")
            lines.append(f"   {body}")
            lines.append("")
    lines.append("🧠 نکته: اولویت با کارهای «پول نقدِ آماده» است، بعد قدرت نظامی.")
    return "\n".join(lines)


async def war_readiness_text(session, uid: int) -> str:
    """آمادگی جنگ — پویا و کاربردی."""
    s = await gather_snapshot(session, uid)
    a_name = getattr(s.get("assistant"), "name", None) or "کنسیلیری"
    score = 50
    notes = []

    if s["army_total"] <= 0:
        score -= 40
        notes.append("❌ ارتش نداری — حمله نکن.")
    elif s["army_total"] < 100:
        score -= 15
        notes.append("⚠️ ارتش سبک‌تر از حد ایده‌آله.")
    else:
        score += 10
        notes.append(f"✅ شمار نیرو: {s['army_total']:,}")

    if s["combat"] >= 80_000:
        score += 15
        notes.append(f"✅ قدرت رزمی بالا ({s['combat']:,})")
    elif s["combat"] >= 20_000:
        score += 5
        notes.append(f"🟡 قدرت متوسط ({s['combat']:,})")
    else:
        score -= 10
        notes.append(f"⚠️ قدرت پایین ({s['combat']:,})")

    weak = _weakness(s["army_cats"])
    if weak:
        score -= 12
        notes.append(f"❌ حفره ترکیب: {weak}")
    else:
        score += 8
        notes.append("✅ ترکیب نسبتاً متوازن")

    # average level of top units
    if s["top_units"]:
        avg_lv = sum(u[3] for u in s["top_units"]) / max(1, len(s["top_units"]))
        if avg_lv < 1:
            score -= 10
            notes.append("⚠️ لول نیروهای اصلیت پایینه — ارتقا بده")
        elif avg_lv >= 3:
            score += 8
            notes.append(f"✅ لول میانگین نیروهای اصلی ≈ {avg_lv:.1f}")
        else:
            notes.append(f"🟡 لول میانگین نیروهای اصلی ≈ {avg_lv:.1f}")

    if s["shield_on"]:
        notes.append("🛡️ سپر داری — می‌تونی نفسی تازه کنی")
    if s["cash"] < 100_000:
        score -= 5
        notes.append("💸 نقدینگی کم — بعد از جنگ غرامت/ریکاوری سخته")

    score = max(0, min(100, score))
    if score >= 75:
        verdict = "🟢 آماده‌ی شکار. هدف هم‌رده یا ضعیف‌تر انتخاب کن."
    elif score >= 50:
        verdict = "🟡 قابل قبول، ولی قبلش یک ضعف رو ببند."
    else:
        verdict = "🔴 حمله الان ریسکش بالاست — اول ارتش/ترکیب."

    lines = [
        f"⚔️ <b>{a_name} — آمادگی جنگ</b>",
        f"امتیاز آمادگی: <b>{score}/100</b>",
        verdict,
        "",
        f"💥 قدرت: {s['combat']:,} | 🪖 {s['army_total']:,} نیرو | 🏭 قدرت ارتش {s['army_power']:,}",
        "",
        "📋 چک‌لیست:",
    ]
    for n in notes:
        lines.append(f"• {n}")

    if s["top_units"]:
        lines.append("")
        lines.append("⭐ ستون‌های ارتش:")
        for _pw, nm, c, lv in s["top_units"][:4]:
            lines.append(f"• {nm}: {c:,}" + (f" ⚙️{lv}" if lv else ""))

    lines.append("")
    lines.append(
        "💡 قانون طلایی: به کسی حمله کن که قدرتش حدود ۷۰–۱۱۰٪ تو باشه؛ "
        "یا خیلی ضعیف‌تر — نه غول بی‌شاخ‌دم."
    )
    return "\n".join(lines)


async def daily_mission_text(session, uid: int) -> str:
    """۳ مأموریت کوتاه روزانه — بر اساس seed روز + وضعیت."""
    s = await gather_snapshot(session, uid)
    a_name = getattr(s.get("assistant"), "name", None) or "کنسیلیری"
    day = datetime.utcnow().strftime("%Y%m%d")
    rng = random.Random(f"{uid}-{day}")

    pool = []
    # always available-ish
    pool.append(("🕵️ دزد حرفه‌ای", "۳ بار دزدی موفق انجام بده.", "پول نقد سریع + XP"))
    pool.append(("🏭 کارخانه‌دار", "همه خطوط بیکار را روشن کن و یک‌بار جمع‌آوری کن.", "جریان درآمد"))
    pool.append(("🪖 سربازگیری", f"حداقل {max(20, s['level']*2)} نیرو بخر یا صف پرورش بگذار.", "قدرت"))
    pool.append(("⚙️ استاد آموزش", "یک نوع نیرو را یک لول ارتقا بده.", "تلفات کمتر در جنگ"))
    pool.append(("🏅 شکار رنک", "یک جنگ رنکینگ انجام بده (برد یا دفاع).", "کاپ + اعتبار"))
    pool.append(("🏷️ جاه‌طلب", "به بخش القاب سر بزن و یک پیشرفت نزدیک را چک کن.", "هویت و بونس"))
    pool.append(("🏦 حساب‌کشی", "موجودی بانک/وام را یک‌بار بررسی کن.", "امنیت اقتصادی"))
    if s.get("city_name"):
        pool.append(("🏙️ شهردار", f"به شهر «{s['city_name']}» سر بزن و یک ساخت/ارتقای کوچک بزن.", "درآمد شهری"))
    else:
        pool.append(("🗺️ زمین‌دار", "اگر لولت رسید، برای تأسیس/مدیریت شهر برنامه‌ریزی کن.", "بلندمدت"))
    if s["stock_lines"]:
        pool.append(("💎 فروش لوکس", "از انبار پر حداقل یک فروش در بازار بزن.", "نقد کردن موجودی"))

    # bias toward needed actions
    weighted = list(pool)
    if s["idle_factories"]:
        weighted += [pool[1]] * 2
    if s["army_total"] < 50:
        weighted += [p for p in pool if "سرباز" in p[0]] * 2
    if s["xp_left"] and s["xp_left"] < 800:
        weighted += [pool[0]]

    picks = []
    seen = set()
    while len(picks) < 3 and weighted:
        item = rng.choice(weighted)
        if item[0] in seen:
            weighted = [w for w in weighted if w[0] != item[0]]
            continue
        seen.add(item[0])
        picks.append(item)

    lines = [
        f"🎖️ <b>{a_name} — مأموریت روزانه</b>",
        f"📅 {day[:4]}/{day[4:6]}/{day[6:]}",
        "۳ مأموریت کوتاه. انجام بده، قدرت و پول جلو می‌افته.",
        "",
    ]
    for i, (title, task, reward) in enumerate(picks, 1):
        lines.append(f"{i}) <b>{title}</b>")
        lines.append(f"   📌 {task}")
        lines.append(f"   🎁 چرا؟ {reward}")
        lines.append("")
    lines.append("✨ فردا مأموریت‌ها عوض می‌شن. امروز رو نسوزون.")
    if s["xp_left"]:
        lines.append(f"⚡ تا لول بعد: {s['xp_left']:,} XP")
    return "\n".join(lines)


async def field_radar_text(session, uid: int) -> str:
    """رصد میدان: جنگ‌های اخیر بازیکن + اخبار زنده بازی."""
    s = await gather_snapshot(session, uid)
    a_name = getattr(s.get("assistant"), "name", None) or "کنسیلیری"
    lines = [
        f"📡 <b>{a_name} — رصد میدان</b>",
        "",
        "⚔️ <b>نبردهای ۴۸ ساعت اخیر تو:</b>",
    ]
    if not s["recent_battles"]:
        lines.append("• هنوز نبرد تازه‌ای برات ثبت نشده.")
    else:
        for b in s["recent_battles"]:
            role = "حمله" if b["as_attacker"] else "دفاع"
            if not b["finalized"]:
                res = "در جریان…"
            else:
                res = "برد ✅" if b["won"] else "باخت ❌"
            loot = f" | غنیمت {b['loot']:,}$" if b.get("loot") else ""
            mode = "رنک" if b.get("mode") == "ranked" else "کلاسیک"
            lines.append(f"• [{mode}/{role}] vs {b.get('opp') or '?'} — {res}{loot}")

    lines.append("")
    lines.append("📰 <b>خلاصه میدان بازی:</b>")
    try:
        from app.services.game_digest import build_game_digest

        digest, n = await build_game_digest(session, hours=24, mark_published=False)
        # take a few bullet lines only
        bullets = [ln for ln in (digest or "").splitlines() if ln.strip().startswith("• ")][:8]
        if bullets:
            lines.extend(bullets)
        else:
            # fallback first lines
            for ln in (digest or "").splitlines()[:10]:
                if ln.strip():
                    lines.append(ln)
    except Exception:
        lines.append("• فعلاً خلاصه میدان در دسترس نیست.")

    lines.append("")
    lines.append("🧠 اگر دفاع باختی: لول نیرو + پدافند/ترکیب را بالا ببر، بعد برگرد.")
    return "\n".join(lines)


async def full_dynamic_report(session, uid: int) -> str:
    """گزارش کامل پویا (جایگزین گزارش خشک قدیمی)."""
    pulse = await pulse_text(session, uid)
    # compact extras
    s = await gather_snapshot(session, uid)
    a_name = getattr(s.get("assistant"), "name", None) or "کنسیلیری"
    bits = [pulse, "", "— — —", ""]

    # one top opportunity
    try:
        opp = await opportunities_text(session, uid)
        # extract first medal block roughly
        bits.append("🎯 <b>داغ‌ترین فرصت الان</b>")
        lines = opp.splitlines()
        # skip header
        body = [ln for ln in lines if ln.startswith("🥇") or ln.startswith("   ")]
        if body:
            bits.extend(body[:3])
        else:
            bits.append("• وضعیت پایدار — توسعه بلندمدت.")
    except Exception:
        pass

    bits.append("")
    bits.append(f"🤖 {a_name}: دکمه‌های زیر زنده‌ان — هر کدوم یه زاویه جدا بهت می‌ده.")
    return "\n".join(bits)
