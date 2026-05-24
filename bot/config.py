from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"

load_dotenv(ENV_PATH)


class Settings(BaseSettings):
    BOT_TOKEN: str

    PGHOST: str = "localhost"
    PGPORT: int = 5432
    PGUSER: str = "postgres"
    PGPASSWORD: str = "111"
    PG_MAINTENANCE_DB: str = "postgres"

    model_config = SettingsConfigDict(
        env_file=str(ENV_PATH),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
