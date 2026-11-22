# -*- coding: utf-8 -*-
"""Stage 87.2 — pure rules for branching, choice-driven Dark World cases."""
from __future__ import annotations

from app.data import dark_world as D

CASE_EXPIRY_HOURS = 72
CASE_HISTORY_LIMIT = 24
MOMENTUM_MIN, MOMENTUM_MAX = -15, 20
DANGER_MIN, DANGER_MAX = 0, 10
TOOL_MAX_QTY = 5

SKILL_LABELS = {
    "stealth": "نفوذ",
    "social": "فریب",
    "tech": "فناوری",
    "force": "جسارت",
}

TOOL_ORDER = ("lockpick", "disguise", "jammer", "escape_kit")
TOOLS = {
    "lockpick": {
        "name": "قفل‌شکن نانو", "icon": "🗝️", "cost": 35_000_000,
        "skills": ("stealth", "tech"), "bonus": 12,
        "description": "+۱۲٪ آزمون نفوذ یا فناوری؛ پس از استفاده مصرف می‌شود.",
    },
    "disguise": {
        "name": "هویت جعلی", "icon": "🎭", "cost": 70_000_000,
        "skills": ("social",), "bonus": 15,
        "description": "+۱۵٪ آزمون فریب؛ پس از استفاده مصرف می‌شود.",
    },
    "jammer": {
        "name": "مختل‌کننده سیگنال", "icon": "📡", "cost": 110_000_000,
        "skills": ("tech",), "bonus": 18,
        "description": "+۱۸٪ آزمون فناوری؛ پس از استفاده مصرف می‌شود.",
    },
    "escape_kit": {
        "name": "کیت فرار", "icon": "🪂", "cost": 160_000_000,
        "skills": ("force", "stealth"), "bonus": 15,
        "description": "+۱۵٪ آزمون جسارت یا نفوذ؛ پس از استفاده مصرف می‌شود.",
    },
}

CASE_ORDER = ("midnight_train", "masked_ball", "glass_vault")
CASES = {
    "midnight_train": {
        "name": "قطار نیمه‌شب", "icon": "🚂", "difficulty": 2,
        "difficulty_name": "حرفه‌ای", "required_influence": 75,
        "energy": 20, "intel_cost": 2, "entry_cost": 20_000_000, "start_node": "platform",
        "base_cash": 140_000_000, "base_xp": 5_000, "base_dark_xp": 70,
        "description": "محموله‌ای بی‌صاحب پیش از سپیده‌دم از شهر خارج می‌شود؛ راه ورود و خروج با توست.",
        "endings": {
            "perfect": {"name": "بدون یک رد", "success": True, "cash_mult": 1.15, "xp_mult": 1.20, "influence": 52, "heat": 3, "intel": 3, "text": "قطار رفت و حتی دوربین‌ها هم حضور تو را به خاطر نیاوردند."},
            "rich": {"name": "معامله دوطرفه", "success": True, "cash_mult": 1.35, "xp_mult": 1.10, "influence": 45, "heat": 9, "intel": 2, "text": "محموله و خریدار هر دو به مقصد رسیدند؛ شهر اما نامی تازه زمزمه می‌کند."},
            "noisy": {"name": "فرار با بار", "success": True, "cash_mult": .78, "xp_mult": .95, "influence": 30, "heat": 17, "intel": 1, "text": "بار را بردی، ولی صدای آژیر تا صبح در ایستگاه ماند."},
            "caught": {"name": "واگن بسته", "success": False, "cash_mult": 0, "xp_mult": .38, "influence": -18, "heat": 25, "intel": 0, "text": "قطار بدون تو حرکت کرد و پرونده‌ای تازه روی میز مأموران باز شد."},
        },
    },
    "masked_ball": {
        "name": "مهمانی نقاب‌ها", "icon": "🎭", "difficulty": 3,
        "difficulty_name": "مرگبار", "required_influence": 200,
        "energy": 30, "intel_cost": 5, "entry_cost": 85_000_000, "start_node": "gate",
        "base_cash": 420_000_000, "base_xp": 12_500, "base_dark_xp": 165,
        "description": "دفتر بدهکاران شهر امشب میان مهمان‌هایی است که هیچ‌کدام نام واقعی ندارند.",
        "endings": {
            "phantom": {"name": "مهمان سیزدهم", "success": True, "cash_mult": 1.20, "xp_mult": 1.25, "influence": 125, "heat": 5, "intel": 5, "text": "دفتر ناپدید شد و میزبان هنوز تعداد مهمان‌هایش را اشتباه می‌شمارد."},
            "auctioneer": {"name": "صاحب مزایده", "success": True, "cash_mult": 1.48, "xp_mult": 1.12, "influence": 108, "heat": 16, "intel": 3, "text": "به‌جای دزدیدن دفتر، معامله را تصاحب کردی؛ سود بزرگ‌تر و دشمنان بیشتر."},
            "scarred": {"name": "نقاب شکسته", "success": True, "cash_mult": .72, "xp_mult": 1.0, "influence": 72, "heat": 24, "intel": 2, "text": "با مدرک بیرون آمدی، اما نصف سالن چهره‌ات را دید."},
            "exposed": {"name": "چراغ‌های سالن", "success": False, "cash_mult": 0, "xp_mult": .42, "influence": -45, "heat": 35, "intel": 0, "text": "چراغ‌ها روشن شدند و تنها نقاب افتاده، نقاب تو بود."},
        },
    },
    "glass_vault": {
        "name": "خزانه شیشه‌ای", "icon": "💎", "difficulty": 4,
        "difficulty_name": "کابوس", "required_influence": 500,
        "energy": 45, "intel_cost": 10, "entry_cost": 320_000_000, "start_node": "perimeter",
        "base_cash": 1_250_000_000, "base_xp": 30_000, "base_dark_xp": 380,
        "description": "خزانه‌ای هوشمند هر تصمیم مهاجم را پیش‌بینی می‌کند؛ برای برد باید قابل پیش‌بینی نباشی.",
        "endings": {
            "zero_trace": {"name": "رد صفر", "success": True, "cash_mult": 1.25, "xp_mult": 1.30, "influence": 330, "heat": 8, "intel": 8, "text": "صبح، خزانه سالم بود؛ فقط چیزی برای نگهبانی باقی نمانده بود."},
            "kingmaker": {"name": "کلید شهر", "success": True, "cash_mult": 1.58, "xp_mult": 1.16, "influence": 285, "heat": 24, "intel": 5, "text": "هسته را فروختی و حالا چند قدرت بزرگ شهر به تو بدهکارند."},
            "burned": {"name": "شیشه سوخته", "success": True, "cash_mult": .68, "xp_mult": 1.05, "influence": 190, "heat": 38, "intel": 3, "text": "با بخشی از غنیمت گریختی؛ رد آتش مسیرت را لو داد."},
            "captured": {"name": "اتاق سفید", "success": False, "cash_mult": 0, "xp_mult": .48, "influence": -110, "heat": 48, "intel": 0, "text": "خزانه بسته شد و اتاقی سفید برای بازجویی تو باز شد."},
        },
    },
}

