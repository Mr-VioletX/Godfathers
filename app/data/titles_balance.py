# -*- coding: utf-8 -*-
"""بازتنظیم شرط القاب — v1.7.6 (منطق واقعی بازی فعلی).

آستانه‌ها بر اساس آمارهایی که واقعاً شمرده می‌شوند (PlayerStats + stats_bridge):
  thefts/loot, spy, battle/mafia wins, cities, countries, military_power,
  level/capital proxies, active_days, streaks.

القاب رویدادی (stat=None) دست‌نخورده می‌مانند و فقط با grant/ادمین می‌آیند.
"""

BALANCE: dict[str, int] = {
    # ── زنانه ──
    "queen_of_shadows": 80,          # spy_success
    "lilith": 1,                     # countries_founded
    "freya": 40,                     # war_assists
    "lagertha": 120,                 # mafia_wins
    "goddess_of_war": 200,           # battle_wins
    "dark_empress": 8,               # cities_controlled / related
    "lady_of_valhalla": 40_000,      # military_power واقعی
    "lady_of_shadows": 140,          # sabotage/spy mix
    "lady_of_lightning": 60,
    "fire_queen": 15,
    "lady_of_death": 40,
    "queen_of_vengeance": 15,
    "lady_of_storm": 40,             # country wars rare
    "goddess_of_economy": 5_000_000_000,
    "golden_lady": 80,
    "queen_of_wolves": 220,
    "lady_of_night": 120,
    "crowned_of_nation": 40,
    "ice_lady": 20,
    "goddess_of_darkness": 300,
    "ruler_of_fate": 40,
    "crown_of_olympus_f": 3,
    # ── مردانه ──
    "god_of_war": 80,
    "hades": 600,
    "ares": 160,
    "thor": 120,
    "odin": 20,
    "loki": 150,
    "anubis": 120,
    "horus": 1,
    "ragnar": 60,
    "floki": 40,
    "bjorn": 20,
    "ivar": 80,
    "leonidas": 80,
    "achilles": 140,
    "great_devil": 600,
    "mafia_sultan": 40,
    "ruler_of_olympus": 3,
    "lord_of_thunder": 150,
    "king_of_valhalla": 40_000,
    # ── مشترک ──
    "world_conqueror": 6,
    "immortal": 180,                 # active_days realistic
    "legend": 80,
    "destroyer": 300,
    "king_of_economy": 50_000_000_000,
    # ── زنانه رده۲ ──
    "athena": 180,
    "valkyrie": 120,
    "medusa": 180,
    "hecate": 220,
    "nemesis": 40,
    "persephone": 10,
    "aphrodite": 70,
    "bastet": 120,
    "ishtar": 8_000_000_000,
    "sekhmet": 260,
    "morgana": 3,
    "artemis": 60,
    "hel": 90,
    "circe": 180,
    # ── مردانه رده۲ ──
    "kratos": 300,
    "heracles": 80,
    "apollo": 20,
    "hermes": 220,
    "tyr": 180,
    "fenrir": 140,
    "set_god": 700,
    "ra": 40,
    "spartacus": 70,
    "genghis": 8,
    "caesar": 35,
    "hannibal": 90,
    "belial": 1_000,
    "gilgamesh": 70,
    # ── مشترک رده۲ ──
    "titan": 3,
    "orion": 600,
    "cronus": 365,
    "gaia": 20,
    "nyx": 320,
    "chimera": 300,
    "leviathan": 35,
    "behemoth": 600,
    "cerberus": 180,
    "undisputed_king": 70,
}

OP_OVERRIDES: dict[str, str] = {}


def apply_balance(titles: list[dict]) -> int:
    """بازتنظیم value/op روی TITLES؛ تعداد تغییر را برمی‌گرداند."""
    changed = 0
    for t in titles:
        key = t.get("key")
        if key in BALANCE and t.get("stat"):
            new_val = BALANCE[key]
            if t.get("value") != new_val:
                t["value"] = new_val
                changed += 1
            if key in OP_OVERRIDES and t.get("op") != OP_OVERRIDES[key]:
                t["op"] = OP_OVERRIDES[key]
                changed += 1
    return changed
