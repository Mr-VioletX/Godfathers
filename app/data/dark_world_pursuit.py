# -*- coding: utf-8 -*-
"""Stage 87.3 — pure strategic pursuit, hideout and counter-intelligence rules."""
from __future__ import annotations

from app.data import dark_world as D

THREAT_TTL_HOURS = 24
RECON_INTEL_COST = 1
MAX_CLUES = 3
FORGED_ID_COST = 95_000_000
FORGED_ID_MAX = 3
PRISON_MINUTES = 30

HEAT_BANDS = (
    (0, 20, "نامرئی", "هیچ پرونده فعالی روی میز نیست."),
    (20, 40, "زیر ذره‌بین", "ردهای پراکنده جمع می‌شوند؛ عملیات کمی سخت‌تر است."),
    (40, 60, "بازرسی", "یک واحد تحقیقاتی فعال است و تهدید پنهان شکل می‌گیرد."),
    (60, 80, "حکم تعقیب", "بازرسی‌ها سنگین‌اند؛ شناختن الگو قبل از واکنش حیاتی است."),
    (80, 101, "تعقیب سراسری", "شروع عملیات تازه قفل است تا تهدید جاری خنثی شود."),
)

THREAT_ORDER = ("paper_trail", "camera_net", "tactical_raid")
THREATS = {
    "paper_trail": {
        "name": "رد مالی", "icon": "🧾", "counter": "bribe",
        "intro": "کسی تراکنش‌ها و واسطه‌های تو را کنار هم می‌چیند.",
        "clues": (
            "حسابدار می‌گوید سه پرداخت کوچک با یک امضای مشترک علامت خورده‌اند.",
            "مأمورهای دیده‌شده لباس رسمی دارند، اما واحد عملیاتی همراهشان نیست.",
            "یک واسطه برای پاک‌کردن نامت، عددی دقیق پیشنهاد داده است.",
        ),
    },
    "camera_net": {
        "name": "شبکه مراقبت", "icon": "📹", "counter": "relocate",
        "intro": "مسیرهایت آرام‌آرام در یک نقشه دیجیتال بسته می‌شوند.",
        "clues": (
            "خودروی بی‌نشان در سه مسیر متفاوت، فاصله‌ای یکسان را حفظ کرده است.",
            "دوربین یک تقاطع برخلاف بقیه شهر، هر شب دقیقاً ساعت ثابتی می‌چرخد.",
            "خبرچین هیچ نامی در اداره پیدا نکرد؛ ردگیری از خیابان انجام می‌شود.",
        ),
    },
    "tactical_raid": {
        "name": "یورش تاکتیکی", "icon": "🚨", "counter": "fortify",
        "intro": "تیم واکنش منتظر یک اشتباه برای شکستن در مخفیگاه است.",
        "clues": (
            "دو ون سنگین نزدیک محله پارک شده‌اند و پلاک هر دو تازه است.",
            "برق کوچه برای چند ثانیه قطع شد؛ کسی زمان پشتیبان را اندازه گرفت.",
            "نگهبان صدای بی‌سیم کوتاه و قدم‌های هماهنگ پشت دیوار شنیده است.",
        ),
    },
}

ACTION_ORDER = ("bribe", "relocate", "fortify", "disguise")
ACTIONS = {
    "bribe": {
        "name": "خریدن زنجیره اداری", "icon": "🤝", "cash": 120_000_000,
        "energy": 4, "intel": 0, "description": "بهترین پاسخ به رد مالی؛ در برابر یورش تقریباً بی‌اثر.",
    },
    "relocate": {
        "name": "جابجایی با مسیر فریب", "icon": "🚚", "cash": 75_000_000,
        "energy": 18, "intel": 1, "description": "شبکه دوربین را با چند مقصد جعلی گمراه می‌کند.",
    },
    "fortify": {
        "name": "تله و دفاع لایه‌ای", "icon": "🛡️", "cash": 55_000_000,
        "energy": 22, "intel": 2, "description": "پاسخ اصلی به یورش؛ مقابل پرونده مالی فقط زمان می‌خرد.",
    },
    "disguise": {
        "name": "سوزاندن هویت و جعل تازه", "icon": "🎭", "cash": 0,
        "energy": 10, "intel": 0, "forged_id": 1,
        "description": "پاسخ منعطف اما محدود؛ یک هویت جعلی مصرف می‌شود.",
    },
}

