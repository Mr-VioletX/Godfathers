# -*- coding: utf-8 -*-
"""تستِ منطقِ خالصِ مرحله ۲۱ (بدونِ aiogram/sqlalchemy/شبکه).

فقط app.data.admin (و کمی app.data.subscription) را می‌آزماید.
اجرا: python stage21_logic_test.py
"""
import sys

from app.data import admin as A

_fails = []


def check(name, cond):
    status = "✅" if cond else "❌"
    print(f"{status} {name}")
    if not cond:
        _fails.append(name)


print("=== دسترسی‌ها (permissions) ===")
check("PERMISSION_ORDER و PERMISSIONS هم‌طول‌اند",
      set(A.PERMISSION_ORDER) == set(A.PERMISSIONS.keys()))
check("MAIN_ONLY زیرمجموعه‌ی PERMISSIONS است",
      A.MAIN_ONLY.issubset(set(A.PERMISSIONS.keys())))
check("channel و admins در MAIN_ONLY هستند",
      "channel" in A.MAIN_ONLY and "admins" in A.MAIN_ONLY)
check("GRANTABLE شاملِ MAIN_ONLY نیست",
      all(k not in A.GRANTABLE for k in A.MAIN_ONLY))
check("GRANTABLE شاملِ users/economy/subscriptions/titles است",
      all(k in A.GRANTABLE for k in ("users", "economy", "subscriptions", "titles")))
check("is_valid_perm درست کار می‌کند",
      A.is_valid_perm("users") and not A.is_valid_perm("nope"))
check("perm_label ایموجی دارد",
      "👥" in A.perm_label("users"))

print("\n=== normalize/dumps ===")
check("normalize_perms تکراری‌ها و نامعتبرها را حذف می‌کند",
      A.normalize_perms(["users", "users", "xxx", "economy"]) == ["users", "economy"])
check("normalize_perms خروجی را بر اساسِ PERMISSION_ORDER مرتّب می‌کند",
      A.normalize_perms(["stats", "users"]) == ["users", "stats"])
check("normalize_perms رشته‌ی JSON را می‌پذیرد",
      A.normalize_perms('["users","news"]') == ["users", "news"])
check("normalize_perms رشته‌ی کامایی را می‌پذیرد",
      A.normalize_perms("users, news") == ["users", "news"])
check("dumps_perms یک JSONِ معتبر می‌دهد",
      A.dumps_perms(["users"]) == '["users"]')
check("normalize_perms خالی/None",
      A.normalize_perms(None) == [] and A.normalize_perms([]) == [])

print("\n=== رمزِ عبور ===")
h = A.hash_password("secret123")
check("hash_password قالبِ <salt>$<hex>", "$" in h and len(h.split("$")[1]) == 64)
check("verify_password با رمزِ درست", A.verify_password("secret123", h))
check("verify_password با رمزِ غلط", not A.verify_password("WRONG", h))
check("verify_password با storedِ None", not A.verify_password("x", None))
check("دو هش از یک رمز متفاوت‌اند (saltِ تصادفی)",
      A.hash_password("same") != A.hash_password("same"))

print("\n=== رمزِ اولیه ===")
pw = A.generate_initial_password()
check("generate_initial_password طولِ پیش‌فرض ۸", len(pw) == 8)
check("رمزِ اولیه کاراکترِ گیج‌کننده (O/0/I/1/l) ندارد",
      not any(c in pw for c in "O0I1l"))
check("generate_initial_password حداقل ۴",
      len(A.generate_initial_password(2)) >= 4)

print("\n=== اعتبارسنجیِ رمزِ جدید ===")
ok, val = A.password_ok("abcd")
check("password_ok رمزِ معتبر", ok and val == "abcd")
ok2, _ = A.password_ok("ab")
check("password_ok رمزِ کوتاه را رد می‌کند", not ok2)
ok3, _ = A.password_ok("has space")
check("password_ok فاصله را رد می‌کند", not ok3)

print("\n=== کلماتِ ورود/خروج/راهنما ===")
check("«ادمین مود» در ENTER_WORDS", "ادمین مود" in A.ENTER_WORDS)
check("«خروج از حالت ادمین مود» در EXIT_WORDS",
      "خروج از حالت ادمین مود" in A.EXIT_WORDS)
check("«راهنمای ادمین‌ها» در HELP_ADMIN_WORDS",
      "راهنمای ادمین‌ها" in A.HELP_ADMIN_WORDS)
check("«راهنمای ادمین اصلی» در HELP_MAIN_WORDS",
      "راهنمای ادمین اصلی" in A.HELP_MAIN_WORDS)
check("ENTER و EXIT هم‌پوشانی ندارند",
      A.ENTER_WORDS.isdisjoint(A.EXIT_WORDS))

print("\n=== متنِ راهنما ===")
main_help = A.help_text(True, A.PERMISSION_ORDER)
sub_help = A.help_text(False, ["users", "news"])
check("راهنمای اصلی همه‌ی بخش‌ها را دارد",
      all(A.PERMISSIONS[k]["label"] in main_help for k in A.PERMISSION_ORDER))
check("راهنمای فرعی فقط بخش‌هایِ مجاز را دارد",
      A.PERMISSIONS["users"]["label"] in sub_help
      and A.PERMISSIONS["admins"]["label"] not in sub_help)
check("راهنمای فرعیِ بدونِ دسترسی پیامِ مناسب دارد",
      "دسترسی" in A.help_text(False, []))

print("\n=== subscription (هم‌خوانی با پنلِ ادمین) ===")
from app.data import subscription as S
check("TIER_ORDER شاملِ free است", "free" in S.TIER_ORDER)
non_free = [t for t in S.TIER_ORDER if t != "free"]
check("حداقل یک سطحِ غیررایگان برای پیکرِ ادمین هست", len(non_free) >= 1)
check("get_tier برای هر سطح dict می‌دهد",
      all(isinstance(S.get_tier(t), dict) for t in S.TIER_ORDER))
code = S.generate_tracking_code()
check("generate_tracking_code با SUB- شروع می‌شود", code.startswith("SUB-"))

print("\n" + ("=" * 40))
if _fails:
    print(f"❌ {len(_fails)} تست رد شد: {_fails}")
    sys.exit(1)
print("🎉 همه‌ی تست‌هایِ منطقیِ مرحله ۲۱ پاس شدند.")
