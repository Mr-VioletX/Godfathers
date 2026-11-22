# -*- coding: utf-8 -*-
"""v1.7.9.3 — استخراج پک ایموجی پرمیوم → فایل نگاشت (برای تبدیل ایموجی‌های ربات در آخرین مرحله).

ربات آدرس پک را می‌گیرد، همه‌ی ایموجی‌هایش را می‌خواند و فایلی می‌سازد که کاربر
به Notion AI می‌دهد تا custom_emoji_id ها در ساختار ربات استفاده شوند. هر خط
شامل ایموجی استاندارد + آیدی + نام/موضوع است تا ایموجی‌ها در هم نروند.
"""
from __future__ import annotations

import re
import unicodedata


def parse_pack_name(raw: str) -> str | None:
    """از آدرس/نام پک، نام پک را بیرون می‌کشد.

    می‌پذیرد: https://t.me/addemoji/Name ، t.me/addemoji/Name ، addstickers/Name ، @Name ، Name
    """
    raw = (raw or "").strip()
    if not raw:
        return None
    m = re.search(r"(?:addemoji|addstickers)/([A-Za-z0-9_]+)", raw)
    if m:
        return m.group(1)
    raw = raw.lstrip("@").strip()
    if re.match(r"^[A-Za-z0-9_]+$", raw):
        return raw
    return None


async def harvest_pack(bot, pack_name: str) -> list[tuple[str, str]]:
    """همه‌ی ایموجی‌های پک را می‌خواند: [(ایموجی استاندارد, custom_emoji_id)]."""
    ss = await bot.get_sticker_set(pack_name)
    items: list[tuple[str, str]] = []
    for st in ss.stickers:
        ceid = getattr(st, "custom_emoji_id", None)
        if not ceid:
            continue
        items.append((getattr(st, "emoji", None) or "❓", str(ceid)))
    return items


def emoji_subject(emoji_char: str) -> str:
    """نام/موضوع ایموجی استاندارد — برای تشخیص ظاهر و جلوگیری از درهم‌رفتنِ ایموجی‌ها."""
    try:
        return unicodedata.name(emoji_char).title()
    except (ValueError, TypeError):
        return "Unknown"


def build_mapping_text(pack_name: str, items: list[tuple[str, str]]) -> str:
    """متن فایل نگاشت — کاربر آن را به Notion AI می‌دهد تا در ساختار ربات استفاده شود."""
    lines = [
        f"# 😎 Emoji Pack Mapping — {pack_name} — {len(items)} emoji — v1.7.9.3",
        "# این فایل را برای Notion AI بفرست تا ایموجی‌های پرمیوم در ربات استفاده شوند.",
        "# فرمت هر خط: ایموجی استاندارد | custom_emoji_id | نام/موضوع",
        "",
    ]
    for emoji_char, ceid in items:
        lines.append(f"{emoji_char} | {ceid} | {emoji_subject(emoji_char)}")
    return "\n".join(lines) + "\n"
