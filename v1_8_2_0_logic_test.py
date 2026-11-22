# -*- coding: utf-8 -*-
"""v1.8.2.0 — تستِ منطقِ آفلاین:

  الف) حفظ ایموجی‌های استاندارد Unicode روی دکمه‌ها
  ب) منطقِ اسکادران/ظرفیتِ سربازخانه‌ی اتحادیه (app/data/alliance_military.py)
  ج) منوهای جدیدِ سربازخانه + سالم‌بودنِ callback_dataها (بدونِ تغییر در ساختار)
  د) جدولِ روتینگِ کالبک‌های alliance_war.py (استخراج از خودِ فایل) + رگرسیون‌های رفع‌شده
  هـ) سیستمِ لاگینگ (فایل‌ها ساخته و پر می‌شوند) + میدل‌ورِ ردیابی

روی هاست (aiogram==3.13.1 واقعی) همین فایل با همان کد اجرا می‌شود؛ بدونِ aiogram،
یک استابِ سازگار با همان معناشناسیِ pydantic (extra="allow") تزریق می‌شود تا همان
مسیرهای کد تست شوند — aiogram 3.13.1 در سازنده‌ی تایپ‌ها **extra_data می‌پذیرد
(مستنداتِ همان نسخه) و فیلدهای اضافه در model_dump می‌مانند.

اجرا:  python3 v1_8_2_0_logic_test.py      (کدِ خروج ۰ = موفق)
"""
from __future__ import annotations

import asyncio
import os
import re
import sys
import types

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)


# ---------------------------------------------------------------------------
# استابِ aiogram (فقط اگر aiogram واقعی نصب نباشد — مثلاً CI آفلاین)
# ---------------------------------------------------------------------------
def _install_aiogram_stub() -> None:
    from pydantic import BaseModel, ConfigDict

    class TelegramObject(BaseModel):
        model_config = ConfigDict(extra="allow", populate_by_name=True)

    class InlineKeyboardButton(TelegramObject):
        text: str
        callback_data: str | None = None
        url: str | None = None

    class InlineKeyboardMarkup(TelegramObject):
        inline_keyboard: list[list[InlineKeyboardButton]]


    class InlineKeyboardBuilder:
        def __init__(self):
            self._buttons: list[InlineKeyboardButton] = []
            self._sizes: tuple[int, ...] = (1,)

        def button(self, **kwargs):
            return self.add(self._button_type(**kwargs))

        @property
        def _button_type(self):
            return InlineKeyboardButton

        def add(self, *btns):
            self._buttons.extend(btns)
            return self

        def row(self, *btns, width=1):
            # ساده‌سازی: دکمه‌ها را اضافه می‌کند؛ عرض در adjust اعمال می‌شود
            return self.add(*btns)

        def adjust(self, *sizes):
            self._sizes = sizes or (1,)
            return self

        def as_markup(self):
            rows, idx, sizes = [], 0, list(self._sizes)
            while idx < len(self._buttons):
                size = sizes[min(len(rows), len(sizes) - 1)]
                rows.append(self._buttons[idx: idx + size])
                idx += size
            return InlineKeyboardMarkup(inline_keyboard=rows)

    class _Event:
        def __init__(self, **kw):
            for k, v in kw.items():
                setattr(self, k, v)

    class User(_Event):
        pass

    class Chat(_Event):
        pass

    class Message(_Event):
        pass

    class CallbackQuery(_Event):
        pass

    class Update(_Event):
        pass

    class ErrorEvent(_Event):
        pass

    class BaseMiddleware:
        pass

    class TelegramAPIError(Exception):
        pass

    class TelegramBadRequest(TelegramAPIError):
        pass

    class _Method(TelegramObject):
        text: str | None = None
        caption: str | None = None
        reply_markup: object | None = None

    method_names = (
        "SendMessage", "EditMessageText", "SendPhoto", "SendVideo", "SendAnimation",
        "SendDocument", "SendAudio", "SendVoice", "EditMessageCaption", "CopyMessage",
    )
    methods_mod = types.ModuleType("aiogram.methods")
    for _n in method_names:
        setattr(methods_mod, _n, type(_n, (_Method,), {}))

    class FSMContext:  # فقط برای ایمپورت
        pass

    class State:
        pass

    class StatesGroup:
        pass

    aiogram = types.ModuleType("aiogram")
    aiogram.BaseMiddleware = BaseMiddleware
    aiogram.F = types.SimpleNamespace()  # هندلرها ایمپورت نمی‌شوند؛ فقط برای اطمینان

    types_mod = types.ModuleType("aiogram.types")
    for _n, _c in {
        "InlineKeyboardButton": InlineKeyboardButton,
        "InlineKeyboardMarkup": InlineKeyboardMarkup,
        "User": User, "Chat": Chat, "Message": Message,
        "CallbackQuery": CallbackQuery, "Update": Update, "ErrorEvent": ErrorEvent,
    }.items():
        setattr(types_mod, _n, _c)

    utils_mod = types.ModuleType("aiogram.utils")
    kb_mod = types.ModuleType("aiogram.utils.keyboard")
    kb_mod.InlineKeyboardBuilder = InlineKeyboardBuilder
    utils_mod.keyboard = kb_mod

    exc_mod = types.ModuleType("aiogram.exceptions")
    exc_mod.TelegramAPIError = TelegramAPIError
    exc_mod.TelegramBadRequest = TelegramBadRequest

    fsm_mod = types.ModuleType("aiogram.fsm")
    fsm_ctx = types.ModuleType("aiogram.fsm.context")
    fsm_ctx.FSMContext = FSMContext
    fsm_state = types.ModuleType("aiogram.fsm.state")
    fsm_state.State = State
    fsm_state.StatesGroup = StatesGroup
    fsm_mod.context = fsm_ctx
    fsm_mod.state = fsm_state

    for name, mod in [
        ("aiogram", aiogram), ("aiogram.types", types_mod),
        ("aiogram.utils", utils_mod), ("aiogram.utils.keyboard", kb_mod),
        ("aiogram.exceptions", exc_mod), ("aiogram.methods", methods_mod),
        ("aiogram.fsm", fsm_mod), ("aiogram.fsm.context", fsm_ctx),
        ("aiogram.fsm.state", fsm_state),
    ]:
        sys.modules[name] = mod


