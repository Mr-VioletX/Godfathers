# -*- coding: utf-8 -*-
"""منوهای بازار و کارخانه‌ها — مرحله ۲۸.

نکاتِ جدید:
  • ۵ کارخانه‌ی یکتا (بدون #شماره) و هر کدام فقط یک‌بار قابلِ ساخت.
  • تولید با انتخابِ درصدِ حجمِ خالیِ انبار (پله‌ی ۱۰٪).
  • نمودارِ قیمت بر اساسِ کارخانه‌ها گروه‌بندی شده: هر کارخانه فقط محصولاتِ خودش.
  • همه‌ی لیست‌های بلندتر از ۸ ردیف، دو دکمه‌ی پیمایشِ ◀️/▶️ دارند.
"""
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.data.factories import (
    FACTORY_ORDER,
    FACTORY_TYPES,
    PERCENT_STEPS,
    factory_name,
    products_for_factory,
)
from app.data.market import get_product
from app.utils.ui import PAGE_SIZE, add_pager, paginate


def locked_menu():
    """وقتی بازار قفل است — فقط دکمه‌ی «بازگشت به منو»."""
    builder = InlineKeyboardBuilder()
    builder.button(text="↩️ بازگشت به منو", callback_data="menu:main")
    builder.adjust(1)
    return builder.as_markup()


def market_hub_menu(factories, can_build=True, page=0, owner_id=None):
    """منوی اصلیِ بازار: کارخانه‌های ساخته‌شده + ساخت + نمودارها + انبارِ اصلی."""
    builder = InlineKeyboardBuilder()
    rows, page, pages = paginate(list(factories), page, PAGE_SIZE)
    for f in rows:
        key = getattr(f, "factory_key", None) or ""
        builder.button(
            text=factory_name(key) if key in FACTORY_TYPES else "🏭 کارخانه",
            callback_data=f"factory:view:{f.id}",
        )
    add_pager(builder, page, pages, "market:hubp", owner_id)
    if can_build:
        builder.button(text="🏗️ ساختِ کارخانه", callback_data="factory:build")
    builder.button(text="📈 نمودارِ قیمتِ کارخانه‌ها", callback_data="market:prices")
    builder.button(text="🏢 انبارِ اصلی", callback_data="menu:warehouse")
    builder.button(text="↩️ بازگشت به منو", callback_data="menu:main")
    builder.adjust(1)
    return builder.as_markup()


def build_list_menu(items, page=0, owner_id=None):
    """لیستِ کارخانه‌های قابلِ ساخت. items = [(factory_key, cost, buildable, lock_kind)]"""
    builder = InlineKeyboardBuilder()
    rows, page, pages = paginate(list(items), page, PAGE_SIZE)
    for item in rows:
        key, cost, buildable = item[0], item[1], item[2]
        lock_kind = item[3] if len(item) > 3 else None
        if buildable:
            builder.button(
                text=f"{factory_name(key)} — {cost:,}$",
                callback_data=f"factory:new:{key}",
            )
        elif lock_kind == "giga":
            builder.button(
                text=f"🔒 {factory_name(key)} — 💎ویژه",
                callback_data="factory:locked_giga",
            )
        else:
            builder.button(
                text=f"🔒 {factory_name(key)}",
                callback_data="factory:locked",
            )
    add_pager(builder, page, pages, "factory:buildp", owner_id)
    builder.button(text="↩️ بازگشت", callback_data="market:hub")
    builder.adjust(1)
    return builder.as_markup()