# Player reasoning matters: matching the observed threat is far stronger than blind clicking.
MATCHUP_CHANCE = {
    "paper_trail": {"bribe": 84, "relocate": 46, "fortify": 30, "disguise": 64},
    "camera_net": {"bribe": 34, "relocate": 84, "fortify": 45, "disguise": 68},
    "tactical_raid": {"bribe": 24, "relocate": 42, "fortify": 86, "disguise": 58},
}
HEAT_REDUCTION = {"bribe": 26, "relocate": 30, "fortify": 34, "disguise": 24}
FAIL_HEAT = {"bribe": 13, "relocate": 11, "fortify": 9, "disguise": 16}

HIDEOUT_LEVELS = {
    1: {"name": "اتاق پشتی", "upgrade_cost": 220_000_000, "influence": 75},
    2: {"name": "خانه امن", "upgrade_cost": 550_000_000, "influence": 200},
    3: {"name": "پناهگاه زیرزمینی", "upgrade_cost": 1_200_000_000, "influence": 500},
    4: {"name": "دژ بی‌نام", "upgrade_cost": 2_500_000_000, "influence": 1100},
    5: {"name": "شهر زیر شهر", "upgrade_cost": 0, "influence": 2300},
}


def clamp(value: int | float, low: int | float, high: int | float):
    return max(low, min(high, value))


def heat_band(heat: int) -> dict:
    value = int(clamp(int(heat or 0), 0, D.HEAT_MAX))
    for low, high, name, description in HEAT_BANDS:
        if low <= value < high:
            return {"low": low, "high": high - 1, "name": name, "description": description}
    return {"low": 80, "high": 100, "name": "تعقیب سراسری", "description": HEAT_BANDS[-1][3]}


def get_threat(key: str | None) -> dict | None:
    return THREATS.get(str(key or ""))


def get_action(key: str | None) -> dict | None:
    return ACTIONS.get(str(key or ""))


def hideout(level: int) -> dict:
    return HIDEOUT_LEVELS[int(clamp(int(level or 1), 1, 5))]


def action_chance(threat_key: str, action_key: str, *, heat: int, hideout_level: int,
                  clue_count: int, has_fixer: bool = False) -> dict:
    if threat_key not in THREATS or action_key not in ACTIONS:
        return {}
    base = MATCHUP_CHANCE[threat_key][action_key]
    level_bonus = (int(clamp(hideout_level, 1, 5)) - 1) * 3
    intel_bonus = int(clamp(clue_count, 0, MAX_CLUES)) * 2
    fixer_bonus = 5 if has_fixer and action_key in ("bribe", "disguise") else 0
    heat_penalty = max(0, int(heat or 0) - 60) * .20
    chance = round(float(clamp(base + level_bonus + intel_bonus + fixer_bonus - heat_penalty, 12, 95)), 2)
    return {
        "chance": chance, "base": base, "level_bonus": level_bonus,
        "intel_bonus": intel_bonus, "fixer_bonus": fixer_bonus,
        "heat_penalty": round(heat_penalty, 2),
        "is_counter": THREATS[threat_key]["counter"] == action_key,
    }


def resolve_action(threat_key: str, action_key: str, roll: float, *, heat: int,
                   hideout_level: int, clue_count: int, has_fixer: bool = False) -> dict:
    info = action_chance(threat_key, action_key, heat=heat, hideout_level=hideout_level,
                         clue_count=clue_count, has_fixer=has_fixer)
    if not info:
        return {}
    success = float(roll) < float(info["chance"])
    if success:
        reduction = HEAT_REDUCTION[action_key] + (hideout_level - 1) * 2 + (5 if info["is_counter"] else 0)
        return {"success": True, "chance": info["chance"], "heat_delta": -int(reduction),
                "integrity_delta": 0, "jailed": False, "is_counter": info["is_counter"]}
    fail_heat = FAIL_HEAT[action_key] + (5 if threat_key == "tactical_raid" else 0)
    integrity = -max(4, 18 - hideout_level * 2) if threat_key == "tactical_raid" else -4
    jailed = int(heat or 0) + fail_heat >= 95
    return {"success": False, "chance": info["chance"], "heat_delta": int(fail_heat),
            "integrity_delta": integrity, "jailed": jailed, "is_counter": info["is_counter"]}


def operation_locked(heat: int) -> bool:
    return int(heat or 0) >= 80


def threat_required(heat: int) -> bool:
    return int(heat or 0) >= 40
