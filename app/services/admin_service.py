# -*- coding: utf-8 -*-
"""سرویسِ مدیریتِ ادمین (مرحله ۲۱).

مسئولیت‌ها:
  • seed کردنِ ادمینِ اصلی (از روی MAIN_ADMIN_ID) + رمزِ پیش‌فرض از settings
  • احرازِ هویت/ورود/تغییرِ رمز
  • انتصاب/عزل/ویرایشِ دسترسیِ ادمین‌ها
  • مدیریتِ تنظیمات (کانالِ گزارش)
  • لاگِ کارها

وضعیتِ «درِ حالتِ ادمین» (ADMIN_ACTIVE) درون‌حافظه است؛ با ریستارتِ ربات
ادمین باید دوباره وارد شود (امن‌تر).
"""
from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import select

from app.config import MAIN_ADMIN_ID, settings
from app.data import admin as A
from app.database.engine import async_session
from app.models.admin import AdminAudit, AdminSetting, AdminUser

# مجموعه‌یِ یوزرآیدیِ ادمین‌هایی که هم‌اکنون درِ حالتِ ادمین‌اند
ADMIN_ACTIVE: set[int] = set()

# مجموعه‌یِ یوزرآیدیِ کاربرانِ محدود/بن‌شده (در حافظه؛ هنگامِ startup پر می‌شود)
BANNED_IDS: set[int] = set()

# کلیدهایِ تنظیمات
SETTING_REPORT_CHANNEL = "report_channel_id"
SETTING_REPORT_CHANNEL_TITLE = "report_channel_title"
SETTING_NEWS_CHANNEL = "news_channel_id"
SETTING_NEWS_CHANNEL_TITLE = "news_channel_title"
# 🆕 مرحله ۲۱.۱ — پنلِ گسترده‌یِ اشتراک: ادمینِ فروش + دریافت/عدمِ دریافتِ پیامِ درخواست توسطِ ادمینِ اصلی
SETTING_SALES_ADMIN_ID = "sales_admin_id"
SETTING_MAIN_NOTIFY_PURCHASE = "main_notify_purchase_requests"


# ---------------------------------------------------------------------------
# seed ادمینِ اصلی
# ---------------------------------------------------------------------------
async def ensure_seed_main_admin(session) -> AdminUser | None:
    """ادمینِ اصلی را (اگر MAIN_ADMIN_ID تعریف شده) می‌سازد/به‌روز می‌کند.

    اگر ADMIN_PASSWORD در settings تعریف شده باشد، همان رمزِ پیش‌فرضِ
    ادمینِ اصلی می‌شود (بدونِ اجبارِ تغییر). وگرنه در اولین ورود باید رمز بسازد.
    """
    if not MAIN_ADMIN_ID:
        return None
    row = await session.get(AdminUser, None) if False else await _by_uid(session, MAIN_ADMIN_ID)
    if row is None:
        row = AdminUser(
            tg_user_id=MAIN_ADMIN_ID,
            role="main",
            permissions=json.dumps(A.PERMISSION_ORDER),
            active=True,
            label="ادمینِ اصلی",
        )
        if settings.admin_password:
            row.password_hash = A.hash_password(settings.admin_password)
            row.must_change_password = False
        else:
            row.password_hash = None
            row.must_change_password = True
        session.add(row)
        await session.commit()
    else:
        changed = False
        if row.role != "main":
            row.role = "main"
            changed = True
        if not row.active:
            row.active = True
            changed = True
        # اگر رمزی تاکنون ثبت نشده ولی settings.admin_password داریم، همان را قرار بده
        if row.password_hash is None and settings.admin_password:
            row.password_hash = A.hash_password(settings.admin_password)
            row.must_change_password = False
            changed = True
        if changed:
            await session.commit()
    return row


async def _by_uid(session, uid: int) -> AdminUser | None:
    return (await session.execute(
        select(AdminUser).where(AdminUser.tg_user_id == uid)
    )).scalar_one_or_none()


# ---------------------------------------------------------------------------
# خواندن/دسترسی
# ---------------------------------------------------------------------------
def is_main_admin(uid: int) -> bool:
    return MAIN_ADMIN_ID is not None and uid == MAIN_ADMIN_ID


