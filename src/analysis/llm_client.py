"""Claude API wrapper for uniqueness analysis."""

from __future__ import annotations

import json
import logging
import os

import anthropic

from src.config import LLM_MAX_TOKENS, LLM_MODEL
from src.analysis.prompts import (
    SYSTEM_PROMPT,
    build_analysis_prompt,
    format_publications_for_prompt,
)
from src.models import (
    AnalysisReport,
    MilitaryBranch,
    PublicationComparison,
    SimilarityResult,
    UserProposal,
    Verdict,
)

logger = logging.getLogger(__name__)


def _results_to_prompt_dicts(results: list[SimilarityResult]) -> list[dict]:
    """Convert SimilarityResult list to dicts for prompt formatting."""
    pub_dicts = []
    for r in results:
        pub = r.publication
        pub_dicts.append({
            "id": pub.id,
            "title": pub.title,
            "abstract": pub.best_abstract,
            "pub_year": pub.pub_year,
            "authors": ", ".join(pub.authors) if pub.authors else "Unknown",
            "journal_title": pub.journal_title,
            "detected_branches": [b.value for b in pub.detected_branches],
            "times_cited": pub.times_cited,
            "similarity_score": r.similarity_score,
        })
    return pub_dicts


def _parse_llm_response(text: str) -> dict:
    """Parse the JSON response from the LLM, handling potential markdown fences."""
    cleaned = text.strip()
    # Remove markdown code fences if present
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        # Remove first and last lines (fences)
        lines = [l for l in lines if not l.strip().startswith("```")]
        cleaned = "\n".join(lines)
    return json.loads(cleaned)


async def analyze_uniqueness(
    proposal: UserProposal,
    similarity_results: list[SimilarityResult],
    search_queries_used: list[str],
) -> AnalysisReport:
    """Send the proposal and similar publications to Claude for analysis."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable is required")

    pub_dicts = _results_to_prompt_dicts(similarity_results)
    publications_text = format_publications_for_prompt(pub_dicts)

    user_prompt = build_analysis_prompt(
        proposal_title=proposal.title,
        proposal_abstract=proposal.abstract,
        proposal_keywords=proposal.keywords,
        proposal_branch=proposal.military_branch.value,
        additional_context=proposal.additional_context,
        publications_text=publications_text,
    )

    logger.info("Sending analysis request to Claude (%s)", LLM_MODEL)

    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model=LLM_MODEL,
        max_tokens=LLM_MAX_TOKENS,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )

    response_text = message.content[0].text
    logger.info("Received LLM response (%d chars)", len(response_text))

    try:
        parsed = _parse_llm_response(response_text)
    except json.JSONDecodeError as e:
        logger.error("Failed to parse LLM response as JSON: %s", e)
        # Return a NEEDS_REVIEW report with the raw response
        return AnalysisReport(
            proposal=proposal,
            verdict=Verdict.NEEDS_REVIEW,
            confidence=0.0,
            executive_summary=f"LLM response could not be parsed. Raw response:\n\n{response_text}",
            total_results_found=len(similarity_results),
            results_analyzed=len(similarity_results),
            search_queries_used=search_queries_used,
        )

    # Build comparisons
    comparisons = []
    for comp_data in parsed.get("comparisons", []):
        comparisons.append(
            PublicationComparison(
                publication_id=comp_data.get("publication_id", ""),
                title=comp_data.get("title", ""),
                similarity_assessment=comp_data.get("similarity_assessment", ""),
                key_differences=comp_data.get("key_differences", []),
                key_overlaps=comp_data.get("key_overlaps", []),
                threat_level=comp_data.get("threat_level", "low"),
            )
        )

    return AnalysisReport(
        proposal=proposal,
        verdict=Verdict(parsed.get("verdict", "NEEDS_REVIEW")),
        confidence=float(parsed.get("confidence", 0.0)),
        executive_summary=parsed.get("executive_summary", ""),
        comparisons=comparisons,
        points_of_differentiation=parsed.get("points_of_differentiation", []),
        recommendations=parsed.get("recommendations", []),
        total_results_found=len(similarity_results),
        results_analyzed=len(similarity_results),
        search_queries_used=search_queries_used,
    )
