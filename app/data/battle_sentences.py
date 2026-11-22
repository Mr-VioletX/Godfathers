# -*- coding: utf-8 -*-
"""🆕 v1.7.4 — روایت متنوع فازهای نبرد (بدون تکرار خسته‌کننده)."""
from __future__ import annotations

import random

from app.data import military as M

PHASES = [
    ("🚨", "شبیخون آغازین"),
    ("💣", "آتش‌بار سنگین"),
    ("🛡️", "نبرد خط مقدم"),
    ("✈️", "نبرد آسمان"),
    ("🔥", "ضدحمله"),
    ("🏁", "یورش پایانی"),
]

# هر فاز استخر جملهٔ مخصوص خودش را دارد تا تکرار بین فازها کم شود
PHASE_OPEN = {
    0: [
        "دیده‌بان‌های {att} پیش از طلوع خط اول {defn} را علامت زدند.",
        "{att} بی‌صدا از جناح وارد شد؛ {defn} هنوز آرایش کامل نگرفته بود.",
        "اولین شلیک‌ها از سمت {att} سکوت میدان را شکست.",
        "ستون‌های پیشرو {att} مه را شکافتند و به محدودهٔ {defn} رسیدند.",
        "موج شناسایی {att} نقاط کور دفاع {defn} را لو داد.",
    ],
    1: [
        "باران آتش {att} سنگرهای پیشین {defn} را زیر گرفت.",
        "آتش‌بار هماهنگ {att} خط تدارکات {defn} را قطع کرد.",
        "موج دوم شلیک‌ها از سمت {att} شدت گرفت؛ دود میدان را پوشاند.",
        "{defn} زیر رگبار سنگین قرار گرفت و مجبور به جابه‌جایی سریع شد.",
        "توپخانه و پشتیبانی {att} ریتم حمله را تندتر کرد.",
    ],
    2: [
        "در خط مقدم، یگان‌های زمینی دو طرف به‌هم رسیدند.",
        "نبرد خانه‌به‌خانه در لبهٔ جبهه بین {att} و {defn} بالا گرفت.",
        "فشار پیاده و زرهی {att} خط دفاعی {defn} را خم کرد.",
        "{defn} با ذخیره‌های نزدیک خط کوشید جلو پیشروی را بگیرد.",
        "خاکریزها چند بار دست‌به‌دست شدند؛ هیچ‌کس عقب نکشید.",
    ],
    3: [
        "آسمان میدان با ورود یگان‌های هوایی تغییر کرد.",
        "درگیری هوایی بالای سر {defn} شدت گرفت.",
        "پدافند و جنگنده‌ها برای کنترل ارتفاع وارد عمل شدند.",
        "{att} تلاش کرد برتری هوایی بگیرد تا زمین را باز کند.",
        "رد موشک و مانور هوایی مسیر نبرد زمینی را عوض کرد.",
    ],
    4: [
        "{defn} با یگان ذخیره دست به ضدحمله زد.",
        "موج برگشتی {defn} آرایش جلو {att} را به‌هم ریخت.",
        "ضدضربه از جناح {defn} لحظه‌ای ابتکار را جابه‌جا کرد.",
        "{att} مجبور شد بخشی از نیرو را برای مهار ضدحمله عقب بکشد.",
        "نبرد برای لحظاتی دو سره شد؛ هر دو طرف روی تمام توان فشار آوردند.",
    ],
    5: [
        "آخرین یورش {att} برای شکستن مقاومت {defn} آغاز شد.",
        "هر دو طرف ذخایر پایانی را وارد میدان کردند.",
        "غبار که فرو نشست، تکلیف میدان کم‌کم روشن شد.",
        "فشار نهایی روی ضعیف‌ترین نقطهٔ {defn} متمرکز شد.",
        "نبرد به دقیقهٔ آخر رسید؛ دیگر جایی برای محافظه‌کاری نماند.",
    ],
}

