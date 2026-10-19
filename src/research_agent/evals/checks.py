from __future__ import annotations

from typing import Any


def check_report(
    report: dict[str, Any],
    evidence_urls: set[str],
    expectations: dict[str, Any],
) -> list[str]:
    """Return a list of failures for a report; an empty list means it passed.

    Expectations (all optional):
      required_headings: substrings that must appear in some section heading
      min_citations: minimum number of distinct cited source URLs
      max_unverified_ratio: max share of sections flagged verified=False
    """
    failures: list[str] = []
    sections = report.get("sections") or []

    headings = " | ".join(str(s.get("heading", "")).lower() for s in sections)
    for needle in expectations.get("required_headings", []):
        if needle.lower() not in headings:
            failures.append(f"missing section about '{needle}'")

    cited = {c["url"] for s in sections for c in s.get("citations") or [] if c.get("url")}
    minimum = expectations.get("min_citations", 0)
    if len(cited) < minimum:
        failures.append(f"only {len(cited)} distinct citations, expected >= {minimum}")

    invented = cited - evidence_urls
    if invented:
        failures.append(f"citations not in evidence: {sorted(invented)}")

    source_urls = {s.get("url") for s in report.get("sources") or []}
    stray = source_urls - evidence_urls
    if stray:
        failures.append(f"sources not in evidence: {sorted(u for u in stray if u)}")

    if sections:
        flagged = sum(1 for s in sections if s.get("verified") is False)
        ratio = flagged / len(sections)
        limit = expectations.get("max_unverified_ratio", 1.0)
        if ratio > limit:
            failures.append(f"{ratio:.0%} of sections unverified, limit {limit:.0%}")

    if not report.get("executive_summary"):
        failures.append("empty executive_summary")
    return failures
