# -*- coding: utf-8 -*-
"""کیبوردهای مرحله ۱۹ — بخشِ نظامی. پیشوندِ کالبک: mil:"""
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.data import military as M
from app.utils.ui import with_owner


def military_home_menu(owner_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="🪖 سربازخانه و ارتش", callback_data=with_owner("mil:army", owner_id))
    b.button(text="🏗️ صفِ پرورشِ نیرو", callback_data=with_owner("mil:queue", owner_id))
    b.button(text="⬆️ ارتقای سربازخانه", callback_data=with_owner("mil:barracks", owner_id))
    b.button(text="🏪 کارخانه‌ی تسلیحاتی", callback_data=with_owner("mil:shop", owner_id))
    b.button(text="⬆️ ارتقا و آموزش", callback_data=with_owner("mil:upgrade", owner_id))
    b.button(text="📖 راهنمای نیروها", callback_data=with_owner("mil:guide", owner_id))
    b.button(text="⚔️ آوردگاهِ آزمایشی", callback_data=with_owner("mil:spar", owner_id))
    b.button(text="🏥 بیمارستان / تعمیر", callback_data=with_owner("mil:hospital", owner_id))
    b.button(text="↩️ بازگشت به منو", callback_data=with_owner("menu:main", owner_id))
    # v1.7.6.3 - منوی نطامی دوستونه شد: ۸ دکمه بخش‌ها در ۴ ردیف دوتایی
    # و دکمه «بازگشت به منو» تک‌ردیفه در پایین.
    b.adjust(2, 2, 2, 2, 1)
    return b.as_markup()



def barracks_upgrade_menu(owner_id: int, can_upgrade: bool) -> InlineKeyboardMarkup:
    b=InlineKeyboardBuilder()
    if can_upgrade: b.button(text="✅ شروع ارتقای یک‌روزه", callback_data=with_owner("mil:barracksgo", owner_id))
    b.button(text="↩️ بازگشت به نظامی", callback_data=with_owner("mil:hub", owner_id)); b.adjust(1); return b.as_markup()

def military_back_menu(owner_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="↩️ بازگشت به نظامی", callback_data=with_owner("mil:hub", owner_id))
    b.adjust(1)
    return b.as_markup()


# --------------------------- 🆕 v1.7.6.3 — بیمارستانِ دستی ---------------------------
def hospital_list_menu(owner_id: int, wards, now=None) -> InlineKeyboardMarkup:
    """فهرستِ ردیف‌های مجروحان — هر نبرد یک ردیفِ جداگانه با مهلتِ خودش."""
    from app.services import hospital_service as HS

    b = InlineKeyboardBuilder()
    for ward in (wards or []):
        b.button(
            text=HS.ward_button_text(ward, now),
            callback_data=with_owner(f"mil:hosp:v:{int(ward.id)}", owner_id),
        )
    b.button(text="🔄 بروزرسانی", callback_data=with_owner("mil:hospital", owner_id))
    b.button(text="↩️ بازگشت به نظامی", callback_data=with_owner("mil:hub", owner_id))
    # هر ردیفِ مجروحان تک‌ستونه (متنِ بلنددارد)؛ دو دکمهٔ پایانی کنار هم.
    b.adjust(*([1] * len(list(wards or []))), 2)
    return b.as_markup()


def hospital_detail_menu(owner_id: int, ward_id: int, payable: bool = True) -> InlineKeyboardMarkup:
    """جزئیاتِ یک ردیف + دکمهٔ پرداختِ هزینهٔ درمان."""
    b = InlineKeyboardBuilder()
    if payable:
        b.button(
            text="💰 پرداخت و درمان",
            callback_data=with_owner(f"mil:hosp:pay:{int(ward_id)}", owner_id),
        )
    b.button(text="↩️ فهرستِ بیمارستان", callback_data=with_owner("mil:hospital", owner_id))
    b.button(text="🏠 بازگشت به نظامی", callback_data=with_owner("mil:hub", owner_id))
    b.adjust(1, 2) if payable else b.adjust(2)
    return b.as_markup()