async def get_admin(session, uid: int) -> AdminUser | None:
    """ادمینِ فعال (active=True) را برمی‌گرداند، وگرنه None."""
    row = await _by_uid(session, uid)
    if row is not None and row.active:
        return row
    return None


async def get_admin_any(session, uid: int) -> AdminUser | None:
    """ادمین را حتی اگر غیرفعال باشد برمی‌گرداند."""
    return await _by_uid(session, uid)


async def is_admin(session, uid: int) -> bool:
    """آیا کاربر یک ادمینِ فعال است؟ (مستقل از اینکه درِ حالتِ ادمین باشد)."""
    return (await get_admin(session, uid)) is not None


def perms_of(admin: AdminUser | None) -> list[str]:
    if admin is None:
        return []
    if admin.role == "main":
        return list(A.PERMISSION_ORDER)
    return A.normalize_perms(admin.permissions)


def has_permission(admin: AdminUser | None, perm_key: str) -> bool:
    if admin is None or not admin.active:
        return False
    if admin.role == "main":
        return True
    return perm_key in A.normalize_perms(admin.permissions)


async def list_admins(session) -> list[AdminUser]:
    rows = (await session.execute(
        select(AdminUser).order_by(AdminUser.role.desc(), AdminUser.created_at)
    )).scalars().all()
    return list(rows)


# ---------------------------------------------------------------------------
# حالتِ ادمین (درون‌حافظه)
# ---------------------------------------------------------------------------
async def is_in_admin_mode(uid: int) -> bool:
    """۲۲۲ رفعِ باگی — روی هاست‌های با چند پروسه (مثلاً Passenger)، مجموعهٔ درون‌حافظهٔ ADMIN_ACTIVE فقط مخصوصِ همان پروسه است و بینِ پروسه‌ها همسان نیست؛ همین باعث می‌شد ادمین‌های فرعی بینِ درخواست‌ها دسترسی قطع شود یا به اشتباه احساس شود که از حالتِ ادمین خارج شده‌اند بدون اینکه دکمهِ خروج را زده باشند.
    ابتدا حافظهِ محلی را چک می‌کند (سریع)؛ اگر نبود، از روی مقدارِ پایدارِ دیتابیس (session_active) می‌خواند و اگر فعال بود آن را در حافظهِ همین پروسه هم گرم می‌کند.
    """
    if uid in ADMIN_ACTIVE:
        return True
    async with async_session() as session:
        admin = await _by_uid(session, uid)
    if admin is not None and admin.active and admin.session_active:
        ADMIN_ACTIVE.add(uid)
        return True
    return False


async def enter_admin_mode(uid: int) -> None:
    """🆕 مرحله ۲۲.۱ — ورود به حالتِ ادمین را هم در حافظه و هم در دیتابیس ثبت می‌کند
    تا با ری‌استارتِ ربات/پسنجر (مثلاً روی هاستِ اشتراکی) از حالتِ ادمین خارج نشود."""
    ADMIN_ACTIVE.add(uid)
    async with async_session() as session:
        admin = await _by_uid(session, uid)
        if admin is not None:
            admin.session_active = True
            await session.commit()


async def exit_admin_mode(uid: int) -> None:
    """🆕 مرحله ۲۲.۱ — خروج از حالتِ ادمین را هم در حافظه و هم در دیتابیس ثبت می‌کند."""
    ADMIN_ACTIVE.discard(uid)
    async with async_session() as session:
        admin = await _by_uid(session, uid)
        if admin is not None:
            admin.session_active = False
            await session.commit()


async def load_active_admin_sessions(session) -> None:
    """🆕 مرحله ۲۲.۱ — هنگامِ راه‌اندازیِ ربات (پولینگ/پسنجر)، فهرستِ ادمین‌هایی که قبلاً
    درِ حالتِ ادمین بوده‌اند (session_active=True) را از دیتابیس به حافظه بر‌می‌گرداند؛
    این‌طوری ری‌استارتِ پسنجر/ربات دیگر باعثِ خروجِ ناخواسته‌ی ادمین از حالتِ ادمین نمی‌شود."""
    rows = (await session.execute(
        select(AdminUser.tg_user_id).where(
            AdminUser.session_active.is_(True),
            AdminUser.active.is_(True),
        )
    )).scalars().all()
    ADMIN_ACTIVE.clear()
    ADMIN_ACTIVE.update(int(x) for x in rows)


