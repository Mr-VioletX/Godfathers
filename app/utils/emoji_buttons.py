# -*- coding: utf-8 -*-
"""🆕 v1.8.2.0 — Custom Emoji روی دکمه‌های شیشه‌ای (Inline Keyboard).

═══════════════════════════════════════════════════════════════════════════════
بررسیِ رسمیِ Telegram Bot API (بدونِ حدس — از changelog و core.telegram.org/bots/api):
═══════════════════════════════════════════════════════════════════════════════
• از Bot API 9.4 فیلدِ «icon_custom_emoji_id» به InlineKeyboardButton (و
  KeyboardButton) اضافه شده است: «allowing bots to show a custom emoji on
  buttons if they are able to use custom emoji in the message».
• این فیلد دقیقاً «یک» آیکونِ ایموجیِ پرمیوم را «قبل از متنِ» دکمه نمایش می‌دهد.
• متنِ دکمه‌ها هیچ‌گونه MessageEntity (از جمله type="custom_emoji" با
  offset/length) نمی‌پذیرد؛ entity فقط برای متن/کپشنِ پیام کار می‌کند. پس قرار‌دادنِ
  چند ایموجیِ پرمیوم «داخلِ» متنِ دکمه از نظرِ API ممکن نیست — راهِ رسمیِ دکمه
  فقط همین فیلدِ آیکون است (یک آیکون در کنارِ متنِ معمولی).
• شرطِ دسترسی: ربات باید مجاز به استفاده از custom emoji باشد (خریدِ یوزرنیمِ
  اضافه از Fragment، یا پرمیومِ مالکِ ربات در چت‌های خصوصی/گروه/سوپرگروه) — همان
  شرطی که tg-emoji در متنِ پیام دارد (این ربات از v1.8.1.6 از آن استفاده می‌کند).

سازگاری با aiogram 3.13.1 (نسخه‌ی پین‌شده‌ی پروژه):
• این نسخه قدیمی‌تر از Bot API 9.4 است و فیلد را در مدل ندارد، اما تایپ‌های
  aiogram 3 با extra="allow" ساخته شده‌اند؛ فیلد به‌عنوانِ فیلدِ اضافه عبور می‌کند
  و در سریالایزِ نهاییِ درخواست (model_dump) دست‌نخورده به تلگرام می‌رسد.
• این ماژول هنگامِ ساختِ اولین دکمه این رفتار را «اجرایی» آزمون می‌کند؛ اگر نسخه‌ی
  aiogram روزی این قابلیت را از دست بدهد، با خطای شفاف خبر می‌دهد، نه اینکه بی‌صدا
  آیکون‌ها را قورت بدهد. اگر aiogram ارتقا پیدا کند و فیلد بومی شود، همین کد بدونِ
  تغییر از مسیرِ بومی استفاده می‌کند.

استفاده:
    from app.utils.emoji_buttons import EmojiKeyboardBuilder, emoji_button

    b = EmojiKeyboardBuilder()
    b.button(text="فروشگاه", custom_emoji_id="5431499171045581032", callback_data="shop")
    b.button(text="🛒 فروشگاه", emoji="🛒", callback_data="shop")   # از نگاشتِ پکِ خودت
    b.button(text="منو", callback_data="menu:main")                 # بدونِ آیکون = مثلِ قبل

    # یا مستقیم:
    btn = emoji_button(text="فروشگاه", custom_emoji_id="...", callback_data="shop")
"""
from __future__ import annotations

import logging

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, MessageEntity
from aiogram.utils.keyboard import InlineKeyboardBuilder

log = logging.getLogger(__name__)

ICON_FIELD = "icon_custom_emoji_id"
STYLE_FIELD = "style"   # Bot API 9.4 — danger/success/primary (اختیاری؛ پاس‌ترو)

_VS16 = "\ufe0f"


