# -*- coding: utf-8 -*-
"""v1.7.6.5 — استخدامِ شهردار برای رساندنِ پیامِ مردم در طولِ سال.

منطقِ خالص و بی‌دیتابیس. هر ردهٔ شهردار:
  • hire_cost   — هزینهٔ یک‌بارهٔ استخدام
  • salary      — حقوقی که سرِ هر سالِ بازی از خزانه کم می‌شود
  • reports     — تعدادِ گزارشِ مردم در هر سالِ بازی
  • sat_bonus   — افزایشِ درصدیِ رضایت به‌خاطرِ مدیریتِ بهتر
  • detail      — عمقِ گزارش (۱ خلاصه، ۲ متوسط، ۳ کامل)
"""
from __future__ import annotations

# هر ۳ روزِ واقعی = ۱ سالِ بازی (هماهنگ با mafia_city.GAME_YEAR_REAL_DAYS)
MAYORS: dict[str, dict] = {
    "clerk": {
        "name": "🧑‍💼 کارمندِ شهرداری",
        "hire_cost": 40_000_000,
        "salary": 8_000_000,
        "reports": 1,
        "sat_bonus": 2,
        "detail": 1,
        "desc": "یک گزارشِ ساده در هر سال؛ فقط رضایت و جمعیت.",
    },
    "manager": {
        "name": "🏛️ مدیرِ شهری",
        "hire_cost": 150_000_000,
        "salary": 30_000_000,
        "reports": 2,
        "sat_bonus": 5,
        "detail": 2,
        "desc": "دو گزارش در سال به‌علاوهٔ فهرستِ نیازهایِ برآورده‌نشده.",
    },
    "veteran": {
        "name": "🎖️ شهردارِ کارکشته",
        "hire_cost": 500_000_000,
        "salary": 90_000_000,
        "reports": 4,
        "sat_bonus": 9,
        "detail": 3,
        "desc": "چهار گزارش در سال، نیازها، و دلیلِ دقیقِ توقفِ رشدِ جمعیت.",
    },
}

MAYOR_ORDER = ["clerk", "manager", "veteran"]


def get_mayor(key: str | None) -> dict | None:
    if not key:
        return None
    return MAYORS.get(str(key))


def mayor_name(key: str | None) -> str:
    m = get_mayor(key)
    return m["name"] if m else "—"


def hire_cost(key: str) -> int:
    m = get_mayor(key)
    return int(m["hire_cost"]) if m else 0


def salary(key: str | None) -> int:
    m = get_mayor(key)
    return int(m["salary"]) if m else 0


def reports_per_year(key: str | None) -> int:
    m = get_mayor(key)
    return max(1, int(m["reports"])) if m else 0


def sat_bonus(key: str | None) -> int:
    m = get_mayor(key)
    return int(m["sat_bonus"]) if m else 0


def detail_level(key: str | None) -> int:
    m = get_mayor(key)
    return int(m["detail"]) if m else 0


def report_interval_hours(key: str | None, game_year_real_days: int = 3) -> float:
    """فاصلهٔ واقعیِ دو گزارشِ پیاپی، برحسبِ ساعت.

    مقدارِ ۰ یعنی شهرداری استخدام نشده و هیچ گزارشی نباید برود.
    """
    n = reports_per_year(key)
    if n <= 0:
        return 0.0
    return float(game_year_real_days) * 24.0 / float(n)


def options_text() -> str:
    lines = ["🏛️ <b>استخدامِ شهردار</b>", ""]
    lines.append(
        "شهردار در طولِ سال خواستهٔ مردم را برایت پیام می‌دهد و رضایت را بالا می‌برد."
    )
    lines.append("حقوق سرِ هر سالِ بازی (هر ۳ روزِ واقعی) از موجودی‌ات کم می‌شود.")
    lines.append("")
    for key in MAYOR_ORDER:
        m = MAYORS[key]
        lines.append("• <b>%s</b>" % m["name"])
        lines.append(
            "   💰 استخدام: <b>%s$</b> · 🧾 حقوقِ سالانه: <b>%s$</b>"
            % ("{:,}".format(m["hire_cost"]), "{:,}".format(m["salary"]))
        )
        lines.append(
            "   📨 گزارش در سال: <b>%d</b> · 😊 رضایت: <b>+%d٪</b>"
            % (m["reports"], m["sat_bonus"])
        )
        lines.append("   <i>%s</i>" % m["desc"])
        lines.append("")
    return "\n".join(lines).rstrip()
