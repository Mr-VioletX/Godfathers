# -*- coding: utf-8 -*-
"""log_healthcheck.py -- تستِ سریعِ لاگ — ۱۰۰ خط‌ِ اخرِ لاگ را می‌خواند و دنبالِ خطا/استثنا می‌گردد.

چرا لازم است؟
-----------
روی هاست (cPanel) خروجیِ cron_ticks.py با `>> cron.log 2>&1` در همین پوشه‌ی پروژه ذخیره می‌شود.
روی VPS/کامپیوترِ شخصی هم اگر ربات را با ریدایرکت اجرا کرده باشی
(مثلاً `python3 bot.py >> bot.log 2>&1 &`) همین اسکریپت روی هر فایلِ لاگی کار می‌کند.

استفاده:
    python3 log_healthcheck.py                     # بررسیِ cron.log کنارِ همین اسکریپت، ۱۰۰ خطِ اخر
    python3 log_healthcheck.py bot.log              # بررسیِ فایلِ دلخواه
    python3 log_healthcheck.py cron.log --lines 300 # تعدادِ دیگری از خطوط

خروج:
    - کدِ بازگشت ۰ یعنی هیچ خطا/استثنایی در آخرین N خط پیدا نشد.
    - کدِ بازگشت ۱ یعنی حداقل یک خطا/استثنا پیدا شد (مناسب برای استفاده در اسکریپت‌های مانیتورینگ/هشدار).
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from collections import deque

# الگوی تشخیصِ خطوطِ مشکوک/خطادار:
#   - هر خطی که با یکی از سطح‌بندی (levelname) های لاگینگ پایتون شروع شود: ERROR / CRITICAL
#   - هر خطی که با Traceback شروع شود (شروعِ استثنای پایتون)
#   - هر خطی که به یک نامِ کلاسِ استثنایِ پایتون (مانند AttributeError:, TypeError:, KeyError: و...) ختم می‌شود
ERROR_PATTERN = re.compile(
    r"(^|[\s:])(ERROR|CRITICAL|Traceback \(most recent call last\)|\w*Error)\b"
)


def tail_lines(path: str, n: int) -> list[str]:
    """۱۰۰ (یا n) خطِ اخرِ فایل را بدون بارگذاریِ کاملِ فایل‌های بزرگ می‌خواند."""
    dq: deque[str] = deque(maxlen=n)
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            dq.append(line.rstrip("\n"))
    return list(dq)


def check_log(path: str, n: int = 100) -> int:
    if not os.path.isfile(path):
        print(f"⚠️  فایلِ لاگ پیدا نشد: {path}")
        return 2

    lines = tail_lines(path, n)
    if not lines:
        print(f"ℹ️  فایلِ لاگ خالی است: {path}")
        return 0

    problems = [(i, ln) for i, ln in enumerate(lines, 1) if ERROR_PATTERN.search(ln)]

    print(f"🔍 بررسیِ {len(lines)} خطِ اخرِ فایل: {path}\n")

    if not problems:
        print("✅ هیچ خطا/استثنایی در این بازه پیدا نشد.")
        return 0

    print(f"❌ {len(problems)} خط/استثنای در آخرین {len(lines)} خط پیدا شد:\n")
    for i, ln in problems:
        print(f"  [خطِ {i}] {ln}")
    return 1


def main() -> None:
    parser = argparse.ArgumentParser(description="بررسیِ آخرین N خطِ یک فایلِ لاگ برای خطا/استثنا")
    parser.add_argument(
        "logfile", nargs="?", default="cron.log",
        help="مسیرِ فایلِ لاگ (پیش‌فرض: cron.log کنارِ همین اسکریپت)",
    )
    parser.add_argument("--lines", type=int, default=100, help="تعدادِ خطوطِ اخر برای بررسی (پیش‌فرض ۱۰۰)")
    args = parser.parse_args()

    base_dir = os.path.dirname(os.path.abspath(__file__))
    path = args.logfile if os.path.isabs(args.logfile) else os.path.join(base_dir, args.logfile)

    exit_code = check_log(path, args.lines)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
