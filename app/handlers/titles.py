# -*- coding: utf-8 -*-
"""هندلرهای سیستمِ القاب (مرحله ۱۱).

قابلیت‌ها:
  - /titles و دکمه‌ی منو → خانه‌ی القاب
  - دیدنِ القابِ کسب‌شده و تنظیمِ لقبِ فعال
  - خریدِ اشتراک و نوشتنِ لقبِ دلخواه (FSM با اعتبارسنجی)
"""
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from app.data import titles as T
from app.database.engine import async_session
from app.keyboards.titles_menu import (
    back_kb,
    choose_active_kb,
    subscription_kb,
    titles_home_kb,
)
from app.keyboards.main_menu import BTN_TITLES, WORD_TITLES
from app.services import titles as svc
from app.utils.ui import CANCEL_HINT, ensure_owner, handle_cancel_word, safe_edit

router = Router(name="titles")


class CustomTitleSG(StatesGroup):
    waiting = State()


async def _sub_active(session, uid: int) -> bool:
    from app.models.title import TitleProfile

    pr = await session.get(TitleProfile, uid)
    if pr and pr.subscription_active():
        return True
    # 🆕 مرحله ۲۱ — ادمین‌ها بدونِ اشتراک هم به لقبِ دلخواه دسترسی دارند
    try:
        from app.services import admin_service
        return await admin_service.is_admin(session, uid)
    except Exception:
        return False


def _home_text() -> str:
    return (
        "<b>[لقب] سیستمِ القاب</b>" + '\n' +
        '\n' +
        "القاب آماری وقتی شرطشان را پر کنی، <b>خودکار وارد صف تأیید ادمین</b> می‌شوند." + '\n' +
        "تا تأیید ادمین اصلی، لقب فعال/اعطا نمی‌شود." + '\n' +
        "با اشتراک (طلایی) می‌توانی لقب دلخواه بنویسی."
    )

# --------------------------- ورودی‌ها ---------------------------
@router.message(Command("titles"))
@router.message(F.text == BTN_TITLES)
@router.message(F.text == WORD_TITLES)
async def titles_cmd(message: Message):
    uid = message.from_user.id
    async with async_session() as session:
        active = await _sub_active(session, uid)
    await message.answer(
        _home_text(), reply_markup=titles_home_kb(uid, active), parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("titles:home"))
async def titles_home(callback: CallbackQuery):
    if not await ensure_owner(callback):
        return
    uid = callback.from_user.id
    async with async_session() as session:
        active = await _sub_active(session, uid)
    await safe_edit(callback.message, _home_text(), titles_home_kb(uid, active))
    await callback.answer()



@router.callback_query(F.data.startswith("titles:mine"))
async def titles_mine(callback: CallbackQuery):
    if not await ensure_owner(callback):
        return
    uid = callback.from_user.id
    async with async_session() as session:
        owned = await svc.list_player_titles(session, uid)
        pending_rows = []
        try:
            from app.models.title import TitleApproval
            from sqlalchemy import select as _sel
            pending_rows = list(
                (
                    await session.execute(
                        _sel(TitleApproval)
                        .where(
                            TitleApproval.tg_user_id == uid,
                            TitleApproval.status == "pending",
                        )
                        .order_by(TitleApproval.requested_at.desc())
                        .limit(30)
                    )
                ).scalars().all()
            )
        except Exception:
            pending_rows = []
    out_lines = ["<b>🏷 القابِ تو</b>", ""]
    if owned:
        out_lines.append("<b>✅ کسب‌شده / تاییدشده:</b>")
        for t in owned:
            tag = " (تک)" if t.get("unique") else ""
            rarity = t.get("rarity", "")
            eff = t.get("effect", "")
            eff_txt = ("" if not eff else ("\n   🎁 اثر: " + str(eff)))
            out_lines.append("• <b>" + str(t.get("name", "")) + "</b>" + tag + " — [" + str(rarity) + "]")
            out_lines.append("   <i>" + str(t.get("req", "")) + "</i>" + eff_txt)
    else:
        out_lines.append("هنوز لقب تایید‌شده‌ای نداری.")
    if pending_rows:
        out_lines.append("")
        out_lines.append("<b>⏳ در صف تأیید ادمین:</b>")
        from app.data import titles as _TD
        for r in pending_rows:
            t = _TD.get_title(r.title_key) or {"name": r.title_key}
            out_lines.append("• " + str(t.get("name", r.title_key)) + " <i>(#" + str(r.id) + ")</i>")
        out_lines.append("بعد از تأیید ادمین اصلی، به لیست کسب‌شده اضافه می‌شود.")
    if not owned and not pending_rows:
        out_lines.append("")
        out_lines.append("با فعالیت در بازی وارد صف القاب می‌شوی.")
    else:
        out_lines.append("")
        out_lines.append("ℹ️ فقط القاب تایید‌شده اثر دائمی دارند و قابل انتخاب‌اند.")
    text = "\n".join(out_lines)
    await safe_edit(callback.message, text, back_kb(uid))
    await callback.answer()

@router.callback_query(F.data.startswith("titles:choose"))
async def titles_choose(callback: CallbackQuery):
    if not await ensure_owner(callback):
        return
    uid = callback.from_user.id
    async with async_session() as session:
        owned = await svc.list_player_titles(session, uid)
    if not owned:
        await callback.answer("ابتدا باید یک لقب کسب کنی.", show_alert=True)
        return
    await safe_edit(
        callback.message,
        "یکی از القابِ خود را برای نمایش انتخاب کن:",
        choose_active_kb(uid, owned),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("titles:set:"))
