"""Application settings.

One `Settings` object is the single source of truth for configuration (see
IMPLEMENTATION.md section 6.5 for the environment contract). Never read `os.environ`
directly anywhere else in the codebase.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["local", "test", "staging", "production"]


class Settings(BaseSettings):
    """Environment-driven configuration.

    Values are read from (in order of precedence) explicit constructor arguments,
    environment variables, the backend `.env`, then the repository root `.env`.
    """

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Application ---
    app_name: str = "football-ai-analyst"
    environment: Environment = "local"
    log_level: str = "INFO"

    # --- Database (Phase 1+) ---
    # Empty means "no database configured"; /health reports that instead of failing.
    database_url: str = ""
    db_health_timeout_seconds: float = 2.0

    # --- Vector store (Phase 7+) ---
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str = ""

    # --- LLM (Phase 3+) ---
    groq_api_key: str = ""
    llm_api_key: str = ""
    llm_model: str = "llama-3.3-70b-versatile"
    llm_base_url: str = "https://api.groq.com/openai/v1"
    llm_timeout_seconds: float = 45.0
    tool_timeout_seconds: float = 10.0
    max_critic_retries: int = 2

    @property
    def resolved_llm_api_key(self) -> str:
        """Return the active LLM API key (GROQ_API_KEY or LLM_API_KEY)."""
        return self.groq_api_key or self.llm_api_key

    # --- Observability (Phase 11) ---
    langchain_tracing_v2: bool = False
    langchain_api_key: str = ""

    # --- CORS ---
    # Kept as a plain comma-separated string: pydantic-settings would otherwise try to
    # JSON-parse list-typed fields, which surprises people writing `CORS_ORIGINS=a,b`.
    cors_origins: str = "http://localhost:5173"

    @property
    def cors_origins_list(self) -> list[str]:
        """Allowed browser origins, split and trimmed from `CORS_ORIGINS`."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings object (cached)."""
    return Settings()
