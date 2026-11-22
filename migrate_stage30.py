# -*- coding: utf-8 -*-
"""Stage 30 migration: fsm_states + alliance_permissions tables.

Both tables are auto-created at runtime as well, so running this script is
optional; it only makes the first start faster and safer.

usage:  python3 migrate_stage30.py
"""
import asyncio

from app.database.engine import engine, init_db


SQL = (
    """
    CREATE TABLE IF NOT EXISTS fsm_states (
        key TEXT PRIMARY KEY,
        state TEXT,
        data TEXT,
        updated_at TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS alliance_permissions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        alliance_id INTEGER NOT NULL,
        player_id INTEGER NOT NULL,
        perm_key TEXT NOT NULL
    )
    """,
    """
    CREATE UNIQUE INDEX IF NOT EXISTS uq_alliance_perm
        ON alliance_permissions (alliance_id, player_id, perm_key)
    """,
)


async def main() -> None:
    from sqlalchemy import text

    await init_db()
    async with engine.begin() as conn:
        for stmt in SQL:
            await conn.execute(text(stmt))
    print("stage 30 migration done")


if __name__ == "__main__":
    asyncio.run(main())
