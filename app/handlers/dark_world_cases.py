# -*- coding: utf-8 -*-
"""Stage 87.2 — handlers for branching Dark World text cases."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery

from app.database.engine import async_session
from app.data import dark_world as D
from app.data import dark_world_cases as C
from app.data import leveling
from app.keyboards.dark_world_case_menu import (
    abandon_confirm_menu,
    case_hub_menu,
    case_list_menu,
    case_preview_menu,
    ending_menu,
    node_menu,
    shop_menu,
    tools_menu,
)
from app.services import dark_world_case_service as CS
from app.services import dark_world_service as DS
from app.services.operation_guard import BusyOperation, DuplicateOperation, economic_operation
from app.utils.ui import click_debounce, ensure_owner, safe_answer, safe_show, split_owner

router = Router(name="dark_world_cases")


def _base(callback: CallbackQuery) -> str:
    return split_owner(callback.data or "")[0]


def case_hub_text(profile, run, inventory: dict[str, int]) -> str:
    active = "نداری"
    if run:
        case = C.get_case(run.case_key)
        node = C.get_node(run.case_key, run.node_key)
        active = f"{case['name'] if case else run.case_key} — {node['title'] if node else run.node_key}"
    total_tools = sum(max(0, int(qty)) for qty in inventory.values())
    return (
        "🎲 <b>پرونده‌های تعاملی دنیای سیاه</b>\n"
        "<i>بازی متنی چندشاخه؛ هر انتخاب می‌تواند مسیر و پایان را عوض کند.</i>\n\n"
        f"🗝️ نفوذ: <b>{int(profile.influence or 0):,}</b>\n"
        f"⚡ انرژی: <b>{int(profile.energy or 0)}/{D.ENERGY_MAX}</b>\n"
        f"👁️ اطلاعات: <b>{int(profile.intel or 0):,}</b>\n"
        f"🚨 Heat: <b>{int(profile.heat or 0)}/{D.HEAT_MAX}</b>\n"
        f"🎒 ابزار مصرفی: <b>{total_tools}</b>\n"
        f"📂 پرونده فعال: <b>{active}</b>\n\n"
        "هر آزمون شانس مستقل دارد. موفقیت Momentum می‌سازد؛ شکست Danger و Heat را بالا می‌برد. "
        "پرونده‌ها چند پایان موفق، نیمه‌موفق و شکست کامل دارند."
    )


def case_preview_text(plan: dict, ready: bool) -> str:
    case = plan["case"]
    endings = list(case["endings"].values())
    success_endings = sum(1 for item in endings if item["success"])
    lines = [
        f"{case['icon']} <b>{case['name']}</b>",
        case["description"], "",
        f"☠️ سختی: <b>{case['difficulty']}/4 — {case['difficulty_name']}</b>",
        f"🗝️ نفوذ لازم: {int(case['required_influence']):,}",
        f"🎟️ ورودی غیرقابل‌برگشت: <b>{int(case['entry_cost']):,}</b>",
        f"⚡ انرژی: {int(case['energy'])} (موجود {int(plan['energy_available'])})",
        f"👁️ اطلاعات: {int(case.get('intel_cost', 0))} (موجود {int(plan['intel_available'])})",
        f"⏳ مهلت تکمیل: {C.CASE_EXPIRY_HOURS} ساعت", "",
        f"🧭 پایان‌ها: <b>{success_endings} موفق/نیمه‌موفق + {len(endings) - success_endings} شکست</b>",
        f"💵 غنیمت پایه پیش از ضریب پایان: {int(case['base_cash']):,}",
        f"✨ XP پایه پیش از ضرایب: {int(case['base_xp']):,}",
        "🧮 XP نهایی = پایه سختی × پایان × پیشرفت × آزمون‌های موفق × ریسک", 
        "", "✅ آماده بازکردن پرونده است." if ready else "⚠️ فعلاً قابل شروع نیست:",
    ]
    if not ready:
        lines.extend(f"• {issue}" for issue in plan.get("issues") or ["شرایط کامل نیست."])
    return "\n".join(lines)


def node_text(state: dict, check_result: dict | None = None) -> str:
    case, node, run, profile = state["case"], state["node"], state["run"], state["profile"]
    lines: list[str] = []
    if check_result:
        icon = "✅" if check_result["check_success"] else "❌"
        lines += [
            f"{icon} <b>{check_result['check_text']}</b>",
            f"🎲 شانس {float(check_result['chance']):.2f}٪ · رول {float(check_result['roll']):.2f}",
        ]
        if check_result.get("tool_consumed"):
            tool = C.get_tool(check_result["tool_consumed"])
            lines.append(f"🎒 {tool['name'] if tool else check_result['tool_consumed']} مصرف شد.")
        lines += [""]
    selected = state.get("selected_tool")
    selected_text = "نداری"
    if selected and C.get_tool(selected):
        tool = C.get_tool(selected)
        selected_text = f"{tool['icon']} {tool['name']} (+{int(tool['bonus'])}٪ روی مهارت سازگار)"
    lines += [
        f"{case['icon']} <b>{case['name']}</b>",
        f"📍 <b>{node['title']}</b>",
        node["text"], "",
        f"⚡ Momentum: <b>{int(run.momentum):+d}</b> · ☠️ Danger: <b>{int(run.danger)}/{C.DANGER_MAX}</b>",
        f"🚨 Heat فعلی: <b>{int(profile.heat or 0)}/{D.HEAT_MAX}</b>",
        f"🎒 ابزار انتخابی: <b>{selected_text}</b>",
        f"🧾 انتخاب‌های ثبت‌شده: <b>{len(state['history'])}</b>", "",
        "<b>تصمیم بعدی:</b>",
    ]
    for row in state["choices"]:
        choice, chance = row["choice"], row["chance"]
        tool_note = f" · ابزار +{int(chance['tool_bonus'])}٪" if chance.get("tool_applies") else ""
        lines.append(
            f"• {choice['icon']} {choice['label']} — {C.SKILL_LABELS[choice['skill']]} "
            f"<b>{float(chance['chance']):.2f}٪</b>{tool_note}"
        )
    lines += ["", "ابزار فقط در آزمون سازگار مصرف می‌شود؛ callback قدیمی پس از تغییر مرحله معتبر نیست."]
    return "\n".join(lines)


def tools_text(inventory: dict[str, int], selected: str | None) -> str:
    lines = ["🎒 <b>انبار ابزارهای مصرفی</b>", "", "هر ابزار فقط یک آزمون سازگار را تقویت می‌کند و سپس مصرف می‌شود.", ""]
    for key in C.TOOL_ORDER:
        tool = C.TOOLS[key]
        mark = " — انتخاب‌شده" if selected == key else ""
        lines.append(f"{tool['icon']} <b>{tool['name']}</b> ×{int(inventory.get(key, 0))}{mark}\n   {tool['description']}")
    return "\n".join(lines)


def shop_text(inventory: dict[str, int]) -> str:
    lines = ["🛒 <b>فروشگاه ابزار پرونده</b>", "", f"سقف انبار هر ابزار: {C.TOOL_MAX_QTY}", ""]
    for key in C.TOOL_ORDER:
        tool = C.TOOLS[key]
        lines.append(
            f"{tool['icon']} <b>{tool['name']}</b> — {int(tool['cost']):,}\n"
            f"   موجودی {int(inventory.get(key, 0))}/{C.TOOL_MAX_QTY} · {tool['description']}"
        )
    return "\n".join(lines)


def ending_text(payload: dict) -> str:
    case, ending, reward = payload["case"], payload["ending"], payload["reward"]
    icon = "🏆" if reward["success"] else "⛓️"
    lines = [
        f"{icon} <b>{ending['name']}</b>",
        ending["text"], "",
        f"{case['icon']} پرونده: {case['name']}",
        f"🧭 نتیجه: {'موفق' if reward['success'] else 'شکست'}",
        f"💵 درآمد: <b>+{int(reward['cash']):,}</b>",
        f"🌘 XP سیاه: +{int(reward['dark_xp']):,}",
        f"🗝️ تغییر نفوذ: {int(reward['influence']):+d}",
        f"👁️ اطلاعات: +{int(reward['intel']):,}",
        f"🚨 Heat پایان: +{int(reward['heat'])}",
        f"☠️ Danger نهایی: {int(payload['danger'])}/{C.DANGER_MAX}",
        f"🧮 ضریب XP: پیشرفت ×{float(reward['progress_factor']):.2f} · مهارت ×{float(reward['skill_factor']):.2f} · ریسک ×{float(reward['risk_factor']):.2f}",
    ]
    lines.append(leveling.xp_note(payload["xp_result"]).lstrip() or "✨ XP عمومی: ۰")
    if payload.get("team_note"): lines.append(payload["team_note"].strip())
    return "\n".join(lines)


@router.callback_query(F.data.startswith("dwc:hub"))
async def cases_hub(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback): return
    async with async_session() as session:
        ok, reason, snapshot = await DS.hub_snapshot(session, callback.from_user.id)
        run = await CS.get_run(session, callback.from_user.id) if ok else None
        inventory = await CS.inventory_map(session, callback.from_user.id) if ok else {}
        await session.commit()
    if not ok:
        await safe_answer(callback, reason, show_alert=True); return
    await safe_show(callback.message, case_hub_text(snapshot["profile"], run, inventory), case_hub_menu(callback.from_user.id, bool(run)))
    await safe_answer(callback)


@router.callback_query(F.data.startswith("dwc:list"))
async def cases_list(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback): return
    async with async_session() as session:
        ok, reason, snapshot = await DS.hub_snapshot(session, callback.from_user.id)
        await session.commit()
    if not ok:
        await safe_answer(callback, reason, show_alert=True); return
    profile = snapshot["profile"]
    lines = ["🗂️ <b>پرونده‌های چندشاخه</b>", "", "هر پرونده چند مسیر و چهار پایان دارد؛ شکست یک آزمون همیشه پایان کار نیست.", ""]
    for key in C.CASE_ORDER:
        case = C.CASES[key]
        status = "✅" if int(profile.influence or 0) >= int(case["required_influence"]) else "🔒"
        lines.append(f"{status} {case['icon']} <b>{case['name']}</b> — سختی {case['difficulty']}/4 · نیاز {int(case['required_influence']):,} نفوذ")
    await safe_show(callback.message, "\n".join(lines), case_list_menu(profile.influence, callback.from_user.id))
    await safe_answer(callback)


@router.callback_query(F.data.startswith("dwc:case:"))
async def case_detail(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback): return
    case_key = _base(callback).split(":")[2]
    async with async_session() as session:
        ready, reason, plan = await CS.case_preview(session, callback.from_user.id, case_key)
        await session.commit()
    if not plan:
        await safe_answer(callback, reason[:180], show_alert=True); return
    await safe_show(callback.message, case_preview_text(plan, ready), case_preview_menu(case_key, callback.from_user.id, ready))
    await safe_answer(callback)


@router.callback_query(F.data.startswith("dwc:start:"))
async def case_start(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback): return
    if click_debounce(callback.from_user.id, "dark_case_start", 3):
        await safe_answer(callback, "کلیک قبلی در حال پردازش است."); return
    case_key = _base(callback).split(":")[2]
    try:
        async with economic_operation(callback.from_user.id, f"dwc-start:{callback.id}"):
            async with async_session() as session:
                ok, message = await CS.start_case(session, callback.from_user.id, case_key)
                if ok:
                    state_ok, _, state = await CS.case_state(session, callback.from_user.id)
                    await session.commit()
    except (BusyOperation, DuplicateOperation):
        await safe_answer(callback, "این درخواست قبلاً اجرا شده یا عملیات دیگری در حال پردازش است.", show_alert=True); return
    if not ok:
        await safe_answer(callback, message[:180], show_alert=True); return
    await safe_show(callback.message, node_text(state), node_menu(state, callback.from_user.id))
    await safe_answer(callback, "پرونده باز شد")


@router.callback_query(F.data.startswith("dwc:active"))
async def case_active(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback): return
    async with async_session() as session:
        ok, reason, state = await CS.case_state(session, callback.from_user.id)
        await session.commit()
    if not ok:
        await safe_answer(callback, reason[:180], show_alert=True)
        await safe_show(callback.message, reason, case_hub_menu(callback.from_user.id, False))
        return
    await safe_show(callback.message, node_text(state), node_menu(state, callback.from_user.id))
    await safe_answer(callback)


@router.callback_query(F.data.startswith("dwc:choice:"))
async def case_choice(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback): return
    if click_debounce(callback.from_user.id, "dark_case_choice", 2.5):
        await safe_answer(callback, "انتخاب قبلی در حال ثبت است."); return
    choice_key = _base(callback).split(":")[2]
    try:
        async with economic_operation(callback.from_user.id, f"dwc-choice:{callback.id}"):
            async with async_session() as session:
                ok, message, payload = await CS.apply_choice(session, callback.from_user.id, choice_key)
                if ok and not payload.get("ended"):
                    state_ok, state_reason, state = await CS.case_state(session, callback.from_user.id)
                    await session.commit()
    except (BusyOperation, DuplicateOperation):
        await safe_answer(callback, "این انتخاب قبلاً ثبت شده یا کلیک دیگری در حال پردازش است.", show_alert=True); return
    if not ok:
        await safe_answer(callback, message[:180], show_alert=True); return
    if payload.get("ended"):
        await safe_show(callback.message, ending_text(payload), ending_menu(callback.from_user.id))
        await safe_answer(callback, "پایان پرونده ثبت شد")
        return
    if not state_ok:
        await safe_answer(callback, state_reason[:180], show_alert=True); return
    await safe_show(callback.message, node_text(state, payload), node_menu(state, callback.from_user.id))
    await safe_answer(callback, "انتخاب ثبت شد")


@router.callback_query(F.data.startswith("dwc:tools"))
async def case_tools(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback): return
    async with async_session() as session:
        run = await CS.get_run(session, callback.from_user.id)
        inventory = await CS.inventory_map(session, callback.from_user.id)
        selected = str(run.selected_tool_key or "") if run else None
    await safe_show(callback.message, tools_text(inventory, selected), tools_menu(inventory, selected, callback.from_user.id, bool(run)))
    await safe_answer(callback)


@router.callback_query(F.data.startswith("dwc:tool:"))
async def case_tool_select(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback): return
    tool_key = _base(callback).split(":")[2]
    async with async_session() as session:
        ok, message = await CS.select_tool(session, callback.from_user.id, tool_key)
        if ok:
            state_ok, reason, state = await CS.case_state(session, callback.from_user.id)
            await session.commit()
    if not ok:
        await safe_answer(callback, message, show_alert=True); return
    if not state_ok:
        await safe_answer(callback, reason, show_alert=True); return
    await safe_show(callback.message, node_text(state), node_menu(state, callback.from_user.id))
    await safe_answer(callback, message)


@router.callback_query(F.data.startswith("dwc:shop"))
async def case_shop(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback): return
    async with async_session() as session:
        player = await DS.get_player(session, callback.from_user.id)
        blocked = DS.access_message(player)
        inventory = await CS.inventory_map(session, callback.from_user.id) if not blocked else {}
    if blocked:
        await safe_answer(callback, blocked, show_alert=True); return
    await safe_show(callback.message, shop_text(inventory), shop_menu(inventory, callback.from_user.id))
    await safe_answer(callback)


@router.callback_query(F.data.startswith("dwc:buy:"))
async def case_buy_tool(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback): return
    if click_debounce(callback.from_user.id, "dark_tool_buy", 2.5):
        await safe_answer(callback, "خرید قبلی در حال ثبت است."); return
    tool_key = _base(callback).split(":")[2]
    try:
        async with economic_operation(callback.from_user.id, f"dwc-buy:{callback.id}"):
            async with async_session() as session:
                ok, message = await CS.buy_tool(session, callback.from_user.id, tool_key)
                inventory = await CS.inventory_map(session, callback.from_user.id) if ok else {}
    except (BusyOperation, DuplicateOperation):
        await safe_answer(callback, "این خرید قبلاً اجرا شده یا عملیات دیگری در حال پردازش است.", show_alert=True); return
    if not ok:
        await safe_answer(callback, message[:180], show_alert=True); return
    await safe_show(callback.message, shop_text(inventory), shop_menu(inventory, callback.from_user.id))
    await safe_answer(callback, "ابزار خریداری شد")


@router.callback_query(F.data.startswith("dwc:abandon_yes"))
async def case_abandon_confirmed(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback): return
    try:
        async with economic_operation(callback.from_user.id, f"dwc-abandon:{callback.id}"):
            async with async_session() as session:
                ok, message = await CS.abandon_case(session, callback.from_user.id)
    except (BusyOperation, DuplicateOperation):
        await safe_answer(callback, "این درخواست قبلاً اجرا شده است.", show_alert=True); return
    await safe_show(callback.message, message, case_hub_menu(callback.from_user.id, False))
    await safe_answer(callback, "پرونده رها شد" if ok else message, show_alert=not ok)


@router.callback_query(F.data.startswith("dwc:abandon"))
async def case_abandon(callback: CallbackQuery) -> None:
    if not await ensure_owner(callback): return
    await safe_show(
        callback.message,
        "⚠️ <b>رهاکردن پرونده؟</b>\n\nهزینه ورود و منابع برنمی‌گردند؛ ۵ Heat اضافه و ۵ نفوذ کم می‌شود.",
        abandon_confirm_menu(callback.from_user.id),
    )
    await safe_answer(callback)


@router.callback_query(F.data.startswith("dwc:locked"))
async def case_locked(callback: CallbackQuery) -> None:
    if await ensure_owner(callback): await safe_answer(callback, "نفوذ لازم را از عملیات‌ها و پرونده‌های بازشده به دست بیاور.", show_alert=True)


@router.callback_query(F.data.startswith("dwc:no_tool"))
async def case_no_tool(callback: CallbackQuery) -> None:
    if await ensure_owner(callback): await safe_answer(callback, "این ابزار را نداری؛ از فروشگاه تهیه کن.", show_alert=True)


@router.callback_query(F.data.startswith("dwc:max_tool"))
async def case_max_tool(callback: CallbackQuery) -> None:
    if await ensure_owner(callback): await safe_answer(callback, "انبار این ابزار پر است.")
