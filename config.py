import ssl
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Telegram Bot API
    telegram_bot_token: str
    webhook_port: int = 8080
    webhook_url: str

    # Parsing
    bolshoi_news_url: str = "https://bolshoi.ru/news/obyavleniya/"
    parse_interval_hours: int = 6
    notify_before_minutes: int = 30

    # PostgreSQL — Yandex Managed Service for PostgreSQL
    db_host: str
    db_port: int = 6432
    db_name: str
    db_user: str
    db_password: str
    db_ssl_ca: str = ""

    # Logging
    log_level: str = "INFO"
    log_file: str = "/var/log/bolshoi-bot/bot.log"

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    @property
    def telegram_api_base(self) -> str:
        # All Telegram Bot API methods are called as
        # https://api.telegram.org/bot<TOKEN>/<METHOD>
        return f"https://api.telegram.org/bot{self.telegram_bot_token}"

    def build_ssl_context(self) -> ssl.SSLContext | None:
        if not self.db_ssl_ca:
            return None
        ctx = ssl.create_default_context(cafile=self.db_ssl_ca)
        return ctx


@lru_cache
def get_settings() -> Settings:
    return Settings()
