from datetime import datetime, timedelta

from aiogram import BaseMiddleware, Bot
from aiogram.types import Message
from sqlalchemy import select, update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.database.engine import async_session
from app.data.profile import (
    announce_idle_minutes,   # 🆕 مرحله ۳۰
    announce_in_group,       # 🆕 مرحله ۳۰
    is_group_announce_enabled,
    load_announce,
    load_privacy,
)
from app.models.group_membership import GroupMembership
from app.models.player import Player

# 🆕 مرحله ۳۰ — این عدد دیگر ثابت نیست: هر کاربر از بخشِ «اعلام آنلاین»
# فاصلهٔ دلخواهِ خودش را انتخاب می‌کند. این فقط پیش‌فرضِ پشتیبان است.
ANNOUNCE_COOLDOWN = timedelta(hours=3)


class TrackingMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: Message, data: dict):
        # 🆕 مرحله ۳۱ — سقفِ نخ‌ها را یک‌بار نصب کن (رفعِ can't start new thread)
        try:
            from app.utils import runtime
            runtime.install()
        except Exception:
            pass
        if isinstance(event, Message) and event.from_user:
            # 🆕 مرحله ۲۱ — کاربرانِ بن‌شده: ربات هیچ واکنشی نشان نمی‌دهد (drop)
            try:
                from app.services.admin_service import BANNED_IDS
                if event.from_user.id in BANNED_IDS:
                    return
            except Exception:
                pass
            chat_type = event.chat.type
            if chat_type in ("group", "supergroup"):
                await self._track_group(event)
                # 🆕 مرحله ۳۰ — فعالیت درِ گروه هم می‌تواند اعلامِ آنلاین را راه بیندازد
                await self._maybe_announce(event, data, from_group=True)
            elif chat_type == "private":
                await self._maybe_announce(event, data)
            # 🆕 مرحله ۳۰ — ارزیابیِ خودکارِ القاب پس از هر کنش (با خفه‌کنِ زمانی)
            await self._check_titles(event)
            # 🆕 مرحله ۳۱ — اخبارِ روزانه روی هاستِ وب‌هوکی (بدونِ cron هم کار کند)
            await self._maybe_schedule(data)
        return await handler(event, data)

    @staticmethod
    async def _maybe_schedule(data: dict) -> None:
        """زمان‌بندِ فرصت‌طلب: فقط هر چند دقیقه یک‌بار واقعاً کاری می‌کند."""
        try:
            bot = data.get("bot")
            if bot is None:
                return
            from app.services import host_scheduler
            await host_scheduler.maybe_run(bot)
        except Exception:
            pass

    @staticmethod
    async def _check_titles(event: Message) -> None:
        """v1.7.6 — فقط صف تأیید؛ تبریک فقط بعد از تأیید ادمین اصلی."""
        try:
            from app.services import title_hook

            async with async_session() as session:
                queued = await title_hook.check(session, event.from_user.id)
            if not queued:
                return
            names = []
            for t in queued:
                if isinstance(t, dict) and t.get("name"):
                    names.append(str(t["name"]))
            if names:
                try:
                    msg = "📝 درخواستِ لقب برای تأیید ادمین ثبت شد:\n" + "\n".join(f"• {n}" for n in names[:5]) + "\n\n⏳ تا تأیید ادمین اصلی، لقب فعال نمی‌شود."
                    await event.answer(msg)
                except Exception:
                    pass
            try:
                from app.config import MAIN_ADMIN_ID
                from app.data import titles as TDATA
                if MAIN_ADMIN_ID:
                    lines = ["🎖️ <b>صفِ لقب — درخواستِ جدید</b>", f"👤 <code>{event.from_user.id}</code>", ""]
                    for t in queued:
                        nm = t.get("name") if isinstance(t, dict) else None
                        key = t.get("key") if isinstance(t, dict) else None
                        if not nm and key:
                            nm = (TDATA.get_title(key) or {}).get("name", key)
                        lines.append(f"• {nm or key or '?'}")
                    lines.append("")
                    lines.append("از ادمین‌مود → القاب → صف تایید لقب بررسی کن.")
                    await event.bot.send_message(int(MAIN_ADMIN_ID), "\n".join(lines))
            except Exception:
                pass
        except Exception:
            pass

    async def _track_group(self, event: Message) -> None:
        async with async_session() as session:
            stmt = (
                sqlite_insert(GroupMembership)
                .values(
                    tg_user_id=event.from_user.id,
                    chat_id=event.chat.id,
                    chat_title=event.chat.title,
                )
                .on_conflict_do_update(
                    index_elements=["tg_user_id", "chat_id"],
                    set_={"chat_title": event.chat.title},
                )
            )
            await session.execute(stmt)
            # همگام‌سازیِ یوزرنیم (برای هدف‌گیریِ جاسوسی) — برای کاربرانِ ثبت‌شده
            await session.execute(
                update(Player)
                .where(Player.tg_user_id == event.from_user.id)
                .values(username=event.from_user.username)
            )
            await session.commit()

    async def _maybe_announce(
        self, event: Message, data: dict, from_group: bool = False
    ) -> None:
        bot: Bot = data["bot"]
        now = datetime.utcnow()
        async with async_session() as session:
            result = await session.execute(
                select(Player).where(Player.tg_user_id == event.from_user.id)
            )
            player = result.scalar_one_or_none()
            if not player:
                return
            # Stage 27 (performance): cheap checks first, single commit at the end.
            announce = load_announce(player.announce_settings)
            # 🆕 مرحله ۳۰ — فاصلهٔ اعلام را خودِ کاربر تعیین می‌کند:
            # اگر از آخرین دستورِ او بیش از idle_minutes گذشته باشد، بارِ بعدی که
            # درِ ربات یا گروه چیزی بنویسد ← اعلامِ آنلاین می‌شود.
            idle_gap = timedelta(minutes=announce_idle_minutes(announce))
            was_away = (player.last_seen is None) or (now - player.last_seen >= idle_gap)
            allowed_source = (not from_group) or announce_in_group(announce)
            fresh_announce = not (
                player.last_announce_at
                and now - player.last_announce_at < idle_gap
            )
            should_try = (
                bool(announce.get("enabled", True))
                and allowed_source
                and was_away
                and fresh_announce
            )
            if not should_try:
                # only the lightweight presence fields are touched, one commit
                player.last_seen = now
                if player.username != event.from_user.username:
                    player.username = event.from_user.username
                await session.commit()
                return
            if player.username != event.from_user.username:
                player.username = event.from_user.username
                await session.commit()
            player.last_seen = now   # 🆕 مرحله ۱۳.۶ — به‌روزرسانیِ آخرین فعالیت (تشخیصِ آنلاین در چت‌مود)
            await session.commit()
            _active_title = None   # 🆕 مرحله ۳۰
            # Stage 27: only players with an active title broadcast their online status.
            # This query runs only when an announcement is actually due (not on every message).
            try:
                from app.services import titles as _titles

                _active_title = await _titles.display_title(session, player.tg_user_id)
                if not _active_title:
                    return
            except Exception:
                pass

            groups = await session.execute(
                select(GroupMembership).where(
                    GroupMembership.tg_user_id == event.from_user.id
                )
            )
            chat_ids = [m.chat_id for m in groups.scalars().all()]

            player.last_announce_at = now
            privacy = load_privacy(player.privacy_settings)
            banner = self._banner(player, privacy, _active_title)
            await session.commit()

        for chat_id in chat_ids:
            # فقط گروه‌هایی که کاربر در تنظیمات پروفایل روشن گذاشته
            if not is_group_announce_enabled(announce, chat_id):
                continue
            try:
                await bot.send_message(chat_id, banner)
            except Exception:
                # ربات ممکن است از گروه حذف شده باشد؛ بی‌صدا رد کن.
                pass

    @staticmethod
    def _banner(player: Player, privacy: dict, active_title: str | None = None) -> str:
        parts = [f"🟢 <b>{player.name}</b> آنلاین شد!"]
        _title = active_title or player.custom_title   # 🆕 مرحله ۳۰
        if _title and privacy.get("title", True):
            parts.append(f"🎖️ {_title}")
        if privacy.get("level", True):
            parts.append(f"⭐ سطح {player.level}")
        return "  —  ".join(parts)