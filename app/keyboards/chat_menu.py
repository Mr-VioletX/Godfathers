# app/keyboards/chat_menu.py
"""کیبوردهایِ چت‌مود (مرحله ۱۳.۶)."""
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

from app.utils.ui import with_owner

PAGE = 10   # صفحه‌بندیِ ۱۰‌تاییِ مخاطبین


def chat_home_menu(owner_id: int) -> InlineKeyboardMarkup:
    """منویِ اصلیِ «خطِ محرمانه»."""
    b = InlineKeyboardBuilder()
    b.button(text="▶️ شروعِ چت‌مود", callback_data=with_owner("chat:start", owner_id))
    b.button(text="📨 پیام‌های خوانده‌نشده", callback_data=with_owner("chat:unread", owner_id))
    b.button(text="📜 درخواست‌های چتِ هفته‌ی اخیر", callback_data=with_owner("chat:reqhistory", owner_id))
    b.button(text="⏹️ پایانِ چت‌مود", callback_data=with_owner("chat:end", owner_id))
    b.button(text="🚫 کاربرانِ بلاک‌شده", callback_data=with_owner("chat:blocked", owner_id))
    b.button(text="↩️ بازگشت به منو", callback_data=with_owner("menu:main", owner_id))
    b.adjust(1)
    return b.as_markup()


def contacts_pick_menu(contacts: list, owner_id: int, page: int = 0) -> InlineKeyboardMarkup:
    """انتخابِ مخاطب برایِ شروعِ چت + صفحه‌بندی."""
    total = max(1, (len(contacts) + PAGE - 1) // PAGE)
    page = max(0, min(page, total - 1))
    chunk = contacts[page * PAGE:(page + 1) * PAGE]
    b = InlineKeyboardBuilder()
    for c in chunk:
        title = c.display_name or (f"@{c.username}" if c.username else str(c.contact_id))
        b.row(InlineKeyboardButton(
            text=f"💬 {title}",
            callback_data=with_owner(f"chat:pick:{c.contact_id}", owner_id),
        ))
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(
            text="صفحه‌ی قبل ➡️",
            callback_data=with_owner(f"chat:pgt:{page - 1}", owner_id),
        ))
    if page < total - 1:
        nav.append(InlineKeyboardButton(
            text="⬅️ صفحه‌ی بعد",
            callback_data=with_owner(f"chat:pgt:{page + 1}", owner_id),
        ))
    if nav:
        b.row(*nav)
    b.row(InlineKeyboardButton(text="↩️ بازگشت", callback_data=with_owner("chat:menu", owner_id)))
    return b.as_markup()


def request_decision_menu(requester_id: int, target_id: int) -> InlineKeyboardMarkup:
    """دکمه‌هایِ تأیید/ردِ درخواستِ چت (سمتِ هدف؛ owner=target)."""
    b = InlineKeyboardBuilder()
    b.button(text="✅ تأیید و شروعِ چت", callback_data=with_owner(f"chat:accept:{requester_id}", target_id))
    b.button(text="❌ رد", callback_data=with_owner(f"chat:reject:{requester_id}", target_id))
    b.adjust(2)
    return b.as_markup()


def offline_leave_menu(target_id: int, owner_id: int) -> InlineKeyboardMarkup:
    """پیشنهادِ گذاشتنِ پیامِ آفلاین یا انصراف از درخواست (سمتِ درخواست‌دهنده)."""
    b = InlineKeyboardBuilder()
    b.button(text="✍️ گذاشتنِ پیام", callback_data=with_owner(f"chat:leavemsg:{target_id}", owner_id))
    b.button(text="❌ انصراف از درخواست", callback_data=with_owner(f"chat:cancelreq:{target_id}", owner_id))
    b.button(text="↩️ بازگشت", callback_data=with_owner("chat:menu", owner_id))
    b.adjust(1)
    return b.as_markup()


def request_sent_menu(target_id: int, owner_id: int) -> InlineKeyboardMarkup:
    """🆕 بعد از ارسالِ درخواستِ چت (وقتی هدف آنلاین است): امکانِ انصراف از درخواست."""
    b = InlineKeyboardBuilder()
    b.button(text="❌ انصراف از درخواست", callback_data=with_owner(f"chat:cancelreq:{target_id}", owner_id))
    b.button(text="↩️ بازگشت", callback_data=with_owner("chat:menu", owner_id))
    b.adjust(1)
    return b.as_markup()


def request_history_menu(entries: list, owner_id: int) -> InlineKeyboardMarkup:
    """🆕 لیستِ درخواست‌های چتِ هفته‌ی اخیر: دکمه‌ی پاسخ/شروعِ چت برای هر فرستنده.

    entries: لیستی از دیکشنری‌های {"requester_id": int, "name": str}
    """
    b = InlineKeyboardBuilder()
    seen_ids: set = set()
    for e in entries[:10]:
        rid = e["requester_id"]
        if rid in seen_ids:
            continue
        seen_ids.add(rid)
        b.button(text=f"💬 پاسخ/شروعِ چت با {e['name']}", callback_data=with_owner(f"chat:pick:{rid}", owner_id))
    b.button(text="↩️ بازگشت", callback_data=with_owner("chat:menu", owner_id))
    b.adjust(1)
    return b.as_markup()


def offline_reply_menu(from_id: int, owner_id: int) -> InlineKeyboardMarkup:
    """دکمه‌یِ پاسخ/شروعِ چت با فرستنده‌یِ پیامِ آفلاین."""
    b = InlineKeyboardBuilder()
    b.button(text="💬 پاسخ / شروعِ چت", callback_data=with_owner(f"chat:pick:{from_id}", owner_id))
    b.adjust(1)
    return b.as_markup()


def blocked_menu(blocked: list, owner_id: int) -> InlineKeyboardMarkup:
    """لیستِ بلاک‌شده‌ها با دکمه‌یِ رفعِ بلاک."""
    b = InlineKeyboardBuilder()
    for bu in blocked[:25]:
        b.button(
            text=f"♻️ رفعِ بلاک: {bu.blocked_id}",
            callback_data=with_owner(f"chat:unblock:{bu.blocked_id}", owner_id),
        )
    b.button(text="↩️ بازگشت", callback_data=with_owner("chat:menu", owner_id))
    b.adjust(1)
    return b.as_markup()


def chat_active_kb() -> ReplyKeyboardMarkup:
    """کیبوردِ پایینِ حینِ چتِ فعال."""
    b = ReplyKeyboardBuilder()
    b.add(
        KeyboardButton(text="⏹️ پایان چت"),
        KeyboardButton(text="🚨 گزارش"),
        KeyboardButton(text="🚫 بلاک کاربر"),
    )
    b.adjust(3)
    return b.as_markup(resize_keyboard=True)
