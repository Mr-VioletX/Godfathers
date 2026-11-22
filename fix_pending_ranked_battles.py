import asyncio
from app.database.engine import async_session, init_models
from app.services.ranked_battle_finalizer import finalize_finished_ranked_battles
async def main():
    await init_models()
    async with async_session() as session:
        n=await finalize_finished_ranked_battles(session, limit=500)
        await session.commit()
    print(f'✅ finalized {n} pending ranked battles')
if __name__=='__main__': asyncio.run(main())
