# -*- coding: utf-8 -*-
"""مرحله ۲۸ — بازطراحیِ حرفه‌ای‌ها.

تغییرِ اصلی: «چیدن در اسلات» حذف شد. هر عمارت **۴ حرفه‌ایِ مخصوصِ خودش** دارد که
نام و توانایی‌شان با نقشِ همان عمارت هم‌خوان است. با استخدام، حرفه‌ای مستقیماً
روی همان عمارت فعال می‌شود (نیازی به چیدن دستی نیست).

جمعِ کل: ۱۰ عمارت × ۴ حرفه‌ای = ۴۰ حرفه‌ای.
"""
from __future__ import annotations

# --- گروه‌ها = خودِ عمارت‌ها (سازگاری با کدهای قبلی حفظ شده) ---
GROUPS = {
    "cupola": "🏛️ کاپولا (شورای مرکزی)",
    "fortezza": "🛡️ فورتزا (دژِ عملیات)",
    "emporio": "📈 امپوریو (بازارگاه)",
    "ombra": "🕶️ اومبرا (سایه)",
    "porto_nero": "📦 پورتو نرو (بندرِ سیاه)",
    "banco": "💰 بانکو (بانک)",
    "santuario": "🩺 سانتواریو (درمانگاه)",
    "legione": "⚔️ لجیونه (لژیون)",
    "fonderia": "🏭 فوندریا (ریخته‌گری)",
    "senato": "⚖️ سناتو (مجلس)",
}

