import asyncio
from app.database.engine import init_models
async def main():
    await init_models(); print('✅ stage53 tables/settings ready')
if __name__=='__main__': asyncio.run(main())
