# -*- coding: utf-8 -*-
"""تستِ منطقیِ خالصِ مرحله ۱۸ (بدونِ دیتابیس/aiogram).

اجرا:
    python stage18_logic_test.py
"""
from app.data import alliance as A
from app.data import war as W

_passed = 0
_failed = 0


def check(name, cond):
    global _passed, _failed
    if cond:
        _passed += 1
        print(f"✅ {name}")
    else:
        _failed += 1
        print(f"❌ {name}")


# --------------------------- ۵۰ شهرِ قابلِ تصرف ---------------------------
check("NPC_CITIES == 50", len(W.NPC_CITIES) == 50)
check("NPC_CITY_ORDER == 50", len(W.NPC_CITY_ORDER) == 50)
check("کلیدها یکتا هستند", len(set(W.NPC_CITY_ORDER)) == 50)
check("شهرِ دستی capitale هست", "capitale" in W.NPC_CITIES)
check("شهرِ تولیدی palermo هست", "palermo" in W.NPC_CITIES)
check("هر شهر کلیدهای لازم دارد",
      all(set(c) >= {"name", "population", "defense", "reward"} for c in W.NPC_CITIES.values()))
check("get_npc_city کار می‌کند", W.get_npc_city("palermo") is not None and W.get_npc_city("nope") is None)

# --------------------------- منعِ حمله به ضعیف‌ترها ---------------------------
check("WEAK_TARGET_RATIO = 0.5", W.WEAK_TARGET_RATIO == 0.5)
check("مهاجمِ تازه‌کار محدودیت ندارد", W.min_target_power(200) == 0)
check("حداقلِ هدف برای قدرتِ 1000 == 500", W.min_target_power(1000) == 500)
check("حمله به هدفِ نصفِ قدرت مجاز است", W.attack_allowed(1000, 500) is True)
check("حمله به هدفِ خیلی ضعیف ممنوع است", W.attack_allowed(1000, 499) is False)
check("تازه‌کار می‌تواند به هر کسی حمله کند", W.attack_allowed(200, 1) is True)

# --------------------------- جنگِ کشوری ---------------------------
check("ضریبِ رده‌های کشور", set(W.COUNTRY_TIER_POWER) == {"small", "medium", "large", "empire"})
check("country_power رده‌ی بالاتر ← قدرتِ بیشتر",
      W.country_power("empire", 100_000, 5_000) > W.country_power("small", 100_000, 5_000))
check("country_power غیرمنفی", W.country_power("small", 0, 0) >= 0)
check("درصدِ غنیمتِ کشوری در بازه",
      W.COUNTRY_LOOT_PCT_MIN <= W.country_loot_percent(5000, 3000) <= W.COUNTRY_LOOT_PCT_MAX)
check("درصدِ غرامتِ کشوری در بازه",
      W.COUNTRY_PENALTY_PCT_MIN <= W.country_penalty_percent(3000, 5000) <= W.COUNTRY_PENALTY_PCT_MAX)
check("غنیمتِ کشوری سقف‌خورده", W.country_loot_amount(1000, 50) == 500)
check("غنیمت بیش از موجودی نمی‌شود", W.country_loot_amount(100, 200) == 100)
check("غرامتِ کشوری سقف‌خورده", W.country_penalty_amount(1000, 30) == 300)
check("roll_country_battle بولین", isinstance(W.roll_country_battle(1000, 1000), bool))

# --------------------------- اتحادیه‌ها ---------------------------
check("tag معتبر", A.tag_is_valid("Cosa_Nostra") is True)
check("tag نامعتبر (کوتاه)", A.tag_is_valid("ab") is False)
check("normalize_tag @ و حروف کوچک", A.normalize_tag("@Family") == "family")
check("clamp_sub_pct در بازه", A.clamp_sub_pct(999) == A.SUB_PCT_MAX and A.clamp_sub_pct(0) == A.SUB_PCT_MIN)
check("clamp_sub_days در بازه", A.clamp_sub_days(999) == A.SUB_DAYS_MAX and A.clamp_sub_days(0) == A.SUB_DAYS_MIN)
check("سقفِ اعضا در سطح 1 == 20", A.member_cap_for_level(1) == 20)
check("سقفِ اعضا سقف‌خورده در 200", A.member_cap_for_level(100) == A.MEMBER_CAP_MAX)
check("cap_is_maxed در سطحِ بالا", A.cap_is_maxed(100) is True)
check("رأی‌گیری: 50٪ تصویب می‌شود", A.vote_passes(5, 10) is True)
check("رأی‌گیری: کمتر از 50٪ رد", A.vote_passes(4, 10) is False)
check("بونوسِ درآمد سقف 15٪", A.income_bonus_pct(100) == 15)
check("قدرتِ اتحادیه ← نظامی + 20٪ اعضا", A.alliance_power(1000, 5000) == 2000)
check("درصدِ غنیمتِ اتحادیه در بازه",
      A.WAR_LOOT_PCT_MIN <= A.war_loot_percent(5000, 3000) <= A.WAR_LOOT_PCT_MAX)
check("roll_alliance_battle بولین", isinstance(A.roll_alliance_battle(1000, 1000), bool))

print(f"\n——————————————————————————————")
print(f"نتیجه: {_passed} موفق، {_failed} ناموفق")
if _failed:
    raise SystemExit(1)
