from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from research_agent.agent.nodes import (
    finalize_report,
    gather_evidence,
    normalize_brief,
    plan_research,
    synthesize_report,
)
from research_agent.agent.state import ResearchState

_graph = None


def build_research_graph():
    graph = StateGraph(ResearchState)
    graph.add_node("normalize_brief", normalize_brief)
    graph.add_node("plan_research", plan_research)
    graph.add_node("gather_evidence", gather_evidence)
    graph.add_node("synthesize_report", synthesize_report)
    graph.add_node("finalize_report", finalize_report)

    graph.add_edge(START, "normalize_brief")
    graph.add_edge("normalize_brief", "plan_research")
    graph.add_edge("plan_research", "gather_evidence")
    graph.add_edge("gather_evidence", "synthesize_report")
    graph.add_edge("synthesize_report", "finalize_report")
    graph.add_edge("finalize_report", END)
    return graph.compile()


def get_research_graph():
    global _graph
    if _graph is None:
        _graph = build_research_graph()
    return _graph
