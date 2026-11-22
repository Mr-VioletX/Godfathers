from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def gender_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    # callback_data یک برچسب مخفی است که هنگام کلیک به ربات فرستاده می‌شود
    builder.button(text="🤵 مرد (The Don)", callback_data="gender:male")
    builder.button(text="👰 زن (La Donna)", callback_data="gender:female")
    builder.adjust(2)  # هر دو دکمه در یک ردیف
    return builder.as_markup()