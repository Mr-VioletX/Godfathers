# -*- coding: utf-8 -*-
"""v1.7.9.6 — سرویس بازار نقل‌وانتقال فوتبال (F3): خرید عادی با پول بازی + مزایده‌ی
بازیکن تک‌نسخه‌ای با پول واقعی + صف پرداخت ۳۰ دقیقه + انتقال/دادن/گرفتن توسط ادمین.
"""
from __future__ import annotations

import json
import random
import uuid
from datetime import datetime, timedelta

from sqlalchemy import select

from app.data import football_players as FP
from app.models.football import FootballClub, FootballPlayerCard
from app.models.football_market import FootballMarketSale, FootballUniqueOwner

AUCTION_HOURS = 2                 # مهلت مزایده
PAYMENT_MINUTES = 30              # مهلت پرداخت هر نفر
COMMON_MIN_PRICE = 100_000_000    # کمترین قیمت بازیکن عادی (دلار بازی)


def _code() -> str:
    return uuid.uuid4().hex[:10].upper()


# --------------------------- مالکیت بازیکن تک ---------------------------
async def owner_of(session, template_key: str) -> int | None:
    row = await session.get(FootballUniqueOwner, template_key)
    return int(row.owner_id) if row else None


async def is_sold(session, template_key: str) -> bool:
    return (await session.get(FootballUniqueOwner, template_key)) is not None


async def has_active_sale(session, template_key: str) -> FootballMarketSale | None:
    return (await session.execute(
        select(FootballMarketSale).where(
            FootballMarketSale.template_key == template_key,
            FootballMarketSale.status.in_(["auction", "awaiting_admin", "awaiting_payment", "receipt_check"]),
        ).order_by(FootballMarketSale.id.desc())
    )).scalars().first()


async def effective_price(session, template_key: str) -> int:
    """قیمت مؤثر = override ادمین یا پیش‌فرض کاتالوگ."""
    p = FP.get(template_key)
    if p is None:
        return 0
    try:
        from app.services import admin_service as adm
        raw = await adm.get_setting(session, f"player_price:{template_key}")
        if raw is not None and str(raw).isdigit():
            return int(raw)
    except Exception:
        pass
    return int(p["price"])


async def set_price_override(session, template_key: str, price: int) -> None:
    from app.services import admin_service as adm
    await adm.set_setting(session, f"player_price:{template_key}", str(int(price)), commit=False)
    await session.flush()


# --------------------------- خرید عادی (پول بازی، غیرتک) ---------------------------
async def buy_common(session, uid: int, club: FootballClub, template_key: str, player) -> tuple[bool, str]:
    p = FP.get(template_key)
    if p is None:
        return False, "بازیکن نامعتبر."
    if p["currency"] != "game":
        return False, "این بازیکن با پول واقعی است — از بخش مزایده."
    price = max(COMMON_MIN_PRICE, await effective_price(session, template_key))
    cash = int(getattr(player, "cash", 0) or 0)
    if cash < price:
        return False, f"موجودی کافی نیست. قیمت: {price:,}$ (موجودی: {cash:,}$)"
    player.cash = cash - price
    card = FootballPlayerCard(
        club_id=club.id, owner_id=int(uid), template_key=template_key,
        name=p["name"], pos=p["pos"], tier=p["tier"], base_power=p["power"],
        tracking_code=_code(), acquired_via="shop",
    )
    session.add(card)
    await session.flush()
    return True, f"✅ <b>{p['name']}</b> به باشگاهت پیوست (+💪{p['power']:,}). هزینه: {price:,}$"


# --------------------------- مزایده‌ی بازیکن تک (پول واقعی) ---------------------------
def _queue(sale: FootballMarketSale) -> list:
    try:
        return json.loads(sale.queue_json or "[]")
    except Exception:
        return []


def _save_queue(sale: FootballMarketSale, q: list) -> None:
    sale.queue_json = json.dumps(q, ensure_ascii=False)


