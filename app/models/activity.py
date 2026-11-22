from datetime import datetime
from sqlalchemy import BigInteger, DateTime, Integer, String, Text, func, Index
from sqlalchemy.orm import Mapped, mapped_column
from app.database.base import Base
class PlayerActivityLog(Base):
    __tablename__='player_activity_logs'
    id: Mapped[int]=mapped_column(Integer, primary_key=True, autoincrement=True)
    player_id: Mapped[int|None]=mapped_column(Integer, nullable=True, index=True)
    tg_user_id: Mapped[int|None]=mapped_column(BigInteger, nullable=True, index=True)
    action_key: Mapped[str]=mapped_column(String(80), index=True)
    title: Mapped[str]=mapped_column(String(255))
    amount: Mapped[int]=mapped_column(BigInteger, default=0)
    before_value: Mapped[int|None]=mapped_column(BigInteger, nullable=True)
    after_value: Mapped[int|None]=mapped_column(BigInteger, nullable=True)
    meta: Mapped[str|None]=mapped_column(Text, nullable=True)
    created_at: Mapped[datetime]=mapped_column(DateTime, server_default=func.now(), index=True)
Index('idx_activity_player_created', PlayerActivityLog.player_id, PlayerActivityLog.created_at)
