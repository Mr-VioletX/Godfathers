# -*- coding: utf-8 -*-
"""مرحله ۱۹.۲ — منطقِ خالصِ «بانکِ مافیایی».

ثروتِ خالص (net worth) = نقدینگی + درآمدِ روزانه + ارزشِ شهرها + ارزشِ کشورها.
بانکِ مافیایی: سپرده (سودِ روزانه)، وام (با بهره) و رتبه‌بندیِ ثروتمندان.
کاملاً خالص تا مستقل تست شود.
"""
from __future__ import annotations

WORLDBANK_UNLOCK_LEVEL = 16

# سپرده
DEPOSIT_DAILY_RATE = 0.02        # ۲٪ سودِ روزانه
DEPOSIT_MAX_DAYS = 30            # سقفِ روزهای محاسبه‌ی سود

# وام — سقفِ وام تابعی از ثروتِ خالص است
LOAN_MAX_RATIO = 0.5            # حداکثر ۵۰٪ِ ثروتِ خالص
LOAN_DAILY_INTEREST = 0.03      # ۳٪ بهره‌ی روزانه
LOAN_MAX_DAYS = 30

# رده‌های بانکی بر اساسِ ثروتِ خالص
TIERS = [
    (0, "🪙 عادی", 0.02),
    (5_000_000, "🥈 نقره‌ای", 0.025),
    (25_000_000, "🥇 طلایی", 0.03),
    (100_000_000, "💎 پلاتینی", 0.035),
    (500_000_000, "👑 ثروتمندِ جهانی", 0.04),
]


def net_worth(cash: int, daily_income: int, city_value: int, country_value: int) -> int:
    """ثروتِ خالص = نقدینگی + درآمدِ روزانه + ارزشِ شهرها + ارزشِ کشورها."""
    return int(max(0, cash) + max(0, daily_income) + max(0, city_value) + max(0, country_value))


def tier_for(net: int):
    label, rate = TIERS[0][1], TIERS[0][2]
    for threshold, name, r in TIERS:
        if net >= threshold:
            label, rate = name, r
        else:
            break
    return label, rate


def next_tier(net: int):
    for threshold, name, r in TIERS:
        if net < threshold:
            return threshold, name
    return None


def deposit_rate_for(net: int) -> float:
    return tier_for(net)[1]


def deposit_interest(amount: int, days: int, rate: float) -> int:
    """سودِ ساده‌ی سپرده تا سقفِ روزها."""
    d = max(0, min(int(days), DEPOSIT_MAX_DAYS))
    return int(max(0, amount) * rate * d)


def max_loan(net: int, current_debt: int) -> int:
    cap = int(max(0, net) * LOAN_MAX_RATIO)
    return max(0, cap - max(0, current_debt))


def loan_due(principal: int, days: int) -> int:
    """مبلغِ قابلِ بازپرداختِ وام با بهره‌ی ساده."""
    d = max(0, min(int(days), LOAN_MAX_DAYS))
    return int(max(0, principal) * (1 + LOAN_DAILY_INTEREST * d))


# --------------------------- گاوصندوق (امنیت پول از جنگ/جاسوسی) ---------------------------
# v1.7.7.6 — بدون سود؛ فقط فضای امن
SAFEBOX_MAX_LEVEL = 100
SAFEBOX_COST_L1 = 10_000_000_000          # ۱۰ میلیارد پایه
SAFEBOX_COST_L100 = 1_000_000_000_000     # ۱ تریلیون در لول ۱۰۰
SAFEBOX_CAP_L1 = 15_000_000_000           # ۱۵ میلیارد
SAFEBOX_CAP_L100 = 1_500_000_000_000      # ۱.۵ تریلیون
DEPOSIT_WAR_SAFE_PCT = 50                 # default; live value via admin panel
DEPOSIT_WAR_LOOTABLE_PCT = 50             # = 100 - safe pct


