import os
from pathlib import Path
from functools import lru_cache
from typing import List
from pydantic import Field
from pydantic_settings import BaseSettings

_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = Path(os.getenv("DATA_DIR", str(_ROOT / "data")))
LOG_DIR = Path(os.getenv("LOG_DIR", str(_ROOT / "logs")))
DATA_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)


class Settings(BaseSettings):
    # Telegram User
    TELEGRAM_API_ID: int = Field(...)
    TELEGRAM_API_HASH: str = Field(...)
    TELEGRAM_PHONE: str = Field(...)
    TELEGRAM_BOT_TOKEN: str = Field(...)

    # Kanallar — .env da SOURCE_CHANNELS nomi bilan
    SOURCE_CHANNELS: List[str] = Field(default=["goszakupki_uz"])
    TARGET_CHANNEL: str = Field(...)

    # AI
    AI_API_KEY: str = Field(...)
    AI_MODEL: str = Field(default="gpt-4o-mini")
    AI_BASE_URL: str = Field(default="https://api.openai.com/v1")

    # Runtime
    MAX_RETRIES: int = Field(default=3)
    RETRY_DELAY_SECONDS: int = Field(default=10)
    LOG_LEVEL: str = Field(default="INFO")

    class Config:
        env_file = str(_ROOT / ".env")
        env_file_encoding = "utf-8"
        extra = "ignore"  

    def db_url(self) -> str:
        return f"sqlite+aiosqlite:///{DATA_DIR / 'pipeline.db'}"

    def user_session(self) -> str:
        return str(DATA_DIR / "user_session")

    def bot_session(self) -> str:
        return str(DATA_DIR / "bot_session")

    def log_file(self) -> str:
        return str(LOG_DIR / "pipeline.log")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()