NODES = {
    "midnight_train": {
        "platform": {"title": "سکوی خاموش", "text": "قطار هفت دقیقه دیگر حرکت می‌کند. مأمور فهرست مسافران را می‌بندد و مه روی سقف واگن‌ها نشسته است.", "choices": {
            "manifest": {"icon": "🎫", "label": "با بارنامه جعلی وارد شو", "skill": "social", "target": 55, "success": "cargo", "failure": "inspector", "success_text": "مهر جعلی از زیر نور رد شد.", "failure_text": "مأمور تفاوت جوهر را دید.", "momentum_success": 4, "momentum_failure": -3, "danger_success": 0, "danger_failure": 2, "heat_success": 0, "heat_failure": 3},
            "roof": {"icon": "🌫️", "label": "از سقف واگن بالا برو", "skill": "stealth", "target": 61, "success": "cargo", "failure": "chase", "success_text": "مه تو را بلعید.", "failure_text": "صدای کفش روی فلز نگهبان را چرخاند.", "momentum_success": 5, "momentum_failure": -4, "danger_success": 1, "danger_failure": 3, "heat_success": 0, "heat_failure": 4},
        }},
        "inspector": {"title": "بازرسی دوم", "text": "مأمور دفتر را بسته و دستش روی بی‌سیم است. هنوز می‌توانی روایت را عوض کنی.", "choices": {
            "calm_lie": {"icon": "🗣️", "label": "یک داستان آرام بساز", "skill": "social", "target": 66, "success": "cargo", "failure": "end:caught", "success_text": "تردید مأمور به خستگی تبدیل شد.", "failure_text": "سؤال سوم، داستانت را شکست.", "momentum_success": 3, "momentum_failure": -5, "danger_success": 0, "danger_failure": 2, "heat_success": 1, "heat_failure": 7},
            "blackout": {"icon": "🔌", "label": "برق سکو را قطع کن", "skill": "tech", "target": 63, "success": "cargo", "failure": "chase", "success_text": "سکو سه ثانیه تاریک شد؛ کافی بود.", "failure_text": "فیوز پشتیبان پیش از تو بیدار شد.", "momentum_success": 4, "momentum_failure": -2, "danger_success": 1, "danger_failure": 3, "heat_success": 1, "heat_failure": 5},
        }},
        "cargo": {"title": "واگن بار", "text": "دو صندوق هم‌شکل روبه‌رویت است؛ یکی هدف، دیگری تله وزنی.", "choices": {
            "switch": {"icon": "⚙️", "label": "حسگر وزن را شبیه‌سازی کن", "skill": "tech", "target": 62, "success": "exit", "failure": "alarm", "success_text": "حسگر هنوز همان عدد را می‌خواند.", "failure_text": "یک گرم اختلاف برای آژیر کافی بود.", "momentum_success": 5, "momentum_failure": -4, "danger_success": 0, "danger_failure": 3, "heat_success": 0, "heat_failure": 5},
            "take_all": {"icon": "💪", "label": "هر دو صندوق را بردار", "skill": "force", "target": 58, "success": "chase", "failure": "alarm", "success_text": "وزن بیشتر، سود بیشتر؛ حالا باید فرار کنی.", "failure_text": "قفل دوم روی مچت بسته شد.", "momentum_success": 2, "momentum_failure": -4, "danger_success": 3, "danger_failure": 4, "heat_success": 3, "heat_failure": 6},
        }},
        "alarm": {"title": "سی ثانیه قرمز", "text": "درها یکی‌یکی قفل می‌شوند و بی‌سیم نگهبان‌ها نام واگن را فریاد می‌زند.", "choices": {
            "jam": {"icon": "📡", "label": "شبکه قفل‌ها را مختل کن", "skill": "tech", "target": 72, "success": "exit", "failure": "end:caught", "success_text": "در آخرین فریم باز ماند.", "failure_text": "شبکه تو را زودتر از تو شناخت.", "momentum_success": 4, "momentum_failure": -6, "danger_success": 1, "danger_failure": 3, "heat_success": 2, "heat_failure": 8},
            "jump": {"icon": "🪂", "label": "از پنجره به واگن بعد بپر", "skill": "force", "target": 70, "success": "chase", "failure": "end:caught", "success_text": "لبه فلزی را با یک دست گرفتی.", "failure_text": "نگهبان زودتر به پنجره رسید.", "momentum_success": 3, "momentum_failure": -6, "danger_success": 3, "danger_failure": 4, "heat_success": 4, "heat_failure": 9},
        }},
        "chase": {"title": "تعقیب روی ریل", "text": "نورافکن پشت سرت می‌لغزد و قطار وارد بخش صنعتی شهر می‌شود.", "choices": {
            "lose_tail": {"icon": "🏃", "label": "از پل سرویس بپر", "skill": "force", "target": 67, "success": "end:noisy", "failure": "end:caught", "success_text": "فرود درد داشت، اما آزاد بودی.", "failure_text": "پل پیش از قدم آخر تمام شد.", "momentum_success": 2, "momentum_failure": -6, "danger_success": 2, "danger_failure": 4, "heat_success": 5, "heat_failure": 10},
            "blend": {"icon": "🥷", "label": "میان کارگران محو شو", "skill": "stealth", "target": 72, "success": "end:perfect", "failure": "end:caught", "success_text": "نورافکن از صورت دیگری عبور کرد.", "failure_text": "لباس تمیزت میان کارگران فریاد می‌زد.", "momentum_success": 4, "momentum_failure": -6, "danger_success": 0, "danger_failure": 3, "heat_success": 1, "heat_failure": 9},
        }},
        "exit": {"title": "ایستگاه آخر", "text": "محموله دست توست. می‌توانی بی‌صدا ناپدید شوی یا همان‌جا خریدار تازه‌ای بسازی.", "choices": {
            "clean": {"icon": "🕳️", "label": "از تونل خدمات خارج شو", "skill": "stealth", "target": 60, "success": "end:perfect", "failure": "end:noisy", "success_text": "دوربین تونل فقط مه ضبط کرد.", "failure_text": "دوربین آخر یک سایه ثبت کرد.", "momentum_success": 3, "momentum_failure": -2, "danger_success": 0, "danger_failure": 2, "heat_success": 0, "heat_failure": 4},
            "buyer": {"icon": "🤝", "label": "در حرکت خریدار دوم پیدا کن", "skill": "social", "target": 65, "success": "end:rich", "failure": "end:noisy", "success_text": "دو پیام کافی بود تا قیمت عوض شود.", "failure_text": "خریدار آمد، اما تنها نبود.", "momentum_success": 3, "momentum_failure": -2, "danger_success": 2, "danger_failure": 3, "heat_success": 3, "heat_failure": 6},
        }},
    },
    "masked_ball": {
        "gate": {"title": "دروازه عمارت", "text": "دعوت‌نامه‌ها با چهره مهمان تطبیق داده می‌شوند؛ نقاب فقط نیمی از دروغ است.", "choices": {
            "borrow_name": {"icon": "🎭", "label": "هویت یک مهمان غایب را بازی کن", "skill": "social", "target": 66, "success": "ballroom", "failure": "service", "success_text": "نگهبان تو را با نامی دیگر خوش‌آمد گفت.", "failure_text": "نام درست بود؛ لحن نه.", "momentum_success": 4, "momentum_failure": -3, "danger_success": 0, "danger_failure": 2, "heat_success": 0, "heat_failure": 4},
            "service_door": {"icon": "🗝️", "label": "قفل ورودی کارکنان را باز کن", "skill": "tech", "target": 69, "success": "service", "failure": "exposure", "success_text": "قفل برای یک ثانیه تو را کارمند شناخت.", "failure_text": "سامانه شماره ابزار را ثبت کرد.", "momentum_success": 4, "momentum_failure": -4, "danger_success": 1, "danger_failure": 3, "heat_success": 1, "heat_failure": 5},
        }},
        "service": {"title": "راهروی خدمتکاران", "text": "پیشخدمت‌ها حرکتت را می‌پوشانند، اما مدیر سالن همه چهره‌ها را می‌شناسد.", "choices": {
            "command": {"icon": "🗣️", "label": "مثل مدیر تازه دستور بده", "skill": "social", "target": 70, "success": "ballroom", "failure": "exposure", "success_text": "اعتمادبه‌نفس جای کارت شناسایی را گرفت.", "failure_text": "مدیر واقعی پشت سرت ایستاده بود.", "momentum_success": 4, "momentum_failure": -5, "danger_success": 0, "danger_failure": 3, "heat_success": 1, "heat_failure": 6},
            "vent": {"icon": "🥷", "label": "از کانال تهویه عبور کن", "skill": "stealth", "target": 72, "success": "archive", "failure": "exposure", "success_text": "موسیقی صدای فلز را بلعید.", "failure_text": "پیچ زنگ‌زده روی زمین افتاد.", "momentum_success": 5, "momentum_failure": -5, "danger_success": 1, "danger_failure": 3, "heat_success": 0, "heat_failure": 6},
        }},
        "ballroom": {"title": "رقص اطلاعات", "text": "کلید آرشیو گردن میزبان است؛ صد مهمان، صد شاهد و تنها یک آهنگ فرصت داری.", "choices": {
            "dance": {"icon": "💃", "label": "میزبان را وارد رقص کن", "skill": "social", "target": 73, "success": "archive", "failure": "exposure", "success_text": "کلید میان چرخش دست‌ها صاحبش را عوض کرد.", "failure_text": "میزبان لبخند زد و نگهبان‌ها نزدیک شدند.", "momentum_success": 5, "momentum_failure": -5, "danger_success": 0, "danger_failure": 3, "heat_success": 1, "heat_failure": 7},
            "lights": {"icon": "💡", "label": "نور سالن را برنامه‌ریزی کن", "skill": "tech", "target": 75, "success": "archive", "failure": "service", "success_text": "سه ثانیه تاریکی، کلید را بی‌صاحب کرد.", "failure_text": "نور اضطراری فقط روی تو روشن شد.", "momentum_success": 4, "momentum_failure": -4, "danger_success": 1, "danger_failure": 3, "heat_success": 2, "heat_failure": 7},
        }},
        "archive": {"title": "دفتر بدهکاران", "text": "دفتر کاغذی کنار نسخه رمزگذاری‌شده است. یکی امن‌تر، دیگری باارزش‌تر.", "choices": {
            "copy": {"icon": "📖", "label": "فقط نسخه لازم را بردار", "skill": "stealth", "target": 72, "success": "exit", "failure": "exposure", "success_text": "صفحه‌ها جابه‌جا شدند، نه وزن قفسه.", "failure_text": "نخ امنیتی پاره شد.", "momentum_success": 5, "momentum_failure": -5, "danger_success": 0, "danger_failure": 3, "heat_success": 0, "heat_failure": 7},
            "own_auction": {"icon": "🧮", "label": "بدهی‌ها را همان‌جا بفروش", "skill": "tech", "target": 79, "success": "end:auctioneer", "failure": "exposure", "success_text": "مهمان‌ها بدون فهمیدن، مشتری تو شدند.", "failure_text": "قیمت اول را سامانه امنیتی پیشنهاد داد.", "momentum_success": 4, "momentum_failure": -6, "danger_success": 3, "danger_failure": 4, "heat_success": 5, "heat_failure": 9},
        }},
        "exposure": {"title": "نقاب ترک‌خورده", "text": "دو نگهبان راه را بسته‌اند و جمعیت هنوز نمی‌داند نمایش واقعی شروع شده است.", "choices": {
            "speech": {"icon": "🎙️", "label": "جمعیت را علیه میزبان بشوران", "skill": "social", "target": 80, "success": "exit", "failure": "end:exposed", "success_text": "شک، سالن را سریع‌تر از آتش گرفت.", "failure_text": "هیچ‌کس برای غریبه دست نزد.", "momentum_success": 3, "momentum_failure": -7, "danger_success": 2, "danger_failure": 4, "heat_success": 5, "heat_failure": 11},
            "break_line": {"icon": "💥", "label": "حلقه نگهبان‌ها را بشکن", "skill": "force", "target": 76, "success": "exit", "failure": "end:exposed", "success_text": "نقاب ماند؛ در شکست.", "failure_text": "نفر سوم را ندیده بودی.", "momentum_success": 2, "momentum_failure": -7, "danger_success": 3, "danger_failure": 5, "heat_success": 7, "heat_failure": 12},
        }},
        "exit": {"title": "آخرین نقاب", "text": "دفتر در دست توست؛ خروج آرام یا تبدیل مهمانی به بازار خودت؟", "choices": {
            "fade": {"icon": "🥷", "label": "با مهمان‌های خروجی محو شو", "skill": "stealth", "target": 74, "success": "end:phantom", "failure": "end:scarred", "success_text": "دروازه تعداد ورود و خروج را برابر دید.", "failure_text": "یک دوربین، نقابت را دیر شناخت.", "momentum_success": 4, "momentum_failure": -3, "danger_success": 0, "danger_failure": 2, "heat_success": 1, "heat_failure": 6},
            "take_stage": {"icon": "🎩", "label": "مزایده را تصاحب کن", "skill": "social", "target": 82, "success": "end:auctioneer", "failure": "end:scarred", "success_text": "چکش آخر را تو زدی.", "failure_text": "سود را بردی، ولی نامت را جا گذاشتی.", "momentum_success": 5, "momentum_failure": -3, "danger_success": 3, "danger_failure": 3, "heat_success": 6, "heat_failure": 8},
        }},
    },
    "glass_vault": {
        "perimeter": {"title": "حلقه بدون سایه", "text": "خزانه از الگوی حرکت شهر تغذیه می‌کند. قدم عادی مشکوک‌تر از قدم اشتباه است.", "choices": {
            "blind_spot": {"icon": "📡", "label": "نقطه کور مصنوعی بساز", "skill": "tech", "target": 77, "success": "lasers", "failure": "drone", "success_text": "سامانه نبودنت را ثبت کرد.", "failure_text": "نقطه کور، دقیقاً روی تو بسته شد.", "momentum_success": 5, "momentum_failure": -4, "danger_success": 0, "danger_failure": 3, "heat_success": 1, "heat_failure": 7},
            "delivery": {"icon": "🚚", "label": "در قالب تیم تعمیر وارد شو", "skill": "social", "target": 80, "success": "lasers", "failure": "drone", "success_text": "سامانه برای تعمیر خودش در را باز کرد.", "failure_text": "هیچ تعمیراتی در برنامه نبود.", "momentum_success": 4, "momentum_failure": -5, "danger_success": 1, "danger_failure": 3, "heat_success": 2, "heat_failure": 8},
        }},
        "drone": {"title": "چشم پرنده", "text": "پهپاد بی‌صدا فاصله را می‌بندد؛ شناسایی هنوز کامل نشده است.", "choices": {
            "spoof": {"icon": "💻", "label": "شناسه پهپاد را جعل کن", "skill": "tech", "target": 84, "success": "lasers", "failure": "end:captured", "success_text": "پهپاد تو را بخشی از دیوار دید.", "failure_text": "امضای جعلی به مرکز فرمان رسید.", "momentum_success": 4, "momentum_failure": -8, "danger_success": 1, "danger_failure": 4, "heat_success": 2, "heat_failure": 12},
            "drop": {"icon": "🪂", "label": "از کانال بار پایین برو", "skill": "force", "target": 81, "success": "lasers", "failure": "end:captured", "success_text": "فرود سخت بود؛ شناسایی ناقص ماند.", "failure_text": "کانال پیش از تو قفل شد.", "momentum_success": 3, "momentum_failure": -8, "danger_success": 3, "danger_failure": 5, "heat_success": 5, "heat_failure": 13},
        }},
        "lasers": {"title": "راهروی احتمال", "text": "لیزرها مسیر ثابت ندارند؛ هسته رفتار بعدی تو را حدس می‌زند.", "choices": {
            "random_walk": {"icon": "♟️", "label": "الگوی حرکت غیرمنطقی بساز", "skill": "stealth", "target": 82, "success": "core", "failure": "lockdown", "success_text": "پیش‌بینی‌گر برای اولین بار مکث کرد.", "failure_text": "تصادفی‌بودن هم الگویی داشت.", "momentum_success": 6, "momentum_failure": -5, "danger_success": 0, "danger_failure": 3, "heat_success": 1, "heat_failure": 8},
            "rewrite": {"icon": "📡", "label": "نقشه لیزرها را بازنویسی کن", "skill": "tech", "target": 86, "success": "core", "failure": "lockdown", "success_text": "لیزرها راهی برای عبورت طراحی کردند.", "failure_text": "کد تو به دیوار قرمز تبدیل شد.", "momentum_success": 6, "momentum_failure": -6, "danger_success": 1, "danger_failure": 4, "heat_success": 2, "heat_failure": 9},
        }},
        "lockdown": {"title": "قفل انطباقی", "text": "اکسیژن کم می‌شود و هسته هر پنج ثانیه کلید تازه‌ای می‌سازد.", "choices": {
            "overload": {"icon": "⚡", "label": "کلیدساز را اضافه‌بار بده", "skill": "tech", "target": 89, "success": "core", "failure": "end:captured", "success_text": "هسته برای یک لحظه خودش را قفل کرد.", "failure_text": "اضافه‌بار به مدار تو برگشت.", "momentum_success": 5, "momentum_failure": -9, "danger_success": 2, "danger_failure": 5, "heat_success": 4, "heat_failure": 15},
            "break_floor": {"icon": "💥", "label": "کف سرویس را بشکن", "skill": "force", "target": 84, "success": "core", "failure": "end:captured", "success_text": "معماری قدیمی‌تر از هوش خزانه بود.", "failure_text": "لایه دوم، بتن نبود.", "momentum_success": 3, "momentum_failure": -9, "danger_success": 4, "danger_failure": 5, "heat_success": 7, "heat_failure": 16},
        }},
        "core": {"title": "هسته پیش‌بینی", "text": "می‌توانی دارایی را برداری یا هسته‌ای را بفروشی که آینده حمله‌ها را می‌بیند.", "choices": {
            "silent_copy": {"icon": "💎", "label": "دارایی را با نسخه جعلی عوض کن", "skill": "stealth", "target": 85, "success": "escape", "failure": "burn_route", "success_text": "وزن و دما تغییر نکرد؛ مالکیت چرا.", "failure_text": "نسخه جعلی یک میلی‌متر بلندتر بود.", "momentum_success": 6, "momentum_failure": -6, "danger_success": 0, "danger_failure": 4, "heat_success": 1, "heat_failure": 10},
            "steal_core": {"icon": "🧠", "label": "خود هسته را جدا کن", "skill": "tech", "target": 91, "success": "king_exit", "failure": "burn_route", "success_text": "برای اولین بار، خزانه آینده خودش را ندید.", "failure_text": "هسته لحظه جداشدن را پیش‌بینی کرده بود.", "momentum_success": 7, "momentum_failure": -7, "danger_success": 4, "danger_failure": 5, "heat_success": 8, "heat_failure": 13},
        }},
        "burn_route": {"title": "مسیر سوخته", "text": "دود شیشه را مات کرده و نیروهای واکنش سریع نزدیک‌اند؛ هنوز بخشی از غنیمت همراهت است.", "choices": {
            "blast": {"icon": "💥", "label": "خروج اضطراری را منفجر کن", "skill": "force", "target": 86, "success": "end:burned", "failure": "end:captured", "success_text": "شیشه شکست و شب وارد خزانه شد.", "failure_text": "شارژ انفجاری فقط مسیر را بست.", "momentum_success": 3, "momentum_failure": -9, "danger_success": 3, "danger_failure": 5, "heat_success": 10, "heat_failure": 18},
            "maintenance": {"icon": "🥷", "label": "در دود وارد کانال نگهداری شو", "skill": "stealth", "target": 89, "success": "end:burned", "failure": "end:captured", "success_text": "دود، آخرین دوربین را کور کرد.", "failure_text": "حسگر حرارتی دود را نمی‌دید؛ تو را دید.", "momentum_success": 4, "momentum_failure": -9, "danger_success": 2, "danger_failure": 5, "heat_success": 8, "heat_failure": 17},
        }},
        "escape": {"title": "خروج بدون گذشته", "text": "غنیمت امن است؛ تنها یک در میان تو و افسانه رد صفر مانده.", "choices": {
            "erase": {"icon": "🧬", "label": "اثر زیستی را پاک کن", "skill": "tech", "target": 86, "success": "end:zero_trace", "failure": "end:burned", "success_text": "سامانه حضور انسانی ثبت نکرد.", "failure_text": "یک تار مو برای ساختن پرونده کافی بود.", "momentum_success": 5, "momentum_failure": -4, "danger_success": 0, "danger_failure": 3, "heat_success": 1, "heat_failure": 8},
            "shadow": {"icon": "🥷", "label": "پشت تیم واکنش خارج شو", "skill": "stealth", "target": 88, "success": "end:zero_trace", "failure": "end:burned", "success_text": "آن‌ها وارد شدند و سایه‌شان بیرون آمد.", "failure_text": "یکی از سایه‌ها خلاف نور حرکت کرد.", "momentum_success": 5, "momentum_failure": -4, "danger_success": 1, "danger_failure": 3, "heat_success": 2, "heat_failure": 9},
        }},
        "king_exit": {"title": "خریدار آینده", "text": "هسته ارزش پول نیست؛ ارزش قدرت است. خریدار منتظر مدرک زنده ماندنش است.", "choices": {
            "auction_core": {"icon": "👑", "label": "هسته را میان سه جناح بفروش", "skill": "social", "target": 90, "success": "end:kingmaker", "failure": "end:burned", "success_text": "سه جناح پیشنهاد دادند و هر سه بدهکار شدند.", "failure_text": "چهارمین جناح معامله را شنید.", "momentum_success": 6, "momentum_failure": -5, "danger_success": 4, "danger_failure": 5, "heat_success": 10, "heat_failure": 15},
            "vanish_core": {"icon": "🕳️", "label": "هسته را برای خودت پنهان کن", "skill": "stealth", "target": 92, "success": "end:zero_trace", "failure": "end:burned", "success_text": "حتی خریدار هم مطمئن نیست هسته وجود داشت.", "failure_text": "پنهان‌کردن آینده، گذشته‌ات را لو داد.", "momentum_success": 7, "momentum_failure": -6, "danger_success": 2, "danger_failure": 5, "heat_success": 5, "heat_failure": 14},
        }},
    },
}

