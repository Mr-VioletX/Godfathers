# -*- coding: utf-8 -*-
"""v1.8.2.7 — clean, value-ranked football player catalogue.

The old PDF extraction mixed Persian names, duplicate/transposed roles and even
paragraphs of document text into the player list.  This catalogue is curated in
English and ranked deterministically from each player's historical peak market
value, the year of that peak, a football-market inflation index and a bounded
career score.  The model is intentionally transparent and testable.

Every real-money (toman) player is single-copy and can only be acquired through
an auction.  Common game-dollar cards remain repeatable/direct-purchase so new
clubs can always build a squad.
"""
from __future__ import annotations

import math
import re
import unicodedata
from typing import Iterable

CATALOG_VERSION = "2026.09-stage84"
CURRENT_MARKET_YEAR = 2026
TIER_ORDER = ("common", "rare", "epic", "legend", "mythic")
POSITION_ORDER = ("GK", "DEF", "MID", "FWD")
POSITION_FA = {"GK": "دروازه‌بان", "DEF": "مدافع", "MID": "هافبک", "FWD": "مهاجم"}
POSITION_EMOJI = {"GK": "🧤", "DEF": "🛡️", "MID": "🎯", "FWD": "⚡"}

# Approximate football-market price index, normalized to 2026.  Linear
# interpolation is used between anchors.  It reflects football-price inflation,
# not consumer CPI; the cap also prevents ancient-era cards from exploding.
MARKET_INFLATION_INDEX: dict[int, float] = {
    1960: 8.00, 1970: 7.00, 1980: 6.00, 1990: 4.50,
    2000: 3.00, 2005: 2.50, 2010: 2.00, 2015: 1.60,
    2020: 1.25, 2023: 1.12, 2026: 1.00,
}


def inflation_factor(peak_year: int) -> float:
    year = max(min(int(peak_year), CURRENT_MARKET_YEAR), min(MARKET_INFLATION_INDEX))
    anchors = sorted(MARKET_INFLATION_INDEX)
    if year <= anchors[0]:
        return MARKET_INFLATION_INDEX[anchors[0]]
    for left, right in zip(anchors, anchors[1:]):
        if left <= year <= right:
            ratio = (year - left) / (right - left)
            value = MARKET_INFLATION_INDEX[left] + ratio * (
                MARKET_INFLATION_INDEX[right] - MARKET_INFLATION_INDEX[left]
            )
            return round(value, 3)
    return 1.0


def adjusted_peak_value(peak_value_eur_m: float, peak_year: int) -> float:
    return round(max(0.0, float(peak_value_eur_m)) * inflation_factor(peak_year), 1)


def rank_from_market(adjusted_value_eur_m: float, peak_year: int, career_score: int) -> str:
    """Assign rank from adjusted peak value plus a bounded career tiebreaker.

    Mythic is deliberately reserved for pre-2006 all-time icons; Messi and
    Cristiano Ronaldo therefore remain in the expanded Legend catalogue as
    requested rather than becoming the only two entries in a special list.
    """
    value = float(adjusted_value_eur_m)
    legacy = max(0, min(100, int(career_score)))
    if int(peak_year) <= 2005 and legacy >= 98:
        return "mythic"
    if value >= 140.0 or legacy >= 91:
        return "legend"
    if value >= 60.0 or legacy >= 85:
        return "epic"
    if value >= 25.0 or legacy >= 78:
        return "rare"
    return "common"


OVERALL_RANGE_BY_TIER = {
    "common": (65, 74),
    "rare": (75, 82),
    "epic": (83, 90),
    "legend": (91, 96),
    "mythic": (97, 99),
}


def overall_from_market(adjusted_value_eur_m: float, career_score: int, tier: str | None = None) -> int:
    """Calculate OVR from adjusted value/career score, then keep ranks ordered."""
    value = max(0.0, float(adjusted_value_eur_m))
    market_rating = min(99.0, 60.0 + 24.0 * math.log10(1.0 + value / 8.0))
    overall = round(0.65 * market_rating + 0.35 * max(60, min(100, int(career_score))))
    overall = max(60, min(99, overall))
    if tier is not None:
        low, high = OVERALL_RANGE_BY_TIER[tier]
        overall = max(low, min(high, overall))
    return overall


