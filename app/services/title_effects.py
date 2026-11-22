# -*- coding: utf-8 -*-
"""🆕 مرحله ۳۰ — اعمالِ واقعیِ اثرِ مثبتِ القاب در سراسرِ بازی.

مشکلِ قبلی: تابعِ services/titles.aggregate_effects وجود داشت امّا هیچ جایِ کد صدا زده
نمی‌شد؛ بنابراین بونوسِ لقب‌ها (attack_pct / defense_pct / spy_pct / income_pct / territory_pct)
فقط در توضیحات نوشته می‌شد و هیچ تأثیری در محاسبات نداشت.

این ماژول یک لایهٔ سبک با کشِ کوتاه‌مدّت است که جمعِ بونوسِ القاب را می‌دهد تا
بخش‌هایِ جنگ، جاسوسی، درآمد و دزدی از آن استفاده کنند.

واحدِ مقادیر: درصد (مثلاً income_pct = 7 یعنی ۷٪ درآمدِ بیشتر).
"""
from __future__ import annotations

import time

# uid -> (expires_at, bonuses dict)
_CACHE: dict[int, tuple[float, dict]] = {}
_TTL = 60.0   # ثانیه — تا بارِ دیتابیس زیاد نشود
_MAX_PCT = 300.0   # سقفِ ایمنی تا ترکیبِ لقب‌ها بازی را نشکند


def invalidate(uid: int | None = None) -> None:
    """پس از گرفتن/حذفِ لقب صدا زده می‌شود."""
    if uid is None:
        _CACHE.clear()
    else:
        _CACHE.pop(int(uid), None)


async def bonuses(session, uid: int) -> dict:
    """جمعِ بونوسِ همهٔ القابِ کسب‌شدهٔ بازیکن (برحسبِ درصد)."""
    uid = int(uid or 0)
    if uid <= 0:
        return {}
    now = time.time()
    hit = _CACHE.get(uid)
    if hit and hit[0] > now:
        return hit[1]
    data: dict = {}
    try:
        from app.services.titles import aggregate_effects
        res = await aggregate_effects(session, uid)
        data = dict(res.get("bonuses") or {})
    except Exception:
        data = {}
    _CACHE[uid] = (now + _TTL, data)
    return data


async def pct(session, uid: int, key: str) -> float:
    """مقدارِ یک بونوس برحسبِ درصد (مثلاً 12.0 یعنی ۱۲٪)."""
    b = await bonuses(session, uid)
    return max(0.0, min(_MAX_PCT, float(b.get(key, 0) or 0)))


async def multiplier(session, uid: int, key: str) -> float:
    """ضریبِ آمادهٔ مصرف: 1 + pct/100."""
    return 1.0 + (await pct(session, uid, key)) / 100.0


async def combat_multiplier(session, uid: int) -> float:
    """میانگینِ حمله/دفاع برایِ قدرتِ رزمیِ کل."""
    b = await bonuses(session, uid)
    atk = float(b.get("attack_pct", 0) or 0)
    dfn = float(b.get("defense_pct", 0) or 0)
    total = max(0.0, min(_MAX_PCT, (atk + dfn) / 2.0))
    return 1.0 + total / 100.0


async def summary_text(session, uid: int) -> str:
    """متنِ خلاصهٔ اثرِ فعّالِ القاب برایِ نمایش در پنلِ القاب."""
    labels = {
        "attack_pct": "⚔️ حمله",
        "defense_pct": "🛡️ دفاع",
        "spy_pct": "🕵️ جاسوسی",
        "income_pct": "💰 درآمد",
        "territory_pct": "🗺️ قلمرو",
    }
    b = await bonuses(session, uid)
    rows = [f"{labels.get(k, k)} +{int(v)}٪" for k, v in b.items() if int(v or 0) > 0]
    if not rows:
        return "— هنوز لقبی با اثرِ مثبت نداری."
    return " • ".join(rows)