# ---------------------------------------------------------------------------
# محدودیت/بن (drop شدنِ پیام‌هایِ کاربرِ بن‌شده در میدل‌ور)
# ---------------------------------------------------------------------------
async def load_banned(session) -> None:
    """فهرستِ کاربرانِ بن‌شده را از دیتابیس به حافظه بارگذاری می‌کند (startup)."""
    from app.models.player import Player
    rows = (await session.execute(
        select(Player.tg_user_id).where(Player.banned.is_(True))
    )).scalars().all()
    BANNED_IDS.clear()
    BANNED_IDS.update(int(x) for x in rows)


async def set_ban(session, uid: int, banned: bool, commit: bool = True) -> None:
    """وضعیتِ بنِ کاربر را در دیتابیس و حافظه هم‌زمان به‌روز می‌کند."""
    from app.models.player import Player
    pl = (await session.execute(
        select(Player).where(Player.tg_user_id == uid)
    )).scalar_one_or_none()
    if pl is not None:
        pl.banned = banned
    if banned:
        BANNED_IDS.add(uid)
    else:
        BANNED_IDS.discard(uid)
    if commit:
        await session.commit()


# ---------------------------------------------------------------------------
# 🆕 مرحله ۲۷ — ابزارهایِ ویژه: هدیهِ همگانی و ریستِ کاملِ یک کاربر
# ---------------------------------------------------------------------------
# جدول‌هایی که در ریستِ کاربر دست نمی‌خورند (خودِ بازیکن جداگانه ریست می‌شود؛
# جدول‌هایِ مدیریتی/لاگ هم باید دست‌نخورده باقی بمانند)
RESET_SKIP_TABLES = {"players", "admins", "admin_settings", "admin_audit"}

# نامِ ستون‌هایی که مالکِ ردیف را مشخص می‌کنند
RESET_OWNER_COLUMNS = (
    "tg_user_id", "owner_id", "player_id", "from_user_id", "to_user_id",
    "opponent_user_id", "contact_id",
    "invited_id", "referrer_id", "attacker_id", "defender_id",
)

# مقدارهایِ پیش‌فرضِ بازگرداندنِ بازیکن به نقطه‌ی صفر (نام/جنسیت/یوزرنیم حفظ می‌شوند)
PLAYER_RESET_DEFAULTS = {
    "level": 1,
    "xp": 0,
    "cash": 1000,
    "fatigue": 0,
    "last_theft_at": None,
    "custom_title": None,
    "earned_titles": None,
    "is_premium": False,
    "jail_until": None,
    "jail_forced": False,
    "bribe_count": 0,
    "kapatolo_cd_level": 0,
    "spy_penalty_until": None,
    "spy_penalty_to": None,
    "spy_penalty_last_at": None,
}


async def gift_all_players(
    session, kind: str, amount: int, commit: bool = True
) -> int:
    """🎁 هدیهِ همگانی: پول یا XP را به همه‌ی بازیکن‌هایِ ثبت‌شده می‌افزاید.

    kind: "cash" یا "xp". خروجی: تعدادِ بازیکن‌هایی که هدیه گرفتند.
    برایِ XP از منطقِ مرکزیِ leveling.add_xp استفاده می‌شود تا لول‌آپ و سقفِ سطح رعایت شود.
    """
    from app.data import leveling
    from app.models.player import Player

    amount = int(amount or 0)
    if amount <= 0 or kind not in ("cash", "xp"):
        return 0
    players = (await session.execute(select(Player))).scalars().all()
    for pl in players:
        if kind == "cash":
            pl.cash = int(pl.cash or 0) + amount
        else:
            leveling.add_xp(pl, amount)
    if commit:
        await session.commit()
    return len(players)


