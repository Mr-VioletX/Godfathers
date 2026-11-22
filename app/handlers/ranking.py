# -*- coding: utf-8 -*-
"""هندلرِ رتبه‌بندی و لیدربورد (مرحله ۱۳.۵) + v1.7.2 فیلتر گزینه‌های خاموش."""
from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from app.database.engine import async_session
from app.keyboards.main_menu import BTN_RANKING, WORD_RANKING
from app.keyboards.ranking_menu import ranking_kb
from app.services import ranking as R
from app.utils.ui import ensure_owner, safe_show, split_owner

router = Router()

_MEDALS = {1: "🥇", 2: "🥈", 3: "🥉"}


async def _render(session, viewer_id: int, cat: str, page: int) -> tuple[str, object]:
    from app.services import admin_service as _adm

    vis = await _adm.get_rank_visibility(session)
    enabled_cats = [c for c in R.CATEGORIES if vis.get(c[0], True)]
    enabled_codes = {c[0] for c in enabled_cats} or {"power"}
    if cat not in enabled_codes:
        cat = next(iter(enabled_codes))

    ranking = await R.compute_all(session)
    try:
        await R.assign_dynamic_power_titles(session, ranking)
        await session.commit()
    except Exception:
        await session.rollback()

    entries = ranking.get(cat, [])
    rows, page, total = R.page_slice(entries, page)
    label = R.CATEGORY_LABEL.get(cat, cat)

    lines = [f"🏆 <b>جدولِ رتبه‌بندی — {label}</b>"]
    if not entries:
        lines.append("")
        lines.append("هنوز بازیکنی ثبت نشده است.")
        return chr(10).join(lines), ranking_kb(
            viewer_id, cat, page, total, categories=enabled_cats, extra_visibility=vis
        )

    start_idx = page * R.PAGE_SIZE
    lines.append("")
    from app.utils.table import render_table, table_mode_on
    if await table_mode_on("ranking", session):
        _rows = []
        for i, e in enumerate(rows):
            rank = start_idx + i + 1
            name = e.name + (" 👈" if e.tg_user_id == viewer_id else "")
            _rows.append([str(rank), name, R.format_value(cat, e.value)])
        lines.append(render_table(["#", "نام", R.CATEGORY_LABEL.get(cat, "امتیاز")], _rows))
    else:
        for i, e in enumerate(rows):
            rank = start_idx + i + 1
            badge = _MEDALS.get(rank, f"{rank}.")
            me = "  👈 <b>تو</b>" if e.tg_user_id == viewer_id else ""
            lines.append(f"{badge} {e.name} — {R.format_value(cat, e.value)}{me}")

    mine = R.find_rank(entries, viewer_id)
    lines.append("")
    lines.append("──────────")
    if mine:
        my_rank, my_val = mine
        lines.append(
            f"📍 رتبه‌ی تو: <b>{my_rank}</b> از {len(entries)} ({R.format_value(cat, my_val)})"
        )
    else:
        lines.append("📍 تو هنوز در این جدول جایی نداری.")

    return chr(10).join(lines), ranking_kb(
        viewer_id, cat, page, total, categories=enabled_cats, extra_visibility=vis
    )


async def _open_message(message: Message) -> None:
    async with async_session() as session:
        text, markup = await _render(session, message.from_user.id, "power", 0)
    await message.answer(text, reply_markup=markup)


@router.message(F.text.in_({BTN_RANKING, WORD_RANKING}))
async def summon_ranking(message: Message) -> None:
    await _open_message(message)


