# app/data/economy.py
# ثابت‌ها و توابعِ خالصِ اقتصادِ عمارت (مرحله ۷):
# درآمدِ خودکارِ ساعتی، زیردستانِ 4^N، حقوقِ هفتگی و جریمه‌ی دیرکرد.

from datetime import datetime

# ---------- درآمدِ خودکار ----------
INCOME_PER_SUB_PER_HOUR = 50    # درآمدِ هر زیردست در هر ساعت (دلار)
MAX_OFFLINE_HOURS = 24          # سقفِ ساعتِ انباشتِ درآمدِ آفلاین (بیشتر جمع نمی‌شود)

# ---------- زیردستان: 4^N ----------
MAX_PROF_LEVEL = 10             # v1.7.8.9 — ۵ سطح اضافه؛ منطق همان ۴^N است
PROMOTE_BASE_COST = 20_000       # پایه‌ی هزینه‌ی ترفیع


def subordinates_for_level(level: int) -> int:
    """تعدادِ زیردستانِ یک حرفه‌ای در سطحِ N برابرِ 4^N است (سطح ۱=۴، ۲=۱۶، ۳=۶۴...)."""
    return 4 ** max(1, level)


def promote_cost(current_level: int) -> int:
    """هزینه‌ی ترفیع از سطحِ فعلی به سطحِ بعدی (نمایی، هماهنگ با 4^N)."""
    return PROMOTE_BASE_COST * (4 ** current_level)


def effective_subs(op) -> int:
    """زیردستانِ مؤثرِ یک حرفه‌ای؛ اگر ستونِ subordinates خالی/۰ بود (ردیفِ قدیمی)،
    از روی سطح حساب می‌کند تا کد نشکند."""
    return op.subordinates or subordinates_for_level(op.level)


def income_rate_per_hour(subordinates: int) -> int:
    """نرخِ درآمدِ ساعتیِ یک حرفه‌ای بر اساسِ تعدادِ زیردستانش."""
    return subordinates * INCOME_PER_SUB_PER_HOUR


# ---------- حقوقِ هفتگی و جریمه ----------
SALARY_PERIOD_DAYS = 7          # دوره‌ی پرداختِ حقوق (روز)
WAGE_PER_SUB = 10               # حقوقِ هفتگیِ هر زیردست
LATE_PENALTY_PER_DAY = 0.05     # جریمه‌ی دیرکرد: ۵٪ روی حقوق به‌ازای هر روزِ تأخیر
STRIKE_AFTER_DAYS = 14          # بعد از این تعداد روزِ بی‌حقوقی، حرفه‌ای اعتصاب می‌کند


SALARY_PERIOD_HOURS = SALARY_PERIOD_DAYS * 24   # ۱۶۸ ساعت


def weekly_salary(subordinates: int) -> int:
    """حقوقِ یک هفتهٔ کامل بر اساسِ تعدادِ زیردستان (مرجعِ نرخ)."""
    return subordinates * WAGE_PER_SUB


def salary_rate_per_hour(subordinates: int) -> float:
    """🆕 مرحله ۶۹ — نرخِ لحظه‌ایِ حقوق (دلار بر ساعت).

    دقیقاً مثلِ income_rate_per_hour: حقوق لحظه‌به‌لحظه انباشت می‌شود
    و کاربر هر وقت خواست می‌تواند پرداخت کند. مجموعِ یک هفته دقیقاً
    برابرِ همان weekly_salary قبلی است، پس تعادلِ بازی تغییر نمی‌کند.
    """
    return weekly_salary(subordinates) / float(SALARY_PERIOD_HOURS)


# ---------- توابعِ زمانی ----------
def hours_between(start: datetime, end: datetime) -> float:
    """تعدادِ ساعتِ بینِ دو زمان (هیچ‌وقت منفی نمی‌شود)."""
    if start is None:
        return 0.0
    return max(0.0, (end - start).total_seconds() / 3600)


def days_since(anchor: datetime, now: datetime) -> float:
    """تعدادِ روزِ گذشته از یک زمانِ مبنا."""
    if anchor is None:
        return 0.0
    return max(0.0, (now - anchor).total_seconds() / 86400)


def salary_anchor(op, now: datetime) -> datetime:
    """🆕 مرحله ۶۷ — مبدأِ محاسبهٔ حقوق (هرگز None برنمی‌گرداند).

    اگر هم last_paid و هم created_at خالی باشند (ردیف‌ِ قدیمی)، قبلاً بدهی همیشه
    صفر می‌شد و دکمهٔ پرداختِ حقوق عملاً بی‌اثر بود.
    """
    return op.last_paid or op.created_at or now


def next_salary_in_days(op, now: datetime) -> float:
    """منسوخ — حقوق دیگر سررسید ندارد و لحظه‌ای انباشت می‌شود.

    فقط برای سازگاریِ عقب‌رو نگه داشته شده و همیشه ۰ برمی‌گرداند.
    """
    return 0.0


def salary_accrued_for(op, now: datetime) -> int:
    """🆕 مرحله ۶۹ — حقوقِ انباشته‌شدهٔ لحظه‌ای (بدونِ جریمه)."""
    anchor = salary_anchor(op, now)
    hours = hours_between(anchor, now)
    return int(salary_rate_per_hour(effective_subs(op)) * hours)


def salary_due_for(op, now: datetime):
    """(مبلغِ قابل‌پرداخت، روزهای تأخیر، آیا اعتصاب) را برمی‌گرداند.

    🆕 مرحله ۶۹ — حقوق دیگر «سررسیدِ هفتگی» ندارد. دقیقاً مثلِ درآمد،
    لحظه‌به‌لحظه انباشت می‌شود و کاربر هر زمان خواست می‌تواند پرداخت کند.
    قبلاً تا وقتی ۷ روز کامل نمی‌گذشت مبلغ ۰ بود و کاربر پیامِ «تسویه است» می‌گرفت.

    جریمهٔ دیرکرد فقط وقتی اعمال می‌شود که از یک دورهٔ کامل بیشتر معطل شده باشد.
    """
    anchor = salary_anchor(op, now)
    d = days_since(anchor, now)
    strike = d >= STRIKE_AFTER_DAYS
    base = salary_accrued_for(op, now)
    if base <= 0:
        return 0, 0, strike
    late_days = int(max(0.0, d - SALARY_PERIOD_DAYS))
    penalty = int(base * LATE_PENALTY_PER_DAY * late_days)
    return base + penalty, late_days, strike