# ---------------------------------------------------------------------------
# نگاشتِ ایموجیِ استاندارد ← custom_emoji_id (پکِ پرمیومِ خودِ ربات)
# ---------------------------------------------------------------------------
def resolve_custom_emoji_id(emoji: str | None) -> str | None:
    """custom_emoji_id متناظر با یک ایموجیِ استاندارد را از نگاشتِ پک برمی‌گرداند.

    نگاشت (app/data/premium_emoji.py ← emoji.txt) عمداً واریاسیون‌های «بدونِ VS16»
    را هم دارد؛ این تابع هر سه شکل (همان‌طورکه هست / بدونِ VS16 / با VS16) را می‌آزماید.
    اگر ایموجی در پک نباشد None برمی‌گردد (یعنی دکمه باید بدونِ آیکون ساخته شود).
    """
    if not emoji:
        return None
    try:
        from app.data.premium_emoji import EMOJI_IDS
    except Exception:
        return None
    hit = EMOJI_IDS.get(emoji)
    if hit:
        return hit
    stripped = emoji.replace(_VS16, "")
    if stripped != emoji and EMOJI_IDS.get(stripped):
        return EMOJI_IDS[stripped]
    with_vs = emoji + _VS16
    if EMOJI_IDS.get(with_vs):
        return EMOJI_IDS[with_vs]
    return None


# ---------------------------------------------------------------------------
# ساختِ دکمه با فیلدِ آیکون (سازگار با aiogram 3.13.1 و نسخه‌های جدیدتر)
# ---------------------------------------------------------------------------
def _set_optional_field(btn: InlineKeyboardButton, field: str, value: str) -> None:
    """فیلد را روی دکمه می‌نشاند و «اثبات» می‌کند که در خروجیِ نهایی می‌ماند.

    سه مسیر: ۱) فیلدِ بومیِ مدل (aiogramهای جدید) ۲) extra="allow" (aiogram 3.13.1)
    ۳) تزریقِ مستقیم به __pydantic_extra__. اگر هیچ‌کدام نشد، خطای شفاف.
    """
    try:
        setattr(btn, field, value)
    except Exception:
        extra = getattr(btn, "__pydantic_extra__", None)
        if isinstance(extra, dict):
            extra[field] = value
        else:  # pragma: no cover — حالتِ غیرمنتظره
            raise RuntimeError(
                f"این نسخه‌ی aiogram اجازه‌ی فیلدِ {field} را روی دکمه نمی‌دهد."
            )
    dumped = btn.model_dump(exclude_none=True)
    if str(dumped.get(field) or "") != str(value):
        extra = getattr(btn, "__pydantic_extra__", None)
        if isinstance(extra, dict):
            extra[field] = value
            dumped = btn.model_dump(exclude_none=True)
    if str(dumped.get(field) or "") != str(value):
        raise RuntimeError(
            f"aiogram فیلدِ {field} را در سریالایزِ دکمه نگه نمی‌دارد؛ "
            "aiogram را به نسخه‌ای با پشتیبانیِ Bot API 9.4 ارتقا بده."
        )


def _strip_leading_emoji(text: str, emoji: str) -> str:
    """اگر متن با همان ایموجی شروع شده باشد آن را برمی‌دارد تا کنارِ آیکونِ
    پرمیوم «دو بار» دیده نشود (آیکون را خودِ تلگرام قبل از متن می‌گذارد)."""
    for cand in {emoji, emoji.replace(_VS16, ""), emoji + _VS16}:
        if cand and text.startswith(cand):
            return text[len(cand):].lstrip("  ").lstrip(_VS16).lstrip(" ")
    return text


