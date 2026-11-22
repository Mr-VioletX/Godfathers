import re
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.data.economy import MAX_PROF_LEVEL, promote_cost
from app.data.estates import CUPOLA_KEY, SLOTS_PER_ESTATE, get_estate_role
from app.data.professionals import (
    GROUPS,
    get_professional,
    professionals_for_estate,
    professionals_in_group,
)
from app.utils.ui import with_owner

def _fa_name(name) -> str:
    """فقط اسم فارسی — بخش انگلیسی داخل پرانتز حذف می‌شود (مثل «(Underboss)»)."""
    return re.sub(r"\s*\([A-Za-z][^)]*\)\s*$", "", str(name or "")).strip()


def _fa_estate_name(full) -> str:
    """اسم عمارت فقط فارسی: «🏛️ Cupola (کاپولا / شورای مرکزی)» → «🏛️ کاپولا»."""
    s = str(full or "").strip()
    emoji = ""
    m = re.match(r"^(\S+)", s)
    if m:
        emoji = m.group(1)
    paren = re.search(r"\(([^)]*)", s)
    if paren:
        inner = paren.group(1).split("/")[0].strip()
        if inner:
            return (emoji + " " + inner).strip()
    s2 = re.sub(r"[A-Za-z]", "", s).replace(emoji, "", 1).strip(" /-()").strip()
    return (emoji + " " + s2).strip() if emoji else (s2 or s)



def locked_menu() -> InlineKeyboardMarkup:
    """وقتی عمارت قفل است — فقط دکمه‌ی «بازگشت به منو»."""
    builder = InlineKeyboardBuilder()
    builder.button(text="↩️ بازگشت به منو", callback_data="menu:main")
    builder.adjust(2)
    return builder.as_markup()