async def reset_player(session, uid: int, commit: bool = True) -> tuple[bool, str]:
    """♻️ ریستِ کاملِ یک کاربر: همه‌ی دارایی‌ها/پایگاه/عمارت/کارخانه/انبار/نیروها و …
    پاک می‌شوند و خودِ بازیکن به حالتِ اولِ بازی برمی‌گردد (نام/جنسیت/یوزرنیم حفظ می‌شود).

    روش کار: روی همه‌ی جدول‌هایِ ثبت‌شده‌ی دیتابیس پیمایش می‌کند و هر ردیفی که ستونِ مالکیتِ
    معروفی دارد و به این کاربر تعلق دارد را حذف می‌کند؛ بنابراین با اضافه‌شدنِ بخش‌هایِ جدیدِ بازی
    هم خودبه‌خود کامل می‌ماند.
    """
    from sqlalchemy import delete as sa_delete

    from app.database.base import Base
    from app.models.player import Player

    pl = (await session.execute(
        select(Player).where(Player.tg_user_id == uid)
    )).scalar_one_or_none()
    # v1.7.6 — حتی اگر ردیف players نبود، باقی‌مانده‌های جداول را پاک کن
    orphan_cleanup = pl is None

    try:
        from app.services import referral_service as refs
        await refs.clear_user_referrals(session, uid)
    except Exception:
        pass

    removed = 0
    for table in Base.metadata.sorted_tables:
        if table.name in RESET_SKIP_TABLES:
            continue
        for col_name in RESET_OWNER_COLUMNS:
            col = table.c.get(col_name)
            if col is None:
                continue
            res = await session.execute(sa_delete(table).where(col == uid))
            removed += int(res.rowcount or 0)

    for field, value in PLAYER_RESET_DEFAULTS.items():
        if hasattr(pl, field):
            setattr(pl, field, value)
    if commit:
        await session.commit()
    return True, f"✅ کاربر <code>{uid}</code> کاملاً ریست شد ({removed} ردیفِ مربوط پاک شد)."



async def delete_player(session, uid: int, commit: bool = True) -> tuple[bool, str]:
    """🗑️ حذف کامل کاربر از دیتابیس (برای تست دعوت / پاکسازی).

    برخلاف reset_player که ردیف players را نگه می‌دارد، اینجا خودِ بازیکن هم حذف می‌شود
    تا با /start دوباره ثبت‌نام کند و لینک دعوت قابل تست باشد.
    """
    from sqlalchemy import delete as sa_delete

    from app.database.base import Base
    from app.models.player import Player

    uid = int(uid)
    pl = (await session.execute(
        select(Player).where(Player.tg_user_id == uid)
    )).scalar_one_or_none()
    # v1.7.6 — حتی اگر ردیف players نبود، باقی‌مانده‌های جداول را پاک کن
    orphan_cleanup = pl is None

    try:
        from app.services import referral_service as refs
        await refs.clear_user_referrals(session, uid)
    except Exception:
        pass

    removed = 0
    for table in Base.metadata.sorted_tables:
        if table.name in {"admins", "admin_settings", "admin_audit"}:
            continue
        if table.name == "players":
            continue
        for col_name in RESET_OWNER_COLUMNS:
            col = table.c.get(col_name)
            if col is None:
                continue
            res = await session.execute(sa_delete(table).where(col == uid))
            removed += int(res.rowcount or 0)

    if pl is not None:
        await session.execute(sa_delete(Player).where(Player.tg_user_id == uid))
        removed += 1
    if commit:
        await session.commit()
    if removed <= 0 and orphan_cleanup:
        return False, (
            f"⚠ کاربر <code>{uid}</code> در جدول players نیست و ردیف وابسته‌ای هم پیدا نشد."
        )
    note = " (پاکسازی باقی‌مانده‌ها)" if orphan_cleanup else ""
    return True, (
        f"🗑️ کاربر <code>{uid}</code> کاملاً از دیتابیس حذف شد{note} "
        f"({removed} ردیف). حالا می‌تواند دوباره با لینک دعوت /start بزند."
    )


async def reset_sports_rankings(session, commit: bool = True) -> tuple[int, int]:
    """🆕 پچ: ریستِ کاملِ رنکینگِ بخشِ ورزش (تیم‌هایِ ورزشی و برندهایِ مسابقه‌ای).
    فقط آمارِ رقابتی (برد/باخت/تساوی/امتیاز/گل) صفر می‌شود؛ خودِ تیم/برند دست‌نخورده می‌ماند.
    """
    from sqlalchemy import update as sa_update

    from app.models.sports import RacingBrand, SportsTeam

    res_teams = await session.execute(
        sa_update(SportsTeam).values(
            wins=0, draws=0, losses=0, points=0, goals_for=0, goals_against=0
        )
    )
    res_brands = await session.execute(
        sa_update(RacingBrand).values(wins=0, losses=0, points=0)
    )
    if commit:
        await session.commit()
    return int(res_teams.rowcount or 0), int(res_brands.rowcount or 0)


