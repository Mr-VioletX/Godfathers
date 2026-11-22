# -*- coding: utf-8 -*-
"""سازنده‌ی سند اکسلِ سیستم القاب + تولیدِ فایلِ داده‌ی titles.py
یک منبعِ حقیقت (TITLES) → هم خروجیِ اکسل و هم ماژولِ داده‌ی ربات.
"""
import os
import pprint

OUT_DIR = "/data/out"
BOT_DIR = os.path.join(OUT_DIR, "godfather_bot")
DATA_PY = os.path.join(BOT_DIR, "app", "data", "titles.py")
XLSX = os.path.join(OUT_DIR, "سیستم_القاب_مرحله۱۱.xlsx")

# ---------------------------------------------------------------------------
# فیلدهای هر لقب:
#   key        : کلید یکتا (انگلیسی) برای دیتابیس/کد
#   name       : نامِ فارسیِ لقب
#   latin      : معادلِ لاتین (اگر داشته باشد)
#   category   : female | male | legendary   (دسته‌بندی)
#   gender     : female | male | any         (مناسبِ چه جنسیتی)
#   unique     : True یعنی «یونیک/تک» (فقط یک دارنده در کلِ سرور)
#   stat       : نامِ شمارنده در PlayerStats (None یعنی رویدادی/دستی)
#   op         : عملگرِ مقایسه (">=" | ">")
#   value      : آستانه‌ی لازم
#   special    : برای القابِ رویدادی/دستی (اعطا از سیستم‌های دیگر)
#   req        : متنِ فارسیِ فعالیتِ موردِنیاز (برای اکسل و نمایش)
#   note       : توضیحِ طراحی
# ---------------------------------------------------------------------------
TITLES = [
    # ===================== دسته‌ی زنانه (Female) =====================
    dict(key="queen_of_shadows", name="ملکه سایه‌ها", latin="Queen of Shadows",
         category="female", gender="female", unique=True,
         stat="spy_success", op=">=", value=100, special=None,
         req="اولین بازیکنِ دختر که به ۱۰۰ جاسوسیِ موفق برسد",
         note="تک؛ به اولین واجدِ شرایط قفل می‌شود (first-claim)"),
    dict(key="lilith", name="لیلیث", latin="Lilith",
         category="female", gender="female", unique=True,
         stat="countries_founded", op=">=", value=1, special=None,
         req="اولین بازیکنِ دختر که یک کشور تأسیس کند",
         note="تک؛ نیازمندِ سیستمِ کشورسازی (مرحله ۱۲)"),
    dict(key="heir_of_lilith", name="وارث لیلیث", latin="Heir of Lilith",
         category="female", gender="female", unique=True,
         stat="female_rank", op="<=", value=1, special=None,
         req="رسیدن به رتبه‌ی ۱ در میانِ بازیکنانِ دختر (۵۰ جاسوسی + ۵۰ جنگِ موفق نیز شرطِ ورود است)",
         note="تک؛ رتبه‌ی پویا، دارنده با جابه‌جاییِ رتبه عوض می‌شود"),
    dict(key="freya", name="فریا", latin="Freya",
         category="female", gender="female", unique=False,
         stat="war_assists", op=">=", value=50, special=None,
         req="۵۰ بار کمک به هم‌تیمی‌ها در جنگ",
         note="عادی"),
    dict(key="lagertha", name="لاگرتا", latin="Lagertha",
         category="female", gender="female", unique=False,
         stat="mafia_wins", op=">=", value=200, special=None,
         req="۲۰۰ پیروزی در نبردهای مافیایی",
         note="عادی"),
    dict(key="goddess_of_war", name="الهه جنگ", latin="Goddess of War",
         category="female", gender="female", unique=False,
         stat="battle_wins", op=">=", value=300, special=None,
         req="۳۰۰ پیروزی در نبردها",
         note="عادی"),
    dict(key="queen_of_olympus", name="ملکه المپ (هرا)", latin="Hera",
         category="female", gender="female", unique=True,
         stat=None, op=None, value=None, special="paired_with_zeus",
         req="لقبِ همراهِ «زئوس»؛ دارنده‌ی زئوس این لقب را می‌خرد تا برای بانوی منتخبش (هرا) فعال شود",
         note="تک و دستی؛ فقط از طریقِ دارنده‌ی زئوس اعطا می‌شود"),
    dict(key="dark_empress", name="امپراتریس تاریکی", latin="Dark Empress",
         category="female", gender="female", unique=False,
         stat="cities_controlled", op=">=", value=10, special=None,
         req="کنترلِ هم‌زمانِ ۱۰ شهر",
         note="عادی؛ نیازمندِ سیستمِ شهر (مرحله ۱۲)"),
    dict(key="lady_of_valhalla", name="بانوی والهالا", latin="Lady of Valhalla",
         category="female", gender="female", unique=True,
         stat="military_power", op=">=", value=1, special="top_military_power",
         req="داشتنِ بالاترین قدرتِ نظامیِ سرور",
         note="تک؛ رتبه‌ی پویا (بالاترین قدرت نظامی)"),
    dict(key="lady_of_shadows", name="بانوی سایه‌ها", latin="Lady of Shadows",
         category="female", gender="female", unique=False,
         stat="spy_success", op=">=", value=150, special=None,
         req="۱۵۰ جاسوسیِ موفق",
         note="عادی"),
    dict(key="lady_of_lightning", name="بانوی آذرخش (رعد)", latin="Lady of Lightning",
         category="female", gender="female", unique=False,
         stat="enemy_bases_destroyed", op=">=", value=100, special=None,
         req="نابودیِ ۱۰۰ پایگاهِ دشمن",
         note="فعالیتِ خالی بود؛ طراحی شد: نابودیِ پایگاه دشمن"),
    dict(key="fire_queen", name="ملکه آتش", latin="Fire Queen",
         category="female", gender="female", unique=False,
         stat="cities_captured", op=">=", value=20, special=None,
         req="تصرفِ ۲۰ شهر",
         note="عادی"),
    dict(key="lady_of_death", name="بانوی مرگ", latin="Lady of Death",
         category="female", gender="female", unique=False,
         stat="rival_bosses_killed", op=">=", value=50, special=None,
         req="حذفِ ۵۰ رئیسِ مافیای رقیب",
         note="عادی"),
    dict(key="queen_of_vengeance", name="ملکه انتقام", latin="Queen of Vengeance",
         category="female", gender="female", unique=False,
         stat="revenge_wins", op=">=", value=20, special=None,
         req="شکست دادنِ ۲۰ بازیکنی که قبلاً به تو حمله کرده‌اند",
         note="عادی"),
    dict(key="lady_of_storm", name="بانوی طوفان", latin="Lady of Storm",
         category="female", gender="female", unique=False,
         stat="country_wars_won", op=">=", value=100, special=None,
         req="پیروزی در ۱۰۰ جنگِ کشوری",
         note="عادی"),
    dict(key="goddess_of_economy", name="الهه اقتصاد", latin="Goddess of Economy",
         category="female", gender="female", unique=False,
         stat="capital", op=">=", value=10_000_000_000, special=None,
         req="رسیدن به ۱۰ میلیارد دلار سرمایه",
         note="عادی؛ capital از موجودیِ بازیکن خوانده می‌شود"),
    dict(key="golden_lady", name="بانوی زرین", latin="Golden Lady",
         category="female", gender="female", unique=False,
         stat="companies", op=">=", value=100, special=None,
         req="مالکیتِ ۱۰۰ شرکت",
         note="عادی"),
    dict(key="queen_of_wolves", name="ملکه گرگ‌ها", latin="Queen of Wolves",
         category="female", gender="female", unique=False,
         stat="org_members", op=">=", value=500, special=None,
         req="داشتنِ ۵۰۰ عضوِ فعال در سازمان",
         note="فعالیتِ خالی بود؛ طراحی شد: اعضای فعالِ سازمان"),
    dict(key="lady_of_night", name="بانوی شب (ملکه شب)", latin="Lady of Night",
         category="female", gender="female", unique=False,
         stat="sabotage_success", op=">=", value=200, special=None,
         req="۲۰۰ عملیاتِ خرابکاریِ موفق",
         note="عادی"),
    dict(key="crowned_of_nation", name="تاج‌دار ملت", latin="Crowned of the Nation",
         category="female", gender="female", unique=False,
         stat="satisfaction_days_90", op=">=", value=60, special=None,
         req="حفظِ ۹۰٪ رضایتِ مردم برای ۶۰ روز",
         note="عادی؛ شمارنده‌ی روزهای رضایتِ بالای ۹۰٪"),
    dict(key="queen_of_mafia", name="ملکه مافیا", latin="Queen of Mafia",
         category="female", gender="female", unique=True,
         stat=None, op=None, value=None, special="biggest_gang",
         req="رهبریِ بزرگ‌ترین باندِ سرور",
         note="تک و پویا؛ به رهبرِ بزرگ‌ترین باند تعلق می‌گیرد"),
    dict(key="ice_lady", name="بانوی یخی", latin="Ice Lady",
         category="female", gender="female", unique=False,
         stat="consecutive_defense_wins", op=">=", value=30, special=None,
         req="۳۰ دفاعِ موفقِ متوالی بدونِ باخت",
         note="فعالیتِ خالی بود؛ طراحی شد: دفاعِ متوالیِ بی‌باخت"),
    dict(key="goddess_of_darkness", name="الهه تاریکی", latin="Goddess of Darkness",
         category="female", gender="female", unique=False,
         stat="spy_success", op=">=", value=500, special=None,
         req="۵۰۰ جاسوسیِ موفق (تسلطِ کامل بر تاریکی)",
         note="فعالیتِ خالی بود؛ طراحی شد: استادِ جاسوسی"),
    dict(key="ruler_of_fate", name="فرمانروای سرنوشت", latin="Ruler of Fate",
         category="female", gender="female", unique=False,
         stat="level", op=">=", value=50, special=None,
         req="رسیدن به سطحِ ۵۰ (سطحِ نهایی)",
         note="فعالیتِ خالی بود؛ طراحی شد: رسیدن به سقفِ سطح"),
    dict(key="crown_of_olympus_f", name="تاج‌دار المپ", latin="Crown of Olympus",
         category="female", gender="female", unique=True,
         stat="female_legendary_titles", op=">=", value=5, special=None,
         req="داشتنِ هم‌زمانِ ۵ لقبِ اسطوره‌ایِ زنانه",
         note="فعالیتِ خالی بود؛ طراحی شد: گردآوریِ ۵ لقبِ زنانه"),
    dict(key="legendary_goddess", name="الهه افسانه‌ای", latin="Legendary Goddess",
         category="female", gender="female", unique=True,
         stat=None, op=None, value=None, special="all_female_achievements",
         req="تکمیلِ تمامِ دستاوردهای ویژه‌ی دخترانه",
         note="تک؛ رویدادی، پس از کاملِ دستاوردهای زنانه"),

    # ===================== دسته‌ی مردانه (Male) =====================
    dict(key="god_of_war", name="خدای جنگ", latin="God of War",
         category="male", gender="male", unique=True,
         stat="mafia_wins", op=">=", value=100, special=None,
         req="اولین بازیکن که به ۱۰۰ جنگِ مافیاییِ موفق برسد",
         note="تک؛ به اولین واجدِ شرایط قفل می‌شود"),
    dict(key="zeus", name="زئوس", latin="Zeus",
         category="male", gender="male", unique=True,
         stat=None, op=None, value=None, special="vip_or_top_power",
         req="قدرتمندترین بازیکنِ سرور (رتبه ۱ قدرت) — یا خریدِ VIPِ فروشِ تکیِ گران‌قیمت",
         note="تک؛ خدای خدایان؛ VIP فروش تکی یا رتبه ۱ قدرت"),
    dict(key="hades", name="هادس", latin="Hades",
         category="male", gender="male", unique=False,
         stat="enemies_defeated", op=">=", value=1000, special=None,
         req="شکست دادنِ ۱۰۰۰ دشمن",
         note="عادی"),
    dict(key="poseidon", name="پوزیدون", latin="Poseidon",
         category="male", gender="male", unique=True,
         stat=None, op=None, value=None, special="all_ports_controlled",
         req="تسلط بر تمامِ بنادرِ نقشه",
         note="تک و پویا؛ کنترلِ کاملِ بنادر"),
    dict(key="ares", name="آرس", latin="Ares",
         category="male", gender="male", unique=False,
         stat="battles_without_loss", op=">=", value=300, special=None,
         req="۳۰۰ نبرد بدونِ شکست",
         note="عادی"),
    dict(key="thor", name="ثور", latin="Thor",
         category="male", gender="male", unique=False,
         stat="country_wars_won", op=">=", value=500, special=None,
         req="۵۰۰ پیروزی در جنگ‌های کشوری",
         note="عادی"),
    dict(key="odin", name="اودین", latin="Odin",
         category="male", gender="male", unique=True,
         stat="power_rank1_days", op=">=", value=30, special=None,
         req="حفظِ رتبه ۱ قدرت به مدتِ ۳۰ روز",
         note="تک؛ به اولین کسی که ۳۰ روز صدرنشین بماند"),
    dict(key="loki", name="لوکی", latin="Loki",
         category="male", gender="male", unique=False,
         stat="spy_success", op=">=", value=200, special=None,
         req="۲۰۰ عملیاتِ جاسوسیِ موفق",
         note="عادی"),
    dict(key="anubis", name="آنوبیس", latin="Anubis",
         category="male", gender="male", unique=False,
         stat="rival_gangs_destroyed", op=">=", value=200, special=None,
         req="نابودیِ ۲۰۰ باندِ رقیب",
         note="عادی"),
    dict(key="horus", name="هوروس", latin="Horus",
         category="male", gender="male", unique=True,
         stat="countries_founded", op=">=", value=1, special=None,
         req="اولین بازیکنی که کشور تأسیس کند",
         note="تک؛ به اولین بنیان‌گذارِ کشور (هر جنسیت واجدِ شرط، عنوانِ مردانه)"),
    dict(key="ragnar", name="رگنار", latin="Ragnar",
         category="male", gender="male", unique=False,
         stat="win_streak", op=">=", value=100, special=None,
         req="۱۰۰ پیروزیِ متوالی",
         note="عادی"),
    dict(key="floki", name="فلوکی", latin="Floki",
         category="male", gender="male", unique=False,
         stat="spy_tech_built", op=">=", value=100, special=None,
         req="ساختِ تمامِ فناوری‌های جاسوسی (۱۰۰٪)",
         note="عادی؛ درصدِ تکمیلِ درختِ فناوریِ جاسوسی"),
    dict(key="bjorn", name="بیورن", latin="Bjorn",
         category="male", gender="male", unique=False,
         stat="cities_captured", op=">=", value=25, special=None,
         req="فتحِ ۲۵ شهر",
         note="عادی"),
    dict(key="ivar", name="ایوار", latin="Ivar",
         category="male", gender="male", unique=False,
         stat="rival_bosses_killed", op=">=", value=100, special=None,
         req="شکست دادنِ ۱۰۰ رئیسِ مافیا",
         note="عادی"),
    dict(key="leonidas", name="لئونیداس", latin="Leonidas",
         category="male", gender="male", unique=False,
         stat="defenses_won", op=">=", value=100, special=None,
         req="دفاعِ موفق از کشور در ۱۰۰ حمله",
         note="عادی"),
    dict(key="achilles", name="آشیل", latin="Achilles",
         category="male", gender="male", unique=False,
         stat="battles_without_loss", op=">=", value=200, special=None,
         req="شکست‌نخوردن در ۲۰۰ نبرد",
         note="عادی"),
    dict(key="great_devil", name="شیطان بزرگ", latin="Great Devil",
         category="male", gender="male", unique=False,
         stat="attacks_success", op=">=", value=1000, special=None,
         req="انجامِ ۱۰۰۰ حمله‌ی موفق",
         note="عادی"),
    dict(key="mafia_sultan", name="سلطان مافیا", latin="Mafia Sultan",
         category="male", gender="male", unique=False,
         stat="city_economy_pct", op=">=", value=50, special=None,
         req="کنترلِ ۵۰٪ اقتصادِ شهر",
         note="عادی"),
    dict(key="ruler_of_olympus", name="فرمانروای المپ", latin="Ruler of Olympus",
         category="male", gender="male", unique=False,
         stat="countries_conquered", op=">=", value=5, special=None,
         req="تصرفِ ۵ کشور",
         note="عادی"),
    dict(key="emperor_of_shadows", name="امپراتور سایه‌ها", latin="Emperor of Shadows",
         category="male", gender="male", unique=True,
         stat=None, op=None, value=None, special="all_war_achievements",
         req="تکمیلِ تمامِ دستاوردهای جنگی",
         note="تک؛ رویدادی، پس از کاملِ دستاوردهای جنگی"),
    dict(key="lord_of_thunder", name="ارباب رعد", latin="Lord of Thunder",
         category="male", gender="male", unique=False,
         stat="enemy_bases_destroyed", op=">=", value=250, special=None,
         req="نابودیِ ۲۵۰ پایگاهِ دشمن با آذرخش",
         note="فعالیتِ خالی بود؛ طراحی شد: نسخه‌ی مردانه‌ی آذرخش"),
    dict(key="king_of_valhalla", name="پادشاه والهالا", latin="King of Valhalla",
         category="male", gender="male", unique=True,
         stat="military_power", op=">=", value=1, special="top_military_power",
         req="داشتنِ بالاترین قدرتِ نظامیِ سرور (نسخه‌ی مردانه‌ی بانوی والهالا)",
         note="تک و پویا"),

    # ===================== دسته‌ی اسطوره‌ای/مشترک (Legendary) =====================
    dict(key="world_conqueror", name="فاتح جهان", latin="World Conqueror",
         category="legendary", gender="any", unique=False,
         stat="countries_conquered", op=">=", value=10, special=None,
         req="فتحِ ۱۰ کشور",
         note="مشترک"),
    dict(key="absolute_ruler", name="حاکم مطلق", latin="Absolute Ruler",
         category="legendary", gender="any", unique=True,
         stat="map_control_pct", op=">", value=50, special=None,
         req="کنترلِ بیش از ۵۰٪ نقشه‌ی سرور",
         note="تک و پویا"),
    dict(key="immortal", name="جاودانه", latin="Immortal",
         category="legendary", gender="any", unique=False,
         stat="active_days", op=">=", value=365, special=None,
         req="یک سال حضورِ فعال بدونِ حذفِ حساب",
         note="مشترک"),
    dict(key="legend", name="اسطوره", latin="Legend",
         category="legendary", gender="any", unique=False,
         stat="achievements_pct", op=">=", value=100, special=None,
         req="تکمیلِ ۱۰۰٪ دستاوردهای بازی",
         note="مشترک"),
    dict(key="phoenix", name="ققنوس", latin="Phoenix",
         category="legendary", gender="any", unique=False,
         stat=None, op=None, value=None, special="phoenix_return",
         req="بازگشت از نابودیِ کامل و رسیدنِ دوباره به رتبه‌ی ۱۰ برتر",
         note="رویدادی؛ از سیستمِ رتبه‌بندی اعطا می‌شود"),
    dict(key="destroyer", name="نابودگر", latin="Destroyer",
         category="legendary", gender="any", unique=False,
         stat="enemy_bases_destroyed", op=">=", value=500, special=None,
         req="نابودیِ ۵۰۰ پایگاهِ دشمن",
         note="مشترک"),
    dict(key="king_of_economy", name="پادشاه اقتصاد", latin="King of Economy",
         category="legendary", gender="any", unique=False,
         stat="capital", op=">=", value=100_000_000_000, special=None,
         req="رسیدن به ۱۰۰ میلیارد دلار سرمایه",
         note="مشترک"),
    dict(key="emperor_of_world", name="امپراتور جهان", latin="Emperor of the World",
         category="legendary", gender="any", unique=True,
         stat=None, op=None, value=None, special="triple_top",
         req="داشتنِ هم‌زمانِ بزرگ‌ترین اقتصاد، ارتش و کشورِ سرور",
         note="تک و پویا؛ سه صدرنشینیِ هم‌زمان"),
    dict(key="apocalypse", name="آخرالزمان", latin="Apocalypse",
         category="legendary", gender="any", unique=True,
         stat=None, op=None, value=None, special="apocalypse_event",
         req="آغازِ بزرگ‌ترین جنگِ تاریخِ سرور",
         note="تک و رویدادی"),
    dict(key="server_legend", name="افسانه سرور", latin="Server Legend",
         category="legendary", gender="any", unique=True,
         stat=None, op=None, value=None, special="season_champion",
         req="عنوانِ ویژه‌ای که فقط به برنده‌ی فصل (Season Champion) می‌رسد",
         note="تک و فصلی"),
]

