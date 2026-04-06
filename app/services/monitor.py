"""
monitor.py — Real-time Telethon event listener.
Yangi post kelganda bir marta ishlaydi. Polling yo'q.
"""

import re
from typing import Optional
from telethon import TelegramClient, events
from telethon.tl.types import Message, MessageEntityUrl, MessageEntityTextUrl
from loguru import logger

from core.config import settings
from services.database import Database
from services.filter import ContentFilter
from services.translator import Translator
from services.poster import ChannelPoster
from services.fetcher import fetch_url_content


class ChannelMonitor:
    def __init__(
        self,
        db: Database,
        content_filter: ContentFilter,
        translator: Translator,
        poster: ChannelPoster,
    ) -> None:
        self._db         = db
        self._filter     = content_filter
        self._translator = translator
        self._poster     = poster

        self._client = TelegramClient(
            session=settings.user_session(),
            api_id=settings.TELEGRAM_API_ID,
            api_hash=settings.TELEGRAM_API_HASH,
        )

    async def start(self) -> None:
        await self._client.start(phone=settings.TELEGRAM_PHONE)
        me = await self._client.get_me()
        logger.info(f"User ulandi: @{me.username or me.first_name}")

    async def stop(self) -> None:
        if self._client.is_connected():
            await self._client.disconnect()

    async def run(self) -> None:
        await self.start()
        stats = await self._db.get_stats()
        logger.info(f"DB holati: {stats}")

        @self._client.on(events.NewMessage(chats=settings.SOURCE_CHANNEL))
        async def on_new_post(event: events.NewMessage.Event) -> None:
            logger.info(f"⚡ Yangi post: #{event.message.id}")
            await self._handle(event.message)

        logger.info(f"✅ Listening: @{settings.SOURCE_CHANNEL}")
        logger.info("Yangi post kelganda bir marta ishlaydi...")
        await self._client.run_until_disconnected()

    async def _handle(self, msg: Message) -> None:
        mid  = msg.id
        text = _get_text(msg)
        link = _get_link(msg)

        logger.info(f"#{mid} | {len(text)} belgi | link={'bor' if link else 'yoq'}")

        # 1. Dublikat — bir marta
        if await self._db.is_processed(mid):
            logger.info(f"#{mid} allaqachon ishlangan — skip")
            return

        # 2. Juda qisqa
        if len(text.strip()) < settings.MIN_TEXT_LENGTH and not link:
            logger.info(f"#{mid} juda qisqa — skip")
            await self._db.save(message_id=mid, channel=settings.SOURCE_CHANNEL,
                                original_text=text, is_relevant=False, skip_reason="qisqa")
            return

        # 3. Rus tilida emas
        if text and not self._filter.is_russian(text):
            logger.info(f"#{mid} rus tilida emas — skip")
            await self._db.save(message_id=mid, channel=settings.SOURCE_CHANNEL,
                                original_text=text, is_relevant=False, skip_reason="rus_emas")
            return

        # 4. Kalit so'z filtri (bepul)
        if not self._filter.is_relevant(text or link or ""):
            logger.info(f"#{mid} kalit so'z yo'q — skip")
            await self._db.save(message_id=mid, channel=settings.SOURCE_CHANNEL,
                                original_text=text, is_relevant=False, skip_reason="kalit_yoq")
            return

        # 5. AI relevantlik
        if text and not await self._translator.is_relevant(text):
            logger.info(f"#{mid} AI: tegishli emas — skip")
            await self._db.save(message_id=mid, channel=settings.SOURCE_CHANNEL,
                                original_text=text, is_relevant=False, skip_reason="ai_skip")
            return

        # 6. Link mazmunini o'qi
        link_content: Optional[str] = None
        if link:
            logger.info(f"#{mid} link o'qilmoqda: {link[:70]}")
            link_content = await fetch_url_content(link)
            if link_content:
                logger.info(f"#{mid} link mazmuni: {len(link_content)} belgi")

        # 7. Post yaratish
        try:
            post_text = await self._translator.create_post(
                telegram_text=text,
                link_content=link_content,
            )
        except Exception as exc:
            logger.error(f"#{mid} post yaratish xato: {exc}")
            await self._db.save(message_id=mid, channel=settings.SOURCE_CHANNEL,
                                original_text=text, error=str(exc))
            return

        # 8. Kanalga yuborish — bool qaytaradi
        posted: bool = await self._poster.post(post_text, link=link)

        # 9. DB ga saqlash
        await self._db.save(
            message_id=mid,
            channel=settings.SOURCE_CHANNEL,
            original_text=text,
            translated_text=post_text,
            is_relevant=True,
            posted=posted,            # bu har doim True yoki False
            error=None if posted else "post_xato",
        )
        logger.info(f"#{mid} yakunlandi | {'✅ OK' if posted else '❌ XATO'}")


def _get_text(msg: Message) -> str:
    return (msg.text or msg.message or "").strip()


def _get_link(msg: Message) -> Optional[str]:
    for ent in msg.entities or []:
        if isinstance(ent, MessageEntityTextUrl):
            return ent.url
        if isinstance(ent, MessageEntityUrl):
            txt = msg.text or ""
            return txt[ent.offset: ent.offset + ent.length]
    if msg.reply_markup:
        try:
            for row in msg.reply_markup.rows:
                for btn in row.buttons:
                    if hasattr(btn, "url") and btn.url:
                        return btn.url
        except Exception:
            pass
    raw = msg.text or msg.message or ""
    m = re.search(r"https?://[^\s\)\]\>\"\']+", raw, re.I)
    return m.group(0) if m else None