async def start_auction(session, uid: int, template_key: str, initial_bid: int) -> tuple[bool, str, FootballMarketSale | None]:
    p = FP.get(template_key)
    if p is None or p["currency"] != "toman" or p.get("sale_mode") != "auction":
        return False, "این بازیکن تومانی/مزایده‌ای نیست.", None
    if await is_sold(session, template_key):
        return False, "این بازیکن فروخته شده — فقط با «درخواست به دارنده» قابل انتقال است.", None
    if await has_active_sale(session, template_key):
        return False, "برای این بازیکن همین حالا یک مزایده در جریان است — با «پیشنهاد بالاتر» شرکت کن.", None
    base_price = await effective_price(session, template_key)
    if initial_bid < base_price:
        return False, f"کمترین پیشنهاد {base_price:,} تومان است.", None
    sale = FootballMarketSale(
        template_key=template_key, player_name=p["name"], status="auction",
        highest_bid=int(initial_bid), highest_bidder=int(uid),
        auction_ends_at=datetime.utcnow() + timedelta(hours=AUCTION_HOURS),
        tracking_code=_code(),
    )
    _save_queue(sale, [{"uid": int(uid), "bid": int(initial_bid)}])
    sale.current_candidate = int(uid)
    session.add(sale)
    await session.flush()
    return True, sale.tracking_code, sale


async def place_bid(session, uid: int, sale: FootballMarketSale, amount: int) -> tuple[bool, str]:
    if sale.status != "auction":
        return False, "مزایده بسته شده."
    if datetime.utcnow() >= sale.auction_ends_at:
        return False, "مهلت مزایده تمام شده."
    amount = int(amount)
    if amount <= int(sale.highest_bid or 0):
        return False, f"پیشنهاد باید بیشتر از {int(sale.highest_bid):,} تومان باشد."
    q = _queue(sale)
    q = [b for b in q if b["uid"] != int(uid)]  # پیشنهاد قبلیِ همین کاربر حذف
    q.append({"uid": int(uid), "bid": amount})
    q.sort(key=lambda b: b["bid"], reverse=True)
    _save_queue(sale, q)
    sale.highest_bid = amount
    sale.highest_bidder = int(uid)
    sale.current_candidate = int(uid)
    await session.flush()
    return True, f"✅ پیشنهاد {amount:,} تومان ثبت شد — تو الان بالاترین پیشنهاد را داری."


# --------------------------- تیک مزایده (تایمر) ---------------------------
async def tick(session, bot) -> None:
    """پایان مزایده‌های سررسیدشده + پیشبرد صف پرداخت ۳۰ دقیقه‌ای."""
    now = datetime.utcnow()
    # ۱) پایان مزایده‌ها
    ended = list((await session.execute(
        select(FootballMarketSale).where(
            FootballMarketSale.status == "auction",
            FootballMarketSale.auction_ends_at <= now,
        )
    )).scalars().all())
    for sale in ended:
        q = _queue(sale)
        if not q:
            sale.status = "cancelled"
            continue
        sale.status = "awaiting_admin"   # بالاترین پیشنهاد → منتظر تأیید ادمین
        sale.current_candidate = q[0]["uid"]
        sale.highest_bid = q[0]["bid"]
        sale.highest_bidder = q[0]["uid"]
        if bot is not None:
            try:
                from app.config import MAIN_ADMIN_ID
                if MAIN_ADMIN_ID:
                    await bot.send_message(int(MAIN_ADMIN_ID), f"⚽ مزایده‌ی <b>{sale.player_name}</b> تمام شد — بالاترین پیشنهاد {sale.highest_bid:,} تومان (کاربر <code>{sale.highest_bidder}</code>). از «خریدهای ورزشی» تأیید کن.")
            except Exception:
                pass
    # ۲) سررسید پرداخت نفرِ جلو → نفر بعدی
    waiting = list((await session.execute(
        select(FootballMarketSale).where(
            FootballMarketSale.status == "awaiting_payment",
            FootballMarketSale.payment_deadline.is_not(None),
            FootballMarketSale.payment_deadline <= now,
        )
    )).scalars().all())
    for sale in waiting:
        await _advance_queue(session, sale, bot, reason="⏰ مهلت پرداخت تمام شد")
    await session.flush()


