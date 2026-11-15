from functools import lru_cache
from pathlib import Path

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_JWT_SECRET = "change-me-change-me-change-me-change-me"  # noqa: S105


class Settings(BaseSettings):
    # One file for Docker Compose, make and the application; .env.local may override it.
    model_config = SettingsConfigDict(env_file=(ROOT / ".env", ROOT / ".env.local"), extra="ignore")

    env: str = "local"
    database_url: str = "postgresql://telcron:telcron_dev@127.0.0.1:5433/telcron"
    redis_url: str = "redis://127.0.0.1:6381"
    web_origin: str = "http://localhost:3200"
    jwt_secret: str = DEFAULT_JWT_SECRET
    access_token_minutes: int = 60
    refresh_token_days: int = 30
    code_ttl_minutes: int = 10
    code_max_attempts: int = 5
    login_max_failures: int = 5
    login_lock_minutes: int = 15
    # Local only: return verification codes in the register response instead of sending them.
    dev_expose_codes: bool = False
    # stub | bedrock. Bedrock is not wired yet (WO-004).
    ai_provider: str = "stub"
    passport_cache_seconds: int = 24 * 3600
    # Local demos only: the application seed shortens every earn rule's confirmation delay to this.
    coin_confirm_delay_seconds: int | None = None
    run_outbox_publisher: bool = True
    # The seed creates an admin from this, and only when ENV is local or dev. Never in production.
    seed_admin_password: str | None = None

    @field_validator("database_url")
    @classmethod
    def _use_the_async_driver(cls, url: str) -> str:
        # .env carries the plain URL that psql, dbmate and the schema tests share.
        for prefix in ("postgresql://", "postgres://"):
            if url.startswith(prefix):
                return "postgresql+asyncpg://" + url[len(prefix):]
        return url

    @model_validator(mode="after")
    def _refuse_default_secret_outside_local(self) -> "Settings":
        if self.env not in ("local", "test") and self.jwt_secret == DEFAULT_JWT_SECRET:
            raise ValueError("JWT_SECRET must be set when ENV is not local")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
