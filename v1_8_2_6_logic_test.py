# -*- coding: utf-8 -*-
"""Stage 83 / v1.8.2.6 regression tests for stderr and news transactions."""
from __future__ import annotations

import asyncio
import ast
import io
import logging
import os
import sys
import tempfile
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("BOT_TOKEN", "123456:offline-test-token")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

# Only news_ticker's exception class is needed when aiogram is unavailable offline.
try:
    import aiogram  # noqa: F401
except ModuleNotFoundError:
    aiogram_mod = types.ModuleType("aiogram")
    exceptions_mod = types.ModuleType("aiogram.exceptions")

    class TelegramForbiddenError(Exception):
        pass

    exceptions_mod.TelegramForbiddenError = TelegramForbiddenError
    aiogram_mod.exceptions = exceptions_mod
    sys.modules["aiogram"] = aiogram_mod
    sys.modules["aiogram.exceptions"] = exceptions_mod

from app.utils.logging_setup import SafeConsoleHandler, _ConsoleFilter, _file_handler
from app.utils.stderr_cleanup import INTERVAL_SECONDS, maybe_cleanup_stderr


# 1) A strict ASCII Passenger-like stream must never create a logging traceback.
buffer = io.BytesIO()
ascii_stream = io.TextIOWrapper(buffer, encoding="ascii", errors="strict")
handler = SafeConsoleHandler(ascii_stream)
handler.setFormatter(logging.Formatter("%(levelname)s | %(message)s"))
logger = logging.Logger("stage83.ascii", level=logging.INFO)
logger.propagate = False
logger.addHandler(handler)
logger.info("سلام 🐢 — متن فارسی")
handler.flush()
ascii_bytes = buffer.getvalue()
assert b"Logging error" not in ascii_bytes
assert b"\\u" in ascii_bytes or b"\\U" in ascii_bytes

# 2) UTF-8 file logs retain the original text.
with tempfile.TemporaryDirectory(prefix="stage83_log_") as td:
    path = Path(td) / "bot.log"
    file_handler = _file_handler(str(path), logging.INFO, backups=1)
    assert file_handler is not None
    file_logger = logging.Logger("stage83.file", level=logging.INFO)
    file_logger.propagate = False
    file_logger.addHandler(file_handler)
    file_logger.info("سلام 🐢")
    file_handler.flush()
    assert "سلام 🐢" in path.read_text(encoding="utf-8")
    file_handler.close()

# 3) Update INFO noise is filtered only from console; warnings/errors remain.
flt = _ConsoleFilter()
info_record = logging.LogRecord("godfather.updates", logging.INFO, __file__, 1, "x", (), None)
error_record = logging.LogRecord("godfather.updates", logging.ERROR, __file__, 1, "x", (), None)
other_record = logging.LogRecord("app.test", logging.INFO, __file__, 1, "x", (), None)
assert flt.filter(info_record) is False
assert flt.filter(error_record) is True
assert flt.filter(other_record) is True

# 4) The stderr policy is based on an independent 72-hour state timestamp.
with tempfile.TemporaryDirectory(prefix="stage83_cleanup_") as td:
    td_path = Path(td)
    stderr_path = td_path / "stderr.log"
    state_path = td_path / "state.json"
    stderr_path.write_bytes(b"x" * 4096)
    first = maybe_cleanup_stderr(paths=[stderr_path], state_path=state_path, now=1_000)
    assert first["due"] and first["cleaned_files"] == 1
    assert first["removed_bytes"] == 4096 and stderr_path.stat().st_size == 0

    stderr_path.write_bytes(b"new-errors")
    early = maybe_cleanup_stderr(
        paths=[stderr_path], state_path=state_path, now=1_000 + INTERVAL_SECONDS - 1
    )
    assert not early["due"] and stderr_path.read_bytes() == b"new-errors"

    due = maybe_cleanup_stderr(
        paths=[stderr_path], state_path=state_path, now=1_000 + INTERVAL_SECONDS
    )
    assert due["due"] and due["cleaned_files"] == 1
    assert stderr_path.stat().st_size == 0


