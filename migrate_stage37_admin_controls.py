# -*- coding: utf-8 -*-
import asyncio
from app.database.engine import engine, init_models
from app.models.admin import GameRestriction, GameNumberSetting  # noqa

async def main():
    await init_models()
    print("✅ admin control/game number tables are ready.")
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
