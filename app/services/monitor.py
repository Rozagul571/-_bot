"""
monitor.py — Real-time listener.
1gz.uz/#/document linkli postlar — AVTOMATIK tegishli.
"""

import re
from typing import Optional

from telethon import TelegramClient, events
from telethon.tl.types import Message, MessageEntityUrl, MessageEntityTextUrl
from loguru import logger

from core.config import settings
from services.database import Database
from services.translator import Translator
from services.poster import ChannelPoster
from services.fetcher import fetch_url_content

MIN_TEXT_LENGTH = 20
OFFICIAL_DOMAIN = "1gz.uz"


class ChannelMonitor:
    def __init__(self, db: Database, translator: Translator, poster: ChannelPoster) -> None:
        self._db = db
        self._translator = translator
        self._poster = poster

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
        mid = msg.id
        text = _get_text(msg)
        link = _get_link(msg)

        # 1gz.uz rasmiy hujjat havolasimi?
        is_official = bool(link and OFFICIAL_DOMAIN in link and "/document" in link)

        logger.info(
            f"#{mid} | {len(text)} belgi | "
            f"link={'bor' if link else 'yoq'} | "
            f"rasmiy={'ha' if is_official else 'yoq'}"
        )

        # 1. Dublikat
        if await self._db.is_processed(mid):
            logger.info(f"#{mid} allaqachon ishlangan — skip")
            return

        # 2. Juda qisqa (faqat link ham yo'q bo'lsa)
        if len(text.strip()) < MIN_TEXT_LENGTH and not link:
            logger.info(f"#{mid} juda qisqa — skip")
            await self._db.save(
                message_id=mid, channel=settings.SOURCE_CHANNEL,
                original_text=text, is_relevant=False, skip_reason="qisqa",
            )
            return

        # 3. Link mazmunini o'qi
        link_content: Optional[str] = None
        if link:
            logger.info(f"#{mid} link o'qilmoqda: {link[:70]}")
            link_content = await fetch_url_content(link)
            if link_content:
                logger.info(f"#{mid} link mazmuni: {len(link_content)} belgi")

        # 4. AI: bitta so'rov — tekshiruv + post
        logger.info(f"#{mid} AI ga yuborilmoqda...")
        result = await self._translator.process(
            telegram_text=text,
            link_content=link_content,
            has_1gz_link=is_official,
        )

        # 5. Tegishli emas
        if not result["is_relevant"]:
            logger.info(f"#{mid} AI: tegishli emas — skip")
            await self._db.save(
                message_id=mid, channel=settings.SOURCE_CHANNEL,
                original_text=text, is_relevant=False, skip_reason="ai_skip",
            )
            return

        # 6. Post bo'sh
        post_text = result["post"]
        if not post_text:
            logger.warning(f"#{mid} AI post bo'sh")
            await self._db.save(
                message_id=mid, channel=settings.SOURCE_CHANNEL,
                original_text=text, error="ai_post_empty",
            )
            return

        # 7. Kanalga yubor
        posted: bool = await self._poster.post(post_text)

        # 8. DB saqlash
        await self._db.save(
            message_id=mid,
            channel=settings.SOURCE_CHANNEL,
            original_text=text,
            translated_text=post_text,
            is_relevant=True,
            posted=posted,
            error=None if posted else "post_xato",
        )
        logger.info(f"#{mid} yakunlandi | {'OK' if posted else 'XATO'}")


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
