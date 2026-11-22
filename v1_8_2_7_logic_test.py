# -*- coding: utf-8 -*-
"""Stage 84 / v1.8.2.7 football catalogue and market regression checks."""
from __future__ import annotations

import ast
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from app.data import football_players as FP
from app.data import football_progress as FPROG

version = (ROOT / "VERSION.txt").read_text(encoding="utf-8").strip()
version_parts = tuple(int(part) for part in version.split("."))
assert version_parts >= (1, 8, 2, 7), version

audit = FP.audit_catalog()
assert audit["total"] == 140
assert audit["tier_counts"] == {
    "common": 32, "rare": 24, "epic": 24, "legend": 40, "mythic": 20
}
assert audit["english_only"] and audit["unique_names"] and audit["toman_auction_only"]

# Every rank has a meaningful menu for every football role.
for tier in FP.TIER_ORDER:
    for pos in FP.POSITION_ORDER:
        assert audit["role_counts"][tier][pos] >= 5, (tier, pos)

# English/canonical names only, with no duplicate after accent/punctuation folding.
def folded(name: str) -> str:
    text = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().casefold()
    return re.sub(r"[^a-z0-9]+", "", text)

names = [p["name"] for p in FP.PLAYERS.values()]
assert len(names) == len({folded(name) for name in names})
assert not any(re.search(r"[\u0600-\u06ff]", name) for name in names)
assert not any("�" in name or len(name) > 40 for name in names)
assert not any(key.startswith("p") for key in FP.PLAYERS)  # old sold-card namespace is isolated

# Legendary catalogue is broad and roles are corrected.
legends = FP.by_tier("legend")
legend_names = {p["name"] for p in legends}
assert len(legends) == 40
assert {"Lionel Messi", "Cristiano Ronaldo", "Ronaldinho", "Thierry Henry"} <= legend_names
assert FP.by_tier_and_pos("legend", "FWD")
assert next(p for p in legends if p["name"] == "Iker Casillas")["pos"] == "GK"
assert next(p for p in legends if p["name"] == "Rio Ferdinand")["pos"] == "DEF"
assert next(p for p in legends if p["name"] == "Xavi")["pos"] == "MID"

# Rank, OVR, power and price must all be reproducible from the market model.
for key, player in FP.PLAYERS.items():
    adjusted = FP.adjusted_peak_value(player["peak_value_eur_m"], player["peak_year"])
    assert adjusted == player["adjusted_value_eur_m"], key
    assert FP.rank_from_market(adjusted, player["peak_year"], player["career_score"]) == player["tier"]
    assert FP.overall_from_market(adjusted, player["career_score"], player["tier"]) == player["overall"]
    assert FP.power_from_overall(player["overall"], player["tier"]) == player["power"]
    price, currency, unique, sale_mode = FP.price_from_market(adjusted, player["tier"])
    assert (price, currency, unique, sale_mode) == (
        player["price"], player["currency"], player["unique"], player["sale_mode"]
    )
    assert 60 <= player["overall"] <= 99

# OVR bands are strictly ordered, so a lower rank can never outrank a higher one.
for lower, higher in zip(FP.TIER_ORDER, FP.TIER_ORDER[1:]):
    assert max(p["overall"] for p in FP.by_tier(lower)) < min(
        p["overall"] for p in FP.by_tier(higher)
    ), (lower, higher)

assert FP.inflation_factor(1980) > FP.inflation_factor(2000) > FP.inflation_factor(2020)
assert all(p["sale_mode"] == "direct" and not p["unique"] for p in FP.by_tier("common"))
assert all(
    p["currency"] == "toman" and p["sale_mode"] == "auction" and p["unique"]
    for p in FP.PLAYERS.values() if p["tier"] != "common"
)

# Starter squad remains formation-safe after the catalogue rebuild.
starters = FP.starters_pack()
assert len(starters) == 18
assert {pos: sum(p["pos"] == pos for p in starters) for pos in FP.POSITION_ORDER} == {
    "GK": 2, "DEF": 6, "MID": 6, "FWD": 4
}

# Internal stadium indexes 0..9 display as levels 1..10; level 10 is exactly 100bn.
assert FPROG.STADIUM_LEVEL_COUNT == 10
assert FPROG.STADIUM_MAX_LEVEL == 9
assert FPROG.stadium_display_level(0) == 1
assert FPROG.stadium_display_level(9) == 10
assert FPROG.STADIUM_LEVELS[-1] == (125_000, 100_000_000_000)
costs = [cost for _capacity, cost in FPROG.STADIUM_LEVELS]
assert costs == sorted(costs) and costs[-1] == 100_000_000_000

# Static integration checks keep the Telegram menu dependency-free in offline QA.
handler_source = (ROOT / "app/handlers/football.py").read_text(encoding="utf-8")
market_source = (ROOT / "app/services/football_market.py").read_text(encoding="utf-8")
assert 'sub == "role"' in handler_source
assert 'fb:market:role:{tier}:{pos}' in handler_source
assert 'FP.POSITION_ORDER' in handler_source
assert 'player_row["sale_mode"] == "direct"' in handler_source
assert 'p.get("sale_mode") != "auction"' in handler_source
assert 'p["currency"] != "toman" or p.get("sale_mode") != "auction"' in market_source

# All Python sources remain syntactically valid UTF-8.
python_files = sorted(ROOT.rglob("*.py"))
for path in python_files:
    ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

print(f"OK: clean English catalogue ({len(FP.PLAYERS)} unique players)")
print("OK: all five ranks expose GK/DEF/MID/FWD filters")
print("OK: Legend contains 40 correctly positioned icons including Messi and Ronaldo")
print("OK: rank/OVR/power are reproducible from peak value + football inflation")
print("OK: every toman player is single-copy and auction-only")
print("OK: stadium level 10 is capped at 100,000,000,000 game dollars")
print(f"OK: {len(python_files)} Python files parsed; version {version} retains stage 84")
