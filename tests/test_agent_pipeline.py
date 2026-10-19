import pytest

from research_agent.agent import nodes
from research_agent.agent.graph import build_research_graph
from research_agent.core.config import get_settings
from research_agent.evals.checks import check_report


class FakeLLM:
    """Stands in for a chat model; returns a canned object per structured-output schema."""

    def __init__(self, outputs):
        self.outputs = outputs

    def with_structured_output(self, schema):
        output = self.outputs[schema]

        class _Bound:
            async def ainvoke(self_inner, messages):
                return output

        return _Bound()


@pytest.fixture
def fake_pipeline(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("LLM_API_KEY", "test")

    async def fake_search(query, **kwargs):
        return [
            {"url": "https://a.example/pricing", "title": "A", "snippet": "snip a"},
            {"url": "https://b.example/news", "title": "B", "snippet": "snip b"},
        ]

    async def fake_fetch(url, max_chars=6000):
        return {"url": url, "title": None, "text": f"Full text of {url}: Pro plan costs $20."}

    llm = FakeLLM(
        {
            nodes.ResearchPlan: nodes.ResearchPlan(
                steps=[nodes.PlanStep(question="pricing?", query="acme pricing")]
            ),
            nodes.StructuredReport: nodes.StructuredReport(
                title="Acme",
                executive_summary="Summary",
                sections=[
                    nodes.ReportSection(
                        heading="Pricing",
                        content="Pro plan costs $20.",
                        citation_urls=["https://a.example/pricing", "https://invented.example/x"],
                    ),
                    nodes.ReportSection(heading="Positioning", content="Premium.", citation_urls=[]),
                ],
            ),
            nodes.VerificationResult: nodes.VerificationResult(
                verdicts=[nodes.SectionVerdict(index=0, supported=True)]
            ),
        }
    )
    monkeypatch.setattr(nodes, "tavily_search", fake_search)
    monkeypatch.setattr(nodes, "fetch_url", fake_fetch)
    monkeypatch.setattr(nodes, "get_chat_model", lambda cheap=False: llm)
    yield
    get_settings.cache_clear()


async def _run(brief):
    graph = build_research_graph()
    return await graph.ainvoke(
        {"run_id": "r1", "brief": brief, "plan": [], "evidence": [], "meta": {}}
    )


async def test_pipeline_fetches_pages_and_verifies(fake_pipeline):
    state = await _run({"topic": "Acme competitor snapshot", "depth": "quick"})

    assert state["error"] is None
    assert state["meta"]["pages_fetched"] == 2
    assert all(item.get("content") for item in state["evidence"])

    sections = {s["heading"]: s for s in state["report"]["sections"]}
    # invented URL stripped, real one kept
    assert [c["url"] for c in sections["Pricing"]["citations"]] == ["https://a.example/pricing"]
    assert sections["Pricing"]["verified"] is True
    # no citation -> flagged
    assert sections["Positioning"]["verified"] is False
    assert any("Positioning" in r for r in state["report"]["risks_or_unknowns"])
    assert "Unverified" in state["report_markdown"]


async def test_seed_urls_are_fetched(fake_pipeline):
    state = await _run(
        {"topic": "Acme competitor snapshot", "depth": "quick", "seed_urls": ["https://seed.example/"]}
    )
    assert "https://seed.example/" in {e["url"] for e in state["evidence"]}


async def test_fetch_failure_does_not_fail_run(fake_pipeline, monkeypatch):
    async def boom(url, max_chars=6000):
        raise RuntimeError("blocked")

    monkeypatch.setattr(nodes, "fetch_url", boom)
    state = await _run({"topic": "Acme competitor snapshot", "depth": "quick"})
    assert state["error"] is None
    assert state["meta"]["pages_fetched"] == 0
    assert state["report"] is not None


def test_check_report_flags_problems():
    report = {
        "executive_summary": "x",
        "sections": [
            {"heading": "Pricing", "citations": [{"url": "https://ghost.example"}], "verified": False}
        ],
        "sources": [],
    }
    failures = check_report(
        report,
        {"https://real.example"},
        {"required_headings": ["pricing", "news"], "min_citations": 2, "max_unverified_ratio": 0.5},
    )
    joined = " ".join(failures)
    assert "news" in joined
    assert "expected >= 2" in joined
    assert "ghost.example" in joined
    assert "unverified" in joined
