# -*- coding: utf-8 -*-
"""Stage 87.2 / v1.8.3.1 branching Dark World case tests (dependency-free)."""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from app.data import dark_world as D
from app.data import dark_world_cases as C

version = tuple(map(int, (ROOT / "VERSION.txt").read_text(encoding="utf-8").strip().split(".")))
assert version >= (1, 8, 3, 1)

# Three complete, reachable branching stories with multiple outcomes.
assert C.CASE_ORDER == ("midnight_train", "masked_ball", "glass_vault")
assert C.validate_case_graph() == []
assert [C.CASES[key]["difficulty"] for key in C.CASE_ORDER] == [2, 3, 4]
assert [C.CASES[key]["base_xp"] for key in C.CASE_ORDER] == sorted(C.CASES[key]["base_xp"] for key in C.CASE_ORDER)
for case_key in C.CASE_ORDER:
    case = C.CASES[case_key]
    nodes = C.NODES[case_key]
    endings = case["endings"]
    assert len(nodes) >= 5 and len(endings) == 4
    assert sum(bool(item["success"]) for item in endings.values()) == 3
    assert case["energy"] > 0 and case["intel_cost"] > 0 and case["entry_cost"] > 0
    seen_nodes = {case["start_node"]}
    seen_endings = set()
    frontier = [case["start_node"]]
    all_choice_keys = []
    while frontier:
        node_key = frontier.pop()
        node = nodes[node_key]
        assert len(node["choices"]) >= 2
        for choice_key, choice in node["choices"].items():
            all_choice_keys.append(choice_key)
            for required in ("skill", "target", "success", "failure", "success_text", "failure_text"):
                assert required in choice
            assert choice["skill"] in C.SKILL_LABELS and 50 <= int(choice["target"]) <= 95
            for destination in (choice["success"], choice["failure"]):
                if destination.startswith("end:"):
                    seen_endings.add(destination[4:])
                elif destination not in seen_nodes:
                    seen_nodes.add(destination); frontier.append(destination)
    assert seen_nodes == set(nodes), (case_key, seen_nodes, set(nodes))
    assert seen_endings == set(endings), (case_key, seen_endings, set(endings))
    assert len(all_choice_keys) == len(set(all_choice_keys)), f"stale callback collision in {case_key}"

# Skill tests respond to level, internal rank, Heat, Danger, recruit, Momentum and a compatible tool.
choice = C.get_choice("midnight_train", "platform", "manifest")
base = C.choice_chance(choice, 50, 75, 0, 0, 0, (), None)
elite = C.choice_chance(choice, 60, 8000, 0, 0, 0, ("fixer",), "disguise")
hot = C.choice_chance(choice, 50, 75, 100, 0, 0, (), None)
dangerous = C.choice_chance(choice, 50, 75, 0, 0, 10, (), None)
momentum = C.choice_chance(choice, 50, 75, 0, 12, 0, (), None)
incompatible = C.choice_chance(choice, 50, 75, 0, 0, 0, (), "jammer")
assert elite["chance"] > base["chance"] > hot["chance"]
assert momentum["chance"] > base["chance"] > dangerous["chance"]
assert elite["tool_applies"] and elite["tool_bonus"] == C.TOOLS["disguise"]["bonus"]
assert not incompatible["tool_applies"] and incompatible["tool_bonus"] == 0

# A fixed chance+roll is deterministic and failure can branch instead of always ending the run.
win = C.resolve_choice(choice, base, 0.0, 0, 0)
lose = C.resolve_choice(choice, base, 99.99, 0, 0)
assert win["success"] and win["destination"] == "cargo"
assert not lose["success"] and lose["destination"] == "inspector"
assert C.resolve_choice(choice, base, 0.0, 0, 0) == win
assert C.MOMENTUM_MIN <= lose["momentum"] <= C.MOMENTUM_MAX
assert C.DANGER_MIN <= lose["danger"] <= C.DANGER_MAX

# Outcome XP scales with difficulty and progress; late failure still grants learning XP.
perfect_rewards = [C.ending_reward(key, next(k for k, v in C.CASES[key]["endings"].items() if v["success"]), 0, 100) for key in C.CASE_ORDER]
assert [r["xp"] for r in perfect_rewards] == sorted(r["xp"] for r in perfect_rewards)
for case_key in C.CASE_ORDER:
    endings = C.CASES[case_key]["endings"]
    success_key = next(key for key, item in endings.items() if item["success"])
    failure_key = next(key for key, item in endings.items() if not item["success"])
    success = C.ending_reward(case_key, success_key, 0, 100)
    failure = C.ending_reward(case_key, failure_key, 0, 100)
    risky = C.ending_reward(case_key, success_key, 10, 100)
    assert success["cash"] > 0 == failure["cash"]
    assert 100 <= failure["xp"] < success["xp"]
    assert risky["cash"] > success["cash"]
    early_failure = C.ending_reward(case_key, failure_key, 3, 100, steps=1, passed_checks=0)
    late_failure = C.ending_reward(case_key, failure_key, 3, 100, steps=5, passed_checks=3)
    assert late_failure["xp"] > early_failure["xp"] >= 100

