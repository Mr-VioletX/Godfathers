# -*- coding: utf-8 -*-
"""Central, rotating and host-safe logging configuration.

File handlers always use UTF-8.  The Passenger/cPanel console can advertise an
ASCII-only encoding; :class:`SafeConsoleHandler` therefore writes the original
Unicode message when possible and falls back to escaped ASCII instead of letting
``logging`` generate recursive ``--- Logging error ---`` tracebacks.
"""
from __future__ import annotations

import logging
import logging.handlers
import os
import sys
from typing import TextIO

_CONFIGURED = False

_FMT = "%(asctime)s | %(levelname)-8s | %(name)s | %(funcName)s:%(lineno)d | %(message)s"
_DATEFMT = "%Y-%m-%d %H:%M:%S"


class SafeConsoleHandler(logging.StreamHandler):
    """A StreamHandler that cannot fail merely because its stream is ASCII.

    Passenger sometimes exposes stdout/stderr as a strict ASCII text stream.
    Standard ``StreamHandler.emit`` catches the resulting UnicodeEncodeError and
    prints a large internal logging traceback to stderr.  Here we retry the same
    line with ``backslashreplace``; UTF-8 file logs still retain the original text.
    """

    @staticmethod
    def _escaped(payload: str, stream: TextIO) -> str:
        encoding = getattr(stream, "encoding", None) or "ascii"
        try:
            return payload.encode(encoding, errors="backslashreplace").decode(encoding)
        except (LookupError, UnicodeError):
            return payload.encode("ascii", errors="backslashreplace").decode("ascii")

    def emit(self, record: logging.LogRecord) -> None:
        try:
            payload = self.format(record) + self.terminator
            stream = self.stream
            try:
                stream.write(payload)
            except UnicodeEncodeError:
                safe_payload = self._escaped(payload, stream)
                try:
                    stream.write(safe_payload)
                except UnicodeEncodeError:
                    # Some WSGI wrappers report a UTF encoding but still accept ASCII only.
                    stream.write(payload.encode("ascii", "backslashreplace").decode("ascii"))
            self.flush()
        except RecursionError:
            raise
        except Exception:
            self.handleError(record)


class _ConsoleFilter(logging.Filter):
    """Keep per-update INFO traces in files, not Passenger's stderr stream."""

    def filter(self, record: logging.LogRecord) -> bool:
        return not (
            record.name.startswith("godfather.updates")
            and record.levelno < logging.WARNING
        )


def _file_handler(path: str, level: int, backups: int) -> logging.Handler | None:
    try:
        handler = logging.handlers.RotatingFileHandler(
            path,
            maxBytes=5_000_000,
            backupCount=backups,
            encoding="utf-8",
        )
    except OSError:
        return None
    handler.setLevel(level)
    handler.setFormatter(logging.Formatter(_FMT, _DATEFMT))
    return handler


def _remove_unsafe_console_handlers(root: logging.Logger) -> None:
    """Remove basicConfig/plain console handlers before installing the safe one."""
    for handler in list(root.handlers):
        if isinstance(handler, logging.StreamHandler) and not isinstance(
            handler, logging.FileHandler
        ):
            root.removeHandler(handler)
            try:
                handler.close()
            except Exception:
                pass


def setup_logging(level: int = logging.INFO, log_dir: str | None = None) -> str:
    """Install safe console and rotating UTF-8 file handlers once."""
    global _CONFIGURED
    log_dir = log_dir or os.environ.get("GODFATHER_LOG_DIR", "logs")
    if _CONFIGURED:
        return log_dir

    try:
        os.makedirs(log_dir, exist_ok=True)
    except OSError:
        log_dir = "."

    # Clear/rotate the hosting stderr file on its independent 72-hour schedule.
    cleanup_result: dict | None = None
    try:
        from app.utils.stderr_cleanup import maybe_cleanup_stderr

        cleanup_result = maybe_cleanup_stderr()
    except Exception:
        cleanup_result = None

    formatter = logging.Formatter(_FMT, _DATEFMT)
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)  # handler levels are the real filters
    _remove_unsafe_console_handlers(root)

    console = SafeConsoleHandler(sys.stdout)
    console.setLevel(level)
    console.setFormatter(formatter)
    console.addFilter(_ConsoleFilter())
    root.addHandler(console)

    bot_file = _file_handler(os.path.join(log_dir, "bot.log"), logging.INFO, backups=5)
    if bot_file:
        root.addHandler(bot_file)

    error_file = _file_handler(
        os.path.join(log_dir, "errors.log"), logging.ERROR, backups=10
    )
    if error_file:
        root.addHandler(error_file)

    updates = logging.getLogger("godfather.updates")
    updates.setLevel(logging.INFO)
    update_file = _file_handler(
        os.path.join(log_dir, "updates.log"), logging.INFO, backups=5
    )
    if update_file:
        updates.addHandler(update_file)

    for noisy in ("aiosqlite", "apscheduler", "aiogram.event", "aiogram.dispatcher"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    _CONFIGURED = True
    log = logging.getLogger(__name__)
    log.info(
        "logging ready -> dir=%s (bot.log / errors.log / updates.log)",
        os.path.abspath(log_dir),
    )
    if cleanup_result and cleanup_result.get("cleaned_files"):
        log.info(
            "stderr maintenance: cleared %s file(s), %s byte(s)",
            cleanup_result["cleaned_files"],
            cleanup_result.get("removed_bytes", 0),
        )
    return log_dir


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
