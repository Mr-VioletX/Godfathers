مرحله ۸۳ — v1.8.2.6 — فیکس کامل خطاهای ثبت‌شده در stderr (1).log

فایل ارسالی ۲۰۸٬۵۳۴ خط داشت. تمام ۵٬۴۷۷ traceback آن تحلیل شد:
- ۵٬۴۷۶ مورد UnicodeEncodeError از کنسول ASCII هاست
- ۱ مورد InvalidRequestError از استفاده دوباره از session خبرها پس از commit ناموفق

نسخه حاضر هر دو ریشه را اصلاح می‌کند، false-success خبر روزانه را حذف می‌کند،
برای شکست تراکنش retry ایمن دارد و stderr را با state مستقل هر ۷۲ ساعت پاک می‌کند.
هیچ تغییر گیم‌پلی در این نسخه انجام نشده است.

برای مسیر سفارشی stderr در cPanel:
GODFATHER_STDERR_PATH=/home/USERNAME/APP_PATH/stderr.log

پاک‌سازی اضطراری دستی:
python cleanup_stderr.py --force
