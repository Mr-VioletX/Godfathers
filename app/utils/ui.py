from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

# مرحله ۲۸ — پیمایشِ منوها: هر منوی شیشه‌ای بیش از ۸ ردیف، صفحه‌بندی می‌شود.
PAGE_SIZE = 8


# 🆕 رفعِ باگ: دکمه‌ی شیشه‌ایِ «✖ انصراف» گاهی بی‌پاسخ به‌نظر می‌رسید (چون فقط ادیتِ
# پیام ممکن بود ناموفق بماند). حالا به‌جای دکمه، از کلمه‌ی متنیِ «انصراف» استفاده
# می‌شود: کاربر همان چیزی که همیشه در دستِ اوست (کیبورد) را تایپ می‌کند، بدونِ نیاز
# به ادیتِ پیامِ قبلی — یعنی این مسیر اصلاً به موفقیتِ ادیتِ تلگرام وابسته نیست.
CANCEL_WORDS = {"انصراف", "لغو", "/cancel", "cancel"}
CANCEL_HINT = "\n\n✖️ برای انصراف، همینجا بنویس: انصراف"


def is_cancel_text(text: str | None) -> bool:
    """آیا متنِ ارسالی یکی از کلماتِ انصراف است؟"""
    return (text or "").strip() in CANCEL_WORDS


async def handle_cancel_word(message: Message, state: FSMContext) -> bool:
    """اگر کاربر به‌جایِ مقدار، کلمه‌ی «انصراف» (یا مشابه) فرستاده باشد: استیت را پاک
    می‌کند، پیامِ موفقیت را نشان می‌دهد و True برمی‌گرداند تا هندلرِ فراخوان‌کننده ادامه
    ندهد. اگر کلمه‌ی انصراف نبود، هیچ کاری نمی‌کند و False برمی‌گرداند."""
    if not is_cancel_text(message.text):
        return False
    await state.clear()
    uid = message.from_user.id
    b = InlineKeyboardBuilder()
    b.button(text="🏠 بازگشت به منوی اصلی", callback_data=with_owner("menu:main", uid))
    b.adjust(1)
    await message.reply("✅ با موفقیت لغو شد! هیچ تغییری ثبت نشد.", reply_markup=b.as_markup())
    return True


def with_owner(data: str, owner_id: int) -> str:
    """شناسه‌ی صاحبِ پنل را به‌عنوان آخرین بخش به callback_data می‌چسباند."""
    return f"{data}:{owner_id}"


def split_owner(data: str) -> tuple[str, int | None]:
    """(اکشنِ پایه، شناسه‌ی صاحب) را برمی‌گرداند؛ صاحب همیشه آخرین بخشِ عددی است."""
    base, _, last = data.rpartition(":")
    if base and last.lstrip("-").isdigit():
        return base, int(last)
    return data, None


async def ensure_owner(callback: CallbackQuery) -> bool:
    """اگر کلیک‌کننده صاحبِ پنل نباشد، هشدار می‌دهد و False برمی‌گرداند."""
    _, owner_id = split_owner(callback.data)
    if owner_id is not None and callback.from_user.id != owner_id:
        await callback.answer(
            "⛔ این پنل مالِ شخص دیگری است. خودت «منو» را بفرست تا پنلِ خودت باز شود.",
            show_alert=True,
        )
        return False
    return True


