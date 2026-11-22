# -*- coding: utf-8 -*-
"""v1.7.9.1 — ارتشِ اتحادیه (سربازخانه): ۱۷ واحد در ۷ دسته با نام‌های مستقلِ مافیایی.

قواعدِ قفل‌شده (تأیید امیر):
  • آمار و سیستمِ سنگ‌کاغذقیچی دقیقاً از app/data/military.py مشتق می‌شود — هر واحد
    متناظرِ یک واحدِ جنگِ عادی است (همان atk/def/hp و همان ضرایبِ counter).
  • هزینه‌ی تولید = ۵ × جنگِ عادی.
  • ارتقای سطحِ واحد / سربازخانه / سقفِ اعضا = ۳۰ × بخشِ عادی و فقط از صندوق.
  • تولید به‌صورتِ اسکادران (گروهی): پیاده/تسلیحات ۲۰تایی، زرهی/پدافند ۱۰تایی،
    موشکی/جنگنده/بمب‌افکن ۵تایی.
  • نیروها فقط متعلق به اتحادیه‌اند و با پولِ شخصی ساخته نمی‌شوند.
"""
from __future__ import annotations

from app.data import military as M
from app.data import alliance as A

# --------------------------- ثابت‌ها ---------------------------
PROD_COST_MULT = 5          # هزینه‌ی تولید نسبت به جنگِ عادی
UPGRADE_COST_MULT = 30      # هزینه‌ی ارتقا نسبت به بخشِ عادی
MAX_UNIT_LEVEL = M.MAX_UNIT_LEVEL
UPGRADE_POWER_STEP = M.UPGRADE_POWER_STEP

SQUADRON_BY_CAT = {
    "soldier": 20,
    "weapon": 20,
    "tank": 10,
    "aa": 10,
    "missile": 5,
    "fighter": 5,
    "bomber": 5,
}

CATEGORY_LABELS = {
    "soldier": "🪖 پیاده",
    "weapon": "🔫 تسلیحاتِ سبک",
    "tank": "🛡️ زرهی",
    "aa": "🎯 پدافند",
    "missile": "🚀 موشکی",
    "fighter": "✈️ جنگنده",
    "bomber": "🛩️ بمب‌افکن",
}
CATEGORY_ORDER = ["soldier", "weapon", "tank", "aa", "missile", "fighter", "bomber"]

# (کلیدِ جنگِ عادی, کلیدِ اتحادیه, نام, رده)
_MAP = [
    ("militia",        "a_s1", "🗡️ شمشیرهای خاموش",     1),
    ("rifleman",       "a_s2", "🥷 لژیون سایه",          2),
    ("commando",       "a_s3", "💀 گارد مرگ",            3),
    ("pistol",         "a_w1", "🔫 زرادخانه‌ی خانواده",  1),
    ("rifle",          "a_w2", "💣 آرسیمال انتقام",      2),
    ("rpg",            "a_w3", "☠️ زرادخانه‌ی آخرالزمان", 3),
    ("apc",            "a_t1", "🛡️ دیوار آهنین",         1),
    ("tank",           "a_t2", "🦾 غول فولادی",          2),
    ("heavy_tank",     "a_t3", "⚙️ لشکر تایتان",         3),
    ("aa_gun",         "a_a1", "🌩️ تندر شب",             1),
    ("sam",            "a_a2", "🛰️ گنبد آهنین",          2),
    ("rocket",         "a_m1", "🐍 نیش افعی",            1),
    ("ballistic",      "a_m2", "☢️ اژدهای آتشین",        2),
    ("fighter",        "a_f1", "🦅 شاهین تاریکی",        1),
    ("jet",            "a_f2", "⚡ صاعقه‌ی شب",           2),
    ("bomber",         "a_b1", "🌑 هلال سیاه",           1),
    ("stealth_bomber", "a_b2", "👹 شبح ویرانگر",         2),
]

ALLIANCE_UNITS: dict[str, dict] = {}
UNIT_ORDER: list[str] = []
A2B: dict[str, str] = {}   # alliance key → base (normal war) key
B2A: dict[str, str] = {}   # base key → alliance key

for _base, _key, _name, _tier in _MAP:
    _bu = M.UNITS[_base]
    ALLIANCE_UNITS[_key] = {
        "cat": _bu["cat"],
        "name": _name,
        "tier": _tier,
        "base": _base,
        "dclass": _bu["dclass"],
        "can_hit": list(_bu.get("can_hit") or []),
        "atk": int(_bu["atk"]),
        "def": int(_bu["def"]),
        "hp": int(_bu["hp"]),
        "cost": int(_bu["cost"]) * PROD_COST_MULT,
        "vs": dict(_bu.get("vs") or {}),
        "squad": SQUADRON_BY_CAT[_bu["cat"]],
        "unlock_barracks": _tier,          # T1 ← سربازخانه ۱، T2 ← ۲، T3 ← ۳
    }
    if _bu.get("wpn_bonus"):
        ALLIANCE_UNITS[_key]["wpn_bonus"] = int(_bu["wpn_bonus"])
    UNIT_ORDER.append(_key)
    A2B[_key] = _base
    B2A[_base] = _key


