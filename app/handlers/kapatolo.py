# -*- coding: utf-8 -*-
"""مرحله ۱۶ — بخشِ «کول‌داونِ دزدی» در عمارتِ کاپولا (۲۰ لِوِل، ۵→۲ دقیقه)."""
from aiogram import F, Router
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select

from app.database.engine import async_session
from app.models.player import Player
from app.models.estate import Estate
from app.data import kapatolo
from app.data.estates import CUPOLA_KEY
from app.utils.ui import ensure_owner, safe_show, safe_edit, with_owner

router = Router()

WORD_KAPATOLO = "کاپولا"
NO_CUPOLA = (
    "🏛️ هنوز عمارتِ کاپولا نساخته‌ای.\n"
    "پس از ساختِ پایگاهِ 🏛️ Palazzo و ساختِ کاپولا، بخشِ «کول‌داونِ دزدی» اینجا فعال می‌شود."
)


async def _has_cupola(session, uid: int) -> bool:
    row = await session.scalar(
        select(Estate).where(Estate.tg_user_id == uid, Estate.role_key == CUPOLA_KEY)
    )
    return row is not None


def _menu(owner_id: int, can_upgrade: bool, cost: int):
    b = InlineKeyboardBuilder()
    if can_upgrade:
        b.button(
            text=f"⬆️ ارتقای کول‌داون ({cost:,}$)",
            callback_data=with_owner("kapatolo:cdup", owner_id),
        )
    b.button(text="↩️ بازگشت به منو", callback_data=with_owner("menu:main", owner_id))
    b.adjust(1)
    return b.as_markup()


def _text(player) -> str:
    # 🆕 مرحله ۳۰ — همه‌ی زمان‌ها به صورتِ «دقیقه و ثانیه» نوشته می‌شوند
    lvl = int(player.kapatolo_cd_level or 0)
    lines = [
        "🕰️ <b>کول‌داونِ دزدی — بخشی از عمارتِ کاپولا</b>",
        "",
        f"📉 کول‌داونِ فعلی: <b>{kapatolo.cooldown_mmss(lvl)}</b>",
        f"🔧 لِوِلِ بخش: <b>{lvl}</b>/{kapatolo.KAPATOLO_COOLDOWN_MAX_LEVEL}",
    ]
    if lvl > 0:
        lines.append(f"⏱️ تا اینجا کم کرده‌ای: <b>{kapatolo.cooldown_saving_mmss(lvl)}</b>")
    lines += [
        "",
        f"با ارتقا، فاصلهٔ بینِ دزدی‌ها از {kapatolo.fmt_mmss(kapatolo.cooldown_seconds(0))} "
        f"تا {kapatolo.fmt_mmss(kapatolo.cooldown_seconds(kapatolo.KAPATOLO_COOLDOWN_MAX_LEVEL))} کم می‌شود.",
    ]
    if lvl >= kapatolo.KAPATOLO_COOLDOWN_MAX_LEVEL:
        lines.append("\n✅ این بخش به بالاترین لِوِل رسیده است.")
    else:
        nxt_s = kapatolo.cooldown_seconds(lvl + 1)
        gain = kapatolo.cooldown_seconds(lvl) - nxt_s
        cost = kapatolo.cooldown_upgrade_cost(lvl)
        lines.append(
            f"\n➡️ لِوِلِ بعد: <b>{kapatolo.fmt_mmss(nxt_s)}</b> "
            f"(−{kapatolo.fmt_mmss(gain)}) — هزینه: <b>{cost:,}$</b>"
        )
    return "\n".join(lines)


async def _render(session, uid: int, owner_id: int):
    player = await session.scalar(select(Player).where(Player.tg_user_id == uid))
    if player is None:
        return "اول در چت خصوصی ربات /start را بزن.", None
    if not await _has_cupola(session, uid):
        return NO_CUPOLA, None
    lvl = int(player.kapatolo_cd_level or 0)
    can = lvl < kapatolo.KAPATOLO_COOLDOWN_MAX_LEVEL
    cost = kapatolo.cooldown_upgrade_cost(lvl) if can else 0
    return _text(player), _menu(owner_id, can, cost)


@router.message(F.text == WORD_KAPATOLO)
async def open_kapatolo(message: Message) -> None:
    async with async_session() as session:
        text, markup = await _render(session, message.from_user.id, message.from_user.id)
    await message.reply(text, reply_markup=markup)


@router.callback_query(F.data.startswith("menu:kapatolo"))
async def open_kapatolo_cb(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    async with async_session() as session:
        text, markup = await _render(session, callback.from_user.id, callback.from_user.id)
    await safe_show(callback.message, text, markup)
    await callback.answer()


@router.callback_query(F.data.startswith("kapatolo:cdup"))
async def upgrade_cd(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    uid = callback.from_user.id
    async with async_session() as session:
        player = await session.scalar(select(Player).where(Player.tg_user_id == uid))
        if player is None:
            await callback.answer("اول /start را بزن.", show_alert=True)
            return
        if not await _has_cupola(session, uid):
            await callback.answer("اول باید کاپولا بسازی.", show_alert=True)
            return
        lvl = int(player.kapatolo_cd_level or 0)
        if lvl >= kapatolo.KAPATOLO_COOLDOWN_MAX_LEVEL:
            await callback.answer("این بخش در بالاترین لِوِل است.", show_alert=True)
            return
        cost = kapatolo.cooldown_upgrade_cost(lvl)
        if int(player.cash or 0) < cost:
            await callback.answer(f"💸 پول کافی نداری. هزینه: {cost:,}$", show_alert=True)
            return
        player.cash = int(player.cash) - cost
        player.kapatolo_cd_level = lvl + 1
        from app.data import leveling as _lv
        _xp_res = {}
        try:   # XP for kapatolo cooldown upgrades
            _xp_res = await _lv.grant_xp(session, player, (20 + 10 * (lvl + 1)) // 2, source="kapatolo_upgrade")
        except Exception:
            pass
        await session.commit()
        text, markup = await _render(session, uid, uid)
    await safe_edit(callback.message, text, markup)
    await callback.answer(
        f"✅ کول‌داون کم شد! اکنون: {kapatolo.cooldown_mmss(lvl + 1)}" + _lv.xp_note(_xp_res)
    )