def power_from_overall(overall: int, tier: str) -> int:
    ovr = int(overall)
    if tier == "common":
        return max(100, min(950, 100 + (ovr - 60) * 55))
    if tier == "rare":
        return max(1_000, min(4_200, 1_000 + (ovr - 74) * 320))
    if tier == "epic":
        return max(4_500, min(11_000, 4_500 + (ovr - 83) * 900))
    if tier == "legend":
        return max(12_000, min(25_500, 12_000 + (ovr - 90) * 2_200))
    return max(26_000, min(30_000, 26_000 + (ovr - 97) * 2_000))


def price_from_market(adjusted_value_eur_m: float, tier: str) -> tuple[int, str, bool, str]:
    value = max(0.0, float(adjusted_value_eur_m))
    if tier == "common":
        # Repeatable cards use game dollars and stay directly purchasable.
        return max(100_000_000, int(round(value * 20_000_000))), "game", False, "direct"
    floor = {"rare": 100_000, "epic": 500_000, "legend": 3_000_000, "mythic": 10_000_000}[tier]
    rate = {"rare": 7_500, "epic": 12_000, "legend": 25_000, "mythic": 50_000}[tier]
    return max(floor, int(round(value * rate))), "toman", True, "auction"


# (expected rank, English name, role, historical peak €m, peak year, career score)
_RAW: tuple[tuple[str, str, str, float, int, int], ...] = (
    # Common — repeatable/game-dollar foundation (8 per role)
    ("common", "Senne Lammens", "GK", 15, 2025, 75),
    ("common", "Altay Bayındır", "GK", 10, 2023, 74),
    ("common", "James Trafford", "GK", 18, 2025, 76),
    ("common", "Filip Jörgensen", "GK", 16, 2024, 76),
    ("common", "Łukasz Skorupski", "GK", 8, 2019, 74),
    ("common", "Alex Meret", "GK", 18, 2022, 76),
    ("common", "Freddie Woodman", "GK", 6, 2021, 72),
    ("common", "Sam Johnstone", "GK", 12, 2020, 74),
    ("common", "Ashley Phillips", "DEF", 8, 2025, 72),
    ("common", "Calvin Ramsay", "DEF", 10, 2022, 72),
    ("common", "Kiko Femenía", "DEF", 8, 2018, 74),
    ("common", "Luke Thomas", "DEF", 12, 2021, 74),
    ("common", "Japhet Tanganga", "DEF", 15, 2020, 75),
    ("common", "Brandon Williams", "DEF", 10, 2021, 73),
    ("common", "Max Aarons", "DEF", 18, 2021, 76),
    ("common", "Kevin Danso", "DEF", 18, 2022, 76),
    ("common", "Billy Gilmour", "MID", 18, 2024, 76),
    ("common", "Carney Chukwuemeka", "MID", 15, 2023, 74),
    ("common", "Fabio Miretti", "MID", 18, 2024, 76),
    ("common", "Oliver Skipp", "MID", 20, 2023, 76),
    ("common", "Tom Davies", "MID", 18, 2019, 75),
    ("common", "Lewis Miley", "MID", 20, 2025, 76),
    ("common", "Harvey Elliott", "MID", 22, 2025, 77),
    ("common", "Hannibal Mejbri", "MID", 12, 2023, 74),
    ("common", "Facundo Pellistri", "FWD", 10, 2023, 73),
    ("common", "Omari Forson", "FWD", 5, 2025, 70),
    ("common", "Dane Scarlett", "FWD", 7, 2024, 71),
    ("common", "Patson Daka", "FWD", 20, 2021, 76),
    ("common", "Chuba Akpom", "FWD", 15, 2023, 75),
    ("common", "Adam Armstrong", "FWD", 15, 2022, 75),
    ("common", "Samuel Iling-Junior", "FWD", 15, 2024, 74),
    ("common", "Neal Maupay", "FWD", 15, 2019, 75),

    # Rare — auction-only (6 per role)
    ("rare", "David Raya", "GK", 35, 2024, 82),
    ("rare", "Unai Simón", "GK", 35, 2022, 82),
    ("rare", "Gregor Kobel", "GK", 40, 2023, 83),
    ("rare", "Mike Maignan", "GK", 45, 2022, 84),
    ("rare", "Diogo Costa", "GK", 45, 2025, 84),
    ("rare", "Giorgi Mamardashvili", "GK", 40, 2025, 83),
    ("rare", "Ben White", "DEF", 50, 2022, 84),
    ("rare", "Marc Guéhi", "DEF", 45, 2025, 83),
    ("rare", "Nathan Aké", "DEF", 40, 2023, 83),
    ("rare", "Pau Torres", "DEF", 50, 2022, 84),
    ("rare", "Fikayo Tomori", "DEF", 50, 2023, 84),
    ("rare", "Pedro Porro", "DEF", 45, 2025, 83),
    ("rare", "Conor Gallagher", "MID", 50, 2025, 83),
    ("rare", "James Ward-Prowse", "MID", 40, 2020, 82),
    ("rare", "Mateo Kovačić", "MID", 45, 2021, 84),
    ("rare", "Hakan Çalhanoğlu", "MID", 45, 2023, 84),
    ("rare", "Teun Koopmeiners", "MID", 50, 2024, 84),
    ("rare", "Mikel Merino", "MID", 45, 2024, 83),
    ("rare", "Ivan Toney", "FWD", 50, 2023, 83),
    ("rare", "Jonathan David", "FWD", 50, 2025, 84),
    ("rare", "Marcus Thuram", "FWD", 50, 2025, 84),
    ("rare", "Jarrod Bowen", "FWD", 50, 2024, 84),
    ("rare", "Cody Gakpo", "FWD", 50, 2024, 84),
    ("rare", "Kaoru Mitoma", "FWD", 45, 2025, 83),

    # Epic — auction-only (6 per role)
    ("epic", "Ederson", "GK", 70, 2019, 89),
    ("epic", "André Onana", "GK", 55, 2023, 86),
    ("epic", "Jan Oblak", "GK", 100, 2018, 90),
    ("epic", "Marc-André ter Stegen", "GK", 90, 2018, 90),
    ("epic", "Gianluigi Donnarumma", "GK", 65, 2021, 89),
    ("epic", "Emiliano Martínez", "GK", 35, 2023, 88),
    ("epic", "Antonio Rüdiger", "DEF", 55, 2022, 87),
    ("epic", "William Saliba", "DEF", 80, 2025, 89),
    ("epic", "Joško Gvardiol", "DEF", 80, 2025, 88),
    ("epic", "Achraf Hakimi", "DEF", 75, 2024, 89),
    ("epic", "Rúben Dias", "DEF", 80, 2021, 90),
    ("epic", "Éder Militão", "DEF", 70, 2023, 88),
    ("epic", "Bernardo Silva", "MID", 100, 2020, 90),
    ("epic", "Frenkie de Jong", "MID", 90, 2019, 89),
    ("epic", "Martin Ødegaard", "MID", 110, 2024, 90),
    ("epic", "Bruno Fernandes", "MID", 90, 2021, 90),
    ("epic", "Jamal Musiala", "MID", 120, 2025, 90),
    ("epic", "Pedri", "MID", 120, 2025, 90),
    ("epic", "Son Heung-min", "FWD", 90, 2020, 90),
    ("epic", "Lautaro Martínez", "FWD", 110, 2024, 90),
    ("epic", "Victor Osimhen", "FWD", 120, 2023, 90),
    ("epic", "Khvicha Kvaratskhelia", "FWD", 90, 2025, 89),
    ("epic", "Ousmane Dembélé", "FWD", 100, 2025, 90),
    ("epic", "Riyad Mahrez", "FWD", 60, 2021, 88),

    # Legend — expanded to 40 English-name icons, including Messi and Ronaldo
    ("legend", "Gianluigi Buffon", "GK", 70, 2004, 97),
    ("legend", "Iker Casillas", "GK", 60, 2009, 96),
    ("legend", "Manuel Neuer", "GK", 75, 2015, 96),
    ("legend", "Petr Čech", "GK", 50, 2006, 94),
    ("legend", "Edwin van der Sar", "GK", 40, 2004, 93),
    ("legend", "Thibaut Courtois", "GK", 75, 2018, 92),
    ("legend", "Alisson Becker", "GK", 90, 2019, 92),
    ("legend", "Dida", "GK", 35, 2003, 92),
    ("legend", "David Seaman", "GK", 25, 1998, 91),
    ("legend", "Andoni Zubizarreta", "GK", 20, 1990, 91),
    ("legend", "Sergio Ramos", "DEF", 80, 2018, 97),
    ("legend", "Fabio Cannavaro", "DEF", 35, 2006, 94),
    ("legend", "Carles Puyol", "DEF", 45, 2009, 95),
    ("legend", "Roberto Carlos", "DEF", 40, 2002, 96),
    ("legend", "Alessandro Nesta", "DEF", 45, 2003, 95),
    ("legend", "Philipp Lahm", "DEF", 40, 2014, 95),
    ("legend", "Dani Alves", "DEF", 45, 2011, 95),
    ("legend", "Marcelo", "DEF", 70, 2018, 94),
    ("legend", "John Terry", "DEF", 50, 2006, 94),
    ("legend", "Rio Ferdinand", "DEF", 46, 2002, 94),
    ("legend", "Xavi", "MID", 65, 2010, 97),
    ("legend", "Andrés Iniesta", "MID", 70, 2012, 97),
    ("legend", "Luka Modrić", "MID", 55, 2018, 97),
    ("legend", "Toni Kroos", "MID", 80, 2018, 95),
    ("legend", "Sergio Busquets", "MID", 80, 2018, 95),
    ("legend", "Andrea Pirlo", "MID", 45, 2006, 95),
    ("legend", "Clarence Seedorf", "MID", 40, 2003, 93),
    ("legend", "Kaká", "MID", 70, 2007, 95),
    ("legend", "Kevin De Bruyne", "MID", 150, 2021, 95),
    ("legend", "Jude Bellingham", "MID", 180, 2025, 92),
    ("legend", "Lionel Messi", "FWD", 180, 2018, 100),
    ("legend", "Cristiano Ronaldo", "FWD", 120, 2014, 99),
    ("legend", "Neymar", "FWD", 180, 2018, 95),
    ("legend", "Kylian Mbappé", "FWD", 200, 2025, 94),
    ("legend", "Erling Haaland", "FWD", 220, 2026, 93),
    ("legend", "Thierry Henry", "FWD", 50, 2004, 97),
    ("legend", "Ronaldinho", "FWD", 80, 2006, 97),
    ("legend", "Luis Suárez", "FWD", 90, 2016, 96),
    ("legend", "Robert Lewandowski", "FWD", 90, 2021, 96),
    ("legend", "Karim Benzema", "FWD", 90, 2022, 96),

    # Mythic — pre-2006 all-time icons (5 per role)
    ("mythic", "Lev Yashin", "GK", 35, 1963, 100),
    ("mythic", "Dino Zoff", "GK", 25, 1982, 98),
    ("mythic", "Gordon Banks", "GK", 22, 1966, 98),
    ("mythic", "Peter Schmeichel", "GK", 35, 1993, 98),
    ("mythic", "Oliver Kahn", "GK", 45, 2002, 98),
    ("mythic", "Franz Beckenbauer", "DEF", 45, 1976, 100),
    ("mythic", "Paolo Maldini", "DEF", 50, 1995, 100),
    ("mythic", "Franco Baresi", "DEF", 35, 1989, 99),
    ("mythic", "Bobby Moore", "DEF", 30, 1966, 99),
    ("mythic", "Cafu", "DEF", 35, 2002, 98),
    ("mythic", "Diego Maradona", "MID", 70, 1987, 100),
    ("mythic", "Johan Cruyff", "MID", 55, 1974, 100),
    ("mythic", "Zinedine Zidane", "MID", 75, 2001, 100),
    ("mythic", "Michel Platini", "MID", 45, 1985, 99),
    ("mythic", "Zico", "MID", 45, 1982, 98),
    ("mythic", "Pelé", "FWD", 65, 1970, 100),
    ("mythic", "Ronaldo Nazário", "FWD", 70, 1997, 99),
    ("mythic", "Gerd Müller", "FWD", 45, 1974, 99),
    ("mythic", "Ferenc Puskás", "FWD", 40, 1960, 99),
    ("mythic", "Eusébio", "FWD", 40, 1965, 98),
)


