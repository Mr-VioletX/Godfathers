# -*- coding: utf-8 -*-
"""Stage 87.1 — transactional Dark World engine."""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta
from types import SimpleNamespace

from sqlalchemy import select

from app.data import dark_world as D
from app.data import dark_world_npcs as N  # extends NPC catalog
from app.data import leveling
from app.models.dark_world import DarkWorldContractLog, DarkWorldProfile, DarkWorldRecruit
from app.models.player import Player


def _now() -> datetime:
    return datetime.utcnow()


async def get_player(session, uid: int) -> Player | None:
    return (await session.execute(
        select(Player).where(Player.tg_user_id == int(uid))
    )).scalar_one_or_none()


async def get_profile(session, uid: int, create: bool = False) -> DarkWorldProfile | None:
    profile = await session.get(DarkWorldProfile, int(uid))
    if profile is None and create:
        now = _now()
        profile = DarkWorldProfile(
            tg_user_id=int(uid), energy=D.ENERGY_MAX, heat=0,
            last_energy_at=now, last_heat_at=now,
        )
        session.add(profile)
        await session.flush()
    return profile


def access_message(player) -> str | None:
    if player is None:
        return "اول در چت خصوصی ربات /start را بزن."
    if int(player.level or 1) < D.ACCESS_LEVEL:
        return (
            f"🔒 دنیای سیاه از سطح {D.ACCESS_LEVEL} باز می‌شود.\n"
            f"سطح فعلی تو: {int(player.level or 1)}"
        )
    return None


def apply_recovery(profile: DarkWorldProfile, now: datetime | None = None) -> dict[str, int]:
    """Lazy, restart-safe energy regeneration and heat decay."""
    now = now or _now()
    before_energy = int(profile.energy or 0)
    before_heat = int(profile.heat or 0)

    if before_energy >= D.ENERGY_MAX:
        profile.energy = D.ENERGY_MAX
        profile.last_energy_at = now
    else:
        steps, advanced = D.recovery_steps(profile.last_energy_at, now, D.ENERGY_REGEN_SECONDS)
        profile.energy = min(D.ENERGY_MAX, before_energy + steps)
        profile.last_energy_at = now if int(profile.energy) >= D.ENERGY_MAX else advanced

    if before_heat <= 0:
        profile.heat = 0
        profile.last_heat_at = now
    else:
        steps, advanced = D.recovery_steps(profile.last_heat_at, now, D.HEAT_DECAY_SECONDS)
        profile.heat = max(0, before_heat - steps)
        profile.last_heat_at = now if int(profile.heat) <= 0 else advanced

    return {
        "energy_gained": max(0, int(profile.energy) - before_energy),
        "heat_lost": max(0, before_heat - int(profile.heat)),
    }


async def recruit_rows(session, uid: int) -> list[DarkWorldRecruit]:
    return list((await session.execute(
        select(DarkWorldRecruit)
        .where(DarkWorldRecruit.owner_id == int(uid))
        .order_by(DarkWorldRecruit.id)
    )).scalars().all())


async def recruit_keys(session, uid: int) -> set[str]:
    return {str(row.recruit_key) for row in await recruit_rows(session, uid)}


def active_remaining(profile: DarkWorldProfile, now: datetime | None = None) -> int:
    if not profile.active_contract_key or profile.active_ready_at is None:
        return 0
    return max(0, int((profile.active_ready_at - (now or _now())).total_seconds()))


def success_rate(profile: DarkWorldProfile) -> int:
    total = int(profile.successes or 0) + int(profile.failures or 0)
    return int(round(int(profile.successes or 0) * 100 / total)) if total else 0


async def hub_snapshot(session, uid: int) -> tuple[bool, str, dict]:
    player = await get_player(session, uid)
    blocked = access_message(player)
    if blocked:
        return False, blocked, {"player": player}
    profile = await get_profile(session, uid, create=True)
    apply_recovery(profile)
    recruits = await recruit_rows(session, uid)
    tier = D.rank_for(int(profile.influence or 0))
    return True, "ok", {
        "player": player, "profile": profile, "recruits": recruits,
        "tier": tier, "next_tier": D.next_rank(int(profile.influence or 0)),
        "remaining": active_remaining(profile),
    }