PHASE_ACT = {
    0: [
        "نقش پررنگ: {unit} — تمرکز روی {area}.",
        "آرایش {style} {att} در باز شدن جبهه مؤثر بود.",
        "ضعف {defn} در {weak} همان نقطهٔ ورود اول بود.",
        "هماهنگی دیده‌بان و پیشرو، شبیخون را دقیق کرد.",
        "ضربهٔ اول روی {area} فرود آمد.",
        "کمبود {missing} می‌توانست شبیخون را کند کند، ولی فشار حفظ شد.",
    ],
    1: [
        "{unit} آتش سرکوب را روی {area} نگه داشت.",
        "فشار موشکی/آتشین مسیر تدارک {defn} را بست.",
        "سطح آموزش نیروها در پایداری زیر آتش معلوم شد.",
        "{defn} کوشید پراکنده شود تا از تمرکز آتش بگریزد.",
        "ترکیب آتش مستقیم و منحنی، خط اول را سایید.",
    ],
    2: [
        "درگیری نزدیک، کیفیت پیاده و زره را عیان کرد.",
        "{unit} ستون فقرات فشار زمینی شد.",
        "اگر {missing} کم باشد، خط به‌سختی دوام می‌آورد.",
        "{defn} با دفاع لایه‌لایه سعی کرد زمان بخرد.",
        "پیشروی متر‌به‌متر و پرهزینه پیش رفت.",
    ],
    3: [
        "{unit} در ارتفاع پایین برای شکستن پوشش ظاهر شد.",
        "پدافند {defn} آسمان را پر از ترکش کرد.",
        "کنترل آسمان، پشتیبانی زمینی را جابه‌جا کرد.",
        "نبرد هوایی بیش از انتظار طول کشید.",
        "هر دو طرف برای حفظ برتری ارتفاع هزینه دادند.",
    ],
    4: [
        "ضدحمله روی جناح {area} متمرکز شد.",
        "{defn} از {weak} خودش برای غافلگیری استفاده کرد.",
        "{att} با آرایش مجدد جلوی شکاف را گرفت.",
        "این فاز بیش از همه به زمان‌بندی ذخیره وابسته بود.",
        "فشار متقابل، آمار تلفات را بالا کشید.",
    ],
    5: [
        "یورش آخر همهٔ برگ‌های مانده را رو کرد.",
        "{unit} در ضربهٔ نهایی نقش تعیین‌کننده داشت.",
        "مقاومت {defn} در {area} یا شکست یا ایستاد.",
        "نتیجه بیشتر از شانس، از ترکیب و لول نیروها آمد.",
        "با خاموش شدن آتش، میدان برندهٔ خود را نشان داد.",
    ],
}

# جملات عمومی اضافه برای جلوگیری از بن‌بست اگر استخر فاز خالی شد
FALLBACK_OPEN = [
    "میدان بین {att} و {defn} همچنان داغ بود.",
    "فشار عملیات جابه‌جا می‌شد و هیچ‌کس میدان را رها نکرد.",
]
FALLBACK_ACT = [
    "ترکیب نیروها مسیر این مرحله را ساخت.",
    "کیفیت آرایش و لول آموزش اثرش را گذاشت.",
]

LOSS_LINES = [
    "📡 برآورد لحظه‌ای تلفات — مهاجم: {a:,} | مدافع: {d:,}",
    "🩸 تا این عملیات: {a:,} واحد از {att} و {d:,} واحد از {defn} از رده خارج شده‌اند.",
    "🚑 آمار میدانی تجمعی → خودی/مهاجم {a:,} — حریف/مدافع {d:,}",
    "📻 بی‌سیم ستاد: تلفات تقریبی {att} {a:,} و {defn} {d:,}.",
    "📉 شمارش خسارت تاکنون: {a:,} در برابر {d:,}.",
]


def _counts(stacks):
    d = {}
    for k, c, lv in stacks or []:
        cat = (M.get_unit(k) or {}).get("cat", "unknown")
        d[cat] = d.get(cat, 0) + int(c or 0)
    return d


def _top_units(stacks, n=3):
    ranked = []
    for k, c, lv in stacks or []:
        if int(c or 0) <= 0:
            continue
        sc = M.unit_power(k, int(c or 0), int(lv or 0))
        name = (M.get_unit(k) or {}).get("name", k)
        ranked.append((sc, name, int(lv or 0), (M.get_unit(k) or {}).get("cat", "")))
    ranked.sort(reverse=True)
    return ranked[:n]


def _missing(c):
    for cat, name in [
        ("aa", "پدافند"),
        ("fighter", "جنگنده"),
        ("tank", "زرهی"),
        ("soldier", "پیاده‌نظام"),
        ("missile", "موشک"),
        ("bomber", "بمب‌افکن"),
    ]:
        if c.get(cat, 0) <= 0:
            return name
    return "پشتیبانی عمیق"


