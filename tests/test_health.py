import pytest
from httpx import ASGITransport, AsyncClient

from research_agent.core.config import get_settings
from research_agent.main import create_app


@pytest.fixture
def app(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("API_KEYS", "test-key")
    get_settings.cache_clear()
    application = create_app()
    yield application
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_health(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_research_requires_api_key(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/v1/research/runs",
            json={"topic": "Competitor landscape for mid-market CRM tools"},
        )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_research_rejects_short_topic(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/v1/research/runs",
            headers={"X-API-Key": "test-key"},
            json={"topic": "short"},
        )
    assert response.status_code == 422
