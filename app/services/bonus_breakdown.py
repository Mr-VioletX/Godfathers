# -*- coding: utf-8 -*-
"""v1.7.6 — نمایش شفاف اثر بونس اشتراک و رویداد روی درآمد/هزینه."""
from __future__ import annotations


async def income_breakdown(session, uid: int, base_amount: int) -> dict:
    """base_amount = مبلغ خام قبل از بونس‌ها.

    خروجی:
      base, sub_pct, sub_extra, event_mult, event_extra, total, note_lines
    """
    base = max(0, int(base_amount or 0))
    sub_pct = 0
    event_mult = 1.0
    try:
        from app.services import subscription_service as subs
        sub_pct = int(await subs.income_bonus_pct(session, uid) or 0)
    except Exception:
        sub_pct = 0
    after_sub = int(round(base * (100 + sub_pct) / 100)) if sub_pct else base
    sub_extra = max(0, after_sub - base)
    try:
        from app.data import events as EV
        event_mult = float(EV.BONUS.money_multiplier() or 1.0)
    except Exception:
        event_mult = 1.0
    total = int(EV.apply_money(after_sub)) if event_mult else after_sub
    try:
        from app.data import events as EV
        total = int(EV.apply_money(after_sub))
    except Exception:
        total = after_sub
    event_extra = max(0, total - after_sub)
    lines = []
    if sub_pct > 0 or event_mult > 1.0:
        lines.append(f"💵 پایه: <b>{base:,}$</b>")
        if sub_pct > 0:
            lines.append(f"💎 بونس اشتراک (+{sub_pct}٪): <b>+{sub_extra:,}$</b>")
        if event_mult > 1.0:
            lines.append(f"✨ بونس رویداد (×{event_mult:g}): <b>+{event_extra:,}$</b>")
        lines.append(f"✅ دریافتی نهایی: <b>{total:,}$</b>")
    return {
        "base": base,
        "sub_pct": sub_pct,
        "sub_extra": sub_extra,
        "event_mult": event_mult,
        "event_extra": event_extra,
        "total": total,
        "note": "\n".join(lines),
    }


async def discount_breakdown(session, uid: int, base_cost: int) -> dict:
    """base_cost = قیمت خام قبل از تخفیف اشتراک."""
    base = max(0, int(base_cost or 0))
    disc_pct = 0
    try:
        from app.services import subscription_service as subs
        disc_pct = int(await subs.discount_pct(session, uid) or 0)
    except Exception:
        disc_pct = 0
    final = int(round(base * (100 - disc_pct) / 100)) if disc_pct else base
    saved = max(0, base - final)
    lines = []
    if disc_pct > 0:
        lines.append(f"🏷 قیمت پایه: <b>{base:,}$</b>")
        lines.append(f"💎 تخفیف اشتراک (−{disc_pct}٪): <b>−{saved:,}$</b>")
        lines.append(f"✅ مبلغ پرداختی: <b>{final:,}$</b>")
    return {
        "base": base,
        "disc_pct": disc_pct,
        "saved": saved,
        "final": final,
        "note": "\n".join(lines),
    }


def append_note(msg: str, note: str) -> str:
    if not note:
        return msg
    return (msg or "") + "\n\n" + note
