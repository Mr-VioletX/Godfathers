# -*- coding: utf-8 -*-
"""تستِ منطقیِ خالصِ مرحله ۱۷ (بدونِ نیاز به DB/aiogram/SQLAlchemy).

اجرا:
    python stage17_logic_test.py
"""
import random

from app.data import war as W

_pass = 0


def check(cond, label):
    global _pass
    assert cond, f"FAIL: {label}"
    _pass += 1
    print(f"  ✓ {label}")


def test_win_probability():
    for a, d in [(1, 10_000), (10_000, 1), (500, 500), (0, 0), (123, 456)]:
        p = W.win_probability(a, d)
        check(W.WIN_PROB_FLOOR <= p <= W.WIN_PROB_CEIL, f"win_prob در بازه ({a},{d})={p:.3f}")
    check(W.win_probability(1000, 100) > W.win_probability(100, 1000), "قوی‌تر شانسِ بیشتر")


def test_loot_penalty_pct():
    for a, d in [(1, 10_000), (10_000, 1), (500, 500), (300, 700)]:
        lp = W.loot_percent(a, d)
        pp = W.penalty_percent(a, d)
        check(W.LOOT_PCT_MIN <= lp <= W.LOOT_PCT_MAX, f"loot% در بازه ({a},{d})={lp}")
        check(W.PENALTY_PCT_MIN <= pp <= W.PENALTY_PCT_MAX, f"penalty% در بازه ({a},{d})={pp}")
    check(W.loot_percent(10_000, 1) >= W.loot_percent(500, 500), "غنیمتِ مهاجمِ قوی‌تر بیشتر")
    check(W.penalty_percent(1, 10_000) >= W.penalty_percent(500, 500), "غرامتِ مهاجمِ ضعیف بیشتر")


def test_amounts():
    check(W.loot_amount(10_000, 20, 5_000) == 5_000, "غنیمت سقف‌خورده با موجودیِ بازنده")
    check(W.loot_amount(10_000, 10, 10**9) == 10_000 * 10 // 100 * W.LOOT_DAYS, "غنیمتِ ۱۰روزه")
    check(W.loot_amount(0, 20, 10**9) == 0, "درآمدِ صفر → غنیمتِ صفر")
    check(W.penalty_amount(1_000, 40) == 400, "غرامتِ ۴۰٪")
    check(W.penalty_amount(0, 40) == 0, "غرامتِ بی‌پول")


def test_battle_roll_deterministic():
    r = random.Random(42)
    wins = sum(1 for _ in range(1000) if W.roll_battle(1000, 1000, r))
    check(300 < wins < 700, f"نبردِ ۵۰/۵۰ حولِ نیمه (wins={wins})")
    r = random.Random(42)
    strong = sum(1 for _ in range(1000) if W.roll_battle(10_000, 100, r))
    check(strong > 800, f"مهاجمِ قوی اکثراً می‌برد (wins={strong})")


def test_npc_cities():
    check(set(W.NPC_CITIES) == set(W.NPC_CITY_ORDER), "ترتیبِ شهرها کامل")
    for k, c in W.NPC_CITIES.items():
        check({"name", "population", "defense", "reward"} <= set(c), f"ساختارِ شهرِ {k}")
    check(W.get_npc_city("borgo") is not None and W.get_npc_city("zzz") is None, "get_npc_city")
    check(0.0 <= W.capture_success_chance(500, 500) <= 1.0, "شانسِ تصرف در بازه")


def test_country():
    check(W.country_tier(2, 100_000) is None, "کمتر از ۳ شهر → بدونِ کشور")
    check(W.country_tier(3, W.COUNTRY_FOUND_MIN_POP)[0] == "small", "کوچک")
    check(W.country_tier(4, 18_000)[0] == "medium", "متوسط")
    check(W.country_tier(6, 40_000)[0] == "large", "بزرگ")
    check(W.country_tier(8, 80_000)[0] == "empire", "امپراتوری")
    check(W.can_found_country(3, W.COUNTRY_FOUND_MIN_POP), "واجدِ شرایط")
    check(not W.can_found_country(3, W.COUNTRY_FOUND_MIN_POP - 1), "جمعیتِ ناکافی")
    check(not W.can_found_country(2, 10**9), "شهرِ ناکافی")


def test_safe_message():
    r = random.Random(1)
    msg = W.safe_mode_message(3, r)
    check("3" in msg and isinstance(msg, str), "پیامِ ایمن شاملِ تعدادِ روز")


def main():
    tests = [
        ("win_probability", test_win_probability),
        ("loot/penalty %", test_loot_penalty_pct),
        ("amounts", test_amounts),
        ("battle roll", test_battle_roll_deterministic),
        ("npc cities", test_npc_cities),
        ("country", test_country),
        ("safe message", test_safe_message),
    ]
    for name, fn in tests:
        print(f"▶ {name}")
        fn()
    print(f"\n✅ همه‌ی {_pass} ادعای منطقیِ مرحله ۱۷ پاس شد.")


if __name__ == "__main__":
    main()
