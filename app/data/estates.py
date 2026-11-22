# --- ثابت‌های عمومی عمارت ---
SLOTS_PER_ESTATE = 4        # حداکثر حرفه‌ایِ فعال در هر عمارت
CUPOLA_KEY = "cupola"       # کلیدِ عمارت اصلی

# آخرین تیرِ پایگاه شخصی (پایگاهِ تخصصی). ساختِ هر عمارت نیازمندِ پایگاهِ تخصصیِ مخصوصِ خودش در این تیر است.
# کلیدِ داخلیِ base_type را «mansion» نگه می‌داریم (تا دیتای قدیمی نریزد)؛ نامِ نمایشی‌اش از TIER4_BASES خوانده می‌شود.
MAX_BASE_TYPE = "mansion"

# --- پرک‌های عمارت Cupola — جایگزینِ ویژگی‌های پایگاهِ تخصصی می‌شوند ---
# (چون با ساختِ عمارت، پایگاهِ تخصصی مصرف می‌شود و دیگر بونوسِ ویژگی‌ها وجود ندارد)
CUPOLA_PERKS = {
    "sec_bonus": 0.10,       # ۱۰٪ کاهش ریسک دستگیری
    "vault_bonus": 0.30,     # ۳۰٪ افزایش پاداش دزدی
    "recovery_bonus": 15,    # +۱۵ بازیابی خستگی در دقیقه
}

# --- کاتالوگِ کاملِ ۱۰ عمارتِ هرم ---
# قانونِ باز شدن (هرمِ دوطرفه): هر عمارت با کلیدِ "prereqs" مشخص می‌کند برای باز شدن،
# ساخته‌شدنِ کدام عمارت‌های بالادستی لازم است (میانی = دو والد، گوشه = یک والد).
ESTATES = {
    "cupola": {
        "key": "cupola", "name": "🏛️ Cupola (کاپولا / شورای مرکزی)", "row": 1,
        "required_base": MAX_BASE_TYPE, "found_cost": 300_000, "prereqs": [],
        "desc": "قلبِ خانواده؛ با ساختنش استخدامِ حرفه‌ای‌ها باز می‌شود.",
    },
    "fortezza": {
        "key": "fortezza", "name": "🛡️ Fortezza (فورتزا / دژ)", "row": 2,
        "required_base": MAX_BASE_TYPE, "found_cost": 500_000, "prereqs": ["cupola"],
        "desc": "عمارت نظامی؛ ستونِ چپِ ردیف دوم.",
    },
    "emporio": {
        "key": "emporio", "name": "📈 Emporio (امپوریو / بازارگاه)", "row": 2,
        "required_base": MAX_BASE_TYPE, "found_cost": 500_000, "prereqs": ["cupola"],
        "desc": "عمارت تجاری؛ ستونِ راستِ ردیف دوم.",
    },
    "ombra": {
        "key": "ombra", "name": "🕶️ Ombra (اومبرا / سایه)", "row": 3,
        "required_base": MAX_BASE_TYPE, "found_cost": 800_000, "prereqs": ["fortezza"],
        "desc": "عمارت اطلاعاتی؛ گوشه‌ی چپِ ردیف سوم (یک والد).",
    },
    "porto_nero": {
        "key": "porto_nero", "name": "📦 Porto Nero (پورتو نرو / بندر سیاه)", "row": 3,
        "required_base": MAX_BASE_TYPE, "found_cost": 800_000, "prereqs": ["fortezza", "emporio"],
        "desc": "عمارت قاچاق؛ میانیِ ردیف سوم (دو والد).",
    },
    "banco": {
        "key": "banco", "name": "💰 Banco (بانکو / بانک)", "row": 3,
        "required_base": MAX_BASE_TYPE, "found_cost": 800_000, "prereqs": ["emporio"],
        "desc": "عمارت مالی؛ گوشه‌ی راستِ ردیف سوم (یک والد).",
    },
    "santuario": {
        "key": "santuario", "name": "🩺 Santuario (سانتواریو / درمانگاه)", "row": 4,
        "required_base": MAX_BASE_TYPE, "found_cost": 1_200_000, "prereqs": ["ombra"],
        "desc": "عمارت درمانی؛ گوشه‌ی چپِ ردیف چهارم (یک والد).",
    },
    "legione": {
        "key": "legione", "name": "⚔️ Legione (لجیونه / لژیون)", "row": 4,
        "required_base": MAX_BASE_TYPE, "found_cost": 1_200_000, "prereqs": ["ombra", "porto_nero"],
        "desc": "عمارت جنگ؛ میانیِ ردیف چهارم (دو والد).",
    },
    "fonderia": {
        "key": "fonderia", "name": "🏭 Fonderia (فوندریا / ریخته‌گری)", "row": 4,
        "required_base": MAX_BASE_TYPE, "found_cost": 1_200_000, "prereqs": ["porto_nero", "banco"],
        "desc": "عمارت صنعتی؛ میانیِ ردیف چهارم (دو والد).",
    },
    "senato": {
        "key": "senato", "name": "⚖️ Senato (سناتو / مجلس)", "row": 4,
        "required_base": MAX_BASE_TYPE, "found_cost": 1_200_000, "prereqs": ["banco"],
        "desc": "عمارت سیاسی؛ گوشه‌ی راستِ ردیف چهارم (یک والد).",
    },
}


