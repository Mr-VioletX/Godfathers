# -*- coding: utf-8 -*-
"""کیبوردهای برندسازی — پیشوندِ کالبک: brd:

\U0001f195 مرحله ۲۸: ۵ شرکتِ یکتا (۴ تولیدی + هولدینگِ تفریحی)، تولیدِ درصدی،
نمودارِ قیمتِ مستقل، نام‌گذاری، و صفحه‌بندیِ ۸‌ردیفی با دکمه‌های چپ/راست.
"""
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.data import branding as B
from app.data import brands as BR
from app.utils.ui import add_pager, paginate, with_owner


def _cb(data, owner_id):
    return with_owner(data, owner_id) if owner_id is not None else data


# --------------------------- برندِ پایه ---------------------------
def brand_back_menu(owner_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="↩️ بازگشت به برند", callback_data=_cb("brd:hub", owner_id))
    b.adjust(1)
    return b.as_markup()


def brand_create_menu(owner_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(
        text=f"🏷️ ثبتِ برند ({B.BRAND_FOUND_COST:,}$)",
        callback_data=_cb("brd:create", owner_id),
    )
    b.button(text="↩️ بازگشت به منو", callback_data=_cb("menu:main", owner_id))
    b.adjust(1)
    return b.as_markup()


def brand_home_menu(owner_id: int, level: int) -> InlineKeyboardMarkup:
    """خانه‌ی برند: شرکت‌ها، هولدینگ، نمودارِ قیمت، کمپین و ارتقا."""
    b = InlineKeyboardBuilder()
    b.button(text="🏢 شرکت‌های من", callback_data=_cb("brd:cos", owner_id))
    b.button(text="🎡 هولدینگِ تفریحی", callback_data=_cb("brd:hold", owner_id))
    b.button(text="📈 نمودارِ قیمتِ برند", callback_data=_cb("brd:prices", owner_id))
    b.button(text="📣 کمپینِ تبلیغاتی", callback_data=_cb("brd:camp", owner_id))
    if B.can_upgrade(level):
        b.button(
            text=f"⬆️ ارتقای برند ({B.upgrade_cost(level):,}$)",
            callback_data=_cb("brd:upg", owner_id),
        )
    b.button(text="✏️ تغییرِ نامِ برند", callback_data=_cb("brd:rn:brand:0", owner_id))
    b.button(text="🏆 رتبه‌بندیِ برندها", callback_data=_cb("brd:rank", owner_id))
    b.button(text="↩️ بازگشت به منو", callback_data=_cb("menu:main", owner_id))
    b.adjust(1)
    return b.as_markup()


def campaigns_menu(owner_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for key in B.CAMPAIGN_ORDER:
        c = B.CAMPAIGNS[key]
        b.button(
            text=f"{c['name']} — {c['cost']:,}$ (+{c['rep']}⭐)",
            callback_data=_cb(f"brd:campgo:{key}", owner_id),
        )
    b.button(text="↩️ بازگشت به برند", callback_data=_cb("brd:hub", owner_id))
    b.adjust(1)
    return b.as_markup()


# --------------------------- \U0001f195 شرکت‌ها ---------------------------
def companies_menu(owned, owner_id: int, page: int = 0) -> InlineKeyboardMarkup:
    """owned = دیکشنری {company_key: BrandCompany}."""
    b = InlineKeyboardBuilder()
    items = list(BR.COMPANY_ORDER)
    shown, page, pages = paginate(items, page)
    for key in shown:
        info = BR.COMPANIES[key]
        co = owned.get(key)
        if co is not None:
            title = co.title or info["name"]
            if key == BR.HOLDING_KEY:
                b.button(text=f"🎡 {title}", callback_data=_cb("brd:hold", owner_id))
            else:
                b.button(text=f"✅ {title}", callback_data=_cb(f"brd:co:{co.id}", owner_id))
        else:
            b.button(
                text=f"➕ {info['name']} — {info['cost']:,}$",
                callback_data=_cb(f"brd:new:{key}", owner_id),
            )
    add_pager(b, page, pages, "brd:cosp", owner_id)
    b.button(text="📈 نمودارِ قیمتِ برند", callback_data=_cb("brd:prices", owner_id))
    b.button(text="↩️ بازگشت به برند", callback_data=_cb("brd:hub", owner_id))
    b.adjust(1)
    return b.as_markup()


def company_menu(company, products, ready_map, can_expand, costs, owner_id: int,
                 page: int = 0, queue_count: int = 0) -> InlineKeyboardMarkup:
    """پنلِ یک شرکتِ تولیدی: محصولات + مسیرهای ارتقا."""
    b = InlineKeyboardBuilder()
    shown, page, pages = paginate(list(products), page)
    for bp in shown:
        p = BR.get_brand_product(bp.product_key) or {"name": bp.product_key}
        # 🆕 v1.7.8.18 — هر محصول دو خطِ مستقل دارد (status و status2)
        _busy = (str(getattr(bp, "status", "") or "") == "producing"
                 or str(getattr(bp, "status2", "") or "") == "producing")
        if ready_map.get(bp.id):
            mark = "✅"
        elif _busy:
            mark = "⏳"
        elif bp.stock:
            mark = "📦"
        else:
            mark = "⚪"
        b.button(
            text=f"{mark} {p['name']}",
            callback_data=_cb(f"brd:cp:{company.id}:{bp.product_key}", owner_id),
        )
    add_pager(b, page, pages, f"brd:copg:{company.id}", owner_id)
    b.button(text="▶️ شروعِ همه‌ی خطوط", callback_data=_cb(f"brd:cstartall:{company.id}", owner_id))
    b.button(text="📥 جمع‌آوریِ همه", callback_data=_cb(f"brd:ccolall:{company.id}", owner_id))
    b.button(text="🛑 لغو همه تولیدها", callback_data=_cb(f"brd:ccancelall:{company.id}", owner_id))
    b.button(text="🏢 انتقالِ همه به انبارِ اصلی", callback_data=_cb(f"brd:ctomainall:{company.id}", owner_id))
    if can_expand and costs.get("expand"):
        b.button(
            text=f"🏗️ محصولِ جدید ({costs['expand']:,}$)",
            callback_data=_cb(f"brd:cexpand:{company.id}", owner_id),
        )
    if costs.get("cap"):
        b.button(
            text=f"📦 ارتقای انبار ({costs['cap']:,}$)",
            callback_data=_cb(f"brd:cup:cap:{company.id}", owner_id),
        )
    if costs.get("spd"):
        b.button(
            text=f"⚡ ارتقای سرعت ({costs['spd']:,}$)",
            callback_data=_cb(f"brd:cup:spd:{company.id}", owner_id),
        )
    if costs.get("line"):
        b.button(
            text=f"🧵 خطِ تولیدِ بیشتر ({costs['line']:,}$)",
            callback_data=_cb(f"brd:cup:line:{company.id}", owner_id),
        )
    # 🆕 v1.7.8.17 — صفِ ساختِ شرکت
    b.button(
        text=(f"🧾 صفِ ساخت ({queue_count})" if queue_count else "🧾 صفِ ساخت"),
        callback_data=_cb(f"brd:cq:{company.id}", owner_id),
    )
    b.button(text="✏️ تغییرِ نامِ شرکت", callback_data=_cb(f"brd:rn:co:{company.id}", owner_id))
    b.button(text="🏢 شرکت‌های من", callback_data=_cb("brd:cos", owner_id))
    b.adjust(1)
    return b.as_markup()


def product_menu(company_id: int, bp, ready: bool, owner_id: int, has_warehouse: bool = False,
                 cap_cost=None, cap_level: int = 1, queue_count: int = 0,
                 can_start=None, busy=None) -> InlineKeyboardMarkup:
    """پنلِ یک محصولِ برندی.

    🆕 v1.7.8.17 — ارتقایِ انبارِ همین محصول + صفِ ساخت.
    🆕 v1.7.8.18 — هر محصول دو خطِ مستقل دارد؛ دکمهٔ «درصدِ تولید»
    تا وقتی یک خطِ آزاد باشد نشان داده می‌شود.
    """
    b = InlineKeyboardBuilder()
    key = bp.product_key
    if busy is None:
        busy = (str(getattr(bp, "status", "") or "") == "producing"
                or str(getattr(bp, "status2", "") or "") == "producing")
    if can_start is None:
        can_start = not (str(getattr(bp, "status", "") or "") == "producing"
                         and str(getattr(bp, "status2", "") or "") == "producing")
    if can_start:
        b.button(text="🎛️ درصدِ تولید", callback_data=_cb(f"brd:cpct:{company_id}:{key}", owner_id))
    if ready:
        b.button(text="📥 دریافتِ تولید", callback_data=_cb(f"brd:ccol:{company_id}:{key}", owner_id))
    elif busy:
        b.button(text="⏳ در حالِ تولید…", callback_data=_cb("brd:wait", owner_id))
    if busy:
        b.button(text="🛑 لغو تولید", callback_data=_cb(f"brd:ccancel:{company_id}:{key}", owner_id))
    b.button(text=f"💰 فروشِ انبار ({bp.stock or 0:,})", callback_data=_cb(f"brd:csell:{company_id}:{key}", owner_id))
    b.button(text="🏢 انتقال به انبارِ اصلی", callback_data=_cb(f"brd:ctomain:{company_id}:{key}", owner_id))
    # 🆕 v1.7.8.17 — صفِ ساخت و ارتقایِ انبارِ محصول
    b.button(text="🧾 افزودن به صفِ ساخت", callback_data=_cb(f"brd:cqpct:{company_id}:{key}", owner_id))
    if queue_count:
        b.button(
            text=f"🧾 صفِ ساختِ این شرکت ({queue_count})",
            callback_data=_cb(f"brd:cq:{company_id}", owner_id),
        )
    if cap_cost is not None:
        b.button(
            text=f"📦 انبارِ محصول ← سطح {cap_level + 1} ({cap_cost:,}$)",
            callback_data=_cb(f"brd:pcap:{company_id}:{key}", owner_id),
        )
    b.button(text="📈 نمودارِ قیمت", callback_data=_cb(f"brd:chart:{key}", owner_id))
    b.button(text="↩️ بازگشت به شرکت", callback_data=_cb(f"brd:co:{company_id}", owner_id))
    b.adjust(1)
    return b.as_markup()


def percent_menu(company_id: int, product_key: str, owner_id: int) -> InlineKeyboardMarkup:
    """انتخابِ درصدِ حجمِ خالی (پله‌ی ۱۰٪)."""
    b = InlineKeyboardBuilder()
    for pct in BR.PERCENT_STEPS:
        b.button(
            text=f"{pct}٪",
            callback_data=_cb(f"brd:cstart:{company_id}:{product_key}:{pct}", owner_id),
        )
    b.adjust(5)
    b.row()
    b.button(text="✖ انصراف", callback_data=_cb(f"brd:cp:{company_id}:{product_key}", owner_id))
    return b.as_markup()


def queue_percent_menu(company_id: int, product_key: str, owner_id: int) -> InlineKeyboardMarkup:
    """🆕 v1.7.8.17 — درصدِ ظرفیتِ انبارِ محصول برایِ سفارشِ صف."""
    b = InlineKeyboardBuilder()
    for pct in BR.PERCENT_STEPS:
        b.button(
            text=f"{pct}٪",
            callback_data=_cb(f"brd:cqadd:{company_id}:{product_key}:{pct}", owner_id),
        )
    b.adjust(5)
    b.row()
    b.button(text="✖ انصراف", callback_data=_cb(f"brd:cp:{company_id}:{product_key}", owner_id))
    return b.as_markup()


def company_queue_menu(company_id: int, items, owner_id: int, page: int = 0) -> InlineKeyboardMarkup:
    """🆕 v1.7.8.17 — منویِ صفِ ساختِ یک شرکتِ برند."""
    b = InlineKeyboardBuilder()
    items = list(items or [])
    shown, page, pages = paginate(items, page)
    for it in shown:
        p = BR.get_brand_product(it.product_key) or {"name": it.product_key}
        b.button(
            text=f"🗑️ {p['name']} — {int(getattr(it, 'units', 0) or 0):,} واحد",
            callback_data=_cb(f"brd:cqdel:{it.id}", owner_id),
        )
    add_pager(b, page, pages, f"brd:cqpg:{company_id}", owner_id)
    if items:
        b.button(text="▶️ شروعِ صف", callback_data=_cb(f"brd:cqrun:{company_id}", owner_id))
        b.button(
            text="🗑️ خالی‌کردنِ صف (بازپرداختِ کامل)",
            callback_data=_cb(f"brd:cqclr:{company_id}", owner_id),
        )
    b.button(text="↩️ بازگشت به شرکت", callback_data=_cb(f"brd:co:{company_id}", owner_id))
    b.adjust(1)
    return b.as_markup()


def expand_menu(company_id: int, keys, owner_id: int, page: int = 0) -> InlineKeyboardMarkup:
    """انتخابِ محصولِ جدید برای بازکردن."""
    b = InlineKeyboardBuilder()
    shown, page, pages = paginate(list(keys), page)
    for key in shown:
        p = BR.get_brand_product(key) or {"name": key}
        b.button(
            text=f"🏗️ {p['name']}",
            callback_data=_cb(f"brd:caddp:{company_id}:{key}", owner_id),
        )
    add_pager(b, page, pages, f"brd:cexpandp:{company_id}", owner_id)
    b.button(text="↩️ بازگشت به شرکت", callback_data=_cb(f"brd:co:{company_id}", owner_id))
    b.adjust(1)
    return b.as_markup()


# --------------------------- \U0001f195 هولدینگ ---------------------------
def holding_buy_menu(owner_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    info = BR.COMPANIES[BR.HOLDING_KEY]
    b.button(
        text=f"🎡 خریدِ هولدینگ ({info['cost']:,}$)",
        callback_data=_cb(f"brd:new:{BR.HOLDING_KEY}", owner_id),
    )
    b.button(text="↩️ بازگشت به برند", callback_data=_cb("brd:hub", owner_id))
    b.adjust(1)
    return b.as_markup()


def holding_menu(units, owner_id: int, page: int = 0) -> InlineKeyboardMarkup:
    """units = دیکشنری {unit_key: HoldingUnit}."""
    b = InlineKeyboardBuilder()
    shown, page, pages = paginate(list(BR.HOLDING_UNIT_ORDER), page)
    for key in shown:
        info = BR.HOLDING_UNITS[key]
        u = units.get(key)
        if u is not None:
            b.button(text=f"✅ {u.title or info['name']}", callback_data=_cb(f"brd:hu:{u.id}", owner_id))
        elif info["base"]:
            b.button(text=f"🏨 {info['name']} (پایه)", callback_data=_cb(f"brd:hbuy:{key}", owner_id))
        else:
            b.button(
                text=f"➕ {info['name']} — {info['cost']:,}$",
                callback_data=_cb(f"brd:hbuy:{key}", owner_id),
            )
    add_pager(b, page, pages, "brd:holdp", owner_id)
    b.button(text="💰 دریافتِ درآمدِ هولدینگ", callback_data=_cb("brd:hcol", owner_id))
    b.button(text="✏️ تغییرِ نامِ هولدینگ", callback_data=_cb("brd:rn:hold:0", owner_id))
    b.button(text="↩️ بازگشت به برند", callback_data=_cb("brd:hub", owner_id))
    b.adjust(1)
    return b.as_markup()


def holding_unit_menu(unit, tracks: dict, owner_id: int, page: int = 0) -> InlineKeyboardMarkup:
    """منوی ارتقای یک واحدِ هولدینگ."""
    b = InlineKeyboardBuilder()
    info = BR.HOLDING_UNITS.get(unit.unit_key) or {"tracks": {}}
    items = list((info.get("tracks") or {}).items())
    shown, page, pages = paginate(items, page)
    for tkey, t in shown:
        lv = int((tracks or {}).get(tkey, 0) or 0)
        if lv >= BR.HOLDING_TRACK_MAX:
            b.button(text=f"✅ {t['name']} — سطحِ نهایی", callback_data=_cb("brd:hmax", owner_id))
        else:
            cost = BR.unit_track_cost(unit.unit_key, tkey, lv)
            b.button(
                text=f"⬆️ {t['name']} (سطح {lv}) — {cost:,}$",
                callback_data=_cb(f"brd:ht:{unit.id}:{tkey}", owner_id),
            )
    add_pager(b, page, pages, f"brd:hup:{unit.id}", owner_id)
    b.button(text="✏️ تغییرِ نام", callback_data=_cb(f"brd:rn:hu:{unit.id}", owner_id))
    b.button(text="🎡 هولدینگ", callback_data=_cb("brd:hold", owner_id))
    b.adjust(1)
    return b.as_markup()


# --------------------------- \U0001f195 نمودارِ قیمتِ برند ---------------------------
def brand_prices_menu(owner_id: int, page: int = 0) -> InlineKeyboardMarkup:
    """گروه‌های قیمت به تفکیکِ شرکت."""
    b = InlineKeyboardBuilder()
    items = BR.producer_companies()
    shown, page, pages = paginate(items, page)
    for key in shown:
        b.button(text=BR.company_name(key), callback_data=_cb(f"brd:pc:{key}", owner_id))
    add_pager(b, page, pages, "brd:pricesp", owner_id)
    b.button(text="↩️ بازگشت به برند", callback_data=_cb("brd:hub", owner_id))
    b.adjust(1)
    return b.as_markup()


def company_prices_menu(company_key: str, owner_id: int, page: int = 0) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    items = BR.company_products(company_key)
    shown, page, pages = paginate(items, page)
    for key in shown:
        p = BR.get_brand_product(key) or {"name": key}
        b.button(text=f"📈 {p['name']}", callback_data=_cb(f"brd:chart:{key}", owner_id))
    add_pager(b, page, pages, f"brd:pcp:{company_key}", owner_id)
    b.button(text="🏢 همه‌ی شرکت‌ها", callback_data=_cb("brd:prices", owner_id))
    b.button(text="↩️ بازگشت به برند", callback_data=_cb("brd:hub", owner_id))
    b.adjust(1)
    return b.as_markup()


def brand_chart_back_menu(product_key: str, owner_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    ckey = BR.company_of_product(product_key)
    if ckey:
        b.button(text=f"↩️ {BR.company_name(ckey)}", callback_data=_cb(f"brd:pc:{ckey}", owner_id))
    b.button(text="🏢 همه‌ی شرکت‌ها", callback_data=_cb("brd:prices", owner_id))
    b.button(text="↩️ بازگشت به برند", callback_data=_cb("brd:hub", owner_id))
    b.adjust(1)
    return b.as_markup()
