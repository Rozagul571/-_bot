import sys
from pathlib import Path
from loguru import logger
from core.config import LOG_DIR


def setup_logging():
    """Logging sozlamalari"""
    log_file = LOG_DIR / "pipeline.log"

    logger.remove()

    # Console
    logger.add(
        sys.stdout,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan> | <level>{message}</level>",
        level="INFO"
    )

    # File
    logger.add(
        log_file,
        rotation="10 MB",
        retention="7 days",
        compression="gz",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}",
        level="DEBUG"
    )

    logger.info("Logging tizimi ishga tushdi")