async def reset_race_limit_today(session, commit: bool = True) -> int:
    """🆕 ریستِ محدودیتِ روزانه‌ی مسابقات (برای همه).
    سهمیه‌ی روزانه‌ی مسابقه (DAILY_MATCH_LIMIT) بر پایه‌ی تعدادِ SportsMatch‌هایِ امروز
    (به‌وقتِ تهران) محاسبه می‌شود؛ پس حذفِ رکوردهای امروز = صفرشدنِ سهمیه. خروجی: تعدادِ حذف‌شده.
    """
    from sqlalchemy import delete as sa_delete

    from app.models.sports import SportsMatch
    from app.services.sports_service import _tehran_day_bounds_utc

    start_utc, end_utc = _tehran_day_bounds_utc()
    res = await session.execute(
        sa_delete(SportsMatch).where(
            SportsMatch.played_at >= start_utc,
            SportsMatch.played_at < end_utc,
        )
    )
    if commit:
        await session.commit()
    return int(res.rowcount or 0)


# ---------------------------------------------------------------------------
# ورود/رمز
# ---------------------------------------------------------------------------
async def verify_login(session, uid: int, password: str) -> bool:
    admin = await get_admin(session, uid)
    if admin is None:
        return False
    if admin.password_hash is None:
        # رمزی ثبت نشده — ورودِ اولیه‌ی ادمینِ اصلی بدونِ رمز (باید بسازد)
        return False
    return A.verify_password(password, admin.password_hash)


async def set_password(session, uid: int, new_password: str, commit: bool = True) -> None:
    admin = await _by_uid(session, uid)
    if admin is None:
        return
    admin.password_hash = A.hash_password(new_password)
    admin.must_change_password = False
    if commit:
        await session.commit()


async def sync_password_from_env(session, uid: int, commit: bool = True) -> tuple[bool, str]:
    """🆕 فقط ادمینِ اصلی: رمزِ ورود را با مقدارِ ADMIN_PASSWORD در فایلِ .env هم‌زمان می‌کند.

    برایِ زمانی‌ست که ادمینِ اصلی رمزش را فراموش کرده یا می‌خواهد از طریقِ ویرایشِ
    فایلِ .env (و ری‌استارتِ ربات) رمزِ ورود را عوض کند.
    """
    if not settings.admin_password:
        return False, "⚠ مقدارِ ADMIN_PASSWORD در فایلِ .env خالی است؛ اول آن را پر کن و ربات را ری‌استارت کن."
    admin = await _by_uid(session, uid)
    if admin is None:
        return False, "⚠ ادمین پیدا نشد."
    admin.password_hash = A.hash_password(settings.admin_password)
    admin.must_change_password = False
    if commit:
        await session.commit()
    return True, "✅ رمزِ ورود با مقدارِ ADMIN_PASSWORD در فایلِ .env هم‌زمان شد."


# ---------------------------------------------------------------------------
# انتصاب/عزل/ویرایش
# ---------------------------------------------------------------------------
async def assign_admin(
    session,
    uid: int,
    perms: list[str],
    initial_password: str,
    assigned_by: int,
    label: str | None = None,
    commit: bool = True,
) -> AdminUser:
    """انتصابِ یک ادمینِ فرعی (یا فعال‌سازیِ دوباره‌یِ عزل‌شده).

    • رمزِ اولیه هش می‌شود و must_change_password=True تا در اولین ورود عوض شود.
    • دسترسی‌هایِ MAIN_ONLY حذف می‌شوند (قابلِ واگذاری نیستند).
    """
    clean = [p for p in A.normalize_perms(perms) if p not in A.MAIN_ONLY]
    admin = await _by_uid(session, uid)
    if admin is None:
        admin = AdminUser(tg_user_id=uid, role="admin")
        session.add(admin)
    if admin.role != "main":
        admin.role = "admin"
    admin.permissions = json.dumps(clean)
    admin.password_hash = A.hash_password(initial_password)
    admin.must_change_password = True
    admin.active = True
    admin.assigned_by = assigned_by
    if label:
        admin.label = label
    if commit:
        await session.commit()
    return admin


