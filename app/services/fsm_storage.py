# -*- coding: utf-8 -*-
"""🆕 مرحله ۳۲ — انبارِ پایدارِ FSM (نسخهٔ ۳ — ضدِ از‌دست‌رفتن state).

🐞 v1.7.5.1 — ریشهٔ باگ «اسم شهر دریافت نمی‌شود»:
  set_data وقتی کش miss می‌شد state را در کش None می‌نوشت؛ get_state
  تا ۲ ثانیه state=None برمی‌گرداند و StateFilter هندلر نام را نمی‌گرفت.
  همچنین INSERT دیتای جدید state را NULL می‌گذاشت اگر ردیف نبود.

حالا set_state/set_data همیشه state+data را اتمیک و با خواندنِ قبلی merge می‌کنند.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Tuple

from aiogram.fsm.state import State
from aiogram.fsm.storage.base import BaseStorage, StorageKey
from sqlalchemy import text

from app.database.engine import async_session

# اگر کاربر یک عملیات را نیمه‌کاره رها کند، پس از این مدت دیگر معتبر نیست.
STATE_TTL_HOURS = 12

# کشِ درون‌پروسه‌ای (فقط برای خواندنِ پشت‌سرِهم در یک آپدیت)
CACHE_TTL_SECONDS = 2.0

_DDL = (
    "CREATE TABLE IF NOT EXISTS fsm_states ("
    "  key TEXT PRIMARY KEY,"
    "  state TEXT,"
    "  data TEXT,"
    "  updated_at TEXT"
    ")"
)
_DDL_INDEX = "CREATE INDEX IF NOT EXISTS ix_fsm_states_updated ON fsm_states (updated_at)"


class DatabaseFSMStorage(BaseStorage):
    """انبارِ FSM روی همان دیتابیسِ بازی (مقاوم در برابرِ ریستارتِ پروسه)."""

    def __init__(self) -> None:
        self._ready = False
        self._cache: Dict[str, Tuple[Optional[str], Dict[str, Any], float]] = {}

    # ------------------------------------------------------------------ utils
    @staticmethod
    def _skey(key: StorageKey) -> str:
        return f"{key.bot_id}:{key.chat_id}:{key.user_id}:{getattr(key, 'destiny', 'default')}"

    def _cache_get(self, skey: str):
        hit = self._cache.get(skey)
        if not hit:
            return None
        state, data, ts = hit
        if (time.monotonic() - ts) > CACHE_TTL_SECONDS:
            return None
        return state, data

    def _cache_put(self, skey: str, state, data) -> None:
        self._cache[skey] = (state, dict(data or {}), time.monotonic())

    def _cache_drop(self, skey: str) -> None:
        self._cache.pop(skey, None)

    async def _ensure(self) -> None:
        if self._ready:
            return
        async with async_session() as session:
            await session.execute(text(_DDL))
            try:
                await session.execute(text(_DDL_INDEX))
            except Exception:
                pass
            await session.commit()
        self._ready = True

    async def _read(self, skey: str, use_cache: bool = True) -> Tuple[Optional[str], Dict[str, Any]]:
        if use_cache:
            hit = self._cache_get(skey)
            if hit is not None:
                return hit[0], dict(hit[1])
        await self._ensure()
        async with async_session() as session:
            row = (await session.execute(
                text("SELECT state, data, updated_at FROM fsm_states WHERE key = :k"),
                {"k": skey},
            )).first()
        if row is None:
            self._cache_put(skey, None, {})
            return None, {}
        state, raw, updated = row[0], row[1], row[2]
        # وضعیتِ خیلی قدیمی = رهاشده؛ دیگر اعمال نمی‌شود.
        if updated:
            try:
                if datetime.utcnow() - datetime.fromisoformat(updated) > timedelta(hours=STATE_TTL_HOURS):
                    try:
                        await self._delete(skey)
                    except Exception:
                        pass
                    self._cache_put(skey, None, {})
                    return None, {}
            except Exception:
                pass
        try:
            data = json.loads(raw or "{}")
            if not isinstance(data, dict):
                data = {}
        except Exception:
            data = {}
        self._cache_put(skey, state, data)
        return state, data

    async def _delete(self, skey: str) -> None:
        await self._ensure()
        async with async_session() as session:
            await session.execute(text("DELETE FROM fsm_states WHERE key = :k"), {"k": skey})
            await session.commit()
        self._cache_drop(skey)

    async def _upsert_both(
        self, skey: str, state: Optional[str], data: Dict[str, Any]
    ) -> None:
        """یک UPSERT اتمیک برای state + data (دیگر state با data پاک نمی‌شود)."""
        await self._ensure()
        payload = {
            "k": skey,
            "s": state,
            "d": json.dumps(data or {}, ensure_ascii=False),
            "u": datetime.utcnow().isoformat(),
        }
        async with async_session() as session:
            await session.execute(
                text(
                    "INSERT INTO fsm_states (key, state, data, updated_at) "
                    "VALUES (:k, :s, :d, :u) "
                    "ON CONFLICT(key) DO UPDATE SET "
                    "  state = excluded.state, "
                    "  data = excluded.data, "
                    "  updated_at = excluded.updated_at"
                ),
                payload,
            )
            await session.commit()
        self._cache_put(skey, state, data or {})

    # ------------------------------------------------------- BaseStorage API
    async def set_state(self, key: StorageKey, state: Any = None) -> None:
        skey = self._skey(key)
        value = state.state if isinstance(state, State) else state
        # همیشه data فعلی را از DB/کش بخوان تا wipe نشود
        try:
            _cur_state, cur_data = await self._read(skey, use_cache=True)
        except Exception:
            cur_data = {}
        if value is None and not cur_data:
            try:
                await self._delete(skey)
            except Exception:
                self._cache_put(skey, None, {})
            return
        try:
            await self._upsert_both(skey, value, cur_data)
        except Exception:
            # حداقل کش را درست نگه دار تا در همین پروسه StateFilter کار کند
            self._cache_put(skey, value, cur_data)

    async def get_state(self, key: StorageKey) -> Optional[str]:
        skey = self._skey(key)
        try:
            state, _data = await self._read(skey)
            return state
        except Exception:
            hit = self._cache.get(skey)
            return hit[0] if hit else None

    async def set_data(self, key: StorageKey, data: Dict[str, Any]) -> None:
        skey = self._skey(key)
        # 🔑 همیشه state فعلی را از DB بخوان — هرگز با cache-miss آن را None نکن
        try:
            cur_state, _old = await self._read(skey, use_cache=True)
        except Exception:
            hit = self._cache.get(skey)
            cur_state = hit[0] if hit else None
        try:
            await self._upsert_both(skey, cur_state, data or {})
        except Exception:
            self._cache_put(skey, cur_state, data or {})

    async def get_data(self, key: StorageKey) -> Dict[str, Any]:
        skey = self._skey(key)
        try:
            _state, data = await self._read(skey)
            return dict(data)
        except Exception:
            hit = self._cache.get(skey)
            return dict(hit[1]) if hit else {}

    async def update_data(self, key: StorageKey, data: Dict[str, Any]) -> Dict[str, Any]:
        current = await self.get_data(key)
        current.update(data or {})
        await self.set_data(key, current)
        return dict(current)

    async def close(self) -> None:  # pragma: no cover
        return None

    async def wait_closed(self) -> None:  # pragma: no cover
        return None
