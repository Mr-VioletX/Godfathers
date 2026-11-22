# -*- coding: utf-8 -*-
"""Stage 87.2 — persistent engine for branching Dark World cases."""
from __future__ import annotations

import json
import secrets
from datetime import datetime, timedelta

from sqlalchemy import select

from app.data import dark_world as D
from app.data import dark_world_cases as C
from app.data import leveling
from app.models.dark_world import (
    DarkWorldCaseLog,
    DarkWorldCaseRun,
    DarkWorldProfile,
    DarkWorldToolInventory,
)
from app.services import dark_world_service as DS


def _now() -> datetime:
    return datetime.utcnow()


def _history(run: DarkWorldCaseRun) -> list[dict]:
    try:
        value = json.loads(run.history_json or "[]")
        return value if isinstance(value, list) else []
    except Exception:
        return []


def _save_history(run: DarkWorldCaseRun, rows: list[dict]) -> None:
    run.history_json = json.dumps(rows[-C.CASE_HISTORY_LIMIT :], ensure_ascii=False, separators=(",", ":"))


async def get_run(session, uid: int) -> DarkWorldCaseRun | None:
    return (await session.execute(
        select(DarkWorldCaseRun).where(DarkWorldCaseRun.owner_id == int(uid))
    )).scalar_one_or_none()


async def inventory_rows(session, uid: int) -> list[DarkWorldToolInventory]:
    return list((await session.execute(
        select(DarkWorldToolInventory)
        .where(DarkWorldToolInventory.owner_id == int(uid))
        .order_by(DarkWorldToolInventory.id)
    )).scalars().all())


async def inventory_map(session, uid: int) -> dict[str, int]:
    return {str(row.tool_key): max(0, int(row.qty or 0)) for row in await inventory_rows(session, uid)}


async def _tool_row(session, uid: int, tool_key: str) -> DarkWorldToolInventory | None:
    return (await session.execute(
        select(DarkWorldToolInventory).where(
            DarkWorldToolInventory.owner_id == int(uid),
            DarkWorldToolInventory.tool_key == str(tool_key),
        )
    )).scalar_one_or_none()


async def case_preview(session, uid: int, case_key: str) -> tuple[bool, str, dict]:
    player = await DS.get_player(session, uid)
    blocked = DS.access_message(player)
    if blocked:
        return False, blocked, {}
    profile = await DS.get_profile(session, uid, create=True)
    DS.apply_recovery(profile)
    case = C.get_case(case_key)
    if not case:
        return False, "پرونده نامعتبر است.", {}
    active_case = await get_run(session, uid)
    issues: list[str] = []
    if D.operation_locked(int(profile.heat or 0)):
        issues.append("Heat به ۸۰ رسیده؛ ابتدا در بخش تعقیب و مخفیگاه تهدید را خنثی کن.")
    if active_case is not None:
        issues.append("یک پرونده تعاملی فعال داری.")
    if profile.active_contract_key:
        issues.append("یک عملیات زمان‌دار فعال داری؛ اول نتیجه آن را بگیر.")
    required = int(case["required_influence"])
    if int(profile.influence or 0) < required:
        issues.append(f"برای این پرونده {required:,} نفوذ لازم است.")
    if int(profile.energy or 0) < int(case["energy"]):
        issues.append(f"کمبود انرژی: {int(case['energy']) - int(profile.energy or 0)}")
    intel_cost = int(case.get("intel_cost", 0))
    if int(profile.intel or 0) < intel_cost:
        issues.append(f"کمبود اطلاعات: {intel_cost - int(profile.intel or 0)}")
    if int(player.cash or 0) < int(case["entry_cost"]):
        issues.append(f"کمبود پول ورودی: {int(case['entry_cost']) - int(player.cash or 0):,}")
    plan = {
        "case_key": case_key,
        "case": case,
        "issues": issues,
        "energy_available": int(profile.energy or 0),
        "intel_available": int(profile.intel or 0),
        "cash_available": int(player.cash or 0),
        "influence": int(profile.influence or 0),
    }
    return not issues, "\n".join(issues) if issues else "ok", plan