async def revoke_admin(session, uid: int, by: int, commit: bool = True) -> bool:
    """عزلِ کاملِ ادمین: active=False، دسترسی‌ها پاک، خروج از حالتِ ادمین.

    ادمینِ اصلی قابلِ عزل نیست.
    """
    admin = await _by_uid(session, uid)
    if admin is None or admin.role == "main":
        return False
    admin.active = False
    admin.permissions = json.dumps([])
    admin.password_hash = None
    admin.must_change_password = True
    await exit_admin_mode(uid)
    if commit:
        await session.commit()
    return True


async def update_permissions(session, uid: int, perms: list[str], commit: bool = True) -> bool:
    admin = await _by_uid(session, uid)
    if admin is None or admin.role == "main":
        return False
    admin.permissions = json.dumps([p for p in A.normalize_perms(perms) if p not in A.MAIN_ONLY])
    if commit:
        await session.commit()
    return True


# ---------------------------------------------------------------------------
# تنظیمات (key/value)
# ---------------------------------------------------------------------------
async def get_setting(session, key: str) -> str | None:
    row = await session.get(AdminSetting, key)
    return row.value if row else None


async def set_setting(session, key: str, value: str | None, commit: bool = True) -> None:
    row = await session.get(AdminSetting, key)
    if row is None:
        row = AdminSetting(key=key, value=value)
        session.add(row)
    else:
        row.value = value
    if commit:
        await session.commit()


# ---- کانالِ گزارش (تنها یک کانالِ مجاز) ----
async def get_report_channel_id(session) -> int | None:
    val = await get_setting(session, SETTING_REPORT_CHANNEL)
    if val is None:
        return None
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


async def get_report_channel_title(session) -> str | None:
    return await get_setting(session, SETTING_REPORT_CHANNEL_TITLE)


async def set_report_channel(session, chat_id: int, title: str | None = None, commit: bool = True) -> None:
    await set_setting(session, SETTING_REPORT_CHANNEL, str(chat_id), commit=False)
    await set_setting(session, SETTING_REPORT_CHANNEL_TITLE, title or "", commit=False)
    if commit:
        await session.commit()


async def clear_report_channel(session, commit: bool = True) -> None:
    await set_setting(session, SETTING_REPORT_CHANNEL, None, commit=False)
    await set_setting(session, SETTING_REPORT_CHANNEL_TITLE, None, commit=False)
    if commit:
        await session.commit()


# ---- کانالِ اخبارِ روزانه (تنها یک کانالِ مجاز) ----
async def get_news_channel_id(session) -> int | None:
    val = await get_setting(session, SETTING_NEWS_CHANNEL)
    if val is None:
        return None
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


async def get_news_channel_title(session) -> str | None:
    return await get_setting(session, SETTING_NEWS_CHANNEL_TITLE)


async def set_news_channel(session, chat_id: int, title: str | None = None, commit: bool = True) -> None:
    await set_setting(session, SETTING_NEWS_CHANNEL, str(chat_id), commit=False)
    await set_setting(session, SETTING_NEWS_CHANNEL_TITLE, title or "", commit=False)
    if commit:
        await session.commit()


async def clear_news_channel(session, commit: bool = True) -> None:
    await set_setting(session, SETTING_NEWS_CHANNEL, None, commit=False)
    await set_setting(session, SETTING_NEWS_CHANNEL_TITLE, None, commit=False)
    if commit:
        await session.commit()


# ---------------------------------------------------------------------------
# 🆕 مرحله ۲۱.۱ — ادمینِ فروش + دریافت/عدمِ دریافتِ پیامِ درخواستِ خرید (فقط ادمینِ اصلی تغییر می‌دهد)
# ---------------------------------------------------------------------------
async def get_sales_admin_id(session) -> int | None:
    val = await get_setting(session, SETTING_SALES_ADMIN_ID)
    if not val:
        return None
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


