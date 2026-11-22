# -*- coding: utf-8 -*-
"""تستِ منطقیِ مرحله ۱۵.۵ + ۱۶ (بدونِ دیتابیس)."""
import sys

from app.data import leveling, kapatolo
from app.data import thefts as T

fails = []


def check(name, cond):
    print(f"{'✅' if cond else '❌'} {name}")
    if not cond:
        fails.append(name)


class P:
    def __init__(self, level=1, xp=0):
        self.level = level
        self.xp = xp


# --- leveling ---
check("xp_needed سطح۱=۱۰۰", leveling.xp_needed(1) == 100)
check("xp_needed سطح۵=۵۰۰", leveling.xp_needed(5) == 500)
check("xp_needed در سقف=۰", leveling.xp_needed(leveling.MAX_LEVEL) == 0)

p = P(level=1, xp=0)
r = leveling.add_xp(p, 250)  # 100 (→L2) + 150 → L2 needs 200 → xp=150 at L2
check("add_xp لول‌آپ به ۲", p.level == 2 and p.xp == 150 and r["leveled_up"])

p = P(level=leveling.MAX_LEVEL - 1, xp=0)
leveling.add_xp(p, 10 ** 9)
check("add_xp در سقف می‌ماند", p.level == leveling.MAX_LEVEL)
check("xp در سقف صفر", p.xp == 0)
check("progress_str در سقف = MAX", leveling.progress_str(p) == "MAX")
check("progress_str قالب ۵۰/۱۰۰", leveling.progress_str(P(1, 50)) == "50 / 100")

# --- kapatolo cooldown ---
check("cooldown lvl0 = 300s", kapatolo.cooldown_seconds(0) == 300)
check("cooldown lvl20 = 120s", kapatolo.cooldown_seconds(20) == 120)
check("cooldown نزولی", kapatolo.cooldown_seconds(5) > kapatolo.cooldown_seconds(15))
check("cooldown کلیپ بالای مکس", kapatolo.cooldown_seconds(999) == 120)
check("cd_upgrade_cost lvl0=100k", kapatolo.cooldown_upgrade_cost(0) == 100_000)
check("۴ پایگاهِ پساکاپولا", len(kapatolo.POST_KAPATOLO_BASES) == 4)

# --- thefts risk / keywords / bribe ---
pk = T.get_theft("pickpocket")
r_low = T.compute_risk(pk, level=1, fatigue=0)
r_hi = T.compute_risk(pk, level=1, fatigue=100)
check("خستگی ریسک را بالا می‌برد", r_hi > r_low)
check("لولِ بالاتر ریسک کمتر",
      T.compute_risk(pk, 20, 0) < T.compute_risk(pk, 1, 0))
check("ریسک کلیپ ۰٫۹۵", T.compute_risk(pk, 1, 100, risk_reduction=-100) <= 0.95)
check("ریسک کلیپ ۰٫۰۲", T.compute_risk(pk, 999, 0, risk_reduction=100) >= 0.02)

check("keyword جیب بری", T.theft_by_keyword("جیب بری")["key"] == "pickpocket")
check("keyword ماشین", T.theft_by_keyword("ماشین")["key"] == "car")
check("keyword نامربوط None", T.theft_by_keyword("سلام رفیق") is None)

# باجِ نزولی: بیشتر زمان باقی = گران‌تر
full = T.bribe_for_remaining(10, T.JAIL_SECONDS)      # ۱۵ دقیقه کامل
late = T.bribe_for_remaining(10, 145)                 # ~۲:۲۵ → ۳ دقیقه
check("باجِ کامل = base*level", full == T.JAIL_BRIBE_BASE * 10)
check("باجِ دیرهنگام ارزان‌تر", late < full)
check("باجِ ۲:۲۵ = ۳ دقیقه", late == round(T.JAIL_BRIBE_BASE * 10 / 15 * 3))
check("FATIGUE_RECOVERY=1", T.FATIGUE_RECOVERY_PER_MIN == 1)
check("BRIBE_LIMIT=10", T.BRIBE_LIMIT == 10)

# --- transfer fee محاسبه ---
amount = 10_000
fee = round(amount * 0.02)
check("کارمزد ۲٪ = 200", fee == 200)
check("خالص = 9800", amount - fee == 9800)

print("\n" + ("🎉 همه پاس شدند" if not fails else f"❌ {len(fails)} تست رد شد: {fails}"))
sys.exit(1 if fails else 0)