def shop_categories_menu(owner_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for cat in M.CATEGORY_ORDER:
        b.button(text=M.CATEGORY_LABELS[cat], callback_data=with_owner(f"mil:cat:{cat}", owner_id))
    b.button(text="↩️ بازگشت به نظامی", callback_data=with_owner("mil:hub", owner_id))
    b.adjust(2)
    return b.as_markup()


def category_units_menu(owner_id: int, cat: str, player_level: int, levels: dict) -> InlineKeyboardMarkup:
    """levels: {unit_key: upgrade_level} برای محاسبه‌ی قیمتِ خریدِ فعلی."""
    b = InlineKeyboardBuilder()
    for k in M.units_in_category(cat):
        u = M.get_unit(k)
        lv = int(levels.get(k, 0))
        price = M.buy_cost(k, lv)
        if int(player_level) < u["unlock"]:
            b.button(text=f"🔒 {u['name']} (سطح {u['unlock']})", callback_data=with_owner("mil:locked", owner_id))
        else:
            b.button(text=f"{u['name']} — {price:,}$", callback_data=with_owner(f"mil:buy:{k}", owner_id))
    b.button(text="↩️ دسته‌ها", callback_data=with_owner("mil:shop", owner_id))
    b.adjust(1)
    return b.as_markup()


def buy_qty_menu(owner_id: int, unit_key: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for q in (1, 250, 500, 1000):
        b.button(text=f"🛒 ×{q}", callback_data=with_owner(f"mil:buyq:{unit_key}:{q}", owner_id))
    b.button(text="⌨️ واردکردنِ تعداد", callback_data=with_owner(f"mil:buyn:{unit_key}", owner_id))
    b.button(text="↩️ بازگشت", callback_data=with_owner(f"mil:cat:{M.get_unit(unit_key)['cat']}", owner_id))
    b.adjust(2)
    return b.as_markup()



def buy_confirm_menu(owner_id: int, unit_key: str, qty: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="✅ تأیید خرید", callback_data=with_owner(f"mil:buyok:{unit_key}:{qty}", owner_id))
    b.button(text="✖️ انصراف", callback_data=with_owner(f"mil:buy:{unit_key}", owner_id))
    b.adjust(1)
    return b.as_markup()

def upgrade_units_menu(owner_id: int, owned: list, cash: int | None = None) -> InlineKeyboardMarkup:
    """owned: [(unit_key, count, level), ...]

    🆕 مرحله ۲۷ (رفعِ باگِ بخشِ ارتقایِ نیروها): فقط نیروهایی که واقعاً داری نمایش داده
    می‌شوند، و اگر پولِ کافی نداشته باشی رویِ دکمه علامتِ 🔒 می‌خورد (قبلاً هیچ بازخوردی نبود)."""
    b = InlineKeyboardBuilder()
    for k, cnt, lv in owned:
        u = M.get_unit(k)
        if not u or int(cnt) <= 0:
            continue
        if M.can_upgrade(lv):
            cost = M.upgrade_cost(k, lv, cnt)
            poor = cash is not None and int(cash) < cost
            mark = "🔒" if poor else "⬆️"
            b.button(
                text=f"{mark} {u['name']} لول{lv}→{lv+1} — {cost:,}$",
                callback_data=with_owner(f"mil:upgo:{k}", owner_id),
            )
        else:
            b.button(text=f"✅ {u['name']} — بیشینه (لول {lv})", callback_data=with_owner("mil:noop", owner_id))
    b.button(text="🔄 به‌روزرسانی", callback_data=with_owner("mil:upgrade", owner_id))
    b.button(text="↩️ بازگشت به نظامی", callback_data=with_owner("mil:hub", owner_id))
    b.adjust(1)
    return b.as_markup()


def training_queue_menu(owner_id: int, page: int = 0, total_pages: int = 1) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="🗑️ لغو صف‌ها و بازگشت پول", callback_data=with_owner(f"mil:qcancelmenu:{page}", owner_id))
    if total_pages > 1:
        b.button(text="◀️ قبلی", callback_data=with_owner(f"mil:queue:{(page - 1) % total_pages}", owner_id))
        b.button(text=f"{page + 1}/{total_pages}", callback_data=with_owner("mil:noop", owner_id))
        b.button(text="بعدی ▶️", callback_data=with_owner(f"mil:queue:{(page + 1) % total_pages}", owner_id))
    b.button(text="🔄 به‌روزرسانی", callback_data=with_owner(f"mil:queue:{page}", owner_id))
    b.button(text="🏪 ساختِ نیروی جدید", callback_data=with_owner("mil:shop", owner_id))
    b.button(text="↩️ بازگشت به نظامی", callback_data=with_owner("mil:hub", owner_id))
    b.adjust(1, 3, 1, 1)
    return b.as_markup()


def training_cancel_menu(owner_id: int, inactive: list[dict], page: int, total_pages: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for q in inactive:
        b.button(text=f"🗑️ {q['name']} ×{q['qty']:,}", callback_data=with_owner(f"mil:qcancel:{q['id']}:{page}", owner_id))
    if total_pages > 1:
        b.button(text="◀️ قبلی", callback_data=with_owner(f"mil:qcancelmenu:{(page - 1) % total_pages}", owner_id))
        b.button(text=f"{page + 1}/{total_pages}", callback_data=with_owner("mil:noop", owner_id))
        b.button(text="بعدی ▶️", callback_data=with_owner(f"mil:qcancelmenu:{(page + 1) % total_pages}", owner_id))
    b.button(text="↩️ بازگشت به صف‌ها", callback_data=with_owner(f"mil:queue:{page}", owner_id))
    b.adjust(1)
    return b.as_markup()
