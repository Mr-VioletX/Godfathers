# -*- coding: utf-8 -*-
"""Stage 86 / v1.8.2.9 city batch-building and population regression tests."""
from __future__ import annotations

import ast
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent
import sys
sys.path.insert(0, str(ROOT))

from app.data import mafia_city as C
from app.data.economy import MAX_PROF_LEVEL, subordinates_for_level
from app.data.professionals import PROFESSIONALS

version = (ROOT / "VERSION.txt").read_text(encoding="utf-8").strip()
assert tuple(int(part) for part in version.split(".")) >= (1, 8, 2, 9), version

# Root-cause proof: 40 max-level professionals were incorrectly copied into city population.
legacy_41m = len(PROFESSIONALS) * (subordinates_for_level(MAX_PROF_LEVEL) + 1)
assert len(PROFESSIONALS) == 40
assert subordinates_for_level(MAX_PROF_LEVEL) == 1_048_576
assert legacy_41m == 41_943_080
assert legacy_41m > C.POP_CAP

# New cities always start at 100 and enough small houses are derived from real capacity.
assert C.STARTING_POPULATION == 100
assert C.starting_house_count() == 17
assert C.starting_house_count() * C.HOUSING["small_house"]["residents"] >= C.STARTING_POPULATION
assert C.normalize_population_seed(100, 100) == (100, 100, False)
assert C.normalize_population_seed(legacy_41m, legacy_41m) == (100, 100, True)
# Preserve growth earned above the phantom seed while removing the phantom part.
assert C.normalize_population_seed(legacy_41m, 42_000_000) == (100, 57_020, True)
assert C.normalize_population_seed(0, 12_345) == (100, 12_345, True)
assert C.normalize_population_seed(100, 30_000_000) == (100, C.POP_CAP, True)
assert C.legacy_starter_house_count(legacy_41m) == 10_485_770

# Quantity parser accepts localized separators/digits and rejects unsafe values.
for raw, expected in [(1, 1), ("1,000", 1000), ("۱۰٬۰۰۰", 10_000), (10_000, 10_000)]:
    assert C.normalize_build_amount(raw) == expected
for raw in (None, True, 0, -1, 10_001, "2.5", "abc", ""):
    assert C.normalize_build_amount(raw) is None
assert C.BATCH_BUILD_PRESETS == (1, 5, 10, 25, 50, 100, 500, 1_000)

# Batch quotes scale exact per-unit cash/resources and keep one shared build duration.
unit = C.batch_build_quote("small_house", 1)
for amount in (1, 5, 100, 10_000):
    quote = C.batch_build_quote("small_house", amount)
    assert quote["cash"] == unit["cash"] * amount
    assert quote["resources"] == {key: value * amount for key, value in unit["resources"].items()}
    assert quote["seconds"] == unit["seconds"]
assert C.batch_build_quote("small_house", 0) == {}
assert C.batch_build_quote("small_house", 10_001) == {}
assert C.batch_build_quote("missing", 5) == {}

service_path = ROOT / "app/services/mafia_city_service.py"
service_source = service_path.read_text(encoding="utf-8")
service_tree = ast.parse(service_source)
service_functions = {
    node.name: node for node in service_tree.body
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
}
assert "effective_subs" not in service_source
assert "base_population = C.STARTING_POPULATION" in service_source
assert "sum(int(effective_subs" not in service_source
assert "for _ in range(amount)" not in ast.get_source_segment(service_source, service_functions["build_many"])

# Execute the real build_plan function with dependency-free fakes.
def compile_function(name: str, namespace: dict):
    node = service_functions[name]
    module = ast.Module(body=[node], type_ignores=[])
    ast.fix_missing_locations(module)
    exec(compile(module, str(service_path), "exec"), namespace)
    return namespace[name]

class Pending:
    def __init__(self, btype, qty, kind="build"):
        self.btype, self.qty, self.kind = btype, qty, kind

class PlanSession:
    pass

async def run_plan_tests():
    city = SimpleNamespace(id=7, population=100)
    player = SimpleNamespace(cash=10**18)
    counts = {"road": 1, "power": 1, "water": 1, "small_house": 17}
    stock = {key: 10**9 for key in C.RESOURCE_ORDER}
    pending_rows = []
    async def get_city(session, uid): return city
    async def get_player(session, uid): return player
    async def tick(session, obj): return counts
    async def buildings(session, city_id): return dict(counts)
    async def pending(session, city_id): return list(pending_rows)
    async def discount(session, uid, cost): return int(cost * 0.9), 10
    ns = {
        "C": C,
        "get_city": get_city,
        "_player": get_player,
        "tick": tick,
        "_buildings": buildings,
        "pending_builds": pending,
        "build_quote": C.batch_build_quote,
        "_discounted_cost": discount,
        "_resources": lambda obj: dict(stock),
    }
    build_plan = compile_function("build_plan", ns)
    ready, reason, plan = await build_plan(PlanSession(), 1, "small_house", 100)
    assert ready and reason == "ok"
    assert plan["amount"] == 100 and plan["after_ready"] == 117
    assert plan["cash"] == int(plan["cash_before_discount"] * 0.9)
    assert plan["discount_pct"] == 10

    # Pending units count toward an explicit welfare cap; no oversubscription.
    counts.clear(); counts.update({"bank": 1, "power": 1, "bourse": 5})
    pending_rows[:] = [Pending("bourse", 3)]
    ready, reason, plan = await build_plan(PlanSession(), 1, "bourse", 3)
    assert not ready and plan["pending"] == 3 and plan["cap"] == 10
    assert "فقط 2 واحد" in reason

    # Missing prerequisites and insufficient inventory block confirmation.
    counts.clear(); counts.update({"small_house": 17})
    stock.update({key: 0 for key in stock})
    ready, reason, plan = await build_plan(PlanSession(), 1, "small_house", 5)
    assert not ready
    assert "پیش‌نیاز ناقص" in reason and "کمبود منابع" in reason