RECRUIT_SKILL_BONUS = {"informant": ("stealth", 7), "fixer": ("social", 7), "driver": ("force", 7), "accountant": ("tech", 7)}


def clamp_int(value: int, low: int, high: int) -> int:
    return max(low, min(high, int(value)))


def get_case(case_key: str) -> dict | None:
    return CASES.get(str(case_key or ""))


def get_node(case_key: str, node_key: str) -> dict | None:
    return NODES.get(str(case_key or ""), {}).get(str(node_key or ""))


def get_choice(case_key: str, node_key: str, choice_key: str) -> dict | None:
    node = get_node(case_key, node_key)
    return (node.get("choices") or {}).get(str(choice_key or "")) if node else None


def get_ending(case_key: str, ending_key: str) -> dict | None:
    case = get_case(case_key)
    return (case.get("endings") or {}).get(str(ending_key or "")) if case else None


def get_tool(tool_key: str | None) -> dict | None:
    return TOOLS.get(str(tool_key or ""))


def rank_index(influence: int) -> int:
    key = D.rank_for(influence)["key"]
    return next((i for i, tier in enumerate(D.RANK_TIERS) if tier["key"] == key), 0)


def choice_chance(choice: dict, level: int, influence: int, heat: int, momentum: int, danger: int, recruit_keys=(), tool_key: str | None = None, team_effectiveness: float = 1.0, team_tactic: str = "balanced") -> dict:
    skill = str(choice["skill"])
    level_bonus = max(0, min(10, int(level or 1) - D.ACCESS_LEVEL)) * 1.5
    tier_bonus = rank_index(influence) * 2.0
    recruit_bonus = sum(bonus for key, (matched, bonus) in RECRUIT_SKILL_BONUS.items() if key in set(recruit_keys or ()) and matched == skill) * float(team_effectiveness)
    tactic_bonus = (4 * float(team_effectiveness)) if ((team_tactic == "silent" and skill == "stealth") or (team_tactic == "aggressive" and skill == "force")) else 0
    tool = get_tool(tool_key)
    tool_bonus = int(tool["bonus"]) if tool and skill in tuple(tool["skills"]) else 0
    heat_penalty = max(0, int(heat or 0) - 20) * .15
    danger_penalty = max(0, int(danger or 0)) * 1.25
    target_penalty = int(choice["target"]) - 50
    chance = D.clamp(50 + level_bonus + tier_bonus + recruit_bonus + int(momentum or 0) + tool_bonus + tactic_bonus - heat_penalty - danger_penalty - target_penalty, 8, 95)
    return {"chance": round(chance, 2), "skill": skill, "tool_applies": bool(tool_bonus), "tool_bonus": tool_bonus, "level_bonus": level_bonus, "rank_bonus": tier_bonus, "recruit_bonus": recruit_bonus, "heat_penalty": round(heat_penalty, 2), "danger_penalty": round(danger_penalty, 2)}


