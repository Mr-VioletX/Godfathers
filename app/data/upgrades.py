# --- ویژگی‌های امضای پایگاه (هر تیر یک ویژگی) ---
# کلیدِ هر ویژگی با نامِ ستونِ مدل Hideout هماهنگ است: <feature>_level
# max_level برای همه ۵ است.

FEATURES = {
    "security": {
        "key": "security",
        "name": "🥷 مخفی‌کاری",
        "desc": "هر سطح، احتمالِ دستگیری در دزدی را ۱٫۲٪ کم می‌کند.",
        "base_cost": 1_000,
        "max_level": 5,
    },
    "safehouse": {
        "key": "safehouse",
        "name": "💤 بازیابی",
        "desc": "هر سطح، سرعتِ بازیابیِ خستگی را +۱٫۵ در دقیقه بیشتر می‌کند.",
        "base_cost": 1_600,
        "max_level": 5,
    },
    "vault": {
        "key": "vault",
        "name": "💰 خزانه",
        "desc": "هر سطح، پاداشِ دزدیِ موفق را ۳٪ بیشتر می‌کند.",
        "base_cost": 3_000,
        "max_level": 5,
    },
    "authority": {
        "key": "authority",
        "name": "👑 اقتدار",
        "desc": "هر سطح، هر سه ویژگی را با هم تقویت می‌کند: ۰٫۶٪ ریسک−، ۱+ بازیابی، ۲٪ پاداش+.",
        "base_cost": 8_000,
        "max_level": 5,
    },
}
MAX_FEATURE_LEVEL = 5

# --- ضریبِ اثرِ هر سطحِ ویژگی ---
SECURITY_RISK_REDUCTION = 0.012   # 🥷 مخفی‌کاری: ۱٫۲٪ کاهش ریسک
SAFEHOUSE_RECOVERY_BONUS = 1.5    # 💤 بازیابی: +۱٫۵ خستگی/دقیقه
VAULT_REWARD_BONUS = 0.03         # 💰 خزانه: ۳٪ افزایش پاداش

# --- اثرِ هر سطحِ «اقتدارِ» ویلا (روی هر سه با هم) ---
AUTHORITY_RISK_REDUCTION = 0.006  # ۰٫۶٪ کاهش ریسک به‌ازای هر سطح
AUTHORITY_RECOVERY_BONUS = 1      # +۱ بازیابی/دقیقه به‌ازای هر سطح
AUTHORITY_REWARD_BONUS = 0.02     # ۲٪ افزایش پاداش به‌ازای هر سطح


def upgrade_cost(base_cost: int, current_level: int) -> int:
    """هزینه‌ی ارتقای ویژگی از سطحِ فعلی به سطحِ بعدی."""
    return base_cost * (current_level + 1)


def get_feature(key: str):
    """اطلاعاتِ یک ویژگی را با کلیدش برمی‌گرداند (یا None)."""
    return FEATURES.get(key)


def effect_percent_line(key: str, level: int) -> str:
    """🆕 مرحله ۱۶: توضیحِ درصدیِ اثرِ فعلیِ یک ویژگی در لولِ داده‌شده."""
    if level <= 0:
        return "بدونِ اثر (لول ۰)"
    if key == "security":
        return f"−{level * SECURITY_RISK_REDUCTION * 100:.1f}٪ ریسکِ دستگیری"
    if key == "safehouse":
        return f"+{level * SAFEHOUSE_RECOVERY_BONUS:.1f} بازیابیِ خستگی در دقیقه"
    if key == "vault":
        return f"+{level * VAULT_REWARD_BONUS * 100:.0f}٪ پاداشِ دزدیِ موفق"
    if key == "authority":
        return (
            f"−{level * AUTHORITY_RISK_REDUCTION * 100:.1f}٪ ریسک، "
            f"+{level * AUTHORITY_RECOVERY_BONUS} بازیابی، "
            f"+{level * AUTHORITY_REWARD_BONUS * 100:.0f}٪ پاداش"
        )
    return ""