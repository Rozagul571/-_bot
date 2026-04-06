import os
from pathlib import Path
from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings

_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = Path(os.getenv("DATA_DIR", str(_ROOT / "data")))
LOG_DIR  = Path(os.getenv("LOG_DIR",  str(_ROOT / "logs")))
DATA_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)


class Settings(BaseSettings):
    TELEGRAM_API_ID: int       = Field(...)
    TELEGRAM_API_HASH: str     = Field(...)
    TELEGRAM_PHONE: str        = Field(...)
    TELEGRAM_BOT_TOKEN: str    = Field(...)
    SOURCE_CHANNEL: str        = Field(...)
    TARGET_CHANNEL: str        = Field(...)
    OPENAI_API_KEY: str        = Field(...)
    OPENAI_MODEL: str          = Field(default="llama-3.3-70b-versatile")
    MAX_RETRIES: int           = Field(default=3)
    RETRY_DELAY_SECONDS: int   = Field(default=10)
    MIN_TEXT_LENGTH: int       = Field(default=30)
    FETCH_LIMIT: int           = Field(default=20)
    LOG_LEVEL: str             = Field(default="INFO")

    class Config:
        env_file = str(_ROOT / ".env")
        env_file_encoding = "utf-8"

    def db_url(self)       -> str: return f"sqlite+aiosqlite:///{DATA_DIR / 'pipeline.db'}"
    def user_session(self) -> str: return str(DATA_DIR / "user_session")
    def bot_session(self)  -> str: return str(DATA_DIR / "bot_session")
    def log_file(self)     -> str: return str(LOG_DIR  / "pipeline.log")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()

settings = get_settings()