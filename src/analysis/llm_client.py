"""Claude API wrapper for landscape analysis."""

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
from src.analysis.scoring import (
    compute_confidence,
    compute_overlap_rating,
    compute_verdict,
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


def _build_precomputed_metrics_text(
    similarity_results: list[SimilarityResult],
    overlap_ratings: list[str],
    verdict: Verdict,
    confidence: float,
) -> str:
    """Format pre-computed metrics as text for the LLM prompt."""
    lines = [
        f"**Landscape Assessment:** {verdict.value}",
        f"**Confidence:** {confidence:.2f}",
        "",
        "**Per-Publication Relevance Ratings:**",
    ]
    for sr, rating in zip(similarity_results, overlap_ratings):
        lines.append(
            f"- {sr.publication.id} ({sr.publication.title[:60]}): "
            f"similarity={sr.similarity_score:.3f} → relevance={rating}"
        )
    return "\n".join(lines)


async def analyze_uniqueness(
    proposal: UserProposal,
    similarity_results: list[SimilarityResult],
    search_queries_used: list[str],
) -> AnalysisReport:
    """Send the topic and similar publications to Claude for landscape analysis."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable is required")

    # Compute deterministic metrics before LLM call
    overlap_ratings = [
        compute_overlap_rating(r.similarity_score) for r in similarity_results
    ]
    verdict = compute_verdict(
        similarity_results, overlap_ratings, proposal.military_branch.value
    )
    confidence = compute_confidence(similarity_results, overlap_ratings, verdict)

    logger.info(
        "Computed metrics: verdict=%s confidence=%.2f overlaps=%s",
        verdict.value, confidence,
        {r: overlap_ratings.count(r) for r in ("high", "medium", "low")},
    )

    pub_dicts = _results_to_prompt_dicts(similarity_results)
    publications_text = format_publications_for_prompt(pub_dicts)

    precomputed_text = _build_precomputed_metrics_text(
        similarity_results, overlap_ratings, verdict, confidence
    )

    user_prompt = build_analysis_prompt(
        proposal_title=proposal.title,
        proposal_abstract=proposal.topic_description or proposal.abstract,
        proposal_keywords=proposal.keywords,
        proposal_branch=proposal.military_branch.value,
        additional_context=proposal.additional_context,
        publications_text=publications_text,
        precomputed_metrics=precomputed_text,
    )

    logger.info("Sending analysis request to Claude (%s)", LLM_MODEL)

    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model=LLM_MODEL,
        max_tokens=LLM_MAX_TOKENS,
        temperature=0.7,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )

    response_text = message.content[0].text
    logger.info("Received LLM response (%d chars)", len(response_text))

    try:
        parsed = _parse_llm_response(response_text)
    except json.JSONDecodeError as e:
        logger.error("Failed to parse LLM response as JSON: %s", e)
        # Return report with computed metrics even on parse failure
        return AnalysisReport(
            proposal=proposal,
            verdict=verdict,
            confidence=confidence,
            executive_summary=f"LLM response could not be parsed. Raw response:\n\n{response_text}",
            total_results_found=len(similarity_results),
            results_analyzed=len(similarity_results),
            search_queries_used=search_queries_used,
        )

    # Build lookup from similarity results for enrichment
    # Use multiple key formats: exact ID, numeric-only, lowercase title
    id_lookup: dict[str, SimilarityResult] = {}
    title_lookup: dict[str, SimilarityResult] = {}
    for sr in similarity_results:
        full_id = sr.publication.id.strip()
        id_lookup[full_id] = sr
        # Strip "pub." prefix → index by bare numeric ID
        bare_id = full_id.replace("pub.", "").strip()
        if bare_id:
            id_lookup[bare_id] = sr
        # Case-insensitive, stripped title lookup
        norm_title = sr.publication.title.strip().lower()
        if norm_title:
            title_lookup[norm_title] = sr

    # Build index from similarity results to overlap ratings
    sr_overlap_map: dict[str, str] = {}
    for sr, rating in zip(similarity_results, overlap_ratings):
        sr_overlap_map[sr.publication.id] = rating

    def _find_sr(pub_id: str, title: str) -> SimilarityResult | None:
        """Find matching SimilarityResult by ID or title."""
        pid = pub_id.strip()
        # Try exact ID
        if pid in id_lookup:
            return id_lookup[pid]
        # Try stripping "pub." from what LLM returned
        bare = pid.replace("pub.", "").strip()
        if bare in id_lookup:
            return id_lookup[bare]
        # Try adding "pub." prefix
        if f"pub.{bare}" in id_lookup:
            return id_lookup[f"pub.{bare}"]
        # Fallback: case-insensitive title match
        norm = title.strip().lower()
        if norm in title_lookup:
            return title_lookup[norm]
        # Brute-force: check if any SR ID contains the bare numeric part,
        # or if titles share substantial overlap
        for sr in similarity_results:
            sr_bare = sr.publication.id.replace("pub.", "").strip()
            if bare and sr_bare and bare == sr_bare:
                return sr
        for sr in similarity_results:
            sr_title = sr.publication.title.strip().lower()
            if norm and sr_title and (norm in sr_title or sr_title in norm):
                return sr
        return None

    # Build comparisons — use computed overlap_rating instead of LLM's
    comparisons = []
    for comp_data in parsed.get("comparisons", []):
        pub_id = comp_data.get("publication_id", "")
        comp_title = comp_data.get("title", "")
        sr = _find_sr(pub_id, comp_title)
        pub = sr.publication if sr else None

        if sr:
            logger.info("Enrichment hit: %r → score=%.3f url=%s", pub_id, sr.similarity_score, sr.publication.url[:60])
        else:
            # Dump all available IDs and titles for debugging
            available_ids = [s.publication.id for s in similarity_results[:5]]
            available_titles = [s.publication.title[:50] for s in similarity_results[:5]]
            logger.warning(
                "Enrichment miss: pub_id=%r title=%r — %d results available. "
                "Sample IDs: %s  Sample titles: %s",
                pub_id, comp_title[:60], len(similarity_results),
                available_ids, available_titles,
            )

        # Use computed overlap rating from scoring module
        computed_rating = sr_overlap_map.get(pub.id, "low") if pub else "low"

        comparisons.append(
            PublicationComparison(
                publication_id=pub_id,
                title=comp_data.get("title", ""),
                similarity_assessment=comp_data.get("similarity_assessment", ""),
                key_differences=comp_data.get("key_differences", []),
                key_overlaps=comp_data.get("key_overlaps", []),
                overlap_rating=computed_rating,
                url=pub.url if pub else "",
                pub_year=pub.pub_year if pub else None,
                funding_branches=[b.value for b in pub.detected_branches] if pub else [],
                similarity_score=sr.similarity_score if sr else 0.0,
            )
        )

    return AnalysisReport(
        proposal=proposal,
        verdict=verdict,
        confidence=confidence,
        executive_summary=parsed.get("executive_summary", ""),
        comparisons=comparisons,
        points_of_differentiation=parsed.get("points_of_differentiation", []),
        recommendations=parsed.get("recommendations", []),
        total_results_found=len(similarity_results),
        results_analyzed=len(similarity_results),
        search_queries_used=search_queries_used,
    )
