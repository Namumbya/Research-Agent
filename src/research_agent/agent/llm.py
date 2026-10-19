from langchain_openai import ChatOpenAI

from research_agent.core.config import get_settings


def get_chat_model(*, cheap: bool = False) -> ChatOpenAI:
    """Build a chat model for any OpenAI-compatible endpoint (see LLM_BASE_URL)."""
    settings = get_settings()
    if not settings.llm_api_key:
        raise RuntimeError("LLM_API_KEY is not configured")

    kwargs: dict = {
        "model": settings.llm_model_cheap if cheap else settings.llm_model,
        "api_key": settings.llm_api_key,
        "temperature": 0.2,
    }
    if settings.llm_base_url:
        kwargs["base_url"] = settings.llm_base_url
    return ChatOpenAI(**kwargs)