try:
    import aiogram  # noqa: F401
    USING_STUB = False
except ModuleNotFoundError:
    _install_aiogram_stub()
    USING_STUB = True

# ---------------------------------------------------------------------------
from aiogram.utils.keyboard import InlineKeyboardBuilder as StandardKeyboardBuilder  # noqa: E402
from app.utils.ui import split_owner, with_owner  # noqa: E402
from app.data import alliance_military as AM  # noqa: E402
from app.keyboards import alliance_menu as ALKB  # noqa: E402
from app.states import AllianceStates  # noqa: E402

_OK = 0
_FAIL = 0


def check(name: str, cond: bool, extra: str = "") -> None:
    global _OK, _FAIL
    if cond:
        _OK += 1
        print(f"  ✅ {name}")
    else:
        _FAIL += 1
        print(f"  ❌ {name} {extra}")


def dump(obj):
    return obj.model_dump(exclude_none=True)


print(f"== v1.8.2.0 logic test ==  (aiogram: {'stub' if USING_STUB else 'REAL'})")

# ---------------------------------------------------------------------------
print("\n[الف] ایموجی‌های استاندارد Unicode روی دکمه‌ها")
# ---------------------------------------------------------------------------
_std = StandardKeyboardBuilder()
_std.button(text="🛒 فروشگاه", callback_data="shop:test:42")
_std.button(text="⚔️ بخش نظامی", callback_data="mil:hub:42")
_std_rows = dump(_std.adjust(1).as_markup())["inline_keyboard"]
check("متن دکمه‌ها ایموجی استاندارد را عیناً حفظ می‌کند",
      [_std_rows[0][0]["text"], _std_rows[1][0]["text"]] == ["🛒 فروشگاه", "⚔️ بخش نظامی"])
check("دکمه‌ها فقط فیلدهای استاندارد دارند",
      all(set(btn).issubset({"text", "callback_data", "url"}) for row in _std_rows for btn in row))

