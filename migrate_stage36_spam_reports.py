# -*- coding: utf-8 -*-
import asyncio
from app.database.engine import engine, init_models
from app.models.admin import SpamReport  # noqa: F401

async def main():
    await init_models()
    print("✅ spam_reports table is ready.")
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