# 5) A failed commit is rolled back and the next job receives a fresh session.
# The release test is dependency-free: provide tiny import stubs when SQLAlchemy
# is not installed in the local/offline QA environment.
try:
    import sqlalchemy  # noqa: F401
except ModuleNotFoundError:
    sqlalchemy_mod = types.ModuleType("sqlalchemy")
    sqlalchemy_mod.select = lambda *args, **kwargs: (args, kwargs)
    sys.modules["sqlalchemy"] = sqlalchemy_mod
    engine_mod = types.ModuleType("app.database.engine")
    engine_mod.async_session = None
    sys.modules["app.database.engine"] = engine_mod

from app.services import news_ticker as NT

NT.log.handlers[:] = [logging.NullHandler()]
NT.log.propagate = False


class FakeSession:
    def __init__(self, commit_error: Exception | None = None):
        self.commit_error = commit_error
        self.commit_calls = 0
        self.rollback_calls = 0
        self.closed = False

    async def commit(self):
        self.commit_calls += 1
        if self.commit_error is not None:
            raise self.commit_error

    async def rollback(self):
        self.rollback_calls += 1


class FakeContext:
    def __init__(self, session: FakeSession):
        self.session = session

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, exc_type, exc, tb):
        self.session.closed = True


class FakeFactory:
    def __init__(self, sessions):
        self.sessions = list(sessions)
        self.used = []

    def __call__(self):
        session = self.sessions.pop(0)
        self.used.append(session)
        return FakeContext(session)


async def transaction_checks():
    failed = FakeSession(RuntimeError("prepared-state simulation"))
    fresh = FakeSession()
    factory = FakeFactory([failed, fresh])
    original_factory = NT.async_session
    NT.async_session = factory
    try:
        async def job(session):
            return id(session)

        try:
            await NT._run_in_fresh_session(job)
        except RuntimeError:
            pass
        else:
            raise AssertionError("failed commit must propagate")
        assert failed.commit_calls == 1 and failed.rollback_calls == 1 and failed.closed

        result = await NT._run_in_fresh_session(job)
        assert result == id(fresh)
        assert fresh.commit_calls == 1 and fresh.rollback_calls == 0 and fresh.closed
        assert factory.used == [failed, fresh]
    finally:
        NT.async_session = original_factory

    original_post = NT._post_once
    try:
        async def fail_post(_bot):
            raise RuntimeError("temporary")

        async def ok_post(_bot):
            return None

        NT._post_once = fail_post
        assert await NT.news_tick_once(None) is False
        NT._post_once = ok_post
        assert await NT.news_tick_once(None) is True
    finally:
        NT._post_once = original_post


asyncio.run(transaction_checks())

# 6) Scheduler code must only mark the date after a true result.
host_source = (ROOT / "app/services/host_scheduler.py").read_text(encoding="utf-8")
cron_source = (ROOT / "cron_ticks.py").read_text(encoding="utf-8")
assert 'if posted:' in host_source
assert 'state["last_news_date"] = today' in host_source
assert 'if await news_tick_once(bot):' in cron_source
assert 'date not marked' in cron_source

# 7) Full source remains valid and the release number is correct.
python_files = sorted(ROOT.rglob("*.py"))
for path in python_files:
    ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
version = (ROOT / "VERSION.txt").read_text(encoding="utf-8").strip()
version_parts = tuple(int(part) for part in version.split("."))
assert version_parts >= (1, 8, 2, 6), version

print(f"OK: {len(python_files)} Python files parsed")
print("OK: ASCII console is Unicode-safe")
print("OK: UTF-8 file logs preserve original text")
print("OK: stderr cleanup follows a 72-hour persisted schedule")
print("OK: failed news sessions rollback and are never reused")
print(f"OK: version {version} retains stage 83 stderr safeguards")