# ---------------------------------------------------------------------------
print("\n[ب] منطقِ اسکادران/ظرفیت (data-layer)")
# ---------------------------------------------------------------------------
check("squad_cost خطی است", AM.squad_cost("a_s1", 3) == 3 * AM.squad_cost("a_s1", 1))
check("squad_unit_cost = squad_cost×1", AM.squad_unit_cost("a_s1") == AM.squad_cost("a_s1", 1))
check("max_squads: ظرفیت ۱۰۰۰ / اسکادران ۲۰تایی = ۵۰", AM.max_squads_possible("a_s1", 1000, 10**12) == 50)
check("max_squads: صندوقِ صفر = ۰", AM.max_squads_possible("a_s1", 1000, 0) == 0)
check("max_squads: ظرفیتِ ۱۹ (< یک اسکادران) = ۰", AM.max_squads_possible("a_s1", 19, 10**12) == 0)
check("max_squads: صندوق محدودکننده است", AM.max_squads_possible("a_s1", 10**9, AM.squad_cost("a_s1", 1) * 2) == 2)
check("presets: با سقفِ ۵۰ → [1,2,5,10]", AM.squad_preset_options("a_s1", 50) == [1, 2, 5, 10])
check("presets: با سقفِ ۳ → [1,2]", AM.squad_preset_options("a_s1", 3) == [1, 2])
check("presets: با سقفِ ۰ → []", AM.squad_preset_options("a_s1", 0) == [])
check("ظرفیتِ سربازخانه: س۱=۱٬۰۰۰ / س۲=۲٬۰۰۰ / س۱۰=۵۱۲٬۰۰۰",
      (AM.barracks_capacity(1), AM.barracks_capacity(2), AM.barracks_capacity(10)) == (1000, 2000, 512000))
check("train_seconds صعودی است", AM.train_seconds("a_s1", 2) > AM.train_seconds("a_s1", 1) > 0)
check("هر ۷ دسته نیرو دارد و برچسب دارد", all(AM.units_in_category(c) and c in AM.CATEGORY_LABELS for c in AM.CATEGORY_ORDER))

# ---------------------------------------------------------------------------
print("\n[ج] منوهای جدیدِ سربازخانه + سلامتِ callback_data")
# ---------------------------------------------------------------------------
UID = 777
menus = []
m_home = ALKB.alw_barracks_home_menu(UID, can_manage=True, auto_on=False, queued_count=3)
menus.append(("home", m_home))
m_shop = ALKB.alw_shop_categories_menu(UID)
menus.append(("shop", m_shop))
m_cat1 = ALKB.alw_category_units_menu(UID, "soldier", bk_level=1, counts={"a_s1": 40})
m_cat3 = ALKB.alw_category_units_menu(UID, "soldier", bk_level=3, counts={})
menus += [("cat_lv1", m_cat1), ("cat_lv3", m_cat3)]
m_buy = ALKB.alw_buy_squads_menu(UID, "a_s1", AM.squad_preset_options("a_s1", 50), 50)
menus.append(("buy", m_buy))
m_confirm = ALKB.alw_buy_confirm_menu(UID, "a_s1", 5)
menus.append(("confirm", m_confirm))
m_q = ALKB.alw_queue_menu(UID, page=1, total_pages=3, can_manage=True)
menus.append(("queue", m_q))
m_qc = ALKB.alw_queue_cancel_menu(UID, [{"id": 9, "name": "X", "squads": 2, "units": 40}], 1, 3)
menus.append(("qcancel", m_qc))
m_up = ALKB.alw_upgrade_menu(UID, [("a_s1", 40, 0)], treasury=10**12)
menus.append(("upgrade", m_up))


def all_buttons(markup):
    return [b for row in dump(markup)["inline_keyboard"] for b in row]


home_cbs = [b["callback_data"] for b in all_buttons(m_home)]
check("هاب: دکمه‌ی تولید به alw:shop می‌رود (نه منوی کشویی)", any(c.startswith(f"alw:shop:{UID}") for c in home_cbs))
check("هاب: صفِ تولید با شمارنده", any(c.startswith(f"alw:queue:0:{UID}") for c in home_cbs))
check("هاب: ارتقا و آموزشِ مستقل (alw:upgm)", any(c.startswith(f"alw:upgm:{UID}") for c in home_cbs))
check("هاب: بیمارستان/راهنما/بازگشت حفظ شده‌اند",
      any(c.startswith(f"alw:hosp:{UID}") for c in home_cbs)
      and any(c.startswith(f"alw:guide:{UID}") for c in home_cbs)
      and any(c.startswith(f"all:hub:{UID}") for c in home_cbs))
check("هاب: ایموجی‌های استاندارد داخل متن دکمه‌ها حفظ شده‌اند",
      any(str(b.get("text", "")).startswith("🏭") for b in all_buttons(m_home)))

shop_cbs = [b["callback_data"] for b in all_buttons(m_shop)]
check("فروشگاه: هر ۷ دسته دکمه‌ی خودش را دارد", sum(1 for c in shop_cbs if c.startswith("alw:cat:")) == 7)