# Consumables are bounded, single-use in the service, and cover all four skills.
assert C.TOOL_MAX_QTY == 5 and len(C.TOOL_ORDER) == 4
covered = {skill for key in C.TOOL_ORDER for skill in C.TOOLS[key]["skills"]}
assert covered == set(C.SKILL_LABELS)

model = (ROOT / "app/models/dark_world.py").read_text(encoding="utf-8")
service = (ROOT / "app/services/dark_world_case_service.py").read_text(encoding="utf-8")
handler = (ROOT / "app/handlers/dark_world_cases.py").read_text(encoding="utf-8")
keyboard = (ROOT / "app/keyboards/dark_world_case_menu.py").read_text(encoding="utf-8")
bot = (ROOT / "bot.py").read_text(encoding="utf-8")
roadmap = (ROOT / "STAGE87_DARK_WORLD_ROADMAP.md").read_text(encoding="utf-8")

# Restart-safe run, choice history, inventory and immutable completion audit.
for table in ("dark_world_case_runs", "dark_world_tool_inventory", "dark_world_case_logs"):
    assert table in model
for field in ("history_json", "node_key", "momentum", "danger", "selected_tool_key", "expires_at"):
    assert field in model
for future_field in ("actor_id", "beneficiary_id", "employment_contract_id"):
    assert model.count(future_field) >= 2 and future_field in service
assert "chance_bp" in service and "roll_bp" in service and "history_json" in service
assert "secrets.randbelow(10_000)" in service and "leveling.grant_xp" in service
assert "source=\"dark_world_case\"" in service and "source=\"dark_world_tool\"" in service
assert "tool_row.qty = max(0" in service and "await session.delete(run)" in service

# Every economic mutation is owner-bound, debounced and guarded by a persistent operation id.
assert "from app.handlers import dark_world_cases" in bot and "include_router(dark_world_cases.router)" in bot
for route in ("dwc:hub", "dwc:list", "dwc:case:", "dwc:start:", "dwc:choice:", "dwc:tools", "dwc:tool:", "dwc:shop", "dwc:buy:", "dwc:abandon"):
    assert route in handler or route in keyboard
assert "economic_operation" in handler and "DuplicateOperation" in handler and "BusyOperation" in handler
for op in ("dwc-start:{callback.id}", "dwc-choice:{callback.id}", "dwc-buy:{callback.id}", "dwc-abandon:{callback.id}"):
    assert op in handler
assert "ensure_owner" in handler and "with_owner" in keyboard

# Clarified Stage 87.5 is explicitly user-to-user paid work, separate from NPC recruits.
for phrase in ("بازار کار و استخدام کاربران", "کارفرما", "کاربر دیگر", "escrow", "self-hire", "ضدپول‌شویی"):
    assert phrase in roadmap or phrase in (ROOT / "app/handlers/dark_world.py").read_text(encoding="utf-8")

# Owner suffix included: every generated callback remains below Telegram's 64-byte limit.
uid = "1234567890123456789"
callbacks = [f"dwc:start:{case_key}:{uid}" for case_key in C.CASE_ORDER]
callbacks += [f"dwc:case:{case_key}:{uid}" for case_key in C.CASE_ORDER]
callbacks += [f"dwc:buy:{tool_key}:{uid}" for tool_key in C.TOOL_ORDER]
callbacks += [f"dwc:tool:{tool_key}:{uid}" for tool_key in C.TOOL_ORDER]
for case_key in C.CASE_ORDER:
    callbacks += [f"dwc:choice:{choice_key}:{uid}" for node in C.NODES[case_key].values() for choice_key in node["choices"]]
assert max(len(value.encode("utf-8")) for value in callbacks) <= 64

# Every Python file remains valid UTF-8 / AST.
files = sorted(ROOT.rglob("*.py"))
for path in files:
    ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

print("OK: 3 fully reachable branching cases, 18+ nodes and 12 distinct endings")
print("OK: skill checks react to level, rank, Heat, Danger, Momentum, recruits and tools")
print("OK: persistent choices/rolls block restart rerolls and stale callback reuse")
print("OK: consumable tool inventory/shop and owner-bound economic guards")
print("OK: difficulty-scaled XP, partial outcomes and high-risk cash premium")
print("OK: actor/beneficiary/employment fields preserve Stage 87.5 architecture")
print(f"OK: {len(files)} Python files parsed")
