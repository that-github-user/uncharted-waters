"""Markdown report generation from analysis results."""

from __future__ import annotations

from datetime import datetime, timezone

from src.models import AnalysisReport, Verdict

VERDICT_BADGES = {
    Verdict.UNIQUE: "UNIQUE",
    Verdict.NAVY_UNIQUE: "NAVY UNIQUE",
    Verdict.AT_RISK: "AT RISK",
    Verdict.NEEDS_REVIEW: "NEEDS REVIEW",
}

VERDICT_DESCRIPTIONS = {
    Verdict.UNIQUE: "No substantially similar work was found in the DTIC database.",
    Verdict.NAVY_UNIQUE: "Similar work exists but was not funded by the Navy.",
    Verdict.AT_RISK: "Very similar existing work was found. Uniqueness may be difficult to demonstrate.",
    Verdict.NEEDS_REVIEW: "Partial overlaps found that require human expert judgment.",
}


def generate_markdown_report(report: AnalysisReport) -> str:
    """Generate a full Markdown report from the analysis results."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    badge = VERDICT_BADGES[report.verdict]
    desc = VERDICT_DESCRIPTIONS[report.verdict]

    lines = [
        f"# DTIC Uniqueness Assessment Report",
        f"",
        f"**Generated:** {now}",
        f"",
        f"---",
        f"",
        f"## Verdict: {badge}",
        f"",
        f"**Confidence:** {report.confidence:.0%}",
        f"",
        f"> {desc}",
        f"",
        f"---",
        f"",
        f"## Proposal Summary",
        f"",
        f"**Title:** {report.proposal.title}",
        f"",
        f"**Military Branch:** {report.proposal.military_branch.value}",
        f"",
        f"**Abstract:** {report.proposal.abstract}",
        f"",
    ]

    if report.proposal.keywords:
        lines.append(f"**Keywords:** {', '.join(report.proposal.keywords)}")
        lines.append("")

    lines.extend([
        f"---",
        f"",
        f"## Executive Summary",
        f"",
        f"{report.executive_summary}",
        f"",
        f"---",
        f"",
        f"## Search Statistics",
        f"",
        f"- **Queries Used:** {len(report.search_queries_used)}",
        f"- **Total Publications Found:** {report.total_results_found}",
        f"- **Publications Analyzed (Top Matches):** {report.results_analyzed}",
        f"",
    ])

    if report.search_queries_used:
        lines.append("### Search Queries")
        lines.append("")
        for i, q in enumerate(report.search_queries_used, 1):
            lines.append(f"{i}. {q}")
        lines.append("")

    if report.comparisons:
        lines.extend([
            f"---",
            f"",
            f"## Publication-by-Publication Comparison",
            f"",
        ])
        for comp in report.comparisons:
            threat_indicator = {"low": "Low", "medium": "Medium", "high": "HIGH"}.get(
                comp.threat_level, comp.threat_level
            )
            lines.extend([
                f"### {comp.title}",
                f"",
                f"**ID:** {comp.publication_id} | **Threat Level:** {threat_indicator}",
                f"",
                f"{comp.similarity_assessment}",
                f"",
            ])
            if comp.key_overlaps:
                lines.append("**Key Overlaps:**")
                for overlap in comp.key_overlaps:
                    lines.append(f"- {overlap}")
                lines.append("")
            if comp.key_differences:
                lines.append("**Key Differences:**")
                for diff in comp.key_differences:
                    lines.append(f"- {diff}")
                lines.append("")

    if report.points_of_differentiation:
        lines.extend([
            f"---",
            f"",
            f"## Points of Differentiation",
            f"",
        ])
        for point in report.points_of_differentiation:
            lines.append(f"- {point}")
        lines.append("")

    if report.recommendations:
        lines.extend([
            f"---",
            f"",
            f"## Recommendations",
            f"",
        ])
        for rec in report.recommendations:
            lines.append(f"- {rec}")
        lines.append("")

    lines.extend([
        f"---",
        f"",
        f"*This report was generated automatically by the DTIC Uniqueness Analyzer. "
        f"It is intended to assist with research proposal preparation and should be "
        f"reviewed by a subject matter expert before submission.*",
    ])

    return "\n".join(lines)


def generate_step_summary(report: AnalysisReport) -> str:
    """Generate a shorter summary for GitHub Actions step summary."""
    badge = VERDICT_BADGES[report.verdict]

    lines = [
        f"## DTIC Uniqueness Assessment: {badge}",
        f"",
        f"**Proposal:** {report.proposal.title}",
        f"",
        f"**Confidence:** {report.confidence:.0%}",
        f"",
        f"**Publications Found:** {report.total_results_found} | "
        f"**Analyzed:** {report.results_analyzed}",
        f"",
        f"### Summary",
        f"",
        f"{report.executive_summary}",
        f"",
    ]

    if report.recommendations:
        lines.append("### Key Recommendations")
        lines.append("")
        for rec in report.recommendations:
            lines.append(f"- {rec}")
        lines.append("")

    lines.append("*Full report available as workflow artifact.*")

    return "\n".join(lines)