def factory_menu(factory, fps, ready_map, can_expand, costs, page=0, owner_id=None,
                 queue_count=0):
    """منوی جزئیاتِ یک کارخانه: محصولات + گسترش + مسیرهای ارتقا."""
    builder = InlineKeyboardBuilder()
    rows, page, pages = paginate(list(fps), page, PAGE_SIZE)
    for fp in rows:
        p = get_product(fp.product_key)
        name = p["name"] if p else fp.product_key
        # 🆕 v1.7.8.18 — هر محصول دو خطِ مستقل دارد (status و status2)
        _busy = (str(getattr(fp, "status", "") or "") == "producing"
                 or str(getattr(fp, "status2", "") or "") == "producing")
        if ready_map.get(fp.id):
            tag = "✅"
        elif _busy:
            tag = "⏳"
        else:
            tag = "⚪"
        extra = f" 📦{fp.stock:,}" if fp.stock else ""
        builder.button(text=f"{tag} {name}{extra}", callback_data=f"fp:view:{fp.id}")
    add_pager(builder, page, pages, f"factory:page:{factory.id}", owner_id)
    if can_expand and costs.get("expand") is not None:
        builder.button(
            text=f"🏗️ بازکردنِ محصولِ بعدی ({costs['expand']:,}$)",
            callback_data=f"factory:expand:{factory.id}",
        )
    if costs.get("cap") is not None:
        builder.button(
            text=f"📦 ظرفیت ← سطح {factory.capacity_level + 1} ({costs['cap']:,}$)",
            callback_data=f"factory:up:cap:{factory.id}",
        )
    if costs.get("spd") is not None:
        builder.button(
            text=f"⚡ سرعت ← سطح {factory.speed_level + 1} ({costs['spd']:,}$)",
            callback_data=f"factory:up:spd:{factory.id}",
        )
    builder.button(text="🛑 لغو تولید همه خطوط", callback_data=f"factory:cancelall:{factory.id}")
    if costs.get("line") is not None:
        builder.button(
            text=f"🧵 خطِ تولید ← سطح {factory.line_level + 1} ({costs['line']:,}$)",
            callback_data=f"factory:up:line:{factory.id}",
        )
    if fps:
        builder.button(text="▶️ شروعِ همه‌ی خط‌ها", callback_data=f"factory:startall:{factory.id}")
        if any(ready_map.get(fp.id) for fp in fps):
            builder.button(text="📦 جمع‌آوریِ همه", callback_data=f"factory:collectall:{factory.id}")
        if any(fp.stock > 0 for fp in fps):
            builder.button(
                text="🏢 انتقالِ همه به انبارِ اصلی",
                callback_data=f"factory:allmain:{factory.id}",
            )
            builder.button(
                text="💵 فروشِ همه‌ی محصولات",
                callback_data=f"factory:sellall:{factory.id}",
            )
    # 🆕 v1.7.8.17 — صفِ ساختِ کارخانه
    builder.button(
        text=(f"🧾 صفِ ساخت ({queue_count})" if queue_count else "🧾 صفِ ساخت"),
        callback_data=f"fq:menu:{factory.id}",
    )
    builder.button(
        text="📈 نمودارِ قیمتِ محصولاتِ این کارخانه",
        callback_data=f"market:pf:{getattr(factory, 'factory_key', '') or ''}",
    )
    builder.button(text="↩️ بازگشت به بازار", callback_data="market:hub")
    builder.adjust(1)
    return builder.as_markup()


def expand_list_menu(factory_id, keys, cost, page=0, owner_id=None):
    """لیستِ محصولاتِ قابلِ بازشدنِ همین کارخانه."""
    builder = InlineKeyboardBuilder()
    rows, page, pages = paginate(list(keys), page, PAGE_SIZE)
    for key in rows:
        p = get_product(key)
        name = p["name"] if p else key
        builder.button(
            text=f"➕ {name} ({cost:,}$)",
            callback_data=f"factory:addprod:{factory_id}:{key}",
        )
    add_pager(builder, page, pages, f"factory:expandp:{factory_id}", owner_id)
    builder.button(text="↩️ بازگشت", callback_data=f"factory:view:{factory_id}")
    builder.adjust(1)
    return builder.as_markup()


