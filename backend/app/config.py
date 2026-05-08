from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator


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
    # Bills/persons endpoint (ParliamentInfo service — still active for KNS_Bill, KNS_Person, etc.)
    knesset_api_base_url: str = "https://knesset.gov.il/Odata/ParliamentInfo.svc"
    # Votes endpoint — moved to a separate service in 2024
    # Entity: View_vote_rslts_hdr_Approved (headers), vote_rslts_kmmbr_shadow (per-MK results)
    knesset_votes_api_base_url: str = "https://knesset.gov.il/Odata/Votes.svc"
    oknesset_api_base_url: str = "https://oknesset.org/api/v2"
    # Most recent Knesset number. Bump this when a new election occurs.
    # Knesset 26 was sworn in ~November 2025.
    current_knesset: int = 26
    # Highest Knesset number with confirmed vote data in Votes.svc.
    # As of May 2026 the service only contains Knessets 1–24 (last vote 2021-07-13).
    # Knessets 25 and 26 data are NOT yet published to this endpoint.
    # The importer will also dynamically probe knessets above this value in case the
    # API is updated — no manual bump needed in that case.
    last_knesset_with_votes: int = 24

    # Question bank bulk generation
    # Maximum number of questions to generate in one "generate question bank" run.
    # These are pre-generated offline so the questionnaire never needs on-the-fly LLM calls.
    max_questions_to_generate: int = 300
    # Maximum tree depth for generated question trees:
    #   0 = topic-level root questions only
    #   1 = root + policy-item-level follow-ups
    #   2 = root + policy-item + deep directional follow-ups (recommended)
    question_bank_max_depth: int = 2
    question_bank_max_workers: int = 8

    # DB connection pool — expose for production tuning
    db_pool_size: int = 5
    db_max_overflow: int = 10

    @model_validator(mode="after")
    def _validate_production_secrets(self) -> "Settings":
        if self.app_env == "production":
            if self.secret_key == "change-me-in-production":
                raise ValueError(
                    "SECRET_KEY must be set to a strong random value in production. "
                    "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
                )
            if self.admin_password == "admin":
                raise ValueError(
                    "ADMIN_PASSWORD must be changed from the default 'admin' in production."
                )
        return self

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",")]

    @property
    def has_openai(self) -> bool:
        return bool(self.openai_api_key and self.openai_api_key.startswith("sk-"))

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
