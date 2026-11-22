# -*- coding: utf-8 -*-
"""Keyboards for Stage 87.2 branching Dark World cases."""
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.data import dark_world_cases as C
from app.utils.ui import with_owner

SKILL_ICON = {"stealth": "🥷", "social": "🎭", "tech": "📡", "force": "💥"}


def case_hub_menu(owner_id: int, has_run: bool = False) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    if has_run:
        b.button(text="▶️ ادامه پرونده فعال", callback_data=with_owner("dwc:active", owner_id))
    b.button(text="🗂️ پرونده‌های قابل شروع", callback_data=with_owner("dwc:list", owner_id))
    b.button(text="🎒 ابزارهای مصرفی", callback_data=with_owner("dwc:tools", owner_id))
    b.button(text="🛒 خرید ابزار", callback_data=with_owner("dwc:shop", owner_id))
    b.button(text="↩️ هاب دنیای سیاه", callback_data=with_owner("dw:sec:ops", owner_id))
    b.adjust(1, 2, 1, 1)
    return b.as_markup()


def case_list_menu(influence: int, owner_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    points = max(0, int(influence or 0))
    for key in C.CASE_ORDER:
        case = C.CASES[key]
        required = int(case["required_influence"])
        if points >= required:
            text = f"{case['icon']} {case['name']} · سختی {case['difficulty']}"
            data = f"dwc:case:{key}"
        else:
            text = f"🔒 {case['name']} · {required:,} نفوذ"
            data = "dwc:locked"
        b.button(text=text, callback_data=with_owner(data, owner_id))
    b.button(text="↩️ پرونده‌های تعاملی", callback_data=with_owner("dwc:hub", owner_id))
    b.adjust(1)
    return b.as_markup()


def case_preview_menu(case_key: str, owner_id: int, can_start: bool) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    if can_start:
        b.button(text="🎲 پرداخت و بازکردن پرونده", callback_data=with_owner(f"dwc:start:{case_key}", owner_id))
    b.button(text="↩️ پرونده‌ها", callback_data=with_owner("dwc:list", owner_id))
    b.adjust(1)
    return b.as_markup()


def node_menu(state: dict, owner_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for row in state["choices"]:
        choice = row["choice"]
        chance = float(row["chance"]["chance"])
        icon = SKILL_ICON.get(str(choice["skill"]), "🎲")
        b.button(
            text=f"{choice['icon']} {choice['label']} · {icon}{chance:.0f}٪",
            callback_data=with_owner(f"dwc:choice:{row['key']}", owner_id),
        )
    selected = state.get("selected_tool")
    if selected and C.get_tool(selected):
        tool = C.get_tool(selected)
        tool_text = f"🎒 ابزار: {tool['icon']} {tool['name']}"
    else:
        tool_text = "🎒 انتخاب ابزار برای آزمون بعد"
    b.button(text=tool_text, callback_data=with_owner("dwc:tools", owner_id))
    b.button(text="🚪 رهاکردن پرونده", callback_data=with_owner("dwc:abandon", owner_id))
    b.button(text="↩️ پرونده‌ها", callback_data=with_owner("dwc:hub", owner_id))
    b.adjust(1)
    return b.as_markup()


def tools_menu(inventory: dict[str, int], selected: str | None, owner_id: int, has_run: bool = True) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for key in C.TOOL_ORDER:
        tool = C.TOOLS[key]
        qty = int(inventory.get(key, 0))
        mark = " ✅" if selected == key else ""
        if qty > 0:
            b.button(
                text=f"{tool['icon']} {tool['name']} ×{qty}{mark}",
                callback_data=with_owner(f"dwc:tool:{key}", owner_id),
            )
        else:
            b.button(text=f"▫️ {tool['name']} ×0", callback_data=with_owner("dwc:no_tool", owner_id))
    if selected:
        b.button(text="✖️ کنارگذاشتن ابزار انتخابی", callback_data=with_owner("dwc:tool:none", owner_id))
    b.button(text="🛒 فروشگاه ابزار", callback_data=with_owner("dwc:shop", owner_id))
    if has_run:
        b.button(text="↩️ بازگشت به پرونده", callback_data=with_owner("dwc:active", owner_id))
    else:
        b.button(text="↩️ پرونده‌های تعاملی", callback_data=with_owner("dwc:hub", owner_id))
    b.adjust(1)
    return b.as_markup()


def shop_menu(inventory: dict[str, int], owner_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for key in C.TOOL_ORDER:
        tool = C.TOOLS[key]
        qty = int(inventory.get(key, 0))
        if qty >= C.TOOL_MAX_QTY:
            text, data = f"✅ {tool['name']} · انبار {qty}/{C.TOOL_MAX_QTY}", "dwc:max_tool"
        else:
            text, data = f"{tool['icon']} {tool['name']} · {int(tool['cost']):,}", f"dwc:buy:{key}"
        b.button(text=text, callback_data=with_owner(data, owner_id))
    b.button(text="🎒 انبار ابزار", callback_data=with_owner("dwc:tools", owner_id))
    b.button(text="↩️ پرونده‌های تعاملی", callback_data=with_owner("dwc:hub", owner_id))
    b.adjust(1)
    return b.as_markup()


def abandon_confirm_menu(owner_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="⚠️ بله، پرونده را رها کن", callback_data=with_owner("dwc:abandon_yes", owner_id))
    b.button(text="↩️ ادامه پرونده", callback_data=with_owner("dwc:active", owner_id))
    b.adjust(1)
    return b.as_markup()


def ending_menu(owner_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="🗂️ پرونده تازه", callback_data=with_owner("dwc:list", owner_id))
    b.button(text="🌑 هاب دنیای سیاه", callback_data=with_owner("dw:sec:ops", owner_id))
    b.adjust(1)
    return b.as_markup()
