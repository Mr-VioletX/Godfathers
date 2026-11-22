from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.data.market import get_product


def warehouse_locked_menu():
    """وقتی پیش‌نیاز (۳ کارخانه) فراهم نیست."""
    builder = InlineKeyboardBuilder()
    builder.button(text="🏭 رفتن به کارخانه‌ها / بازار", callback_data="market:hub")
    builder.button(text="↩️ بازگشت به منو", callback_data="menu:main")
    builder.adjust(1)
    return builder.as_markup()


def warehouse_build_menu(cost, affordable):
    """وقتی پیش‌نیاز فراهم است ولی هنوز انبار ساخته نشده."""
    builder = InlineKeyboardBuilder()
    builder.button(text=f"🏗️ ساختِ انبارِ اصلی ({cost:,}$)", callback_data="wh:build")
    builder.button(text="🏭 کارخانه‌ها / بازار", callback_data="market:hub")
    builder.button(text="↩️ بازگشت به منو", callback_data="menu:main")
    builder.adjust(1)
    return builder.as_markup()


def warehouse_menu(sellables, up_cost, level):
    """منوی انبارِ ساخته‌شده: فروشِ هر ماده + ارتقا + بروزرسانی."""
    builder = InlineKeyboardBuilder()
    for r in sellables:
        p = get_product(r.product_key)
        name = p["name"] if p else r.product_key
        builder.button(
            text=f"💵 فروشِ {name} ({r.qty:,})",
            callback_data=f"wh:sell:{r.product_key}",
        )
    if sellables:
        builder.button(text="💰 فروشِ همه‌ی موجودی", callback_data="wh:sellall")
    if up_cost is not None:
        builder.button(
            text=f"⬆️ ارتقای انبار ← سطح {level + 1} ({up_cost:,}$)",
            callback_data="wh:upgrade",
        )
    builder.button(text="🔄 بروزرسانی", callback_data="wh:hub")
    builder.button(text="🏭 کارخانه‌ها / بازار", callback_data="market:hub")
    builder.button(text="↩️ بازگشت به منو", callback_data="menu:main")
    builder.adjust(1)
    return builder.as_markup()
