from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    telegram_bot_token: str
    telegram_webhook_secret: str
    deepseek_api_key: str | None = None
    deepseek_model: str = "deepseek-chat"


@lru_cache
def get_settings() -> Settings:
    return Settings()
