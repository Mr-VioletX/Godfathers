# -*- coding: utf-8 -*-
"""مرحله ۱۵.۵ — منطقِ مرکزیِ تجربه (XP) و ارتقای سطح.

تمامِ بخش‌هایِ بازی (دزدی، ورزش، ماموریت‌ها و …) باید XP را از طریقِ
`add_xp()` اضافه کنند تا سقفِ سطح، فرمولِ نیاز و نمایش یک‌جا مدیریت شود.
"""
from __future__ import annotations

# سقفِ سطحِ بازیکن (مرحله ۱۵.۵)
MAX_LEVEL = 60

# Endgame ladder opened by Dark World. Values are XP from level N to N+1.
ELITE_XP_NEEDS = {
    50: 180_000, 51: 220_000, 52: 270_000, 53: 330_000, 54: 400_000,
    55: 480_000, 56: 570_000, 57: 670_000, 58: 780_000, 59: 900_000,
}


def xp_needed(level: int) -> int:
    """XP لازم برای رفتن از «این سطح» به سطحِ بعد.

    فرمولِ سازگار با نسخه‌ی قبلی: سطح۱→۱۰۰، سطح۲→۲۰۰، …
    در سقفِ سطح، ۰ برمی‌گرداند (دیگر ارتقایی نیست).
    """
    if level >= MAX_LEVEL:
        return 0
    if level >= 50:
        return ELITE_XP_NEEDS[int(level)]
    # بالانسِ بچ ۵: از لول ۳۰ به بعد مسیر با درون‌یابی خطی سخت‌تر می‌شود.
    # لول ۳۰→۳۱: ۱۰٬۰۰۰ XP | لول ۴۹→۵۰: ۱۵۰٬۰۰۰ XP.
    if level >= 30:
        interpolated = 10_000 + (level - 30) * (150_000 - 10_000) / (49 - 30)
        return int(round(interpolated / 100.0) * 100)
    return level * 100


def add_xp(player, amount: int, stats=None, source: str = "") -> dict:
    """XP را به بازیکن اضافه می‌کند و لِوِل‌آپ‌ها را با رعایتِ سقفِ ۶۰ اعمال می‌کند.

    - در سقفِ سطح، XP دیگر انباشته نمی‌شود (روی ۰ می‌ماند).
    - اگر `stats` (شیءِ PlayerStats) و `source` داده شود، مجموعِ XP آن منبع ثبت می‌شود.

    خروجی: دیکشنریِ {'leveled_up', 'levels', 'new_level', 'gained'}
    """
    # 🆕 مرحله ۲۷ — اعمالِ رویدادِ بونسِ XP (اونتِ ادمین). چون همه‌ی بخش‌هایِ بازی
    # XP را از همین تابع می‌گیرند، ضریب یک‌جا و برایِ همه‌ی منابع اعمال می‌شود.
    from app.data import events as _events

    amount = _events.apply_xp(int(amount or 0))
    if player.level >= MAX_LEVEL:
        player.xp = 0
        return {"leveled_up": False, "levels": 0, "new_level": player.level, "gained": 0}
    if amount <= 0:
        return {"leveled_up": False, "levels": 0, "new_level": player.level, "gained": 0}

    player.xp = int(player.xp or 0) + amount
    levels = 0
    while player.level < MAX_LEVEL and player.xp >= xp_needed(player.level):
        player.xp -= xp_needed(player.level)
        player.level += 1
        levels += 1
    if player.level >= MAX_LEVEL:
        player.xp = 0   # در سقف، XP معنایی ندارد

    if stats is not None and source:
        try:
            stats.xp_total = int(stats.xp_total or 0) + amount
        except AttributeError:
            pass

    return {
        "leveled_up": levels > 0,
        "levels": levels,
        "new_level": player.level,
        "gained": amount,
    }