async def start_case(session, uid: int, case_key: str) -> tuple[bool, str]:
    ready, reason, plan = await case_preview(session, uid, case_key)
    if not ready:
        return False, reason
    player = await DS.get_player(session, uid)
    profile = await DS.get_profile(session, uid, create=True)
    case = plan["case"]
    player.cash = int(player.cash or 0) - int(case["entry_cost"])
    profile.energy = int(profile.energy or 0) - int(case["energy"])
    profile.intel = int(profile.intel or 0) - int(case.get("intel_cost", 0))
    profile.contracts_started = int(profile.contracts_started or 0) + 1
    now = _now()
    session.add(DarkWorldCaseRun(
        owner_id=int(uid), actor_id=int(uid), beneficiary_id=int(uid), employment_contract_id=None,
        case_key=case_key, node_key=str(case["start_node"]),
        momentum=0, danger=0, selected_tool_key=None, history_json="[]",
        started_at=now, expires_at=now + timedelta(hours=C.CASE_EXPIRY_HOURS),
    ))
    await session.commit()
    return True, (
        f"🎲 پرونده «{case['name']}» باز شد. هزینه ورود و منابع مصرف شدند.\n"
        f"⏳ برای تکمیل تمام انتخاب‌ها {C.CASE_EXPIRY_HOURS} ساعت فرصت داری."
    )


async def case_state(session, uid: int) -> tuple[bool, str, dict]:
    player = await DS.get_player(session, uid)
    blocked = DS.access_message(player)
    if blocked:
        return False, blocked, {}
    profile = await DS.get_profile(session, uid, create=True)
    DS.apply_recovery(profile)
    run = await get_run(session, uid)
    if run is None:
        return False, "پرونده تعاملی فعالی نداری.", {"profile": profile, "player": player}
    if run.expires_at <= _now():
        profile.heat = min(D.HEAT_MAX, int(profile.heat or 0) + 8)
        await session.delete(run)
        return False, "مهلت پرونده تمام شد؛ ورودی از دست رفت و ۸ Heat اضافه شد.", {"profile": profile, "player": player, "expired": True}
    case = C.get_case(run.case_key)
    node = C.get_node(run.case_key, run.node_key)
    if not case or not node:
        return False, "وضعیت پرونده خراب است؛ از پشتیبانی بخواه آن را لغو کند.", {"profile": profile, "player": player}
    inventory = await inventory_map(session, uid)
    from app.services import dark_world_npc_service as NPS
    team = await NPS.team_context(session, uid)
    recruits = team["keys"]
    selected = str(run.selected_tool_key or "") or None
    if selected and inventory.get(selected, 0) <= 0:
        run.selected_tool_key = None
        selected = None
    choices = []
    for choice_key, choice in node["choices"].items():
        chance = C.choice_chance(
            choice, int(player.level or 1), int(profile.influence or 0),
            int(profile.heat or 0), int(run.momentum or 0), int(run.danger or 0),
            recruits, selected, team["effectiveness"], team["tactic"],
        )
        choices.append({"key": choice_key, "choice": choice, "chance": chance})
    return True, "ok", {
        "player": player, "profile": profile, "run": run, "case": case,
        "node": node, "choices": choices, "inventory": inventory,
        "recruits": recruits, "history": _history(run), "selected_tool": selected,
    }


async def select_tool(session, uid: int, tool_key: str | None) -> tuple[bool, str]:
    run = await get_run(session, uid)
    if run is None:
        return False, "پرونده فعالی نداری."
    if tool_key in (None, "", "none"):
        run.selected_tool_key = None
        await session.commit()
        return True, "ابزار انتخابی کنار گذاشته شد."
    tool = C.get_tool(tool_key)
    if not tool:
        return False, "ابزار نامعتبر است."
    row = await _tool_row(session, uid, tool_key)
    if row is None or int(row.qty or 0) <= 0:
        return False, "از این ابزار در انبار نداری."
    run.selected_tool_key = tool_key
    await session.commit()
    return True, f"{tool['icon']} {tool['name']} برای آزمون سازگار بعدی آماده شد."