# ---------------------------------------------------------------------------
# v1.7.8.2 — اعدادِ قابلِ تنطیم از ادمین‌مود (کلیدهای GameNumberSetting)
# مقدارِ پایه در کد، مقدارِ موّر در دیتابیس — همان الگوی بخشِ شهر.
# ---------------------------------------------------------------------------
BANK_SAFE_PCT_KEY = "bank.war_safe_pct"
SAFEBOX_COST_L1_KEY = "bank.safebox_cost_l1"
SAFEBOX_COST_L100_KEY = "bank.safebox_cost_l100"
SAFEBOX_CAP_L1_KEY = "bank.safebox_cap_l1"
SAFEBOX_CAP_L100_KEY = "bank.safebox_cap_l100"

DEFAULT_WAR_SAFE_PCT = 50
DEFAULT_SAFEBOX_COST_L1 = SAFEBOX_COST_L1
DEFAULT_SAFEBOX_COST_L100 = SAFEBOX_COST_L100
DEFAULT_SAFEBOX_CAP_L1 = SAFEBOX_CAP_L1
DEFAULT_SAFEBOX_CAP_L100 = SAFEBOX_CAP_L100

# کشِ runtime — با refresh_bank_settings از DB به‌روز می‌شود
_runtime_safe_pct = DEFAULT_WAR_SAFE_PCT
_runtime_cost_l1 = DEFAULT_SAFEBOX_COST_L1
_runtime_cost_l100 = DEFAULT_SAFEBOX_COST_L100
_runtime_cap_l1 = DEFAULT_SAFEBOX_CAP_L1
_runtime_cap_l100 = DEFAULT_SAFEBOX_CAP_L100


def get_war_safe_pct() -> int:
    """درصدِ سپرده که در جنگ/جاسوسی امن است (۰..۱۰۰)."""
    try:
        return int(max(0, min(100, int(_runtime_safe_pct))))
    except (TypeError, ValueError):
        return int(DEFAULT_WAR_SAFE_PCT)


def get_war_lootable_pct() -> int:
    """مکملِ درصدِ امن — جمعِ این دو همیشه ۱۰۰ است."""
    return 100 - get_war_safe_pct()


def _pos_int(value, fallback) -> int:
    try:
        out = int(round(float(value)))
    except (TypeError, ValueError):
        return int(fallback)
    return out if out > 0 else int(fallback)


def get_safebox_cost_l1() -> int:
    return _pos_int(_runtime_cost_l1, DEFAULT_SAFEBOX_COST_L1)


def get_safebox_cost_l100() -> int:
    return _pos_int(_runtime_cost_l100, DEFAULT_SAFEBOX_COST_L100)


def get_safebox_cap_l1() -> int:
    return _pos_int(_runtime_cap_l1, DEFAULT_SAFEBOX_CAP_L1)


def get_safebox_cap_l100() -> int:
    return _pos_int(_runtime_cap_l100, DEFAULT_SAFEBOX_CAP_L100)


def set_runtime_bank(
    safe_pct=None,
    cost_l1=None,
    cost_l100=None,
    cap_l1=None,
    cap_l100=None,
) -> None:
    """کشِ runtime را عوض می‌کند. هر مقدارِ None دست‌نخورده می‌ماند."""
    global _runtime_safe_pct, _runtime_cost_l1, _runtime_cost_l100
    global _runtime_cap_l1, _runtime_cap_l100
    if safe_pct is not None:
        try:
            _runtime_safe_pct = int(max(0, min(100, int(round(float(safe_pct))))))
        except (TypeError, ValueError):
            pass
    if cost_l1 is not None:
        _runtime_cost_l1 = _pos_int(cost_l1, DEFAULT_SAFEBOX_COST_L1)
    if cost_l100 is not None:
        _runtime_cost_l100 = _pos_int(cost_l100, DEFAULT_SAFEBOX_COST_L100)
    if cap_l1 is not None:
        _runtime_cap_l1 = _pos_int(cap_l1, DEFAULT_SAFEBOX_CAP_L1)
    if cap_l100 is not None:
        _runtime_cap_l100 = _pos_int(cap_l100, DEFAULT_SAFEBOX_CAP_L100)


