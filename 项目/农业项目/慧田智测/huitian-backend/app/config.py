from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    app_name: str = "慧田智测后端"
    app_env: str = "development"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    database_url: str = "sqlite:///./data/huitian.db"

    mqtt_enabled: bool = True
    mqtt_host: str = "172.20.10.2"
    mqtt_port: int = 1883
    mqtt_username: str | None = None
    mqtt_password: str | None = None
    mqtt_client_id: str = "huitian-backend"
    mqtt_topic_prefix: str = "huitian"

    upload_max_mb: int = 5
    edge_api_key: str | None = None
    log_level: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def upload_dir(self) -> Path:
        return BASE_DIR / "uploads"

    @property
    def data_dir(self) -> Path:
        return BASE_DIR / "data"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
