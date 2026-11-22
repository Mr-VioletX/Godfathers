# -*- coding: utf-8 -*-
"""🆕 بچ ۴ — کیبوردهای شهرسازِ جدید (تک‌شهری).

جایگزینِ کیبوردهای قدیمیِ شهر/کشور. هر بازیکن یک شهر دارد، پس
دیگر نیازی به city_id در callback نیست. همه‌ی callbackها owner_id دارند.
"""
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.utils.ui import add_pager, paginate, with_owner
from app.data import mafia_city as C
from app.data import city_mayor as MY


def _cb(data: str, owner_id=None) -> str:
    return with_owner(data, owner_id) if owner_id is not None else data


def locked_menu(owner_id=None) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="↩️ بازگشت به منو", callback_data=_cb("menu:main", owner_id))
    b.adjust(2)
    return b.as_markup()


def buy_menu(owner_id=None) -> InlineKeyboardMarkup:
    """منوی خریدِ شهر (وقتی بازیکن هنوز شهری ندارد)."""
    b = InlineKeyboardBuilder()
    b.button(text=f"🏙️ خریدِ شهر — {C.CITY_COST:,}$", callback_data=_cb("city:buy", owner_id))
    b.button(text="↩️ بازگشت به منو", callback_data=_cb("menu:main", owner_id))
    b.adjust(2)
    return b.as_markup()


def city_menu(owner_id=None, warehouse_level: int = 1) -> InlineKeyboardMarkup:
    """داشبورد خلوت شهر؛ هر خانواده قابلیت در زیرمنوی خودش است."""
    b = InlineKeyboardBuilder()
    b.button(text="🏙️ وضعیت، زیرساخت و صنعت", callback_data=_cb("city:info:services", owner_id))
    b.button(text="👥 شهروندان و نیازها", callback_data=_cb("city:info:needs", owner_id))
    b.button(text="🏗️ کنترل شهر", callback_data=_cb("city:control", owner_id))
    b.button(text="🛒 بازار و منابع", callback_data=_cb("city:resources", owner_id))
    b.button(text="🏦 اقتصاد شهر", callback_data=_cb("city:economy", owner_id))
    b.button(text="🏛️ شهرداری و پیامِ مردم", callback_data=_cb("city:mayor", owner_id))

    b.button(text="✏️ ویرایش نام شهر", callback_data=_cb("city:rename", owner_id))
    b.button(text="❔ راهنمای شهر", callback_data=_cb("city:help", owner_id))
    b.button(text="🏗️ در حال ساخت‌وساز", callback_data=_cb("city:wip", owner_id))
    if int(warehouse_level) >= C.WAREHOUSE_MAX_LEVEL:
        b.button(text="📦 انبار شهر (مکس)", callback_data=_cb("city:maxed", owner_id))
    else:
        cost = C.warehouse_upgrade_cost(int(warehouse_level))
        b.button(text=f"📦 انبار شهر — ارتقا {cost:,}$", callback_data=_cb("city:wh", owner_id))
    b.button(text="↩️ بازگشت به منو", callback_data=_cb("menu:main", owner_id))
    b.adjust(2, 2, 2, 2, 1, 1, 1)
    return b.as_markup()


def city_control_menu(owner_id=None) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="🏘️ خانه‌سازی و تبدیل", callback_data=_cb("city:cat:housing:0", owner_id))
    b.button(text="🛠️ زیرساخت‌ها", callback_data=_cb("city:cat:infra:0", owner_id))
    b.button(text="🏭 صنعت", callback_data=_cb("city:cat:industry:0", owner_id))
    b.button(text="🎪 رفاه و تجارت", callback_data=_cb("city:cat:welfare:0", owner_id))
    b.button(text="↩️ بازگشت به شهر", callback_data=_cb("city:hub", owner_id))
    b.adjust(2, 2, 1)
    return b.as_markup()


def city_economy_menu(owner_id=None) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="💰 جمع‌آوری درآمد", callback_data=_cb("city:collect", owner_id))
    b.button(text="🧾 بانک مرکزی و مالیات", callback_data=_cb("city:tax", owner_id))
    b.button(text="🏭 توان تولید و مصرف", callback_data=_cb("city:info:production", owner_id))
    b.button(text="↩️ بازگشت به شهر", callback_data=_cb("city:hub", owner_id))
    b.adjust(2, 2)
    return b.as_markup()

