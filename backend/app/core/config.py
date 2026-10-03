"""Environment-backed settings; constructing settings never contacts a service."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, HttpUrl, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        extra="ignore",
        hide_input_in_errors=True,
    )

    app_env: Literal["development", "test", "production"] = "development"
    frontend_origin: HttpUrl
    groq_api_key: SecretStr = Field(repr=False)
    firecrawl_api_key: SecretStr = Field(repr=False)
    # SDK endpoint defaults are used unless explicitly overridden.
    groq_base_url: HttpUrl | None = None
    firecrawl_base_url: HttpUrl
    supabase_url: HttpUrl
    supabase_service_role_key: SecretStr = Field(repr=False)
    langsmith_api_key: SecretStr | None = Field(default=None, repr=False)
    langsmith_project: str = Field(min_length=1)
    langsmith_tracing: bool = False
    langsmith_endpoint: HttpUrl | None = None

    groq_model_parser: str = Field(min_length=1)
    groq_model_source_collector: str = Field(min_length=1)
    groq_model_link_check: str = Field(min_length=1)
    groq_model_analyst: str = Field(min_length=1)
    groq_model_matcher: str = Field(min_length=1)
    groq_model_writer: str = Field(min_length=1)
    groq_model_verifier: str = Field(min_length=1)
    groq_model_eval_judge: str = Field(min_length=1)

    provider_max_attempts: int = Field(default=2, ge=1, le=3)
    schema_max_attempts: int = Field(default=2, ge=1, le=3)
    groq_concurrency: int = Field(default=1, ge=1, le=4)
    firecrawl_concurrency: int = Field(default=1, ge=1, le=4)
    retry_base_seconds: float = Field(default=2, ge=0, le=30)
    retry_max_seconds: float = Field(default=30, ge=0, le=120)
    provider_timeout_seconds: float = Field(default=45, gt=0, le=120)
    model_max_output_tokens: int = Field(default=8192, ge=512, le=16384)
    parser_input_chars: int = Field(default=4000, ge=1000, le=20000)
    collector_excerpt_chars: int = Field(default=1200, ge=500, le=4000)
    evidence_quote_limit: int = Field(default=4, ge=1, le=20)
    evidence_quote_chars: int = Field(default=700, ge=100, le=2000)
    news_result_limit: int = Field(default=2, ge=1, le=5)
    source_max_chars: int = Field(default=8000, ge=500, le=16000)
    worker_poll_seconds: float = Field(default=2, ge=0.1, le=30)
    worker_lease_seconds: int = Field(default=120, ge=30, le=600)
    stream_poll_seconds: float = Field(default=1, ge=0.1, le=10)

    @field_validator("frontend_origin")
    @classmethod
    def validate_origin(cls, value: HttpUrl) -> HttpUrl:
        if value.path not in (None, "/") or value.query or value.fragment:
            raise ValueError("FRONTEND_ORIGIN must be an origin without a path or query")
        if value.username or value.password:
            raise ValueError("FRONTEND_ORIGIN cannot contain credentials")
        return value

    @model_validator(mode="after")
    def validate_tracing(self) -> "Settings":
        if self.langsmith_tracing and not self.langsmith_api_key:
            raise ValueError("LANGSMITH_API_KEY is required when tracing is enabled")
        return self

    def model_for(self, node: str) -> str:
        fields = {
            "parser": self.groq_model_parser,
            "source_collector": self.groq_model_source_collector,
            "link_check": self.groq_model_link_check,
            "analyst": self.groq_model_analyst,
            "matcher": self.groq_model_matcher,
            "writer": self.groq_model_writer,
            "verifier": self.groq_model_verifier,
            "eval_judge": self.groq_model_eval_judge,
        }
        return fields[node]


@lru_cache
def get_settings() -> Settings:
    return Settings()
