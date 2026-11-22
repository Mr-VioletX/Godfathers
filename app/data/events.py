# -*- coding: utf-8 -*-
"""مرحله ۲۷ — رویدادهایِ بونس (XP Bonus / Money Bonus).

این فایل منطقِ خالص است (بدونِ وابستگی به دیتابیس/aiogram) تا کاملاً قابلِ تست باشد:
  • نگه‌داشتِ وضعیتِ رویدادهایِ فعال در یک کَشِ سراسری (`BONUS`)
  • اعتبارسنجیِ ضریب و مدتِ رویداد
  • اعمالِ ضریب روی XP و پول (`apply_xp` / `apply_money`)

همه‌ی بخش‌هایِ بازی برایِ محاسبه‌ی XP و درآمد باید از همین توابع استفاده کنند تا
ادمین بتواند با یک سوییچ، اونتِ دلخواهش را روی کلِ بازی فعال/غیرفعال کند.
"""
from __future__ import annotations

from datetime import datetime, timedelta

# ---------------------------------------------------------------------------
# محدوده‌هایِ مجاز
# ---------------------------------------------------------------------------
MIN_MULT = 1.0          # ضریبِ ۱ = بدونِ تغییر
MAX_MULT = 10.0         # سقفِ ضریب (جلوگیری از خرابیِ اقتصادِ بازی)
MAX_HOURS = 24 * 30     # حداکثر مدتِ یک رویداد: ۳۰ روز

KIND_XP = "xp"
KIND_MONEY = "money"
KINDS = (KIND_XP, KIND_MONEY)

KIND_LABEL = {
    KIND_XP: "✨ بونسِ تجربه (XP)",
    KIND_MONEY: "💰 بونسِ پول",
}


def kind_label(kind: str) -> str:
    return KIND_LABEL.get(kind, kind)


# ---------------------------------------------------------------------------
# اعتبارسنجیِ ورودی‌هایِ ادمین
# ---------------------------------------------------------------------------
def parse_multiplier(text: str | None) -> tuple[bool, float | str]:
    """ضریبِ ورودیِ ادمین را می‌خواند. مثال‌هایِ مجاز: 2 / 1.5 / x3 / ۲"""
    raw = (text or "").strip().lower().replace("x", "").replace("*", "").replace("،", ".")
    # تبدیلِ اعدادِ فارسی/عربی به لاتین
    trans = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
    raw = raw.translate(trans).replace("٫", ".")
    try:
        val = float(raw)
    except (TypeError, ValueError):
        return False, "⚠ ضریب باید عدد باشد (مثلاً 2 یا 1.5)."
    if val < MIN_MULT:
        return False, f"⚠ ضریب نمی‌تواند کمتر از {MIN_MULT:g} باشد."
    if val > MAX_MULT:
        return False, f"⚠ ضریب نمی‌تواند بیشتر از {MAX_MULT:g} باشد."
    return True, round(val, 2)


def parse_hours(text: str | None) -> tuple[bool, int | str]:
    """مدتِ رویداد به ساعت؛ «0» یا «بی‌نهایت» یعنی بدونِ انقضا."""
    raw = (text or "").strip().lower()
    trans = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
    raw = raw.translate(trans)
    if raw in {"0", "بی‌نهایت", "بی نهایت", "نامحدود", "همیشه"}:
        return True, 0
    if not raw.isdigit():
        return False, "⚠ مدت باید عددِ ساعت باشد (مثلاً 12) یا «نامحدود»."
    val = int(raw)
    if val > MAX_HOURS:
        return False, f"⚠ حداکثر مدتِ مجاز {MAX_HOURS} ساعت است."
    return True, val


def until_from_hours(hours: int, now: datetime | None = None) -> datetime | None:
    if not hours:
        return None
    return (now or datetime.utcnow()) + timedelta(hours=int(hours))


