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

    model_config = SettingsConfigDict(
        env_file=Path(".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


def get_config() -> AppConfig:
    return AppConfig()