async def contract_preview(session, uid: int, contract_key: str, approach_key: str) -> tuple[bool, str, dict]:
    player = await get_player(session, uid)
    blocked = access_message(player)
    if blocked:
        return False, blocked, {}
    profile = await get_profile(session, uid, create=True)
    apply_recovery(profile)
    contract = D.get_contract(contract_key)
    approach = D.get_approach(approach_key)
    if not contract or not approach:
        return False, "قرارداد یا روش اجرای نامعتبر است.", {}
    from app.services import dark_world_npc_service as NPS
    team = await NPS.team_context(session, uid)
    keys = team["keys"]
    plan = D.contract_plan(
        contract_key, approach_key, heat=int(profile.heat or 0),
        streak=int(profile.current_streak or 0), recruit_keys=keys,
        team_effectiveness=team["effectiveness"], team_tactic=team["tactic"],
    )
    issues: list[str] = []
    if D.operation_locked(int(profile.heat or 0)):
        issues.append("Heat به ۸۰ رسیده؛ ابتدا در بخش تعقیب و مخفیگاه تهدید را خنثی کن.")
    if profile.active_contract_key:
        issues.append("یک عملیات فعال داری؛ اول نتیجهٔ آن را دریافت کن.")
    required = int(contract["required_influence"])
    if int(profile.influence or 0) < required:
        issues.append(f"برای این قرارداد {required:,} نفوذ لازم است.")
    if int(profile.energy or 0) < int(plan["energy"]):
        issues.append(f"کمبود انرژی: {int(plan['energy']) - int(profile.energy or 0)}")
    if int(profile.intel or 0) < int(plan["intel_cost"]):
        issues.append(f"کمبود اطلاعات: {int(plan['intel_cost']) - int(profile.intel or 0)}")
    if int(player.cash or 0) < int(plan["entry_cost"]):
        issues.append(f"کمبود پول ورودی: {int(plan['entry_cost']) - int(player.cash or 0):,}")
    plan.update({
        "issues": issues,
        "available_energy": int(profile.energy or 0),
        "available_intel": int(profile.intel or 0),
        "available_cash": int(player.cash or 0),
        "influence": int(profile.influence or 0),
        "recruit_keys": sorted(keys),
    })
    return not issues, "\n".join(issues) if issues else "ok", plan


async def start_contract(session, uid: int, contract_key: str, approach_key: str) -> tuple[bool, str]:
    ready, reason, plan = await contract_preview(session, uid, contract_key, approach_key)
    if not ready:
        return False, reason
    player = await get_player(session, uid)
    profile = await get_profile(session, uid, create=True)
    # A fresh validation after resolving the profile protects forged callbacks.
    if profile.active_contract_key:
        return False, "یک عملیات فعال داری."
    player.cash = int(player.cash or 0) - int(plan["entry_cost"])
    profile.energy = int(profile.energy or 0) - int(plan["energy"])
    profile.intel = int(profile.intel or 0) - int(plan["intel_cost"])

    roll_bp = secrets.randbelow(10_000)
    cash_factor = 90 + secrets.randbelow(21)
    outcome = D.resolve_plan(plan, roll_bp / 100.0, cash_factor)
    now = _now()
    profile.active_contract_key = contract_key
    profile.active_approach_key = approach_key
    profile.active_started_at = now
    profile.active_ready_at = now + timedelta(seconds=int(plan["duration"]))
    profile.active_success = bool(outcome["success"])
    profile.active_cash = int(outcome["cash"])
    profile.active_xp = int(outcome["xp"])
    profile.active_dark_xp = int(outcome["dark_xp"])
    profile.active_influence = int(outcome["influence"])
    profile.active_heat = int(outcome["heat"])
    profile.active_intel = int(outcome["intel"])
    profile.active_chance_bp = int(round(float(plan["chance"]) * 100))
    profile.active_roll_bp = int(roll_bp)
    profile.contracts_started = int(profile.contracts_started or 0) + 1
    await session.commit()
    contract = D.get_contract(contract_key)
    return True, (
        f"🌑 عملیات «{contract['name']}» آغاز شد.\n"
        f"⏱️ نتیجه پس از {D.fmt_duration(int(plan['duration']))} قابل دریافت است.\n"
        f"🎲 نتیجه همین حالا به‌صورت مخفی ثبت شد و با بازکردن دوباره تغییر نمی‌کند."
    )


def _clear_active(profile: DarkWorldProfile) -> None:
    profile.active_contract_key = None
    profile.active_approach_key = None
    profile.active_started_at = None
    profile.active_ready_at = None
    profile.active_success = None
    profile.active_cash = 0
    profile.active_xp = 0
    profile.active_dark_xp = 0
    profile.active_influence = 0
    profile.active_heat = 0
    profile.active_intel = 0
    profile.active_chance_bp = 0
    profile.active_roll_bp = 0


