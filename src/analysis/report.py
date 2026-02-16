"""Markdown report generation from analysis results."""

from __future__ import annotations

import re
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


def _ensure_paragraph_breaks(text: str) -> str:
    """Convert single newlines between non-empty lines to double newlines.

    CommonMark treats single \\n as a soft break (space), so LLM output
    that uses single newlines between paragraphs renders as one blob.
    """
    lines = text.split("\n")
    result: list[str] = []
    for i, line in enumerate(lines):
        result.append(line)
        # If this line and the next are both non-empty, insert an extra blank line
        if (
            i < len(lines) - 1
            and line.strip()
            and lines[i + 1].strip()
            # Don't double-break if there's already a blank line
            and not line.strip().startswith("-")
            and not lines[i + 1].strip().startswith("-")
        ):
            result.append("")
    return "\n".join(result)


def _slugify(text: str) -> str:
    """Create a URL-safe anchor slug from a title."""
    slug = text.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    return slug.strip("-")


def _add_executive_summary_links(
    summary_text: str,
    title_slug_pairs: list[tuple[str, str]],
) -> str:
    """Find exact title matches in the executive summary and wrap them as anchor links.

    Sorts by title length descending to avoid substring conflicts.
    """
    # Sort longest first so "Foo Bar Baz" is matched before "Foo Bar"
    pairs = sorted(title_slug_pairs, key=lambda p: len(p[0]), reverse=True)
    for title, slug in pairs:
        # Only link the first occurrence, avoid double-linking
        if title in summary_text and f"[{title}]" not in summary_text:
            summary_text = summary_text.replace(
                title, f"[{title}](#{slug})", 1
            )
    return summary_text


def generate_markdown_report(report: AnalysisReport) -> str:
    """Generate a full Markdown report from the analysis results."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    badge = VERDICT_BADGES[report.verdict]
    desc = VERDICT_DESCRIPTIONS[report.verdict]

    # Pre-compute title/slug pairs for anchor linking
    title_slug_pairs = [
        (comp.title, _slugify(comp.title)) for comp in report.comparisons
    ]

    # Process executive summary: paragraph breaks + anchor links
    exec_summary = _ensure_paragraph_breaks(report.executive_summary)
    exec_summary = _add_executive_summary_links(exec_summary, title_slug_pairs)

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
        f"{exec_summary}",
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
            overlap_indicator = {"low": "Low", "medium": "Medium", "high": "HIGH"}.get(
                comp.overlap_rating, comp.overlap_rating
            )
            slug = _slugify(comp.title)
            assessment = _ensure_paragraph_breaks(comp.similarity_assessment)

            # Title as hyperlink if URL is available, otherwise plain text
            title_display = (
                f"[{comp.title}]({comp.url})" if comp.url else comp.title
            )

            # Build metadata line: ID | Year | Funding | Overlap Rating | Similarity
            id_display = (
                f"[{comp.publication_id}]({comp.url})"
                if comp.url else comp.publication_id
            )
            meta_parts = [f"**ID:** {id_display}"]
            if comp.pub_year:
                meta_parts.append(f"**Year:** {comp.pub_year}")
            if comp.funding_branches:
                branches_str = ", ".join(
                    b.replace("_", " ").title() for b in comp.funding_branches
                )
                meta_parts.append(f"**Funding:** {branches_str}")
            meta_parts.append(f"**Overlap Rating:** {overlap_indicator}")
            if comp.similarity_score > 0:
                meta_parts.append(f"**Similarity:** {comp.similarity_score:.3f}")
            meta_line = " | ".join(meta_parts)

            lines.extend([
                f'<a id="{slug}"></a>',
                f"",
                f"### {title_display}",
                f"",
                f"{meta_line}",
                f"",
                f"{assessment}",
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
    exec_summary = _ensure_paragraph_breaks(report.executive_summary)

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
        f"{exec_summary}",
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
