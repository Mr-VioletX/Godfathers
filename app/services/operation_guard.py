# -*- coding: utf-8 -*-
"""قفل کاربر/رکورد و ثبت شناسهٔ یک‌بارمصرف برای عملیات اقتصادی."""
from __future__ import annotations
import asyncio
from datetime import datetime, timedelta
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from app.database.engine import async_session
from app.models.operation_lock import EconomicOperationLock, ProcessedOperation

_LOCKS: dict[int, asyncio.Lock] = {}
STALE_AFTER = timedelta(minutes=2)

class DuplicateOperation(Exception): pass
class BusyOperation(Exception): pass

class economic_operation:
    def __init__(self, user_id: int, operation_id: str):
        self.user_id, self.operation_id = int(user_id), str(operation_id)[:128]
        self.local = _LOCKS.setdefault(self.user_id, asyncio.Lock())
        self.acquired = False
    async def __aenter__(self):
        if self.local.locked():
            raise BusyOperation()
        await self.local.acquire()
        try:
            async with async_session() as session:
                # شناسهٔ تلگرام فقط یک بار اجرا می‌شود؛ رکورد دائمی برای بازپخش شبکه.
                if await session.get(ProcessedOperation, self.operation_id):
                    raise DuplicateOperation()
                existing = await session.get(EconomicOperationLock, self.user_id)
                now = datetime.utcnow()
                if existing and now - existing.locked_at <= STALE_AFTER:
                    raise BusyOperation()
                if existing:
                    await session.delete(existing)
                    await session.flush()
                session.add(EconomicOperationLock(user_id=self.user_id, operation_id=self.operation_id, locked_at=now))
                await session.commit()
                self.acquired = True
            return self
        except Exception:
            self.local.release()
            raise
    async def __aexit__(self, exc_type, exc, tb):
        try:
            if self.acquired:
                async with async_session() as session:
                    # فقط اجرای موفق یک‌بارمصرف ثبت می‌شود؛ خطا اجازهٔ تلاش دوباره می‌دهد.
                    if exc_type is None:
                        session.add(ProcessedOperation(operation_id=self.operation_id, user_id=self.user_id))
                    await session.execute(delete(EconomicOperationLock).where(
                        EconomicOperationLock.user_id == self.user_id,
                        EconomicOperationLock.operation_id == self.operation_id,
                    ))
                    try:
                        await session.commit()
                    except IntegrityError:
                        await session.rollback()
        finally:
            if self.local.locked(): self.local.release()

async def purge_old_operations() -> None:
    """قابل فراخوانی توسط کران؛ داده‌های یک‌بارمصرف بیش از ۷ روز را حذف می‌کند."""
    async with async_session() as session:
        cutoff = datetime.utcnow() - timedelta(days=7)
        await session.execute(delete(ProcessedOperation).where(ProcessedOperation.created_at < cutoff))
        await session.execute(delete(EconomicOperationLock).where(EconomicOperationLock.locked_at < datetime.utcnow() - STALE_AFTER))
        await session.commit()
