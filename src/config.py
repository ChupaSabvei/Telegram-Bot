from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppConfig(BaseSettings):
    bot_token: str = Field(default="dev-bot-token", alias="BOT_TOKEN")
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_api_base: str | None = Field(default=None, alias="OPENAI_API_BASE")
    openai_model: str = Field(default="gpt-4o-mini", alias="OPENAI_MODEL")
    database_url: str = Field(default="sqlite+aiosqlite:///./data/bot.db", alias="DATABASE_URL")
    telegram_proxy: str | None = Field(default=None, alias="TELEGRAM_PROXY")
    telegram_channel_sources: str = Field(
        default=(
            "https://t.me/kuda_v_moskva,"
            "https://t.me/msk24afisha,"
            "https://t.me/mcktime,"
            "https://t.me/surfcoffeexmsk,"
            "https://t.me/meropriatia,"
            "https://t.me/sobytiyami,"
            "https://t.me/detstvo_msk,"
            "https://t.me/TOT_STANDUP,"
            "https://vk.ru/afichaspb,"
            "https://vk.ru/timepadru"
        ),
        alias="TELEGRAM_CHANNEL_SOURCES",
    )
    scrapingbee_api_key: str = Field(default="", alias="SCRAPINGBEE_API_KEY")
    scrapingbee_stealth: bool = Field(default=False, alias="SCRAPINGBEE_STEALTH")
    scrapingbee_premium: bool = Field(default=False, alias="SCRAPINGBEE_PREMIUM")
    scrapingbee_country_code: str = Field(default="ru", alias="SCRAPINGBEE_COUNTRY_CODE")
    crawlee_enabled: bool = Field(default=True, alias="CRAWLEE_ENABLED")

    model_config = SettingsConfigDict(
        env_file=Path(".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


def get_config() -> AppConfig:
    return AppConfig()
