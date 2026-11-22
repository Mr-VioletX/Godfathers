#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Manual/cron entry point for the same 72-hour stderr maintenance policy."""
from __future__ import annotations

import argparse
import json

from app.utils.stderr_cleanup import maybe_cleanup_stderr

parser = argparse.ArgumentParser()
parser.add_argument("--force", action="store_true", help="truncate immediately")
args = parser.parse_args()
result = maybe_cleanup_stderr(force=args.force)
print(json.dumps(result, ensure_ascii=False, indent=2))
raise SystemExit(1 if result.get("errors") else 0)
