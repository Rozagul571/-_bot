import asyncio
from typing import Optional
from telethon import TelegramClient
from telethon.errors import (
    FloodWaitError, ChatWriteForbiddenError,
    PeerIdInvalidError, UserBannedInChannelError,
)
from loguru import logger
from core.config import settings


def build_post(ai_body: str) -> str:
    """Faqat AI matni + kanal nomi. Link yo'q."""
    return f"{ai_body.strip()}\n\n📌 {settings.TARGET_CHANNEL}"

class ChannelPoster:
    def __init__(self, api_id: int, api_hash: str, bot_token: str, target_channel: str) -> None:
        self._target    = target_channel
        self._bot_token = bot_token
        self._client    = TelegramClient(
            session=settings.bot_session(),
            api_id=api_id,
            api_hash=api_hash,
        )
        self._started = False

    async def start(self) -> None:
        if not self._started:
            await self._client.start(bot_token=self._bot_token)
            self._started = True
            logger.info("Bot ulandi.")

    async def stop(self) -> None:
        if self._started:
            await self._client.disconnect()
            self._started = False

    async def post(self, ai_body: str, link: Optional[str] = None) -> bool:
        """Link parametri qabul qilinadi lekin postga qo'shilmaydi."""
        await self.start()
        text = build_post(ai_body)

        for attempt in range(1, settings.MAX_RETRIES + 1):
            try:
                await self._client.send_message(
                    entity=self._target,
                    message=text,
                    parse_mode="markdown",
                    link_preview=False,
                )
                logger.info(f"Post yuborildi -> {self._target}")
                return True
            except FloodWaitError as exc:
                logger.warning(f"FloodWait {exc.seconds}s")
                await asyncio.sleep(exc.seconds + 5)
            except (ChatWriteForbiddenError, PeerIdInvalidError, UserBannedInChannelError) as exc:
                logger.error(f"Kanal xatosi: {exc}")
                return False
            except Exception as exc:
                wait = settings.RETRY_DELAY_SECONDS * attempt
                logger.warning(f"Post urinish {attempt}: {exc} -- {wait}s")
                if attempt < settings.MAX_RETRIES:
                    await asyncio.sleep(wait)
        return False