def emoji_button(
    *,
    text: str,
    callback_data: str | None = None,
    custom_emoji_id: str | None = None,
    emoji: str | None = None,
    style: str | None = None,
    **kwargs,
) -> InlineKeyboardButton:
    """یک InlineKeyboardButton معتبر با آیکونِ Custom Emoji می‌سازد.

    پارامترها:
      text            متنِ دکمه (می‌تواند ایموجی‌های استاندارد هم داشته باشد).
      callback_data   مثلِ قبل؛ دست‌نخورده می‌ماند (هیچ‌گاه عوض نمی‌شود).
      custom_emoji_id آیدیِ عددیِ ایموجیِ پرمیوم (مستقیم).
      emoji           جایگزینِ راحت: ایموجیِ استاندارد را می‌دهی، آیدی از نگاشتِ
                      پکِ خودِ ربات (premium_emoji.py) خوانده می‌شود. اگر متن با
                      همین ایموجی شروع شده باشد، از ابتدای متن برداشته می‌شود تا
                      دو بار دیده نشود. اگر در پک نباشد، دکمه بدونِ آیکون ساخته
                      می‌شود (متن دست‌نخورده) — منوها هرگز نمی‌شکنند.
      style           «danger»/«success»/«primary» (Bot API 9.4) — اختیاری.
      kwargs          بقیه‌ی فیلدهای InlineKeyboardButton (url, web_app و ...).
    """
    icon_id: str | None = str(custom_emoji_id) if custom_emoji_id else None
    if icon_id is None and emoji:
        icon_id = resolve_custom_emoji_id(emoji)
        if icon_id:
            text = _strip_leading_emoji(text, emoji)
    btn = InlineKeyboardButton(text=text, callback_data=callback_data, **kwargs)
    if icon_id:
        _set_optional_field(btn, ICON_FIELD, icon_id)
    if style:
        _set_optional_field(btn, STYLE_FIELD, style)
    return btn


# نامِ مستعار برای دقیقاً همان سینتکسِ خواسته‌شده: button(text=..., custom_emoji_id=...)
button = emoji_button


class EmojiKeyboardBuilder(InlineKeyboardBuilder):
    """InlineKeyboardBuilder با پشتیبانیِ custom_emoji_id/emoji/style در button().

    اگر هیچ‌کدام از سه پارامتر داده نشود، دقیقاً رفتارِ بیلدرِ استاندارد را دارد؛
    پس جایگزین‌کردنِ InlineKeyboardBuilder با این کلاس در هیچ منویی چیزی را نمی‌شکند.
    """

    def button(  # type: ignore[override]
        self,
        *,
        text: str,
        custom_emoji_id: str | None = None,
        emoji: str | None = None,
        style: str | None = None,
        **kwargs,
    ) -> "EmojiKeyboardBuilder":
        if custom_emoji_id is None and emoji is None and style is None:
            return super().button(text=text, **kwargs)  # type: ignore[return-value]
        return self.add(  # type: ignore[return-value]
            emoji_button(
                text=text,
                custom_emoji_id=custom_emoji_id,
                emoji=emoji,
                style=style,
                **kwargs,
            )
        )


# ---------------------------------------------------------------------------
# ابزارهای ایمنی/نگه‌داری
# ---------------------------------------------------------------------------
def _iter_buttons(markup: InlineKeyboardMarkup):
    for row in getattr(markup, "inline_keyboard", None) or []:
        for btn in row:
            yield btn


def has_button_icons(markup: InlineKeyboardMarkup | None) -> bool:
    """آیا این کیبورد دست‌کم یک دکمه با آیکونِ پرمیوم (یا style) دارد؟"""
    if markup is None:
        return False
    for btn in _iter_buttons(markup):
        if getattr(btn, ICON_FIELD, None) or getattr(btn, STYLE_FIELD, None):
            return True
    return False


def strip_button_icons(markup: InlineKeyboardMarkup | None) -> int:
    """همه‌ی آیکون‌ها/styleهای دکمه‌ها را برمی‌دارد (شبکهٔ ایمنی وقتی تلگرام
    custom emoji را رد کند). تعدادِ فیلدهای برداشته‌شده را برمی‌گرداند."""
    removed = 0
    if markup is None:
        return removed
    for btn in _iter_buttons(markup):
        for field in (ICON_FIELD, STYLE_FIELD):
            if getattr(btn, field, None):
                extra = getattr(btn, "__pydantic_extra__", None)
                if isinstance(extra, dict) and field in extra:
                    extra.pop(field, None)
                    removed += 1
                else:
                    try:
                        setattr(btn, field, None)
                        removed += 1
                    except Exception:
                        pass
    if removed:
        log.warning("emoji_buttons: %d آیکون/style از دکمه‌ها برداشته شد (ردِ تلگرام).", removed)
    return removed