async def _advance_queue(session, sale: FootballMarketSale, bot, reason: str) -> None:
    """نفرِ جلو حذف و نفرِ بعدی با ۳۰ دقیقه فعال می‌شود؛ اگر کسی نماند → برای امروز لغو."""
    q = _queue(sale)
    if sale.current_candidate is not None:
        q = [b for b in q if b["uid"] != int(sale.current_candidate)]
    if not q:
        sale.status = "cancelled"
        _save_queue(sale, q)
        if bot is not None:
            try:
                from app.config import MAIN_ADMIN_ID
                if MAIN_ADMIN_ID:
                    await bot.send_message(int(MAIN_ADMIN_ID), f"⚽ فروش <b>{sale.player_name}</b> هیچ خریداری نماند — می‌توانی برای امروز لغو و به فردا موکول کنی.")
            except Exception:
                pass
        return
    _save_queue(sale, q)
    nxt = q[0]
    sale.current_candidate = nxt["uid"]
    sale.highest_bid = nxt["bid"]
    sale.highest_bidder = nxt["uid"]
    sale.status = "awaiting_payment"
    sale.payment_deadline = datetime.utcnow() + timedelta(minutes=PAYMENT_MINUTES)
    sale.receipt_file_id = None
    if bot is not None:
        try:
            await bot.send_message(nxt["uid"], f"⏳ نوبت تو برای خرید <b>{sale.player_name}</b> رسید! ({reason}) مبلغ {nxt['bid']:,} تومان — {PAYMENT_MINUTES} دقیقه فرصت پرداخت و ارسال رسید داری.")
        except Exception:
            pass


# --------------------------- ادمین: تأیید/رسید/لغو ---------------------------
async def admin_approve(session, sale: FootballMarketSale) -> None:
    """تأیید ادمین روی بالاترین پیشنهاد → نفر جلو ۳۰ دقیقه برای پرداخت."""
    sale.status = "awaiting_payment"
    sale.payment_deadline = datetime.utcnow() + timedelta(minutes=PAYMENT_MINUTES)
    await session.flush()


async def admin_confirm_receipt(session, sale: FootballMarketSale, uid_winner: int) -> tuple[bool, str]:
    """تأیید رسید → بازیکن به برنده منتقل می‌شود."""
    p = FP.get(sale.template_key)
    legacy_spec = FP.legacy_card_spec(sale.template_key) if p is None else None
    if p is None and legacy_spec is None:
        return False, "بازیکن نامعتبر."
    club = (await session.execute(select(FootballClub).where(FootballClub.owner_id == int(uid_winner)))).scalar_one_or_none()
    if club is None:
        return False, "برنده باشگاهی ندارد."
    if p is not None:
        card_name, card_pos, card_tier, card_power = p["name"], p["pos"], p["tier"], p["power"]
    else:
        card_pos, card_tier, card_power = legacy_spec
        card_name = sale.player_name or f"Legacy Player {sale.template_key.upper()}"
    card = FootballPlayerCard(
        club_id=club.id, owner_id=int(uid_winner), template_key=sale.template_key,
        name=card_name, pos=card_pos, tier=card_tier, base_power=card_power,
        tracking_code=sale.tracking_code, acquired_via="shop",
    )
    session.add(card)
    await session.flush()
    session.add(FootballUniqueOwner(
        template_key=sale.template_key, owner_id=int(uid_winner), card_id=card.id,
        price_paid=int(sale.highest_bid or 0), tracking_code=sale.tracking_code,
    ))
    sale.status = "done"
    await session.flush()
    return True, club.name


async def admin_reject_receipt(session, sale: FootballMarketSale, bot) -> None:
    """رسید رد شد → نفر بعدی با ۳۰ دقیقه."""
    await _advance_queue(session, sale, bot, reason="❌ رسید تأیید نشد")


async def admin_cancel_today(session, sale: FootballMarketSale) -> None:
    sale.status = "cancelled"
    await session.flush()