def category_menu(ckey: str, counts: dict, population: int, materials: int,
                  page: int = 0, owner_id=None, pending: dict | None = None) -> InlineKeyboardMarkup:
    """ساخت زمان‌دار است؛ مسکونی همه در یک صفحه با دکمه‌های دو ستونه."""
    cat = C.CATEGORIES.get(ckey, {})
    order = list(cat.get("order", ()))
    pending = pending or {}
    b = InlineKeyboardBuilder()
    is_housing = ckey == "housing"
    if is_housing:
        rows = order  # بدون صفحه‌بندی
        total_pages = 1
    else:
        rows, page, total_pages = paginate(order, page, per=8)
    for btype in rows:
        info = C.get_building(btype) or {}
        have = int(counts.get(btype, 0))
        wait = int(pending.get(btype, 0))
        mark = f" ⏳{wait}" if wait else ""
        b.button(
            text=f"🏗️ {info.get('name', btype)}{mark}",
            callback_data=_cb(f"city:bq:{btype}:{page}", owner_id),
        )
        if info.get("next") and have >= C.CONVERT_RATIO:
            b.button(
                text=f"♻️ تبدیل {C.CONVERT_RATIO}× {info.get('name', btype)} → {C.building_name(info['next'])}",
                callback_data=_cb(f"city:conv:{btype}:{page}", owner_id),
            )
    if not is_housing:
        add_pager(b, page, total_pages, f"city:cat:{ckey}", owner_id)
    b.button(text="↩️ بازگشت به شهر", callback_data=_cb("city:hub", owner_id))
    b.adjust(1 if is_housing else 2)
    return b.as_markup()


def build_quantity_menu(btype: str, page: int = 0, owner_id=None) -> InlineKeyboardMarkup:
    """Preset/custom quantities; choosing one cannot spend without confirmation."""
    b = InlineKeyboardBuilder()
    for amount in C.BATCH_BUILD_PRESETS:
        b.button(text=f"× {amount:,}", callback_data=_cb(f"city:bv:{btype}:{amount}:{page}", owner_id))
    b.button(text="⌨️ تعداد دلخواه", callback_data=_cb(f"city:bx:{btype}:{page}", owner_id))
    category = C.category_of(btype) or "housing"
    b.button(text="↩️ بازگشت به فهرست", callback_data=_cb(f"city:cat:{category}:{page}", owner_id))
    b.adjust(4, 4, 1, 1)
    return b.as_markup()


def build_confirm_menu(btype: str, amount: int, page: int = 0, owner_id=None, can_confirm: bool = True) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    if can_confirm:
        b.button(text=f"✅ تأیید ساخت ×{int(amount):,}", callback_data=_cb(f"city:bc:{btype}:{int(amount)}:{page}", owner_id))
    b.button(text="🔢 تغییر تعداد", callback_data=_cb(f"city:bq:{btype}:{page}", owner_id))
    category = C.category_of(btype) or "housing"
    b.button(text="↩️ بازگشت به فهرست", callback_data=_cb(f"city:cat:{category}:{page}", owner_id))
    b.adjust(1)
    return b.as_markup()


def tax_menu(owner_id=None) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for rate in C.TAX_OPTIONS:
        b.button(text=f"{rate}%", callback_data=_cb(f"city:settax:{rate}", owner_id))
    b.button(text="↩️ بازگشت به شهر", callback_data=_cb("city:hub", owner_id))
    b.adjust(4)
    return b.as_markup()


def resources_menu(owner_id=None, resources=None) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    resources = resources or {}
    keys = list(getattr(C, "RESOURCE_ORDER", None) or getattr(C, "RESOURCES", {}) or [])
    if not keys:
        keys = ["cement", "steel", "glass", "plastic", "wood", "brick", "fuel", "food"]
    for key in keys:
        try:
            name = C.resource_name(key)
            price = int(C.resource_price(key) or 0)
        except Exception:
            continue
        qty = int(resources.get(key) or 0)
        b.button(text=f"🛒 {name} — خرید {price:,}$", callback_data=_cb(f"city:res:{key}", owner_id))
        if qty > 0:
            sell_p = (price * 80) // 100
            b.button(
                text=f"💵 فروش {name} ({qty:,}) ≈{sell_p * qty:,}$",
                callback_data=_cb(f"city:sellres:{key}", owner_id),
            )
    b.button(text="💵 فروش همه منابع انبار", callback_data=_cb("city:sellresall", owner_id))
    b.button(text="↩️ بازگشت", callback_data=_cb("city:hub", owner_id))
    b.adjust(1)
    return b.as_markup()




def city_mayor_menu(owner_id=None, hired_key=None) -> InlineKeyboardMarkup:
    """v1.7.6.5 -- پنلِ استخدامِ شهردار."""
    b = InlineKeyboardBuilder()
    rows = []
    for key in MY.MAYOR_ORDER:
        info = MY.MAYORS[key]
        if str(hired_key or "") == key:
            b.button(
                text="✅ %s (سرِ کار)" % info["name"],
                callback_data=_cb("city:mayor", owner_id),
            )
        else:
            b.button(
                text="%s — %s$" % (info["name"], "{:,}".format(int(info["hire_cost"]))),
                callback_data=_cb("city:mayor:hire:%s" % key, owner_id),
            )
        rows.append(1)
    if hired_key:
        b.button(
            text="👋 اخراجِ شهردار",
            callback_data=_cb("city:mayor:fire", owner_id),
        )
        rows.append(1)
    b.button(
        text="↩️ بازگشت به شهر",
        callback_data=_cb("city:hub", owner_id),
    )
    rows.append(1)
    b.adjust(*rows)
    return b.as_markup()