def resolve_choice(choice: dict, chance_info: dict, roll: float, momentum: int, danger: int) -> dict:
    success = float(roll) < float(chance_info["chance"])
    suffix = "success" if success else "failure"
    return {
        "success": success,
        "destination": str(choice[suffix]),
        "text": str(choice[f"{suffix}_text"]),
        "momentum": clamp_int(int(momentum or 0) + int(choice.get(f"momentum_{suffix}", 0)), MOMENTUM_MIN, MOMENTUM_MAX),
        "danger": clamp_int(int(danger or 0) + int(choice.get(f"danger_{suffix}", 0)), DANGER_MIN, DANGER_MAX),
        "heat": max(0, int(choice.get(f"heat_{suffix}", 0))),
        "tool_consumed": bool(chance_info.get("tool_applies")),
    }


def ending_reward(case_key: str, ending_key: str, danger: int = 0, cash_factor_pct: int = 100, steps: int = 1, passed_checks: int = 0) -> dict:
    case = get_case(case_key); ending = get_ending(case_key, ending_key)
    if not case or not ending:
        return {}
    factor = int(D.clamp(int(cash_factor_pct or 100), 90, 110))
    success = bool(ending["success"])
    safe_steps = max(1, min(CASE_HISTORY_LIMIT, int(steps or 1)))
    safe_passes = max(0, min(safe_steps, int(passed_checks or 0)))
    cash_risk_factor = 1 + min(DANGER_MAX, max(0, int(danger or 0))) * .02 if success else 1
    # XP is explicit: case difficulty/base × ending × progress × passed checks × risk.
    # A failure after several phases therefore teaches more than failing at the first gate.
    progress_factor = (0.50 + min(5, safe_steps) * .10) if not success else (0.91 + min(5, safe_steps) * .03)
    skill_factor = 1 + min(6, safe_passes) * .04
    xp_risk_factor = 1 + min(DANGER_MAX, max(0, int(danger or 0))) * .01
    cash = round(int(case["base_cash"]) * float(ending["cash_mult"]) * cash_risk_factor * factor / 100)
    xp = max(100, round(int(case["base_xp"]) * float(ending["xp_mult"]) * progress_factor * skill_factor * xp_risk_factor))
    dark_xp = max(1, round(int(case["base_dark_xp"]) * float(ending["xp_mult"]) * progress_factor * skill_factor * xp_risk_factor))
    return {
        "success": success, "cash": max(0, cash), "xp": xp, "dark_xp": dark_xp,
        "influence": int(ending["influence"]), "heat": int(ending["heat"]), "intel": int(ending["intel"]),
        "ending_key": ending_key, "steps": safe_steps, "passed_checks": safe_passes,
        "progress_factor": round(progress_factor, 2), "skill_factor": round(skill_factor, 2),
        "risk_factor": round(xp_risk_factor, 2),
    }


def validate_case_graph() -> list[str]:
    errors: list[str] = []
    for case_key, case in CASES.items():
        nodes = NODES.get(case_key, {})
        if case.get("start_node") not in nodes:
            errors.append(f"{case_key}: missing start")
        for node_key, node in nodes.items():
            if not node.get("choices"):
                errors.append(f"{case_key}:{node_key}: no choices")
            for choice_key, choice in (node.get("choices") or {}).items():
                for branch in ("success", "failure"):
                    dest = str(choice.get(branch, ""))
                    if dest.startswith("end:"):
                        if dest[4:] not in case.get("endings", {}):
                            errors.append(f"{case_key}:{node_key}:{choice_key}: bad ending {dest}")
                    elif dest not in nodes:
                        errors.append(f"{case_key}:{node_key}:{choice_key}: bad node {dest}")
    return errors
