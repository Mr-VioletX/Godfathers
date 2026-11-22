# -*- coding: utf-8 -*-
"""v1.8.2.8 — pure competition qualification rules."""
from __future__ import annotations

UCL_QUALIFIER_LIMIT = 8
UCL_MIN_SOURCE_TEAMS = 8


def ucl_qualified_ranks(source_team_count: int) -> tuple[int, ...]:
    """Only the top eight of a completed Friday League earn UCL places.

    A source league with fewer than eight teams does not create a Champions
    League edition: admitting everybody would contradict the elite-only rule.
    """
    total = max(0, int(source_team_count))
    if total < UCL_MIN_SOURCE_TEAMS:
        return ()
    return tuple(range(1, min(UCL_QUALIFIER_LIMIT, total) + 1))


def is_ucl_rank_eligible(rank: int | None, source_team_count: int) -> bool:
    if rank is None:
        return False
    return int(rank) in ucl_qualified_ranks(source_team_count)


def ucl_period_key(friday_week_key: str) -> str:
    week = str(friday_week_key or "").strip()
    if not week:
        raise ValueError("Friday League week key is required")
    return f"UCL-{week}"


def source_week_from_ucl_period(period_key: str) -> str | None:
    key = str(period_key or "")
    return key[4:] if key.startswith("UCL-") and len(key) > 4 else None

def seeded_group_numbers(qualified_count: int, group_size: int = 4) -> tuple[int, ...]:
    """Snake-seed ranked qualifiers so adjacent top seeds enter different groups."""
    total = max(0, int(qualified_count))
    size = max(1, int(group_size))
    if total == 0 or total % size != 0:
        return ()
    group_count = total // size
    out: list[int] = []
    for index in range(total):
        row_no, col = divmod(index, group_count)
        out.append((col + 1) if row_no % 2 == 0 else (group_count - col))
    return tuple(out)

def select_ucl_qualifiers(ranked_rows):
    """Return only the earned top-eight rows, or none for an undersized league."""
    rows = tuple(ranked_rows)
    ranks = ucl_qualified_ranks(len(rows))
    return tuple(rows[rank - 1] for rank in ranks)
