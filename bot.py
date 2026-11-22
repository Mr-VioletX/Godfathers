# app/bot.py
import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from app.services.assistant_ticker import assistant_reminder_loop
from app.services.spy_ticker import spy_ticker_loop
from app.services.city_ticker import city_ticker_loop   # مرحله 13
from app.services.chat_ticker import chat_request_expiry_loop   # مرحله 13.6
from app.services.news_ticker import news_daily_loop   # مرحله 20 - اخبار روزانه
from app.services.alliance_ticker import alliance_tick_loop  # 🆕 v1.7.9.1 — تیکرِ اتحادیه
from app.services.football_market import market_loop as football_market_loop  # 🆕 v1.7.9.7
from app.services.football_friday import friday_loop as football_friday_loop  # 🆕 v1.7.9.9
from app.services.football_live import live_loop as football_live_loop  # 🆕 v1.7.10.0
from app.services.football_ucl import ucl_loop as football_ucl_loop  # 🆕 v1.7.10.0
from app.services.league_ticker import league_weekly_loop   # مرحله 29 - لیگِ حذفیِ هفتگی
from app.services.hospital_ticker import hospital_ticker_loop   # 🆕 v1.7.6.3 - مرگِ مجروحان پس از ۲۴ ساعت

from app.config import settings
from app.database.engine import init_models, async_session
from app.services import admin_service, event_service
from app.services.ranked_battle_finalizer import finalize_finished_ranked_battles
from app.handlers import assistant, base, city, estate, factory, menu, misc, profile, start, theft, force_join
from app.handlers import contacts, spy
from app.handlers import ranking
from app.handlers import chat
from app.handlers import sports
from app.handlers import football  # 🆕 v1.7.9.2 — فوتبال منیجر
from app.handlers import warehouse
from app.handlers import transfer, kapatolo
from app.handlers import war, alliance
from app.handlers import alliance_war  # 🆕 v1.7.9.1 — جنگِ زنده‌ی اتحادیه
from app.handlers import military, branding, worldbank
from app.services.city_migration import refund_and_cleanup_old_city_system  # 🆕 بچ ۴ — رفاندِ شهر/کشورِ قدیمی
from app.handlers import subscription, news
from app.handlers import walkthrough
from app.handlers import dark_world  # 🆕 v1.8.3.0 — دنیای سیاه
from app.handlers import dark_world_cases  # 🆕 v1.8.3.1 — پرونده‌های چندشاخه
from app.handlers import dark_world_pursuit  # 🆕 v1.8.3.2 — تعقیب و مخفیگاه
from app.handlers import dark_world_npcs  # 🆕 v1.8.3.3 — شبکه پیشرفته NPC
from app.handlers import dark_world_employment  # 🆕 v1.8.3.4 — بازار کار کاربران
from app.handlers import dark_world_smuggling  # 🆕 v1.8.3.5 — قاچاق و بازار اختیاری
from app.handlers import dark_world_finance  # 🆕 v1.8.3.6 — بازار سیاه و پول‌شویی
from app.handlers import dark_world_raids  # 🆕 v1.8.3.7 — شبیخون PvP
from app.handlers import dark_world_seasons  # 🆕 v1.8.3.8 — روایت فصلی
from app.handlers import dark_world_competitive  # 🆕 v1.8.3.9 — پایان فصل رقابتی
from app.handlers import dark_world_laboratory  # 🆕 v1.8.4.0 — آزمایشگاه داستانی
from app.handlers import dark_world_recipes  # 🆕 v1.8.4.1 — فرمول‌ها و گلخانه
from app.handlers import dark_world_distribution  # 🆕 v1.8.4.2 — شبکه توزیع
from app.handlers import dark_world_empire  # 🆕 v1.8.4.3 — رقبا، بازرسی و امپراتوری
from app.handlers import common_ui   # 🆕 مرحله ۲۸ — دکمه‌ی انصرافِ عمومی
from app.middlewares.state_guard import StateGuardMiddleware  # 🆕 مرحله ۳۰
from app.middlewares.tracking import TrackingMiddleware
from app.middlewares.spam_report import SpamReportMiddleware
from app.middlewares.admin_controls import AdminControlMiddleware
from app.middlewares.force_join import ForceJoinMiddleware
from app.middlewares import outgoing_safety   # 🆕 نگهبانِ خروجی: متنِ بلند + HTML خراب
from app.middlewares.update_logging import UpdateLoggingMiddleware, log_unhandled_error  # 🆕 v1.8.2.0 — لاگِ کاملِ آپدیت‌ها/خطاها
from app.services.fsm_storage import DatabaseFSMStorage  # 🆕 مرحله ۳۰
from app.handlers import titles as titles_handlers
from app.handlers import admin as admin_handlers   # مرحله 21 - سیستم ادمین (این ایمپورت وجود نداشت و ادمین‌مود اصلا وصل نبود!)

# 🆕 v1.8.2.0 — لاگینگِ کامل: کنسول + logs/bot.log + logs/errors.log + logs/updates.log
from app.utils.logging_setup import setup_logging

