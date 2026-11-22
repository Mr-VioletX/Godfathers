import json

DEFAULT_PRIVACY = {"cash": True, "level": True, "rank": True, "title": True, "photo": True}
# enabled: کلید اصلی روشن/خاموش. groups: تنظیم جداگانه‌ی هر گروه (chat_id → bool)
# 🆕 مرحله ۳۰ — idle_minutes: اگر این‌قدر دقیقه از آخرین فعالیتِ کاربر گذشته باشد،
#     دفعهٔ بعد که درِ ربات یا گروه چیزی می‌نویسد، آنلاین‌شدنِ او اعلام می‌شود.
# in_group: آیا فعالیت درِ گروه هم اعلام را راه بیندازد؟
DEFAULT_ANNOUNCE = {"enabled": True, "groups": {}, "idle_minutes": 180, "in_group": True}

# گزینه‌هایِ آمادهٔ فاصلهٔ اعلام (دقیقه)
ANNOUNCE_IDLE_CHOICES = [15, 30, 60, 180, 360, 720, 1440]
ANNOUNCE_IDLE_MIN = 5
ANNOUNCE_IDLE_MAX = 10080   # یک هفته


def idle_label(minutes) -> str:
    """برچسبِ فارسیِ یک بازهٔ زمانی."""
    m = int(minutes or 0)
    if m < 60:
        return f"{m} دقیقه"
    if m % 1440 == 0:
        d = m // 1440
        return "یک روز" if d == 1 else f"{d} روز"
    h = m / 60
    return (f"{int(h)} ساعت" if float(h).is_integer() else f"{h:.1f} ساعت")


def announce_idle_minutes(settings: dict) -> int:
    """فاصلهٔ انتخابیِ کاربر (با حدِّ ایمن)."""
    try:
        m = int(settings.get("idle_minutes", 180))
    except (TypeError, ValueError):
        m = 180
    return max(ANNOUNCE_IDLE_MIN, min(ANNOUNCE_IDLE_MAX, m))


def announce_in_group(settings: dict) -> bool:
    """آیا فعالیتِ کاربر درِ گروه هم اعلام را راه بیندازد؟"""
    return bool(settings.get("in_group", True))


def _load(raw: str | None, default: dict) -> dict:
    if not raw:
        return default.copy()
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        return default.copy()
    merged = default.copy()
    merged.update(data)
    return merged


def dump_json(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False)


def load_privacy(raw: str | None) -> dict:
    return _load(raw, DEFAULT_PRIVACY)


def load_announce(raw: str | None) -> dict:
    return _load(raw, DEFAULT_ANNOUNCE)


def is_group_announce_enabled(settings: dict, chat_id: int) -> bool:
    """آیا در این گروه خاص باید اعلام آنلاین ارسال شود؟"""
    if not settings.get("enabled", True):
        return False
    groups = settings.get("groups", {})
    return groups.get(str(chat_id), True)