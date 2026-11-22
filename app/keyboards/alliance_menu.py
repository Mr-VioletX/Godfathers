# -*- coding: utf-8 -*-
"""کیبوردهای مرحله ۱۸ — اتحادیه‌ها و جنگِ اتحادیه. پیشوندِ کالبک: all:"""
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.data import alliance as A
from app.data import alliance_military as AM  # 🆕 v1.7.9.1
from app.utils.ui import with_owner


def alliance_back_menu(owner_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="↩️ بازگشت به اتحادیه", callback_data=with_owner("all:hub", owner_id))
    b.adjust(1)
    return b.as_markup()


def alliance_home_menu(owner_id: int, *, has_alliance: bool, role: str | None = None, perms=None) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    if not has_alliance:
        b.button(text="🏗️ ساختِ اتحادیه", callback_data=with_owner("all:create", owner_id))
        b.button(text="🔍 پیوستن به اتحادیه", callback_data=with_owner("all:browse:0", owner_id))
        b.button(text="🏆 رتبه‌بندیِ اتحادیه‌ها", callback_data=with_owner("all:rank:0", owner_id))
        b.button(text="↩️ بازگشت به منو", callback_data=with_owner("menu:main", owner_id))
        b.adjust(1)
        return b.as_markup()
    is_leader = role == A.ROLE_LEADER
    # 🆕 مرحله ۳۰ — دکمه‌های معاون بر اساسِ دسترسیِ داده‌شده از طرفِ رئیس
    _perms = set(perms or ())

    def _can(key: str) -> bool:
        return is_leader or key in _perms

    # 🆕 v1.8.1.2 — هاب خوشه‌ای: جزئیات در ۳ زیرمنوی تنظیمات/نظامی/اعضا
    b.button(text="📊 پروفایلِ اتحادیه", callback_data=with_owner("all:info", owner_id))
    b.button(text="🏆 رتبه‌بندیِ کل", callback_data=with_owner("all:rank:0", owner_id))
    b.button(text="⚔️ نظامی", callback_data=with_owner("all:sec:military", owner_id))
    b.button(text="👥 اعضا", callback_data=with_owner("all:sec:members", owner_id))
    b.button(text="⚙️ تنظیمات اتحادیه", callback_data=with_owner("all:sec:settings", owner_id))
    b.button(text="↩️ بازگشت به منو", callback_data=with_owner("menu:main", owner_id))
    b.adjust(1)
    return b.as_markup()


def alliance_military_menu(owner_id: int) -> InlineKeyboardMarkup:
    """⚔️ نظامی — جنگ، سربازخانه، صندوق."""
    b = InlineKeyboardBuilder()
    b.button(text="⚔️ جنگِ اتحادیه", callback_data=with_owner("all:war", owner_id))
    b.button(text="🏰 سربازخانه‌ی اتحادیه", callback_data=with_owner("alw:bk", owner_id))
    b.button(text="💰 صندوق و واریز", callback_data=with_owner("alw:trs", owner_id))
    b.button(text="↩️ بازگشت به اتحادیه", callback_data=with_owner("all:hub", owner_id))
    b.adjust(1)
    return b.as_markup()


def alliance_members_menu(owner_id: int, *, role: str | None = None, perms=None) -> InlineKeyboardMarkup:
    """👥 اعضا — رتبه‌بندی داخلی، درخواست‌های عضویت، خروج."""
    b = InlineKeyboardBuilder()
    is_leader = role == A.ROLE_LEADER
    _perms = set(perms or ())

    def _can(key: str) -> bool:
        return is_leader or key in _perms

    b.button(text="👥 رتبه‌بندیِ داخلی", callback_data=with_owner("all:internal", owner_id))
    if _can(A.PERM_REQUESTS):
        b.button(text="📥 درخواست‌های عضویت", callback_data=with_owner("all:requests", owner_id))
    if not is_leader:
        b.button(text="🚪 خروج از اتحادیه", callback_data=with_owner("all:leaveq", owner_id))
    b.button(text="↩️ بازگشت به اتحادیه", callback_data=with_owner("all:hub", owner_id))
    b.adjust(1)
    return b.as_markup()