setup_logging()

# مرحله 22 - bot و dp اکنون در سطحِ ماژول ساخته می‌شوند (نه فقط داخلِ main).
# دلیل: هم اجرای Polling (کامپیوتر شخصی/VPS، تابع main پایین همین فایل) و هم
# passenger_wsgi.py (Webhook، مخصوصِ هاست اشتراکی) باید به همین نمونهِ bot/dp دسترسی داشته باشند.
bot = Bot(
    token=settings.bot_token,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
)
# 🆕 مرحله ۳۰ — انبارِ پایدارِ FSM روی دیتابیس:
#   قبلاً MemoryStorage بود و با خواب/ریستارتِ پروسه وضعیتِ کاربر پاک می‌شد؛
#   پس اگر کاربر بعد از دستور کمی صبر می‌کرد، نام/مقدارِ بعدی گرفته نمی‌شد.
# 🆕 مرحله ۳۲ — قبلاً فقط روی هاست از این انبار استفاده می‌شد؛ برای یکدستیِ کاملِ
# دو نسخه (و رفعِ باگِ دوباره نوشتنِ منطقِ این فایل برای هاست)، اینجا هم از همان
# انبارِ پایدار استفاده می‌شود (روی پایتونِ معمولی هم کاملاً بی‌خطر و بسیار سریع است).
outgoing_safety.install(bot)   # 🆕 تکه‌کردنِ خودکارِ پیامِ بلند و جلوگیری از کرشِ HTML
dp = Dispatcher(storage=DatabaseFSMStorage())
# 🆕 مرحله ۳۰ — نگهبانِ عمومیِ وضعیت: انصرافِ قطعی + لغویِ خودکارِ عملیاتِ نیمه‌کاره
# 🆕 مرحله ۳۲ — حالا روی دکمهٔ شیشه‌ای هم ثبت می‌شود (قبلاً فقط روی پیام بود؛
# باعث می‌شد کلیکِ دکمهٔ دیگر حین‌که عملیاتی نیمه‌کاره باز بود، لغو نشود).
# 🆕 v1.8.2.0 — ردِ کاملِ آپدیت‌ها (logs/updates.log)؛ بیرونی‌ترین لایه تا پیش از همه چیز ثبت شود
dp.message.outer_middleware(UpdateLoggingMiddleware())
dp.callback_query.outer_middleware(UpdateLoggingMiddleware())
dp.errors.register(log_unhandled_error)   # traceback کاملِ خطاها → logs/errors.log
dp.message.outer_middleware(StateGuardMiddleware())
dp.callback_query.outer_middleware(StateGuardMiddleware())
dp.message.outer_middleware(AdminControlMiddleware())
dp.callback_query.outer_middleware(AdminControlMiddleware())
dp.message.outer_middleware(ForceJoinMiddleware())
dp.callback_query.outer_middleware(ForceJoinMiddleware())
dp.message.middleware(TrackingMiddleware())
dp.message.outer_middleware(SpamReportMiddleware())
dp.callback_query.outer_middleware(SpamReportMiddleware())

# ترتیب مهم: ادمین قبل از همه (تا فیلتر متنی ادمین‌مود زودتر بررسی شود)، سپس start/profile پیش از menu؛ menu پیش از theft
dp.include_router(admin_handlers.router)   # مرحله 21 - قبلا اینجا include نشده بود؛ الان اضافه شد
dp.include_router(start.router)
dp.include_router(force_join.router)
dp.include_router(profile.router)
dp.include_router(chat.router)
dp.include_router(menu.router)
dp.include_router(theft.router)
dp.include_router(base.router)
dp.include_router(estate.router)
dp.include_router(factory.router)
dp.include_router(city.router)
dp.include_router(dark_world.router)
dp.include_router(dark_world_cases.router)
dp.include_router(dark_world_pursuit.router)
dp.include_router(dark_world_npcs.router)
dp.include_router(dark_world_employment.router)
dp.include_router(dark_world_smuggling.router)
dp.include_router(dark_world_finance.router)
dp.include_router(dark_world_raids.router)
dp.include_router(dark_world_seasons.router)
dp.include_router(dark_world_competitive.router)
dp.include_router(dark_world_laboratory.router)
dp.include_router(dark_world_recipes.router)
dp.include_router(dark_world_distribution.router)
dp.include_router(dark_world_empire.router)
dp.include_router(assistant.router)
dp.include_router(titles_handlers.router)
dp.include_router(contacts.router)
dp.include_router(spy.router)
dp.include_router(ranking.router)
dp.include_router(football.router)   # 🆕 v1.7.9.2 — قبل از sports تا فوتبالِ جدید جایگزین شود
dp.include_router(sports.router)
dp.include_router(warehouse.router)
dp.include_router(transfer.router)
dp.include_router(kapatolo.router)
dp.include_router(war.router)
dp.include_router(alliance.router)
dp.include_router(alliance_war.router)  # 🆕 v1.7.9.1 — جنگِ زنده‌ی اتحادیه
dp.include_router(military.router)
dp.include_router(branding.router)
dp.include_router(worldbank.router)
dp.include_router(subscription.router)
dp.include_router(news.router)
dp.include_router(walkthrough.router)
dp.include_router(common_ui.router)   # 🆕 مرحله ۲۸
dp.include_router(misc.router)