def _style(c):
    cats = [k for k, v in c.items() if v > 0]
    if len(cats) >= 4:
        return "چندلایه و متوازن"
    if len(cats) == 3:
        return "نیمه‌متوازن"
    if "fighter" in cats or "bomber" in cats:
        return "هوا‌محور"
    if "tank" in cats:
        return "زره‌محور"
    return "تک‌محور"


def _pick_unique(rnd: random.Random, pool: list[str], used: set[str]) -> str:
    choices = [p for p in pool if p not in used]
    if not choices:
        choices = list(pool)
    s = rnd.choice(choices)
    used.add(s)
    return s


def make_battle_phases(att_name, def_name, att_stacks, def_stacks, result, seed=None):
    """۶ فاز داستانی متنوع با تلفات تدریجی (نه عدد ثابت تکراری)."""
    rnd = random.Random(seed)
    ac = _counts(att_stacks)
    dc = _counts(def_stacks)
    top_att = _top_units(att_stacks, 3)
    top_def = _top_units(def_stacks, 3)
    unit = top_att[0][1] if top_att else "نیروهای پیشرو"
    unit_def = top_def[0][1] if top_def else "خط دفاع"
    missing = _missing(ac)
    weak = _missing(dc)
    style = _style(ac)

    att_total = int(sum(int(v) for v in (result.get("att_losses") or {}).values()))
    def_total = int(sum(int(v) for v in (result.get("def_losses") or {}).values()))
    # تلفات فازبه‌فاز تجمعی — نه یک عدد ثابت در هر ۶ فاز
    shares = [0.12, 0.28, 0.48, 0.66, 0.85, 1.00]

    used_open: set[str] = set()
    used_act: set[str] = set()
    used_loss: set[str] = set()
    areas = ["خط مقدم", "آسمان", "پدافند", "زرهی", "موشکی", "عقبه", "جناح چپ", "جناح راست"]
    rnd.shuffle(areas)

    out = []
    for i, (ico, title) in enumerate(PHASES):
        area = areas[i % len(areas)]
        # چرخش واحد شاخص بین برترین‌ها
        if top_att:
            unit_i = top_att[i % len(top_att)][1]
        else:
            unit_i = unit
        ctx = dict(
            att=att_name,
            defn=def_name,
            style=style,
            weak=weak,
            unit=unit_i,
            unit_def=unit_def,
            missing=missing,
            area=area,
        )
        open_pool = PHASE_OPEN.get(i, FALLBACK_OPEN) + FALLBACK_OPEN
        act_pool = PHASE_ACT.get(i, FALLBACK_ACT) + FALLBACK_ACT
        # ACTهای شرطیِ مفید
        act_pool = list(act_pool) + [
            f"نقطه‌ضعف اعلامی {def_name} در {weak} دوباره در این فاز دیده شد.",
            f"آرایش {style} {att_name} هنوز محور تصمیم‌گیری بود.",
        ]

        open_s = _pick_unique(rnd, open_pool, used_open).format(**ctx)
        act_s = _pick_unique(rnd, act_pool, used_act).format(**ctx)

        a = int(att_total * shares[i])
        d = int(def_total * shares[i])
        loss_tpl = _pick_unique(rnd, LOSS_LINES, used_loss)
        loss_s = loss_tpl.format(a=a, d=d, att=att_name, defn=def_name)

        # جزئیات متغیر اضافه: گاهی لول، گاهی ترکیب
        extra = ""
        if i in (1, 4) and top_att:
            sc, nm, lv, cat = top_att[0]
            extra = f"\n⚙️ شاخص فشار {att_name}: {nm}" + (f" (لول {lv})" if lv else "")
        elif i in (2, 5) and top_def:
            sc, nm, lv, cat = top_def[0]
            extra = f"\n🛡️ ستون دفاع {def_name}: {nm}" + (f" (لول {lv})" if lv else "")

        block = (
            f"<b>{ico} عملیاتِ {i + 1} — {title}</b>\n"
            f"{open_s}\n"
            f"{act_s}\n"
            f"{loss_s}"
            f"{extra}"
        )
        out.append(block)
    return out
