# -*- coding: utf-8 -*-
"""مرحله ۱۸ — اتحادیه‌ها، جنگِ اتحادیه و رتبه‌بندی.

قابلیت‌ها:
  • ساختِ اتحادیه (آیدیِ انگلیسیِ یکتا + نام) و پیوستن با درخواست
  • تأیید/ردِ درخواست‌ها (رئیس/معاون)
  • نقش‌ها: انتصاب/عزلِ معاون (رئیس)
  • خروج از اتحادیه (اعضا) و انحلال (فقط رئیس)
  • رتبه‌بندیِ سراسری و داخلی
  • جنگِ اتحادیه با رأی‌گیریِ داخلی (۵۰٪+ موافق)
  • تنظیماتِ رئیس و ارتقای سقفِ اعضا/قدرتِ نظامی

فقط داخلِ PVِ ربات.
"""
from datetime import datetime, timedelta

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import delete, func, select

from app.data import alliance as A
from app.data import war as W
from app.database.engine import async_session
from app.handlers.profile import get_player
from app.keyboards.alliance_menu import perms_menu  # 🆕 مرحله ۳۰
from app.keyboards.alliance_menu import (
    alliance_back_menu,
    alliance_home_menu,
    alliance_members_menu,
    alliance_military_menu,
    alliance_settings_sec_menu,
    browse_menu,
    confirm_menu,
    rank_menu,
    requests_menu,
    roles_menu,
    settings_menu,
    upgrade_menu,
    war_menu,
    war_targets_menu,
    internal_rank_menu,  # 🆕 v1.7.9.1 — رنکینگ داخلی دو اساسی
)
from app.models.alliance import (
    Alliance,
    AllianceJoinRequest,
    AllianceMember,
    AllianceWar,
    AllianceWarBallot,
    AllianceWarVote,
)
from app.services import alliance_service, war_service, military_service
from app.services import alliance_battle as AB            # 🆕 v1.7.9.1 — نبردِ زنده‌ی اتحادیه
from app.data import alliance_military as AM              # 🆕 v1.7.9.1 — ارتشِ اتحادیه
from app.states import AllianceStates
from app.utils.ui import CANCEL_HINT, ensure_owner, handle_cancel_word, safe_show, split_owner, safe_answer

router = Router(name="alliance")

ALLIANCE_ONLY_BOT = "🛡️ بخشِ اتحادیه فقط داخلِ خودِ ربات در دسترس است."


def _is_private(chat_type: str) -> bool:
    return chat_type == "private"


def _is_officer(role: str | None) -> bool:
    return role in (A.ROLE_LEADER, A.ROLE_DEPUTY)


async def _bump_stats(session, uid: int, **deltas) -> None:
    try:
        from app.models.title import PlayerStats
        from app.services.titles import evaluate_titles
        st = await session.get(PlayerStats, uid)
        if st is None:
            st = PlayerStats(tg_user_id=uid)
            session.add(st)
            await session.flush()
        for k, v in deltas.items():
            if hasattr(st, k):
                setattr(st, k, (getattr(st, k) or 0) + v)
        await evaluate_titles(session, uid)
    except Exception:
        pass


async def _name_of(session, uid: int) -> str:
    p = await get_player(session, uid)
    return p.name if (p and p.name) else str(uid)


# --------------------------- خانه ---------------------------
async def _home_text(session, uid: int, membership) -> str:
    if membership is None:
        return (
            "🛡️ <b>اتحادیه‌ها</b>\n\n"
            "هنوز عضوِ هیچ اتحادیه‌ای نیستی.\n"
            f"• می‌توانی با پرداختِ {A.FOUND_COST:,}$ (از سطحِ {A.FOUND_LEVEL}) اتحادیه بسازی.\n"
            "• یا از فهرست، به یک اتحادیه درخواستِ عضویت بده."
        )
    al = await alliance_service.get_alliance(session, membership.alliance_id)
    if al is None:
        return "❌ اتحادیه‌ات پیدا نشد."
    power = await alliance_service.alliance_power_value(session, al)
    # 🆕 v1.7.9.1 — ارتش و سربازخانه‌ی اتحادیه
    try:
        from app.services import alliance_military_service as AMS
        _bk = await AMS.get_or_create_barracks(session, al.id)
        _bk_level = int(_bk.level or 1)
        _army = await AMS.army_power(session, al.id)
    except Exception:
        _bk_level, _army = 1, 0
    cnt = await alliance_service.member_count(session, al.id)
    cap = A.member_cap_for_level(al.level)
    return "\n".join([
        f"🛡️ <b>{al.name}</b>  (<code>{al.tag}</code>)",
        f"{A.ROLE_LABELS.get(membership.role, membership.role)}",
        "",
        f"💥 قدرتِ اتحادیه: <b>{power:,}</b>",
        f"👥 اعضا: {cnt}/{cap}  |  سطح: {al.level}  |  🏰 سربازخانه: سطح {_bk_level}",
        f"💥 قدرتِ ارتش: {_army:,}  |  💰 صندوق: {al.treasury:,}$",
        f"💳 اشتراکِ عضویت: {al.sub_pct}٪ هر {al.sub_days} روز",
        f"🎁 بونوسِ درآمد: +{A.income_bonus_pct(al.level)}٪",
        f"🔐 آستانه‌ی قدرتِ عضویت: {al.min_power:,}",
    ])


async def _show_home(message: Message, uid: int) -> None:
    async with async_session() as session:
        membership = await alliance_service.get_membership(session, uid)
        text = await _home_text(session, uid, membership)
        # 🆕 مرحله ۳۰ — دسترسی‌هایِ معاون برای ساختنِ دکمه‌ها
        perms = set()
        if membership is not None:
            perms = await alliance_service.get_permissions(
                session, membership.alliance_id, uid
            )
    role = membership.role if membership else None
    await safe_show(message, text, alliance_home_menu(
        uid, has_alliance=membership is not None, role=role, perms=perms,
    ))


@router.message(F.text.in_({"اتحادیه", "🛡️ اتحادیه"}))
async def summon_alliance(message: Message) -> None:
    # 🆕 بخشِ اتحادیه اکنون هم در گروه و هم در ربات فعال است.
    async with async_session() as session:
        player = await get_player(session, message.from_user.id)
    if not player:
        await message.reply("اول در چتِ خصوصیِ ربات /start را بزن.")
        return
    await _show_home(message, message.from_user.id)