def bank_snapshot() -> dict:
    return {
        "safe_pct": get_war_safe_pct(),
        "lootable_pct": get_war_lootable_pct(),
        "cost_l1": get_safebox_cost_l1(),
        "cost_l100": get_safebox_cost_l100(),
        "cap_l1": get_safebox_cap_l1(),
        "cap_l100": get_safebox_cap_l100(),
    }


# کلید → (عنوان، پیش‌فرض، راهنما)
BANK_SETTING_META = {
    BANK_SAFE_PCT_KEY: (
        "درصدِ محافظتِ سپرده",
        DEFAULT_WAR_SAFE_PCT,
        "عددی بین ۰ تا ۱۰۰. مقدارِ 50 یعنی نیمی از سپرده در جنگ امن است",
    ),
    SAFEBOX_COST_L1_KEY: (
        "هزینهٔ گاوصندوق در لول ۱",
        DEFAULT_SAFEBOX_COST_L1,
        "هزینهٔ خریدِ اولین سطح؛ قیمت تا لول ۱۰۰ خطی بالا می‌رود",
    ),
    SAFEBOX_COST_L100_KEY: (
        "هزینهٔ گاوصندوق در لول ۱۰۰",
        DEFAULT_SAFEBOX_COST_L100,
        "هزینهٔ آخرین سطح؛ سقفِ خطِ قیمت",
    ),
    SAFEBOX_CAP_L1_KEY: (
        "سقفِ گاوصندوق در لول ۱",
        DEFAULT_SAFEBOX_CAP_L1,
        "چقدر پول در سطحِ یک جا می‌شود",
    ),
    SAFEBOX_CAP_L100_KEY: (
        "سقفِ گاوصندوق در لول ۱۰۰",
        DEFAULT_SAFEBOX_CAP_L100,
        "بیشترین پولی که یک بازیکن می‌تواند کاملاً امن کند",
    ),
}


def safebox_cost(level: int) -> int:
    """هزینه ارتقا از level به level+1 (خطی از L1 تا L100)."""
    cur = max(0, int(level or 0))
    if cur >= SAFEBOX_MAX_LEVEL:
        return 0
    if SAFEBOX_MAX_LEVEL <= 1:
        return int(get_safebox_cost_l1())
    # قیمت خرید/ارتقا به لول n (1-based): خطی
    # cost to go from n-1 -> n uses price at level n
    n = cur + 1  # target level
    if n <= 1:
        return int(get_safebox_cost_l1())
    # linear: price(n) = L1 + (L100-L1)*(n-1)/(100-1)
    t = (n - 1) / (SAFEBOX_MAX_LEVEL - 1)
    return int(round(get_safebox_cost_l1() + (get_safebox_cost_l100() - get_safebox_cost_l1()) * t))


def safebox_capacity(level: int) -> int:
    """ظرفیت گاوصندوق در لول داده‌شده (0 = 0)."""
    lv = max(0, min(SAFEBOX_MAX_LEVEL, int(level or 0)))
    if lv <= 0:
        return 0
    if lv == 1:
        return int(get_safebox_cap_l1())
    t = (lv - 1) / (SAFEBOX_MAX_LEVEL - 1)
    return int(round(get_safebox_cap_l1() + (get_safebox_cap_l100() - get_safebox_cap_l1()) * t))


def lootable_bank_deposit(deposit: int, safebox_balance: int = 0) -> int:
    """بخش غارت‌پذیر سپرده = ۵۰٪ از (سپرده − موجودی گاوصندوق امن)."""
    dep = max(0, int(deposit or 0))
    safe = max(0, min(dep, int(safebox_balance or 0)))
    exposed = max(0, dep - safe)
    return int(exposed * get_war_lootable_pct() // 100)


def lootable_wealth(cash: int, deposit: int, safebox_balance: int = 0) -> int:
    """ثروت قابل‌غارت = نقد + ۵۰٪ سپردهٔ غیرگاوصندوق."""
    return max(0, int(cash or 0)) + lootable_bank_deposit(deposit, safebox_balance)

