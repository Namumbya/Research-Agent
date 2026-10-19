from __future__ import annotations

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph

from research_agent.agent.nodes import (
    cite_and_verify,
    fetch_pages,
    finalize_report,
    gather_evidence,
    normalize_brief,
    plan_research,
    synthesize_report,
)
from research_agent.agent.state import ResearchState

_graph = None
_graph_with_checkpoint = None


def build_research_graph(checkpointer: BaseCheckpointSaver | None = None):
    graph = StateGraph(ResearchState)
    graph.add_node("normalize_brief", normalize_brief)
    graph.add_node("plan_research", plan_research)
    graph.add_node("gather_evidence", gather_evidence)
    graph.add_node("fetch_pages", fetch_pages)
    graph.add_node("synthesize_report", synthesize_report)
    graph.add_node("cite_and_verify", cite_and_verify)
    graph.add_node("finalize_report", finalize_report)

    graph.add_edge(START, "normalize_brief")
    graph.add_edge("normalize_brief", "plan_research")
    graph.add_edge("plan_research", "gather_evidence")
    graph.add_edge("gather_evidence", "fetch_pages")
    graph.add_edge("fetch_pages", "synthesize_report")
    graph.add_edge("synthesize_report", "cite_and_verify")
    graph.add_edge("cite_and_verify", "finalize_report")
    graph.add_edge("finalize_report", END)
    return graph.compile(checkpointer=checkpointer)


def get_research_graph(checkpointer: BaseCheckpointSaver | None = None):
    """Return a compiled graph. Pass a checkpointer for durable runs."""
    global _graph, _graph_with_checkpoint

    if checkpointer is not None:
        if _graph_with_checkpoint is None:
            _graph_with_checkpoint = build_research_graph(checkpointer=checkpointer)
        return _graph_with_checkpoint

    if _graph is None:
        _graph = build_research_graph()
    return _graph


def reset_research_graph() -> None:
    global _graph, _graph_with_checkpoint
    _graph = None
    _graph_with_checkpoint = None