asyncio.run(run_plan_tests())

# Execute the real build_many body: one payment, one queue row, one commit, any N.
async def run_atomic_test():
    plan = {
        "amount": 10_000, "cash": 123, "resources": {"stone": 45},
        "seconds": 3600, "discount_pct": 0,
    }
    city = SimpleNamespace(id=9)
    calls = {"spend": 0}
    async def build_plan(session, uid, btype, amount): return True, "ok", dict(plan)
    async def get_city(session, uid): return city
    async def spend(session, uid, city_obj, cash, resources):
        calls["spend"] += 1
        assert cash == 123 and resources == {"stone": 45}
        return True, "ok"
    class Queue:
        def __init__(self, **kwargs): self.__dict__.update(kwargs)
    class Session:
        def __init__(self): self.added=[]; self.commits=0
        def add(self, obj): self.added.append(obj)
        async def commit(self): self.commits += 1
    ns = {
        "build_plan": build_plan, "get_city": get_city, "_spend": spend,
        "CityBuildQueue": Queue, "datetime": datetime, "timedelta": timedelta, "C": C,
    }
    build_many = compile_function("build_many", ns)
    session = Session()
    ok, message = await build_many(session, 1, "small_house", 10_000)
    assert ok and "10,000" in message
    assert calls["spend"] == 1 and session.commits == 1 and len(session.added) == 1
    queued = session.added[0]
    assert queued.qty == 10_000 and queued.kind == "build" and queued.btype == "small_house"

asyncio.run(run_atomic_test())

# Execute legacy seed repair: 10,485,770 generated houses become 17, earned extras preserved.
async def run_repair_test():
    city = SimpleNamespace(id=3, base_population=legacy_41m, population=legacy_41m)
    row = SimpleNamespace(qty=C.legacy_starter_house_count(legacy_41m) + 7)
    class Session:
        def __init__(self): self.flushes=0; self.added=[]
        async def flush(self): self.flushes += 1
        def add(self, obj): self.added.append(obj)
    async def get_row(session, city_id, btype): return row
    ns = {"C": C, "_get_row": get_row, "MafiaCity": object, "MafiaBuilding": object}
    repair = compile_function("_normalize_city_population_seed", ns)
    counts = {"small_house": row.qty}
    session = Session()
    changed = await repair(session, city, counts)
    assert changed and city.base_population == 100 and city.population == 100
    assert row.qty == C.starting_house_count() + 7
    assert counts["small_house"] == C.starting_house_count() + 7
    assert session.flushes == 1

asyncio.run(run_repair_test())

# UI flow: rank-safe callback sizes, preset + custom + preview + confirm, no direct spend.
handler_source = (ROOT / "app/handlers/city.py").read_text(encoding="utf-8")
keyboard_source = (ROOT / "app/keyboards/city_menu.py").read_text(encoding="utf-8")
states_source = (ROOT / "app/states.py").read_text(encoding="utf-8")
for token in ("city:bq:", "city:bv:", "city:bx:", "city:bc:"):
    assert token in handler_source and token in keyboard_source
assert "CityStates.building_amount" in handler_source
assert "building_amount = State()" in states_source
assert 'callback_data=_cb(f"city:build:' not in keyboard_source
assert "build_confirm_menu" in handler_source
assert "pending.get(q.btype, 0) + max(1, int(q.qty or 1))" in handler_source

longest = max((key for cat in C.CATEGORIES.values() for key in cat["table"]), key=len)
uid = "1234567890123456789"
callbacks = (
    f"city:bq:{longest}:99:{uid}",
    f"city:bv:{longest}:10000:99:{uid}",
    f"city:bx:{longest}:99:{uid}",
    f"city:bc:{longest}:10000:99:{uid}",
)
assert all(len(callback.encode()) <= 64 for callback in callbacks)

# Full UTF-8/AST safety.
python_files = sorted(ROOT.rglob("*.py"))
for path in python_files:
    ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

print(f"OK: legacy 4^N root cause reproduced exactly ({legacy_41m:,})")
print("OK: fresh and repaired cities use 100 citizens and 17 starter houses")
print("OK: earned growth/houses above the corrupt seed are preserved")
print("OK: batch amount 1..10,000 supports presets, custom input and confirmation")
print("OK: exact cash/resources/caps are validated before payment")
print("OK: 10,000 units use one atomic payment, one queue row and one commit")
print(f"OK: {len(python_files)} Python files parsed")