_SUPPORT_CACHE: bool | None = None


def buttons_support_check() -> bool:
    """آزمونِ اجرایی: آیا aiogramِ نصب‌شده icon_custom_emoji_id را سریالایز می‌کند؟
    نتیجه کش می‌شود؛ در لاگ هم ثبت می‌شود تا روی هاست قابلِ رؤیت باشد."""
    global _SUPPORT_CACHE
    if _SUPPORT_CACHE is not None:
        return _SUPPORT_CACHE
    try:
        probe = emoji_button(text="probe", callback_data="probe:cb", custom_emoji_id="1")
        ok = probe.model_dump(exclude_none=True).get(ICON_FIELD) == "1"
    except Exception as e:  # pragma: no cover
        log.error("emoji_buttons: پشتیبانیِ icon_custom_emoji_id تأیید نشد: %s", e)
        ok = False
    _SUPPORT_CACHE = ok
    log.info("emoji_buttons: پشتیبانیِ آیکونِ پرمیوم روی دکمه = %s", ok)
    return ok


# ---------------------------------------------------------------------------
# MessageEntity برای «متنِ پیام» (نه دکمه) — راهِ رسمیِ custom emoji در متن
# ---------------------------------------------------------------------------
def custom_emoji_entities(text: str, *, mapping: dict | None = None) -> list[MessageEntity]:
    """برای هر ایموجیِ نگاشت‌شده در «متنِ پیام» یک MessageEntity با
    type="custom_emoji" و offset/lengthِ درست (بر حسبِ واحدهای UTF-16، طبقِ API)
    می‌سازد. خروجی را به‌عنوانِ entities به sendMessage/… بده (در آن حالت
    parse_mode نده). برای دکمه‌ها کاربرد ندارد — دکمه فقط icon_custom_emoji_id.
    """
    if mapping is None:
        try:
            from app.data.premium_emoji import EMOJI_IDS as mapping  # type: ignore[assignment]
        except Exception:
            mapping = {}
    entities: list[MessageEntity] = []
    if not text or not mapping:
        return entities
    offset16 = 0
    i = 0
    keys = sorted(mapping.keys(), key=len, reverse=True)
    while i < len(text):
        hit = None
        for k in keys:
            if text.startswith(k, i):
                hit = k
                break
        chunk = hit if hit else text[i]
        units = len(chunk.encode("utf-16-le")) // 2
        if hit:
            entities.append(
                MessageEntity(
                    type="custom_emoji",
                    offset=offset16,
                    length=units,
                    custom_emoji_id=str(mapping[hit]),
                )
            )
        offset16 += units
        i += len(chunk)
    return entities


# ---------------------------------------------------------------------------
# نمونه‌ی واقعیِ خواسته‌شده — کیبورد ۳ دکمه‌ای با Custom Emoji و callback_dataهای
# واقعیِ خودِ ربات (بخش‌های موجود: فروشگاهِ نظامی/هابِ نظامی/منوی اصلی).
# ---------------------------------------------------------------------------
def demo_keyboard(owner_id: int) -> InlineKeyboardMarkup:
    """۳ دکمه: هر سه آیکونِ پرمیوم دارند (از پکِ RestrictedEmoji) و callback_data
    همانِ بخش‌های واقعیِ ربات است؛ پس کلیک، دقیقاً همان مسیرهای همیشگی را طی می‌کند."""
    from app.utils.ui import with_owner

    b = EmojiKeyboardBuilder()
    b.button(text="🛒 فروشگاهِ تسلیحات", emoji="🛒", callback_data=with_owner("mil:shop", owner_id))
    b.button(text="⚔️ بخشِ نظامی", emoji="⚔️", callback_data=with_owner("mil:hub", owner_id))
    b.button(text="🏠 منوی اصلی", emoji="🏠", callback_data=with_owner("menu:main", owner_id))
    b.adjust(1)
    return b.as_markup()


# در اولین ایمپورت، وضعیتِ پشتیبانی را یک‌بار در لاگ ثبت کن (بدونِ شکستنِ ربات).
try:
    buttons_support_check()
except Exception:  # pragma: no cover
    pass
