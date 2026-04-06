from datetime import datetime
from typing import Optional
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, DateTime, Text, Boolean, Integer, select
from loguru import logger


class Base(DeclarativeBase):
    pass


class ProcessedMessage(Base):
    __tablename__ = "processed_messages"
    id: Mapped[int]    = mapped_column(Integer, primary_key=True, autoincrement=True)
    message_id: Mapped[int] = mapped_column(Integer, nullable=False, unique=True, index=True)
    channel: Mapped[str]    = mapped_column(String(128))
    original_text: Mapped[Optional[str]]   = mapped_column(Text, nullable=True)
    translated_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_relevant: Mapped[bool]  = mapped_column(Boolean, default=True)
    posted: Mapped[bool]       = mapped_column(Boolean, default=False)
    posted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    error: Mapped[Optional[str]]       = mapped_column(Text, nullable=True)
    skip_reason: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Database:
    def __init__(self, url: str) -> None:
        self._engine   = create_async_engine(url, echo=False, pool_pre_ping=True)
        self._sessions = async_sessionmaker(self._engine, class_=AsyncSession, expire_on_commit=False)

    async def init(self) -> None:
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("✅ Database ready")

    async def close(self) -> None:
        await self._engine.dispose()

    async def is_processed(self, message_id: int) -> bool:
        async with self._sessions() as s:
            r = await s.execute(select(ProcessedMessage).where(ProcessedMessage.message_id == message_id))
            return r.scalar_one_or_none() is not None

    async def save(
        self, *, message_id: int, channel: str,
        original_text: str = "", translated_text: str = "",
        is_relevant: bool = True, posted: bool = False,
        error: Optional[str] = None, skip_reason: Optional[str] = None,
    ) -> None:
        # posted ni har doim bool ga aylantiramiz
        posted = bool(posted)
        async with self._sessions() as s:
            exists = await s.execute(select(ProcessedMessage).where(ProcessedMessage.message_id == message_id))
            if exists.scalar_one_or_none():
                return
            s.add(ProcessedMessage(
                message_id=message_id, channel=channel,
                original_text=(original_text or "")[:4000],
                translated_text=(translated_text or "")[:4000],
                is_relevant=bool(is_relevant),
                posted=bool(posted),
                posted_at=datetime.utcnow() if posted else None,
                error=error, skip_reason=skip_reason,
            ))
            await s.commit()

    async def get_stats(self) -> dict:
        async with self._sessions() as s:
            rows = (await s.execute(select(ProcessedMessage))).scalars().all()
        return {"jami": len(rows), "joylandi": sum(1 for r in rows if r.posted),
                "skip": sum(1 for r in rows if r.skip_reason), "xato": sum(1 for r in rows if r.error)}