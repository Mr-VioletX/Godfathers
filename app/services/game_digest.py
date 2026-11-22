# -*- coding: utf-8 -*-
"""🆕 v1.7.5 — ساخت خلاصهٔ اخبار زنده از دیتابیس (جنگ‌ها، القاب، …).

اگر جدول news_items خالی باشد، از live_battles و سایر منابع زنده digest می‌سازد
تا بخش اخبار دیگر همیشه «خبر مهمی رخ نداده» نگوید.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta

from sqlalchemy import desc, select

from app.data import news as N


def _name(plan: dict, key: str, fallback) -> str:
    return str(plan.get(key) or fallback or "?")


def _loss_total(d: dict | None) -> int:
    return int(sum(int(v or 0) for v in (d or {}).values()))


async def collect_live_events(session, *, hours: int = 24, limit: int = 40) -> list[dict]:
    """رویدادهای زندهٔ ۲۴ ساعت اخیر را به شکل آیتم خبر برمی‌گرداند."""
    since = datetime.utcnow() - timedelta(hours=max(1, int(hours)))
    items: list[dict] = []

    # ---- جنگ‌های زنده (تمام‌شده) ----
    try:
        from app.models.live_battle import LiveBattle

        rows = list(
            (
                await session.execute(
                    select(LiveBattle)
                    .where(LiveBattle.started_at >= since)
                    .order_by(desc(LiveBattle.started_at))
                    .limit(80)
                )
            ).scalars().all()
        )
    except Exception:
        rows = []

    battle_scored = []
    for row in rows:
        try:
            plan = json.loads(row.plan_json or "{}")
        except Exception:
            plan = {}
        att = _name(plan, "att_name", row.attacker_id)
        deff = _name(plan, "def_name", row.defender_id)
        won = bool(plan.get("attacker_won"))
        ap = int(plan.get("att_power") or 0)
        dp = int(plan.get("def_power") or 0)
        al = _loss_total(plan.get("att_losses"))
        dl = _loss_total(plan.get("def_losses"))
        loot = int(plan.get("loot") or 0)
        mode = "رنکینگ" if str(row.mode) == "ranked" else "کلاسیک"
        score = ap + dp + al * 10 + dl * 10 + loot // 1000
        if won:
            # 🆕 v1.7.9.1 — مبلغِ غنیمت در اخبار اعلام نمی‌شود
            text = (
                f"[{mode}] {att} بر {deff} پیروز شد "
                f"(قدرت {ap:,} vs {dp:,} | تلفات {al:,}/{dl:,})"
            )
        else:
            text = (
                f"[{mode}] {deff} حملهٔ {att} را دفع کرد "
                f"(قدرت {ap:,} vs {dp:,} | تلفات {al:,}/{dl:,})"
            )
        imp = 3 if (ap + dp) >= 100_000 or loot >= 50_000_000 else 2
        battle_scored.append((score, {
            "category": "war",
            "text": text,
            "importance": imp,
            "created_at": row.started_at,
        }))

    battle_scored.sort(key=lambda x: x[0], reverse=True)
    # بزرگ‌ترین جنگ‌ها اول
    for i, (_sc, it) in enumerate(battle_scored):
        if i == 0 and len(battle_scored) >= 1:
            it = dict(it)
            it["text"] = "🏆 بزرگ‌ترین نبرد بازه: " + it["text"]
            it["importance"] = 3
        items.append(it if isinstance(it, dict) else it)

    # ---- اخبار ثبت‌شده در news_items ----
    try:
        from app.services import news_service

        stored = await news_service.items_since(session, since, only_unpublished=False)
        for it in stored:
            items.append({
                "category": getattr(it, "category", "event"),
                "text": getattr(it, "text", ""),
                "importance": int(getattr(it, "importance", 1) or 1),
                "created_at": getattr(it, "created_at", None),
            })
    except Exception:
        pass

    # ---- القاب تازه (از title claims اگر موجود) ----
    try:
        from app.models.title import PlayerTitle
        from app.models.player import Player

        trows = list(
            (
                await session.execute(
                    select(PlayerTitle, Player)
                    .join(Player, Player.tg_user_id == PlayerTitle.tg_user_id)
                    .where(PlayerTitle.granted_at >= since)
                    .order_by(desc(PlayerTitle.granted_at))
                    .limit(15)
                )
            ).all()
        )
        for pt, pl in trows:
            tname = getattr(pt, "title_key", None) or getattr(pt, "key", None) or "لقب"
            pname = getattr(pl, "name", None) or pt.tg_user_id
            items.append({
                "category": "title",
                "text": f"{pname} لقب «{tname}» را کسب کرد.",
                "importance": 2,
                "created_at": getattr(pt, "granted_at", None),
            })
    except Exception:
        pass

    # مرتب‌سازی: اهمیت سپس تازگی
    def _key(it):
        imp = int(it.get("importance") or 1)
        ts = it.get("created_at") or datetime.utcnow()
        try:
            epoch = ts.timestamp()
        except Exception:
            epoch = 0
        return (imp, epoch)

    items.sort(key=_key, reverse=True)
    # حذف متن تکراری
    seen = set()
    unique = []
    for it in items:
        t = (it.get("text") or "").strip()
        if not t or t in seen:
            continue
        seen.add(t)
        unique.append(it)
        if len(unique) >= limit:
            break
    return unique


async def build_game_digest(session, *, hours: int = 24, mark_published: bool = False) -> tuple[str, int]:
    """خلاصهٔ کامل اخبار بازی (زنده + ذخیره‌شده)."""
    # اول digest استاندارد از news_items منتشرنشده
    try:
        from app.services import news_service

        text0, n0 = await news_service.compile_daily_digest(
            session, mark_published=mark_published
        )
    except Exception:
        text0, n0 = "", 0

    live = await collect_live_events(session, hours=hours, limit=N.MAX_ITEMS_IN_DIGEST)
    if not live and n0:
        return text0, n0
    if not live:
        # آمار حداقلی حتی اگر خبری نباشد
        try:
            from app.models.player import Player
            from sqlalchemy import func

            total_p = int(
                (await session.execute(select(func.count()).select_from(Player))).scalar() or 0
            )
        except Exception:
            total_p = 0
        label = N.today_label()
        return (
            f"📰 <b>اخبارِ روزانه‌ی بازی</b> — {label}\n\n"
            f"👥 بازیکنان ثبت‌شده: <b>{total_p:,}</b>\n"
            "در ۲۴ ساعت اخیر نبرد نهایی‌شده یا رویداد ثبت‌شده‌ای پیدا نشد.\n"
            "با انجام جنگ، کسب لقب و رویدادهای مهم، اینجا پر می‌شود."
        ), 0

    # اگر digest ذخیره‌شده خالی/بی‌محتواست، از live بساز
    if n0 <= 0 or "خبرِ مهمی ثبت نشد" in (text0 or "") or "خبر مهمی" in (text0 or ""):
        return N.compile_digest(live), len(live)

    # ترکیب: هدر digest + آیتم‌های live که در text0 نیستند
    extra_lines = []
    for it in live:
        line = "• " + N.format_item(it.get("category"), it.get("text", ""))
        if line not in (text0 or ""):
            extra_lines.append(line)
    if not extra_lines:
        return text0, n0
    return (text0 or N.compile_digest([])) + "\n\n📌 <b>بروزرسانی زنده:</b>\n" + "\n".join(extra_lines[:20]), n0 + len(extra_lines)
