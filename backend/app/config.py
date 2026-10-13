import secrets
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://raffle:raffle@localhost:5432/raffle"
    admin_username: str = "admin"
    admin_password: str = "change-me"
    jwt_secret: str = secrets.token_urlsafe(48)  # set JWT_SECRET to survive restarts
    jwt_hours: int = 12
    cors_origins: str = "http://localhost:4200"
    upload_dir: Path = Path("uploads")
    max_upload_bytes: int = 8 * 1024 * 1024
    max_lockin_attempts: int = 10


config = Config()
