from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppConfig(BaseSettings):
    bot_token: str = Field(default="dev-bot-token", alias="BOT_TOKEN")
    openai_api_key: str = Field(default="dev-openai-key", alias="OPENAI_API_KEY")
    database_url: str = Field(default="sqlite+aiosqlite:///./data/bot.db", alias="DATABASE_URL")

    model_config = SettingsConfigDict(
        env_file=Path(".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


def get_config() -> AppConfig:
    return AppConfig()
