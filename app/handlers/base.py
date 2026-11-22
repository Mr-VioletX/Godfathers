from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select

from app.database.engine import async_session
from app.models.player import Player
from app.models.hideout import get_hideout, buy_base
from app.keyboards.main_menu import BTN_BASE, WORD_BASE
from app.keyboards.base_menu import base_menu, buy_base_menu
from app.data.upgrades import FEATURES, MAX_FEATURE_LEVEL, upgrade_cost, get_feature, effect_percent_line
from app.data.bases import BASE_TIERS, FIRST_TIER, MAX_TIER, get_tier, final_variant_choices, final_variant_name
from app.data.estates import ESTATES
from app.keyboards.base_menu import final_variant_menu, all_done_menu
from app.utils.ui import ensure_owner, safe_edit, split_owner, safe_answer, click_debounce

router = Router()


async def _get_player(session, tg_user_id: int):
    result = await session.execute(
        select(Player).where(Player.tg_user_id == tg_user_id)
    )
    return result.scalar_one_or_none()


async def _built_estate_keys(session, tg_user_id: int):
    """🆕 مرحله ۲۶: کلیدِ عمارت‌هایی که بازیکن الان ساخته (برای محاسبهِ عمارت‌های دردسترس)."""
    from app.models.estate import Estate
    result = await session.execute(select(Estate.role_key).where(Estate.tg_user_id == tg_user_id))
    return [row[0] for row in result.all()]


# ---------- متن‌ها (بدونِ تغییر از بخش ۶) ----------
def hideout_status_text(player: Player, hideout) -> str:
    """متنِ وضعیتِ تیرِ فعلی + وضعیتِ همه‌ی ویژگی‌ها (قفل/فعال/بازنشده)."""
    tier = get_tier(hideout.base_type)
    display_name = final_variant_name(hideout.final_variant) if hideout.base_type == MAX_TIER else tier['name']
    lines = [
        f"🏰 <b>پایگاه تو: {display_name}</b> (تیر {tier['order']}/۴)",
        f"💵 موجودی: <b>{player.cash:,}</b> دلار",
        f"✨ {tier['perk']}",
        "",
        "<b>ویژگی‌ها:</b>",
    ]
    for t in BASE_TIERS.values():
        feat = FEATURES[t["feature"]]
        lvl = getattr(hideout, f"{feat['key']}_level")
        if t["order"] < tier["order"]:
            state = "🔒 قفل (اثر فعال)"
        elif t["order"] == tier["order"]:
            state = "🔧 قابلِ ارتقا"
        else:
            state = "⬛ باز نشده"
        eff = effect_percent_line(feat['key'], lvl)
        lines.append(f"{feat['name']}: سطح <b>{lvl}</b>/{MAX_FEATURE_LEVEL} — {state}")
        lines.append(f"    ↳ اثر: {eff}")
    lines.append("")
    feat = FEATURES[tier["feature"]]
    current = getattr(hideout, f"{feat['key']}_level")
    if current >= MAX_FEATURE_LEVEL:
        if tier["next"]:
            lines.append("✅ ویژگی مکس شد! می‌توانی به تیرِ بعد ارتقا دهی 👇")
        else:
            # 🆕 مرحله ۲۶.۲: چون انتخابِ عمارتِ هدف همیشه هنگامِ ساختِ خودِ تیرِ چهار انجام می‌شود،
            # final_variant در این نقطه همیشه مقداردهی شده است.
            lines.append(f"🎉 {final_variant_name(hideout.final_variant)} کامل شد! حالا برو در بخشِ «🏛️ عمارت» همون عمارت را بساز.")
    else:
        lines.append("برای ارتقا، دکمه‌ی زیر را بزن 👇")
    return "\n".join(lines)