cat1_cbs = [b["callback_data"] for b in all_buttons(m_cat1)]
check("دسته (سطح ۱): ساختِ T1 باز، T2/T3 قفل",
      any(c.startswith(f"alw:buy:a_s1:{UID}") for c in cat1_cbs)
      and not any(c.startswith(f"alw:buy:a_s2:{UID}") for c in cat1_cbs)
      and sum(1 for c in cat1_cbs if c.startswith(f"alw:locked:{UID}")) == 2)
cat3_cbs = [b["callback_data"] for b in all_buttons(m_cat3)]
check("دسته (سطح ۳): هر ۳ نیرو قابلِ ساخت", sum(1 for c in cat3_cbs if c.startswith("alw:buy:")) == 3)

buy_cbs = [b["callback_data"] for b in all_buttons(m_buy)]
check("انتخابِ تعداد: ۴ پیش‌فرض + حداکثر + دستی + بازگشت",
      sum(1 for c in buy_cbs if c.startswith("alw:buyq:")) == 5
      and any(c.startswith(f"alw:buyn:a_s1:{UID}") for c in buy_cbs)
      and any(c.startswith(f"alw:cat:soldier:{UID}") for c in buy_cbs))
check("انتخابِ تعداد: دکمه‌ی حداکثر = ۵۰ اسکادران", any(c == f"alw:buyq:a_s1:50:{UID}" for c in buy_cbs))

check("تأیید: alw:buyok با همان تعداد", any(b["callback_data"] == f"alw:buyok:a_s1:5:{UID}" for b in all_buttons(m_confirm)))
q_cbs = [b["callback_data"] for b in all_buttons(m_q)]
check("صف: پیمایش صفحه را حفظ می‌کند (نه برگشت به اول)",
      any(c == f"alw:queue:2:{UID}" for c in q_cbs) and any(c == f"alw:queue:0:{UID}" for c in q_cbs) and any(c == f"alw:queue:1:{UID}" for c in q_cbs))
qc_cbs = [b["callback_data"] for b in all_buttons(m_qc)]
check("لغو: دکمه‌ی بچ با id و صفحه", any(c == f"alw:qcancel:9:1:{UID}" for c in qc_cbs))
check("ارتقا: دکمه‌ی alw:upgu برای واحدِ دارا", any(b["callback_data"] == f"alw:upgu:a_s1:{UID}" for b in all_buttons(m_up)))

# ---------------------------------------------------------------------------
print("\n[د] روتینگِ کالبک‌ها (از خودِ alliance_war.py) + رگرسیون‌ها")
# ---------------------------------------------------------------------------
# جدولِ روتینگ از همه‌ی فایل‌های هندلر (همان‌طور که bot.py همه‌ی روترها را include می‌کند)
# تا کالبک‌های بین‌روتری (all:hub, menu:main, mil:*, ui:noop و ...) هم پوشش داده شوند.
_ROUTES: list[tuple[list[tuple[str, str]], str, str]] = []
for _hf in sorted(os.listdir(os.path.join(ROOT, "app/handlers"))):
    if not _hf.endswith(".py"):
        continue
    _src = open(os.path.join(ROOT, "app/handlers", _hf), encoding="utf-8").read()
    # (.*) حریصانه تا «آخرین» پرانتزِ خط می‌رود و [^\n]* کامنت‌های انتهایی را هم می‌پوشاند
    for _m in re.finditer(r'@router\.callback_query\((.*)\)[^\n]*\n\s*async def (\w+)', _src):
        _expr, _fn = _m.group(1), _m.group(2)
        _filters = [("sw", p) for p in re.findall(r'F\.data\.startswith\("([^"]+)"\)', _expr)]
        _filters += [("eq", p) for p in re.findall(r'F\.data\s*==\s*"([^"]+)"', _expr)]
        if _filters:
            _ROUTES.append((_filters, _fn, _hf))


def route(data: str) -> str | None:
    for filters, fn, _hf in _ROUTES:
        for kind, pat in filters:
            if (kind == "sw" and data.startswith(pat)) or (kind == "eq" and data == pat):
                return fn
    return None