@router.callback_query(F.data.startswith("menu:ranking"))
async def open_ranking_cb(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    async with async_session() as session:
        text, markup = await _render(session, callback.from_user.id, "power", 0)
    await safe_show(callback.message, text, markup)
    await callback.answer()


@router.callback_query(F.data.startswith("rank:noop"))
async def rank_noop(callback: CallbackQuery) -> None:
    await callback.answer()


@router.callback_query(F.data.startswith("rank:"))
async def navigate_ranking(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    base, _ = split_owner(callback.data)
    parts = base.split(":")
    cat = parts[1] if len(parts) > 1 else "power"
    try:
        page = int(parts[2]) if len(parts) > 2 else 0
    except ValueError:
        page = 0
    async with async_session() as session:
        text, markup = await _render(session, callback.from_user.id, cat, page)
    await safe_show(callback.message, text, markup)
    await callback.answer()


from app.data import ranks as _RANKS  # noqa: E402
from app.keyboards.ranking_menu import (  # noqa: E402
    global_ladder_kb,
    league_ladder_kb,
    rank_info_kb,
)
from app.services import rank_service as _RS  # noqa: E402
from app.services import war_service as _WS  # noqa: E402

_RANK_MEDALS = {1: "🥇", 2: "🥈", 3: "🥉"}


@router.callback_query(F.data.startswith("rankx:global"))
async def rankx_global(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    async with async_session() as session:
        from app.services import admin_service as _adm

        vis = await _adm.get_rank_visibility(session)
    if not vis.get("global", True):
        await callback.answer("این بخش توسط ادمین خاموش شده است.", show_alert=True)
        return
    base, _ = split_owner(callback.data)
    parts = base.split(":")
    try:
        page = int(parts[2]) if len(parts) > 2 else 0
    except ValueError:
        page = 0
    uid = callback.from_user.id
    async with async_session() as session:
        entries = await _RS.ladder(session)
    rows, page, pages = _RS.page_slice(entries, page, _RS.PAGE_SIZE)
    lines = ["🌍 <b>رتبه‌بندیِ کلی</b> (بر اساسِ کاپ)", ""]
    if not entries:
        lines.append("هنوز کسی کاپی نگرفته است.")
    else:
        start = page * _RS.PAGE_SIZE
        for i, e in enumerate(rows):
            rank = start + i + 1
            badge = _RANK_MEDALS.get(rank, f"{rank}.")
            me = "  👈 <b>تو</b>" if e.uid == uid else ""
            lines.append(
                f"{badge} {e.name} — 🏆{e.cups:,} ({_RANKS.league_name(e.cups)}) | 💥{e.power:,}{me}"
            )
        idx = _RS.index_of(entries, uid)
        lines.append("")
        lines.append("──────────")
        if idx >= 0:
            lines.append(f"📍 رتبه‌ی تو: <b>{idx + 1}</b> از {len(entries)}")
    await safe_show(callback.message, chr(10).join(lines), global_ladder_kb(uid, page, pages))
    await callback.answer()


@router.callback_query(F.data.startswith("rankx:league"))
async def rankx_league(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    async with async_session() as session:
        from app.services import admin_service as _adm

        vis = await _adm.get_rank_visibility(session)
    if not vis.get("league", True):
        await callback.answer("این بخش توسط ادمین خاموش شده است.", show_alert=True)
        return
    base, _ = split_owner(callback.data)
    parts = base.split(":")
    try:
        idx = int(parts[2]) if len(parts) > 2 else 0
    except ValueError:
        idx = 0
    try:
        page = int(parts[3]) if len(parts) > 3 else 0
    except ValueError:
        page = 0
    idx = max(0, min(idx, _RANKS.LEAGUE_COUNT - 1))
    uid = callback.from_user.id
    async with async_session() as session:
        entries = await _RS.ladder(session)
    league_rows = _RS.league_entries(entries, idx)
    rows, page, pages = _RS.page_slice(league_rows, page, _RS.PAGE_SIZE)
    lines = [
        f"🏅 <b>{_RANKS.league_name_by_index(idx)}</b>",
        f"({_RANKS.league_range_text(idx)} کاپ)",
        "",
    ]
    if not league_rows:
        lines.append("هنوز کسی در این رنک نیست.")
    else:
        start = page * _RS.PAGE_SIZE
        for i, e in enumerate(rows):
            rank = start + i + 1
            badge = _RANK_MEDALS.get(rank, f"{rank}.")
            me = "  👈 <b>تو</b>" if e.uid == uid else ""
            lines.append(f"{badge} {e.name} — 🏆{e.cups:,} | 💥{e.power:,}{me}")
    await safe_show(
        callback.message,
        chr(10).join(lines),
        league_ladder_kb(uid, idx, page, pages, _RANKS.LEAGUE_COUNT),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("rankx:power"))
async def rankx_power(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    async with async_session() as session:
        from app.services import admin_service as _adm

        vis = await _adm.get_rank_visibility(session)
    if not vis.get("power_formula", True):
        await callback.answer("این بخش توسط ادمین خاموش شده است.", show_alert=True)
        return
    uid = callback.from_user.id
    async with async_session() as session:
        power = await _WS.compute_combat_power(session, uid)
    lines = [
        _WS.power_formula_help(),
        "",
        f"💥 قدرتِ رزمیِ فعلیِ تو: <b>{power:,}</b>",
    ]
    await safe_show(callback.message, chr(10).join(lines), rank_info_kb(uid))
    await callback.answer()
