# -*- coding: utf-8 -*-
"""Stage 82 / v1.8.2.5: regression checks for standard Unicode emoji mode."""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent

removed_files = [
    ROOT / "app/middlewares/premium_emoji.py",
    ROOT / "app/data/premium_emoji.py",
    ROOT / "app/services/emoji_pack_service.py",
    ROOT / "app/utils/emoji_buttons.py",
]
assert all(not path.exists() for path in removed_files), removed_files

runtime_files = [ROOT / "bot.py", *sorted((ROOT / "app").rglob("*.py"))]
forbidden_parts = [
    "premium_" + "emoji",
    "emoji_" + "pack_service",
    "emoji_" + "buttons",
    "adm:" + "emoji",
    "emoji_" + "pack_wait",
    "icon_" + "custom_emoji_id",
    "custom_" + "emoji_id",
    "<tg-" + "emoji",
]
for path in runtime_files:
    text = path.read_text(encoding="utf-8")
    ast.parse(text, filename=str(path))
    for token in forbidden_parts:
        assert token not in text, f"{token!r} remains in {path.relative_to(ROOT)}"

bot_source = (ROOT / "bot.py").read_text(encoding="utf-8")
alliance_source = (ROOT / "app/keyboards/alliance_menu.py").read_text(encoding="utf-8")
admin_source = (ROOT / "app/handlers/admin.py").read_text(encoding="utf-8")
admin_menu_source = (ROOT / "app/keyboards/admin_menu.py").read_text(encoding="utf-8")
states_source = (ROOT / "app/states.py").read_text(encoding="utf-8")

assert "outgoing_safety.install(bot)" in bot_source
assert "InlineKeyboardBuilder()" in alliance_source
for label in ("🏭 تولید نیرو", "🤖 تولید خودکار", "🎖️ ارتقا و آموزش", "🏥 بیمارستان", "📖 راهنمای ارتش"):
    assert label in alliance_source, label
assert "استخراج پک ایموجی" not in admin_source
assert "ایموجی پرمیوم (پک)" not in admin_menu_source
assert "emoji_pack_wait" not in states_source
version = (ROOT / "VERSION.txt").read_text(encoding="utf-8").strip()
version_parts = tuple(int(part) for part in version.split("."))
assert version_parts >= (1, 8, 2, 5), version

print(f"OK: {len(runtime_files)} runtime Python files parsed")
print("OK: premium emoji runtime removed")
print("OK: standard Unicode emoji labels preserved")
print(f"OK: version {version} retains stage 82")
