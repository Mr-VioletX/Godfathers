# مرحله ۸۳ — v1.8.2.6 — رفع خطاهای stderr

## نتیجه تحلیل فایل جدید
- اندازه فایل: 16,302,095 بایت
- تعداد خطوط: 208,534
- بلوک‌های `--- Logging error ---`: 5,888
- tracebackها: 5,477
- `UnicodeEncodeError`: 5,476
- `sqlalchemy.exc.InvalidRequestError`: 1
- خطاهای قفل دیتابیس، کمبود thread، Telegram API، timeout، connection، NameError، TypeError، AttributeError و KeyError: صفر

## اصلاحات
1. `SafeConsoleHandler` جایگزین StreamHandler عادی شد؛ کنسول ASCII دیگر با متن فارسی/Unicode traceback داخلی تولید نمی‌کند.
2. فایل‌های `bot.log`، `errors.log` و `updates.log` همچنان UTF-8 واقعی ذخیره می‌شوند.
3. INFOهای پرتعداد `godfather.updates` از کنسول Passenger فیلتر و فقط در فایل‌های لاگ نگه‌داری می‌شوند؛ warning/error همچنان در کنسول دیده می‌شود.
4. handlerهای ناامن ساخته‌شده با `basicConfig` هنگام راه‌اندازی حذف می‌شوند.
5. ارزیابی القاب و ساخت دایجست اخبار در sessionهای کاملاً جدا اجرا می‌شوند.
6. هر شکست تراکنش rollback می‌شود و session خراب هرگز دوباره استفاده نمی‌شود.
7. `news_tick_once` موفقیت واقعی را با bool گزارش می‌دهد.
8. host scheduler و cron فقط پس از موفقیت، تاریخ خبر روزانه را ثبت می‌کنند؛ در شکست، اجرای بعدی دوباره تلاش می‌کند.
9. پاک‌سازی `stderr.log` با state مستقل هر 72 ساعت پیاده‌سازی و به startup، host scheduler و cron متصل شد.
10. `cleanup_stderr.py --force` برای پاک‌سازی دستی اضطراری اضافه شد.

## تست‌ها
- compileall: موفق
- UTF-8/AST: 246 فایل، صفر خطا
- تست شبیه‌سازی stream سخت‌گیر ASCII: موفق
- تست حفظ Unicode در فایل‌های لاگ: موفق
- تست زمان‌بندی پاک‌سازی 72 ساعته: موفق
- تست rollback و fresh-session پس از commit ناموفق: موفق
- تست retry زمان‌بند و جلوگیری از false-success: موفق
- رگرسیون مرحله 82: موفق
- رگرسیون v1.8.2.0: 36 موفق، صفر ناموفق
