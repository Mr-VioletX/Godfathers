# app/handlers/contacts.py
"""سیستمِ «اشخاصِ اضافه‌شده» (Contacts) — مرحله ۱۳.

افزودن: در گروه رویِ پیامِ شخص ریپلای کن و کلمهٔ «افزودن» را بفرست.
دیدن/حذف: از دکمهٔ «👥 اشخاص» در منوی خصوصی.

⚠️ این روتر باید پیش از misc ثبت شود (misc یک هندلرِ catch-all دارد).
"""
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.database.engine import async_session
from app.keyboards.contacts_menu import contacts_menu
from app.models.contact import Contact
from app.models.player import Player
from app.states import ContactStates
from app.utils.ui import ensure_owner, safe_show, split_owner, handle_cancel_word

router = Router()

ADD_WORDS = {"افزودن", "افزودن مخاطب", "افزودن به اشخاص"}
CONTACTS_TITLE = "👥 <b>مخاطبین</b>"


async def _load_contacts(session, owner_id: int):
    return (await session.execute(
        select(Contact).where(Contact.owner_id == owner_id).order_by(Contact.added_at.desc())
    )).scalars().all()



async def _resolve_manual_contact(session, owner_id: int, raw: str):
    raw = (raw or "").strip()
    if not raw:
        return None, "آیدی عددی یا یوزرنیم را بفرست."
    target = None
    if raw.lstrip("+-").isdigit():
        target = await session.scalar(select(Player).where(Player.tg_user_id == int(raw)))
    else:
        uname = raw.lstrip("@").lower()
        target = await session.scalar(select(Player).where(func.lower(Player.username) == uname))
    if target is None:
        return None, "این کاربر در دیتابیس بازی پیدا نشد؛ باید قبلاً /start زده باشد یا یوزرنیمش ثبت شده باشد."
    if int(target.tg_user_id) == int(owner_id):
        return None, "نمی‌توانی خودت را به مخاطبین اضافه کنی."
    return target, None

def _contacts_text(contacts: list) -> str:
    if not contacts:
        return (
            f"{CONTACTS_TITLE}\n\nهنوز کسی را اضافه نکرده‌ای.\n\n"
            "💡 در گروه رویِ پیامِ هرکس ریپلای کن و بنویس: <b>افزودن</b>"
        )
    lines = [CONTACTS_TITLE, ""]
    for i, c in enumerate(contacts, 1):
        uname = f" (@{c.username})" if c.username else ""
        lines.append(f"{i}. <b>{c.display_name or c.contact_id}</b>{uname} — <code>{c.contact_id}</code>")
    lines.append("\n🗑️ برای حذف، رویِ نامِ هرکس بزن.")
    return "\n".join(lines)


# ---------- افزودن با ریپلایِ «افزودن» (در گروه) ----------
@router.message(F.reply_to_message, F.text.in_(ADD_WORDS))
async def add_contact_by_reply(message: Message) -> None:
    replied = message.reply_to_message
    if replied is None or replied.from_user is None:
        return
    target = replied.from_user
    owner_id = message.from_user.id

    if target.is_bot:
        await message.reply("❌ ربات را نمی‌توان اضافه کرد.")
        return
    if target.id == owner_id:
        await message.reply("❌ نمی‌توانی خودت را اضافه کنی.")
        return

    display = target.full_name or target.first_name or (target.username or str(target.id))
    async with async_session() as session:
        existing = (await session.execute(
            select(Contact).where(
                Contact.owner_id == owner_id,
                Contact.contact_id == target.id,
            )
        )).scalar_one_or_none()
        if existing is not None:
            await message.reply(
                f"ℹ️ <b>{existing.display_name or display}</b> را از قبل در لیستِ مخاطبینِ خود داری."
            )
            return
        stmt = (
            sqlite_insert(Contact)
            .values(
                owner_id=owner_id,
                contact_id=target.id,
                username=target.username,
                display_name=display,
            )
            .on_conflict_do_update(
                index_elements=["owner_id", "contact_id"],
                set_={"username": target.username, "display_name": display},
            )
        )
        await session.execute(stmt)
        await session.commit()

    await message.reply(
        f"✅ <b>{display}</b> به مخاطبینِ تو اضافه شد."
    )


# ---------- دیدنِ لیست ----------
@router.callback_query(F.data.startswith("contacts:list") | F.data.startswith("menu:contacts"))
async def show_contacts(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    async with async_session() as session:
        contacts = await _load_contacts(session, callback.from_user.id)
    await safe_show(
        callback.message,
        _contacts_text(contacts),
        contacts_menu(contacts, callback.from_user.id),
    )
    await callback.answer()


# ---------- حذف ----------
@router.callback_query(F.data.startswith("contact:del:"))
async def delete_contact(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    # فرمت: contact:del:<contact_id>:<owner_id>
    parts = callback.data.split(":")
    try:
        contact_id = int(parts[2])
    except (IndexError, ValueError):
        await callback.answer("خطا در شناسه.", show_alert=True)
        return
    async with async_session() as session:
        await session.execute(
            delete(Contact).where(
                Contact.owner_id == callback.from_user.id,
                Contact.contact_id == contact_id,
            )
        )
        await session.commit()
        contacts = await _load_contacts(session, callback.from_user.id)
    await safe_show(
        callback.message,
        _contacts_text(contacts),
        contacts_menu(contacts, callback.from_user.id),
    )
    await callback.answer("🗑️ حذف شد.")


@router.callback_query(F.data.startswith("contact:addmanual"))
async def add_manual_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not await ensure_owner(callback):
        return
    await state.set_state(ContactStates.adding_manual)
    await safe_show(
        callback.message,
        "➕ <b>افزودن دستی مخاطب</b>\n\nآیدی عددی یا یوزرنیم کاربر را بفرست.\nمثال: <code>123456789</code> یا <code>@username</code>\n\nبرای انصراف بنویس: انصراف",
        None,
    )
    await callback.answer()


@router.message(ContactStates.adding_manual)
async def add_manual_receive(message: Message, state: FSMContext) -> None:
    if await handle_cancel_word(message, state):
        return
    owner_id = message.from_user.id
    async with async_session() as session:
        target, err = await _resolve_manual_contact(session, owner_id, message.text or "")
        if err:
            await message.answer(f"❌ {err}\nدوباره بفرست یا بنویس: انصراف")
            return
        display = target.name or (f"@{target.username}" if target.username else str(target.tg_user_id))
        stmt = (
            sqlite_insert(Contact)
            .values(owner_id=owner_id, contact_id=target.tg_user_id, username=target.username, display_name=display)
            .on_conflict_do_update(
                index_elements=["owner_id", "contact_id"],
                set_={"username": target.username, "display_name": display},
            )
        )
        await session.execute(stmt)
        await session.commit()
    await state.clear()
    await message.answer(f"✅ <b>{display}</b> به مخاطبین تو اضافه شد.")
