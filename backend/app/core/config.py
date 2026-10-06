from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://intellicrm:intellicrm@localhost:5432/intellicrm"
    redis_url: str = ""
    jwt_secret: str = "dev-only-change-me-access-secret-32bytes"
    jwt_refresh_secret: str = "dev-only-change-me-refresh-secret-32bytes"
    access_ttl_minutes: int = 15
    refresh_ttl_days: int = 14
    storage_dir: str = "../storage"
    max_upload_bytes: int = 10 * 1024 * 1024
    cors_origins: str = "http://localhost:3000"
    llm_api_key: str = ""
    model_dir: str = "../ml/artifacts"
    default_currency: str = "INR"


settings = Settings()
