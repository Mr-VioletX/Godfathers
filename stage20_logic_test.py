# -*- coding: utf-8 -*-
"""تستِ منطقیِ مرحله ۲۰ — فقط لایه‌ی داده (بدونِ aiogram/sqlalchemy/شبکه).

پوشش:
  1) اشتراکِ ۴ سطحی (ترتیب/مزایا/تخفیف/درآمد/اجازه‌ی لقب)
  2) کدِ پیگیری (فرمت + یکتایی)
  3) اخبارِ روزانه (زمان‌بندی/دایجست/دسته‌بندی)
  4) دستیارِ قابلِ ارتقا (سطوح/ویژگی‌های بازشده/هزینه)
  5) بازتنظیمِ القاب (military_power و سقف‌ها)

اجرا: python stage20_logic_test.py
"""
import datetime as _dt

from app.data import subscription as S
from app.data import news as N
from app.data import assistant as A

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


# ---------------- 1) اشتراکِ ۴ سطحی ----------------
print("\n── اشتراکِ ۴ سطحی ──")
check("چهار سطح تعریف شده", S.TIER_ORDER == ["free", "bronze", "silver", "gold"])
check("هر سطح در TIERS موجود است", all(k in S.TIERS for k in S.TIER_ORDER))
check("سه سطحِ پولی", [t["key"] for t in S.paid_tiers()] == ["bronze", "silver", "gold"])
check("رتبه‌ها صعودی", S.tier_rank("free") < S.tier_rank("bronze") < S.tier_rank("silver") < S.tier_rank("gold"))
check("قیمتِ صعودی", S.price_of("bronze") < S.price_of("silver") < S.price_of("gold"))
check("free رایگان", S.price_of("free") == 0)
check("سطحِ نامعتبر ← free", S.get_tier("???")["key"] == "free")
check("next_tier(bronze)=silver", (S.next_tier("bronze") or {}).get("key") == "silver")
check("next_tier(gold)=None", S.next_tier("gold") is None)
check("تخفیفِ gold > free", S.discount_pct("gold") > S.discount_pct("free"))
check("بونوسِ درآمدِ gold > 0", S.income_bonus_pct("gold") > 0)
check("اعمالِ تخفیف کاهشی", S.apply_discount("gold", 1000) <= 1000)
check("اعمالِ بونوس افزایشی", S.apply_income_bonus("gold", 1000) >= 1000)
check("free بدونِ تغییرِ درآمد", S.apply_income_bonus("free", 1000) == 1000)
check("badge شاملِ نام", S.get_tier("gold")["name"] in S.badge("gold"))
# لقبِ دلخواه: حداقل یک سطحِ پولی باید اجازه بدهد (ملاکِ بازشدنِ لقبِ دلخواه)
check("gold اجازه‌ی لقبِ دلخواه", S.allows_custom_title("gold"))
check("free بدونِ لقبِ دلخواه", not S.allows_custom_title("free"))

# ---------------- 2) کدِ پیگیری ----------------
print("\n── کدِ پیگیری ──")
code = S.generate_tracking_code()
check("پیشوندِ SUB-", code.startswith("SUB-"))
check("طولِ کد = 10 (SUB-+6)", len(code) == 10)
check("بدونِ کاراکترهای مبهم (O/0/I/1/L)", not any(c in code[4:] for c in "O0I1L"))
codes = {S.generate_tracking_code() for _ in range(2000)}
check("یکتاییِ بالا در ۲۰۰۰ تولید (>1990 یکتا)", len(codes) > 1990)

# ---------------- 3) اخبارِ روزانه ----------------
print("\n── اخبارِ روزانه ──")
check("ساعتِ انتشار = 20:00", N.POST_HOUR == 20 and N.POST_MINUTE == 0)
check("دسته‌ها تعریف شده‌اند", set(["war", "title", "alliance", "economy", "event"]).issubset(set(N.CATEGORIES)))
check("دسته‌ی پیش‌فرض معتبر", N.DEFAULT_CATEGORY in N.CATEGORIES)
meta = N.category_meta("war")
check("category_meta شاملِ emoji/label", "emoji" in meta and "label" in meta)
check("format_item یک رشته می‌دهد", isinstance(N.format_item("war", "حمله‌ای رخ داد"), str))
secs = N.seconds_until_next_post()
check("seconds_until_next_post در بازه‌ی ۰..۲۴h", 0 <= secs <= 24 * 3600 + 60)
# دایجستِ خالی
now = _dt.datetime.utcnow()
empty = N.compile_digest([], now)
check("دایجستِ خالی رشته است", isinstance(empty, str))
# دایجست با چند آیتم ساختگی
fake = [
    {"category": "war", "text": "جنگِ شهری", "importance": 3, "created_at": now},
    {"category": "economy", "text": "سقوطِ بازار", "importance": 1, "created_at": now},
]
dig = N.compile_digest(fake, now)
check("دایجستِ غیرخالی متن دارد", isinstance(dig, str) and len(dig) > 0)

# ---------------- 4) دستیارِ قابلِ ارتقا ----------------
print("\n── دستیارِ قابلِ ارتقا ──")
check("حداکثر سطح = 4", A.ASSISTANT_MAX_LEVEL == 4)
check("سطحِ 1 ویژگیِ اقتصادی دارد", "economy" in A.unlocked_features(1))
check("سطحِ 4 ویژگیِ اخبار دارد", "news" in A.unlocked_features(4))
check("ویژگی‌های سطحِ بالاتر ⊇ پایین‌تر", set(A.unlocked_features(1)).issubset(set(A.unlocked_features(4))))
check("can_report(1, economy) درست", A.can_report(1, "economy"))
check("can_report(1, news) نادرست", not A.can_report(1, "news"))
check("هزینه‌ی ارتقا صعودی", A.upgrade_cost(2) < A.upgrade_cost(3) < A.upgrade_cost(4))
check("next_upgrade(4)=None", A.next_upgrade(4) is None)

# ---------------- 5) بازتنظیمِ القاب ----------------
print("\n── بازتنظیمِ القاب ──")
from app.data import titles_balance as TB

sample = [
    {"key": "lady_of_valhalla", "stat": "military_power", "op": ">=", "value": 1},
    {"key": "king_of_valhalla", "stat": "military_power", "op": ">=", "value": 1},
    {"key": "special_none", "stat": None, "op": None, "value": None},
]
changed = TB.apply_balance(sample)
check("apply_balance تعدادِ تغییر برمی‌گرداند", isinstance(changed, int))
valh = {t["key"]: t for t in sample}
check("lady_of_valhalla military_power ≥ 50000", valh["lady_of_valhalla"]["value"] >= 50_000)
check("king_of_valhalla military_power ≥ 50000", valh["king_of_valhalla"]["value"] >= 50_000)
check("لقبِ stat=None دست‌نخورده", valh["special_none"]["value"] is None)

# اطمینان از اعمالِ بازتنظیم روی دیتای واقعیِ titles.py
from app.data import titles as T
tbk = T.TITLES_BY_KEY
if "lady_of_valhalla" in tbk and tbk["lady_of_valhalla"].get("stat") == "military_power":
    check("titles.py → lady_of_valhalla بازتنظیم شد", tbk["lady_of_valhalla"]["value"] >= 50_000)

print(f"\n──────────────────────────")
print(f"پاس: {_passed}   —   مردود: {_failed}")
if _failed:
    raise SystemExit(1)
print("🎉 همه‌ی تست‌های منطقیِ مرحله ۲۰ پاس شدند.")
