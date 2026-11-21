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
    # stub | llm. `llm` scores hazards with a model over an OpenAI-compatible API (Groq's free plan
    # by default) and falls back to the keyword stub when it cannot answer.
    ai_provider: str = "stub"
    llm_api_key: str | None = None
    llm_base_url: str = "https://api.groq.com/openai/v1"
    llm_model: str = "openai/gpt-oss-120b"
    vision_model: str = "qwen/qwen3.8-27b"
    # Used when the main model's daily token allowance is spent (each model has its own on the
    # free plan): research reading, hazard scoring and the assistant keep working.
    llm_fallback_model: str = "openai/gpt-oss-20b"
    passport_cache_seconds: int = 24 * 3600
    # Local demos only: the application seed shortens every earn rule's confirmation delay to this.
    coin_confirm_delay_seconds: int | None = None
    run_outbox_publisher: bool = True
    # The seed creates an admin from this, and only when ENV is local or dev. Never in production.
    seed_admin_password: str | None = None
    # The commit this build was made from; baked into the image, reported by /health.
    git_sha: str = "dev"
    # Verification codes by email: `log` (local, codes shown in the sign-up response), `smtp` or `ses`.
    mail_provider: str = "log"
    mail_from: str | None = None
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str | None = None  # defaults to MAIL_FROM
    smtp_password: str | None = None
    # Product research (WO-014): live recall databases and a web search. TAVILY_API_KEY selects
    # Tavily; without it the LLM provider's built-in browser search is used, sparingly.
    research_enabled: bool = True
    tavily_api_key: str | None = None
    research_model: str = "openai/gpt-oss-20b"
    research_cooldown_hours: int = 24
    # Photos (WO-014): `none` keeps nothing; `s3` stores them in MEDIA_BUCKET with the host role.
    media_store: str = "none"
    media_bucket: str | None = None
    # `rekognition` reads text and labels from a photo before the vision model; `none` skips it.
    image_reader: str = "none"
    # Embeddings (WO-015): our own embedder service (services/embedder). Unset = no vectors; search
    # and the assistant fall back to text matching and recency.
    embed_url: str | None = None
    embed_token: str | None = None
    embed_model: str = "bge-small-en-v1.5:384"
    aws_region: str = "us-east-2"
    # Level 1 needs a verified phone too. Off until an SMS route exists (ADR-006).
    level1_requires_phone: bool = False
    # A JSON file to read instead of calling the CPSC feed. For stacks that must not depend on the
    # network (the pipeline's browser tests). Never set where real recalls are wanted.
    cpsc_fixture: str | None = None

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