def estates_hub_menu(estates, buildable_count: int, total_pending: int = 0, overdue_total: int = 0) -> InlineKeyboardMarkup:
    """داشبوردِ امپراتوری: یک دکمه برای هر عمارت (فقط اسم فارسی) + ساختِ جدید."""
    builder = InlineKeyboardBuilder()
    for e in estates:
        role = get_estate_role(e.role_key)
        name = _fa_estate_name(role["name"]) if role else e.role_key
        builder.button(text=name, callback_data=f"estate:view:{e.id}")
    label = "🏗️ ساختِ عمارتِ جدید"
    if buildable_count:
        label += f" ({buildable_count})"
    builder.button(text=label, callback_data="estate:build")
    collect_label = "💰 جمع‌آوریِ همه‌ی درآمدها"
    if total_pending > 0:
        collect_label += f" ({total_pending:,}$)"
    builder.button(text=collect_label, callback_data="estate:collectall")
    payall_label = "💵 پرداختِ دسته‌جمعیِ حقوق‌ها"
    if overdue_total > 0:
        payall_label += f" ({overdue_total:,}$)"
    builder.button(text=payall_label, callback_data="estate:payall")
    builder.button(text="↩️ بازگشت به منو", callback_data="menu:main")
    n = len(estates)
    rows = [2] * (n // 2) + ([1] if n % 2 else [])
    rows += [1, 1, 1, 1]
    builder.adjust(*rows)
    return builder.as_markup()


def build_list_menu(buildable_keys, has_estates: bool) -> InlineKeyboardMarkup:
    """لیستِ عمارت‌های قابلِ ساخت (فقط با پایگاهِ تخصصیِ تیرِ ۴ و اقتدارِ مکس)."""
    builder = InlineKeyboardBuilder()
    for key in buildable_keys:
        role = get_estate_role(key)
        builder.button(
            text=f"🏗️ {_fa_estate_name(role['name'])} — {role['found_cost']:,}$",
            callback_data=f"estate:found:{key}",
        )
    builder.button(text="↩️ بازگشت", callback_data="estate:hub" if has_estates else "menu:main")
    builder.adjust(2)
    return builder.as_markup()


def estate_menu(estate_id, assigned_count, pending_income=0, overdue_count=0, upgrade_cost=None, is_cupola=False, cd_level=None, cd_cost=None, cd_minutes=None):
    """منوی جزئیاتِ یک عمارتِ مشخص (همه‌ی کال‌بک‌ها estate_id دارند)."""
    builder = InlineKeyboardBuilder()
    builder.button(text="👔 استخدام حرفه‌ای", callback_data=f"estate:hire:{estate_id}")
    builder.button(text="📈 ترفیع حرفه‌ای", callback_data=f"estate:promote:{estate_id}")
    builder.button(text=f"💰 جمع‌آوری درآمد ({pending_income:,}$)", callback_data=f"estate:collect:{estate_id}")
    salary_label = "💵 پرداخت حقوق"
    if overdue_count:
        salary_label += f" ({overdue_count:,}$)"
    builder.button(text=salary_label, callback_data=f"estate:salary:{estate_id}")
    if is_cupola:
        if cd_cost:
            builder.button(
                text=f"🕰️ کاهشِ زمانِ دزدی — لِوِل {cd_level} ({cd_cost:,}$)",
                callback_data="menu:kapatolo",
            )
        else:
            builder.button(
                text=f"🕰️ زمانِ دزدی: {cd_minutes:g} دقیقه (مکس ✅)",
                callback_data="menu:kapatolo",
            )
    if upgrade_cost is not None:
        builder.button(text=f"🏗️ ارتقای عمارت ({upgrade_cost:,}$)", callback_data=f"estate:upgrade:{estate_id}")
    builder.button(text="↩️ بازگشت به عمارت‌ها", callback_data="estate:hub")
    rows = [2, 1, 1]
    extra = (1 if is_cupola else 0) + (1 if upgrade_cost is not None else 0)
    if extra == 2:
        rows += [2]
    elif extra == 1:
        rows += [1]
    rows += [1]
    builder.adjust(*rows)
    return builder.as_markup()


def estate_hire_menu(estate_key, estate_id, owned_keys, assigned_count=0):
    """🆕 مرحله ۲۸ — فقط ۴ حرفه‌ی مخصوصِ همین عمارت (بدونِ بخشِ اسلات)."""
    builder = InlineKeyboardBuilder()
    for prof_key, info in professionals_for_estate(estate_key):
        if prof_key in owned_keys:
            builder.button(text=f"{_fa_name(info['name'])} ✅ استخدام‌شده", callback_data="hire_owned")
        else:
            builder.button(
                text=f"👔 {_fa_name(info['name'])} — {info['base_price']:,}$",
                callback_data=f"hire:{prof_key}:{estate_id}",
            )
    builder.button(text="↩️ بازگشت به عمارت", callback_data=f"estate:view:{estate_id}")
    builder.adjust(1)
    return builder.as_markup()


def hire_categories_menu(estate_id) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for group_key, label in GROUPS.items():
        builder.button(text=label, callback_data=f"hirecat:{group_key}:{estate_id}")
    builder.button(text="↩️ بازگشت", callback_data=f"estate:view:{estate_id}")
    builder.adjust(1)
    return builder.as_markup()


def hire_group_menu(group_key, owned_keys, estate_id):
    builder = InlineKeyboardBuilder()
    for prof_key, info in professionals_in_group(group_key):
        if prof_key in owned_keys:
            builder.button(text=f"{_fa_name(info['name'])} ✅ خریده‌شده", callback_data="hire_owned")
        else:
            builder.button(
                text=f"{_fa_name(info['name'])} — {info['base_price']:,}$",
                callback_data=f"hire:{prof_key}:{estate_id}",
            )
    builder.button(text="↩️ بازگشت به گروه‌ها", callback_data=f"estate:hire:{estate_id}")
    builder.adjust(1)
    return builder.as_markup()


def assign_menu(owned, estate_id):
    """چیدن در اسلاتِ یک عمارتِ مشخص. حرفه‌ایِ مشغول در عمارتِ دیگر قفل است."""
    builder = InlineKeyboardBuilder()
    for op in owned:
        info = get_professional(op.prof_key)
        name = _fa_name(info["name"]) if info else op.prof_key
        if op.assigned_estate_id == estate_id:
            builder.button(text=f"➖ {name} (در این عمارت)", callback_data=f"unassign:{op.id}:{estate_id}")
        elif op.assigned_estate_id is None:
            builder.button(text=f"➕ {name}", callback_data=f"assign:{op.id}:{estate_id}")
        else:
            builder.button(text=f"🔒 {name} (عمارتِ دیگر)", callback_data="assign_busy")
    builder.button(text="↩️ بازگشت به عمارت", callback_data=f"estate:view:{estate_id}")
    builder.adjust(2)
    return builder.as_markup()


def promote_menu(active, estate_id):
    builder = InlineKeyboardBuilder()
    for op in active:
        info = get_professional(op.prof_key)
        name = _fa_name(info["name"]) if info else op.prof_key
        if op.level >= MAX_PROF_LEVEL:
            builder.button(text=f"{name} — سطح {op.level} (مکس ✅)", callback_data="promote_max")
        else:
            cost = promote_cost(op.level)
            builder.button(
                text=f"📈 {name} — سطح {op.level}→{op.level + 1} ({cost:,}$)",
                callback_data=f"promote:{op.id}:{estate_id}",
            )
    builder.button(text="↩️ بازگشت به عمارت", callback_data=f"estate:view:{estate_id}")
    builder.adjust(1)
    return builder.as_markup()


def salary_menu(rows, estate_id):
    """rows = لیستِ (op, due, late, strike)."""
    builder = InlineKeyboardBuilder()
    any_due = False
    for op, due, late, strike in rows:
        info = get_professional(op.prof_key)
        name = _fa_name(info["name"]) if info else op.prof_key
        if due > 0:
            any_due = True
            tag = "🚨" if strike else (f"⏰+{late}" if late else "")
            builder.button(text=f"💵 {name} — {due:,}$ {tag}", callback_data=f"paysal:{op.id}:{estate_id}")
        else:
            builder.button(text=f"✅ {name} — تازه تسویه شده", callback_data="sal_ok")
    if any_due:
        total_due = sum(max(0, d) for _op, d, _l, _s in rows)
        builder.button(text=f"💰 پرداختِ همه ({total_due:,}$)", callback_data=f"paysal:all:{estate_id}")
    builder.button(text="↩️ بازگشت به عمارت", callback_data=f"estate:view:{estate_id}")
    builder.adjust(2)
    return builder.as_markup()
