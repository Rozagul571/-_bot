import asyncio
import signal
import sys

from core.config import settings
from core.logger import setup_logging

setup_logging()

from loguru import logger
from services.database import Database
from services.translator import Translator
from services.poster import ChannelPoster
from services.monitor import ChannelMonitor


def build_pipeline():
    db = Database(url=settings.db_url())

    translator = Translator(
        api_key=settings.AI_API_KEY,
        model=settings.AI_MODEL,
        base_url=settings.AI_BASE_URL,
    )

    poster = ChannelPoster(
        api_id=settings.TELEGRAM_API_ID,
        api_hash=settings.TELEGRAM_API_HASH,
        bot_token=settings.TELEGRAM_BOT_TOKEN,
        target_channel=settings.TARGET_CHANNEL,
    )

    monitor = ChannelMonitor(
        db=db,
        translator=translator,
        poster=poster,
    )
    return monitor, db, poster


async def main() -> None:
    logger.info("=" * 52)
    logger.info("  TENDERZON — Qonunchilik Yangiliklari")
    channel_name = settings.SOURCE_CHANNELS[0] if settings.SOURCE_CHANNELS else "unknown"
    logger.info(f"  Manba  : @{channel_name}")
    logger.info(f"  Manzil : {settings.TARGET_CHANNEL}")
    logger.info(f"  Model  : {settings.AI_MODEL}")
    logger.info("=" * 52)

    monitor, db, poster = build_pipeline()
    await db.init()

    loop = asyncio.get_running_loop()

    async def _shutdown(sig_name: str) -> None:
        logger.warning(f"{sig_name} — toxtatilmoqda...")
        await poster.stop()
        for t in asyncio.all_tasks():
            if t is not asyncio.current_task():
                t.cancel()
        loop.stop()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(
            sig, lambda s=sig: asyncio.create_task(_shutdown(s.name))
        )

    try:
        await monitor.run()
    except asyncio.CancelledError:
        pass
    finally:
        await poster.stop()
        await db.close()
        logger.info("Pipeline toxtatildi.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)