def get_unit(key: str) -> dict | None:
    return ALLIANCE_UNITS.get(key)


def units_in_category(cat: str) -> list[str]:
    return [k for k in UNIT_ORDER if ALLIANCE_UNITS[k]["cat"] == cat]


def to_base_stacks(stacks) -> list[tuple[str, int, int]]:
    """پشته‌های اتحادیه → پشته‌های جنگِ عادی (برای موتورِ شبیه‌سازی)."""
    return [(A2B.get(k, k), int(c), int(lv)) for k, c, lv in stacks]


def to_alliance_losses(losses: dict) -> dict:
    """تلفاتِ برگشتی از موتور (کلیدهای عادی) → کلیدهای اتحادیه."""
    out: dict[str, int] = {}
    for k, v in (losses or {}).items():
        ak = B2A.get(k, k)
        out[ak] = out.get(ak, 0) + int(v)
    return out


def level_multiplier(level: int) -> float:
    return M.level_multiplier(level)


def unit_power(unit_key: str, count: int, level: int) -> int:
    u = ALLIANCE_UNITS.get(unit_key)
    if not u or count <= 0:
        return 0
    return M.unit_power(u["base"], int(count), int(level))


def stacks_power(stacks) -> int:
    return sum(unit_power(k, c, lv) for k, c, lv in stacks)


def squad_size(unit_key: str) -> int:
    u = ALLIANCE_UNITS.get(unit_key)
    return int(u["squad"]) if u else 1


def squad_cost(unit_key: str, squads: int = 1) -> int:
    """هزینه‌ی تولیدِ n اسکادران (قیمتِ واحد ×۵ قبلاً اعمال شده)."""
    u = ALLIANCE_UNITS.get(unit_key)
    if not u:
        return 0
    return int(u["cost"]) * int(u["squad"]) * max(1, int(squads))


def unit_upgrade_cost(unit_key: str, level: int) -> int:
    """هزینه‌ی ارتقای سطحِ واحد = ۳۰ × فرمولِ جنگِ عادی (cost × ۲۲ × (level+1))."""
    u = ALLIANCE_UNITS.get(unit_key)
    if not u:
        return 0
    base = M.UNITS[u["base"]]
    return int(base["cost"] * 22 * (max(0, int(level)) + 1)) * UPGRADE_COST_MULT


def train_seconds(unit_key: str, squads: int = 1) -> int:
    """زمانِ تولیدِ n اسکادران — خطی مثل جنگِ عادی."""
    u = ALLIANCE_UNITS.get(unit_key)
    if not u:
        return 0
    qty = int(u["squad"]) * max(1, int(squads))
    return M.train_seconds(u["base"], qty)


# --------------------------- سربازخانه ---------------------------
BARRACKS_MAX_LEVEL = 10
BARRACKS_BASE_CAPACITY = 1_000


def barracks_capacity(level: int) -> int:
    """ظرفیتِ کلِ نیرو: سطح ۱ = ۱٬۰۰۰ و هر سطح ×۲ تا سطح ۱۰ = ۵۱۲٬۰۰۰."""
    lvl = max(1, min(BARRACKS_MAX_LEVEL, int(level)))
    return BARRACKS_BASE_CAPACITY * (2 ** (lvl - 1))


def barracks_upgrade_cost(level: int) -> int:
    """۳۰ × مبنای سربازخانه‌ی عادی (۵۰۰M) به‌ازای سطحِ فعلی."""
    return 30 * M.BARRACKS_BASE_COST * max(1, int(level))


def member_cap_upgrade_cost(level: int) -> int:
    """۳۰ × هزینه‌ی فعلیِ ارتقای سقفِ اعضا."""
    return A.cap_upgrade_cost(level) * UPGRADE_COST_MULT


