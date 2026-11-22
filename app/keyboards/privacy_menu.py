from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.utils.ui import with_owner
from app.data.profile import (   # 🆕 مرحله ۳۰
    ANNOUNCE_IDLE_CHOICES,
    announce_idle_minutes,
    announce_in_group,
    idle_label,
)

PRIVACY_LABELS = {
    "cash": "💰 موجودی",
    "level": "⭐ سطح",
    "rank": "🏆 رنکینگ",
    "title": "🎖️ لقب",
    "photo": "🖼️ عکس",   # ⭐ گزینه‌ی جدید
}


def privacy_menu(settings: dict, owner_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for key, label in PRIVACY_LABELS.items():
        shown = settings.get(key, True)
        mark = "✅ نمایش" if shown else "❌ مخفی"
        builder.button(
            text=f"{label} — {mark}",
            callback_data=with_owner(f"privacy:toggle:{key}", owner_id),
        )
    builder.button(text="↩️ بازگشت", callback_data=with_owner("profile:back", owner_id))
    builder.adjust(1)
    return builder.as_markup()


def announce_menu(settings: dict, owner_id: int) -> InlineKeyboardMarkup:
    """منوی اصلی اعلام آنلاین — v1.7.8.19: ساعت‌ها در «فاصلهٔ اعلام» و گروه‌ها در «گروه‌ها»."""
    builder = InlineKeyboardBuilder()
    enabled = settings.get("enabled", True)
    mark = "✅ روشن" if enabled else "❌ خاموش"
    builder.button(
        text=f"📣 اعلام آنلاین (کلی): {mark}",
        callback_data=with_owner("announce:toggle", owner_id),
    )
    if enabled:
        cur_idle = announce_idle_minutes(settings)
        builder.button(
            text=f"⏱️ فاصلهٔ اعلام: {idle_label(cur_idle)}",
            callback_data=with_owner("announce:idle", owner_id),
        )
        builder.button(
            text="👥 گروه‌ها",
            callback_data=with_owner("announce:groups", owner_id),
        )
    builder.button(text="↩️ بازگشت", callback_data=with_owner("profile:back", owner_id))
    builder.adjust(1)
    return builder.as_markup()


def announce_idle_menu(settings: dict, owner_id: int) -> InlineKeyboardMarkup:
    """🆕 v1.7.8.19 — زیرمنوی فاصلهٔ اعلام؛ ساعت‌ها اینجا منتقل شدند."""
    builder = InlineKeyboardBuilder()
    cur_idle = announce_idle_minutes(settings)
    for m in ANNOUNCE_IDLE_CHOICES:
        picked = "✔️ " if m == cur_idle else ""
        builder.button(
            text=f"{picked}{idle_label(m)}",
            callback_data=with_owner(f"announce:idle:set:{m}", owner_id),
        )
    builder.button(text="⬅️ بازگشت", callback_data=with_owner("announce:home", owner_id))
    n = len(ANNOUNCE_IDLE_CHOICES)
    rows = [3] * (n // 3) + ([n % 3] if n % 3 else [])
    builder.adjust(*rows, 1)
    return builder.as_markup()


def announce_groups_menu(
    settings: dict, groups: list[tuple[int, str | None]], owner_id: int
) -> InlineKeyboardMarkup:
    """🆕 v1.7.8.19 — زیرمنوی گروه‌ها؛ فعالیت در گروه + کنترل تک‌تک گروه‌ها اینجا منتقل شدند."""
    builder = InlineKeyboardBuilder()
    gmark = "✅ روشن" if announce_in_group(settings) else "❌ خاموش"
    builder.button(
        text=f"💬 فعالیت در گروه هم حساب شود: {gmark}",
        callback_data=with_owner("announce:ingroup", owner_id),
    )
    group_prefs = settings.get("groups", {})
    if groups:
        for chat_id, chat_title in groups:
            shown = group_prefs.get(str(chat_id), True)
            gmark = "✅ روشن" if shown else "❌ خاموش"
            title = chat_title or f"گروه {chat_id}"
            builder.button(
                text=f"{title} — {gmark}",
                callback_data=with_owner(f"announce:group:{chat_id}", owner_id),
            )
    else:
        builder.button(
            text="— هنوز در هیچ گروهی نیستی —",
            callback_data=with_owner("announce:noop", owner_id),
        )
    builder.button(text="⬅️ بازگشت", callback_data=with_owner("announce:home", owner_id))
    builder.adjust(1)
    return builder.as_markup()
