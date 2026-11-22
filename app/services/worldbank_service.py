# -*- coding: utf-8 -*-
"""سرویسِ بانکِ مافیایی — ثروتِ خالص، سپرده، وام و رتبه‌بندیِ ثروتمندان.

ثروتِ خالص = نقدینگی + درآمدِ روزانه + ارزشِ شهرها + ارزشِ کشورها.
منطقِ خالص در app/data/worldbank.py است.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from app.data import worldbank as WB
from app.models.player import Player
from app.services import mafia_city_service as CS  # 🆕 بچ ۴ — شهرسازِ جدید
from app.models.worldbank import BankAccount
from app.models.admin import GameNumberSetting
from app.services import war_service

# ارزشِ پایه‌ی کشور بر اساسِ رده (برای محاسبه‌ی ثروتِ خالص)
COUNTRY_TIER_VALUE = {
    "small": 2_000_000,
    "medium": 6_000_000,
    "large": 15_000_000,
    "empire": 40_000_000,
}


async def get_account(session, uid: int) -> BankAccount:
    """حساب بانک؛ اگر ستون گاوصندوق هنوز migrate نشده باشد هم نمی‌ترکد."""
    try:
        acc = await session.get(BankAccount, int(uid))
    except Exception:
        # ستون جدید روی DB قدیمی — fallback خام
        try:
            await session.rollback()
        except Exception:
            pass
        from sqlalchemy import text as _text
        try:
            row = (await session.execute(
                _text("SELECT owner_id, deposit, deposit_at, loan_principal, loan_at FROM bank_accounts WHERE owner_id = :oid"),
                {"oid": int(uid)},
            )).mappings().first()
        except Exception:
            row = None
        if row is None:
            acc = BankAccount(owner_id=int(uid), deposit=0, loan_principal=0, safebox_level=0, safebox_balance=0)
            try:
                session.add(acc)
                await session.flush()
            except Exception:
                try:
                    await session.rollback()
                except Exception:
                    pass
            return acc
        acc = BankAccount(
            owner_id=int(row["owner_id"]),
            deposit=int(row["deposit"] or 0),
            deposit_at=row.get("deposit_at"),
            loan_principal=int(row["loan_principal"] or 0),
            loan_at=row.get("loan_at"),
            safebox_level=0,
            safebox_balance=0,
        )
        # attach without insert
        return acc
    if acc is None:
        acc = BankAccount(owner_id=int(uid), deposit=0, loan_principal=0, safebox_level=0, safebox_balance=0)
        session.add(acc)
        await session.flush()
    # defaults for partial rows
    if getattr(acc, "safebox_level", None) is None:
        try:
            acc.safebox_level = 0
        except Exception:
            pass
    if getattr(acc, "safebox_balance", None) is None:
        try:
            acc.safebox_balance = 0
        except Exception:
            pass
    return acc


async def city_value(session, uid: int) -> int:
    """ارزشِ شهر = قیمتِ خرید + ساختمان‌ها + جمعیت. 🆕 بچ ۴: شهرسازِ جدید."""
    try:
        return int(await CS.city_value(session, uid))
    except Exception:
        return 0


async def country_value(session, uid: int) -> int:
    """🆕 بچ ۴ — کشور حذف شد؛ همیشه ۰."""
    return 0


async def compute_net_worth(session, uid: int) -> dict:
    """اجزایِ ثروتِ خالص را برمی‌گرداند."""
    player = (await session.execute(select(Player).where(Player.tg_user_id == uid))).scalar_one_or_none()
    cash = int(player.cash or 0) if player else 0
    # بچ ۵: سپرده‌ی بانک بخشی از ثروتِ واقعی است.
    acc = await get_account(session, uid)
    deposit_value = int(acc.deposit or 0)
    try:
        income = await war_service.daily_income(session, uid)
    except Exception:
        income = 0
    cval = await city_value(session, uid)
    ctval = await country_value(session, uid)
    net = WB.net_worth(cash + deposit_value, income, cval, ctval)
    return {
        "cash": cash,
        "deposit": deposit_value,
        "liquid_and_deposit": cash + deposit_value,
        "daily_income": income,
        "city_value": cval,
        "country_value": ctval,
        "net_worth": net,
    }


async def net_worth_value(session, uid: int) -> int:
    return (await compute_net_worth(session, uid))["net_worth"]


# --------------------------- سپرده ---------------------------
async def deposit(session, uid: int, amount: int) -> tuple[bool, str]:
    amount = int(amount)
    if amount <= 0:
        return False, "مبلغِ معتبر بفرست."
    player = (await session.execute(select(Player).where(Player.tg_user_id == uid))).scalar_one_or_none()
    if player is None or int(player.cash or 0) < amount:
        return False, "💸 پولت کافی نیست."
    acc = await get_account(session, uid)
    # اول سودِ تاکنون را تسویه می‌کنیم
    await _settle_deposit_interest(session, uid, acc)
    player.cash = int(player.cash or 0) - amount
    acc.deposit = int(acc.deposit) + amount
    acc.deposit_at = datetime.utcnow()
    await session.flush()
    return True, f"🏦 {amount:,}$ به سپرده اضافه شد. موجودیِ سپرده: {acc.deposit:,}$"


async def _settle_deposit_interest(session, uid: int, acc: BankAccount) -> int:
    """سودِ انباشته‌ی سپرده را به اصلِ سپرده اضافه می‌کند."""
    if acc.deposit <= 0 or acc.deposit_at is None:
        acc.deposit_at = datetime.utcnow()
        return 0
    days = (datetime.utcnow() - acc.deposit_at).days
    if days <= 0:
        return 0
    net = await net_worth_value(session, uid)
    rate = WB.deposit_rate_for(net)
    # v1.7.8.3 — بونس سود بانکی اشتراک روی نرخ پایه
    try:
        from app.services import subscription_service as _subs
        _bb = int(await _subs.bank_bonus_pct(session, uid) or 0)
        if _bb > 0:
            rate = float(rate) * (1.0 + _bb / 100.0)
    except Exception:
        pass
    interest = WB.deposit_interest(int(acc.deposit), days, rate)
    if interest > 0:
        acc.deposit = int(acc.deposit) + interest
        acc.deposit_at = datetime.utcnow()
    return interest


async def withdraw(session, uid: int, amount: int) -> tuple[bool, str]:
    amount = int(amount)
    acc = await get_account(session, uid)
    await _settle_deposit_interest(session, uid, acc)
    if amount <= 0 or amount > int(acc.deposit):
        return False, f"موجودیِ سپرده‌ات {acc.deposit:,}$ است."
    player = (await session.execute(select(Player).where(Player.tg_user_id == uid))).scalar_one_or_none()
    acc.deposit = int(acc.deposit) - amount
    player.cash = int(player.cash or 0) + amount
    await session.flush()
    return True, f"🏧 {amount:,}$ از سپرده برداشت شد."


# --------------------------- وام ---------------------------
async def take_loan(session, uid: int, amount: int) -> tuple[bool, str]:
    amount = int(amount)
    if amount <= 0:
        return False, "مبلغِ معتبر بفرست."
    acc = await get_account(session, uid)
    if int(acc.loan_principal) > 0:
        return False, "اول باید وامِ قبلی را تسویه کنی."
    net = await net_worth_value(session, uid)
    cap = WB.max_loan(net, int(acc.loan_principal))
    if amount > cap:
        return False, f"🚫 سقفِ وامِ تو {cap:,}$ است (۵۰٪ِ ثروتِ خالص)."
    player = (await session.execute(select(Player).where(Player.tg_user_id == uid))).scalar_one_or_none()
    player.cash = int(player.cash or 0) + amount
    acc.loan_principal = amount
    acc.loan_at = datetime.utcnow()
    await session.flush()
    return True, (
        f"🏦 وامِ {amount:,}$ دریافت شد.\n"
        f"⚠️ بهره‌ی روزانه {int(WB.LOAN_DAILY_INTEREST*100)}٪ — زودتر تسویه کنی ارزان‌تر است."
    )


def loan_balance(acc: BankAccount) -> int:
    if int(acc.loan_principal) <= 0 or acc.loan_at is None:
        return 0
    days = (datetime.utcnow() - acc.loan_at).days
    return WB.loan_due(int(acc.loan_principal), days)


async def repay_loan(session, uid: int) -> tuple[bool, str]:
    acc = await get_account(session, uid)
    due = loan_balance(acc)
    if due <= 0:
        return False, "وامِ فعالی نداری."
    player = (await session.execute(select(Player).where(Player.tg_user_id == uid))).scalar_one_or_none()
    if player is None or int(player.cash or 0) < due:
        return False, f"💸 برای تسویه به {due:,}$ نیاز داری."
    player.cash = int(player.cash or 0) - due
    acc.loan_principal = 0
    acc.loan_at = None
    await session.flush()
    return True, f"✅ وامِ {due:,}$ تسویه شد."


# --------------------------- گاوصندوق v1.7.7.6 ---------------------------
def _sb_level(acc) -> int:
    try:
        return max(0, int(getattr(acc, "safebox_level", 0) or 0))
    except Exception:
        return 0


def _sb_balance(acc) -> int:
    try:
        return max(0, int(getattr(acc, "safebox_balance", 0) or 0))
    except Exception:
        return 0


async def safebox_info(session, uid: int) -> dict:
    await refresh_bank_settings(session)
    acc = await get_account(session, uid)
    lv = _sb_level(acc)
    bal = _sb_balance(acc)
    cap = WB.safebox_capacity(lv)
    bal = min(bal, int(acc.deposit or 0), cap)
    nxt_cost = WB.safebox_cost(lv)
    nxt_cap = WB.safebox_capacity(lv + 1) if lv < WB.SAFEBOX_MAX_LEVEL else cap
    return {
        "level": lv,
        "balance": bal,
        "capacity": cap,
        "next_cost": nxt_cost,
        "next_capacity": nxt_cap,
        "max_level": WB.SAFEBOX_MAX_LEVEL,
        "deposit": int(acc.deposit or 0),
        "lootable_deposit": WB.lootable_bank_deposit(int(acc.deposit or 0), bal),
        "safe_deposit_pct": WB.get_war_safe_pct(),
    }


async def upgrade_safebox(session, uid: int):
    await refresh_bank_settings(session)
    acc = await get_account(session, uid)
    lv = _sb_level(acc)
    if lv >= WB.SAFEBOX_MAX_LEVEL:
        return False, f"گاوصندوق در سقف سطح ({WB.SAFEBOX_MAX_LEVEL}) است."
    cost = WB.safebox_cost(lv)
    player = (await session.execute(select(Player).where(Player.tg_user_id == uid))).scalar_one_or_none()
    if player is None or int(player.cash or 0) < cost:
        return False, f"💸 برای ارتقا به {cost:,}$ نیاز داری."
    player.cash = int(player.cash or 0) - cost
    acc.safebox_level = lv + 1
    if getattr(acc, "safebox_balance", None) is None:
        acc.safebox_balance = 0
    await session.flush()
    info = await safebox_info(session, uid)
    msg = (
        f"🔐 گاوصندوق به سطح <b>{info['level']}</b> ارتقا یافت.\n"
        f"💰 هزینه: {cost:,}$\n"
        f"📦 ظرفیت: <b>{info['capacity']:,}$</b>"
    )
    return True, msg


async def move_to_safebox(session, uid: int, amount: int):
    amount = int(amount)
    if amount <= 0:
        return False, "مبلغ معتبر بفرست."
    acc = await get_account(session, uid)
    await _settle_deposit_interest(session, uid, acc)
    lv = _sb_level(acc)
    if lv <= 0:
        return False, "اول گاوصندوق را بخر/ارتقا بده (سطح ۱)."
    cap = WB.safebox_capacity(lv)
    bal = _sb_balance(acc)
    room = max(0, cap - bal)
    dep = int(acc.deposit or 0)
    available = max(0, dep - bal)
    take = min(amount, room, available)
    if take <= 0:
        return False, f"جا نیست یا سپرده آزاد نداری. ظرفیت خالی: {room:,}$"
    acc.safebox_balance = bal + take
    await session.flush()
    msg = f"🔐 {take:,}$ وارد گاوصندوق شد. موجودی امن: {int(acc.safebox_balance):,}$ / {cap:,}$"
    if take < amount:
        # v1.7.8.19 — کاربر بیشتر از حدِ مجاز نوشته بود؛ شفاف اعلام کن تا اشتباه پیش نیاید.
        reasons = []
        if amount > available:
            reasons.append(f"سپرده‌ی آزادِ بانک فقط {available:,}$ بود")
        if amount > room:
            reasons.append(f"ظرفیتِ خالیِ گاوصندوق فقط {room:,}$ بود")
        msg = (
            f"⚠️ مبلغی که نوشتی ({amount:,}$) بیشتر از حدِ مجاز بود — "
            + " و ".join(reasons)
            + f"؛ برای همین فقط {take:,}$ منتقل شد.\n" + msg
        )
    return True, msg


async def move_from_safebox(session, uid: int, amount: int):
    amount = int(amount)
    if amount <= 0:
        return False, "مبلغ معتبر بفرست."
    acc = await get_account(session, uid)
    bal = _sb_balance(acc)
    take = min(amount, bal)
    if take <= 0:
        return False, "گاوصندوق خالی است."
    acc.safebox_balance = bal - take
    await session.flush()
    msg = f"📤 {take:,}$ از گاوصندوق به سپرده عادی برگشت. باقی امن: {int(acc.safebox_balance):,}$"
    if take < amount:
        # v1.7.8.19 — اعلامِ شفاف وقتی مبلغِ واردشده بیشتر از موجودیِ گاوصندوق است.
        msg = (
            f"⚠️ مبلغی که نوشتی ({amount:,}$) بیشتر از موجودیِ گاوصندوق ({bal:,}$) بود؛ "
            f"برای همین فقط {take:,}$ برگشت.\n" + msg
        )
    return True, msg


async def lootable_wealth_of(session, uid: int) -> dict:
    """ثروت قابل‌غارت = نقد + ۵۰٪ سپرده غیرگاوصندوق."""
    await refresh_bank_settings(session)
    player = (await session.execute(select(Player).where(Player.tg_user_id == uid))).scalar_one_or_none()
    cash = int(player.cash or 0) if player else 0
    acc = await get_account(session, uid)
    dep = int(acc.deposit or 0)
    sb = min(_sb_balance(acc), dep)
    lootable_dep = WB.lootable_bank_deposit(dep, sb)
    total = WB.lootable_wealth(cash, dep, sb)
    return {
        "cash": cash,
        "deposit": dep,
        "safebox": sb,
        "lootable_deposit": lootable_dep,
        "lootable_total": total,
        "protected_deposit": max(0, dep - lootable_dep),
    }



# ---------------------------------------------------------------------------
# v1.7.8.2 — تنطیماتِ بانک از ادمین‌مود
# ---------------------------------------------------------------------------
BANK_SETTING_ALLOWED = frozenset(WB.BANK_SETTING_META.keys())


async def _bank_num(session, key: str, default) -> float:
    """یک عدد از GameNumberSetting بخوان؛ اگر نبود پیش‌فرض را برگردان."""
    try:
        row = await session.get(GameNumberSetting, key)
        if row is not None and row.value not in (None, ""):
            return float(str(row.value).strip())
    except Exception:
        pass
    return float(default)


async def refresh_bank_settings(session) -> dict:
    """اعدادِ بانک را از DB بخوان و کشِ runtime را به‌روز کن.

    در هر نقطهٔ مصرف صدا می‌شود، چون ربات در چند پروسه اجرا می‌شود
    (bot.py ، cron_ticks.py ، passenger_wsgi.py) و کشِ یک پروسه برای بقیه کافی نیست.
    خواندنِ ردیف با کلیدِ اولیه ارزان است و در هر session کش می‌شود.
    """
    safe_pct = await _bank_num(session, WB.BANK_SAFE_PCT_KEY, WB.DEFAULT_WAR_SAFE_PCT)
    cost_l1 = await _bank_num(session, WB.SAFEBOX_COST_L1_KEY, WB.DEFAULT_SAFEBOX_COST_L1)
    cost_l100 = await _bank_num(session, WB.SAFEBOX_COST_L100_KEY, WB.DEFAULT_SAFEBOX_COST_L100)
    cap_l1 = await _bank_num(session, WB.SAFEBOX_CAP_L1_KEY, WB.DEFAULT_SAFEBOX_CAP_L1)
    cap_l100 = await _bank_num(session, WB.SAFEBOX_CAP_L100_KEY, WB.DEFAULT_SAFEBOX_CAP_L100)
    WB.set_runtime_bank(
        safe_pct=safe_pct,
        cost_l1=cost_l1,
        cost_l100=cost_l100,
        cap_l1=cap_l1,
        cap_l100=cap_l100,
    )
    return WB.bank_snapshot()


async def save_bank_setting(session, key: str, value, admin_id: int | None = None) -> dict:
    """یک عددِ بانک را بنویس و کش را فوری رفرش کن."""
    if key not in BANK_SETTING_ALLOWED:
        raise ValueError("invalid bank setting key")
    val = float(value)
    if key == WB.BANK_SAFE_PCT_KEY:
        val = float(max(0, min(100, int(round(val)))))
    else:
        val = float(max(1, int(round(val))))
    stored = str(int(round(val)))
    row = await session.get(GameNumberSetting, key)
    if row is None:
        session.add(GameNumberSetting(key=key, value=stored, updated_by=admin_id))
    else:
        row.value = stored
        row.updated_by = admin_id
    await session.commit()
    return await refresh_bank_settings(session)


async def reset_bank_settings(session, admin_id: int | None = None) -> dict:
    """همهٔ اعدادِ بانک را به پیش‌فرضِ کد برگردان."""
    for key in BANK_SETTING_ALLOWED:
        row = await session.get(GameNumberSetting, key)
        if row is not None:
            await session.delete(row)
    await session.commit()
    return await refresh_bank_settings(session)
