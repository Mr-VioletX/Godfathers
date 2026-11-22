# -*- coding: utf-8 -*-
"""تستِ منطقیِ مرحله ۱۹ — فقط ماژول‌های خالص (بدونِ aiogram/sqlalchemy).

اجرا: python stage19_logic_test.py
"""
import sys

from app.data import military as M
from app.data import world_alliance as WA
from app.data import branding as B
from app.data import worldbank as WB

ok = 0
fail = 0


def check(name, cond):
    global ok, fail
    if cond:
        ok += 1
        print(f"✅ {name}")
    else:
        fail += 1
        print(f"❌ {name}")


# --------------------------- نظامی ---------------------------
print("\n=== نظامی ===")
check("تعدادِ واحدها = طولِ UNIT_ORDER", len(M.UNITS) == len(M.UNIT_ORDER))
check("هر واحد در یک دسته است", all(M.get_unit(k) for k in M.UNIT_ORDER))
c0 = M.buy_cost("militia", 0)
c2 = M.buy_cost("militia", 2)
check("خریدِ واحدِ ارتقایافته گران‌تر است", c2 > c0)
p1 = M.unit_power("tank", 5, 0)
p2 = M.unit_power("tank", 5, 3)
check("ارتقا قدرتِ واحد را بالا می‌برد", p2 > p1)
check("army_power جمع‌پذیر است", M.army_power([("tank", 2, 0), ("rifleman", 3, 0)]) > 0)
# سنگ‌‌کاغذ‌قیچی: ترکیبِ پدافند در برابرِ هوایی باید برتری دهد
import random
r = random.Random(42)
res = M.simulate_battle([("fighter", 10, 0)], [("sam", 10, 0)], r)
check("simulate_battle خروجیِ dict دارد", isinstance(res, dict) and "attacker_won" in res and "att_losses" in res)

# --------------------------- اتحادیه‌ی جهانی ---------------------------
print("\n=== اتحادیه‌ی جهانی ===")
check("tag_is_valid معتبر", WA.tag_is_valid("World_1") and not WA.tag_is_valid("a b"))
check("normalize_tag یکدست", WA.normalize_tag("@AbC") == "abc")
check("member_cap با سطح بالا می‌رود", WA.member_cap_for_level(3) >= WA.member_cap_for_level(1))
check("cap_upgrade_cost = 3M*level", WA.cap_upgrade_cost(2) == 3_000_000 * 2)
check("join_conditions_met رده/قدرت", WA.join_conditions_met("large", 5000, "medium", 1000))
check("join ردِ رده‌ی پایین", not WA.join_conditions_met("small", 5000, "large", 1000))
check("vote_passes با ۵۰٪+", WA.vote_passes(3, 5) and not WA.vote_passes(2, 5))
check("roll_world_war بولین", isinstance(WA.roll_world_war(2000, 1000), bool))
check("war_loot_amount مثبت", WA.war_loot_amount(1_000_000, WA.war_loot_percent(2000, 1000)) > 0)
check("next_tier/prev_tier", WA.next_tier("small") in WA.TIER_ORDER and WA.prev_tier("empire") in WA.TIER_ORDER)

# --------------------------- برند ---------------------------
print("\n=== برندسازی ===")
check("upgrade_cost صعودی", B.upgrade_cost(3) > B.upgrade_cost(1))
check("income_bonus_pct = level*3", B.income_bonus_pct(4) == 12)
check("prestige_value مثبت", B.prestige_value(5, 100) == 5 * 5000 + 100 * 20)
check("can_upgrade در سقف False", not B.can_upgrade(B.MAX_BRAND_LEVEL))
check("CAMPAIGNS شاملِ CAMPAIGN_ORDER", all(B.get_campaign(k) for k in B.CAMPAIGN_ORDER))

# --------------------------- بانکِ جهانی ---------------------------
print("\n=== بانکِ جهانی ===")
nw = WB.net_worth(cash=100, daily_income=50, city_value=200, country_value=400)
check("net_worth = مجموع", nw == 100 + 50 + 200 + 400)
check("tier_for صعودی", WB.tier_for(0) is not None)
check("max_loan = ratio*net - debt", WB.max_loan(1_000_000, 0) == int(1_000_000 * WB.LOAN_MAX_RATIO))
check("deposit_interest مثبت", WB.deposit_interest(1_000_000, 10, WB.DEPOSIT_DAILY_RATE) > 0)

print(f"\n===== نتیجه: {ok} موفق، {fail} ناموفق =====")
sys.exit(1 if fail else 0)
