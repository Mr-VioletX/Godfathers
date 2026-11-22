from sqlalchemy import select, or_
from app.models.admin import GameRestriction


async def is_tester(session, uid: int) -> bool:
    """🆕 v1.7.9.6 — آیا این کاربر «تست‌کننده» است؟ (دسترسی به بخش‌های خاموشِ سراسری)"""
    try:
        import json
        from app.services import admin_service as adm
        raw = await adm.get_setting(session, "ctrl:testers")
        return int(uid) in {int(x) for x in json.loads(raw or "[]")}
    except Exception:
        return False


async def blocked(session, uid: int, section: str) -> bool:
    rule = await session.scalar(select(GameRestriction).where(GameRestriction.active == True, GameRestriction.section == section, or_(GameRestriction.tg_user_id == None, GameRestriction.tg_user_id == int(uid))).order_by(GameRestriction.tg_user_id.desc(), GameRestriction.id.desc()))
    if rule is None:
        return False
    # 🆕 v1.7.9.6 — تست‌کنندگان بخش‌های خاموشِ سراسری را می‌بینند؛ بنِ کاربری (scope:sel) همچنان اعمال می‌شود
    if rule.tg_user_id is None and await is_tester(session, uid):
        return False
    return True
