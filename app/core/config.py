from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    GEMINI_API_KEY: str
    GEMINI_MODEL: str
    GOOGLE_PLACE_API: str | None = None
    GOOGLE_PLACES_API_KEY: str | None = None
    DB_PATH: str = "app/db/cache.sqlite3"

    class Config:
        env_file= ".env"
        env_file_encoding= "utf-8"

    @property
    def google_places_api_key(self) -> str:
        key = self.GOOGLE_PLACE_API or self.GOOGLE_PLACES_API_KEY
        if not key:
            raise ValueError(
                "Set GOOGLE_PLACE_API or GOOGLE_PLACES_API_KEY in .env"
            )
        return key


@lru_cache
def get_settings() -> Settings:
    return Settings()

