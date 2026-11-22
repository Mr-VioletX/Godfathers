# -*- coding: utf-8 -*-
"""Stage 85 / v1.8.2.8 injury balance and UCL qualification tests."""
from __future__ import annotations

import ast
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from app.data import football_competitions as COMP
from app.data import football_progress as PROG

version = (ROOT / "VERSION.txt").read_text(encoding="utf-8").strip()
assert tuple(int(part) for part in version.split(".")) >= (1, 8, 2, 8), version

# --- Team-level injury model ---
assert PROG.INJURY_TEAM_BASE_PCT == 4.0
assert PROG.INJURY_TEAM_MAX_PCT == 10.0
assert PROG.INJURY_HEALTHY_FLOOR == 11
assert PROG.team_injury_chance(0, 1) == 4.0
assert PROG.team_injury_chance(50, 1) == 4.0
assert PROG.player_equivalent_injury_chance(4.0, 20) == 0.2
assert PROG.team_injury_chance(100, 3, "full_attack") <= 10.0
assert PROG.team_injury_chance(75, 3, "full_defense") < PROG.team_injury_chance(75, 3, "full_attack")

# No injury can reduce the healthy roster below eleven.
assert PROG.roll_team_injury_index([20] * 11, 100.0, random.Random(1)) is None
forced = PROG.roll_team_injury_index(
    [20] * 11, 100.0, random.Random(1), healthy_roster_size=12
)
assert forced is not None and 0 <= forced < 11

# One call returns either no event or exactly one selected player, never N rolls.
for seed in range(2_000):
    outcome = PROG.roll_team_injury_index([15] * 20, 4.0, random.Random(seed))
    assert outcome is None or 0 <= outcome < 20

# Monte Carlo validates ~4% TEAM events, i.e. ~0.2% equivalent per card for 20 cards.
rng = random.Random(20260902)
trials = 100_000
injuries = sum(
    PROG.roll_team_injury_index([20] * 20, 4.0, rng) is not None
    for _ in range(trials)
)
rate = injuries * 100 / trials
assert 3.75 <= rate <= 4.25, rate
assert injuries / trials / 20 < 0.0022

# Fatigued cards are more likely only after the single team roll succeeds.
rng = random.Random(85)
counts = [0] * 12
for _ in range(20_000):
    picked = PROG.roll_team_injury_index([0] * 11 + [100], 100.0, rng)
    assert picked is not None
    counts[picked] += 1
assert counts[-1] > 3 * (sum(counts[:-1]) / 11)

# Source inspection ensures the service does not call injury chance inside every card roll.
progress_source = (ROOT / "app/services/football_progress.py").read_text(encoding="utf-8")
progress_tree = ast.parse(progress_source)
train_fn = next(node for node in progress_tree.body if isinstance(node, ast.AsyncFunctionDef) and node.name == "train_session")
called_attrs = [
    node.func.attr
    for node in ast.walk(train_fn)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
]
assert called_attrs.count("team_injury_chance") == 1
assert called_attrs.count("roll_team_injury_index") == 1
assert "injury_chance" not in called_attrs
injury_writes = [
    node for node in ast.walk(train_fn)
    if isinstance(node, ast.Assign)
    and any(isinstance(target, ast.Attribute) and target.attr == "injured_until" for target in node.targets)
]
assert len(injury_writes) == 1

# --- UCL is earned exclusively through the previous completed Friday League ---
assert COMP.UCL_QUALIFIER_LIMIT == 8
assert COMP.UCL_MIN_SOURCE_TEAMS == 8
assert COMP.ucl_qualified_ranks(7) == ()
assert COMP.ucl_qualified_ranks(8) == tuple(range(1, 9))
assert COMP.ucl_qualified_ranks(24) == tuple(range(1, 9))
assert COMP.is_ucl_rank_eligible(1, 24)
assert COMP.is_ucl_rank_eligible(8, 24)
assert not COMP.is_ucl_rank_eligible(9, 24)
assert not COMP.is_ucl_rank_eligible(None, 24)
assert COMP.select_ucl_qualifiers(range(1, 25)) == tuple(range(1, 9))
assert COMP.select_ucl_qualifiers(range(1, 8)) == ()
assert COMP.ucl_period_key("2026-W36") == "UCL-2026-W36"
assert COMP.source_week_from_ucl_period("UCL-2026-W36") == "2026-W36"
assert COMP.seeded_group_numbers(8, 4) == (1, 2, 2, 1, 1, 2, 2, 1)
assert COMP.seeded_group_numbers(7, 4) == ()

ucl_source = (ROOT / "app/services/football_ucl.py").read_text(encoding="utf-8")
friday_source = (ROOT / "app/services/football_friday.py").read_text(encoding="utf-8")
handler_source = (ROOT / "app/handlers/football.py").read_text(encoding="utf-8")
live_source = (ROOT / "app/services/football_live.py").read_text(encoding="utf-8")
assert "latest_completed_season" in ucl_source
assert "select_ucl_qualifiers(table)" in ucl_source
assert 'season.status = "cancelled"' in ucl_source
assert 'if not status["eligible"]' in ucl_source
assert "top eight" in ucl_source
assert "latest_completed_season" in friday_source
assert "🌟 سهمیه UCL" in handler_source
assert "ثبت‌نام عمومی حذف شده" in handler_source
assert 'text="📝 ثبت‌نام در UCL"' not in handler_source
assert 'if m.mode == "ucl"' in live_source
assert "FootballUclFixture as FixtureModel" in live_source
assert "FootballLeagueFixture as FixtureModel" in live_source

# Full UTF-8/AST safety.
python_files = sorted(ROOT.rglob("*.py"))
for path in python_files:
    ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

print(f"OK: team injury simulation {rate:.3f}% (20-player equivalent {rate/20:.3f}%)")
print("OK: at most one injury per training session and healthy floor is 11")
print("OK: fatigue/style modifiers stay inside the 0.5%..10% team cap")
print("OK: only Friday League ranks 1..8 qualify for UCL")
print("OK: UCL entries are auto-seeded and public registration is removed")
print("OK: UCL live results close the correct fixture model")
print(f"OK: {len(python_files)} Python files parsed; version {version} retains stage 85")
