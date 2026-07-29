import uvicorn
from fastapi import FastAPI

from research_agent import __version__
from research_agent.api.router import api_router
from research_agent.core.config import get_settings
from research_agent.core.logging import configure_logging


def create_app() -> FastAPI:
    configure_logging()
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        docs_url="/docs",
        redoc_url="/redoc",
    )
    app.include_router(api_router)
    return app


app = create_app()


def run() -> None:
    uvicorn.run(
        "research_agent.main:app",
        host="0.0.0.0",
        port=8000,
        reload=get_settings().app_env == "local",
    )


if __name__ == "__main__":
    run()
