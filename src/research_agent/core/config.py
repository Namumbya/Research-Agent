from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "research-agent"
    app_env: str = "local"
    log_level: str = "INFO"
    api_keys: str = Field(default="dev-local-key-change-me")

    database_url: str = (
        "postgresql+psycopg://research:research@localhost:5432/research_agent"
    )

    # Any OpenAI-compatible provider works (OpenAI, Gemini, Groq, DeepSeek, OpenRouter).
    # The legacy OPENAI_* names are still accepted.
    llm_api_key: str = Field(
        default="", validation_alias=AliasChoices("LLM_API_KEY", "OPENAI_API_KEY")
    )
    llm_model: str = Field(
        default="gpt-4o-mini", validation_alias=AliasChoices("LLM_MODEL", "OPENAI_MODEL")
    )
    llm_model_cheap: str = Field(
        default="gpt-4o-mini",
        validation_alias=AliasChoices("LLM_MODEL_CHEAP", "OPENAI_MODEL_CHEAP"),
    )
    llm_base_url: str | None = Field(
        default=None, validation_alias=AliasChoices("LLM_BASE_URL", "OPENAI_BASE_URL")
    )

    tavily_api_key: str = ""

    max_tool_calls: int = 12
    max_gather_iterations: int = 5
    max_run_minutes: int = 5
    max_search_results: int = 5
    max_page_fetches: int = 6
    page_fetch_chars: int = 6000
    verify_claims: bool = True

    @property
    def api_key_set(self) -> set[str]:
        return {key.strip() for key in self.api_keys.split(",") if key.strip()}


@lru_cache
def get_settings() -> Settings:
    return Settings()