def product_menu(fp, ready, sell_value, has_warehouse, cap_cost=None, cap_level=1,
                 queue_count=0, can_start=None, busy=None):
    """منوی یک محصولِ داخلِ کارخانه.

    🆕 v1.7.8.17 — دکمهٔ ارتقایِ انبارِ همین محصول و دکمهٔ صفِ ساخت.
    🆕 v1.7.8.18 — هر محصول دو خطِ مستقل دارد؛ پس دکمهٔ «شروعِ تولید»
    همزمان با «جمع‌آوری»/«در حالِ تولید» نشان داده می‌شود.
    """
    builder = InlineKeyboardBuilder()
    if busy is None:
        busy = (str(getattr(fp, "status", "") or "") == "producing"
                or str(getattr(fp, "status2", "") or "") == "producing")
    if can_start is None:
        can_start = not (str(getattr(fp, "status", "") or "") == "producing"
                         and str(getattr(fp, "status2", "") or "") == "producing")
    if can_start:
        builder.button(text="▶️ شروعِ تولید (انتخابِ درصد)", callback_data=f"fp:pct:{fp.id}")
    if ready:
        builder.button(text="📦 جمع‌آوریِ محصول", callback_data=f"fp:collect:{fp.id}")
    elif busy:
        builder.button(text="⏳ در حالِ تولید...", callback_data="factory:wait")
    if busy:
        builder.button(text="🛑 لغو تولید", callback_data=f"fp:cancel:{fp.id}")
    builder.button(
        text=f"💵 فروشِ انبار ({sell_value:,}$)",
        callback_data=f"fp:sell:{fp.id}",
    )
    builder.button(text="🏢 انتقال به انبارِ اصلی", callback_data=f"fp:tomain:{fp.id}")
    # 🆕 v1.7.8.17 — فرستادن به صفِ ساخت
    builder.button(text="🧾 افزودن به صفِ ساخت", callback_data=f"fpq:pct:{fp.id}")
    if queue_count:
        builder.button(
            text=f"🧾 صفِ ساختِ این کارخانه ({queue_count})",
            callback_data=f"fq:menu:{fp.factory_id}",
        )
    # 🆕 v1.7.8.17 — ارتقایِ انبارِ همین محصول
    if cap_cost is not None:
        builder.button(
            text=f"📦 انبارِ محصول ← سطح {cap_level + 1} ({cap_cost:,}$)",
            callback_data=f"fp:upcap:{fp.id}",
        )
    builder.button(text="📈 نمودارِ قیمت", callback_data=f"market:chart:{fp.product_key}")
    builder.button(text="↩️ بازگشت به کارخانه", callback_data=f"factory:view:{fp.factory_id}")
    builder.adjust(1)
    return builder.as_markup()


