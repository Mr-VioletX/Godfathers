# -*- coding: utf-8 -*-
"""🆕 v1.7.6.4 — بیمارستانِ دستی با صفِ درمانِ زمان‌دار.

تاریخچهٔ تغییرات
----------------
v1.7.6.3 — درمانِ خودکار حذف شد و هر نبرد ردیفِ جداگانه گرفت.
v1.7.6.4 — دو باگِ گزارش‌شده برطرف شد:

    باگ ۱) پس از پرداخت، ردیف در جا درمان می‌شد و از فهرست
            «غیب» می‌شد. حالا پرداخت فقط ردیف را واردِ وضعیت
            «🏥 در حالِ درمان» می‌کند و ردیف با تایمرِ باقی‌مانده در
            فهرست دیده می‌شود. نیروها فقط پس از پایانِ زمانِ
            درمان برمی‌گردند (۲ تا ۸ ساعت، تصادفی برای هر ردیف).

    باگ ۲) شفاف نبودنِ درصدِ مجروحان. حالا تعدادِ تلفاتِ پایه
            (base_loss_count) هم ذخیره می‌شود تا در همهٔ متن‌ها
            بنویسیم «از X تلفات، Y مجروح = Z٪» و کاربر خودش بتواند
            راستی‌آزمایی کند که سقفِ ۴۰–۸۰٪ رعایت شده است.

چرخهٔ عمرِ یک ردیف
-------------------
    wounded  ← پایانِ نبرد؛ منتطرِ پرداخت (مهلتِ ۲۴ ساعت)
       │
       ├─ پرداخت → healing ← در حالِ درمان (۲ تا ۸ ساعت)
       │                 │
       │                 └─ پایانِ زمان → healed ← نیروها برگشتند
       │
       └─ اتمامِ مهلت → dead ← نیروها برای همیشه رفتند

نکتهٔ فنی: این مادول عمداً battle_live را import نمی‌کند تا حلقهٔ import درست
نشود؛ battle_live خودش هنگامِ finalize این مادول را صدا می‌زند.
"""
import json
import random
from datetime import datetime, timedelta

from sqlalchemy import select

from app.data import military as MD
from app.models.hospital import HospitalWard
from app.models.player import Player
from app.services import military_service

# مهلتِ پرداخت (ساعت) — پس از آن نیروها می‌میرند.
HEAL_DEADLINE_HOURS = 24
# 🆕 v1.7.6.4 — مدتِ خودِ درمان پس از پرداخت (تصادفی برای هر ردیف)
HEAL_MIN_HOURS = 2
HEAL_MAX_HOURS = 8
# هزینهٔ درمان ≈ ۳۵٪ قیمتِ پایهٔ هر واحد (ارزان‌تر از خریدِ دوباره)
HEAL_COST_PCT = 35
# چند درصد از تلفات «مجروح» حساب می‌شود (بقیه در جا کشته شده‌اند)
WOUNDED_MIN_PCT = 40
WOUNDED_MAX_PCT = 80
# فقط این دسته‌ها درمان/تعمیر می‌شوند (پدافند/موشک مصرفی‌اند)
HEALABLE_CATS = {"soldier", "weapon", "tank", "fighter", "bomber"}
# زیرِ این مقدار (ثانیه) ردیف «فوری» علامت می‌خورد
URGENT_SECONDS = 6 * 3600
# سقفِ ردیف‌هایی که در فهرست نشان داده می‌شود
LIST_LIMIT = 8

# وضعیت‌هایی که هنوز «باز» هستند و باید در فهرست دیده شوند
OPEN_STATUSES = ("wounded", "healing")


# --------------------------- محاسبات ---------------------------
def personnel_only(losses: dict) -> dict:
    """فقط واحدهایی که قابلِ درمان/تعمیرند."""
    out: dict = {}
    for k, n in (losses or {}).items():
        u = MD.get_unit(k) or {}
        if u.get("cat") in HEALABLE_CATS and int(n or 0) > 0:
            out[str(k)] = int(n)
    return out


def cost_of(units: dict) -> int:
    """هزینهٔ درمانِ یک دیکشنری از واحدها."""
    total = 0
    for k, n in (units or {}).items():
        u = MD.get_unit(k) or {}
        total += int(u.get("cost") or 0) * int(n or 0) * HEAL_COST_PCT // 100
    return int(total)


