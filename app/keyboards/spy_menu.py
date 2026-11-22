# app/keyboards/spy_menu.py
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.data.espionage import (
    MAX_SPIES,
    MAX_SPY_LEVEL,
    STATUS_LABELS,
    hire_cost,
    ransom_cost,
    upgrade_cost,
)
from app.utils.ui import with_owner


def back_only_menu(owner_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="↩️ بازگشت به منو", callback_data=with_owner("menu:main", owner_id))
    b.adjust(1)
    return b.as_markup()


def spy_home_menu(spies: list, owner_id: int) -> InlineKeyboardMarkup:
    """خانهٔ جاسوسی: لیستِ جاسوس‌ها + استخدامِ بعدی + اشخاص + بازگشت."""
    b = InlineKeyboardBuilder()
    for s in sorted(spies, key=lambda x: x.slot):
        label = f"🕵️ جاسوس #{s.slot} — Lv{s.level} — {STATUS_LABELS.get(s.status, s.status)}"
        b.button(text=label, callback_data=with_owner(f"spy:open:{s.slot}", owner_id))
    used = len(spies)
    if used < MAX_SPIES:
        next_slot = used + 1
        b.button(
            text=f"➕ استخدامِ جاسوس #{next_slot} — {hire_cost(next_slot):,}$",
            callback_data=with_owner("spy:hire", owner_id),
        )
    b.button(text="👥 مخاطبین", callback_data=with_owner("contacts:list", owner_id))
    b.button(text="↩️ بازگشت به منو", callback_data=with_owner("menu:main", owner_id))
    b.adjust(1)
    return b.as_markup()


def spy_detail_menu(spy, owner_id: int) -> InlineKeyboardMarkup:
    """منوی اختصاصیِ یک جاسوس — برحسبِ وضعیت."""
    b = InlineKeyboardBuilder()
    slot = spy.slot

    if spy.status == "idle":
        b.button(text="📤 اعزام به هدف", callback_data=with_owner(f"spy:deploy:{slot}", owner_id))
    elif spy.status == "active":
        b.button(text="📊 اطلاعاتِ هدف", callback_data=with_owner(f"spy:info:{slot}", owner_id))
        b.button(text="🔙 فراخوانی به پایگاه", callback_data=with_owner(f"spy:recall:{slot}", owner_id))
    elif spy.status == "captured":
        b.button(
            text=f"💵 پرداختِ غرامت — {ransom_cost(slot, spy.level):,}$",
            callback_data=with_owner(f"spy:ransom:{slot}", owner_id),
        )

    # ارتقا — تا وقتی جاسوس زنده است و به سقف نرسیده
    if spy.status in ("idle", "active", "captured"):
        if spy.level >= MAX_SPY_LEVEL:
            b.button(text="⭐ ارتقا (مکس ✅)", callback_data=with_owner(f"spy:upmax:{slot}", owner_id))
        else:
            b.button(
                text=f"⬆️ ارتقا سطح {spy.level} ← {spy.level + 1} ({upgrade_cost(spy.level):,}$)",
                callback_data=with_owner(f"spy:up:{slot}", owner_id),
            )

    b.button(text="↩️ بازگشت به جاسوسی", callback_data=with_owner("spy:hub", owner_id))
    b.adjust(1)
    return b.as_markup()


def deploy_targets_menu(contacts: list, slot: int, owner_id: int) -> InlineKeyboardMarkup:
    """انتخابِ هدف: از اشخاصِ اضافه‌شده یا واردکردنِ دستیِ آیدی/یوزرنیم."""
    b = InlineKeyboardBuilder()
    for c in contacts[:20]:
        title = c.display_name or (f"@{c.username}" if c.username else str(c.contact_id))
        b.button(
            text=f"🎯 {title}",
            callback_data=with_owner(f"spy:target:{slot}:{c.contact_id}", owner_id),
        )
    b.button(
        text="⌨️ واردکردنِ آیدی/یوزرنیم",
        callback_data=with_owner(f"spy:manual:{slot}", owner_id),
    )
    b.button(text="↩️ بازگشت", callback_data=with_owner(f"spy:open:{slot}", owner_id))
    b.adjust(1)
    return b.as_markup()