async def collect_contract(session, uid: int) -> tuple[bool, str]:
    player = await get_player(session, uid)
    profile = await get_profile(session, uid, create=False)
    blocked = access_message(player)
    if blocked:
        return False, blocked
    if profile is None or not profile.active_contract_key:
        return False, "عملیات فعالی برای دریافت نتیجه نداری."
    apply_recovery(profile)
    remaining = active_remaining(profile)
    if remaining > 0:
        return False, f"نتیجه هنوز آماده نیست؛ {D.fmt_duration(remaining)} مانده."

    contract_key = str(profile.active_contract_key)
    approach_key = str(profile.active_approach_key or "calculated")
    contract = D.get_contract(contract_key) or {"name": contract_key, "difficulty": 1}
    success = bool(profile.active_success)
    cash = max(0, int(profile.active_cash or 0))
    xp = max(0, int(profile.active_xp or 0))
    dark_xp = max(0, int(profile.active_dark_xp or 0))
    influence_delta = int(profile.active_influence or 0)
    heat_delta = max(0, int(profile.active_heat or 0))
    intel_delta = max(0, int(profile.active_intel or 0))
    started_at = profile.active_started_at or _now()
    chance_bp = int(profile.active_chance_bp or 0)
    roll_bp = int(profile.active_roll_bp or 0)

    if cash:
        player.cash = int(player.cash or 0) + cash
    xp_result = await leveling.grant_xp(session, player, xp, source="dark_world_contract")
    profile.dark_xp = int(profile.dark_xp or 0) + dark_xp
    profile.influence = max(0, int(profile.influence or 0) + influence_delta)
    profile.heat = min(D.HEAT_MAX, int(profile.heat or 0) + heat_delta)
    profile.intel = max(0, int(profile.intel or 0) + intel_delta)
    profile.cash_earned = int(profile.cash_earned or 0) + cash
    if success:
        profile.successes = int(profile.successes or 0) + 1
        profile.current_streak = int(profile.current_streak or 0) + 1
        profile.best_streak = max(int(profile.best_streak or 0), int(profile.current_streak))
    else:
        profile.failures = int(profile.failures or 0) + 1
        profile.current_streak = 0

    session.add(DarkWorldContractLog(
        owner_id=int(uid), contract_key=contract_key, approach_key=approach_key,
        difficulty=int(contract.get("difficulty", 1)), success=success,
        chance_bp=chance_bp, roll_bp=roll_bp, cash_reward=cash,
        xp_reward=int(xp_result.get("gained") or 0), dark_xp_reward=dark_xp,
        influence_delta=influence_delta, heat_delta=heat_delta,
        intel_delta=intel_delta, started_at=started_at, completed_at=_now(),
    ))
    from app.services import dark_world_npc_service as NPS
    team_note = await NPS.apply_mission_wear(session, uid, int(contract.get("difficulty", 1)), success)
    _clear_active(profile)
    await session.commit()

    if success:
        headline = f"✅ عملیات «{contract['name']}» موفق شد."
        economy = f"💵 غنیمت: +{cash:,}\n🗝️ نفوذ: +{influence_delta:,}"
    else:
        headline = f"❌ عملیات «{contract['name']}» شکست خورد؛ هزینهٔ ورود از دست رفت."
        economy = f"🗝️ نفوذ: {influence_delta:,}"
    return True, (
        f"{headline}\n\n{economy}\n"
        f"🌑 تجربهٔ سیاه: +{dark_xp:,}\n"
        f"👁️ اطلاعات: +{intel_delta:,}\n"
        f"🚨 گرما: +{heat_delta:,} → {int(profile.heat):,}/100"
        + leveling.xp_note(xp_result) + team_note
    )


async def hire_recruit(session, uid: int, recruit_key: str) -> tuple[bool, str]:
    recruit = D.get_recruit(recruit_key)
    if not recruit:
        return False, "نیروی نامعتبر است."
    player = await get_player(session, uid)
    blocked = access_message(player)
    if blocked:
        return False, blocked
    profile = await get_profile(session, uid, create=True)
    apply_recovery(profile)
    owned = await recruit_keys(session, uid)
    if recruit_key in owned:
        return False, "این نیرو قبلاً استخدام شده است."
    required = int(recruit["required_influence"])
    if int(profile.influence or 0) < required:
        return False, f"برای استخدام این نیرو {required:,} نفوذ لازم است."
    cost = int(recruit["cost"])
    if int(player.cash or 0) < cost:
        return False, f"پول کافی نداری؛ هزینهٔ استخدام {cost:,} است."
    player.cash = int(player.cash or 0) - cost
    session.add(DarkWorldRecruit(owner_id=int(uid), recruit_key=recruit_key))
    xp_result = await leveling.grant_xp(
        session, player, max(300, min(3_000, cost // 500_000)), source="dark_world_recruit",
    )
    await session.commit()
    return True, (
        f"✅ {recruit['icon']} «{recruit['name']}» به شبکهٔ تو پیوست.\n"
        f"اثر دائمی: {recruit['description']}\n"
        f"💵 هزینه: {cost:,}"
        + leveling.xp_note(xp_result)
    )


async def ranking(session, uid: int) -> dict:
    rows = (await session.execute(
        select(DarkWorldProfile, Player.name)
        .join(Player, Player.tg_user_id == DarkWorldProfile.tg_user_id)
        .order_by(
            DarkWorldProfile.influence.desc(), DarkWorldProfile.dark_xp.desc(),
            DarkWorldProfile.successes.desc(), DarkWorldProfile.tg_user_id.asc(),
        )
    )).all()
    entries = [
        SimpleNamespace(
            uid=int(profile.tg_user_id), name=str(name or "بی‌نام"),
            influence=int(profile.influence or 0), dark_xp=int(profile.dark_xp or 0),
            successes=int(profile.successes or 0), tier=D.rank_for(int(profile.influence or 0)),
        )
        for profile, name in rows
    ]
    my_rank = next((index for index, entry in enumerate(entries, start=1) if entry.uid == int(uid)), None)
    return {"entries": entries[:D.RANKING_LIMIT], "total": len(entries), "my_rank": my_rank}
