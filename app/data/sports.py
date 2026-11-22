# -*- coding: utf-8 -*-
"""داده و فرمول‌هایِ «امپراتوری ورزشی» (مرحله ۱۴).

این ماژول فقط ثابت‌ها و توابعِ خالص (pure) دارد و به aiogram/SQLAlchemy وابسته
نیست تا بشود آن را جداگانه تست کرد.

پوششِ سندِ طراحی (بخش پنجم):
  ۱) فوتبال/بسکتبال + فرمولِ Team Power
  ۲) فرمول‌یک/موتور + وابستگی به صنعت و تحصیلات (CarQuality)
  ۳) الگوریتمِ شانسِ واقعی (Upset Factor + کارت‌های رویداد)
  ۴) ایونت‌های هفتگی
  ۵) اعلانِ قهرمانِ روزانه (ساعت ۲۰:۰۰)
  ۶) جدولِ هزینه‌ها
  ۷) برندسازی/نام‌گذاری + اعتبارسنجی
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# انواعِ ورزش
# ---------------------------------------------------------------------------
FOOTBALL = "football"
BASKETBALL = "basketball"
F1 = "f1"
MOTO = "moto"

TEAM_SPORTS = (FOOTBALL, BASKETBALL)      # تیمی — از مدلِ SportsTeam
RACING_SPORTS = (F1, MOTO)                # موتوری — از مدلِ RacingBrand
ALL_SPORTS = TEAM_SPORTS + RACING_SPORTS

SPORT_LABEL = {
    FOOTBALL: "⚽ فوتبال",
    BASKETBALL: "🏀 بسکتبال",
    F1: "🏎️ فرمول یک",
    MOTO: "🏍️ موتورسواری",
}
SPORT_EMOJI = {FOOTBALL: "⚽", BASKETBALL: "🏀", F1: "🏎️", MOTO: "🏍️"}

# ---------------------------------------------------------------------------
# ۶) جدولِ هزینه‌ها (دلار)
# ---------------------------------------------------------------------------
TEAM_CREATE_COST = 400_000        # شاملِ استادیومِ لول ۱ (ظرفیت ۵٬۰۰۰)
STADIUM_UPGRADE_BASE = 300_000    # هزینه‌ی ارتقای استادیوم × لولِ بعدی
COACH_UPGRADE_BASE = 160_000       # هزینه‌ی ارتقای کادر فنی × لولِ بعدی
STAR_PLAYER_COST = 2_000_000      # خریدِ بازیکنِ ستاره (+میانگینِ لول)
LEAGUE_ENTRY_FEE = 100_000         # ثبت‌نامِ هفتگیِ لیگِ حذفی (هر رشته جداگانه)
LEAGUE_CHAMPION_PRIZE = 3_000_000  # جایزه‌ی نقدیِ قهرمانیِ لیگِ حذفیِ هفتگی
LEAGUE_CHAMPION_BONUS_POINTS = 5   # امتیازِ پاداشِ قهرمانی
RENAME_COST = 50_000              # تغییرِ نامِ تیم/برند (ضدِ سوءاستفاده)
DAILY_MATCH_LIMIT = 4             # 🆕 پچ محدودیتِ روزانه: هر ورزش حداکثر همین‌قدر مسابقه در روز (به‌وقتِ تهران)

RACING_CREATE_COST = 1_000_000      # ساختِ پیستِ لول ۱ + پایه‌ی برند
TIRE_UPGRADE_BASE = 240_000       # کارخانه‌ی لاستیک
BRAND_UPGRADE_BASE = 500_000      # برندِ خودروسازی
DRIVER_HIRE_COST = 4_000_000      # استخدامِ راننده‌ی حرفه‌ای
TRACK_BUILD_COST = 1_000_000        # ساختِ پیستِ جدید
TECH_UPGRADE_BASE = 200_000       # تیمِ فنی (۸ نفر)

# سقف‌ها
# Stage 27: unified 50-level sports progression for every upgradable component.
SPORT_MAX_LEVEL = 50
STADIUM_MAX_LEVEL = SPORT_MAX_LEVEL
COACH_MAX_LEVEL = SPORT_MAX_LEVEL
BRAND_MAX_LEVEL = SPORT_MAX_LEVEL
TIRE_MAX_LEVEL = SPORT_MAX_LEVEL
TECH_MAX_LEVEL = SPORT_MAX_LEVEL
DRIVER_MAX_SKILL = 100
MAX_TRACKS = 12
AVG_PLAYER_MAX = 100
STAR_PLAYER_STEP = 2          # each star player adds this to avg player level
DRIVER_SKILL_STEP = 4         # each driver upgrade adds this to driver skill

# Rank tiers: every 5 levels the component gets a new rank name (10 tiers).
LEVEL_TIER_SIZE = 5
LEVEL_TIERS = (
    "\U0001f9f1 \u0645\u062d\u0644\u0651\u06cc",
    "\U0001f3d8\ufe0f \u0634\u0647\u0631\u06cc",
    "\U0001f5fa\ufe0f \u0627\u0633\u062a\u0627\u0646\u06cc",
    "\U0001f3c5 \u06a9\u0634\u0648\u0631\u06cc",
    "\U0001f31f \u0645\u0645\u062a\u0627\u0632",
    "\U0001f30d \u0642\u0627\u0631\u0651\u06cc",
    "\U0001f451 \u0628\u06cc\u0646\u200c\u0627\u0644\u0645\u0644\u0644\u06cc",
    "\U0001f48e \u0627\u0644\u0645\u0627\u0633\u06cc",
    "\U0001f3c6 \u0627\u0641\u0633\u0627\u0646\u0647\u200c\u0627\u06cc",
    "\u26a1 \u0627\u0645\u067e\u0631\u0627\u062a\u0648\u0631\u06cc",
)


def level_tier(level: int) -> str:
    """Rank label for a component level on the 1..50 ladder."""
    lv = max(1, min(SPORT_MAX_LEVEL, int(level or 1)))
    idx = min(len(LEVEL_TIERS) - 1, (lv - 1) // LEVEL_TIER_SIZE)
    return LEVEL_TIERS[idx]


def level_bar(level: int, width: int = 10) -> str:
    """Progress bar of a component level toward level 50."""
    lv = max(0, min(SPORT_MAX_LEVEL, int(level or 0)))
    filled = int(round(lv / SPORT_MAX_LEVEL * width))
    return "\u2588" * filled + "\u2591" * (width - filled)


def level_up_xp(level: int) -> int:
    """XP granted for reaching the given component level (Stage 27: XP everywhere)."""
    return int(25 + 5 * max(0, int(level or 0)))

# پیش‌نیازهایِ ساختِ تیمِ فرمول‌یک (سندِ طراحی §۲)
F1_REQUIRE_TIRE_LEVEL = 3
F1_REQUIRE_BRAND_LEVEL = 5
F1_REQUIRE_TRACKS = 3

# ---------------------------------------------------------------------------
# هزینه‌های ارتقا (خطی نسبت به لولِ بعدی)
# ---------------------------------------------------------------------------
def progressive_cost(base: int, level: int) -> int:
    """Stage 27: smooth 1..50 cost curve.

    Early levels stay affordable (close to base x level), while the last tiers
    become a real long-term goal (~x9 of the linear price at level 50).
    """
    lv = max(0, int(level or 0))
    return int(base * (lv + 1) * (1.0 + 0.16 * lv))


def stadium_upgrade_cost(level: int) -> int:
    return progressive_cost(STADIUM_UPGRADE_BASE, level)


def coach_upgrade_cost(level: int) -> int:
    return progressive_cost(COACH_UPGRADE_BASE, level)


def tire_upgrade_cost(level: int) -> int:
    return progressive_cost(TIRE_UPGRADE_BASE, level)


def brand_upgrade_cost(level: int) -> int:
    return progressive_cost(BRAND_UPGRADE_BASE, level)


def tech_upgrade_cost(level: int) -> int:
    return progressive_cost(TECH_UPGRADE_BASE, level)


def driver_upgrade_cost(skill: int) -> int:
    """Driver hiring/training price grows with current skill (0..100)."""
    steps = max(0, int(skill or 0)) // max(1, DRIVER_SKILL_STEP)
    return int(DRIVER_HIRE_COST * (1.0 + 0.12 * steps))


def track_build_cost(track_count: int) -> int:
    """Each new track is more expensive than the previous one."""
    n = max(1, int(track_count or 1))
    return int(TRACK_BUILD_COST * (1.0 + 0.35 * (n - 1)))


# ---------------------------------------------------------------------------
# ۷) اعتبارسنجیِ نام (برندسازی)
# ---------------------------------------------------------------------------
NAME_MIN = 3
NAME_MAX = 32
_BANNED_WORDS = ("admin", "ادمین", "robot", "ربات", "bot", "support", "سازنده")


def validate_name(raw: str) -> tuple[str | None, str | None]:
    """(نامِ پاک‌شده، خطا) را برمی‌گرداند. اگر خطا None باشد نام معتبر است."""
    if raw is None:
        return None, "نام خالی است."
    name = " ".join(raw.strip().split())
    if len(name) < NAME_MIN:
        return None, f"نام باید حداقل {NAME_MIN} کاراکتر باشد."
    if len(name) > NAME_MAX:
        return None, f"نام نباید بیشتر از {NAME_MAX} کاراکتر باشد."
    low = name.lower()
    for w in _BANNED_WORDS:
        if w in low:
            return None, "این نام مجاز نیست (تلاش برای جعلِ نامِ ربات/ادمین)."
    return name, None


# ---------------------------------------------------------------------------
# ۱) فرمولِ قدرتِ تیمِ فوتبال/بسکتبال (Team Power)
# TP = AvgPlayerLvl×40% + CoachLvl×20% + StadiumLvl×15% + FanSupport×15% + Budget×10%
# هر مؤلفه به مقیاسِ ۰..۱۰۰ نرمال می‌شود تا وزن‌ها معنا داشته باشند.
# ---------------------------------------------------------------------------
W_PLAYER = 0.40
W_COACH = 0.20
W_STADIUM = 0.15
W_FAN = 0.15
W_BUDGET = 0.10

BUDGET_FULL = 10_000_000   # این‌قدر بودجه = ۱۰۰ امتیازِ نرمال‌شده
FAN_FULL = 500_000         # این‌قدر هوادارِ راضی = ۱۰۰ امتیاز


def fan_support_points(satisfaction: int, population: int) -> float:
    """FanSupport طبقِ سند: درصدِ رضایت × جمعیت / مقیاس. خروجی ۰..۱۰۰."""
    supporters = (max(0, min(100, satisfaction)) / 100.0) * max(0, population)
    return max(0.0, min(100.0, supporters / FAN_FULL * 100.0))


def team_power(
    avg_player_lvl: int,
    coach_lvl: int,
    stadium_lvl: int,
    satisfaction: int,
    population: int,
    budget: int,
) -> float:
    player_pts = max(0.0, min(100.0, float(avg_player_lvl)))
    coach_pts = max(0.0, min(100.0, coach_lvl * 100.0 / COACH_MAX_LEVEL))
    stadium_pts = max(0.0, min(100.0, stadium_lvl * 100.0 / STADIUM_MAX_LEVEL))
    fan_pts = fan_support_points(satisfaction, population)
    budget_pts = max(0.0, min(100.0, budget / BUDGET_FULL * 100.0))
    tp = (
        player_pts * W_PLAYER
        + coach_pts * W_COACH
        + stadium_pts * W_STADIUM
        + fan_pts * W_FAN
        + budget_pts * W_BUDGET
    )
    return round(tp, 2)


# ---------------------------------------------------------------------------
# ۲) فرمول‌یک/موتور — کیفیتِ ماشین و قدرتِ تیمِ ��وتوری
# CarQuality = BaseBrandLevel × (1 + AvgEducationLevel × 0.05)
# ---------------------------------------------------------------------------
W_DRIVER = 0.40
W_CAR = 0.35
W_TIRE = 0.15
W_TECH = 0.10


def car_quality(brand_level: int, avg_education_level: float) -> float:
    """کیفیتِ پایه‌ی ماشین با اثرِ تحصیلاتِ کشور (مهندسانِ باهوش‌تر)."""
    return brand_level * (1.0 + max(0.0, avg_education_level) * 0.05)


def racing_power(
    driver_skill: int,
    brand_level: int,
    tire_level: int,
    tech_level: int,
    avg_education_level: float = 0.0,
) -> float:
    """قدرتِ نهاییِ تیمِ موتوری روی مقیاسِ ~۰..۱۰۰."""
    driver_pts = max(0.0, min(100.0, float(driver_skill)))
    cq = car_quality(brand_level, avg_education_level)                 # ~0..~20
    car_pts = max(0.0, min(100.0, cq * 100.0 / (BRAND_MAX_LEVEL * 1.5)))
    tire_pts = max(0.0, min(100.0, tire_level * 100.0 / TIRE_MAX_LEVEL))
    tech_pts = max(0.0, min(100.0, tech_level * 100.0 / TECH_MAX_LEVEL))
    rp = (
        driver_pts * W_DRIVER
        + car_pts * W_CAR
        + tire_pts * W_TIRE
        + tech_pts * W_TECH
    )
    return round(rp, 2)


# ---------------------------------------------------------------------------
# ۳) الگوریتمِ شانسِ واقعی (Real-World RNG) — Upset Factor + کارت‌های رویداد
# ---------------------------------------------------------------------------
UPSET_MIN = 0.8
UPSET_MAX = 1.2

# کارت‌های رویداد: (کلید، برچسب، احتمال، توضیح)
EVENT_CARDS = [
    ("injury", "🚑 مصدومیتِ ستاره", 0.05, "بازیکنِ کلیدیِ حریف مصدوم شد (−۲۰٪ قدرتِ حریف)."),
    ("referee", "🟥 اشتباهِ داوری", 0.08, "پنالتیِ مشکوک؛ +۱ به تیمِ ضعیف‌تر."),
    ("weather", "🌧️ شرایطِ جویِ بد", 0.10, "بونوسِ تکنولوژی خنثی شد."),
    ("fans", "📣 شورِ هواداران", 0.15, "رضایتِ میزبان بالای ۸۰٪ (+۱۰٪ به میزبان)."),
    ("corruption", "💸 فسادِ مالی", 0.02, "تیمِ بدهکارِ قوی‌تر عمداً می‌بازد."),
]
EVENT_LABEL = {c[0]: c[1] for c in EVENT_CARDS}
EVENT_DESC = {c[0]: c[3] for c in EVENT_CARDS}


@dataclass
class MatchContext:
    """شرایطِ محیطیِ یک مسابقه (برای اعمالِ کارت‌های رویداد)."""
    host_is_a: bool = True
    host_satisfaction: int = 50          # رضایتِ شهرِ میزبان (٪)
    a_has_bank_debt: bool = False        # بدهیِ بانکیِ سنگینِ تیمِ A
    b_has_bank_debt: bool = False
    a_tech_bonus: float = 0.0            # بونوسِ تکنولوژی (فقط موتوری)
    b_tech_bonus: float = 0.0


@dataclass
class MatchResult:
    winner: str                # "A" | "B" | "draw"
    score_a: int
    score_b: int
    power_a: float
    power_b: float
    final_a: float
    final_b: float
    events: list = field(default_factory=list)   # کلیدهایِ کارت‌های کشیده‌شده


def draw_events(rng: random.Random) -> list[str]:
    """هر کارت مستقل با احتمالِ خودش کشیده می‌شود."""
    drawn = []
    for key, _label, prob, _desc in EVENT_CARDS:
        if rng.random() < prob:
            drawn.append(key)
    return drawn


def _score_to_goals(sport: str, ratio: float, rng: random.Random) -> int:
    """سهمِ نسبیِ یک تیم را به گل/امتیاز تبدیل می‌کند (بسکتبال امتیازِ بالا)."""
    if sport == BASKETBALL:
        base = 70 + ratio * 60          # ~۷۰..۱۳۰
        return int(round(base + rng.uniform(-6, 6)))
    if sport in RACING_SPORTS:
        # در مسابقاتِ موتوری «امتیاز» = امتیازِ جایگاه؛ اینجا فقط برنده مهم است
        return 0
    # فوتبال
    goals = int(round(ratio * 5))       # ~۰..۵
    if rng.random() < 0.15:
        goals += 1
    return max(0, goals)


def simulate_match(
    sport: str,
    power_a: float,
    power_b: float,
    ctx: MatchContext | None = None,
    rng: random.Random | None = None,
) -> MatchResult:
    """یک مسابقه را با ضریبِ غافلگیری و کارت‌های رویداد شبیه‌سازی می‌کند."""
    rng = rng or random.Random()
    ctx = ctx or MatchContext()

    r_a = rng.uniform(UPSET_MIN, UPSET_MAX)
    r_b = rng.uniform(UPSET_MIN, UPSET_MAX)
    fa = max(0.1, power_a) * r_a
    fb = max(0.1, power_b) * r_b

    events = draw_events(rng)
    weaker_bonus = 0   # +۱ گل به تیمِ ضعیف‌تر (اشتباهِ داوری)

    for ev in events:
        if ev == "injury":
            # قدرتِ حریفِ کارت‌خورده کم می‌شود؛ کارت روی یک تیمِ تصادفی
            if rng.random() < 0.5:
                fb *= 0.8
            else:
                fa *= 0.8
        elif ev == "weather":
            # خنثی‌کردنِ بونوسِ تکنولوژی (فقط تأثیرِ نسبی)
            fa -= ctx.a_tech_bonus
            fb -= ctx.b_tech_bonus
        elif ev == "fans":
            if ctx.host_satisfaction > 80:
                if ctx.host_is_a:
                    fa *= 1.10
                else:
                    fb *= 1.10
        elif ev == "corruption":
            # تیمِ قوی‌ترِ بدهکار عمداً می‌بازد
            if fa >= fb and ctx.a_has_bank_debt:
                fa *= 0.5
            elif fb > fa and ctx.b_has_bank_debt:
                fb *= 0.5
        elif ev == "referee":
            weaker_bonus = 1

    fa = max(0.1, fa)
    fb = max(0.1, fb)
    total = fa + fb
    ratio_a = fa / total
    ratio_b = fb / total

    score_a = _score_to_goals(sport, ratio_a, rng)
    score_b = _score_to_goals(sport, ratio_b, rng)

    # اشتباهِ داوری: +۱ به تیمِ ضعیف‌تر (طبقِ قدرتِ خام، نه نهایی)
    if weaker_bonus and sport not in RACING_SPORTS:
        if power_a < power_b:
            score_a += weaker_bonus
        else:
            score_b += weaker_bonus

    if sport in RACING_SPORTS:
        # در موتوری برنده بر اساسِ قدرتِ نهایی تعیین می‌شود (بدونِ گل)
        if abs(fa - fb) < 1e-9:
            winner = "draw"
        else:
            winner = "A" if fa > fb else "B"
        return MatchResult(winner, 0, 0, round(power_a, 2), round(power_b, 2),
                           round(fa, 2), round(fb, 2), events)

    # 🆕 مرحله ۴۵ — بسکتبال در دنیای واقعی مساوی ندارد؛ درصورتِ تساوی وقتِ اضافه بازی می‌شود تا برنده مشخص شود.
    if sport == BASKETBALL and score_a == score_b:
        for _ in range(20):
            score_a += int(round(ratio_a * 10 + rng.uniform(0, 8)))
            score_b += int(round(ratio_b * 10 + rng.uniform(0, 8)))
            if score_a != score_b:
                break
        if score_a == score_b:
            if fb > fa:
                score_b += 2
            else:
                score_a += 2

    if score_a > score_b:
        winner = "A"
    elif score_b > score_a:
        winner = "B"
    else:
        winner = "draw"
    return MatchResult(winner, score_a, score_b, round(power_a, 2), round(power_b, 2),
                       round(fa, 2), round(fb, 2), events)


# ---------------------------------------------------------------------------
# ساختارِ لیگ + امتیازدهی
# ---------------------------------------------------------------------------
DIVISION_TWO = 2   # دسته دو (۱۶ تیم) — صعودِ ۳ تیمِ اول
DIVISION_ONE = 1   # دسته یک (۲۴ تیمِ برتر)
DIVISION_LABEL = {DIVISION_ONE: "دسته یک", DIVISION_TWO: "دسته دو"}
DIVISION_SIZE = {DIVISION_ONE: 24, DIVISION_TWO: 16}
PROMOTION_SLOTS = 3

WIN_POINTS = 3
DRAW_POINTS = 1
LOSS_POINTS = 0


def points_for(result: str, is_a: bool) -> int:
    """امتیازِ لیگ برای یک تیم از نتیجه‌ی یک مسابقه."""
    if result == "draw":
        return DRAW_POINTS
    won = (result == "A" and is_a) or (result == "B" and not is_a)
    return WIN_POINTS if won else LOSS_POINTS


# ---------------------------------------------------------------------------
# ۴) ایونت‌های هفتگی (Weekly Events)
# نگاشتِ روزِ هفته‌ی پایتون: دوشنبه=0 ... یکشنبه=۶
# شنبه=۵، یکشنبه=۶، دوشنبه=۰، سه‌شنبه=۱، چهارشنبه=۲، پنج‌شنبه=۳، جمعه=۴
# ---------------------------------------------------------------------------
WEEKLY_EVENTS = {
    5: {"key": "cup", "name": "🏆 جامِ حذفیِ فوتبال",
        "prize": "۵۰۰٬۰۰۰ دلار + اسکینِ استادیوم",
        "effect": "همه‌ی تیم‌ها (حتی دسته دو) شرکت می‌کنند."},
    6: {"key": "grandprix", "name": "🏎️ گرندپریِ سرعت",
        "prize": "برندینگِ رایگانِ ۱ هفته",
        "effect": "مسابقاتِ F1 و موتور با ضریبِ درآمدِ ۲ برابر."},
    0: {"key": "blackmarket", "name": "🕶️ بازارِ سیاهِ ورزشی",
        "prize": "تخفیفِ ۵۰٪ خریدِ بازیکن",
        "effect": "خریدِ بازیکنانِ ستاره با نصفِ قیمت."},
    1: {"key": "clanwar", "name": "⚔️ جنگِ کلن‌های ورزشی",
        "prize": "ارتقای رایگانِ لولِ کلن",
        "effect": "رقابتِ بینِ اعضای کلن‌ها در لیگ‌ها."},
    2: {"key": "disaster", "name": "🌪️ روزِ بلایای طبیعی",
        "prize": "بیمه‌ی رایگانِ ۱ ماه",
        "effect": "احتمالِ زلزله/سیل ۲ برابر (ریسکِ بالا)."},
    3: {"key": "mafianight", "name": "🌙 شب‌زنده‌داریِ مافیا",
        "prize": "کاهشِ ۵۰٪ ریسکِ دزدی",
        "effect": "بهترین زمان برای عملیات‌های بزرگ."},
    4: {"key": "festival", "name": "🎉 جشنواره‌ی فرهنگی",
        "prize": "+۲۰٪ رضایتِ مردم",
        "effect": "ساختِ پارک و سینما ارزان‌تر."},
}

# ضرایبی که مستقیماً روی سیستمِ ورزش اثر دارند (نگه‌داشته برای سازگاری)
STAR_DISCOUNT_EVENT = "blackmarket"   # نصفِ قیمتِ بازیکن
RACING_DOUBLE_EVENT = "grandprix"     # ۲ برابر درآمدِ موتوری


def event_for_weekday(weekday: int) -> dict:
    return WEEKLY_EVENTS.get(weekday % 7, WEEKLY_EVENTS[5])


# ---------------------------------------------------------------------------
# اثرِ واقعیِ ایونت‌ها روی گیم‌پلی
# هر ایونت علاوه بر متنِ نمایشی، یک اثرِ واقعیِ عددی دارد که فقط برای یک
# «پنجره‌ی زمانی» (۶ تا ۲۴ ساعت بسته به اثر) از ابتدای همان روز به وقتِ
# تهران فعال است تا محیطِ بازی پویا و جذاب بماند.
# ---------------------------------------------------------------------------
TEHRAN_UTC_OFFSET_MIN = 210  # +03:30

EVENT_EFFECTS: dict[str, dict] = {
    "cup":        {"kind": "match_prize", "sports": TEAM_SPORTS,   "mult": 1.5,  "duration_hours": 24,
                   "note": "جایزه‌ی مسابقاتِ فوتبال/بسکتبال ۱.۵ برابر"},
    "grandprix":  {"kind": "match_prize", "sports": RACING_SPORTS, "mult": 2.0,  "duration_hours": 18,
                   "note": "درآمدِ مسابقاتِ F1/موتور ۲ برابر"},
    "blackmarket": {"kind": "star_price", "mult": 0.5,             "duration_hours": 12,
                    "note": "خریدِ بازیکنِ ستاره با نصفِ قیمت"},
    "clanwar":    {"kind": "match_prize", "sports": ALL_SPORTS,    "mult": 1.25, "duration_hours": 12,
                   "note": "جایزه‌ی همه‌ی مسابقات ۱.۲۵ برابر"},
    "disaster":   {"kind": "theft_risk",  "delta": 0.12,           "duration_hours": 6,
                   "note": "ریسکِ دزدی +۱۲٪ (شهر ناامن)"},
    "mafianight": {"kind": "theft_risk",  "mult": 0.5,             "duration_hours": 8,
                   "note": "ریسکِ دزدی ۵۰٪ کمتر"},
    "festival":   {"kind": "city",        "sat_bonus": 15, "build_discount": 0.20, "duration_hours": 24,
                   "note": "+۱۵ رضایتِ مردم و ۲۰٪ تخفیفِ ساختِ رفاهی"},
}


def _tehran_now(now: datetime | None = None) -> datetime:
    """زمانِ فعلی به وقتِ تهران؛ ورودی باید UTC باشد (پیش‌فرض: utcnow)."""
    base = now or datetime.utcnow()
    return base + timedelta(minutes=TEHRAN_UTC_OFFSET_MIN)


# ---------------------------------------------------------------------------
# 🎲 استخرِ ۱۰۰ ایونت — هر روز یکی به‌صورتِ رندوم (اما پایدار در طولِ روز
# و یکسان برای همه‌ی بازیکنان، بر اساسِ تاریخِ تهران) انتخاب و اعمال می‌شود.
# هر ایونت یک اثرِ واقعیِ عددی با ماندگاریِ ۶ تا ۲۴ ساعت از ابتدای روز دارد.
# نام‌ها از ترکیبِ «موضوع + توصیف» ساخته می‌شوند تا تنوعِ کافی داشته باشیم.
# ---------------------------------------------------------------------------
_EVENT_DESCRIPTORS = [
    "بزرگ", "بین‌المللی", "ملی", "شبانه", "بهاره", "تابستانی", "پاییزه",
    "زمستانی", "ویژه", "طلایی", "سالانه", "تاریخی", "افتخاری", "محلی",
    "منطقه‌ای", "جهانی",
]


def _clip_dur(h: int) -> int:
    return max(1, min(24, int(h)))


def _cyc(seq, i):
    return seq[i % len(seq)]


def _win_start(i: int, dur: int) -> int:
    """ساعتِ شروعِ اثر در طولِ روز — قطعی و متنوع، طوری که پنجره درونِ همان روز جا شود.
    اثرِ ۲۴ساعته از ۰۰:۰۰ شروع می‌شود (تا ۲۳:۵۹)."""
    span = 24 - int(dur)
    if span <= 0:
        return 0
    return (i * 5 + 3) % (span + 1)


def _fmt_hour(h) -> str:
    hh = int(h) % 24
    mm = int(round((h - int(h)) * 60))
    if mm == 60:
        hh = (hh + 1) % 24
        mm = 0
    return f"{hh:02d}:{mm:02d}"


def _window_text(start_hour: int, dur: int) -> str:
    """بازه‌ی فعال بودنِ اثر در طولِ روز، مثل «۱۱:۰۰ تا ۱۲:۰۰»."""
    end = start_hour + dur
    end_txt = "23:59" if end >= 24 else _fmt_hour(end)
    return f"{_fmt_hour(start_hour)} تا {end_txt}"


def _gen_events() -> list[dict]:
    events: list[dict] = []

    def add(prefix, emoji, bases, count, prize, eff_builder):
        for i in range(count):
            base = bases[i % len(bases)]
            desc = _EVENT_DESCRIPTORS[(i // len(bases)) % len(_EVENT_DESCRIPTORS)]
            eff = eff_builder(i)
            dur = _clip_dur(eff["duration_hours"])
            start_hour = _win_start(i, dur)
            window = _window_text(start_hour, dur)
            eff["duration_hours"] = dur
            eff["start_hour"] = start_hour
            eff["window"] = window
            events.append({
                "key": f"{prefix}{i + 1}",
                "name": f"{emoji} {base} {desc}",
                "prize": prize,
                "effect": eff["note"],
                "window": window,
                "duration_hours": dur,
                "start_hour": start_hour,
                "_eff": eff,
            })

    def team_eff(i):
        m = _cyc([1.3, 1.4, 1.5, 1.6], i)
        return {"kind": "match_prize", "sports": TEAM_SPORTS, "mult": m,
                "duration_hours": _cyc([24, 18, 12, 6], i),
                "note": f"جایزه‌ی فوتبال/بسکتبال ×{m}"}

    def racing_eff(i):
        m = _cyc([1.6, 1.8, 2.0, 1.5], i)
        return {"kind": "match_prize", "sports": RACING_SPORTS, "mult": m,
                "duration_hours": _cyc([3, 6, 9, 12], i),
                "note": f"درآمدِ F1/موتور ×{m}"}

    def all_eff(i):
        m = _cyc([1.2, 1.25, 1.3, 1.35], i)
        return {"kind": "match_prize", "sports": ALL_SPORTS, "mult": m,
                "duration_hours": _cyc([24, 20, 16, 12], i),
                "note": f"جایزه‌ی همه‌ی مسابقات ×{m}"}

    def stardisc_eff(i):
        m = _cyc([0.5, 0.6, 0.7, 0.45], i)
        return {"kind": "star_price", "mult": m,
                "duration_hours": _cyc([2, 4, 6, 8], i),
                "note": f"خریدِ بازیکنِ ستاره ×{m}"}

    def starsurge_eff(i):
        m = _cyc([1.3, 1.4, 1.5, 1.25], i)
        return {"kind": "star_price", "mult": m,
                "duration_hours": _cyc([1, 2, 3, 4], i),
                "note": f"قیمتِ بازیکنِ ستاره ×{m}"}

    def theftup_eff(i):
        d = _cyc([0.10, 0.12, 0.14, 0.08], i)
        return {"kind": "theft_risk", "delta": d,
                "duration_hours": _cyc([1, 2, 3, 6], i),
                "note": f"ریسکِ دزدی +{int(round(d * 100))}٪"}

    def theftdown_eff(i):
        m = _cyc([0.5, 0.6, 0.7, 0.55], i)
        return {"kind": "theft_risk", "mult": m,
                "duration_hours": _cyc([8, 10, 6, 12], i),
                "note": f"ریسکِ دزدی ×{m}"}

    def prosper_eff(i):
        s = _cyc([12, 15, 18, 10], i)
        disc = _cyc([0.15, 0.20, 0.25, 0.10], i)
        return {"kind": "city", "sat_bonus": s, "build_discount": disc,
                "duration_hours": _cyc([24, 18, 12, 8], i),
                "note": f"+{s} رضایتِ مردم و {int(round(disc * 100))}٪ تخفیفِ ساختِ رفاهی"}

    def unrest_eff(i):
        s = _cyc([-8, -10, -12, -6], i)
        return {"kind": "city", "sat_bonus": s, "build_discount": 0.0,
                "duration_hours": _cyc([4, 6, 8, 12], i),
                "note": f"{s} رضایتِ مردم (نارضایتیِ عمومی)"}

    add("team", "🏆", ["جامِ حذفی", "دربیِ شهر", "لیگِ ستارگان", "سوپرجام", "کأسِ قهرمانان"], 14,
        "جامِ قهرمانی + اسکینِ استادیوم", team_eff)
    add("race", "🏎️", ["گرندپری", "رالیِ کویر", "درگِ سرعت", "چالشِ پیست"], 12,
        "برندینگِ رایگانِ یک هفته", racing_eff)
    add("allsport", "🥇", ["المپیکِ شهر", "هفته‌ی ورزش", "کارناوالِ ورزشی", "جشنِ قهرمانی"], 10,
        "مدالِ افتخار + پاداشِ نقدی", all_eff)
    add("bmkt", "🕶️", ["بازارِ سیاه", "حراجِ نقل‌وانتقالات", "پنجره‌ی خرید", "معامله‌ی زیرزمینی"], 10,
        "تخفیفِ خریدِ بازیکن", stardisc_eff)
    add("surge", "📈", ["کمبودِ بازیکن", "تحریمِ نقل‌وانتقالات", "تورمِ دستمزد", "جنگِ مزایده"], 8,
        "—", starsurge_eff)
    add("raid", "🚨", ["یورشِ پلیس", "گشتِ ویژه", "حکومتِ نظامی", "عملیاتِ پاک‌سازی"], 12,
        "—", theftup_eff)
    add("safe", "🌙", ["شب‌زنده‌داریِ مافیا", "اعتصابِ پلیس", "مه‌گرفتگی", "قطعیِ برق"], 12,
        "کاهشِ ریسکِ عملیات", theftdown_eff)
    add("fest", "🎉", ["جشنواره‌ی فرهنگی", "افتتاحِ پارک", "کنسرتِ خیابانی", "جشنِ ملی"], 12,
        "+رضایتِ مردم و تخفیفِ ساخت", prosper_eff)
    add("unrest", "🌪️", ["اعتراضاتِ مردمی", "بحرانِ اقتصادی", "کمبودِ نان", "موجِ گرما"], 10,
        "—", unrest_eff)

    return events


EVENTS: list[dict] = _gen_events()
EVENT_COUNT = len(EVENTS)   # باید ۱۰۰ باشد


# 🌤️ روزِ عادی — هر ۳ روز یک‌بار: هیچ اونتی و هیچ اثرِ ویژه‌ای فعال نیست.
NORMAL_DAY: dict = {
    "key": "normal",
    "name": "🌤️ روزِ عادی",
    "prize": "—",
    "effect": "امروز روزِ عادی است؛ هیچ اونتی و اثرِ ویژه‌ای فعال نیست.",
    "window": "—",
    "duration_hours": 0,
    "start_hour": 0,
    "_eff": None,
}

# الگو: روز۱ اونت، روز۲ اونت، روز۳ عادی، روز۴ اونت، ... (هر سومین روز عادی)
NORMAL_DAY_CYCLE = 3


def is_normal_day(now: datetime | None = None) -> bool:
    """آیا امروز «روزِ عادی» است؟ (هر ۳ روز یک‌بار، بر اساسِ تاریخِ تهران)."""
    t = _tehran_now(now)
    return t.toordinal() % NORMAL_DAY_CYCLE == 0


def event_for_day(now: datetime | None = None) -> dict:
    """اونتِ امروز — رندوم اما پایدار در طولِ روز و یکسان برای همه (بر اساسِ تاریخِ تهران).
    هر سومین روز «روزِ عادی» است و هیچ اونتی ندارد."""
    if is_normal_day(now):
        return NORMAL_DAY
    t = _tehran_now(now)
    seed = (t.toordinal() * 2654435761) % (2 ** 32)
    return EVENTS[random.Random(seed).randrange(len(EVENTS))]


def active_event_effect(now: datetime | None = None) -> dict | None:
    """اثرِ اونتِ فعال اگر هم‌اکنون در پنجره‌ی زمانیِ آن باشیم، وگرنه None.
    اونت اولِ روز (۰۰:۰۰) انتخاب می‌شود اما اثرش فقط در بازه‌ی [start_hour, start_hour+duration) فعال است."""
    ev = event_for_day(now)
    eff = ev.get("_eff")
    if not eff:
        return None
    t = _tehran_now(now)
    hours_into_day = t.hour + t.minute / 60.0
    start = float(eff.get("start_hour", 0))
    end = start + float(eff["duration_hours"])
    if not (start <= hours_into_day < end):
        return None
    out = dict(eff)
    out["event_key"] = ev["key"]
    out["event_name"] = ev["name"]
    out["remaining_hours"] = end - hours_into_day
    return out


def event_theft_risk(base_risk: float, now: datetime | None = None) -> float:
    """اعمالِ اثرِ ایونت روی ریسکِ دزدی (اول ضرب، سپس جمعِ دلتا)."""
    eff = active_event_effect(now)
    if not eff or eff["kind"] != "theft_risk":
        return base_risk
    return base_risk * float(eff.get("mult", 1.0)) + float(eff.get("delta", 0.0))


def event_match_prize_mult(sport: str, now: datetime | None = None) -> float:
    eff = active_event_effect(now)
    if not eff or eff["kind"] != "match_prize":
        return 1.0
    sports = eff.get("sports")
    if sports is None or sport in sports:
        return float(eff.get("mult", 1.0))
    return 1.0


def event_star_price_mult(now: datetime | None = None) -> float:
    eff = active_event_effect(now)
    if eff and eff["kind"] == "star_price":
        return float(eff.get("mult", 1.0))
    return 1.0


def event_city_bonus(now: datetime | None = None) -> dict:
    eff = active_event_effect(now)
    if eff and eff["kind"] == "city":
        return {"sat_bonus": int(eff.get("sat_bonus", 0)),
                "build_discount": float(eff.get("build_discount", 0.0))}
    return {"sat_bonus": 0, "build_discount": 0.0}


def active_effect_line(now: datetime | None = None) -> str | None:
    """یک‌خطیِ نمایشیِ اثرِ فعال (برای منوها)."""
    eff = active_event_effect(now)
    if not eff:
        return None
    h = eff["remaining_hours"]
    left = f"{int(h)} ساعت" if h >= 1 else f"{int(h * 60)} دقیقه"
    win = eff.get("window", "")
    return f"⚡ اثرِ فعالِ اونت ({win}): {eff.get('note', '')} — {left} دیگر"


def star_player_cost(now: datetime | None = None) -> int:
    """قیمتِ بازیکنِ ستاره با اعمالِ تخفیفِ ایونتِ فعال (بازارِ سیاه)."""
    return int(STAR_PLAYER_COST * event_star_price_mult(now))


# ---------------------------------------------------------------------------
# جوایزِ برد در لیگ (واریزِ خودکار)
# ---------------------------------------------------------------------------
MATCH_WIN_PRIZE = {
    FOOTBALL: 60_000,
    BASKETBALL: 50_000,
    F1: 120_000,
    MOTO: 90_000,
}
MATCH_DRAW_PRIZE = 20_000


def match_prize(sport: str, result_for_team: str, now: datetime | None = None) -> int:
    """جایزه‌ی نقدیِ یک مسابقه برای یک تیم بر اساسِ نتیجه + اثرِ ایونتِ فعال."""
    if result_for_team == "win":
        prize = MATCH_WIN_PRIZE.get(sport, 50_000)
    elif result_for_team == "draw":
        prize = MATCH_DRAW_PRIZE
    else:
        prize = 0
    return int(prize * event_match_prize_mult(sport, now))
