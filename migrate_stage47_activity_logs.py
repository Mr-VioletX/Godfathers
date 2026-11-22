import asyncio
from app.database.engine import init_models
async def main():
    await init_models(); print('✅ player_activity_logs table is ready.')
if __name__=='__main__': asyncio.run(main())