# --- کاتالوگِ ۴۰ حرفه‌ای؛ کلیدِ group = کلیدِ عمارتِ صاحبِ آن حرفه‌ای ---
PROFESSIONALS = {
    # ---------------- 🏛️ Cupola — شورای مرکزی (مدیریت) ----------------
    "consigliere": {"name": "🎩 کنسیلیریِ کاپولا", "group": "cupola", "base_price": 40_000, "ability": "+درصدِ کلی به همه‌ی عمارت‌ها"},
    "underboss":   {"name": "🎖️ معاونِ خانواده (Underboss)", "group": "cupola", "base_price": 60_000, "ability": "+درآمدِ همه‌ی عمارت‌ها"},
    "capo":        {"name": "🧿 کاپوی شورا", "group": "cupola", "base_price": 44_000, "ability": "+بازدهِ حرفه‌ای‌های زیرِ دست"},
    "treasurer":   {"name": "🗝️ خزانه‌دارِ کاپولا", "group": "cupola", "base_price": 50_000, "ability": "کاهشِ حقوقِ پرداختی"},

    # ---------------- 🛡️ Fortezza — دژِ عملیات (تیمِ ضربت و دزدی) ----------------
    "lockpick":       {"name": "🔓 قفل‌شکنِ دژ", "group": "fortezza", "base_price": 10_000, "ability": "کاهشِ ریسکِ دزدی"},
    "safecracker":    {"name": "🔐 گاوصندوق‌بازِ دژ", "group": "fortezza", "base_price": 14_000, "ability": "+پاداشِ دزدی‌های سنگین"},
    "getaway_driver": {"name": "🚗 راننده‌ی فرار", "group": "fortezza", "base_price": 9_000, "ability": "کاهشِ احتمالِ دستگیری"},
    "pickpocket":     {"name": "👜 استادِ جیب‌بری", "group": "fortezza", "base_price": 6_000, "ability": "+درآمدِ دزدی‌های سبک"},

    # ---------------- 📈 Emporio — بازارگاه (تجارت) ----------------
    "broker":    {"name": "📊 دلالِ بازارگاه", "group": "emporio", "base_price": 13_000, "ability": "قیمتِ فروشِ بهتر"},
    "merchant":  {"name": "🛒 تاجرِ امپوریو", "group": "emporio", "base_price": 11_000, "ability": "تخفیفِ خریدِ مواد"},
    "auctioneer":{"name": "🔨 حراج‌گرِ امپوریو", "group": "emporio", "base_price": 15_000, "ability": "+سودِ فروشِ ویژه"},
    "logistics": {"name": "🚚 مدیرِ لجستیکِ بازارگاه", "group": "emporio", "base_price": 18_000, "ability": "+سرعتِ انتقال به انبار"},

    # ---------------- 🕶️ Ombra — سایه (اطلاعات) ----------------
    "spy":         {"name": "🕵️‍♂️ جاسوسِ اومبرا", "group": "ombra", "base_price": 16_000, "ability": "آشکارسازیِ آمارِ رقیب"},
    "hacker":      {"name": "💻 هکرِ سایه", "group": "ombra", "base_price": 26_000, "ability": "نفوذ به سیستمِ رقیب"},
    "informant":   {"name": "👂 خبرچینِ سایه", "group": "ombra", "base_price": 10_000, "ability": "هشدارِ حمله‌ی دشمن"},
    "codebreaker": {"name": "🧩 رمزشکنِ اومبرا", "group": "ombra", "base_price": 30_000, "ability": "لو رفتنِ نقشه‌ی حمله‌ی دشمن"},

    # ---------------- 📦 Porto Nero — بندرِ سیاه (قاچاق) ----------------
    "smuggler":        {"name": "🚢 قاچاقچیِ بندر", "group": "porto_nero", "base_price": 14_000, "ability": "+سودِ بازارِ سیاه"},
    "dealer":          {"name": "🍾 ساقیِ بندر", "group": "porto_nero", "base_price": 13_000, "ability": "درآمدِ کالای ممنوعه"},
    "forger":          {"name": "📝 جاعلِ اسنادِ بندر", "group": "porto_nero", "base_price": 17_000, "ability": "کاهشِ ریسکِ قاچاق"},
    "customs_contact": {"name": "🛃 رابطِ گمرک", "group": "porto_nero", "base_price": 24_000, "ability": "عبورِ بی‌خطرِ محموله‌ها"},

    # ---------------- 💰 Banco — بانک (مالی) ----------------
    "accountant": {"name": "🧾 حسابدارِ بانکو", "group": "banco", "base_price": 12_000, "ability": "+درصدِ درآمدِ خودکار"},
    "launderer":  {"name": "🧼 پول‌شویِ بانکو", "group": "banco", "base_price": 16_000, "ability": "کاهشِ ردِّ مالی و جریمه"},
    "banker":     {"name": "🏦 بانکدارِ خانواده", "group": "banco", "base_price": 24_000, "ability": "سودِ سرمایه‌گذاری"},
    "investor":   {"name": "💼 سرمایه‌گذارِ بانکو", "group": "banco", "base_price": 32_000, "ability": "+سودِ بانکِ جهانی"},

    # ---------------- 🩺 Santuario — درمانگاه ----------------
    "doctor":     {"name": "🩺 پزشکِ سانتواریو", "group": "santuario", "base_price": 14_000, "ability": "کاهشِ خستگی و کول‌داون"},
    "surgeon":    {"name": "🩻 جراحِ سانتواریو", "group": "santuario", "base_price": 22_000, "ability": "احیای سریعِ نیرو"},
    "nurse":      {"name": "💉 پرستارِ درمانگاه", "group": "santuario", "base_price": 8_000, "ability": "بازیابیِ تدریجیِ خستگی"},
    "pharmacist": {"name": "💊 داروسازِ سانتواریو", "group": "santuario", "base_price": 16_000, "ability": "کاهشِ کول‌داونِ استراحت"},

    # ---------------- ⚔️ Legione — لژیون (جنگ) ----------------
    "mercenary": {"name": "🔫 مزدورِ لژیون", "group": "legione", "base_price": 18_000, "ability": "+قدرتِ حمله"},
    "sniper":    {"name": "🎯 تک‌تیراندازِ لژیون", "group": "legione", "base_price": 24_000, "ability": "+ضربه‌ی بحرانی"},
    "bodyguard": {"name": "🛡️ گاردِ لژیون", "group": "legione", "base_price": 12_000, "ability": "+دفاعِ عمارت"},
    "enforcer":  {"name": "🦵 قلچماقِ لژیون", "group": "legione", "base_price": 11_000, "ability": "+باج‌گیری"},

    # ---------------- 🏭 Fonderia — ریخته‌گری (صنعت) ----------------
    "chemist":      {"name": "⚗️ شیمی‌دانِ فوندریا", "group": "fonderia", "base_price": 18_000, "ability": "+بازدهِ کارخانه"},
    "engineer":     {"name": "🛠️ مهندسِ فوندریا", "group": "fonderia", "base_price": 20_000, "ability": "کاهشِ هزینه‌ی تولید"},
    "foreman":      {"name": "👷 سرکارگرِ ریخته‌گری", "group": "fonderia", "base_price": 12_000, "ability": "+سرعتِ تولید"},
    "metallurgist": {"name": "🔥 فلزکارِ فوندریا", "group": "fonderia", "base_price": 24_000, "ability": "+بازدهِ تولیدِ تسلیحات"},

    # ---------------- ⚖️ Senato — مجلس (نفوذ) ----------------
    "lawyer":        {"name": "⚖️ وکیلِ سناتو", "group": "senato", "base_price": 16_000, "ability": "جریمه/باجِ ارزان‌تر"},
    "politician":    {"name": "🏛️ سناتورِ خانواده", "group": "senato", "base_price": 30_000, "ability": "کاهشِ ریسکِ کلی"},
    "judge_contact": {"name": "🧑‍⚖️ رابطِ قاضی", "group": "senato", "base_price": 28_000, "ability": "لغوِ یک دستگیری"},
    "diplomat":      {"name": "🕊️ دیپلماتِ سناتو", "group": "senato", "base_price": 34_000, "ability": "+شانسِ اتحاد و صلح"},
}

PROFESSIONAL_COUNT = len(PROFESSIONALS)

# نقشه‌ی عمارت → حرفه‌ای‌های مخصوصِ آن (به ترتیبِ نمایش)
ESTATE_PROFESSIONALS: dict[str, list[str]] = {}
for _key, _info in PROFESSIONALS.items():
    ESTATE_PROFESSIONALS.setdefault(_info["group"], []).append(_key)


def get_professional(key: str):
    """مشخصاتِ یک حرفه‌ای را با کلیدش برمی‌گرداند (یا None)."""
    return PROFESSIONALS.get(key)


def professionals_in_group(group_key: str):
    """لیستِ (key, info) حرفه‌ای‌های یک عمارت/گروه."""
    return [(k, PROFESSIONALS[k]) for k in ESTATE_PROFESSIONALS.get(group_key, [])]


def professionals_for_estate(estate_key: str):
    """همان professionals_in_group با نامِ گویاتر (۴ حرفه‌ایِ مخصوصِ عمارت)."""
    return professionals_in_group(estate_key)


def estate_of_professional(key: str) -> str | None:
    info = PROFESSIONALS.get(key)
    return info["group"] if info else None
