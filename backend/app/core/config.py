from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    env: str = "development"
    log_level: str = "INFO"

    # SecretStr so a validation error, log line, or repr() never echoes the connection
    # string / signing key — CLAUDE.md: no secrets in code or logs.
    database_url: SecretStr
    test_database_url: SecretStr

    jwt_secret: SecretStr
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60

    cors_origins: str = "http://localhost:3000"

    # Provider key for the Gemini client in agents/llm.py. Optional so the app and the
    # non-LLM test suite boot without it; the client raises when it is actually needed.
    gemini_api_key: SecretStr | None = None
    # Model name only. The vector width is a code constant bound to the migrations
    # (context/embeddings.py EMBEDDING_DIMENSIONS), not a setting.
    embedding_model: str = "gemini-embedding-2"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
