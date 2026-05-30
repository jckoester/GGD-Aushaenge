from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    secret_key: str
    database_url: str = "sqlite:///./ggd_aushaenge.db"
    upload_dir: str = "uploads"
    processed_dir: str = "processed"
    webdav_url: str
    webdav_user: str
    webdav_password: str
    oidc_client_id: str = ""
    oidc_client_secret: str = ""
    oidc_server_metadata_url: str = ""
    oidc_required_group: str = "Infobildschirme"
    dev_mode: bool = False

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

@lru_cache
def get_settings() -> Settings:
    return Settings()