def _build_catalog(rows: Iterable[tuple[str, str, str, float, int, int]]) -> dict[str, dict]:
    catalogue: dict[str, dict] = {}
    seen_names: set[str] = set()
    for index, (expected_tier, name, pos, peak_value, peak_year, career_score) in enumerate(rows, 1):
        key = f"v84p{index:03d}"  # New namespace prevents collisions with old sold/owned p### cards.
        normalized = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().casefold()
        normalized = re.sub(r"[^a-z0-9]+", "", normalized)
        if not normalized or normalized in seen_names:
            raise ValueError(f"duplicate/invalid player name: {name!r}")
        seen_names.add(normalized)
        if pos not in POSITION_ORDER:
            raise ValueError(f"invalid position for {name}: {pos}")
        adjusted = adjusted_peak_value(peak_value, peak_year)
        tier = rank_from_market(adjusted, peak_year, career_score)
        if tier != expected_tier:
            raise ValueError(
                f"rank audit failed for {name}: expected {expected_tier}, calculated {tier} "
                f"(adjusted €{adjusted}m, career={career_score})"
            )
        overall = overall_from_market(adjusted, career_score, tier)
        power = power_from_overall(overall, tier)
        price, currency, unique, sale_mode = price_from_market(adjusted, tier)
        catalogue[key] = {
            "key": key,
            "name": name,
            "pos": pos,
            "position_name": POSITION_FA[pos],
            "tier": tier,
            "overall": overall,
            "power": power,
            "peak_value_eur_m": float(peak_value),
            "peak_year": int(peak_year),
            "inflation_factor": inflation_factor(peak_year),
            "adjusted_value_eur_m": adjusted,
            "career_score": int(career_score),
            "price": price,
            "currency": currency,
            "unique": unique,
            "sale_mode": sale_mode,
        }
    return catalogue