# --------------------------- ادمین: دادن/گرفتن/انتقال ---------------------------
async def admin_give_player(session, uid: int, template_key: str, remove_from_shop: bool = True) -> tuple[bool, str]:
    """دادن بازیکن به کاربر. اگر تک است و remove_from_shop=False → از لیست خرید حذف نمی‌شود (مثل لقب)."""
    p = FP.get(template_key)
    if p is None:
        return False, "بازیکن نامعتبر."
    club = (await session.execute(select(FootballClub).where(FootballClub.owner_id == int(uid)))).scalar_one_or_none()
    if club is None:
        return False, "کاربر باشگاهی ندارد."
    card = FootballPlayerCard(
        club_id=club.id, owner_id=int(uid), template_key=template_key,
        name=p["name"], pos=p["pos"], tier=p["tier"], base_power=p["power"],
        tracking_code=_code(), acquired_via="admin",
    )
    session.add(card)
    await session.flush()
    if p.get("unique") and remove_from_shop:
        # تک → مالکیت ثبت می‌شود (از لیست خرید حذف)
        if not await is_sold(session, template_key):
            session.add(FootballUniqueOwner(template_key=template_key, owner_id=int(uid), card_id=card.id, tracking_code=card.tracking_code))
            await session.flush()
    return True, f"✅ {p['name']} به کاربر {uid} داده شد."


async def admin_take_player(session, uid: int, card_id: int) -> tuple[bool, str]:
    card = await session.get(FootballPlayerCard, int(card_id))
    if card is None or int(card.owner_id) != int(uid):
        return False, "کارت پیدا نشد یا مال این کاربر نیست."
    name = card.name
    tkey = card.template_key
    cid = card.id
    await session.delete(card)
    # فقط اگه همین کارت، کارتِ مالکِ بازار بود، مالکیت آزاد شود (نسخهٔ اهداشده به بازار دست نمی‌زند)
    own = await session.get(FootballUniqueOwner, tkey)
    if own is not None and int(getattr(own, "card_id", 0) or 0) == int(cid):
        await session.delete(own)
    await session.flush()
    return True, f"✅ {name} از کاربر {uid} گرفته شد."


async def transfer_player(session, from_uid: int, card_id: int, to_uid: int) -> tuple[bool, str]:
    """انتقال بازیکن به کاربر هدف (با تأیید ادمین در هندلر)."""
    card = await session.get(FootballPlayerCard, int(card_id))
    if card is None or int(card.owner_id) != int(from_uid):
        return False, "کارت پیدا نشد یا مال تو نیست."
    to_club = (await session.execute(select(FootballClub).where(FootballClub.owner_id == int(to_uid)))).scalar_one_or_none()
    if to_club is None:
        return False, "کاربر هدف باشگاهی ندارد."
    card.owner_id = int(to_uid)
    card.club_id = to_club.id
    own = await session.get(FootballUniqueOwner, card.template_key)
    if own is not None and int(getattr(own, "card_id", 0) or 0) == int(card.id):
        own.owner_id = int(to_uid)
    await session.flush()
    return True, card.name


async def purchase_history(session, uid: int, limit: int = 15) -> list:
    """تاریخچه‌ی خرید/مالکیت بازیکنانِ کاربر (با کد پیگیری)."""
    return list((await session.execute(
        select(FootballPlayerCard).where(FootballPlayerCard.owner_id == int(uid))
        .order_by(FootballPlayerCard.created_at.desc()).limit(limit)
    )).scalars().all())


# --------------------------- حلقه‌ی تایمر (Polling/VPS) ---------------------------
import asyncio as _asyncio
from app.database.engine import async_session as _async_session


async def market_loop(bot) -> None:
    """هر ۶۰ ثانیه: پایان مزایده‌ها + پیشبرد صف پرداخت ۳۰ دقیقه‌ای."""
    while True:
        try:
            async with _async_session() as session:
                await tick(session, bot)
                await session.commit()
        except Exception:
            pass
        await _asyncio.sleep(60)