assert len(TITLES) >= 50, f"باید حداقل ۵۰ لقب باشد، اکنون {len(TITLES)}"
_N_F = sum(1 for t in TITLES if t["category"] == "female")
_N_M = sum(1 for t in TITLES if t["category"] == "male")
_N_L = sum(1 for t in TITLES if t["category"] == "legendary")
_N_U = sum(1 for t in TITLES if t["unique"])
keys = [t["key"] for t in TITLES]
assert len(keys) == len(set(keys)), "کلیدهای تکراری وجود دارد!"


def build_xlsx():
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter

    wb = openpyxl.Workbook()

    # ---------- شیت ۱: القاب ----------
    ws = wb.active
    ws.title = "القاب"
    ws.sheet_view.rightToLeft = True

    headers = [
        "#", "لقب", "معادل لاتین", "دسته", "جنسیت", "یونیک/تک",
        "فعالیتِ موردِنیاز", "کلیدِ شرط (stat)", "عملگر", "آستانه", "توضیحِ طراحی",
    ]
    ws.append(headers)

    cat_fa = {"female": "زنانه", "male": "مردانه", "legendary": "اسطوره‌ای/مشترک"}
    gen_fa = {"female": "زن", "male": "مرد", "any": "مشترک"}
    cat_fill = {
        "female": PatternFill("solid", fgColor="F8D7E6"),
        "male": PatternFill("solid", fgColor="D6E4F5"),
        "legendary": PatternFill("solid", fgColor="FCEFC7"),
    }
    uniq_fill = PatternFill("solid", fgColor="FFF2CC")

    for i, t in enumerate(TITLES, start=1):
        ws.append([
            i,
            t["name"],
            t["latin"] or "",
            cat_fa[t["category"]],
            gen_fa[t["gender"]],
            "✔ تک" if t["unique"] else "—",
            t["req"],
            t["stat"] or ("[رویدادی] " + (t["special"] or "")),
            t["op"] or "",
            t["value"] if t["value"] is not None else "",
            t["note"],
        ])

    # استایلِ هدر
    header_font = Font(bold=True, color="FFFFFF", size=12)
    header_fill = PatternFill("solid", fgColor="3B3B58")
    center = Alignment(horizontal="center", vertical="center", wrap_text=True)
    right = Alignment(horizontal="right", vertical="center", wrap_text=True)
    thin = Side(style="thin", color="BBBBBB")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)

    for c in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=c)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = center
        cell.border = border
    ws.row_dimensions[1].height = 34

    for r in range(2, len(TITLES) + 2):
        t = TITLES[r - 2]
        for c in range(1, len(headers) + 1):
            cell = ws.cell(row=r, column=c)
            cell.border = border
            cell.alignment = center if c in (1, 4, 5, 6, 9, 10) else right
            # رنگ‌آمیزیِ دسته روی ستونِ دسته
            if c == 4:
                cell.fill = cat_fill[t["category"]]
            if c == 6 and t["unique"]:
                cell.fill = uniq_fill
                cell.font = Font(bold=True, color="B8860B")
        # عدد آستانه با جداکننده
        vcell = ws.cell(row=r, column=10)
        if isinstance(vcell.value, int):
            vcell.number_format = "#,##0"

    widths = [5, 20, 22, 15, 9, 10, 46, 24, 8, 16, 34]
    for c, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(c)].width = w

    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(headers))}{len(TITLES) + 1}"

    # ---------- شیت ۲: راهنما و اشتراک ----------
    ws2 = wb.create_sheet("راهنما و اشتراک")
    ws2.sheet_view.rightToLeft = True
    ws2.column_dimensions["A"].width = 26
    ws2.column_dimensions["B"].width = 90

    def row(a, b, bold=False, fill=None, size=11):
        ws2.append([a, b])
        rr = ws2.max_row
        ws2.cell(row=rr, column=1).font = Font(bold=True, size=size)
        ws2.cell(row=rr, column=1).alignment = right
        cb = ws2.cell(row=rr, column=2)
        cb.font = Font(bold=bold, size=size)
        cb.alignment = right
        if fill:
            for cc in (1, 2):
                ws2.cell(row=rr, column=cc).fill = fill

    row("موضوع", "توضیح", bold=True, fill=header_fill, size=12)
    ws2.cell(row=1, column=1).font = Font(bold=True, color="FFFFFF", size=12)
    ws2.cell(row=1, column=2).font = Font(bold=True, color="FFFFFF", size=12)
    row("تعدادِ القاب", f"{len(TITLES)} لقب ({_N_F} زنانه، {_N_M} مردانه، {_N_L} اسطوره‌ای/مشترک) — از جمله {_N_U} لقبِ تک/یونیک")
    row("القابِ تک (یونیک)",
        "القابی که فقط یک دارنده در کلِ سرور دارند؛ یا با first-claim (اولین واجدِ شرط) قفل می‌شوند یا پویا هستند (به صدرنشینِ فعلی می‌رسند).")
    row("اعطای خودکار و مخفی",
        "القابِ آماری خودکار و بی‌سروصدا هنگامِ فعالیت اعطا می‌شوند؛ بازیکن با پیامِ تبریک مطلع می‌شود ولی شرایط از قبل نمایش داده نمی‌شود.")
    row("القابِ رویدادی",
        "مثلِ ققنوس، آخرالزمان، افسانه سرور، هرا؛ از سیستم‌های دیگر (رتبه‌بندی، فصل، VIP) با grant_title اعطا می‌شوند.")
    row("بخشِ اشتراک (سفارشی)",
        "با خریدِ اشتراک، بازیکن می‌تواند لقبِ دلخواهِ خودش را بنویسد و فعال کند. اعتبار زمان‌دار است؛ پس از انقضا لقبِ سفارشی نمایش داده نمی‌شود.")
    row("محدودیتِ ضدباگ",
        "نامِ بازیکن، نامِ دستیار و لقبِ سفارشی نمی‌توانند برابرِ دستورها/دکمه‌های اصلیِ ربات باشند (مثلِ «منو، دزدی، بازار، عمارت...») و نباید با / شروع شوند.")
    row("جنسیت",
        "القابِ زنانه فقط برای بازیکنانِ دختر، مردانه فقط برای پسر، و اسطوره‌ای برای هر دو.")

    for r in range(1, ws2.max_row + 1):
        for c in (1, 2):
            ws2.cell(row=r, column=c).border = border
    ws2.freeze_panes = "A2"

    os.makedirs(OUT_DIR, exist_ok=True)
    wb.save(XLSX)
    print("XLSX نوشته شد:", XLSX)


