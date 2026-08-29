from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Process-wide configuration, loaded once from the environment.

    A missing required variable fails fast at process startup (pydantic-settings
    raises a ValidationError before the app finishes constructing), not on the
    first request that happens to need it.
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Database ---
    database_url: str = Field(..., alias="DATABASE_URL")

    # --- Anthropic / LLM ---
    anthropic_api_key: str = Field(..., alias="ANTHROPIC_API_KEY")
    anthropic_model: str = Field("claude-sonnet-5", alias="ANTHROPIC_MODEL")
    embedding_model: str = Field("all-MiniLM-L6-v2", alias="EMBEDDING_MODEL")

    # --- Auth / JWT ---
    jwt_secret_key: str = Field(..., alias="JWT_SECRET_KEY")
    jwt_algorithm: str = Field("HS256", alias="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(30, alias="ACCESS_TOKEN_EXPIRE_MINUTES")
    refresh_token_expire_days: int = Field(14, alias="REFRESH_TOKEN_EXPIRE_DAYS")
    password_reset_token_expire_minutes: int = Field(60, alias="PASSWORD_RESET_TOKEN_EXPIRE_MINUTES")
    # The backend has otherwise never needed to know the frontend's own
    # origin — needed here to build the link a password-reset email points at.
    frontend_base_url: str = Field("http://localhost:3000", alias="FRONTEND_BASE_URL")

    # --- Email (AWS SES) — all optional so the app runs fine unconfigured;
    # only password reset needs these, validated lazily where used
    # (app/services/email_service.py) rather than at process startup. Access
    # key/secret left optional so boto3's default credential chain (env vars,
    # ~/.aws/credentials, an IAM role in real deployment) can be used instead
    # of hardcoding keys here. ---
    aws_region: str | None = Field(None, alias="AWS_REGION")
    aws_access_key_id: str | None = Field(None, alias="AWS_ACCESS_KEY_ID")
    aws_secret_access_key: str | None = Field(None, alias="AWS_SECRET_ACCESS_KEY")
    email_from: str | None = Field(None, alias="EMAIL_FROM")

    # --- CORS ---
    cors_origins: str = Field("", alias="CORS_ORIGINS")

    # --- Redis (rate limiting / token cache) ---
    redis_url: str = Field(..., alias="REDIS_URL")

    # --- Ingestion / RAG ---
    max_ingest_bytes: int = Field(2_000_000, alias="MAX_INGEST_BYTES")
    daily_token_budget: int | None = Field(None, alias="DAILY_TOKEN_BUDGET")

    # --- ScoreWise: syllabus vector store (ChromaDB) ---
    # Defaults target the host-mapped port docker-compose.yml exposes, for
    # running the API process directly on the host against a dockerized
    # chroma/postgres/redis (mirrors how DATABASE_URL's local default targets
    # localhost:5432). Docker-compose overrides both to the `chromadb`
    # service's container-internal address for the containerized api/migrate
    # services, same pattern as DATABASE_URL/REDIS_URL.
    chroma_host: str = Field("localhost", alias="CHROMA_HOST")
    chroma_port: int = Field(8001, alias="CHROMA_PORT")
    max_syllabus_upload_bytes: int = Field(20 * 1024 * 1024, alias="MAX_SYLLABUS_UPLOAD_BYTES")

    # --- Observability ---
    log_level: str = Field("INFO", alias="LOG_LEVEL")

    # --- Deployment ---
    app_env: Literal["development", "staging", "production"] = Field("development", alias="APP_ENV")
    workers: int = Field(4, alias="WORKERS")

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def docs_enabled(self) -> bool:
        # Gate interactive docs exposure in production, per §10 APP_ENV note.
        return not self.is_production


@lru_cache
def get_settings() -> Settings:
    return Settings()
