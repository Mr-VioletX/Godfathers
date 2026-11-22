# -*- coding: utf-8 -*-
"""Small, dependency-free 72-hour maintenance for Passenger/cPanel stderr.

The state file is independent from stderr's mtime, so a busy log is still
truncated every 72 hours.  ``GODFATHER_STDERR_PATH`` can override/add the exact
host path (multiple paths may be separated with ``os.pathsep``).
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Iterable

INTERVAL_SECONDS = 72 * 60 * 60
_PROCESS_CHECK_GAP = 5 * 60
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_STATE = _PROJECT_ROOT / ".stderr_cleanup_state.json"
_next_process_check = 0.0


def _default_paths() -> list[Path]:
    values: list[Path] = []
    configured = os.environ.get("GODFATHER_STDERR_PATH", "")
    for value in configured.split(os.pathsep):
        if value.strip():
            values.append(Path(value.strip()).expanduser())
    values.extend((_PROJECT_ROOT / "stderr.log", _PROJECT_ROOT / "stderr"))

    unique: list[Path] = []
    seen: set[str] = set()
    for path in values:
        key = str(path.absolute())
        if key not in seen:
            seen.add(key)
            unique.append(path)
    return unique


def _load_state(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_state(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=True, sort_keys=True), encoding="utf-8")
    os.replace(tmp, path)


def maybe_cleanup_stderr(
    *,
    paths: Iterable[str | os.PathLike[str]] | None = None,
    state_path: str | os.PathLike[str] | None = None,
    interval_seconds: int = INTERVAL_SECONDS,
    now: float | None = None,
    force: bool = False,
) -> dict:
    """Truncate configured stderr files when the 72-hour interval is due.

    The first invocation is intentionally due, which clears the pre-deployment
    error flood immediately.  Later invocations are governed by the persisted
    timestamp.  The function never raises for an unreadable/unwritable log file.
    """
    global _next_process_check

    default_call = paths is None and state_path is None and now is None and not force
    monotonic_now = time.monotonic()
    if default_call and monotonic_now < _next_process_check:
        return {
            "due": False,
            "throttled": True,
            "cleaned_files": 0,
            "removed_bytes": 0,
            "errors": [],
        }
    if default_call:
        _next_process_check = monotonic_now + _PROCESS_CHECK_GAP

    current = float(time.time() if now is None else now)
    interval = max(60, int(interval_seconds))
    state_file = Path(state_path) if state_path is not None else _DEFAULT_STATE
    state = _load_state(state_file)
    last_cleanup = float(state.get("last_cleanup", 0) or 0)
    due = bool(force or last_cleanup <= 0 or current - last_cleanup >= interval)
    if not due:
        return {
            "due": False,
            "throttled": False,
            "cleaned_files": 0,
            "removed_bytes": 0,
            "errors": [],
            "next_cleanup": last_cleanup + interval,
        }

    candidates = [Path(p) for p in paths] if paths is not None else _default_paths()
    cleaned: list[str] = []
    removed_bytes = 0
    errors: list[str] = []
    for candidate in candidates:
        try:
            if not candidate.exists() or not candidate.is_file():
                continue
            size = candidate.stat().st_size
            with candidate.open("r+b") as stream:
                stream.truncate(0)
            cleaned.append(str(candidate))
            removed_bytes += int(size)
        except Exception as exc:
            errors.append(f"{candidate}: {type(exc).__name__}: {exc}")

    try:
        _save_state(
            state_file,
            {
                "last_cleanup": current,
                "cleaned_files": cleaned,
                "removed_bytes": removed_bytes,
                "errors": errors,
            },
        )
    except Exception as exc:
        errors.append(f"{state_file}: {type(exc).__name__}: {exc}")

    return {
        "due": True,
        "throttled": False,
        "cleaned_files": len(cleaned),
        "cleaned_paths": cleaned,
        "removed_bytes": removed_bytes,
        "errors": errors,
        "next_cleanup": current + interval,
    }