# --------------------------- تولیدِ خودکارِ روزانه ---------------------------
def auto_build_plan(
    alive_counts: dict,
    healable_counts: dict,
    queued_counts: dict,
    capacity_free: int,
    minimums: dict,
    treasury: int,
) -> list[tuple[str, int, int]]:
    """برنامه‌ی تولیدِ خودکار (روزانه) — منطقِ تأییدشده:

    ۱. نیروهای قابل‌درمانِ بیمارستان به حداقل حساب می‌شوند.
    ۲. ظرفیتِ خالیِ سربازخانه چک می‌شود.
    ۳. اگر خزانه پولِ کافی دارد تا رسیدن به حداقل تولید می‌کند.
    ۴. نیرویِ مرده‌ی بیمارستان در healable نیست → کمبودش فردا دوباره ساخته می‌شود.

    خروجی: [(unit_key, squads, cost)]
    """
    plan: list[tuple[str, int, int]] = []
    free = max(0, int(capacity_free))
    budget = max(0, int(treasury))
    for key in UNIT_ORDER:
        u = ALLIANCE_UNITS[key]
        mn = max(0, int((minimums or {}).get(key, 0) or 0))
        if mn <= 0:
            continue
        squad = int(u["squad"])
        effective = (
            int((alive_counts or {}).get(key, 0) or 0)
            + int((healable_counts or {}).get(key, 0) or 0)
            + int((queued_counts or {}).get(key, 0) or 0)
        )
        need = mn - effective
        if need <= 0:
            continue
        squads = (need + squad - 1) // squad
        while squads > 0:
            units = squads * squad
            cost = units * int(u["cost"])
            if units <= free and cost <= budget:
                plan.append((key, squads, cost))
                free -= units
                budget -= cost
                break
            squads -= 1
    return plan


# --------------------------- راهنمای سنگ‌کاغذقیچی ---------------------------
def rps_guide() -> str:
    return (
        "📖 <b>راهنمای ارتشِ اتحادیه — سنگ‌کاغذقیچی</b>\n\n"
        "هر دسته نقطه‌ی قوت و ضعف دارد؛ ترکیبِ درست مهم‌تر از تعدادِ صِرف است:\n\n"
        "🪖 <b>پیاده</b> — ستونِ ارتش؛ ارزان و سریع. کماندوهای «گارد مرگ» به پدافند و موشکی ضربه‌ی سنگین می‌زنند.\n"
        "🔫 <b>تسلیحاتِ سبک</b> — نیروی مستقل نیست؛ حمله‌ی پیاده را بالا می‌برد (بدون پیاده بی‌فایده است).\n"
        "🛡️ <b>زرهی</b> — شکافنده‌ی خطِ زمینی؛ در برابرِ حمله‌ی هوایی بی‌پناه است.\n"
        "🎯 <b>پدافند</b> — فقط اهدافِ هوایی را می‌زند؛ برابرِ جنگنده/بمب‌افکن حیاتی است، برابرِ زمینی بی‌اثر.\n"
        "🚀 <b>موشکی</b> — ضربه‌ی سنگینِ زمینی با بدنه‌ی ضعیف؛ باید محافظت شود.\n"
        "✈️ <b>جنگنده</b> — آسمان را پاک می‌کند و به زمین هم می‌زند.\n"
        "🛩️ <b>بمب‌افکن</b> — مرگبار برای زمینی‌ها؛ اگر پدافندِ حریف زنده باشد قربانی می‌شود.\n\n"
        "⚠️ ارتشِ تک‌بُعدی ریسک دارد: حریف از نقطه‌ضعفت می‌زند.\n"
        "💰 تولید فقط از <b>صندوقِ اتحادیه</b> و به‌صورتِ اسکادرانی انجام می‌شود؛ "
        "هزینه‌ی تولید ۵ برابرِ جنگِ عادی و ارتقاها ۳۰ برابر است."
    )


# --------------------------- 🆕 v1.8.2.0 — انتخابِ تعدادِ اسکادران ---------------------------
def squad_unit_cost(unit_key: str) -> int:
    """هزینه‌ی «یک» اسکادران (قیمتِ واحد ×۵ قبلاً در cost اعمال شده)."""
    u = ALLIANCE_UNITS.get(unit_key)
    if not u:
        return 0
    return int(u["cost"]) * int(u["squad"])


def max_squads_possible(unit_key: str, capacity_free_units: int, treasury: int) -> int:
    """حداکثرِ اسکادرانِ قابلِ ساختِ همین‌حالا — طبقِ ظرفیتِ خالیِ سربازخانه و صندوق."""
    u = ALLIANCE_UNITS.get(unit_key)
    if not u:
        return 0
    per_squad = squad_unit_cost(unit_key)
    squad = int(u["squad"])
    if per_squad <= 0 or squad <= 0:
        return 0
    by_capacity = max(0, int(capacity_free_units)) // squad
    by_treasury = max(0, int(treasury)) // per_squad
    return max(0, min(by_capacity, by_treasury))


def squad_preset_options(unit_key: str, max_squads: int) -> list[int]:
    """دکمه‌های آماده‌ی تعداد (مثلِ ۱/۲۵۰/۵۰۰/۱۰۰۰ جنگِ عادی ولی در مقیاسِ اسکادران)."""
    mx = max(0, int(max_squads))
    return [n for n in (1, 2, 5, 10) if n <= mx]
