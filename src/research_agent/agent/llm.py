from langchain_openai import ChatOpenAI

from research_agent.core.config import get_settings


def get_chat_model(*, cheap: bool = False) -> ChatOpenAI:
    settings = get_settings()
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured")

    kwargs: dict = {
        "model": settings.openai_model_cheap if cheap else settings.openai_model,
        "api_key": settings.openai_api_key,
        "temperature": 0.2,
    }
    if settings.openai_base_url:
        kwargs["base_url"] = settings.openai_base_url
    return ChatOpenAI(**kwargs)
