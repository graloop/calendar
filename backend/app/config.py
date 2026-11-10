# The app's settings, read from the environment or from .env (the project root's
# when run from backend/, as `npm start` does).

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")

    # The database lives here: /data in the container, backend/data on the laptop.
    data_dir: str = "./data"

    # Swagger UI at /docs. Off by default so the API isn't advertised.
    enable_api_docs: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