# ---------------------------------------------------------------------------
# صفحه‌بندی
# ---------------------------------------------------------------------------
def page_count(total: int, per: int = PAGE_SIZE) -> int:
    per = max(1, int(per))
    return max(1, (max(0, int(total)) + per - 1) // per)


def clamp_page(page, total: int, per: int = PAGE_SIZE) -> int:
    """شماره‌ی صفحه را در بازه‌ی مجاز نگه می‌دارد (از ۰ شروع)."""
    try:
        p = int(page or 0)
    except Exception:
        p = 0
    last = page_count(total, per) - 1
    return max(0, min(p, last))


def paginate(items, page=0, per: int = PAGE_SIZE):
    """(برشِ صفحه، شماره‌ی صفحه، تعدادِ کلِ صفحات) را برمی‌گرداند."""
    items = list(items or [])
    total_pages = page_count(len(items), per)
    p = clamp_page(page, len(items), per)
    start = p * per
    return items[start:start + per], p, total_pages


def add_pager(builder, page: int, total_pages: int, cb_prefix: str, owner_id=None) -> None:
    """دو دکمه‌ی شیشه‌ایِ پیمایشِ چپ/راست را به منو اضافه می‌کند.

    cb_prefix باید طوری باشد که با افزودنِ شماره‌ی صفحه کامل شود؛ مانند
    "market:pf:steel" ← "market:pf:steel:2".
    """
    if total_pages <= 1:
        return
    prev_p = (page - 1) % total_pages
    next_p = (page + 1) % total_pages

    def cb(p):
        data = f"{cb_prefix}:{p}"
        return with_owner(data, owner_id) if owner_id is not None else data

    builder.button(text="◀️ قبلی", callback_data=cb(prev_p))
    builder.button(text=f"۰{page + 1}/{total_pages}".replace("۰", ""), callback_data="ui:noop")
    builder.button(text="بعدی ▶️", callback_data=cb(next_p))


async def safe_edit(message: Message, text: str, reply_markup=None) -> bool:
    """پیام را «درجا» ادیت می‌کند؛ چه متنی باشد چه عکس‌دار (کپشن).
    اگر ادیت ممکن نبود بی‌صدا رد می‌شود تا ربات کرش نکند.

    🐞 رفعِ باگ: قبلاً وقتی edit_text/edit_caption با خطا مواجه می‌شد (مثلاً پیام
    خیلی قدیمی بود یا نوعِ محتوا فرق داشت)، فقط reply_markup عوض می‌شد و متنِ قبلی
    (مثلاً «مبلغِ وام را بفرست») دست‌نخورده روی صفحه می‌ماند — یعنی به کاربر به‌اشتباه
    به‌نظر می‌رسید دکمه‌ی «✖ انصراف» هیچ کاری انجام نداده. حالا این تابع True/False
    برمی‌گرداند تا فراخوان‌کننده در صورتِ شکستِ ادیتِ متن، پیامِ تازه‌ای بفرستد."""
    try:
        if message.photo:
            await message.edit_caption(caption=text, reply_markup=reply_markup)
        else:
            await message.edit_text(text, reply_markup=reply_markup)
        return True
    except TelegramAPIError:
        # 🐞 رفعِ باگ: قبلاً فقط TelegramBadRequest گرفته می‌شد؛ خطاهای دیگرِ تلگرام
        # (مثلاً محدودیتِ سرعتِ ادیت هنگامِ کلیکِ پیاپیِ دکمه‌های پیمایش) گرفته نمی‌شد
        # و بدونِ پاسخ دادن به callback، دکمه برای همیشه در حالتِ «در حالِ بارگذاری» می‌ماند.
        try:
            await message.edit_reply_markup(reply_markup=reply_markup)
        except TelegramAPIError:
            pass
        return False


async def safe_answer(callback: CallbackQuery, *args, **kwargs) -> None:
    """پاسخِ callback query را امن می‌کند.

    🆕 مرحله ۳۱.۲ — رفعِ باگ: وقتی پردازشِ یک کلیک به‌خاطرِ کندی/کرش‌های قبلی طول
    می‌کشید، `callback.answer()` با خطای `TelegramBadRequest: query is too old`
    می‌ترکید و کلِ هندلر کرش می‌کرد — حتی اگر عملیاتِ اصلی (ساخت، ارتقا،
    خرید و ...) قبلاً با موفقیت انجام شده بود. این تابع فقط همین خطای
    خاص را می‌بلعد تا نتیجه‌ی واقعیِ عملیات از بین نرود؛ هر خطای دیگری همچنان
    raise می‌شود.
    """
    try:
        await callback.answer(*args, **kwargs)
    except TelegramBadRequest as e:
        if "query is too old" not in str(e) and "query ID is invalid" not in str(e):
            raise


# ---------------------------------------------------------------------------
# 🆕 v1.7.8.19 — نگهبانِ کلیکِ پیاپی (رفعِ هنگِ پنل‌های شیشه‌ای)
# ---------------------------------------------------------------------------
# علتِ هنگ: زدنِ پشت‌سرِهمِ دکمه‌هایی مثلِ «ارتقای پایگاه» باعث می‌شد چند
# تراکنشِ نوشتنی روی SQLite هم‌زمان شوند؛ هرکدام تا سی ثانیه منتظرِ قفل
# می‌ماندند (busy_timeout) و چون پاسخِ callback در انتهایِ هندلر فرستاده
# می‌شد، دکمه تا سی ثانیه در حالتِ بارگذاری می‌چرخید و پنل هم ادیت نمی‌شد.
# با این نگهبانِ ساده، کلیکِ دومِ همان کاربر در فاصله‌ی کوتاه بی‌صدا رد می‌شود
# و فقط نسخه‌ی اول پردازش می‌شود.
import time as _time

_CLICK_GUARD: dict[tuple[int, str], float] = {}


def click_debounce(uid: int, action: str, seconds: float = 2.0) -> bool:
    """True برمی‌گرداند اگر همین کاربر همین اکشن را لحظاتی پیش زده (باید رد شود)."""
    key = (int(uid), action)
    now = _time.monotonic()
    last = _CLICK_GUARD.get(key, 0.0)
    if now - last < seconds:
        return True
    _CLICK_GUARD[key] = now
    # پاک‌سازیِ گاه‌به‌گاه تا دیکشنری بی‌رویه بزرگ نشود
    if len(_CLICK_GUARD) > 5000:
        cutoff = now - 300
        for k in [k for k, v in _CLICK_GUARD.items() if v < cutoff]:
            _CLICK_GUARD.pop(k, None)
    return False


async def safe_show(
    message: Message, text: str, reply_markup=None, photo: str | None = None
) -> None:
    """نمایشِ «درجا» با پشتیبانی از تبدیلِ متنی↔عکس‌دار."""
    want_photo = photo is not None
    has_photo = bool(message.photo)
    if want_photo == has_photo:
        await safe_edit(message, text, reply_markup)
        return
    try:
        await message.delete()
    except TelegramBadRequest:
        pass
    if want_photo:
        await message.answer_photo(photo, caption=text, reply_markup=reply_markup)
    else:
        await message.answer(text, reply_markup=reply_markup)