# ---------------------------------------------------------------------------
# وضعیتِ رویدادها (کَشِ سراسری)
# ---------------------------------------------------------------------------
class BonusState:
    """وضعیتِ رویدادهایِ بونس. مقدارهایِ پایدار در جدولِ admin_settings ذخیره می‌شوند
    و این کلاس فقط کَشِ درون‌حافظه است تا محاسباتِ XP/پول سریع باشند."""

    def __init__(self) -> None:
        self.xp_active: bool = False
        self.xp_mult: float = 1.0
        self.xp_until: datetime | None = None
        self.money_active: bool = False
        self.money_mult: float = 1.0
        self.money_until: datetime | None = None
        self.title: str = ""

    # --- خواندنِ ضریبِ مؤثر ---
    def _mult(self, active: bool, mult: float, until: datetime | None, now: datetime | None) -> float:
        if not active:
            return 1.0
        if until is not None and (now or datetime.utcnow()) >= until:
            return 1.0
        try:
            val = float(mult or 1.0)
        except (TypeError, ValueError):
            return 1.0
        return max(MIN_MULT, min(MAX_MULT, val))

    def expire_if_needed(self, now: datetime | None = None) -> list[str]:
        """اگر مهلت گذشته باشد فلگ active را در حافظه خاموش می‌کند."""
        now = now or datetime.utcnow()
        expired: list[str] = []
        if self.xp_active and self.xp_until is not None and now >= self.xp_until:
            self.xp_active = False
            expired.append(KIND_XP)
        if self.money_active and self.money_until is not None and now >= self.money_until:
            self.money_active = False
            expired.append(KIND_MONEY)
        return expired

    def xp_multiplier(self, now: datetime | None = None) -> float:
        self.expire_if_needed(now)
        return self._mult(self.xp_active, self.xp_mult, self.xp_until, now)

    def money_multiplier(self, now: datetime | None = None) -> float:
        self.expire_if_needed(now)
        return self._mult(self.money_active, self.money_mult, self.money_until, now)

    def any_active(self, now: datetime | None = None) -> bool:
        return self.xp_multiplier(now) > 1.0 or self.money_multiplier(now) > 1.0


# کَشِ سراسری (توسطِ app/services/event_service.py پر و به‌روز می‌شود)
BONUS = BonusState()


def apply_xp(amount: int, now: datetime | None = None) -> int:
    """XP را با ضریبِ رویدادِ فعال ضرب می‌کند (گِرد به پایین، هرگز کمتر از مقدارِ اصلی)."""
    amount = int(amount or 0)
    if amount <= 0:
        return amount
    mult = BONUS.xp_multiplier(now)
    if mult <= 1.0:
        return amount
    return max(amount, int(amount * mult))


def apply_money(amount: int, now: datetime | None = None) -> int:
    """درآمد را با ضریبِ رویدادِ فعال ضرب می‌کند. فقط روی مقدارهایِ مثبت اثر دارد
    (جریمه/هزینه هرگز بزرگ‌تر نمی‌شود)."""
    amount = int(amount or 0)
    if amount <= 0:
        return amount
    mult = BONUS.money_multiplier(now)
    if mult <= 1.0:
        return amount
    return max(amount, int(amount * mult))


# ---------------------------------------------------------------------------
# متن‌ها
# ---------------------------------------------------------------------------
def _fmt_until(until: datetime | None) -> str:
    if until is None:
        return "نامحدود (تا خاموش‌کردنِ دستی)"
    remain = until - datetime.utcnow()
    hours = int(remain.total_seconds() // 3600)
    if hours <= 0:
        return "منقضی شده"
    if hours < 24:
        return f"{hours} ساعتِ دیگر"
    return f"{hours // 24} روز و {hours % 24} ساعتِ دیگر"


def status_text(state: BonusState | None = None) -> str:
    """متنِ وضعیتِ رویدادها برایِ پنلِ ادمین."""
    st = state or BONUS
    lines = ["🎉 <b>رویدادهایِ بونس</b>", ""]
    if st.title:
        lines += [f"🏷 نامِ رویداد: <b>{st.title}</b>", ""]
    for kind, active, mult, until in (
        (KIND_XP, st.xp_active, st.xp_mult, st.xp_until),
        (KIND_MONEY, st.money_active, st.money_mult, st.money_until),
    ):
        mark = "🟢 فعال" if active else "⚪ خاموش"
        lines.append(f"{kind_label(kind)} — {mark}")
        lines.append(f"   ضریب: <b>×{float(mult or 1):g}</b> | مدت: {_fmt_until(until) if active else '—'}")
    lines += [
        "",
        "ℹ️ ضریبِ XP روی همه‌ی XPهایِ بازی (دزدی، ورزش، ارتقا، خرید و …) اعمال می‌شود.",
        "ℹ️ ضریبِ پول فقط روی <b>درآمدها</b> اعمال می‌شود، نه روی هزینه‌ها و جریمه‌ها.",
    ]
    return "\n".join(lines)


def player_banner(now: datetime | None = None) -> str:
    """نوارِ کوتاهِ اعلانِ رویداد برایِ نمایش به بازیکن (اگر رویدادی فعال باشد)."""
    parts: list[str] = []
    xp = BONUS.xp_multiplier(now)
    money = BONUS.money_multiplier(now)
    if xp > 1.0:
        parts.append(f"✨ XP ×{xp:g}")
    if money > 1.0:
        parts.append(f"💰 درآمد ×{money:g}")
    if not parts:
        return ""
    head = f"🎉 <b>{BONUS.title}</b> — " if BONUS.title else "🎉 <b>رویدادِ ویژه</b> — "
    return head + " | ".join(parts)