PLAYERS: dict[str, dict] = _build_catalog(_RAW)


def get(key: str) -> dict | None:
    return PLAYERS.get(key)


def by_tier(tier: str) -> list[dict]:
    return [p for p in PLAYERS.values() if p["tier"] == tier]


def by_pos(pos: str) -> list[dict]:
    return [p for p in PLAYERS.values() if p["pos"] == pos]


def by_tier_and_pos(tier: str, pos: str | None = None) -> list[dict]:
    rows = by_tier(tier)
    if pos and pos != "ALL":
        rows = [p for p in rows if p["pos"] == pos]
    return sorted(rows, key=lambda p: (p["overall"], p["adjusted_value_eur_m"], p["name"]), reverse=True)


def legacy_card_spec(key: str) -> tuple[str, str, int] | None:
    """Structural fallback for an auction created before the v84 key namespace.

    Legacy rows are not returned by PLAYERS and therefore never appear in the
    cleaned market.  This only lets an already-running old auction finish safely.
    """
    if not re.fullmatch(r"p\d{3}", str(key or "")):
        return None
    from app.data.football_legacy_specs import LEGACY_CARD_SPECS

    return LEGACY_CARD_SPECS.get(str(key))


def starters_pack() -> list[dict]:
    """18 free Common cards: 2 GK + 6 DEF + 6 MID + 4 FWD."""
    commons = sorted(by_tier("common"), key=lambda p: (p["overall"], p["power"], p["name"]))

    def take(pos: str, amount: int) -> list[dict]:
        return [p for p in commons if p["pos"] == pos][:amount]

    return take("GK", 2) + take("DEF", 6) + take("MID", 6) + take("FWD", 4)


def audit_catalog() -> dict[str, object]:
    tier_counts = {tier: len(by_tier(tier)) for tier in TIER_ORDER}
    role_counts = {
        tier: {pos: len(by_tier_and_pos(tier, pos)) for pos in POSITION_ORDER}
        for tier in TIER_ORDER
    }
    toman = [p for p in PLAYERS.values() if p["currency"] == "toman"]
    return {
        "catalog_version": CATALOG_VERSION,
        "total": len(PLAYERS),
        "tier_counts": tier_counts,
        "role_counts": role_counts,
        "english_only": all(not re.search(r"[\u0600-\u06ff]", p["name"]) for p in PLAYERS.values()),
        "unique_names": len({p["name"].casefold() for p in PLAYERS.values()}) == len(PLAYERS),
        "toman_auction_only": all(p["unique"] and p["sale_mode"] == "auction" for p in toman),
    }