@router.callback_query(F.data.startswith("menu:alliance") | F.data.startswith("all:hub"))
async def open_alliance(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    # 🆕 بخشِ اتحادیه اکنون هم در گروه و هم در ربات فعال است.
    await _show_home(callback.message, callback.from_user.id)
    await safe_answer(callback)


# --------------------------- زیرمنوهای خوشه‌ای (v1.8.1.2) ---------------------------
async def _role_perms(session, uid: int):
    membership = await alliance_service.get_membership(session, uid)
    perms = set()
    if membership is not None:
        perms = await alliance_service.get_permissions(session, membership.alliance_id, uid)
    return (membership.role if membership else None), perms


@router.callback_query(F.data.startswith("all:sec:military"))
async def sec_military(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    await safe_show(
        callback.message,
        "⚔️ <b>نظامی</b> — جنگ، سربازخانه و صندوق:",
        alliance_military_menu(callback.from_user.id),
    )
    await safe_answer(callback)


@router.callback_query(F.data.startswith("all:sec:members"))
async def sec_members(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    uid = callback.from_user.id
    async with async_session() as session:
        role, perms = await _role_perms(session, uid)
    await safe_show(
        callback.message,
        "👥 <b>اعضا</b> — رتبه‌بندی داخلی، درخواست‌های عضویت و خروج:",
        alliance_members_menu(uid, role=role, perms=perms),
    )
    await safe_answer(callback)


@router.callback_query(F.data.startswith("all:sec:settings"))
async def sec_settings(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    uid = callback.from_user.id
    async with async_session() as session:
        role, perms = await _role_perms(session, uid)
    await safe_show(
        callback.message,
        "⚙️ <b>تنظیمات اتحادیه</b> — ارتقا، تنظیمات، نقش‌ها و انحلال:",
        alliance_settings_sec_menu(uid, role=role, perms=perms),
    )
    await safe_answer(callback)


# --------------------------- ساخت ---------------------------
@router.callback_query(F.data.startswith("all:create"))
async def create_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not await ensure_owner(callback):
        return
    uid = callback.from_user.id
    async with async_session() as session:
        if await alliance_service.get_membership(session, uid) is not None:
            await safe_answer(callback, "تو قبلاً در یک اتحادیه هستی.", show_alert=True)
            return
        player = await get_player(session, uid)
    if player is None:
        await safe_answer(callback, "اول /start را بزن.", show_alert=True)
        return
    if int(player.level or 1) < A.FOUND_LEVEL:
        await safe_answer(callback, f"🔒 ساختِ اتحادیه از سطحِ {A.FOUND_LEVEL} ممکن است.", show_alert=True)
        return
    if int(player.cash or 0) < A.FOUND_COST:
        await safe_answer(callback, f"پولت کافی نیست. هزینه‌ی تأسیس: {A.FOUND_COST:,}$", show_alert=True)
        return
    await state.set_state(AllianceStates.creating_tag)
    await callback.message.answer(
        "🏗️ آیدیِ انگلیسیِ یکتای اتحادیه را بفرست (۳ تا ۲۰ کاراکتر؛ فقط حروفِ انگلیسی، عدد و زیرخط)." + CANCEL_HINT,
    )
    await safe_answer(callback)


@router.message(AllianceStates.creating_tag)
async def create_tag(message: Message, state: FSMContext) -> None:
    if await handle_cancel_word(message, state):
        return
    raw = (message.text or "").strip()
    if not A.tag_is_valid(raw):
        await message.reply("❌ آیدیِ نامعتبر. فقط A-Z a-z 0-9 و _ ، طول ۳ تا ۲۰.")
        return
    tag = A.normalize_tag(raw)
    async with async_session() as session:
        if await alliance_service.get_alliance_by_tag(session, tag) is not None:
            await message.reply("❌ این آیدی قبلاً گرفته شده. یکی دیگر بفرست.")
            return
    await state.update_data(tag=tag)
    await state.set_state(AllianceStates.creating_name)
    await message.reply(
        "✅ آیدی آزاد است. حالا نامِ نمایشیِ اتحادیه را بفرست (حداکثر ۴۸ کاراکتر)." + CANCEL_HINT,
    )


@router.message(AllianceStates.creating_name)
async def create_name(message: Message, state: FSMContext) -> None:
    if await handle_cancel_word(message, state):
        return
    data = await state.get_data()
    tag = data.get("tag")
    await state.clear()
    name = (message.text or "").strip()[:48]
    if not tag or not name:
        await message.reply("دوباره از منوی اتحادیه تلاش کن.")
        return
    uid = message.from_user.id
    async with async_session() as session:
        if await alliance_service.get_membership(session, uid) is not None:
            await message.reply("تو قبلاً در یک اتحادیه هستی.")
            return
        if await alliance_service.get_alliance_by_tag(session, tag) is not None:
            await message.reply("این آیدی همین حالا گرفته شد. دوباره تلاش کن.")
            return
        player = await get_player(session, uid)
        if player is None or int(player.cash or 0) < A.FOUND_COST:
            await message.reply("پولت کافی نیست.")
            return
        player.cash = int(player.cash or 0) - A.FOUND_COST
        al = Alliance(tag=tag, name=name, leader_id=uid)
        session.add(al)
        await session.flush()
        session.add(AllianceMember(alliance_id=al.id, player_id=uid, role=A.ROLE_LEADER))
        await _bump_stats(session, uid, org_members=1)
        from app.data import leveling as _lv
        _xp_res = {}
        try:   # XP for founding an alliance
            _xp_res = await _lv.grant_xp(session, player, 250, source="alliance_found")
        except Exception:
            pass
        await session.commit()
    await message.reply(f"🎉 اتحادیه‌ی <b>{name}</b> (<code>{tag}</code>) تأسیس شد! تو رئیسِ آن هستی." + _lv.xp_note(_xp_res))
    await _show_home(message, uid)


# --------------------------- پیوستن ---------------------------
@router.callback_query(F.data.startswith("all:browse:"))
async def browse(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    base, _ = split_owner(callback.data)
    try:
        page = int(base.split(":")[2])
    except (IndexError, ValueError):
        page = 0
    uid = callback.from_user.id
    async with async_session() as session:
        if await alliance_service.get_membership(session, uid) is not None:
            await safe_answer(callback, "تو قبلاً در یک اتحادیه هستی.", show_alert=True)
            return
        rows = await alliance_service.compute_all_alliances(session)
    per = 8
    total = max(1, (len(rows) + per - 1) // per)
    page = max(0, min(page, total - 1))
    chunk = rows[page * per:(page + 1) * per]
    if not rows:
        text = "🔍 هنوز هیچ اتحادیه‌ای ساخته نشده. اولین نفر باش!"
    else:
        lines = ["🔍 <b>اتحادیه‌های موجود</b>\n"]
        for al, power, cnt in chunk:
            cap = A.member_cap_for_level(al.level)
            lines.append(f"🛡️ <b>{al.name}</b> (<code>{al.tag}</code>) — 💥{power:,} — 👥{cnt}/{cap} — 💳{al.sub_pct}٪")
        text = "\n".join(lines)
    await safe_show(callback.message, text, browse_menu(chunk, uid, page, total))
    await safe_answer(callback)


@router.callback_query(F.data.startswith("all:reqjoin:"))
async def request_join(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    base, _ = split_owner(callback.data)
    alliance_id = int(base.split(":")[2])
    uid = callback.from_user.id
    async with async_session() as session:
        if await alliance_service.get_membership(session, uid) is not None:
            await safe_answer(callback, "تو قبلاً در یک اتحادیه هستی.", show_alert=True)
            return
        al = await alliance_service.get_alliance(session, alliance_id)
        if al is None:
            await safe_answer(callback, "این اتحادیه پیدا نشد.", show_alert=True)
            return
        cnt = await alliance_service.member_count(session, al.id)
        if cnt >= A.member_cap_for_level(al.level):
            await safe_answer(callback, "ظرفیتِ این اتحادیه پر است.", show_alert=True)
            return
        if al.min_power > 0:
            power = await war_service.compute_combat_power(session, uid)
            if power < al.min_power:
                await safe_answer(callback, 
                    f"🔐 قدرتت ({power:,}) کمتر از آستانه‌ی عضویت ({al.min_power:,}) است.",
                    show_alert=True,
                )
                return
        dup = (await session.execute(
            select(AllianceJoinRequest).where(
                AllianceJoinRequest.alliance_id == alliance_id,
                AllianceJoinRequest.player_id == uid,
                AllianceJoinRequest.status == "pending",
            )
        )).scalar_one_or_none()
        if dup is not None:
            await safe_answer(callback, "قبلاً درخواست داده‌ای؛ منتظرِ تأیید بمان.", show_alert=True)
            return
        session.add(AllianceJoinRequest(alliance_id=alliance_id, player_id=uid))
        await session.commit()
    await safe_answer(callback, "✅ درخواستِ عضویت ثبت شد. منتظرِ تأییدِ رئیس/معاون بمان.", show_alert=True)


# --------------------------- درخواست‌ها ---------------------------
@router.callback_query(F.data.startswith("all:requests"))
async def list_requests(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    uid = callback.from_user.id
    async with async_session() as session:
        membership = await alliance_service.get_membership(session, uid)
        if not await alliance_service.has_permission(session, membership, A.PERM_REQUESTS):
            await safe_answer(callback, "🔒 رئیس باید دسترسیِ «درخواست‌های عضویت» را به تو بدهد.", show_alert=True)
            return
        reqs = (await session.execute(
            select(AllianceJoinRequest).where(
                AllianceJoinRequest.alliance_id == membership.alliance_id,
                AllianceJoinRequest.status == "pending",
            ).order_by(AllianceJoinRequest.created_at)
        )).scalars().all()
        items = []
        for r in reqs:
            nm = await _name_of(session, r.player_id)
            pw = await war_service.compute_combat_power(session, r.player_id)
            items.append((r.player_id, nm, pw))
    if not items:
        await safe_show(callback.message, "📥 درخواستِ در‌انتظاری نداری.", alliance_back_menu(uid))
        await safe_answer(callback)
        return
    lines = ["📥 <b>درخواست‌های عضویت</b>\n"]
    for pid, nm, pw in items:
        lines.append(f"• {nm} — 💥{pw:,}")
    await safe_show(callback.message, "\n".join(lines), requests_menu(items, uid))
    await safe_answer(callback)


@router.callback_query(F.data.startswith("all:acc:"))
async def accept_request(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    base, _ = split_owner(callback.data)
    pid = int(base.split(":")[2])
    uid = callback.from_user.id
    async with async_session() as session:
        membership = await alliance_service.get_membership(session, uid)
        if not await alliance_service.has_permission(session, membership, A.PERM_WAR):
            await safe_answer(callback, "اجازه نداری.", show_alert=True)
            return
        al = await alliance_service.get_alliance(session, membership.alliance_id)
        req = (await session.execute(
            select(AllianceJoinRequest).where(
                AllianceJoinRequest.alliance_id == membership.alliance_id,
                AllianceJoinRequest.player_id == pid,
                AllianceJoinRequest.status == "pending",
            )
        )).scalar_one_or_none()
        if req is None:
            await safe_answer(callback, "این درخواست دیگر معتبر نیست.", show_alert=True)
            return
        if await alliance_service.get_membership(session, pid) is not None:
            req.status = "rejected"
            await session.commit()
            await safe_answer(callback, "این کاربر حالا در اتحادیه‌ی دیگری است.", show_alert=True)
            return
        if await alliance_service.member_count(session, al.id) >= A.member_cap_for_level(al.level):
            await safe_answer(callback, "ظرفیتِ اتحادیه پر است.", show_alert=True)
            return
        req.status = "accepted"
        session.add(AllianceMember(alliance_id=al.id, player_id=pid, role=A.ROLE_MEMBER))
        await _bump_stats(session, uid, org_members=1)
        await session.commit()
        nm = await _name_of(session, pid)
    await safe_show(callback.message, f"✅ <b>{nm}</b> به اتحادیه پیوست.", alliance_back_menu(uid))
    await safe_answer(callback, "پذیرفته شد.")


@router.callback_query(F.data.startswith("all:rej:"))
async def reject_request(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    base, _ = split_owner(callback.data)
    pid = int(base.split(":")[2])
    uid = callback.from_user.id
    async with async_session() as session:
        membership = await alliance_service.get_membership(session, uid)
        if not await alliance_service.has_permission(session, membership, A.PERM_WAR):
            await safe_answer(callback, "اجازه نداری.", show_alert=True)
            return
        req = (await session.execute(
            select(AllianceJoinRequest).where(
                AllianceJoinRequest.alliance_id == membership.alliance_id,
                AllianceJoinRequest.player_id == pid,
                AllianceJoinRequest.status == "pending",
            )
        )).scalar_one_or_none()
        if req is not None:
            req.status = "rejected"
            await session.commit()
    await safe_show(callback.message, "❌ درخواست رد شد.", alliance_back_menu(uid))
    await safe_answer(callback)


# --------------------------- نقش‌ها ---------------------------
@router.callback_query(F.data.startswith("all:roles"))
async def roles_home(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    uid = callback.from_user.id
    async with async_session() as session:
        membership = await alliance_service.get_membership(session, uid)
        if membership is None or membership.role != A.ROLE_LEADER:
            await safe_answer(callback, "فقط رئیس می‌تواند نقش‌ها را مدیریت کند.", show_alert=True)
            return
        members = (await session.execute(
            select(AllianceMember).where(AllianceMember.alliance_id == membership.alliance_id)
        )).scalars().all()
        items = []
        for m in members:
            nm = await _name_of(session, m.player_id)
            items.append((m.player_id, nm, m.role))
    lines = [
        "🎖️ <b>نقش‌ها و دسترسی‌ها</b>\n",
        "با دکمه‌ی 🔑 می‌توانی برای هر معاون جداگانه "
        "تعیین کنی که به کدام بخش‌های اتحادیه دسترسی داشته باشد.\n",
    ]
    for pid, nm, role in items:
        lines.append(f"• {A.ROLE_LABELS.get(role, role)} — {nm}")
    await safe_show(callback.message, "\n".join(lines), roles_menu(items, uid))
    await safe_answer(callback)


@router.callback_query(F.data.startswith("all:promote:"))
async def promote_member(callback: CallbackQuery) -> None:
    await _set_role(callback, A.ROLE_DEPUTY)


@router.callback_query(F.data.startswith("all:demote:"))
async def demote_member(callback: CallbackQuery) -> None:
    await _set_role(callback, A.ROLE_MEMBER)


async def _set_role(callback: CallbackQuery, new_role: str) -> None:
    if not await ensure_owner(callback):
        return
    base, _ = split_owner(callback.data)
    pid = int(base.split(":")[2])
    uid = callback.from_user.id
    async with async_session() as session:
        leader = await alliance_service.get_membership(session, uid)
        if leader is None or leader.role != A.ROLE_LEADER:
            await safe_answer(callback, "فقط رئیس می‌تواند نقش تغییر دهد.", show_alert=True)
            return
        target = await alliance_service.get_membership(session, pid)
        if target is None or target.alliance_id != leader.alliance_id:
            await safe_answer(callback, "این عضو در اتحادیه‌ی تو نیست.", show_alert=True)
            return
        if target.role == A.ROLE_LEADER:
            await safe_answer(callback, "نمی‌توانی نقشِ رئیس را تغییر دهی.", show_alert=True)
            return
        target.role = new_role
        # 🆕 مرحله ۳۰ — با معاون‌شدن، دسترسی‌های پیش‌فرض؛ با عزل، لغوی همه
        if new_role == A.ROLE_DEPUTY:
            await alliance_service.grant_default_permissions(
                session, target.alliance_id, pid
            )
        else:
            await alliance_service.clear_permissions(session, target.alliance_id, pid)
        await session.commit()
    await safe_answer(callback, "✅ نقش به‌روز شد.")
    await roles_home(callback)


# --------------------------- خروج ---------------------------
@router.callback_query(F.data.startswith("all:leaveq"))
async def leave_confirm(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    uid = callback.from_user.id
    async with async_session() as session:
        membership = await alliance_service.get_membership(session, uid)
    if membership is None:
        await safe_answer(callback, "در هیچ اتحادیه‌ای نیستی.", show_alert=True)
        return
    if membership.role == A.ROLE_LEADER:
        await safe_answer(callback, "رئیس نمی‌تواند خارج شود؛ اول اتحادیه را منحل کن.", show_alert=True)
        return
    await safe_show(callback.message, "🚪 مطمئنی می‌خواهی از اتحادیه خارج شوی؟", confirm_menu(uid, "leave"))
    await safe_answer(callback)


@router.callback_query(F.data.startswith("all:leavego"))
async def leave_go(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    uid = callback.from_user.id
    async with async_session() as session:
        membership = await alliance_service.get_membership(session, uid)
        if membership is None:
            await safe_answer(callback, "در هیچ اتحادیه‌ای نیستی.", show_alert=True)
            return
        if membership.role == A.ROLE_LEADER:
            await safe_answer(callback, "رئیس باید اتحادیه را منحل کند.", show_alert=True)
            return
        await session.execute(delete(AllianceMember).where(AllianceMember.player_id == uid))
        await session.commit()
    await safe_answer(callback, "از اتحادیه خارج شدی.")
    await _show_home(callback.message, uid)


# --------------------------- انحلال ---------------------------
@router.callback_query(F.data.startswith("all:disq"))
async def disband_confirm(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    uid = callback.from_user.id
    async with async_session() as session:
        membership = await alliance_service.get_membership(session, uid)
    if membership is None or membership.role != A.ROLE_LEADER:
        await safe_answer(callback, "فقط رئیس می‌تواند اتحادیه را منحل کند.", show_alert=True)
        return
    await safe_show(callback.message, "💥 این کار غیرقابل‌بازگشت است! اتحادیه و همه‌ی عضویت‌ها حذف می‌شوند. مطمئنی؟", confirm_menu(uid, "disband"))
    await safe_answer(callback)


@router.callback_query(F.data.startswith("all:disgo"))
async def disband_go(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    uid = callback.from_user.id
    async with async_session() as session:
        membership = await alliance_service.get_membership(session, uid)
        if membership is None or membership.role != A.ROLE_LEADER:
            await safe_answer(callback, "فقط رئیس می‌تواند منحل کند.", show_alert=True)
            return
        aid = membership.alliance_id
        vote_ids = (await session.execute(
            select(AllianceWarVote.id).where(
                (AllianceWarVote.alliance_id == aid) | (AllianceWarVote.target_id == aid)
            )
        )).scalars().all()
        if vote_ids:
            await session.execute(delete(AllianceWarBallot).where(AllianceWarBallot.vote_id.in_(vote_ids)))
        await session.execute(delete(AllianceWarVote).where(
            (AllianceWarVote.alliance_id == aid) | (AllianceWarVote.target_id == aid)
        ))
        await session.execute(delete(AllianceJoinRequest).where(AllianceJoinRequest.alliance_id == aid))
        await session.execute(delete(AllianceMember).where(AllianceMember.alliance_id == aid))
        al = await alliance_service.get_alliance(session, aid)
        if al is not None:
            await session.delete(al)
        await session.commit()
    await safe_answer(callback, "💥 اتحادیه منحل شد.")
    await _show_home(callback.message, uid)


# --------------------------- رتبه‌بندیِ سراسری ---------------------------
@router.callback_query(F.data.startswith("all:rank:"))
async def global_rank(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    base, _ = split_owner(callback.data)
    try:
        page = int(base.split(":")[2])
    except (IndexError, ValueError):
        page = 0
    uid = callback.from_user.id
    async with async_session() as session:
        rows = await alliance_service.compute_all_alliances(session)
        membership = await alliance_service.get_membership(session, uid)
    per = 10
    total = max(1, (len(rows) + per - 1) // per)
    page = max(0, min(page, total - 1))
    chunk = rows[page * per:(page + 1) * per]
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    if not rows:
        text = "🏆 هنوز اتحادیه‌ای ثبت نشده."
    else:
        lines = ["🏆 <b>رتبه‌بندیِ اتحادیه‌ها</b>\n"]
        for i, (al, power, cnt) in enumerate(chunk):
            rank = page * per + i + 1
            tag = medals.get(rank, f"{rank}.")
            lines.append(f"{tag} <b>{al.name}</b> (<code>{al.tag}</code>) — 💥{power:,} — 👥{cnt}")
        if membership is not None:
            for idx, (al, power, cnt) in enumerate(rows):
                if al.id == membership.alliance_id:
                    lines.append(f"\n📍 رتبه‌ی اتحادیه‌ی تو: {idx + 1} از {len(rows)}")
                    break
        text = "\n".join(lines)
    await safe_show(callback.message, text, rank_menu(uid, page, total))
    await safe_answer(callback)


# --------------------------- رتبه‌بندیِ داخلی ---------------------------
@router.callback_query(F.data.startswith("all:internal"))
async def internal_rank(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    base, _ = split_owner(callback.data)
    parts = base.split(":")
    # 🆕 v1.7.9.1 — رنکینگ داخلی بر دو اساس: قدرت / امتیاز مشارکت
    basis = parts[2] if len(parts) >= 3 and parts[2] in ("power", "contrib") else "power"
    uid = callback.from_user.id
    async with async_session() as session:
        membership = await alliance_service.get_membership(session, uid)
        if membership is None:
            await safe_answer(callback, "عضوِ هیچ اتحادیه‌ای نیستی.", show_alert=True)
            return
        rows = await alliance_service.internal_ranking(session, membership.alliance_id)
        data = []
        for m, power in rows:
            nm = await _name_of(session, m.player_id)
            data.append((m, nm, power))
        if basis == "contrib":
            data.sort(key=lambda t: int(t[0].contributed or 0), reverse=True)
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    if basis == "contrib":
        lines = ["👥 <b>رتبه‌بندیِ داخلیِ اعضا — بر اساسِ مشارکت 🎖️</b>\n"]
    else:
        lines = ["👥 <b>رتبه‌بندیِ داخلیِ اعضا — بر اساسِ قدرت 💥</b>\n"]
    for i, (m, nm, power) in enumerate(data):
        tag = medals.get(i + 1, f"{i + 1}.")
        val = f"🎖️{int(m.contributed or 0):,}$" if basis == "contrib" else f"💥{power:,}"
        lines.append(f"{tag} {nm} — {A.ROLE_LABELS.get(m.role, m.role)} — {val}")
    await safe_show(callback.message, "\n".join(lines), internal_rank_menu(uid, basis))
    await safe_answer(callback)


# --------------------------- تنظیمات ---------------------------
async def _leader_alliance(session, uid: int, perm: str | None = A.PERM_SETTINGS):
    """🆕 مرحله ۳۰ — رئیس، یا معاونی که این دسترسی را دارد."""
    m = await alliance_service.get_membership(session, uid)
    if m is None:
        return None, None
    if m.role != A.ROLE_LEADER and (
        perm is None or not await alliance_service.has_permission(session, m, perm)
    ):
        return None, None
    return m, await alliance_service.get_alliance(session, m.alliance_id)


@router.callback_query(F.data.startswith("all:settings"))
async def settings_home(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    uid = callback.from_user.id
    async with async_session() as session:
        _m, al = await _leader_alliance(session, uid)
    if al is None:
        await safe_answer(callback, "🔒 فقط رئیس، یا معاونِ دارای دسترسیِ تنظیمات.", show_alert=True)
        return
    text = (
        "⚙️ <b>تنظیماتِ اتحادیه</b>\n\n"
        f"💳 اشتراک: {al.sub_pct}٪ هر {al.sub_days} روز\n"
        f"🔐 آستانه‌ی قدرتِ عضویت: {al.min_power:,}\n"
        f"🔤 آیدی: <code>{al.tag}</code> | نام: {al.name}"
    )
    await safe_show(callback.message, text, settings_menu(uid, al))
    await safe_answer(callback)


@router.callback_query(F.data.startswith("all:set_sub"))
async def set_sub_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not await ensure_owner(callback):
        return
    await state.set_state(AllianceStates.setting_sub)
    await callback.message.answer(
        f"💳 درصدِ اشتراک ({A.SUB_PCT_MIN}تا{A.SUB_PCT_MAX}) و اختیاری دوره‌ی روز ({A.SUB_DAYS_MIN}تا{A.SUB_DAYS_MAX}) را بفرست.\nمثال: <code>10</code> یا <code>10 3</code>" + CANCEL_HINT,
    )
    await safe_answer(callback)


@router.message(AllianceStates.setting_sub)
async def set_sub_recv(message: Message, state: FSMContext) -> None:
    if await handle_cancel_word(message, state):
        return
    await state.clear()
    parts = (message.text or "").replace("٪", " ").split()
    nums = []
    for p in parts:
        try:
            nums.append(int(p))
        except ValueError:
            pass
    if not nums:
        await message.reply("عددِ معتبری بفرست.")
        return
    uid = message.from_user.id
    async with async_session() as session:
        _m, al = await _leader_alliance(session, uid)
        if al is None:
            await message.reply("فقط رئیس دسترسی دارد.")
            return
        al.sub_pct = A.clamp_sub_pct(nums[0])
        if len(nums) > 1:
            al.sub_days = A.clamp_sub_days(nums[1])
        await session.commit()
        pct, days = al.sub_pct, al.sub_days
    await message.reply(f"✅ اشتراکِ عضویت به {pct}٪ هر {days} روز تنظیم ش��.")
    await _show_home(message, uid)


@router.callback_query(F.data.startswith("all:set_power"))
async def set_power_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not await ensure_owner(callback):
        return
    await state.set_state(AllianceStates.setting_power)
    await callback.message.answer(
        "🔐 آستانه‌ی حداقلِ قدرتِ رزمی برای عضویت را بفرست (۰ یعنی بدونِ محدودیت)." + CANCEL_HINT,
    )
    await safe_answer(callback)


@router.message(AllianceStates.setting_power)
async def set_power_recv(message: Message, state: FSMContext) -> None:
    if await handle_cancel_word(message, state):
        return
    await state.clear()
    try:
        val = max(0, int((message.text or "").strip()))
    except ValueError:
        await message.reply("عددِ معتبری بفرست.")
        return
    uid = message.from_user.id
    async with async_session() as session:
        _m, al = await _leader_alliance(session, uid)
        if al is None:
            await message.reply("فقط رئیس دسترسی دارد.")
            return
        al.min_power = val
        await session.commit()
    await message.reply(f"✅ آستانه‌ی قدرتِ عضویت به {val:,} تنظیم شد.")
    await _show_home(message, uid)


@router.callback_query(F.data.startswith("all:set_name"))
async def set_name_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not await ensure_owner(callback):
        return
    await state.set_state(AllianceStates.setting_name)
    await callback.message.answer(
        "✏️ نامِ جدیدِ اتحادیه را بفرست (حداکثر ۴۸ کاراکتر)." + CANCEL_HINT,
    )
    await safe_answer(callback)


@router.message(AllianceStates.setting_name)
async def set_name_recv(message: Message, state: FSMContext) -> None:
    if await handle_cancel_word(message, state):
        return
    await state.clear()
    name = (message.text or "").strip()[:48]
    if not name:
        await message.reply("نامِ معتبری بفرست.")
        return
    uid = message.from_user.id
    async with async_session() as session:
        _m, al = await _leader_alliance(session, uid)
        if al is None:
            await message.reply("فقط رئیس دسترسی دارد.")
            return
        al.name = name
        await session.commit()
    await message.reply(f"✅ نامِ اتحادیه به <b>{name}</b> تغییر کرد.")
    await _show_home(message, uid)


@router.callback_query(F.data.startswith("all:set_tag"))
async def set_tag_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not await ensure_owner(callback):
        return
    await state.set_state(AllianceStates.setting_tag)
    await callback.message.answer(
        "🔤 آیدیِ جدیدِ انگلیسی را بفرست (۳ تا ۲۰ کاراکتر؛ حروف، عدد، زیرخط)." + CANCEL_HINT,
    )
    await safe_answer(callback)


@router.message(AllianceStates.setting_tag)
async def set_tag_recv(message: Message, state: FSMContext) -> None:
    if await handle_cancel_word(message, state):
        return
    await state.clear()
    raw = (message.text or "").strip()
    if not A.tag_is_valid(raw):
        await message.reply("❌ آیدیِ نامعتبر.")
        return
    tag = A.normalize_tag(raw)
    uid = message.from_user.id
    async with async_session() as session:
        _m, al = await _leader_alliance(session, uid)
        if al is None:
            await message.reply("فقط رئیس دسترسی دارد.")
            return
        other = await alliance_service.get_alliance_by_tag(session, tag)
        if other is not None and other.id != al.id:
            await message.reply("❌ این آیدی قبلاً گرفته شده.")
            return
        al.tag = tag
        await session.commit()
    await message.reply(f"✅ آیدیِ اتحادیه به <code>{tag}</code> تغییر کرد.")
    await _show_home(message, uid)


# --------------------------- ارتقا ---------------------------
@router.callback_query(F.data.startswith("all:upgrade"))
async def upgrade_home(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    uid = callback.from_user.id
    async with async_session() as session:
        membership = await alliance_service.get_membership(session, uid)
        if not await alliance_service.has_permission(session, membership, A.PERM_UPGRADE):
            await safe_answer(callback, "🔒 رئیس باید دسترسیِ «ارتقای اتحادیه» را به تو بدهد.", show_alert=True)
            return
        al = await alliance_service.get_alliance(session, membership.alliance_id)
    text = (
        "⬆️ <b>ارتقای اتحادیه</b>\n\n"
        f"💰 صندوق: {al.treasury:,}$\n"
        f"👥 سقفِ فعلی: {A.member_cap_for_level(al.level)} (سطح {al.level})\n\n"
        "هزینه‌ها از صندوقِ اتحادیه کسر می‌شود (۳۰× بخشِ عادی).\n"
        "⚔️ «ارتقای قدرتِ نظامی» حذف شد — ارتش را از «🏰 سربازخانه‌ی اتحادیه» بساز."
    )
    await safe_show(callback.message, text, upgrade_menu(uid, al))
    await safe_answer(callback)


@router.callback_query(F.data.startswith("all:up_cap"))
async def upgrade_cap(callback: CallbackQuery) -> None:
    await _do_upgrade(callback, "cap")


@router.callback_query(F.data.startswith("all:up_mil"))
async def upgrade_mil(callback: CallbackQuery) -> None:
    await _do_upgrade(callback, "mil")


async def _do_upgrade(callback: CallbackQuery, kind: str) -> None:
    if not await ensure_owner(callback):
        return
    uid = callback.from_user.id
    async with async_session() as session:
        membership = await alliance_service.get_membership(session, uid)
        if not await alliance_service.has_permission(session, membership, A.PERM_UPGRADE):
            await safe_answer(callback, "🔒 رئیس باید دسترسیِ «ارتقای اتحادیه» را به تو بدهد.", show_alert=True)
            return
        al = await alliance_service.get_alliance(session, membership.alliance_id)
        if kind == "cap":
            if A.cap_is_maxed(al.level):
                await safe_answer(callback, "سقفِ اعضا در بیشینه است.", show_alert=True)
                return
            cost = AM.member_cap_upgrade_cost(al.level)  # 🆕 v1.7.9.1 — ارتقاها ۳۰× بخشِ عادی
            if int(al.treasury or 0) < cost:
                await safe_answer(callback, f"صندوق کافی نیست. هزینه: {cost:,}$", show_alert=True)
                return
            al.treasury = int(al.treasury or 0) - cost
            al.level += 1
            msg = f"✅ سقفِ اعضا به {A.member_cap_for_level(al.level)} رسید (سطح {al.level})."
        else:
            # 🆕 v1.7.9.1 — «ارتقای قدرتِ نظامی» حذف شد؛ ارتش در سربازخانه‌ی اتحادیه است
            await safe_answer(callback, "⚔️ این بخش حذف شد — ارتش را از «🏰 سربازخانه‌ی اتحادیه» بساز و ارتقا بده.", show_alert=True)
            return
        from app.data import leveling as _lv
        _xp_res = {}
        try:   # XP for the officer performing an alliance upgrade
            player = await get_player(session, uid)
            if player is not None:
                _xp_res = await _lv.grant_xp(session, player, min(150, max(10, cost // 6000)), source="alliance_upgrade")
        except Exception:
            pass
        await session.commit()
    await safe_answer(callback, msg + _lv.xp_note(_xp_res), show_alert=True)
    await upgrade_home(callback)


# --------------------------- جنگِ اتحادیه ---------------------------
async def _active_vote(session, alliance_id: int):
    return (await session.execute(
        select(AllianceWarVote).where(
            AllianceWarVote.alliance_id == alliance_id,
            AllianceWarVote.status == "voting",
        ).order_by(AllianceWarVote.id.desc())
    )).scalars().first()


async def _ballot_counts(session, vote_id: int) -> tuple[int, int]:
    yes = int((await session.execute(
        select(func.count()).select_from(AllianceWarBallot).where(
            AllianceWarBallot.vote_id == vote_id, AllianceWarBallot.choice == 1
        )
    )).scalar() or 0)
    no = int((await session.execute(
        select(func.count()).select_from(AllianceWarBallot).where(
            AllianceWarBallot.vote_id == vote_id, AllianceWarBallot.choice == 0
        )
    )).scalar() or 0)
    return yes, no

async def _apply_member_war_losses(session, attacker_id: int, defender_id: int, attacker_won: bool,
                                   att_power: int = 0, def_power: int = 0) -> tuple[int, int]:
    """🆕 تلفاتِ منطقیِ اعضای دو اتحاد بر اساسِ نسبتِ قدرتِ اتحادیه‌ها (نه درصدِ ثابتِ ارتش).
    خروجی: تعداد واحدهای از دست‌رفتهٔ کلِ مهاجم/مدافع."""
    att_total = def_total = 0
    for uid in await alliance_service.member_ids(session, attacker_id):
        losses = await military_service.apply_scaled_losses(
            session, uid, att_power, def_power,
            won=attacker_won, intensity=W.CASUALTY_INTENSITY["alliance_attacker"],
        )
        att_total += sum(int(v) for v in losses.values())
    for uid in await alliance_service.member_ids(session, defender_id):
        losses = await military_service.apply_scaled_losses(
            session, uid, def_power, att_power,
            won=not attacker_won, intensity=W.CASUALTY_INTENSITY["alliance_defender"],
        )
        def_total += sum(int(v) for v in losses.values())
    return att_total, def_total


async def _resolve_war(session, vote) -> str:
    attacker = await alliance_service.get_alliance(session, vote.alliance_id)
    defender = await alliance_service.get_alliance(session, vote.target_id)
    if attacker is None or defender is None:
        vote.status = "failed"
        return "❌ یکی از اتحادیه‌ها دیگر وجود ندارد؛ جنگ لغو شد."
    att_power = await alliance_service.alliance_power_value(session, attacker)
    def_power = await alliance_service.alliance_power_value(session, defender)
    won = A.roll_alliance_battle(att_power, def_power)
    att_lost_units, def_lost_units = await _apply_member_war_losses(
        session, attacker.id, defender.id, won, att_power, def_power
    )
    vote.status = "resolved"
    if won:
        pct = A.war_loot_percent(att_power, def_power)
        amount = A.war_loot_amount(int(defender.treasury or 0), pct)
        defender.treasury = int(defender.treasury or 0) - amount
        attacker.treasury = int(attacker.treasury or 0) + amount
        session.add(AllianceWar(attacker_id=attacker.id, defender_id=defender.id,
                                winner_id=attacker.id, loser_id=defender.id, amount=amount, attacker_won=1))
        for m_uid in await alliance_service.member_ids(session, attacker.id):
            await _bump_stats(session, m_uid, mafia_wins=1)
        return (f"🏆 پیروزی بر <b>{defender.name}</b>! غنیمت: <b>{amount:,}$</b> "
                f"({pct}٪ صندوقِ حریف) به صندوقِ شما افزوده شد.\n"
                f"🩸 تلفات نیروها — شما: {att_lost_units:,} | حریف: {def_lost_units:,}")
    else:
        pct = A.war_penalty_percent(att_power, def_power)
        amount = A.war_penalty_amount(int(attacker.treasury or 0), pct)
        attacker.treasury = int(attacker.treasury or 0) - amount
        defender.treasury = int(defender.treasury or 0) + amount
        session.add(AllianceWar(attacker_id=attacker.id, defender_id=defender.id,
                                winner_id=defender.id, loser_id=attacker.id, amount=amount, attacker_won=0))
        return (f"💥 شکست در برابرِ <b>{defender.name}</b>! غرامت: <b>{amount:,}$</b> "
                f"({pct}٪ صندوقِ شما) از دست رفت.\n"
                f"🩸 تلفات نیروها — شما: {att_lost_units:,} | حریف: {def_lost_units:,}")


@router.callback_query(F.data.startswith("all:warprop:"))
async def war_propose(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    base, _ = split_owner(callback.data)
    try:
        page = int(base.split(":")[2])
    except (IndexError, ValueError):
        page = 0
    uid = callback.from_user.id
    async with async_session() as session:
        membership = await alliance_service.get_membership(session, uid)
        if not await alliance_service.has_permission(session, membership, A.PERM_WAR):
            await safe_answer(callback, "فقط رئیس/معاون می‌تواند پیشنهادِ جنگ دهد.", show_alert=True)
            return
        if await _active_vote(session, membership.alliance_id) is not None:
            await safe_answer(callback, "همین حالا یک رأی‌گیریِ فعال دارید.", show_alert=True)
            return
        rows = await alliance_service.compute_all_alliances(session)
        my_id = membership.alliance_id
    others = [r for r in rows if r[0].id != my_id]
    per = 8
    total = max(1, (len(others) + per - 1) // per)
    page = max(0, min(page, total - 1))
    chunk = others[page * per:(page + 1) * per]
    if not others:
        await safe_show(callback.message, "حریفی برای جنگ وجود ندارد.", alliance_back_menu(uid))
        await safe_answer(callback)
        return
    await safe_show(callback.message, "⚔️ <b>اتحادیه‌ی هدف را انتخاب کن</b>\nپس از انتخاب، رأی‌گیریِ داخلی آغاز می‌شود.", war_targets_menu(chunk, uid, page, total))
    await safe_answer(callback)


@router.callback_query(F.data.startswith("all:wardo:"))
async def war_do(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    base, _ = split_owner(callback.data)
    target_id = int(base.split(":")[2])
    uid = callback.from_user.id
    async with async_session() as session:
        membership = await alliance_service.get_membership(session, uid)
        if not await alliance_service.has_permission(session, membership, A.PERM_WAR):
            await safe_answer(callback, "فقط رئیس/معاون می‌تواند پیشنهادِ جنگ دهد.", show_alert=True)
            return
        if await _active_vote(session, membership.alliance_id) is not None:
            await safe_answer(callback, "یک رأی‌گیریِ فعال دارید.", show_alert=True)
            return
        target = await alliance_service.get_alliance(session, target_id)
        if target is None or target.id == membership.alliance_id:
            await safe_answer(callback, "هدفِ نامعتبر.", show_alert=True)
            return
        vote = AllianceWarVote(
            alliance_id=membership.alliance_id, target_id=target_id, initiator_id=uid,
            deadline=datetime.utcnow() + timedelta(hours=A.VOTE_HOURS),
        )
        session.add(vote)
        await session.flush()
        session.add(AllianceWarBallot(vote_id=vote.id, voter_id=uid, choice=1))
        await session.commit()
        tname, vid = target.name, vote.id
    await safe_show(
        callback.message,
        (f"🗳️ رأی‌گیریِ حمله به <b>{tname}</b> آغاز شد (مهلت {A.VOTE_HOURS} ساعت).\n"
         "اعضا باید موافقت کنند؛ با ۵۰٪+ موافق، حمله اجرا می‌شود."),
        war_menu(uid, has_active=True, is_officer=True, vote_id=vid),
    )
    await safe_answer(callback, "رأی‌گیری شروع شد.")


@router.callback_query(F.data.startswith("all:vote:"))
async def cast_vote(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    base, _ = split_owner(callback.data)
    parts = base.split(":")
    vote_id = int(parts[2])
    choice = 1 if parts[3] == "1" else 0
    uid = callback.from_user.id
    result_msg = None
    async with async_session() as session:
        membership = await alliance_service.get_membership(session, uid)
        vote = await session.get(AllianceWarVote, vote_id)
        if vote is None or vote.status != "voting":
            await safe_answer(callback, "رأی‌گیریِ فعالی نیست.", show_alert=True)
            return
        if membership is None or membership.alliance_id != vote.alliance_id:
            await safe_answer(callback, "تو عضوِ این اتحادیه نیستی.", show_alert=True)
            return
        ballot = (await session.execute(
            select(AllianceWarBallot).where(
                AllianceWarBallot.vote_id == vote_id, AllianceWarBallot.voter_id == uid
            )
        )).scalar_one_or_none()
        if ballot is None:
            session.add(AllianceWarBallot(vote_id=vote_id, voter_id=uid, choice=choice))
        else:
            ballot.choice = choice
        await session.flush()
        yes, no = await _ballot_counts(session, vote_id)
        cnt = await alliance_service.member_count(session, vote.alliance_id)
        if A.vote_passes(yes, cnt):
            # 🆕 v1.7.9.1 — جنگِ اتحادیه حالا نبردِ زنده‌ی ۱۵ دقیقه‌ای است (مثل کلاسیک/رنکینگ)
            _ok, _res = await AB.start(session, vote.alliance_id, vote.target_id)
            if _ok:
                vote.status = "resolved"
                result_msg = ("⚔️ نصاب رأی رسید — <b>نبردِ زنده‌ی اتحادیه آغاز شد!</b>\n"
                              "از بخشِ «⚔️ جنگِ اتحادیه» فازها را با «🔄 بروزرسانی» دنبال کنید.")
            else:
                vote.status = "failed"
                result_msg = f"❌ جنگ آغاز نشد: {_res}"
            for v in (await session.execute(
                select(AllianceWarBallot.voter_id).where(
                    AllianceWarBallot.vote_id == vote_id, AllianceWarBallot.choice == 1
                )
            )).scalars().all():
                await _bump_stats(session, v, war_assists=1)
        await session.commit()
        role = membership.role
    if result_msg:
        await safe_show(callback.message, f"🗳️ رأی ثبت شد — حدِ نصاب رسید!\n\n{result_msg}", alliance_back_menu(uid))
    else:
        await safe_show(
            callback.message,
            f"🗳️ رأیت ثبت شد.\n✅ موافق: {yes} از {cnt} عضو  |  ❌ مخالف: {no}\n(نصاب: ۵۰٪ اعضا)",
            war_menu(uid, has_active=True, is_officer=_is_officer(role), vote_id=vote_id),
        )
    await safe_answer(callback)


@router.callback_query(F.data.startswith("all:war"))
async def war_open(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    uid = callback.from_user.id
    async with async_session() as session:
        membership = await alliance_service.get_membership(session, uid)
        if membership is None:
            await safe_answer(callback, "اول باید عضوِ اتحادیه باشی.", show_alert=True)
            return
        vote = await _active_vote(session, membership.alliance_id)
        if vote is not None:
            target = await alliance_service.get_alliance(session, vote.target_id)
            yes, no = await _ballot_counts(session, vote.id)
            cnt = await alliance_service.member_count(session, membership.alliance_id)
            initiator = await _name_of(session, vote.initiator_id)
            text = (
                "⚔️ <b>جنگِ اتحادیه</b>\n\n"
                f"🗳️ رأی‌گیریِ حمله به <b>{target.name if target else '?'}</b> در جریان است.\n"
                f"پیشنهاددهنده: {initiator}\n"
                f"✅ موافق: {yes} از {cnt}  |  ❌ مخالف: {no}\n"
                "(با ۵۰٪+ موافق، حمله اجرا می‌شود)"
            )
            vid = vote.id
        else:
            text = (
                "⚔️ <b>جنگِ اتحادیه</b>\n\n"
                "در حالِ حاضر رأی‌گیریِ فعالی نیست.\n"
                "رئیس یا معاون می‌تواند حمله به یک اتحادیه‌ی دیگر را پیشنهاد دهد."
            )
            vid = None
        role = membership.role
        # 🆕 v1.7.9.1 — نمایشِ نبردِ زنده‌ی درجریان
        _bt = await AB.running_battle_for(session, membership.alliance_id)
        if _bt is not None:
            text += "\n\n🔥 <b>یک نبردِ زنده در جریان است!</b>\nبا دکمه‌ی «🔥 نبردِ زنده» فازها را دنبال کن."
        # 🆕 مرحله ۳۰ — پیشنهادِ جنگ بر اساسِ دسترسی
        _can_war = await alliance_service.has_permission(session, membership, A.PERM_WAR)
    await safe_show(callback.message, text, war_menu(uid, has_active=vid is not None, is_officer=_can_war, vote_id=vid, has_battle=_bt is not None))
    await safe_answer(callback)


# ===========================================================================
# 🆕 مرحله ۳۰ — پروفایلِ کاملِ اتحادیه + دسترسی‌هایِ معاون
# ===========================================================================
def _perm_text(perms) -> str:
    have = set(perms or ())
    names = [A.PERM_LABELS[k] for k in A.PERM_ORDER if k in have]
    return "، ".join(names) if names else "بدونِ دسترسیِ ویژه"


@router.callback_query(F.data.startswith("all:info"))
async def alliance_profile(callback: CallbackQuery) -> None:
    """پروفایلِ اتحادیه — قبلاً هیچ اطلاعی نشان نمی‌داد."""
    if not await ensure_owner(callback):
        return
    uid = callback.from_user.id
    async with async_session() as session:
        membership = await alliance_service.get_membership(session, uid)
        if membership is None:
            await safe_answer(callback, "تو در هیچ اتحادیه‌ای نیستی.", show_alert=True)
            return
        al = await alliance_service.get_alliance(session, membership.alliance_id)
        if al is None:
            await safe_answer(callback, "اتحادیه پیدا نشد.", show_alert=True)
            return
        rows = await alliance_service.internal_ranking(session, al.id)
        power = await alliance_service.alliance_power_value(session, al)
        leader_name = await _name_of(session, al.leader_id)
        wars = (await session.execute(
            select(AllianceWar).where(
                (AllianceWar.attacker_id == al.id) | (AllianceWar.defender_id == al.id)
            )
        )).scalars().all()
        wins = sum(1 for w in wars if w.winner_id == al.id)
        losses = sum(1 for w in wars if w.loser_id == al.id)
        names = {}
        perms_map = {}
        for m, _pw in rows:
            names[m.player_id] = await _name_of(session, m.player_id)
            if m.role == A.ROLE_DEPUTY:
                perms_map[m.player_id] = await alliance_service.get_permissions(
                    session, al.id, m.player_id
                )
        my_perms = await alliance_service.get_permissions(session, al.id, uid)
    try:
        bonus = A.income_bonus_pct(al.level)
    except Exception:
        bonus = 0
    lines = [
        "📊 <b>پروفایلِ اتحادیه</b>",
        f"🛡️ نام: <b>{al.name}</b>  (<code>{al.tag}</code>)",
        "",
        f"👑 رئیس: {leader_name}",
        f"👥 اعضا: {len(rows)}/{A.member_cap_for_level(al.level)}  |  سطح: {al.level}",
        f"⚔️ قدرتِ نظامی: سطح {al.mil_level} ({A.mil_power_for_level(al.mil_level):,})",
        f"💥 قدرتِ کل: <b>{power:,}</b>",
        f"💰 صندوق: {int(al.treasury or 0):,}$",
        f"🎁 بونوسِ درآمد: +{bonus}٪",
        f"💳 اشتراکِ عضویت: {al.sub_pct}٪ هر {al.sub_days} روز",
        f"🔐 آستانه‌ی قدرتِ عضویت: {int(al.min_power or 0):,}",
        f"🏆 کارنامه‌ی جنگ: {wins} برد / {losses} باخت",
        "",
        "👥 <b>اعضا (به ترتیبِ قدرت):</b>",
    ]
    for m, pw in rows[:15]:
        mark = "👉" if m.player_id == uid else "•"
        nm = names.get(m.player_id, "بازیکن")
        lines.append(
            f"{mark} {A.ROLE_LABELS.get(m.role, m.role)} — {nm} "
            f"— 💥{pw:,} — 🎁{int(m.contributed or 0):,}$"
        )
        if m.role == A.ROLE_DEPUTY:
            lines.append(f"    🔑 {_perm_text(perms_map.get(m.player_id))}")
    if membership.role == A.ROLE_DEPUTY:
        lines += ["", f"🔑 دسترسی‌های تو: {_perm_text(my_perms)}"]
    await safe_show(callback.message, "\n".join(lines), alliance_back_menu(uid))
    await safe_answer(callback)


@router.callback_query(F.data.startswith("all:perms:"))
async def member_perms(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    base, _ = split_owner(callback.data)
    try:
        pid = int(base.split(":")[2])
    except (IndexError, ValueError):
        await safe_answer(callback, "عضو پیدا نشد.", show_alert=True)
        return
    uid = callback.from_user.id
    async with async_session() as session:
        leader = await alliance_service.get_membership(session, uid)
        if leader is None or leader.role != A.ROLE_LEADER:
            await safe_answer(callback, "فقط رئیس می‌تواند دسترسی بدهد.", show_alert=True)
            return
        target = await alliance_service.get_membership(session, pid)
        if target is None or target.alliance_id != leader.alliance_id:
            await safe_answer(callback, "این عضو در اتحادیه‌ی تو نیست.", show_alert=True)
            return
        if target.role != A.ROLE_DEPUTY:
            await safe_answer(callback, "اول این عضو را معاون کن، بعد دسترسی بده.", show_alert=True)
            return
        nm = await _name_of(session, pid)
        perms = await alliance_service.get_permissions(session, leader.alliance_id, pid)
    text = (
        f"🔑 <b>دسترسی‌های {nm}</b>\n"
        f"🎖️ نقش: {A.ROLE_LABELS.get(A.ROLE_DEPUTY)}\n\n"
        "هر دسترسی را با زدنِ دکمه‌اش روشن (✅) یا خاموش (❌) کن:\n"
        f"• فعلاً: {_perm_text(perms)}"
    )
    await safe_show(callback.message, text, perms_menu(pid, perms, uid))
    await safe_answer(callback)


@router.callback_query(F.data.startswith("all:permt:"))
async def member_perm_toggle(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback):
        return
    base, _ = split_owner(callback.data)
    parts = base.split(":")
    if len(parts) < 4:
        await safe_answer(callback, "دسترسی نامعتبر است.", show_alert=True)
        return
    try:
        pid = int(parts[2])
    except ValueError:
        await safe_answer(callback, "عضو پیدا نشد.", show_alert=True)
        return
    key = parts[3]
    if key not in A.PERM_ORDER:
        await safe_answer(callback, "دسترسی نامعتبر است.", show_alert=True)
        return
    uid = callback.from_user.id
    async with async_session() as session:
        leader = await alliance_service.get_membership(session, uid)
        if leader is None or leader.role != A.ROLE_LEADER:
            await safe_answer(callback, "فقط رئیس می‌تواند دسترسی بدهد.", show_alert=True)
            return
        target = await alliance_service.get_membership(session, pid)
        if target is None or target.alliance_id != leader.alliance_id:
            await safe_answer(callback, "این عضو در اتحادیه‌ی تو نیست.", show_alert=True)
            return
        if target.role != A.ROLE_DEPUTY:
            await safe_answer(callback, "اول این عضو را معاون کن.", show_alert=True)
            return
        enabled = await alliance_service.toggle_permission(
            session, leader.alliance_id, pid, key
        )
        await session.commit()
        nm = await _name_of(session, pid)
        perms = await alliance_service.get_permissions(session, leader.alliance_id, pid)
    state_txt = "✅ روشن" if enabled else "❌ خاموش"
    text = (
        f"🔑 <b>دسترسی‌های {nm}</b>\n\n"
        f"{A.PERM_LABELS[key]} → {state_txt}\n\n"
        f"• فعلاً: {_perm_text(perms)}"
    )
    await safe_show(callback.message, text, perms_menu(pid, perms, uid))
    await safe_answer(callback, "✅ دسترسی به‌روز شد.")