def get_estate_role(key: str):
    """مشخصات یک نوع عمارت را با کلیدش برمی‌گرداند (یا None)."""
    return ESTATES.get(key)


def estate_prereqs(key: str):
    """لیستِ کلیدِ عمارت‌هایِ پیش‌نیازِ باز شدنِ این عمارت."""
    role = ESTATES.get(key)
    return list(role["prereqs"]) if role else []


def is_estate_unlocked(key: str, built_keys) -> bool:
    """آیا این عمارت با توجه به عمارت‌هایِ ساخته‌شده قابلِ ساخت است؟
    قانون: همه‌ی پیش‌نیازهای هرمی باید از قبل ساخته شده باشند."""
    role = ESTATES.get(key)
    if role is None:
        return False
    built = set(built_keys)
    return all(p in built for p in role["prereqs"])


def missing_prereqs(key: str, built_keys):
    """کلیدِ پیش‌نیازهایی که هنوز ساخته نشده‌اند (برای پیامِ خطا)."""
    built = set(built_keys)
    return [p for p in estate_prereqs(key) if p not in built]

# ================== افکتِ نقشِ عمارت‌ها (مرحله ۸) ==================
ESTATE_MAX_LEVEL = 5   # سقفِ سطحِ خودِ عمارت (تقویتِ نقش)

# هر عمارت یک افکت دارد که با سطحِ عمارت ضرب می‌شود.
# kind: نوعِ افکت | per_level: مقدار به‌ازای هر سطح | label: متنِ نمایشی
ESTATE_EFFECTS = {
    "cupola":     {"kind": "income_pct",  "per_level": 0.05, "label": "💰 درآمدِ کلِ امپراتوری"},
    "banco":      {"kind": "income_pct",  "per_level": 0.08, "label": "💰 سودِ مالی"},
    "porto_nero": {"kind": "income_pct",  "per_level": 0.06, "label": "💰 درآمدِ بازار سیاه"},
    "fonderia":   {"kind": "income_pct",  "per_level": 0.05, "label": "💰 بازدهِ تولید"},
    "emporio":    {"kind": "market_pct",  "per_level": 0.06, "label": "🛒 قیمتِ فروش"},
    "fortezza":   {"kind": "defense_pct", "per_level": 0.10, "label": "🛡️ دفاعِ عمارت‌ها"},
    "legione":    {"kind": "attack_pct",  "per_level": 0.10, "label": "⚔️ قدرتِ حمله"},
    "ombra":      {"kind": "spy_pct",     "per_level": 0.10, "label": "🕶️ دقتِ جاسوسی"},
    "santuario":  {"kind": "recovery",    "per_level": 5,    "label": "💤 بازیابیِ خستگی/دقیقه"},
    "senato":     {"kind": "risk_pct",    "per_level": 0.04, "label": "🎯 کاهشِ ریسکِ کلی"},
}

_EFFECT_ORDER = ["income_pct", "market_pct", "defense_pct", "attack_pct", "spy_pct", "risk_pct", "recovery"]
_EFFECT_LABELS = {
    "income_pct": "💰 درآمد",
    "market_pct": "🛒 بازار",
    "defense_pct": "🛡️ دفاع",
    "attack_pct": "⚔️ حمله",
    "spy_pct": "🕶️ جاسوسی",
    "risk_pct": "🎯 کاهشِ ریسک",
    "recovery": "💤 بازیابی",
}