def wounded_from_losses(losses: dict, rng=None) -> dict:
    """۴۰–۸۰٪ از تلفاتِ قابلِ درمان را «مجروح» در نظر می‌گیرد.

    یک درصدِ واحد برای همهٔ انواعِ یگان انتخاب می‌شود تا نسبتِ کلی
    همیشه درونِ بازهٔ ۴۰–۸۰٪ بماند (اگر برای هر یگان جداگانه
    درصد می‌گرفتیم، جمعِ کل می‌توانست از سقف بگذرد.)

    تضمینِ سخت: حتی پس از رندِ کردن، جمعِ خروجی هرگز از
    WOUNDED_MAX_PCT درصدِ جمعِ ورودی بیشتر نمی‌شود.
    """
    src = personnel_only(losses)
    if not src:
        return {}
    r = rng or random
    pct = r.randint(WOUNDED_MIN_PCT, WOUNDED_MAX_PCT)
    total_in = sum(src.values())
    hard_cap = int(total_in * WOUNDED_MAX_PCT // 100)

    out: dict = {}
    for k, n in src.items():
        h = int(int(n) * pct // 100)  # روبه‌پایین تا از سقف رد نکند
        if h > 0:
            out[k] = h

    # اگر روبه‌پایین همه را صفر کرد، دست‌کم یک واحد از بزرگترین گروه
    if not out:
        big = max(src, key=lambda x: src[x])
        out[big] = 1

    # تضمینِ سقف
    while sum(out.values()) > hard_cap and hard_cap > 0:
        big = max(out, key=lambda x: out[x])
        out[big] -= 1
        if out[big] <= 0:
            del out[big]
        if not out:
            break
    return out


def units_of(ward) -> dict:
    """دیکشنریِ واحدهای یک ردیف."""
    if ward is None:
        return {}
    try:
        data = json.loads(getattr(ward, "units_json", None) or "{}")
        return {str(k): int(v) for k, v in data.items() if int(v) > 0}
    except Exception:
        return {}


def units_text(units: dict) -> str:
    if not units:
        return "بدون واحدِ قابلِ درمان"
    parts = []
    for k, n in units.items():
        u = MD.get_unit(k) or {}
        parts.append(f"{u.get('name', k)} ×{int(n):,}")
    return "، ".join(parts)


def wounded_ratio_text(ward) -> str:
    """🆕 v1.7.6.4 — خطِ شفافیت: از چند تلفات، چند تا مجروح شد."""
    base = int(getattr(ward, "base_loss_count", 0) or 0)
    got = int(getattr(ward, "unit_count", 0) or 0)
    if base <= 0:
        return f"🩹 مجروح: <b>{got:,}</b> واحد"
    pct = int(round(got * 100 / base))
    return (
        f"🩹 از <b>{base:,}</b> تلفاتِ قابلِ درمان، "
        f"<b>{got:,}</b> واحد مجروح شد (<b>{pct}٪</b>)"
    )


# --------------------------- زمان ---------------------------
def _expires(ward) -> datetime:
    exp = getattr(ward, "expires_at", None)
    if isinstance(exp, datetime):
        return exp
    created = getattr(ward, "created_at", None)
    if not isinstance(created, datetime):
        created = datetime.utcnow()
    return created + timedelta(hours=HEAL_DEADLINE_HOURS)


def seconds_left(ward, now=None) -> int:
    """ثانیهٔ باقی‌مانده تا اتمامِ مهلتِ پرداخت."""
    now = now or datetime.utcnow()
    try:
        return int((_expires(ward) - now).total_seconds())
    except Exception:
        return 0


def heal_seconds_left(ward, now=None) -> int:
    """🆕 v1.7.6.4 — ثانیهٔ باقی‌مانده تا پایانِ خودِ درمان."""
    now = now or datetime.utcnow()
    until = getattr(ward, "heal_until", None)
    if not isinstance(until, datetime):
        return 0
    try:
        return int((until - now).total_seconds())
    except Exception:
        return 0


def is_urgent(ward, now=None) -> bool:
    left = seconds_left(ward, now)
    return 0 < left <= URGENT_SECONDS


def _hm(seconds: int) -> str:
    hours, minutes = divmod(max(0, int(seconds)) // 60, 60)
    if hours <= 0:
        return f"{minutes} دقیقه"
    return f"{hours} ساعت و {minutes} دقیقه"


def remaining_text(ward, now=None) -> str:
    left = seconds_left(ward, now)
    if left <= 0:
        return "مهلت تمام شد"
    return _hm(left)


def heal_remaining_text(ward, now=None) -> str:
    """🆕 v1.7.6.4 — متنِ تایمرِ درمان."""
    left = heal_seconds_left(ward, now)
    if left <= 0:
        return "آمادهٔ تحویل"
    return _hm(left)


def is_healing(ward) -> bool:
    return str(getattr(ward, "status", "")) == "healing"


def ward_button_text(ward, now=None) -> str:
    """متنِ دکمهٔ یک ردیف در فهرست."""
    count = int(getattr(ward, "unit_count", 0) or 0)
    if is_healing(ward):
        # 🆕 v1.7.6.4 — ردیفِ در‌حال‌درمان دیگر غیب نمی‌شود
        return (
            f"🏥 #{int(ward.id)} · {count:,} واحد · در حالِ درمان · "
            f"{heal_remaining_text(ward, now)}"
        )
    mark = "🔴" if is_urgent(ward, now) else "🩹"
    return (
        f"{mark} #{int(ward.id)} · {count:,} واحد · "
        f"{int(ward.cost or 0):,}$ · {remaining_text(ward, now)}"
    )


# --------------------------- ساختِ ردیف ---------------------------
async def create_ward(
    session,
    uid,
    losses,
    battle_id=None,
    mode="classic",
    opponent_name=None,
    now=None,
):
    """در پایانِ نبرد یک ردیفِ مجروحان می‌سازد.

    اگر چیزی برای درمان نباشد None برمی‌گرداند.
    اگر برای همین نبرد قبلاً ردیفی ساخته شده (finalize دو بار صدا شود)،
    همان ردیفِ قبلی برمی‌گردد و ردیفِ تکراری ساخته نمی‌شود.
    """
    base_src = personnel_only(losses)
    units = wounded_from_losses(losses)
    if not units:
        return None
    uid = int(uid)
    now = now or datetime.utcnow()

    if battle_id:
        dup = (
            await session.execute(
                select(HospitalWard).where(
                    HospitalWard.owner_id == uid,
                    HospitalWard.battle_id == int(battle_id),
                )
            )
        ).scalars().first()
        if dup is not None:
            return dup

    ward = HospitalWard(
        owner_id=uid,
        battle_id=int(battle_id) if battle_id else None,
        mode=str(mode or "classic")[:16],
        opponent_name=(str(opponent_name)[:64] if opponent_name else None),
        units_json=json.dumps(units, ensure_ascii=False),
        unit_count=int(sum(units.values())),
        # 🆕 v1.7.6.4 — تلفاتِ پایه برای شفافیتِ درصد
        base_loss_count=int(sum(base_src.values())),
        cost=cost_of(units),
        status="wounded",
        created_at=now,
        expires_at=now + timedelta(hours=HEAL_DEADLINE_HOURS),
        notified_dead=0,
        notified_healed=0,
        heal_hours=0,
        heal_until=None,
    )
    session.add(ward)
    await session.flush()
    return ward


def battle_end_notice(ward) -> str:
    """پیامِ پایانِ جنگ که به گزارشِ هر طرف چسبانده می‌شود."""
    if ward is None:
        return ""
    return (
        "🏥 <b>پایانِ نبرد — مجروحان</b>\n"
        f"{wounded_ratio_text(ward)}\n"
        f"📋 {units_text(units_of(ward))}\n"
        f"💰 هزینهٔ درمانِ این نبرد: <b>{int(ward.cost or 0):,}$</b>\n"
        f"⏳ فقط <b>{HEAL_DEADLINE_HOURS} ساعت</b> فرصت داری هزینه را بپردازی؛ "
        "پس از آن این نیروها <b>برای همیشه می‌میرند</b>.\n"
        f"🏥 خودِ درمان پس از پرداخت بینِ "
        f"<b>{HEAL_MIN_HOURS} تا {HEAL_MAX_HOURS} ساعت</b> طول می‌کشد.\n"
        "👈 برو به «🎖️ نظامی ← 🏥 بیمارستان / تعمیر» و ردیفِ همین نبرد را پرداخت کن."
    )


def dead_notice(ward) -> str:
    """پیامِ «نیروهایت مردند» پس از اتمامِ مهلت."""
    return (
        "⚰️ <b>نیروهایت مردند</b>\n\n"
        f"مهلتِ {HEAL_DEADLINE_HOURS} ساعتهٔ ردیفِ <b>#{int(ward.id)}</b> "
        f"(نبرد با {ward.opponent_name or '—'}) تمام شد و هزینهٔ درمان پرداخت نشد.\n\n"
        f"🪖 از دست رفته: <b>{int(ward.unit_count or 0):,}</b> واحد\n"
        f"📋 {units_text(units_of(ward))}\n\n"
        "دفعهٔ بعد زودتر به «🎖️ نظامی ← 🏥 بیمارستان / تعمیر» سر بزن."
    )


def healed_notice(ward) -> str:
    """🆕 v1.7.6.4 — پیامِ پایانِ درمان (نیروها برگشتند)."""
    return (
        "✅ <b>درمان تمام شد</b>\n\n"
        f"🏥 ردیفِ <b>#{int(ward.id)}</b> "
        f"(نبرد با {ward.opponent_name or '—'}) با موفقیت درمان شد.\n\n"
        f"🪖 بازگشته به ارتش: <b>{int(ward.unit_count or 0):,}</b> واحد\n"
        f"📋 {units_text(units_of(ward))}\n\n"
        "نیروها الان در سربازخانه آماده‌اند."
    )


# --------------------------- خواندن / جاروب ---------------------------
async def sweep_expired(session, uid=None, now=None):
    """ردیف‌هایی که مهلتِ پرداختشان تمام شده را dead می‌کند.

    خروجی: فهرستِ ردیف‌هایی که همین الان مردند (برای ارسالِ پیام).
    عمداً commit نمی‌کند تا فراخواننده خودش تصمیم بگیرد.

    توجه: ردیف‌های healing هرگز نمی‌میرند — کاربر پولش را داده است.
    """
    now = now or datetime.utcnow()
    q = select(HospitalWard).where(
        HospitalWard.status == "wounded",
        HospitalWard.expires_at <= now,
    )
    if uid is not None:
        q = q.where(HospitalWard.owner_id == int(uid))
    rows = list((await session.execute(q.limit(500))).scalars().all())
    for ward in rows:
        ward.status = "dead"
        ward.resolved_at = now
    if rows:
        await session.flush()
    return rows


async def complete_healing(session, uid=None, now=None):
    """🆕 v1.7.6.4 — ردیف‌هایی که زمانِ درمانشان تمام شده را تحویل می‌دهد.

    نیروها را به ارتش اضافه می‌کند و وضعیت را healed می‌کند.
    خروجی: فهرستِ ردیف‌هایی که همین الان تمام شدند (برای پیام).
    عمداً commit نمی‌کند.
    """
    now = now or datetime.utcnow()
    q = select(HospitalWard).where(
        HospitalWard.status == "healing",
        HospitalWard.heal_until.isnot(None),
        HospitalWard.heal_until <= now,
    )
    if uid is not None:
        q = q.where(HospitalWard.owner_id == int(uid))
    rows = list((await session.execute(q.limit(200))).scalars().all())
    done = []
    for ward in rows:
        units = units_of(ward)
        if units:
            try:
                await military_service.add_units_bulk(session, int(ward.owner_id), units)
            except Exception:
                # اگر افزودن شکست خورد، ردیف را دست‌نخورده بگذار تا دورِ بعد
                continue
        ward.status = "healed"
        ward.resolved_at = now
        done.append(ward)
    if done:
        await session.flush()
    return done


async def list_wards(session, uid, now=None, limit=LIST_LIMIT):
    """ردیف‌های بازِ کاربر (منتطرِ پرداخت + در‌حال‌درمان).

    قبل از خواندن، دو جاروبِ تنبل انجام می‌دهد (اتمامِ مهلت و پایانِ
    درمان)؛ چون روی هاستِ اشتراکی (passenger/webhook) تیکرِ پس‌زمینه
    همیشه زنده نیست.

    ترتیب: اول منتطرِ پرداخت (فوری‌ترین مهلت)، بعد در‌حال‌درمان.
    """
    now = now or datetime.utcnow()
    await sweep_expired(session, uid=uid, now=now)
    await complete_healing(session, uid=uid, now=now)
    rows = (
        await session.execute(
            select(HospitalWard)
            .where(
                HospitalWard.owner_id == int(uid),
                HospitalWard.status.in_(OPEN_STATUSES),
            )
            .order_by(HospitalWard.status.desc(), HospitalWard.expires_at)
            .limit(int(limit))
        )
    ).scalars().all()
    return list(rows)


async def recent_dead(session, uid, limit=3):
    """چند ردیفِ اخیر که مردند (فقط برای نمایش)."""
    rows = (
        await session.execute(
            select(HospitalWard)
            .where(
                HospitalWard.owner_id == int(uid),
                HospitalWard.status == "dead",
            )
            .order_by(HospitalWard.id.desc())
            .limit(int(limit))
        )
    ).scalars().all()
    return list(rows)


async def get_ward(session, uid, ward_id):
    """یک ردیف — فقط اگر مالِ خودِ کاربر باشد."""
    try:
        ward = await session.get(HospitalWard, int(ward_id))
    except Exception:
        return None
    if ward is None or int(ward.owner_id) != int(uid):
        return None
    return ward


async def count_wounded(session, uid, now=None) -> int:
    return len(await list_wards(session, uid, now=now))


# --------------------------- پرداخت و درمان ---------------------------
async def heal_ward(session, uid, ward_id, now=None, rng=None):
    """پرداختِ هزینهٔ یک ردیف و شروعِ صفِ درمان.

    🆕 v1.7.6.4 — دیگر در جا نیرو برنمی‌گرداند. فقط پول می‌گیرد و
    ردیف را واردِ وضعیت healing با تایمرِ ۲ تا ۸ ساعته می‌کند.

    خروجی: (ok, پیام)
    """
    now = now or datetime.utcnow()
    uid = int(uid)
    ward = await get_ward(session, uid, ward_id)
    if ward is None:
        return False, "❌ این ردیف پیدا نشد."
    if str(ward.status) == "healing":
        return False, (
            f"🏥 این ردیف الان <b>در حالِ درمان</b> است.\n"
            f"⏳ زمانِ باقی‌مانده: <b>{heal_remaining_text(ward, now)}</b>\n"
            "پس از پایان، نیروها خودبه‌خود به ارتش بازمی‌گردند."
        )
    if str(ward.status) == "healed":
        return False, "✅ این ردیف قبلاً درمان شده است."
    if str(ward.status) == "dead":
        return False, "⚰️ مهلتِ این ردیف تمام شده و نیروها از دست رفته‌اند."
    if seconds_left(ward, now) <= 0:
        ward.status = "dead"
        ward.resolved_at = now
        await session.flush()
        return False, (
            f"⚰️ دیر شد! مهلتِ {HEAL_DEADLINE_HOURS} ساعتهٔ این ردیف تمام شد و "
            f"{int(ward.unit_count or 0):,} واحد از دست رفت."
        )

    units = units_of(ward)
    if not units:
        ward.status = "healed"
        ward.resolved_at = now
        await session.flush()
        return False, "چیزی برای درمان در این ردیف نیست."

    cost = int(ward.cost or 0)
    player = (
        await session.execute(select(Player).where(Player.tg_user_id == uid))
    ).scalar_one_or_none()
    if player is None:
        return False, "اول /start را بزن."
    have = int(player.cash or 0)
    if have < cost:
        return False, (
            f"💸 هزینهٔ درمانِ این ردیف <b>{cost:,}$</b> است، "
            f"اما موجودی‌ات <b>{have:,}$</b> است.\n"
            f"⏳ مهلتِ باقی‌مانده: {remaining_text(ward, now)}"
        )

    # پول را بگیر و صفِ درمان را باز کن — نیروها هنوز برنمی‌گردند.
    r = rng or random
    hours = r.randint(HEAL_MIN_HOURS, HEAL_MAX_HOURS)
    player.cash = have - cost
    ward.status = "healing"
    ward.heal_hours = int(hours)
    ward.heal_until = now + timedelta(hours=hours)
    ward.notified_healed = 0
    await session.flush()
    return True, (
        f"🏥 ردیفِ <b>#{int(ward.id)}</b> واردِ <b>صفِ درمان</b> شد.\n"
        f"🩹 در درمان: <b>{int(ward.unit_count or 0):,}</b> واحد\n"
        f"📋 {units_text(units)}\n"
        f"💰 پرداختی: <b>{cost:,}$</b>\n"
        f"💵 موجودی: <b>{int(player.cash or 0):,}$</b>\n\n"
        f"⏳ مدتِ درمان: <b>{hours} ساعت</b>\n"
        "🔔 وقتی تمام شود خبرت می‌دهم و نیروها به ارتش بازمی‌گردند.\n"
        "👁 تا آن موقع همین ردیف را با تایمر در فهرستِ بیمارستان می‌بینی."
    )
