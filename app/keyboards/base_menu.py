from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.data.bases import FIRST_TIER, MAX_TIER, get_tier, next_tier
from app.data.upgrades import FEATURES, MAX_FEATURE_LEVEL, upgrade_cost
from app.utils.ui import with_owner


def buy_base_menu(owner_id: int) -> InlineKeyboardMarkup:
    """منوی خریدِ اولیه: فقط تیرِ اول (Covo) + بازگشت به منو."""
    tier = get_tier(FIRST_TIER)
    builder = InlineKeyboardBuilder()
    builder.button(
        text=f"🥷 خریدِ {tier['name']} — {tier['up_cost']:,}$",
        callback_data=with_owner("buybase", owner_id),
    )
    builder.button(text="↩️ بازگشت به منو", callback_data=with_owner("menu:main", owner_id))
    builder.adjust(1)
    return builder.as_markup()


def base_menu(hideout, owner_id: int) -> InlineKeyboardMarkup:
    """منوی تیرِ فعلی: ارتقای ویژگی + (در صورتِ مکس) ارتقا به تیرِ بعد + بازگشت به منو."""
    builder = InlineKeyboardBuilder()
    tier = get_tier(hideout.base_type)
    feat = FEATURES[tier["feature"]]
    current = getattr(hideout, f"{feat['key']}_level")

    if current >= MAX_FEATURE_LEVEL:
        builder.button(text=f"{feat['name']} (مکس ✅)", callback_data=with_owner("upgrade:max", owner_id))
    else:
        cost = upgrade_cost(feat["base_cost"], current)
        builder.button(
            text=f"⬆️ {feat['name']} — سطح {current} ← {current + 1} ({cost:,}$)",
            callback_data=with_owner(f"upgrade:{feat['key']}", owner_id),
        )

    nxt_key = next_tier(hideout.base_type)
    if current >= MAX_FEATURE_LEVEL and nxt_key is not None:
        nxt = get_tier(nxt_key)
        builder.button(
            text=f"🏗️ ارتقا به {nxt['name']} — {nxt['up_cost']:,}$",
            callback_data=with_owner(f"tierup:{nxt_key}", owner_id),
        )

    # 🆕 مرحله ۲۶.۲: دکمه‌ی جداگانه‌ی «تغییرِ نام» حذف شد — انتخابِ عمارتِ هدف
    # فقط همون لحظه‌ی ساختِ پایگاهِ تیرِ چهار (در tierup_callback) اتفاق می‌افتد.

    builder.button(text="↩️ بازگشت به منو", callback_data=with_owner("menu:main", owner_id))
    builder.adjust(1)
    return builder.as_markup()


def final_variant_menu(choices, owner_id: int) -> InlineKeyboardMarkup:
    """منوی انتخابِ نامِ پایگاهِ لولِ نهایی براساسِ عمارت‌های دردسترس (choices = [(key, name), ...])."""
    builder = InlineKeyboardBuilder()
    for key, name in choices:
        builder.button(text=name, callback_data=with_owner(f"tierupname:{key}", owner_id))
    builder.button(text="↩️ انصراف", callback_data=with_owner("menu:base", owner_id))
    builder.adjust(1)
    return builder.as_markup()


def all_done_menu(owner_id: int) -> InlineKeyboardMarkup:
    """منو برایِ وقتی تمامِ عمارت‌ها ساخته شده و دیگه پایگاهی برای ساخت نیست."""
    builder = InlineKeyboardBuilder()
    builder.button(text="🏛️ رفتن به بخشِ عمارت", callback_data=with_owner("menu:estate", owner_id))
    builder.button(text="↩️ بازگشت به منو", callback_data=with_owner("menu:main", owner_id))
    builder.adjust(1)
    return builder.as_markup()