async def set_sales_admin_id(session, uid: int | None, commit: bool = True) -> None:
    """تعیین/حذفِ ادمینِ فروش (uid=None یعنی حذف)."""
    await set_setting(session, SETTING_SALES_ADMIN_ID, (str(uid) if uid else None), commit=commit)


async def main_notify_on_purchase(session) -> bool:
    """آیا ادمینِ اصلی پیامِ درخواستِ خریدِ جدید را دریافت می‌کند؟ پیش‌فرض: بله."""
    val = await get_setting(session, SETTING_MAIN_NOTIFY_PURCHASE)
    return val != "0"


async def set_main_notify_on_purchase(session, enabled: bool, commit: bool = True) -> None:
    await set_setting(session, SETTING_MAIN_NOTIFY_PURCHASE, ("1" if enabled else "0"), commit=commit)


# ---------------------------------------------------------------------------
# رزولوشنِ ورودیِ کانال (لینک/آیدی/فوروارد)
# ---------------------------------------------------------------------------
def parse_channel_id_from_text(text: str) -> int | None:
    """از متن، آیدیِ عددیِ کانال را درمی‌آورد (منطقِ خالص، قابلِ تست).

    پشتیبانی:
      • آیدیِ عددی مانندِ -1001234567890
      • لینکِ دعوتِ خصوصی t.me/c/1234567890/5 → -1001234567890
      • لینکِ دعوت t.me/+XXXX یا t.me/joinchat/... → None (باید فوروارد یا آیدی بدهد)
    """
    if not text:
        return None
    t = text.strip()
    # آیدیِ عددیِ مستقیم
    if t.lstrip("-").isdigit():
        try:
            return int(t)
        except ValueError:
            return None
    # لینکِ t.me/c/<internal>/<msg>
    if "t.me/c/" in t:
        try:
            after = t.split("t.me/c/", 1)[1]
            internal = after.split("/", 1)[0].split("?", 1)[0]
            internal = "".join(ch for ch in internal if ch.isdigit())
            if internal:
                return int("-100" + internal)
        except (IndexError, ValueError):
            return None
    return None


# ---------------------------------------------------------------------------
# لاگ
# ---------------------------------------------------------------------------
async def audit(session, admin_id: int, action: str, target_id: int | None = None,
                detail: str | None = None, commit: bool = True) -> None:
    session.add(AdminAudit(
        admin_id=admin_id, action=action, target_id=target_id, detail=detail,
    ))
    if commit:
        await session.commit()


async def recent_audit(session, limit: int = 20) -> list[AdminAudit]:
    rows = (await session.execute(
        select(AdminAudit).order_by(AdminAudit.created_at.desc()).limit(limit)
    )).scalars().all()
    return list(rows)


# ===========================================================================
# 🆕 مرحله ۳۰ — هدیه به یک کاربرِ خاص و هدیهِ لقب
# ===========================================================================
async def gift_one_player(
    session, uid: int, kind: str, amount: int, commit: bool = True
) -> tuple[bool, str]:
    """🎁 هدیهِ پول یا XP فقط به یک بازیکنِ مشخص.

    خروجی: (موفقیت، متنِ گزارش).
    """
    from app.data import leveling
    from app.models.player import Player

    amount = int(amount or 0)
    if amount <= 0 or kind not in ("cash", "xp"):
        return False, "❗ مقدار یا نوعِ هدیه نامعتبر است."
    pl = (await session.execute(select(Player).where(Player.tg_user_id == int(uid)))).scalar_one_or_none()
    if pl is None:
        return False, "⚠ کاربری با این یوزرآیدی در بازی ثبت نشده است."
    if kind == "cash":
        pl.cash = int(pl.cash or 0) + amount
        note = f"💰 <b>{amount:,}$</b>"
    else:
        leveling.add_xp(pl, amount)
        note = f"✨ <b>{amount:,} XP</b>"
    if commit:
        await session.commit()
    return True, (
        f"🎁 به کاربر <code>{uid}</code> ({pl.name}) مقدارِ {note} هدیه داده شد."
    )