def build_titles_py():
    os.makedirs(os.path.dirname(DATA_PY), exist_ok=True)
    body = pprint.pformat(TITLES, width=100, sort_dicts=False)
    header = '''# -*- coding: utf-8 -*-
"""داده و منطقِ سیستمِ القاب (مرحله ۱۱).

این فایل تنها منبعِ حقیقتِ القاب است و توسطِ build_titles.py تولید شده.
هر لقب یک dict با کلیدهای زیر است:
  key, name, latin, category, gender, unique, stat, op, value, special, req, note
"""
from typing import Optional

# کلماتِ رزرو: کاربر نباید این‌ها را به عنوانِ نام/لقب انتخاب کند (ضدِ باگ).
# شاملِ دستورها و متنِ دکمه‌های اصلیِ ربات در مراحلِ ۱ تا ۱۰.
RESERVED_WORDS = {
    "start", "help", "admin", "menu", "cancel", "id",
    "منو", "خانه", "بازگشت", "انصراف", "راهنما",
    "دزدی", "پایگاه", "پروفایل", "رنکینگ", "رتبه", "رتبه\u200cبندی",
    "عمارت", "کارخانه", "بازار", "بانک", "دستیار", "کنسیلیری",
    "جنگ", "جاسوسی", "حمله", "دفاع", "کمک", "استخدام", "ارتقا",
    "خرید", "فروش", "گزارش", "لقب", "القاب", "اشتراک", "سازمان",
    "شهر", "کشور", "شرکت", "عضویت", "تنظیمات",
}

MAX_TITLE_LEN = 24
MIN_TITLE_LEN = 2

# هزینه و مدتِ اشتراک برای لقبِ سفارشی (قابلِ تنظیم).
SUBSCRIPTION_COST = 500_000       # هزینه‌ی یک دوره اشتراک (دلارِ داخلِ بازی)
SUBSCRIPTION_DAYS = 30            # مدتِ اعتبارِ اشتراک به روز


'''
    funcs = '''

# ---------- ایندکس‌ها و کمکی‌ها ----------
TITLES_BY_KEY = {t["key"]: t for t in TITLES}


def get_title(key: str) -> Optional[dict]:
    return TITLES_BY_KEY.get(key)


def auto_titles():
    """القابی که خودکار بر اساسِ آمار اعطا می‌شوند (stat دارند)."""
    return [t for t in TITLES if t["stat"] is not None]


def _cmp(current, op: str, threshold) -> bool:
    if current is None or threshold is None:
        return False
    if op == ">=":
        return current >= threshold
    if op == ">":
        return current > threshold
    if op == "<=":
        return current <= threshold
    if op == "==":
        return current == threshold
    return False


def gender_ok(title: dict, gender: Optional[str]) -> bool:
    """آیا این لقب برای جنسیتِ بازیکن مجاز است؟"""
    if title["gender"] == "any":
        return True
    return gender == title["gender"]


def meets_requirement(title: dict, stats: dict) -> bool:
    """آیا آمارِ بازیکن شرطِ آماریِ لقب را برآورده می‌کند؟ (فقط القابِ stat-دار)"""
    if title["stat"] is None:
        return False
    return _cmp(stats.get(title["stat"]), title["op"], title["value"])


def normalize(text: str) -> str:
    return (text or "").strip().lower()


def is_reserved(text: str) -> bool:
    """آیا متن یک دستور/دکمه‌ی اصلیِ ربات است؟ (برای جلوگیری از باگ)"""
    t = normalize(text)
    if not t:
        return True
    if t.startswith("/"):
        return True
    if t in {w.lower() for w in RESERVED_WORDS}:
        return True
    # اگر دقیقاً برابرِ یکی از کلماتِ رزرو باشد (با حذفِ ایموجی/فاصله‌ی اضافه)
    compact = "".join(ch for ch in t if ch.isalnum() or ch in "\u0600-\u06FF")
    for w in RESERVED_WORDS:
        if compact == "".join(ch for ch in w.lower() if ch.isalnum()):
            return True
    return False


def validate_custom_title(raw: str):
    """اعتبارسنجیِ لقبِ سفارشیِ اشتراکی.
    خروجی: (ok: bool, cleaned_or_reason: str)
    """
    name = (raw or "").strip()
    if len(name) < MIN_TITLE_LEN:
        return False, f"لقب باید حداقل {MIN_TITLE_LEN} نویسه باشد."
    if len(name) > MAX_TITLE_LEN:
        return False, f"لقب نباید بیشتر از {MAX_TITLE_LEN} نویسه باشد."
    _bad = set("<>{}[]|") | {chr(96), chr(34), chr(92)}
    if any(ch in name for ch in _bad):
        return False, "لقب شاملِ نویسه‌های غیرمجاز است."
    if "http" in name.lower() or "t.me" in name.lower() or "@" in name:
        return False, "لقب نباید شاملِ لینک یا یوزرنیم باشد."
    if is_reserved(name):
        return False, "این عبارت یک دستورِ اصلیِ ربات است و نمی‌تواند لقب باشد."
    return True, name


def validate_name(raw: str):
    """اعتبارسنجیِ نامِ بازیکن/دستیار — همان قواعدِ ضدباگ."""
    return validate_custom_title(raw)
'''
    with open(DATA_PY, "w", encoding="utf-8") as f:
        f.write(header)
        f.write("TITLES = " + body + "\n")
        f.write(funcs)
    print("titles.py نوشته شد:", DATA_PY)


if __name__ == "__main__":
    build_xlsx()
    build_titles_py()
    print("تعداد القاب:", len(TITLES))