# ================== 🆕 مرحله ۲۸ — درآمدِ مختصِ هر عمارت ==================
# قبلاً درآمدِ همه‌ی عمارت‌ها تقریباً یکسان بود (~۲۵۰ هزار/ساعت).
# اکنون هر عمارت بسته به ماهیتِ اقتصادی‌اش ضریبِ درآمدِ متفاوتی دارد:
#   • عمارت‌های پولساز (بانک، بندرِ سیاه، تجارت) درآمدِ بالاتر
#   • عمارت‌های پشتیبانی/امنیتی درآمدِ کمتر ولی افکتِ جنگی/دفاعیِ قوی‌تر
ESTATE_INCOME_MULT = {
    "cupola":     1.60,   # 🕰️ مرکزِ قدرت — سهمِ همه‌ی شاخه‌ها
    "banco":      1.85,   # 🏦 مالی — پردرآمدترین
    "porto_nero": 1.70,   # 🚢 قاچاق
    "emporio":    1.45,   # 📈 تجارت
    "fonderia":   1.30,   # 🏭 صنعت
    "senato":     1.15,   # 🏛️ نفوذ
    "ombra":      0.95,   # 🕶️ اطلاعات
    "fortezza":   0.85,   # 🏰 دزدی/دفاع
    "legione":    0.80,   # ⚔️ نطامی
    "santuario":  0.70,   # 🏥 درمانی
}

ESTATE_INCOME_LABEL = {
    "banco": "💰 بسیار پردرآمد",
    "porto_nero": "💰 پردرآمد",
    "cupola": "💰 پردرآمد",
    "emporio": "💵 درآمدِ خوب",
    "fonderia": "💵 درآمدِ متوسط",
    "senato": "💵 درآمدِ متوسط",
    "ombra": "🧿 درآمدِ کم / افکتِ بالا",
    "fortezza": "🧿 درآمدِ کم / افکتِ بالا",
    "legione": "🧿 درآمدِ کم / افکتِ بالا",
    "santuario": "🧿 درآمدِ کم / افکتِ بالا",
}


def estate_income_mult(role_key: str) -> float:
    """ضریبِ درآمدِ مختصِ یک عمارت."""
    return float(ESTATE_INCOME_MULT.get(role_key, 1.0))


def estate_income_label(role_key: str) -> str:
    """برچسبِ توصیفیِ سطحِ درآمدِ عمارت."""
    return ESTATE_INCOME_LABEL.get(role_key, "💵 درآمدِ متوسط")


def estate_upgrade_cost(current_level: int) -> int:
    """هزینه‌ی ارتقای خودِ عمارت (تقویتِ نقشش) از سطحِ فعلی به بعدی."""
    return 100_000 * (2 ** current_level)


def aggregate_effects(estates):
    """estates = لیستِ (role_key, level). جمعِ افکت‌ها را بر حسبِ نوع برمی‌گرداند."""
    totals = {}
    for key, level in estates:
        eff = ESTATE_EFFECTS.get(key)
        if not eff:
            continue
        totals[eff["kind"]] = totals.get(eff["kind"], 0) + eff["per_level"] * level
    return totals


def estate_effect_line(key: str, level: int):
    """توضیحِ افکتِ یک عمارت در سطحِ مشخص (یا None)."""
    eff = ESTATE_EFFECTS.get(key)
    if not eff:
        return None
    val = eff["per_level"] * level
    if eff["kind"] == "recovery":
        return f"{eff['label']}: +{int(val)}"
    return f"{eff['label']}: +{val * 100:.0f}%"


def describe_effects(totals):
    """لیستِ خطوطِ خواناییِ افکتِ کلِ امپراتوری (برای داشبورد)."""
    lines = []
    for kind in _EFFECT_ORDER:
        val = totals.get(kind)
        if not val:
            continue
        if kind == "recovery":
            lines.append(f"{_EFFECT_LABELS[kind]}: +{int(val)}")
        else:
            lines.append(f"{_EFFECT_LABELS[kind]}: +{val * 100:.0f}%")
    return lines