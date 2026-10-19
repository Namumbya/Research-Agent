"""Run the golden briefs against the live graph (needs LLM and Tavily keys).

    python -m research_agent.evals.run [name ...]

Exits non-zero if any brief fails its expectations.
"""

from __future__ import annotations

import asyncio
import json
import sys
import uuid
from pathlib import Path

from research_agent.agent.graph import build_research_graph
from research_agent.evals.checks import check_report

GOLDEN_PATH = Path(__file__).with_name("golden_briefs.json")


async def run_case(case: dict) -> list[str]:
    graph = build_research_graph()
    state = await graph.ainvoke(
        {
            "run_id": str(uuid.uuid4()),
            "brief": case["brief"],
            "plan": [],
            "evidence": [],
            "report": None,
            "report_markdown": None,
            "error": None,
            "meta": {},
            "current_node": "start",
        }
    )
    if state.get("error") or not state.get("report"):
        return [f"run failed: {state.get('error')}"]
    evidence_urls = {e["url"] for e in state.get("evidence") or [] if e.get("url")}
    return check_report(state["report"], evidence_urls, case.get("expect", {}))


async def main(names: list[str]) -> int:
    cases = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    if names:
        cases = [c for c in cases if c["name"] in names]
    failed = 0
    for case in cases:
        failures = await run_case(case)
        print(f"{'FAIL' if failures else 'PASS'}  {case['name']}")
        for failure in failures:
            print(f"      - {failure}")
        failed += bool(failures)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:])))
