# -*- coding: utf-8 -*-
"""🆕 مرحله ۴۶ — روایتِ داستانیِ نبرد.

ماژولِ کاملاً خالص (بدونِ DB): از رویِ نتیجه‌ی شبیه‌سازی، ۶ «عملیات» می‌سازد که
در طولِ ۱۵ دقیقه یکی‌یکی برای کاربر باز می‌شوند. ربات نتیجه را زودتر لو نمی‌دهد؛
فازها فقط فضاسازی و گزارشِ میدانی هستند و نتیجه در پایانِ ۱۵ دقیقه اعلام می‌شود.
"""
from __future__ import annotations

import random

BATTLE_MINUTES = 15
PHASE_COUNT = 6

PHASE_TITLES = [
    "🚨 عملیاتِ ۱ — شبیخونِ آغازین",
    "💣 عملیاتِ ۲ — آتش‌بارِ سنگین",
    "🛡️ عملیاتِ ۳ — نبردِ خطِ مقدم",
    "✈️ عملیاتِ ۴ — نبردِ آسمان",
    "🔥 عملیاتِ ۵ — ضدحمله",
    "🏁 عملیاتِ ۶ — یورشِ پایانی",
]

_OPENING = [
    "ستون‌های {att} در تاریکی از مرز گذشتند؛ دیده‌بان‌های {deff} دیر خبردار شدند.",
    "سکوتِ شب با غرشِ موتورها شکست — نیروهای {att} خطِ نخستِ {deff} را نشانه گرفتند.",
    "فرمانِ حمله صادر شد. {att} بدونِ اخطار وارد قلمروِ {deff} شد.",
]
_BARRAGE = [
    "باران آتش روی مواضعِ {deff} فرود آمد؛ دودِ غلیظ میدان را پوشاند.",
    "توپخانه و راکت‌ها بی‌وقفه کار کردند؛ زمین زیرِ پای {deff} می‌لرزید.",
    "موجِ اولِ آتش، سنگرهای {deff} را درهم کوبید — اما خط هنوز نشکسته بود.",
]
_FRONT = [
    "زرهی‌ها به هم رسیدند؛ نبردِ تن‌به‌تن در خطِ مقدم بالا گرفت.",
    "پیاده‌نظام وارد شهرکِ متروکه شد؛ جنگِ خانه‌به‌خانه شروع شد.",
    "خطِ دفاعی چند بار دست‌به‌دست شد؛ هیچ‌کدام عقب نمی‌نشستند.",
]
_AIR = [
    "جنگنده‌ها در ارتفاعِ پایین ظاهر شدند و پدافند بی‌امان شلیک کرد.",
    "آسمان پر شد از ردِ موشک؛ بمب‌افکن‌ها به سمتِ اهدافِ زمینی رفتند.",
    "نبردِ هوایی سرنوشتِ زمین را تعیین می‌کرد — هر دو طرف بال از دست دادند.",
]
_COUNTER = [
    "{deff} ذخیره‌هایش را وارد کرد و ضدحمله‌ی سختی ترتیب داد.",
    "یگانِ ذخیره‌ی {deff} از جناح زد؛ آرایشِ {att} به‌هم ریخت.",
    "لحظه‌ای همه‌چیز برگشت: {deff} ابتکارِ عمل را به‌دست گرفت.",
]
_FINAL_PUSH = [
    "آخرین یورش آغاز شد؛ هر دو ارتش تا آخرین توان جنگیدند.",
    "فرماندهان همه‌چیز را روی میز گذاشتند — این حمله، حرفِ آخر بود.",
    "گردوغبار که خوابید، تکلیفِ میدان روشن شد…",
]

_POOLS = [_OPENING, _BARRAGE, _FRONT, _AIR, _COUNTER, _FINAL_PUSH]

_FIELD_NOTES = [
    "🩸 گزارشِ میدانی: تلفاتِ ما تا اینجا حدودِ {a:,} نفر — تلفاتِ حریف حدودِ {d:,} نفر.",
    "📻 بی‌سیمِ میدان: تا این لحظه {a:,} واحد از ما و {d:,} واحد از حریف از رده خارج شده‌اند.",
    "🚑 آمارِ لحظه‌ای — خودی: {a:,} | حریف: {d:,}",
]


def phase_unlock_seconds(index: int) -> int:
    """چند ثانیه پس از شروعِ نبرد، فازِ شماره‌ی index (از صفر) باز می‌شود."""
    return int(BATTLE_MINUTES * 60 * index / PHASE_COUNT)


def build_phases(
    seed: int,
    att_name: str,
    def_name: str,
    att_total_loss: int,
    def_total_loss: int,
    engine_log: list | None = None,
) -> list:
    """۶ فازِ داستانی می‌سازد. تلفات به‌تدریج (تجمعی) در فازها گزارش می‌شود."""
    r = random.Random(int(seed) or 1)
    notes = list(engine_log or [])
    phases = []
    shares = [0.10, 0.28, 0.48, 0.66, 0.85, 1.00]
    for i in range(PHASE_COUNT):
        lines = [f"<b>{PHASE_TITLES[i]}</b>", r.choice(_POOLS[i]).format(att=att_name, deff=def_name)]
        a = int(att_total_loss * shares[i])
        d = int(def_total_loss * shares[i])
        if att_total_loss or def_total_loss:
            lines.append(r.choice(_FIELD_NOTES).format(a=a, d=d))
        if notes and i in (1, 3):
            lines.append(notes.pop(0))
        phases.append("\n".join(lines))
    return phases


def result_banner(attacker_won: bool) -> str:
    return "🏆 <b>پیروزی!</b>" if attacker_won else "💀 <b>شکست!</b>"


def fmt_remaining(seconds: int) -> str:
    s = max(0, int(seconds))
    m, s = divmod(s, 60)
    if m <= 0:
        return f"{s} ثانیه"
    return f"{m} دقیقه و {s} ثانیه"
