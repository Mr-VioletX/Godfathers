# --- تعریف تیرهای پایگاه (مسیرِ ارتقای پلکانی) ---
# هر تیر یک «ویژگیِ امضا» دارد که به ستونی در مدل Hideout وصل است:
#   security_level  → 🥷 مخفی‌کاری (کاهش ریسک)   | تیر Covo
#   safehouse_level → 💤 بازیابی (خستگی/دقیقه)  | تیر Rifugio
#   vault_level     → 💰 خزانه (پاداش دزدی)     | تیر Quartiere
#   authority_level → 👑 اقتدار (ترکیبِ هر سه)   | تیرِ چهار (پایگاهِ تخصصی)
#
# order    → ترتیبِ تیر در مسیر (۱..۴)
# feature  → کلیدِ ویژگیِ امضا (همان بخشِ ستون، بدونِ _level)
# up_cost  → هزینه‌ی «ارتقا به این تیر» (برای Covo = خریدِ اولیه)
# level_req→ حداقل سطحِ بازیکن برای رسیدن به این تیر
# next     → کلیدِ تیرِ بعدی (یا None برای آخرین تیر)

BASE_TIERS = {
    "hideout": {
        "key": "hideout", "order": 1,
        "name": "🥷 Covo (مخفیگاه)",
        "feature": "security",
        "up_cost": 2_000, "level_req": 1,
        "next": "safehouse",
        "perk": "مخفی‌کاری: کاهشِ ریسکِ دستگیری.",
    },
    "safehouse": {
        "key": "safehouse", "order": 2,
        "name": "💤 Rifugio (خانه‌ی امن)",
        "feature": "safehouse",
        "up_cost": 16_000, "level_req": 4,
        "next": "hq",
        "perk": "بازیابی: خستگی سریع‌تر کم می‌شود.",
    },
    "hq": {
        "key": "hq", "order": 3,
        "name": "💰 Quartiere (مقر شهری)",
        "feature": "vault",
        "up_cost": 60_000, "level_req": 7,
        "next": "mansion",
        "perk": "خزانه: پاداشِ دزدی بیشتر.",
    },
    "mansion": {
        "key": "mansion", "order": 4,
        "name": "👑 پایگاهِ تیرِ ۴ (تخصصی)",
        "feature": "authority",
        "up_cost": 200_000, "level_req": 10,
        "next": None,
        "perk": "اقتدار: هر سه ویژگیِ قبلی با هم تقویت می‌شوند.",
    },
}

# اولین تیر (خریدِ اولیه)
FIRST_TIER = "hideout"
# آخرین تیر (پایگاهِ تخصصی) — رسیدنِ ویژگی‌اش به مکس، دروازه‌ی ساختِ عمارت است
MAX_TIER = "mansion"


def get_tier(key: str):
    """اطلاعاتِ یک تیرِ پایگاه را با کلیدش برمی‌گرداند (یا None)."""
    return BASE_TIERS.get(key)


def next_tier(key: str):
    """کلیدِ تیرِ بعدی را برمی‌گرداند (یا None اگر آخرین تیر باشد)."""
    tier = BASE_TIERS.get(key)
    return tier["next"] if tier else None


# ============ مرحله ۲۶.۳ — پایگاه‌هایِ تخصصیِ تیرِ چهار (اسمِ لاتین + تگِ فارسی) ============
# دیگر هیچ «ویلا»یِ عمومی وجود ندارد. پایگاهِ تیرِ چهار همیشه یکی از این پایگاه‌هایِ
# تخصصی است و هر کدام دقیقاً پیش‌نیازِ ساختِ یک عمارتِ مشخص در هرم است:
#   • ۹ پایگاهِ تخصصی برای ۹ عمارتِ هرم (بعد از کاپولا)
#   • Palazzo هم پایگاهِ اولین عمارت (کاپولا) است
# هنگامِ ساختِ تیرِ چهار، فقط پایگاه‌هایی نمایش داده می‌شوند که عمارتِ متناظرشان
# طبقِ هرم باز شده و هنوز ساخته نشده (۲ یا ۳ یا ۴ دکمه‌ی شیشه‌ای، بسته به هرم).
TIER4_BASES = {
    "cupola":     "🏛️ Palazzo (پالاتزو / پایگاهِ مرکزی)",
    "fortezza":   "🛡️ Bastione (باستیونه / پایگاهِ نظامی)",
    "emporio":    "📈 Mercato (مرکاتو / پایگاهِ تجاری)",
    "ombra":      "🕶️ Velo (وِلو / پایگاهِ اطلاعاتی)",
    "porto_nero": "📦 Dogana (دوگانا / پایگاهِ قاچاق)",
    "banco":      "💰 Tesoro (تسورو / پایگاهِ اقتصادی)",
    "santuario":  "🩺 Clinica (کلینیکا / پایگاهِ درمانی)",
    "legione":    "⚔️ Caserma (کازرما / پایگاهِ رزمی)",
    "fonderia":   "🏭 Officina (اوفیچینا / پایگاهِ صنعتی)",
    "senato":     "⚖️ Curia (کوریا / پایگاهِ سیاسی)",
}


def final_variant_choices(built_keys):
    """لیستِ (کلیدِ عمارت، نامِ پایگاهِ تخصصی) که الان بر اساسِ هرم قابلِ ساخت‌اند."""
    from app.data.estates import ESTATES, is_estate_unlocked

    built = set(built_keys)
    out = []
    for key in ESTATES:
        if key in built:
            continue
        if is_estate_unlocked(key, built):
            out.append((key, final_variant_name(key)))
    return out


def final_variant_name(variant_key: str) -> str:
    """نامِ نمایشیِ پایگاهِ تخصصیِ تیرِ چهار (یا نامِ عمومیِ تیر اگر کلید نامعتبر/خالی بود)."""
    if not variant_key:
        return get_tier(MAX_TIER)["name"]
    return TIER4_BASES.get(variant_key) or get_tier(MAX_TIER)["name"]


def tier4_base_for_estate(estate_key: str) -> str:
    """نامِ پایگاهِ تخصصی‌ای که پیش‌نیازِ ساختِ این عمارت است."""
    return final_variant_name(estate_key)