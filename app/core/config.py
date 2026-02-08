from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    GEMINI_API_KEY: str
    GEMINI_MODEL: str
    DB_PATH: str = "app/db/cache.sqlite3"

    class Config:
        env_file= ".env"
        env_file_encoding= "utf-8"


@lru_cache
def get_settings() -> Settings:
    return Settings()

