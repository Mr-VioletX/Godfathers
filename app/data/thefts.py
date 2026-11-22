# -*- coding: utf-8 -*-
# ثابت‌های بازی برای سیستمِ دزدی (بازطراحیِ مرحله ۱۶)

COOLDOWN_SECONDS = 120          # کول‌داونِ پایه (۵ دقیقه)؛ در عمل از بخشِ کاپولا خوانده می‌شود
MAX_FATIGUE = 100               # سقف (اوج) خستگی
FATIGUE_PEAK = 100              # در این خستگی کاربر نمی‌تواند دزدی کند
FATIGUE_RECOVERY_PER_MIN = 6    # 🔄 مرحله ۱۶: ریکاوریِ پایه = ۱ واحد/دقیقه (اوج در ~۱۰۰ دقیقه رفع می‌شود)
FATIGUE_RISK_FACTOR = 0.005     # هر واحد خستگی چقدر به ریسک اضافه می‌کند
SKILL_RISK_FACTOR = 0.003       # هر سطح چقدر ریسک را کم می‌کند (لولِ بالاتر = ریسکِ کمترِ دزدیِ سطح‌پایین)

# --- زندان (مرحله ۱۶) ---
JAIL_MINUTES = 5               # مدتِ زندان
JAIL_SECONDS = JAIL_MINUTES * 60
BRIBE_LIMIT = 10                # پس از ۱۰ بار پرداختِ باج، در ۱۱مین دستگیری زندانِ اجباری
JAIL_BRIBE_BASE = 3_000          # باجِ کامل = JAIL_BRIBE_BASE × لولِ بازیکن (برای ۱۵ دقیقهٔ کامل)


# انواع دزدی (هرچه سطح بالاتر، پاداش و ریسک بیشتر)
# keywords → کلماتی که کاربر می‌تواند در گروه بنویسد تا همان دزدی انجام شود
THEFTS = [
    {"key": "pickpocket", "name": "🧤 جیب‌بری",        "min_level": 1, "base_risk": 0.05, "min_reward": 50,   "max_reward": 200,   "fatigue": 10, "xp": 5,
     "keywords": ["جیب بری", "جیب‌بری", "جیب‌زنی", "جیب زنی"]},
    {"key": "shop",       "name": "🏪 دزدی از مغازه",  "min_level": 3, "base_risk": 0.10, "min_reward": 200,  "max_reward": 600,   "fatigue": 15, "xp": 12,
     "keywords": ["دزدی مغازه", "سرقت مغازه", "مغازه"]},
    {"key": "house",      "name": "🏠 دزدی از خانه",   "min_level": 5, "base_risk": 0.15, "min_reward": 500,  "max_reward": 1500,  "fatigue": 20, "xp": 25,
     "keywords": ["دزدی خانه", "سرقت خانه", "خانه"]},
    {"key": "car",        "name": "🚗 سرقت خودرو",     "min_level": 7, "base_risk": 0.22, "min_reward": 1500, "max_reward": 4000,  "fatigue": 30, "xp": 45,
     "keywords": ["سرقت خودرو", "سرقت ماشین", "دزدی ماشین", "ماشین"]},
    {"key": "jewelry",    "name": "💎 سرقت جواهرفروشی", "min_level": 9, "base_risk": 0.30, "min_reward": 4000, "max_reward": 10000, "fatigue": 40, "xp": 80,
     "keywords": ["سرقت جواهر", "جواهرفروشی", "طلافروشی", "جواهر"]},
]


def available_thefts(level: int):
    """لیست دزدی‌های باز‌شده برای این سطح"""
    return [t for t in THEFTS if level >= t["min_level"]]


def best_theft(level: int):
    """بهترین (پرسودترین) دزدی باز‌شده"""
    avail = available_thefts(level)
    return avail[-1] if avail else None


def get_theft(key: str):
    """پیدا کردن یک دزدی با کلید آن"""
    for t in THEFTS:
        if t["key"] == key:
            return t
    return None


def _norm(text: str) -> str:
    return " ".join((text or "").strip().replace("‌", " ").split())


def theft_by_keyword(text: str):
    """اگر متنِ کاربر دقیقاً کلمه‌ی یک دزدی باشد، دیکشنریِ آن دزدی را برمی‌گرداند (یا None)."""
    q = _norm(text)
    if not q:
        return None
    for t in THEFTS:
        for kw in t.get("keywords", []):
            if _norm(kw) == q:
                return t
    return None


def compute_risk(theft: dict, level: int, fatigue: int, risk_reduction: float = 0.0) -> float:
    """احتمالِ دستگیریِ شخصی‌شده‌ی یک دزدی (پیش از اثرِ ایونت).

    خستگی ریسک را بالا می‌برد؛ لول و ویژگی‌های پایگاه/کاپولا آن را پایین می‌آورند.
    خروجی بینِ ۰٫۰۲ تا ۰٫۹۵ کلیپ می‌شود.
    """
    p = (
        theft["base_risk"]
        + int(fatigue or 0) * FATIGUE_RISK_FACTOR
        - int(level or 0) * SKILL_RISK_FACTOR
        - float(risk_reduction or 0.0)
    )
    return min(0.95, max(0.02, p))


def full_bribe(level: int) -> int:
    """باجِ کامل (برای خریدنِ کلِ ۱۵ دقیقهٔ زندان)."""
    return JAIL_BRIBE_BASE * max(1, int(level or 1))


def bribe_for_remaining(level: int, remaining_seconds: int) -> int:
    """باجِ وابسته به زمانِ باقی‌مانده: هر دقیقه کمتر، ارزان‌تر (گرد به بالای دقیقه).

    مثال: ۱۴:۳۰ باقی → ۱۵ دقیقه (کامل)؛ ۲:۲۵ باقی → ۳ دقیقه.
    """
    remaining_seconds = max(0, int(remaining_seconds))
    minutes = max(1, -(-remaining_seconds // 60))   # ceil
    minutes = min(JAIL_MINUTES, minutes)
    per_minute = full_bribe(level) / JAIL_MINUTES
    return int(round(per_minute * minutes))