def find_title(raw: str):
    """🎖️ پیداکردنِ یک لقب با کلیدِ انگلیسی یا نامِ فارسی."""
    from app.data import titles as T

    raw = (raw or "").strip()
    if not raw:
        return None
    t = T.get_title(raw)
    if t:
        return t
    try:
        t = T.get_title_by_name(raw)
        if t:
            return t
    except Exception:
        pass
    low = raw.lower()
    for item in getattr(T, "TITLES", []):
        if low in str(item.get("name", "")).lower() or low in str(item.get("key", "")).lower():
            return item
    return None


def title_suggestions(limit: int = 12) -> str:
    """چند نمونهٔ لقب برایِ راهنماییِ ادمین."""
    from app.data import titles as T

    rows = getattr(T, "TITLES", [])[:limit]
    return "\n".join(f"• <code>{r['key']}</code> — {r['name']}" for r in rows)


# ---------------------------------------------------------------------------
# 🆕 v1.7.2 — روشن/خاموش گزینه‌های رنکینگ + تنظیمات بکاپ دیتابیس
# ---------------------------------------------------------------------------
RANK_VIS_PREFIX = "rank_vis_"  # rank_vis_power=0/1
BACKUP_CHANNEL_KEY = "backup_channel_id"
BACKUP_CHANNEL_TITLE_KEY = "backup_channel_title"
BACKUP_INTERVAL_HOURS_KEY = "backup_interval_hours"  # 0 = خاموش
BACKUP_LAST_TS_KEY = "backup_last_ts"  # unix timestamp string


async def get_rank_visibility(session) -> dict:
    """map code -> enabled (default True)."""
    from app.services import ranking as R
    out = {}
    for code, _label, _unit in R.CATEGORIES:
        raw = await get_setting(session, f"{RANK_VIS_PREFIX}{code}")
        out[code] = (raw is None) or (str(raw) != "0")
    for code in ("global", "league", "war_ranked", "power_formula"):
        raw = await get_setting(session, f"{RANK_VIS_PREFIX}{code}")
        out[code] = (raw is None) or (str(raw) != "0")
    return out


async def set_rank_visibility(session, code: str, enabled: bool, commit: bool = True) -> None:
    await set_setting(session, f"{RANK_VIS_PREFIX}{code}", "1" if enabled else "0", commit=commit)


async def enabled_rank_categories(session):
    from app.services import ranking as R
    vis = await get_rank_visibility(session)
    return [c for c in R.CATEGORIES if vis.get(c[0], True)]


async def get_backup_settings(session) -> dict:
    ch = await get_setting(session, BACKUP_CHANNEL_KEY)
    title = await get_setting(session, BACKUP_CHANNEL_TITLE_KEY)
    hours_raw = await get_setting(session, BACKUP_INTERVAL_HOURS_KEY)
    last_raw = await get_setting(session, BACKUP_LAST_TS_KEY)
    try:
        hours = int(hours_raw or 0)
    except Exception:
        hours = 0
    try:
        last_ts = float(last_raw or 0)
    except Exception:
        last_ts = 0.0
    ch_id = None
    if ch not in (None, "", "None"):
        try:
            ch_id = int(ch)
        except Exception:
            ch_id = None
    return {
        "channel_id": ch_id,
        "channel_title": title or "",
        "interval_hours": max(0, hours),
        "last_ts": last_ts,
    }


async def set_backup_channel(session, chat_id: int, title: str | None = None, commit: bool = True) -> None:
    await set_setting(session, BACKUP_CHANNEL_KEY, str(chat_id), commit=False)
    await set_setting(session, BACKUP_CHANNEL_TITLE_KEY, title or "", commit=False)
    if commit:
        await session.commit()


async def clear_backup_channel(session, commit: bool = True) -> None:
    await set_setting(session, BACKUP_CHANNEL_KEY, None, commit=False)
    await set_setting(session, BACKUP_CHANNEL_TITLE_KEY, None, commit=False)
    if commit:
        await session.commit()


async def set_backup_interval_hours(session, hours: int, commit: bool = True) -> None:
    hours = max(0, int(hours))
    await set_setting(session, BACKUP_INTERVAL_HOURS_KEY, str(hours), commit=commit)


async def mark_backup_done(session, ts: float | None = None, commit: bool = True) -> None:
    import time
    await set_setting(session, BACKUP_LAST_TS_KEY, str(float(ts if ts is not None else time.time())), commit=commit)