async def grant_xp(session, player, amount: int, source: str = "") -> dict:
    """مرحله‌ی رفعِ باگِ v10 — دقیقاً مثلِ add_xp عمل می‌کند، با این تفاوت که
    PlayerStats را خودش می‌گیرد/می‌سازد تا فیلدِ xp_total (کلِ XP کسب‌شده در
    طولِ بازی) برایِ «همه‌ی» منابع به‌روزرسانی شود، نه فقط دزدی.

    قبلاً هر بخش باید خودش شیءِ stats را می‌ساخت و به add_xp می‌داد؛ چون فقط
    theft.py این کار را انجام می‌داد، xp_total فقط با دزدی بالا می‌رفت. از این‌پس
    همه‌جا کافیست به‌جایِ add_xp از grant_xp استفاده شود.
    """
    from app.models.player_stats import get_or_create_stats

    stats = await get_or_create_stats(session, player.tg_user_id)
    # بونس واقعی XP اشتراک: نقره‌ای +۱۰٪ و طلایی +۲۰٪.
    # پیش از اعمال رویداد XP در add_xp محاسبه می‌شود تا هر دو بونس با هم کار کنند.
    try:
        from app.services.subscription_service import active_tier
        from app.data.subscription import xp_bonus_pct
        pct = xp_bonus_pct(await active_tier(session, player.tg_user_id))
        amount = int(round(int(amount or 0) * (100 + pct) / 100))
    except Exception:
        pass
    return add_xp(player, amount, stats=stats, source=source)


def xp_note(res: dict) -> str:
    """یک خطِ کوتاهِ «✨ +N XP» (به‌همراه پیامِ لِول‌آپ در صورتِ وجود) برایِ چسباندن
    به پیامِ تأییدِ هر خرید/ارتقا. اگر XP‌ای اضافه نشده باشد رشته‌ی خالی می‌دهد.
    """
    gained = int((res or {}).get("gained") or 0)
    if gained <= 0:
        return ""
    line = f"\n✨ {gained} XP گرفتی!"
    if res.get("leveled_up"):
        line += f" 🆙 تبریک، رفتی سطح {res['new_level']}!"
    return line


def progress_str(player) -> str:
    """نمایشِ پیشرفتِ XP به شکلِ «۵۰ / ۱۰۰» (یا «MAX» در سقفِ سطح)."""
    if player.level >= MAX_LEVEL:
        return "MAX"
    return f"{int(player.xp or 0)} / {xp_needed(player.level)}"


def xp_remaining(player) -> int:
    """Stage 27: XP remaining to reach the next level (0 at max level)."""
    if player.level >= MAX_LEVEL:
        return 0
    return max(0, xp_needed(player.level) - int(player.xp or 0))


def progress_bar(player, slots: int = 10) -> str:
    """Stage 27: small textual progress bar for the profile card."""
    if player.level >= MAX_LEVEL:
        return "█" * slots
    need = xp_needed(player.level) or 1
    filled = int(min(slots, max(0, (int(player.xp or 0) * slots) // need)))
    return "█" * filled + "░" * (slots - filled)


def progress_line(player) -> str:
    """Stage 27: full progress line: bar + current/needed + remaining XP."""
    if player.level >= MAX_LEVEL:
        return "⚡ XP: MAX (به سقفِ سطح رسیده‌ای)"
    return (
        f"⚡ XP: {int(player.xp or 0):,} / {xp_needed(player.level):,}  {progress_bar(player)}\n"
        f"⏳ باقی‌مانده تا سطحِ {player.level + 1}: <b>{xp_remaining(player):,}</b> XP"
    )


def level_up_line(result: dict) -> str | None:
    """متنِ کوتاهِ لِوِل‌آپ برای افزودن به انتهایِ پیام‌ها (یا None)."""
    if not result.get("leveled_up"):
        return None
    lvl = result["new_level"]
    if lvl >= MAX_LEVEL:
        return f"🌟 <b>لِوِل آپ!</b> به سقفِ سطح (<b>{lvl}</b>) رسیدی! 👑"
    return f"🎉 <b>لِوِل آپ!</b> حالا سطح <b>{lvl}</b> هستی!"
