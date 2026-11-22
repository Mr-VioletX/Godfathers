# -*- coding: utf-8 -*-
"""رندر جدولِ ستونی — غیرفعال. (v1.8.2.2 — جدول‌ها به خواستِ امیر حذف شدند؛ بخش‌ها به حالت ساده برگشتند.)"""
from __future__ import annotations


def render_table(headers, rows):
    cols = list(zip(*([headers] + rows))) if rows else [headers]
    widths = [max(_w(str(c)) for c in col) for col in cols]

    def fmt_row(cells):
        return "  ".join(str(c) + " " * (w - _w(str(c))) for c, w in zip(cells, widths)).rstrip()

    lines = [fmt_row(headers), "  ".join("─" * w for w in widths)]
    for r in rows:
        lines.append(fmt_row(r))
    return "<pre>" + "\n".join(lines) + "</pre>"


def _w(s):
    import unicodedata
    w = 0
    for ch in s:
        o = ord(ch)
        if o >= 0x1F000 or unicodedata.east_asian_width(ch) in ("W", "F"):
            w += 2
        else:
            w += 1
    return w


async def table_mode_on(section=None, session=None) -> bool:
    """جدول همیشه خاموش است — بخش‌ها به حالت ساده (خط‌به‌خط) نمایش داده می‌شوند."""
    return False
