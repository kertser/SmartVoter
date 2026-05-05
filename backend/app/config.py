from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://smartvoter:smartvoter@localhost:5432/smartvoter"
    redis_url: str = "redis://localhost:6379/0"
    app_env: str = "development"
    secret_key: str = "change-me-in-production"
    cors_origins: str = "http://localhost:3000"

    # Admin panel password — must be changed before any deployment
    admin_password: str = "admin"

    # LLM provider configuration
    openai_api_key: str = ""
    openai_model: str = "gpt-5-nano"
    llm_timeout_seconds: int = 30
    llm_max_retries: int = 2

    # Knesset ingestion
    knesset_api_base_url: str = "https://knesset.gov.il/Odata/ParliamentInfo.svc"
    oknesset_api_base_url: str = "https://oknesset.org/api/v2"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",")]

    @property
    def has_openai(self) -> bool:
        return bool(self.openai_api_key and self.openai_api_key.startswith("sk-"))


@lru_cache
def get_settings() -> Settings:
    return Settings()