_EXPECTED = {
    "alw:bk:42": "barracks_home",
    "alw:prod:1:42": "prod_legacy",
    "alw:shop:42": "shop_categories",
    "alw:cat:tank:42": "shop_category",
    "alw:locked:42": "locked_cb",
    "alw:noop:42": "noop_cb",
    "alw:buy:a_s1:42": "buy_choose_squads",
    "alw:buyq:a_s1:5:42": "buy_preview",
    "alw:buyok:a_s1:5:42": "buy_do",
    "alw:buyn:a_s1:42": "buy_manual_start",
    "alw:queue:2:42": "queue_home",
    "alw:qcancelmenu:0:42": "queue_cancel_menu",
    "alw:qcancel:12:1:42": "queue_cancel",
    "alw:upgm:42": "upgrade_menu_cb",
    "alw:upgu:a_s1:42": "upgrade_unit_cb",
    "alw:upbk:42": "upgrade_barracks_cb",
    "alw:auto:42": "auto_home",
    "alw:auto:tg:42": "auto_home",
    "alw:autoset:a_s1:42": "auto_set_start",   # رگرسیون: قبلاً در auto_home می‌افتاد
    "alw:trs:42": "treasury_home",
    "alw:dep:42": "deposit_start",
    "alw:war:rf:7:42": "battle_refresh",
    "alw:war:cf:7:42": "battle_ceasefire",
    "alw:war:42": "battle_home",               # رگرسیون: قبلاً == بدونِ مالک بود و مرده بود
    "alw:hosp:42": "hospital_home",
    "alw:heal:3:42": "heal_cb",
    "alw:rank:0:42": "cup_ranking",
    "alw:guide:42": "guide_cb",
}
check("جدولِ روتینگ از alliance_war استخراج شد", any(fn == "buy_preview" for _f, fn, _hf in _ROUTES))
_bad = [(c, route(c), want) for c, want in _EXPECTED.items() if route(c) != want]
check(f"روتینگ: هر {len(_EXPECTED)} کالبک به هندلرِ درست می‌رسد", not _bad, str(_bad))

_dead = []
for name, mkx in menus:
    for b in all_buttons(mkx):
        if route(b["callback_data"]) is None:
            _dead.append((name, b["callback_data"]))
check("هیچ دکمه‌ی مرده‌ای در منوهای جدید نیست (در کلِ روترها)", not _dead, str(_dead))

check("AllianceStates.buying_squads اضافه شده", hasattr(AllianceStates, "buying_squads"))

# ---------------------------------------------------------------------------
print("\n[هـ] سیستمِ لاگینگ")
# ---------------------------------------------------------------------------
import logging  # noqa: E402
import tempfile  # noqa: E402

from app.utils.logging_setup import setup_logging  # noqa: E402
from app.middlewares.update_logging import UpdateLoggingMiddleware, log_unhandled_error  # noqa: E402
from aiogram.types import CallbackQuery, Chat, ErrorEvent, Message, Update, User  # noqa: E402

_tmp = tempfile.mkdtemp(prefix="logs_test_")
setup_logging(log_dir=_tmp)

_records: list[logging.LogRecord] = []


class _Cap(logging.Handler):
    def emit(self, record):
        _records.append(record)


for _n in ("godfather.updates", "godfather.errors"):
    logging.getLogger(_n).addHandler(_Cap())


def _mw_log_test() -> bool:
    async def run():
        mw = UpdateLoggingMiddleware()
        user = User(id=42, username="amir", full_name="Amir")
        chat = Chat(id=100)
        cb = CallbackQuery(data="alw:buyq:a_s1:5:42", from_user=user, message=Message(chat=chat))

        class _State:
            async def get_state(self):
                return "AllianceStates:buying_squads"

        async def ok_handler(event, data):
            return "done"

        async def bad_handler(event, data):
            raise RuntimeError("boom")

        r = await mw(ok_handler, cb, {"state": _State()})
        assert r == "done"
        try:
            await mw(bad_handler, cb, {"state": _State()})
            return False
        except RuntimeError:
            pass
        # لایه‌ی دوم: خطای کامل
        upd = Update(update_id=1, message=None, edited_message=None, callback_query=cb)
        await log_unhandled_error(ErrorEvent(update=upd, exception=RuntimeError("boom")))
        return True

    return asyncio.run(run())


check("میدل‌ورِ ردیابی: شروع/پایان/خطا ثبت می‌شود", _mw_log_test())
txt = "\n".join(r.getMessage() for r in _records)
check("لاگِ آپدیت شاملِ callback_data و کاربر و state است",
      "alw:buyq:a_s1:5:42" in txt and "uid=42" in txt and "buying_squads" in txt)
check("خطا در لاگرِ errors با traceback ثبت شد",
      any(r.name == "godfather.errors" and r.exc_info for r in _records))
check("فایل‌های لاگ ساخته شدند (bot/errors/updates)",
      all(os.path.exists(os.path.join(_tmp, f)) for f in ("bot.log", "errors.log", "updates.log")))

# ---------------------------------------------------------------------------
print(f"\n== نتیجه: {_OK} موفق، {_FAIL} ناموفق ==")
sys.exit(1 if _FAIL else 0)