def buy_menu_text(player: Player) -> str:
    """متنِ خریدِ اولیه برای بازیکنِ بدونِ پایگاه."""
    tier = get_tier(FIRST_TIER)
    return "\n".join([
        "🏰 <b>هنوز پایگاهی نداری!</b>",
        f"💵 موجودی: <b>{player.cash:,}</b> دلار",
        "",
        f"برای شروع، {tier['name']} را بخر و ویژگیِ امضایش (مخفی‌کاری) را ارتقا بده.",
        "بعداً پله‌پله به تیرهای بالاتر (خانه‌ی امن، مقر شهری، و در نهایت یک پایگاهِ تخصصیِ تیرِ ۴) ارتقا می‌دهی.",
        "",
        f"قیمتِ خریدِ اولیه: <b>{tier['up_cost']:,}$</b>",
    ])


# 🆕 مرحله ۲۶.۱: وقتی تمامِ عمارت‌هایِ هرم ساخته شده و دیگه پایگاهی برای ساخت نیست
def all_estates_done_text(built_keys) -> str:
    lines = [
        "🏆 <b>تمام عمارت‌هاتو ساختی!</b>",
        "",
        "دیگه پایگاهِ تخصصیِ جدیدی برای ساخت نیست — تمامِ هرمِ عمارت‌ها کامل شده.",
        "",
        "<b>پایگاه‌هایِ تخصصیِ تیرِ ۴ که تا الان ساختی:</b>",
    ]
    built = set(built_keys)
    for key in ESTATES:
        if key in built:
            lines.append(f"• {final_variant_name(key)}")
    return "\n".join(lines)


# ---------- ساختِ (متن، منو)ی پایگاه بر اساسِ وضعیت ----------
async def render_base_view(session, player: Player, owner_id: int):
    """اگر پایگاه ندارد → منوی خرید یا پیامِ اتمامِ کل هرم؛ اگر دارد → وضعیت + منوی تیر."""
    hideout = await get_hideout(session, player.tg_user_id)
    if hideout is None:
        built = await _built_estate_keys(session, player.tg_user_id)
        if len(set(built)) >= len(ESTATES):
            return all_estates_done_text(built), all_done_menu(owner_id)
        return buy_menu_text(player), buy_base_menu(owner_id)
    return hideout_status_text(player, hideout), base_menu(hideout, owner_id)


# ---------- ورود با دکمه‌ی معمولیِ ربات (چت خصوصی) ----------
@router.message(F.text.in_({BTN_BASE, WORD_BASE}))   # 🆕 مرحله ۱۲: واژهٔ «پایگاه» در گروه هم
async def base_handler(message: Message):
    async with async_session() as session:
        player = await _get_player(session, message.from_user.id)
        if player is None:
            await message.answer("❗ ابتدا /start را بزن تا ثبت‌نام شوی.")
            return
        text, markup = await render_base_view(session, player, message.from_user.id)
    await message.answer(text, reply_markup=markup)


# ---------- ورود از منوی شیشه‌ای (گروه/ربات) — ادیت درجا ----------
@router.callback_query(F.data.startswith("menu:base"))
async def base_menu_cb(callback: CallbackQuery):
    if not await ensure_owner(callback):
        return
    _, owner = split_owner(callback.data)
    owner_id = owner if owner is not None else callback.from_user.id
    async with async_session() as session:
        player = await _get_player(session, callback.from_user.id)
        if player is None:
            await safe_answer(callback, "❗ ابتدا /start را بزن.", show_alert=True)
            return
        text, markup = await render_base_view(session, player, owner_id)
    await safe_edit(callback.message, text, markup)
    await safe_answer(callback)


