from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # App
    jwt_secret: str = "dev-only-secret-change-me"
    jwt_expire_minutes: int = 1440
    app_db_url: str = "sqlite:///./app_metadata.db"
    cors_origins: str = "http://localhost:5173"

    # Google
    google_client_id: str = ""

    # Demo login (bypasses Google Sign-In with two fixed local accounts — disable for a real deployment)
    allow_demo_login: bool = True

    # Gemini
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.5-flash-lite"

    # Snowflake
    snowflake_account: str = ""
    snowflake_user: str = ""
    snowflake_password: str = ""
    snowflake_private_key_path: str = ""
    snowflake_private_key_passphrase: str = ""
    snowflake_role: str = "SYSADMIN"
    snowflake_warehouse: str = "COMPUTE_WH"
    snowflake_database: str = "ANALYTICS_DB"

    max_upload_mb: int = 25

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
