# -*- coding: utf-8 -*-
"""کیبوردِ رتبه‌بندی (مرحله ۱۳.۵) + v1.7.2 فیلتر گزینه‌های خاموش‌شده."""
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.services.ranking import CATEGORIES
from app.utils.ui import with_owner


def ranking_kb(
    owner_id: int,
    cat: str,
    page: int,
    total_pages: int,
    *,
    categories=None,
    extra_visibility: dict | None = None,
) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    cats = list(categories) if categories is not None else list(CATEGORIES)
    vis = extra_visibility or {}

    cat_buttons = []
    for code, label, _unit in cats:
        text = f"• {label} •" if code == cat else label
        cat_buttons.append(
            InlineKeyboardButton(
                text=text, callback_data=with_owner(f"rank:{code}:0", owner_id)
            )
        )
    # v1.7.6.3 — دکمهٔ «🏅 رنک» از زیرِ دکمه‌های پیمایش به کنارِ دکمهٔ
    # «🏙️ شهر» منتقل شد.
    league_btn = None
    if vis.get("league", True):
        league_btn = InlineKeyboardButton(
            text="🏅 رنک",
            callback_data=with_owner("rankx:league:0:0", owner_id),
        )

    rows = [cat_buttons[_i:_i + 3] for _i in range(0, len(cat_buttons), 3)]

    league_placed = False
    if league_btn is not None:
        _city_cb = with_owner("rank:city:0", owner_id)
        for _ri, _row in enumerate(rows):
            for _ci, _btn in enumerate(_row):
                if _btn.callback_data == _city_cb:
                    if len(_row) >= 3:
                        # ردیف پُر است؛ «شهر» یک ردیف پایین‌تر می‌آید
                        # تا «رنک» دقیقاً کنارش بنشیند.
                        rows.insert(_ri + 1, [_row.pop(_ci), league_btn])
                    else:
                        _row.insert(_ci + 1, league_btn)
                    league_placed = True
                    break
            if league_placed:
                break

    for _row in rows:
        if _row:
            b.row(*_row)

    nav = []
    if page > 0:
        nav.append(
            InlineKeyboardButton(
                text="◀️ قبلی",
                callback_data=with_owner(f"rank:{cat}:{page - 1}", owner_id),
            )
        )
    nav.append(
        InlineKeyboardButton(
            text=f"📄 {page + 1}/{max(1, total_pages)}",
            callback_data=with_owner("rank:noop:0", owner_id),
        )
    )
    if page < total_pages - 1:
        nav.append(
            InlineKeyboardButton(
                text="بعدی ▶️",
                callback_data=with_owner(f"rank:{cat}:{page + 1}", owner_id),
            )
        )
    if nav:
        b.row(*nav)

    row2 = []
    if vis.get("global", True):
        row2.append(InlineKeyboardButton(
            text="🌍 رتبه‌بندیِ کلی",
            callback_data=with_owner("rankx:global:0", owner_id),
        ))
    # اگر دستهٔ «شهر» خاموش/پنهان بود، «رنک» همان جای قبلی می‌ماند تا گم نشود
    if league_btn is not None and not league_placed:
        row2.append(league_btn)
    if row2:
        b.row(*row2)

    row3 = []
    if vis.get("war_ranked", True):
        row3.append(InlineKeyboardButton(
            text="⚔️ جنگِ رنکینگ",
            callback_data=with_owner("war:ranked", owner_id),
        ))
    # 🆕 v1.7.9.1 — رنکینگ کاپ اتحادیه‌ها در بخش رنکینگ اصلی
    if vis.get("alliance", True):
        row3.append(InlineKeyboardButton(
            text="🤝 رنکینگ اتحادیه‌ها",
            callback_data=with_owner("alw:rank:0", owner_id),
        ))
    if vis.get("power_formula", True):
        row3.append(InlineKeyboardButton(
            text="⚡ فرمولِ قدرت",
            callback_data=with_owner("rankx:power", owner_id),
        ))
    if row3:
        b.row(*row3)

    b.row(
        InlineKeyboardButton(
            text="🏠 بازگشت به منو",
            callback_data=with_owner("menu:main", owner_id),
        )
    )
    return b.as_markup()


_LEAGUE_EMOJI = ["🥉", "🥈", "🥇", "💎", "🔱", "👑"]


def _rank_back_row(b, owner_id: int) -> None:
    b.row(
        InlineKeyboardButton(text="🏆 رنکینگ", callback_data=with_owner("menu:ranking", owner_id)),
        InlineKeyboardButton(text="🏠 منو", callback_data=with_owner("menu:main", owner_id)),
    )


def global_ladder_kb(owner_id: int, page: int, pages: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(
            text="◀️ قبلی",
            callback_data=with_owner(f"rankx:global:{page - 1}", owner_id),
        ))
    nav.append(InlineKeyboardButton(
        text=f"📄 {page + 1}/{pages}",
        callback_data=with_owner("rank:noop:0", owner_id),
    ))
    if page < pages - 1:
        nav.append(InlineKeyboardButton(
            text="بعدی ▶️",
            callback_data=with_owner(f"rankx:global:{page + 1}", owner_id),
        ))
    b.row(*nav)
    _rank_back_row(b, owner_id)
    return b.as_markup()


def league_ladder_kb(owner_id: int, idx: int, page: int, pages: int, league_count: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    league_buttons = []
    for i in range(league_count):
        emoji = _LEAGUE_EMOJI[i] if i < len(_LEAGUE_EMOJI) else "🎖️"
        text = f"• {emoji} •" if i == idx else emoji
        league_buttons.append(InlineKeyboardButton(
            text=text,
            callback_data=with_owner(f"rankx:league:{i}:0", owner_id),
        ))
    for j in range(0, len(league_buttons), 3):
        b.row(*league_buttons[j:j + 3])
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(
            text="◀️ قبلی",
            callback_data=with_owner(f"rankx:league:{idx}:{page - 1}", owner_id),
        ))
    nav.append(InlineKeyboardButton(
        text=f"📄 {page + 1}/{pages}",
        callback_data=with_owner("rank:noop:0", owner_id),
    ))
    if page < pages - 1:
        nav.append(InlineKeyboardButton(
            text="بعدی ▶️",
            callback_data=with_owner(f"rankx:league:{idx}:{page + 1}", owner_id),
        ))
    b.row(*nav)
    _rank_back_row(b, owner_id)
    return b.as_markup()


def rank_info_kb(owner_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    _rank_back_row(b, owner_id)
    return b.as_markup()