# ---------- خریدِ اولیه (Covo) ----------
@router.callback_query(F.data.startswith("buybase"))
async def buy_base_callback(callback: CallbackQuery):
    if not await ensure_owner(callback):
        return
    # v1.7.8.19 - کلیک پیاپی فوراً رد می‌شود تا پنل هنگ نکند
    if click_debounce(callback.from_user.id, "buybase"):
        await safe_answer(callback, "⏳ در حالِ پردازش…")
        return
    _, owner = split_owner(callback.data)
    owner_id = owner if owner is not None else callback.from_user.id
    tier = get_tier(FIRST_TIER)
    async with async_session() as session:
        player = await _get_player(session, callback.from_user.id)
        if player is None:
            await safe_answer(callback, "❗ ابتدا /start را بزن.", show_alert=True)
            return
        if await get_hideout(session, callback.from_user.id) is not None:
            await safe_answer(callback, "تو از قبل یک پایگاه داری!", show_alert=True)
            return
        if player.cash < tier["up_cost"]:
            await safe_answer(callback, 
                f"💸 پول کافی نداری! قیمت: {tier['up_cost']:,} دلار", show_alert=True
            )
            return
        player.cash -= tier["up_cost"]
        await buy_base(session, callback.from_user.id, FIRST_TIER)
        from app.data import leveling as _lv
        _xp_res = {}
        try:   # XP for buying first base
            _xp_res = await _lv.grant_xp(session, player, 100, source="base_buy")
        except Exception:
            pass
        await session.commit()
        text, markup = await render_base_view(session, player, owner_id)
    await safe_edit(callback.message, text, markup)
    await safe_answer(callback, f"🎉 پایگاه «{tier['name']}» خریداری شد!" + _lv.xp_note(_xp_res))


