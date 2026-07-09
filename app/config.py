from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "STRATZ Dota Analytics API"
    environment: str = "local"
    database_url: str = "postgresql+psycopg://stratz:stratz@localhost:5432/stratz_anal"
    stratz_graphql_url: str = "https://api.stratz.com/graphql"
    stratz_token: str | None = Field(default=None, repr=False)
    stratz_proxy_url: str | None = Field(default=None, repr=False)
    refresh_cooldown_seconds: int = 900
    match_history_limit: int = 500

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
