from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.data.thefts import available_thefts
from app.utils.ui import with_owner


def theft_menu(level: int, owner_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for t in available_thefts(level):
        label = f"{t['name']} ({t['min_reward']:,}-{t['max_reward']:,}$)"
        builder.button(
            text=label, callback_data=with_owner(f"theft:{t['key']}", owner_id)
        )
    builder.button(
        text="↩️ بازگشت به منو", callback_data=with_owner("menu:main", owner_id)
    )
    builder.adjust(1)
    return builder.as_markup()

def after_theft_menu(owner_id: int) -> InlineKeyboardMarkup:
    """دکمه‌های بعد از نتیجه‌ی دزدی: تکرار یا بازگشت به منو (بدون ReplyKeyboard)."""
    builder = InlineKeyboardBuilder()
    builder.button(text="🔁 دزدی دیگر", callback_data=with_owner("menu:theft", owner_id))
    builder.button(text="↩️ بازگشت به منو", callback_data=with_owner("menu:main", owner_id))
    builder.adjust(1)
    return builder.as_markup()