def alliance_settings_sec_menu(owner_id: int, *, role: str | None = None, perms=None) -> InlineKeyboardMarkup:
    """⚙️ تنظیمات اتحادیه — ارتقا، تنظیمات، نقش‌ها، انحلال."""
    b = InlineKeyboardBuilder()
    is_leader = role == A.ROLE_LEADER
    _perms = set(perms or ())

    def _can(key: str) -> bool:
        return is_leader or key in _perms

    if _can(A.PERM_UPGRADE):
        b.button(text="⬆️ ارتقای اتحادیه", callback_data=with_owner("all:upgrade", owner_id))
    if _can(A.PERM_SETTINGS):
        b.button(text="⚙️ تنظیمات", callback_data=with_owner("all:settings", owner_id))
    if is_leader:
        b.button(text="🎖️ نقش‌ها و دسترسی‌ها", callback_data=with_owner("all:roles", owner_id))
        b.button(text="💥 انحلالِ اتحادیه", callback_data=with_owner("all:disq", owner_id))
    b.button(text="↩️ بازگشت به اتحادیه", callback_data=with_owner("all:hub", owner_id))
    b.adjust(1)
    return b.as_markup()


def browse_menu(chunk, owner_id: int, page: int, total: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for al, power, cnt in chunk:
        b.button(text=f"➕ {al.name} ({al.tag})", callback_data=with_owner(f"all:reqjoin:{al.id}", owner_id))
    if page > 0:
        b.button(text="◀️ قبلی", callback_data=with_owner(f"all:browse:{page-1}", owner_id))
    if page < total - 1:
        b.button(text="بعدی ▶️", callback_data=with_owner(f"all:browse:{page+1}", owner_id))
    b.button(text="↩️ بازگشت به اتحادیه", callback_data=with_owner("all:hub", owner_id))
    b.adjust(1)
    return b.as_markup()


def requests_menu(items, owner_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for pid, nm, pw in items[:10]:
        b.button(text=f"✅ {nm}", callback_data=with_owner(f"all:acc:{pid}", owner_id))
        b.button(text=f"❌ {nm}", callback_data=with_owner(f"all:rej:{pid}", owner_id))
    b.button(text="↩️ بازگشت به اتحادیه", callback_data=with_owner("all:hub", owner_id))
    b.adjust(2)
    return b.as_markup()


def roles_menu(items, owner_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for pid, nm, role in items:
        if role == A.ROLE_LEADER:
            continue
        if role == A.ROLE_DEPUTY:
            b.button(text=f"🔑 دسترسی‌های {nm}", callback_data=with_owner(f"all:perms:{pid}", owner_id))
            b.button(text=f"⬇️ عزلِ معاون: {nm}", callback_data=with_owner(f"all:demote:{pid}", owner_id))
        else:
            b.button(text=f"⬆️ معاون‌کردن: {nm}", callback_data=with_owner(f"all:promote:{pid}", owner_id))
    b.button(text="↩️ بازگشت به اتحادیه", callback_data=with_owner("all:hub", owner_id))
    b.adjust(1)
    return b.as_markup()


def settings_menu(owner_id: int, al) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text=f"💳 درصدِ اشتراک ({al.sub_pct}٪/{al.sub_days}روز)", callback_data=with_owner("all:set_sub", owner_id))
    b.button(text=f"🔐 آستانه‌ی قدرتِ عضویت ({al.min_power:,})", callback_data=with_owner("all:set_power", owner_id))
    b.button(text="✏️ تغییرِ نام", callback_data=with_owner("all:set_name", owner_id))
    b.button(text="🔤 تغییرِ آیدی", callback_data=with_owner("all:set_tag", owner_id))
    b.button(text="↩️ بازگشت به اتحادیه", callback_data=with_owner("all:hub", owner_id))
    b.adjust(1)
    return b.as_markup()


def upgrade_menu(owner_id: int, al) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    if A.cap_is_maxed(al.level):
        b.button(text="👥 سقفِ اعضا: بیشینه ✅", callback_data=with_owner("all:hub", owner_id))
    else:
        nxt = A.member_cap_for_level(al.level + 1)
        cur = A.member_cap_for_level(al.level)
        b.button(
            text=f"👥 ارتقای سقفِ اعضا ({cur}→{nxt}) — {AM.member_cap_upgrade_cost(al.level):,}$",  # 🆕 v1.7.9.1 — ۳۰×
            callback_data=with_owner("all:up_cap", owner_id),
        )
    # 🆕 v1.7.9.1 — «ارتقای قدرتِ نظامی» حذف شد؛ ارتش در سربازخانه است
    b.button(
        text="🏰 سربازخانه‌ی اتحادیه (ساخت/ارتقای ارتش)",
        callback_data=with_owner("alw:bk", owner_id),
    )
    b.button(text="↩️ بازگشت به اتحادیه", callback_data=with_owner("all:hub", owner_id))
    b.adjust(1)
    return b.as_markup()


def war_menu(owner_id: int, *, has_active: bool, is_officer: bool, vote_id: int | None = None, has_battle: bool = False) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    if has_battle:
        b.button(text="🔥 نبردِ زنده — دنبال‌کردنِ فازها", callback_data=with_owner("alw:war", owner_id))
    if has_active and vote_id is not None:
        b.button(text="✅ موافقِ حمله", callback_data=with_owner(f"all:vote:{vote_id}:1", owner_id))
        b.button(text="❌ مخالفِ حمله", callback_data=with_owner(f"all:vote:{vote_id}:0", owner_id))
    elif is_officer:
        b.button(text="⚔️ پیشنهادِ حمله به اتحادیه", callback_data=with_owner("all:warprop:0", owner_id))
    b.button(text="🏆 رنکینگِ کاپِ اتحادیه‌ها", callback_data=with_owner("alw:rank:0", owner_id))
    b.button(text="↩️ بازگشت به اتحادیه", callback_data=with_owner("all:hub", owner_id))
    b.adjust(1)
    return b.as_markup()


def war_targets_menu(chunk, owner_id: int, page: int, total: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for al, power, cnt in chunk:
        b.button(text=f"⚔️ {al.name} ({al.tag}) — 💥{power:,}", callback_data=with_owner(f"all:wardo:{al.id}", owner_id))
    if page > 0:
        b.button(text="◀️ قبلی", callback_data=with_owner(f"all:warprop:{page-1}", owner_id))
    if page < total - 1:
        b.button(text="بعدی ▶️", callback_data=with_owner(f"all:warprop:{page+1}", owner_id))
    b.button(text="↩️ بازگشت به اتحادیه", callback_data=with_owner("all:hub", owner_id))
    b.adjust(1)
    return b.as_markup()


def rank_menu(owner_id: int, page: int, total: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    if page > 0:
        b.button(text="◀️ قبلی", callback_data=with_owner(f"all:rank:{page-1}", owner_id))
    if page < total - 1:
        b.button(text="بعدی ▶️", callback_data=with_owner(f"all:rank:{page+1}", owner_id))
    b.button(text="↩️ بازگشت به اتحادیه", callback_data=with_owner("all:hub", owner_id))
    b.adjust(1)
    return b.as_markup()


def confirm_menu(owner_id: int, kind: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    if kind == "leave":
        b.button(text="✅ بله، خارج شو", callback_data=with_owner("all:leavego", owner_id))
    else:
        b.button(text="✅ بله، منحل کن", callback_data=with_owner("all:disgo", owner_id))
    b.button(text="↩️ انصراف", callback_data=with_owner("all:hub", owner_id))
    b.adjust(1)
    return b.as_markup()


def perms_menu(pid: int, perms, owner_id: int) -> InlineKeyboardMarkup:
    """🆕 مرحله ۳۰ — روشن/خاموش‌کردنِ دسترسی‌هایِ یک معاون."""
    b = InlineKeyboardBuilder()
    have = set(perms or ())
    for key in A.PERM_ORDER:
        mark = "✅" if key in have else "❌"
        b.button(
            text=f"{mark} {A.PERM_LABELS[key]}",
            callback_data=with_owner(f"all:permt:{pid}:{key}", owner_id),
        )
    b.button(text="🎖️ بازگشت به نقش‌ها", callback_data=with_owner("all:roles", owner_id))
    b.button(text="↩️ بازگشت به اتحادیه", callback_data=with_owner("all:hub", owner_id))
    b.adjust(1)
    return b.as_markup()


def internal_rank_menu(owner_id: int, basis: str) -> InlineKeyboardMarkup:
    """رنکینگ داخلی بر دو اساس: قدرت / امتیاز مشارکت (v1.7.9.1 — خواسته‌ی امیر)."""
    b = InlineKeyboardBuilder()
    if basis == "contrib":
        b.button(text="💥 نمایش بر اساس قدرت", callback_data=with_owner("all:internal:power", owner_id))
    else:
        b.button(text="🎖️ نمایش بر اساس مشارکت", callback_data=with_owner("all:internal:contrib", owner_id))
    b.button(text="↩️ بازگشت به اتحادیه", callback_data=with_owner("all:hub", owner_id))
    b.adjust(1)
    return b.as_markup()


# ═══════════════════════════════════════════════════════════════════════════
# 🆕 v1.8.2.0 — منوهای سربازخانه‌ی اتحادیه به سبکِ بخشِ نظامیِ عادی (mil:)
#
# قبلاً «تولید نیرو» یک منوی کشوییِ مسطح بود (۵ واحد در هر صفحه، مخلوط با دکمه‌های
# ارتقا) که بعد از هر خرید به صفحه‌ی اول برمی‌گشت. حالا دقیقاً مثلِ بخشِ نظامی:
#   دسته‌ها (alw:shop) ← هر دسته جایِ خودش ← نیروها (alw:cat) ← انتخابِ تعدادِ
#   اسکادران (alw:buy) ← پیش‌نمایش (alw:buyq) ← تأیید (alw:buyok)
#   + صفِ تولیدِ جداگانه با صفحه‌بندی و لغوِ بازگشت‌دار (alw:queue)
#   + منوی جداگانه‌ی ارتقا و آموزش (alw:upgm)
# همهٔ دکمه‌ها از بیلدر استاندارد aiogram استفاده می‌کنند و ایموجی‌های Unicode
# مستقیماً در متن باقی می‌مانند؛ هیچ آیکون یا نگاشت سفارشی روی آن‌ها اعمال نمی‌شود.
# ═══════════════════════════════════════════════════════════════════════════


def alw_barracks_home_menu(owner_id: int, can_manage: bool, auto_on: bool, queued_count: int = 0) -> InlineKeyboardMarkup:
    """هابِ سربازخانه — مثلِ military_home_menu: هر بخش دکمه‌ی مستقلِ خودش."""
    b = InlineKeyboardBuilder()
    b.button(text="🏭 تولید نیرو (اسکادرانی)", callback_data=with_owner("alw:shop", owner_id))
    b.button(text=f"🏗️ صفِ تولید ({queued_count} بچ)", callback_data=with_owner("alw:queue:0", owner_id))
    if can_manage:
        b.button(text="⬆️ ارتقای سربازخانه", callback_data=with_owner("alw:upbk", owner_id))
        b.button(
            text=("🤖 تولید خودکار: روشن ✅" if auto_on else "🤖 تولید خودکار: خاموش ❌"),
            callback_data=with_owner("alw:auto", owner_id),
        )
        b.button(text="🎖️ ارتقا و آموزشِ ارتش", callback_data=with_owner("alw:upgm", owner_id))
    b.button(text="🏥 بیمارستانِ اتحادیه", callback_data=with_owner("alw:hosp", owner_id))
    b.button(text="📖 راهنمای ارتش", callback_data=with_owner("alw:guide", owner_id))
    b.button(text="↩️ بازگشت به اتحادیه", callback_data=with_owner("all:hub", owner_id))
    b.adjust(1)
    return b.as_markup()


def alw_shop_categories_menu(owner_id: int) -> InlineKeyboardMarkup:
    """🏭 دسته‌های تولید — هر دسته جایِ خودش (مثلِ shop_categories_menu)."""
    b = InlineKeyboardBuilder()
    for cat in AM.CATEGORY_ORDER:
        label = AM.CATEGORY_LABELS[cat]
        first_token = label.split(" ", 1)[0] if label else ""
        b.button(text=label, callback_data=with_owner(f"alw:cat:{cat}", owner_id))
    b.button(text="↩️ بازگشت به سربازخانه", callback_data=with_owner("alw:bk", owner_id))
    b.adjust(2)
    return b.as_markup()


def alw_category_units_menu(owner_id: int, cat: str, bk_level: int, counts: dict) -> InlineKeyboardMarkup:
    """نیروهای یک دسته با دکمه‌ی ساختِ مستقل (مثلِ category_units_menu).

    counts: {unit_key: count} برای نمایشِ «داری: …» روی دکمه.
    """
    b = InlineKeyboardBuilder()
    for key in AM.units_in_category(cat):
        u = AM.get_unit(key)
        if int(bk_level) < int(u["unlock_barracks"]):
            b.button(
                text=f"🔒 {u['name']} — سربازخانه {u['unlock_barracks']}",
                callback_data=with_owner("alw:locked", owner_id),
            )
        else:
            cost = AM.squad_cost(key, 1)
            b.button(
                text=f"{u['name']} ×{u['squad']} — {cost:,}$ (داری: {int(counts.get(key, 0)):,})",
                callback_data=with_owner(f"alw:buy:{key}", owner_id),
            )
    b.button(text="↩️ دسته‌ها", callback_data=with_owner("alw:shop", owner_id))
    b.adjust(1)
    return b.as_markup()


def alw_buy_squads_menu(owner_id: int, unit_key: str, presets: list[int], max_squads: int) -> InlineKeyboardMarkup:
    """انتخابِ تعدادِ اسکادران (مثلِ buy_qty_menu) + حداکثرِ ظرفیت + تعدادِ دستی."""
    b = InlineKeyboardBuilder()
    u = AM.get_unit(unit_key)
    for n in presets:
        units = int(n) * int(u["squad"])
        cost = AM.squad_cost(unit_key, n)
        b.button(
            text=f"⚔️ ×{n} اسکادران ({units:,} نیرو) — {cost:,}$",
            callback_data=with_owner(f"alw:buyq:{unit_key}:{n}", owner_id),
        )
    if int(max_squads) > 0 and int(max_squads) not in [int(p) for p in presets]:
        mu = int(max_squads) * int(u["squad"])
        mcost = AM.squad_cost(unit_key, max_squads)
        b.button(
            text=f"🚀 حداکثر: {int(max_squads)} اسکادران ({mu:,} نیرو) — {mcost:,}$",
            callback_data=with_owner(f"alw:buyq:{unit_key}:{int(max_squads)}", owner_id),
        )
    b.button(text="⌨️ واردکردنِ تعدادِ اسکادران", callback_data=with_owner(f"alw:buyn:{unit_key}", owner_id))
    b.button(text="↩️ بازگشت", callback_data=with_owner(f"alw:cat:{u['cat']}", owner_id))
    b.adjust(1)
    return b.as_markup()


def alw_buy_confirm_menu(owner_id: int, unit_key: str, squads: int) -> InlineKeyboardMarkup:
    """تأییدِ نهاییِ تولید (مثلِ buy_confirm_menu)."""
    b = InlineKeyboardBuilder()
    b.button(
        text="✅ تأیید تولید",
        callback_data=with_owner(f"alw:buyok:{unit_key}:{int(squads)}", owner_id),
    )
    b.button(text="✖️ انصراف", callback_data=with_owner(f"alw:buy:{unit_key}", owner_id))
    b.adjust(1)
    return b.as_markup()


def alw_queue_menu(owner_id: int, page: int, total_pages: int, can_manage: bool) -> InlineKeyboardMarkup:
    """صفِ تولید — پیمایشِ واقعی (مثلِ training_queue_menu)؛ صفحه پس از هر کار حفظ می‌شود."""
    b = InlineKeyboardBuilder()
    if can_manage:
        b.button(text="🗑️ لغو صف و بازگشتِ هزینه", callback_data=with_owner(f"alw:qcancelmenu:{page}", owner_id))
    if total_pages > 1:
        b.button(text="◀️ قبلی", callback_data=with_owner(f"alw:queue:{(page - 1) % total_pages}", owner_id))
        b.button(text=f"{page + 1}/{total_pages}", callback_data=with_owner("alw:noop", owner_id))
        b.button(text="بعدی ▶️", callback_data=with_owner(f"alw:queue:{(page + 1) % total_pages}", owner_id))
    b.button(text="🔄 به‌روزرسانی", callback_data=with_owner(f"alw:queue:{page}", owner_id))
    b.button(text="🏭 تولید نیروی جدید", callback_data=with_owner("alw:shop", owner_id))
    b.button(text="↩️ بازگشت به سربازخانه", callback_data=with_owner("alw:bk", owner_id))
    rows = ([1] if can_manage else []) + ([3] if total_pages > 1 else []) + [1, 1, 1]
    b.adjust(*rows)
    return b.as_markup()


def alw_queue_cancel_menu(owner_id: int, items: list[dict], page: int, total_pages: int) -> InlineKeyboardMarkup:
    """حالتِ لغو: هر بچِ صف یک دکمه (مثلِ training_cancel_menu)."""
    b = InlineKeyboardBuilder()
    for q in items:
        b.button(
            text=f"🗑️ {q['name']} — {q['squads']} اسکادران ({q['units']:,} نیرو)",
            callback_data=with_owner(f"alw:qcancel:{q['id']}:{page}", owner_id),
        )
    if total_pages > 1:
        b.button(text="◀️ قبلی", callback_data=with_owner(f"alw:qcancelmenu:{(page - 1) % total_pages}", owner_id))
        b.button(text=f"{page + 1}/{total_pages}", callback_data=with_owner("alw:noop", owner_id))
        b.button(text="بعدی ▶️", callback_data=with_owner(f"alw:qcancelmenu:{(page + 1) % total_pages}", owner_id))
    b.button(text="↩️ بازگشت به صف‌ها", callback_data=with_owner(f"alw:queue:{page}", owner_id))
    rows = [1] * len(list(items or [])) + ([3] if total_pages > 1 else []) + [1]
    b.adjust(*rows)
    return b.as_markup()


def alw_upgrade_menu(owner_id: int, owned: list, treasury: int | None = None) -> InlineKeyboardMarkup:
    """ارتقا و آموزش — منوی مستقل (مثلِ upgrade_units_menu)؛ کمبودِ صندوق = 🔒."""
    b = InlineKeyboardBuilder()
    for k, cnt, lv in owned:
        u = AM.get_unit(k)
        if not u or int(cnt) <= 0:
            continue
        if int(lv) < AM.MAX_UNIT_LEVEL:
            cost = AM.unit_upgrade_cost(k, lv)
            poor = treasury is not None and int(treasury) < cost
            mark = "🔒" if poor else "⬆️"
            b.button(
                text=f"{mark} {u['name']} سطح {lv}→{lv + 1} — {cost:,}$",
                callback_data=with_owner(f"alw:upgu:{k}", owner_id),
            )
        else:
            b.button(
                text=f"✅ {u['name']} — بیشینه (سطح {lv})",
                callback_data=with_owner("alw:noop", owner_id),
            )
    b.button(text="🔄 به‌روزرسانی", callback_data=with_owner("alw:upgm", owner_id))
    b.button(text="↩️ بازگشت به سربازخانه", callback_data=with_owner("alw:bk", owner_id))
    b.adjust(1)
    return b.as_markup()