_background_tasks_started = False


async def ensure_started() -> None:
    """کارهایی که باید حداقل یک‌بار قبل از پردازشِ هر آپدیت انجام شوند (ساختِ جدول‌های دیتابیس).
    هم از main() (Polling) و هم از passenger_wsgi.py (Webhook، هاستِ اشتراکی) صدا زده می‌شود؛
    اجرای تکراری‌اش کاملا بی‌خطر است."""
    await init_models()
    # v1.7.7.5 — بارگذاری ضریب اقتصاد شهر از DB
    try:
        from app.services import mafia_city_service as _mcs
        from app.database.engine import async_session as _as
        async with _as() as _s:
            await _mcs.refresh_city_balance_settings(_s)
    except Exception:
        pass

    # 🆕 مرحله ۲۲.۱ — بازیابیِ فهرستِ ادمین‌هایی که قبلاً درِ حالتِ ادمین بوده‌اند، از دیتابیس؛
    # باعث می‌شود ری‌استارتِ پسنجر/ربات (هاستِ اشتراکی) باعثِ خروجِ ناخواسته‌ی ادمین از حالتِ ادمین نشود.
    async with async_session() as session:
        await admin_service.load_active_admin_sessions(session)
        # 🆕 مرحله ۲۷ — وضعیتِ رویدادهایِ بونس (XP/پول) هم در استارتِ ربات به کش لود می‌شود
        await event_service.load_bonus(session)
        # 🆕 v1.7.6.4 — bot را می‌دهیم تا گزارشِ پایانِ نبردهای رنکینگ به دو طرف پیام شود
        finalized = await finalize_finished_ranked_battles(session, bot=bot)
        if finalized:
            await session.commit()
        # 🆕 بچ ۴ — مهاجرتِ یک‌باره: رفاندِ نقدیِ شهر/کشورِ قدیمی و پاکسازیِ جدول‌ها
        try:
            from app.services.title_season import bootstrap as bootstrap_title_season
            await bootstrap_title_season(session)
        except Exception as _e:  # pragma: no cover
            logging.warning("title season migration skipped: %s", _e)
        try:
            await refund_and_cleanup_old_city_system(session)
        except Exception as _e:  # pragma: no cover
            logging.warning("city refund migration skipped: %s", _e)


async def main() -> None:
    """اجرای مستقیم با Polling - مخصوصِ کامپیوتر شخصی یا VPS با دسترسی کامل (مسیر B).
    روی هاست اشتراکی (مسیر A) این تابع اجرا نمی‌شود؛ به‌جایش passenger_wsgi.py استفاده می‌شود."""
    global _background_tasks_started
    try:
        _ver = open("VERSION.txt", encoding="utf-8").read().strip()
    except Exception:
        _ver = "?"
    logging.warning("🤖 Godfather bot STARTING — VERSION = %s", _ver)
    await ensure_started()

    # 🆕 v1.7.9.2 — ریست کامل فوتبالِ قدیمی (فقط یک‌بار)؛ باقی ورزش‌ها دست‌نخورده
    try:
        async with async_session() as _fs:
            from app.services.football_service import reset_old_football_once
            await reset_old_football_once(_fs)
    except Exception:
        pass

    if not _background_tasks_started:
        asyncio.create_task(assistant_reminder_loop(bot))
        asyncio.create_task(spy_ticker_loop(bot))
        asyncio.create_task(city_ticker_loop())
        asyncio.create_task(chat_request_expiry_loop(bot))
        asyncio.create_task(news_daily_loop(bot))
        asyncio.create_task(alliance_tick_loop(bot))      # 🆕 v1.7.9.1 — نبرد/تولیدخودکار/اشتراکِ اتحادیه
        asyncio.create_task(football_market_loop(bot))      # 🆕 v1.7.9.7 — مزایده/صف پرداخت بازار
        asyncio.create_task(football_friday_loop(bot))      # 🆕 v1.7.9.9 — لیگ جمعه
        asyncio.create_task(football_live_loop(bot))        # 🆕 v1.7.10.0 — پیشروش بازی‌های زنده
        asyncio.create_task(football_ucl_loop(bot))         # 🆕 v1.7.10.0 — لیگ قه��مانان دوشنبه
        asyncio.create_task(league_weekly_loop(bot))
        # 🆕 v1.7.6.3 — ردیف‌های بیمارستانی که ۲۴ ساعت پرداخت نشدند می‌میرند.
        # روی هاستِ اشتراکی (passenger) این لوپ اجرا نمی‌شود؛ به همین دلیل
        # hospital_service.list_wards هنگامِ بازکردنِ بیمارستان هم جاروبِ تنبل دارد.
        asyncio.create_task(hospital_ticker_loop(bot))
        _background_tasks_started = True

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