def percent_menu(fp_id, unit_cost, free_room):
    """انتخابِ درصدِ حجمِ خالیِ انبار برای تولید (پله‌ی ۱۰٪)."""
    builder = InlineKeyboardBuilder()
    for pct in PERCENT_STEPS:
        units = max(1, int(max(0, free_room) * pct // 100)) if free_room > 0 else 0
        builder.button(
            text=f"{pct}% — {units:,} واحد ({units * unit_cost:,}$)",
            callback_data=f"fp:start:{fp_id}:{pct}",
        )
    builder.adjust(2)
    builder.row()
    builder.button(text="❌ انصراف", callback_data=f"fp:view:{fp_id}")
    return builder.as_markup()


def queue_percent_menu(fp_id, unit_cost, cap):
    """🆕 v1.7.8.17 — انتخابِ حجمِ سفارشی که به صفِ ساخت می‌رود.

    برخلافِ percent_menu که درصدی از *حجمِ خالی* است، اینجا درصدی از
    *کلِ ظرفیتِ انبارِ محصول* است؛ چون هدفِ صف دقیقاً تولیدِ بیشتر از جایِ
    فعلیِ انبار است.
    """
    builder = InlineKeyboardBuilder()
    for pct in PERCENT_STEPS:
        units = max(1, int(max(0, cap) * pct // 100))
        builder.button(
            text=f"{pct}% — {units:,} واحد ({units * unit_cost:,}$)",
            callback_data=f"fpq:add:{fp_id}:{pct}",
        )
    builder.adjust(2)
    builder.row()
    builder.button(text="❌ انصراف", callback_data=f"fp:view:{fp_id}")
    return builder.as_markup()


def factory_queue_menu(factory_id, items, by_id=None, page=0, owner_id=None):
    """🆕 v1.7.8.17 — منویِ صفِ ساختِ یک کارخانه."""
    builder = InlineKeyboardBuilder()
    items = list(items or [])
    rows, page, pages = paginate(items, page, PAGE_SIZE)
    for it in rows:
        p = get_product(it.product_key)
        name = p["name"] if p else it.product_key
        builder.button(
            text=f"🗑️ {name} — {int(getattr(it, 'units', 0) or 0):,} واحد",
            callback_data=f"fq:del:{it.id}",
        )
    add_pager(builder, page, pages, f"fq:page:{factory_id}", owner_id)
    if items:
        builder.button(text="▶️ شروعِ صف", callback_data=f"fq:run:{factory_id}")
        builder.button(
            text="🗑️ خالی‌کردنِ صف (بازپرداختِ کامل)",
            callback_data=f"fq:clear:{factory_id}",
        )
    builder.button(text="↩️ بازگشت به کارخانه", callback_data=f"factory:view:{factory_id}")
    builder.adjust(1)
    return builder.as_markup()


def prices_menu(page=0, owner_id=None):
    """گروه‌های نمودارِ قیمت — دقیقاً بر اساسِ ۵ کارخانه‌ی بازی."""
    builder = InlineKeyboardBuilder()
    rows, page, pages = paginate(list(FACTORY_ORDER), page, PAGE_SIZE)
    for key in rows:
        builder.button(text=factory_name(key), callback_data=f"market:pf:{key}")
    add_pager(builder, page, pages, "market:pricesp", owner_id)
    builder.button(text="💎 نمودارِ برندسازی", callback_data="brd:prices")
    builder.button(text="↩️ بازگشت به بازار", callback_data="market:hub")
    builder.adjust(1)
    return builder.as_markup()


def factory_prices_menu(factory_key, page=0, owner_id=None):
    """نمودارِ قیمتِ محصولاتِ همین کارخانه (و فقط همین کارخانه)."""
    builder = InlineKeyboardBuilder()
    keys = products_for_factory(factory_key)
    rows, page, pages = paginate(keys, page, PAGE_SIZE)
    for key in rows:
        p = get_product(key)
        name = p["name"] if p else key
        builder.button(text=f"📈 {name}", callback_data=f"market:chart:{key}")
    add_pager(builder, page, pages, f"market:pfp:{factory_key}", owner_id)
    builder.button(text="🏭 همه‌ی کارخانه‌ها", callback_data="market:prices")
    builder.button(text="↩️ بازگشت به بازار", callback_data="market:hub")
    builder.adjust(1)
    return builder.as_markup()


def chart_back_menu(product_key=None):
    """بازگشت از نمودار به گروهِ کارخانه‌ی همان محصول."""
    builder = InlineKeyboardBuilder()
    p = get_product(product_key) if product_key else None
    fkey = (p or {}).get("factory")
    if fkey:
        builder.button(
            text=f"📈 محصولاتِ {factory_name(fkey)}",
            callback_data=f"market:pf:{fkey}",
        )
    builder.button(text="🏭 همه‌ی کارخانه‌ها", callback_data="market:prices")
    builder.button(text="↩️ بازگشت به بازار", callback_data="market:hub")
    builder.adjust(1)
    return builder.as_markup()