# ---------- ارتقای ویژگیِ تیرِ فعلی ----------
@router.callback_query(F.data.startswith("upgrade:"))
async def upgrade_callback(callback: CallbackQuery):
    if not await ensure_owner(callback):
        return
    # v1.7.8.19 - کلیک پیاپی فوراً رد می‌شود تا پنل هنگ نکند
    if click_debounce(callback.from_user.id, "baseup:" + (callback.data or "")):
        await safe_answer(callback, "⏳ در حالِ پردازش…")
        return
    base, owner = split_owner(callback.data)
    owner_id = owner if owner is not None else callback.from_user.id
    key = base.split(":")[1]
    if key == "max":
        await safe_answer(callback, "این ویژگی به حداکثر سطح رسیده!", show_alert=True)
        return

    feature = get_feature(key)
    if feature is None:
        await safe_answer(callback, "ویژگیِ نامعتبر.", show_alert=True)
        return

    async with async_session() as session:
        player = await _get_player(session, callback.from_user.id)
        if player is None:
            await safe_answer(callback, "❗ ابتدا /start را بزن.", show_alert=True)
            return

        hideout = await get_hideout(session, callback.from_user.id)
        if hideout is None:
            await safe_answer(callback, "اول باید یک پایگاه بخری!", show_alert=True)
            return

        tier = get_tier(hideout.base_type)
        if key != tier["feature"]:
            await safe_answer(callback, 
                "🔒 این ویژگی قفل است؛ فقط ویژگیِ تیرِ فعلی‌ات قابلِ ارتقاست.",
                show_alert=True,
            )
            return

        current = getattr(hideout, f"{key}_level")
        if current >= feature["max_level"]:
            await safe_answer(callback, "این ویژگی قبلاً مکس شده!", show_alert=True)
            return

        cost = upgrade_cost(feature["base_cost"], current)
        if player.cash < cost:
            await safe_answer(callback, f"💸 پول کافی نداری! هزینه: {cost:,} دلار", show_alert=True)
            return

        player.cash -= cost
        setattr(hideout, f"{key}_level", current + 1)
        from app.data import leveling as _lv
        _xp_res = {}
        try:   # XP for base feature upgrades
            _xp_res = await _lv.grant_xp(session, player, (40 + 20 * (current + 1)) // 2, source="base_upgrade")
        except Exception:
            pass
        await session.commit()
        text, markup = await render_base_view(session, player, owner_id)

    await safe_edit(callback.message, text, markup)
    await safe_answer(callback, f"✅ {feature['name']} به سطح {current + 1} ارتقا یافت!" + _lv.xp_note(_xp_res))


# ---------- ارتقا به تیرِ بعد ----------
@router.callback_query(F.data.startswith("tierup:"))
async def tierup_callback(callback: CallbackQuery):
    if not await ensure_owner(callback):
        return
    # v1.7.8.19 - کلیک پیاپی فوراً رد می‌شود تا پنل هنگ نکند
    if click_debounce(callback.from_user.id, "basetier:" + (callback.data or "")):
        await safe_answer(callback, "⏳ در حالِ پردازش…")
        return
    base, owner = split_owner(callback.data)
    owner_id = owner if owner is not None else callback.from_user.id
    target = base.split(":")[1]

    async with async_session() as session:
        player = await _get_player(session, callback.from_user.id)
        if player is None:
            await safe_answer(callback, "❗ ابتدا /start را بزن.", show_alert=True)
            return

        hideout = await get_hideout(session, callback.from_user.id)
        if hideout is None:
            await safe_answer(callback, "اول باید یک پایگاه بخری!", show_alert=True)
            return

        tier = get_tier(hideout.base_type)
        nxt_key = tier["next"]
        if nxt_key is None or target != nxt_key:
            await safe_answer(callback, "تیرِ بعدی معتبر نیست.", show_alert=True)
            return

        feat = FEATURES[tier["feature"]]
        current = getattr(hideout, f"{feat['key']}_level")
        if current < MAX_FEATURE_LEVEL:
            await safe_answer(callback, 
                f"اول ویژگیِ «{feat['name']}» را به سطح {MAX_FEATURE_LEVEL} برسان.",
                show_alert=True,
            )
            return

        nxt = get_tier(nxt_key)
        if player.level < nxt["level_req"]:
            await safe_answer(callback, 
                f"⛔ برای این تیر باید حداقل سطح {nxt['level_req']} باشی.",
                show_alert=True,
            )
            return

        if player.cash < nxt["up_cost"]:
            await safe_answer(callback, 
                f"💸 پول کافی نداری! هزینه: {nxt['up_cost']:,} دلار", show_alert=True
            )
            return

        # 🔄 مرحله ۲۶.۳: اگر تیرِ بعدی تیرِ چهار باشد، اول باید یکی از پایگاه‌هایِ تخصصیِ قابلِ ساخت انتخاب شود
        if nxt_key == MAX_TIER:
            built = await _built_estate_keys(session, callback.from_user.id)
            if len(set(built)) >= len(ESTATES):
                await safe_answer(callback, 
                    "🏆 تو همه‌ی عمارت‌ها رو ساختی! دیگه نیازی به ساختِ پایگاهِ تیرِ چهارِ جدید نیست.",
                    show_alert=True,
                )
                return
            choices = final_variant_choices(built)
            if choices:
                text = (
                    "🏗️ <b>انتخابِ پایگاهِ تخصصیِ تیرِ ۴</b>\n\n"
                    f"هزینهِ ساخت: {nxt['up_cost']:,}$\n\n"
                    "طبقِ هرمِ عمارت‌هات، این پایگاه‌هایِ تخصصی الان قابلِ ساخت‌اند. "
                    "هر پایگاه فقط پیش‌نیازِ ساختِ عمارتِ خودش است — یکی رو انتخاب کن:"
                )
                await safe_edit(callback.message, text, final_variant_menu(choices, owner_id))
                await safe_answer(callback)
                return
            # نظراً نباید به اینجا برسیم (چون بالاتر چک شد)، ولی برای اطمینان:
            await safe_answer(callback, "⛔ الان پایگاهِ تخصصیِ جدیدی برایِ ساخت در دسترس نیست.", show_alert=True)
            return

        player.cash -= nxt["up_cost"]
        hideout.base_type = nxt_key
        from app.data import leveling as _lv
        _xp_res = {}
        try:   # XP for base tier upgrades
            _xp_res = await _lv.grant_xp(session, player, min(400, max(50, nxt["up_cost"] // 2000)), source="base_tierup")
        except Exception:
            pass
        await session.commit()
        text, markup = await render_base_view(session, player, owner_id)

    await safe_edit(callback.message, text, markup)
    await safe_answer(callback, f"🏗️ به {nxt['name']} ارتقا یافت!" + _lv.xp_note(_xp_res))


# 🆕 مرحله ۲۶.۲: دکمه/هندلرِ جداگانه‌ی «تغییرِ نام» (namepick:open) به کلی حذف شد؛
# انتخابِ عمارتِ هدف فقط در لحظه‌ی ساختِ خودِ پایگاهِ تیرِ چهار (tierup_callback) رخ می‌دهد.
@router.callback_query(F.data.startswith("tierupname:"))
async def tierupname_callback(callback: CallbackQuery):
    if not await ensure_owner(callback):
        return
    base, owner = split_owner(callback.data)
    owner_id = owner if owner is not None else callback.from_user.id
    variant_key = base.split(":", 1)[1]

    async with async_session() as session:
        player = await _get_player(session, callback.from_user.id)
        if player is None:
            await safe_answer(callback, "❗ ابتدا /start را بزن.", show_alert=True)
            return

        hideout = await get_hideout(session, callback.from_user.id)
        if hideout is None:
            await safe_answer(callback, "اول باید یک پایگاه بخری!", show_alert=True)
            return

        # 🆕 مرحله ۲۶.۲: این کال‌بک فقط برایِ خریدِ خودِ پایگاهِ تیرِ چهار با یک عمارتِ هدفِ
        # مشخص کاربرد دارد (نه تغییرِ نامِ پایگاهی که از قبل تیرِ چهار است).
        if hideout.base_type == MAX_TIER:
            await safe_answer(callback, "⛔ پایگاهت از قبل به تیرِ نهایی رسیده.", show_alert=True)
            return

        built = await _built_estate_keys(session, callback.from_user.id)
        valid_keys = {k for k, _ in final_variant_choices(built)}
        if variant_key not in valid_keys:
            await safe_answer(callback, "این عمارت الان در دسترس نیست.", show_alert=True)
            return

        tier = get_tier(hideout.base_type)
        nxt_key = tier["next"]
        if nxt_key != MAX_TIER:
            await safe_answer(callback, "تیرِ بعدی معتبر نیست.", show_alert=True)
            return
        feat = FEATURES[tier["feature"]]
        current = getattr(hideout, f"{feat['key']}_level")
        if current < MAX_FEATURE_LEVEL:
            await safe_answer(callback, f"اول ویژگیِ «{feat['name']}» را به سطح {MAX_FEATURE_LEVEL} برسان.", show_alert=True)
            return
        nxt = get_tier(nxt_key)
        if player.level < nxt["level_req"]:
            await safe_answer(callback, f"⛔ برای این تیر باید حداقل سطح {nxt['level_req']} باشی.", show_alert=True)
            return
        if player.cash < nxt["up_cost"]:
            await safe_answer(callback, f"💸 پول کافی نداری! هزینه: {nxt['up_cost']:,} دلار", show_alert=True)
            return

        player.cash -= nxt["up_cost"]
        hideout.base_type = nxt_key
        hideout.final_variant = variant_key
        from app.data import leveling as _lv
        _xp_res = {}
        try:   # XP for base tier upgrades (final tier w/ variant)
            _xp_res = await _lv.grant_xp(session, player, min(400, max(50, nxt["up_cost"] // 2000)), source="base_tierup")
        except Exception:
            pass
        await session.commit()
        text, markup = await render_base_view(session, player, owner_id)

    await safe_edit(callback.message, text, markup)
    await safe_answer(callback, f"🎉 {final_variant_name(variant_key)} ساخته شد!" + _lv.xp_note(_xp_res))