async def buy_tool(session, uid: int, tool_key: str) -> tuple[bool, str]:
    tool = C.get_tool(tool_key)
    if not tool:
        return False, "ابزار نامعتبر است."
    player = await DS.get_player(session, uid)
    blocked = DS.access_message(player)
    if blocked:
        return False, blocked
    row = await _tool_row(session, uid, tool_key)
    qty = int(row.qty or 0) if row else 0
    if qty >= C.TOOL_MAX_QTY:
        return False, f"از هر ابزار حداکثر {C.TOOL_MAX_QTY} عدد می‌توانی نگه داری."
    cost = int(tool["cost"])
    if int(player.cash or 0) < cost:
        return False, f"پول کافی نداری؛ قیمت {cost:,} است."
    player.cash = int(player.cash or 0) - cost
    if row:
        row.qty = qty + 1
    else:
        session.add(DarkWorldToolInventory(owner_id=int(uid), tool_key=tool_key, qty=1))
    xp_result = await leveling.grant_xp(session, player, max(100, min(500, cost // 500_000)), source="dark_world_tool")
    await session.commit()
    return True, f"✅ {tool['icon']} {tool['name']} خریداری شد. موجودی: {qty + 1}/{C.TOOL_MAX_QTY}" + leveling.xp_note(xp_result)


async def apply_choice(session, uid: int, choice_key: str) -> tuple[bool, str, dict]:
    player = await DS.get_player(session, uid)
    profile = await DS.get_profile(session, uid, create=False)
    run = await get_run(session, uid)
    blocked = DS.access_message(player)
    if blocked:
        return False, blocked, {}
    if profile is None or run is None:
        return False, "پرونده فعالی نداری.", {}
    if run.expires_at <= _now():
        profile.heat = min(D.HEAT_MAX, int(profile.heat or 0) + 8)
        await session.delete(run)
        await session.commit()
        return False, "مهلت پرونده تمام شد؛ ورودی از دست رفت و ۸ Heat اضافه شد.", {"ended": True}
    choice = C.get_choice(run.case_key, run.node_key, choice_key)
    if not choice:
        return False, "این انتخاب دیگر برای مرحله فعلی معتبر نیست.", {}
    from app.services import dark_world_npc_service as NPS
    team = await NPS.team_context(session, uid)
    recruits = team["keys"]
    selected = str(run.selected_tool_key or "") or None
    tool_row = await _tool_row(session, uid, selected) if selected else None
    if selected and (tool_row is None or int(tool_row.qty or 0) <= 0):
        selected = None
        run.selected_tool_key = None
    chance_info = C.choice_chance(
        choice, int(player.level or 1), int(profile.influence or 0),
        int(profile.heat or 0), int(run.momentum or 0), int(run.danger or 0),
        recruits, selected, team["effectiveness"], team["tactic"],
    )
    roll_bp = secrets.randbelow(10_000)
    result = C.resolve_choice(choice, chance_info, roll_bp / 100.0, int(run.momentum or 0), int(run.danger or 0))
    consumed_tool = None
    if result["tool_consumed"] and selected and tool_row:
        tool_row.qty = max(0, int(tool_row.qty or 0) - 1)
        run.selected_tool_key = None
        consumed_tool = selected
    run.momentum = int(result["momentum"])
    run.danger = int(result["danger"])
    profile.heat = min(D.HEAT_MAX, int(profile.heat or 0) + int(result["heat"]))
    rows = _history(run)
    rows.append({
        "node": str(run.node_key), "choice": str(choice_key), "skill": str(choice["skill"]),
        "chance_bp": int(round(float(chance_info["chance"]) * 100)), "roll_bp": int(roll_bp),
        "success": bool(result["success"]), "destination": str(result["destination"]),
        "tool": consumed_tool, "danger": int(run.danger or 0),
    })
    _save_history(run, rows)
    destination = str(result["destination"])
    step_payload = {
        "ended": destination.startswith("end:"), "check_success": bool(result["success"]),
        "check_text": str(result["text"]), "chance": float(chance_info["chance"]),
        "roll": roll_bp / 100.0, "tool_consumed": consumed_tool,
        "momentum": int(run.momentum), "danger": int(run.danger), "heat_added": int(result["heat"]),
    }
    if not destination.startswith("end:"):
        run.node_key = destination
        await session.commit()
        return True, "مرحله ثبت شد.", step_payload

    ending_key = destination[4:]
    ending = C.get_ending(run.case_key, ending_key)
    case = C.get_case(run.case_key)
    passed_checks = sum(1 for item in rows if item.get("success"))
    failed_checks = sum(1 for item in rows if not item.get("success"))
    reward = C.ending_reward(
        run.case_key, ending_key, int(run.danger or 0), 90 + secrets.randbelow(21),
        steps=len(rows), passed_checks=passed_checks,
    )
    if not ending or not reward:
        return False, "پایان پرونده نامعتبر است.", {}
    if int(reward["cash"]):
        player.cash = int(player.cash or 0) + int(reward["cash"])
    xp_result = await leveling.grant_xp(session, player, int(reward["xp"]), source="dark_world_case")
    profile.dark_xp = int(profile.dark_xp or 0) + int(reward["dark_xp"])
    profile.influence = max(0, int(profile.influence or 0) + int(reward["influence"]))
    profile.heat = min(D.HEAT_MAX, int(profile.heat or 0) + int(reward["heat"]))
    profile.intel = max(0, int(profile.intel or 0) + int(reward["intel"]))
    profile.cash_earned = int(profile.cash_earned or 0) + int(reward["cash"])
    if reward["success"]:
        profile.successes = int(profile.successes or 0) + 1
        profile.current_streak = int(profile.current_streak or 0) + 1
        profile.best_streak = max(int(profile.best_streak or 0), int(profile.current_streak))
    else:
        profile.failures = int(profile.failures or 0) + 1
        profile.current_streak = 0
    session.add(DarkWorldCaseLog(
        owner_id=int(uid), actor_id=int(run.actor_id), beneficiary_id=int(run.beneficiary_id),
        employment_contract_id=run.employment_contract_id,
        case_key=str(run.case_key), ending_key=ending_key,
        success=bool(reward["success"]), steps=len(rows),
        passed_checks=passed_checks,
        failed_checks=failed_checks,
        peak_danger=max([int(item.get("danger", 0)) for item in rows] + [0]),
        cash_reward=int(reward["cash"]), xp_reward=int(xp_result.get("gained") or 0),
        dark_xp_reward=int(reward["dark_xp"]), influence_delta=int(reward["influence"]),
        heat_delta=int(reward["heat"]), intel_delta=int(reward["intel"]),
        started_at=run.started_at, completed_at=_now(),
    ))
    team_note = await NPS.apply_mission_wear(session, uid, int(case.get("difficulty", 1)), bool(reward["success"]))
    await session.delete(run)
    await session.commit()
    step_payload.update({
        "ending": ending, "ending_key": ending_key, "reward": reward,
        "xp_result": xp_result, "case": case, "team_note": team_note,
    })
    return True, "پرونده بسته شد.", step_payload


async def abandon_case(session, uid: int) -> tuple[bool, str]:
    profile = await DS.get_profile(session, uid, create=False)
    run = await get_run(session, uid)
    if run is None:
        return False, "پرونده فعالی نداری."
    if profile:
        profile.heat = min(D.HEAT_MAX, int(profile.heat or 0) + 5)
        profile.influence = max(0, int(profile.influence or 0) - 5)
    await session.delete(run)
    await session.commit()
    return True, "پرونده رها شد؛ ورودی برنمی‌گردد، ۵ Heat اضافه و ۵ نفوذ کم شد."