async def titles_set(callback: CallbackQuery):
    if not await ensure_owner(callback):
        return
    uid = callback.from_user.id
    # قالب: titles:set:<key>:<owner_id>
    parts = callback.data.split(":")
    key = parts[2] if len(parts) > 2 else ""
    async with async_session() as session:
        ok, msg = await svc.set_active_title(session, uid, key)
        await session.commit()
    await callback.answer(
        ("لقبِ فعال: " + msg) if ok else msg, show_alert=not ok
    )


# --------------------------- دستوراتِ ادمین ---------------------------
def _is_admin(uid: int) -> bool:
    try:
        from app.config import ADMIN_IDS  # type: ignore

        return uid in set(ADMIN_IDS)
    except Exception:
        return False


@router.message(Command("give_title"))
async def give_title_cmd(message: Message):
    if not _is_admin(message.from_user.id):
        return
    parts = (message.text or "").split()
    if len(parts) < 3:
        await message.answer("قالب: /give_title <user_id> <title_key>")
        return
    try:
        target = int(parts[1])
    except ValueError:
        await message.answer("شناسه‌ی کاربر نامعتبر است.")
        return
    key = parts[2]
    async with async_session() as session:
        ok, msg = await svc.admin_grant_title(session, target, key)
        await session.commit()
    await message.answer(("✅ اعطا شد: " + msg) if ok else ("⚠ " + msg))


@router.message(Command("take_title"))
async def take_title_cmd(message: Message):
    if not _is_admin(message.from_user.id):
        return
    parts = (message.text or "").split()
    if len(parts) < 3:
        await message.answer("قالب: /take_title <user_id> <title_key>")
        return
    try:
        target = int(parts[1])
    except ValueError:
        await message.answer("شناسه‌ی کاربر نامعتبر است.")
        return
    key = parts[2]
    async with async_session() as session:
        ok = await svc.admin_revoke_title(session, target, key)
        await session.commit()
    await message.answer("✅ حذف شد." if ok else "⚠ کاربر این لقب را نداشت.")


@router.callback_query(F.data.startswith("titles:clear"))
async def titles_clear(callback: CallbackQuery):
    if not await ensure_owner(callback):
        return
    uid = callback.from_user.id
    async with async_session() as session:
        await svc.clear_active_title(session, uid)
        await session.commit()
    await callback.answer("لقبِ فعال برداشته شد.")


# --------------------------- اشتراک ---------------------------
@router.callback_query(F.data.startswith("titles:sub:buy"))
async def titles_sub_buy(callback: CallbackQuery):
    if not await ensure_owner(callback):
        return
    uid = callback.from_user.id
    async with async_session() as session:
        ok, msg = await svc.buy_subscription(session, uid)
        await session.commit()
        active = await _sub_active(session, uid)
    await safe_edit(callback.message, msg, subscription_kb(uid, active))
    await callback.answer("✅" if ok else "⚠", show_alert=not ok)


@router.callback_query(F.data.startswith("titles:sub"))
async def titles_sub(callback: CallbackQuery):
    if not await ensure_owner(callback):
        return
    uid = callback.from_user.id
    async with async_session() as session:
        active = await _sub_active(session, uid)
    text = (
        "<b>[اشتراک] اشتراکِ ویژه</b>\n\n"
        f"هزینه: <b>{T.SUBSCRIPTION_COST:,}</b> دلار برای <b>{T.SUBSCRIPTION_DAYS}</b> روز\n"
        "مزیت: نوشتنِ لقبِ سفارشی دلخواه‌ت کنارِ نام.\n\n"
        + ("اشتراکت فعال است." if active else "اشتراکی نداری.")
    )
    await safe_edit(callback.message, text, subscription_kb(uid, active))
    await callback.answer()


# --------------------------- لقبِ دلخواه (FSM) ---------------------------
@router.callback_query(F.data.startswith("titles:custom"))
async def titles_custom_start(callback: CallbackQuery, state: FSMContext):
    if not await ensure_owner(callback):
        return
    uid = callback.from_user.id
    async with async_session() as session:
        if not await _sub_active(session, uid):
            await callback.answer(
                "برای لقبِ دلخواه باید اشتراکِ فعال داشته باشی.", show_alert=True
            )
            return
    await state.set_state(CustomTitleSG.waiting)
    await safe_edit(
        callback.message,
        (
            "لقبِ دلخواهت را بفرست.\n\n"
            f"• طول: {T.MIN_TITLE_LEN} تا {T.MAX_TITLE_LEN} کاراکتر\n"
            "• بدونِ دستوراتِ ربات، لینک و کاراکترِ مخرّب."
        ) + CANCEL_HINT,
        None,
    )
    await callback.answer()


@router.message(CustomTitleSG.waiting)
async def titles_custom_save(message: Message, state: FSMContext):
    if await handle_cancel_word(message, state):
        return
    uid = message.from_user.id
    async with async_session() as session:
        ok, result = await svc.set_custom_title(session, uid, message.text or "")
        await session.commit()
    if not ok:
        await message.answer(f"⚠ {result}\nدوباره امتحان کن:")
        return
    await state.clear()
    await message.answer(
        f"لقبِ دلخواهت ثبت شد: <b>{result}</b>",
        reply_markup=titles_home_kb(uid, True),
        parse_mode="HTML",
    )
