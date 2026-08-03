from functools import lru_cache

from pydantic import Field
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
        "postgresql+asyncpg://research:research@localhost:5432/research_agent"
    )

    openai_api_key: str = ""
    openai_model: str = "gpt-4o"
    openai_model_cheap: str = "gpt-4o-mini"
    openai_base_url: str | None = None

    tavily_api_key: str = ""

    max_tool_calls: int = 12
    max_gather_iterations: int = 5
    max_run_minutes: int = 5
    max_search_results: int = 5

    @property
    def api_key_set(self) -> set[str]:
        return {key.strip() for key in self.api_keys.split(",") if key.strip()}


@lru_cache
def get_settings() -> Settings:
    return Settings()
