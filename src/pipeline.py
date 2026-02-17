"""Orchestrates the full research landscape analysis pipeline."""

from __future__ import annotations

import logging
import os
from pathlib import Path

import numpy as np

from src.analysis.llm_client import analyze_uniqueness
from src.analysis.report import generate_markdown_report, generate_step_summary
from src.config import DEFAULT_OUTPUT_DIR, SIMILARITY_THRESHOLD
from src.embeddings.similarity import rank_publications
from src.models import AnalysisReport, SearchQuery, UserProposal, Verdict
from src.scraper.dimensions import DimensionsScraper

logger = logging.getLogger(__name__)


def generate_search_queries(proposal: UserProposal) -> list[SearchQuery]:
    """Generate multiple search queries from the proposal for broader coverage."""
    queries: list[SearchQuery] = []

    # Strategy 1: direct title search
    queries.append(SearchQuery(text=proposal.title, strategy="title"))

    # Strategy 2: keyword search
    if proposal.keywords:
        queries.append(
            SearchQuery(
                text=" ".join(proposal.keywords),
                strategy="keywords",
            )
        )

    # Strategy 3: topic/abstract excerpt (first ~200 chars of key content)
    description = proposal.topic_description or proposal.abstract
    desc_words = description.split() if description else []
    if len(desc_words) > 10:
        excerpt = " ".join(desc_words[:40])
        queries.append(SearchQuery(text=excerpt, strategy="topic_excerpt"))

    # Strategy 4: title + keywords combined
    if proposal.keywords:
        combined = proposal.title + " " + " ".join(proposal.keywords[:5])
        queries.append(SearchQuery(text=combined, strategy="combined"))

    return queries


def _compute_landscape_map(ranking) -> list[dict]:
    """Project embeddings to 2D via PCA for the landscape scatter plot."""
    if ranking.proposal_embedding.size == 0 or ranking.pub_embeddings.size == 0:
        return []

    # Combine proposal + all publication embeddings
    all_embeddings = np.vstack([
        ranking.proposal_embedding.reshape(1, -1),
        ranking.pub_embeddings,
    ])

    # PCA to 2D (mean-center, then top-2 singular vectors)
    centered = all_embeddings - all_embeddings.mean(axis=0)
    try:
        _, _, Vt = np.linalg.svd(centered, full_matrices=False)
        projected = centered @ Vt[:2].T
    except np.linalg.LinAlgError:
        return []

    points = []

    # First point is the query
    points.append({
        "x": float(projected[0, 0]),
        "y": float(projected[0, 1]),
        "type": "query",
        "label": "Your Topic",
        "similarity": 1.0,
    })

    # Remaining points are publications
    for i, pub in enumerate(ranking.publications):
        sim = float(ranking.similarities[i]) if i < len(ranking.similarities) else 0.0
        above = sim >= ranking.threshold
        points.append({
            "x": float(projected[i + 1, 0]),
            "y": float(projected[i + 1, 1]),
            "type": "relevant" if above else "background",
            "label": pub.title[:60],
            "similarity": round(sim, 3),
        })

    return points


async def run_pipeline(
    proposal: UserProposal,
    output_dir: str = DEFAULT_OUTPUT_DIR,
) -> tuple[AnalysisReport, str, str, list[dict]]:
    """Run the full research landscape analysis pipeline.

    Returns:
        Tuple of (AnalysisReport, markdown_report_text, step_summary_text, landscape_map)
    """
    logger.info("Starting landscape analysis for: %s", proposal.title)

    # Step 1: Generate search queries
    queries = generate_search_queries(proposal)
    query_texts = [q.text for q in queries]
    logger.info("Generated %d search queries", len(queries))

    # Step 2: Search DTIC
    async with DimensionsScraper() as scraper:
        publications = await scraper.search_all(queries)
        logger.info("Found %d unique publications", len(publications))

        if not publications:
            logger.warning("No publications found — topic area appears open")
            report = AnalysisReport(
                proposal=proposal,
                verdict=Verdict.UNIQUE,
                confidence=0.5,
                executive_summary=(
                    "No publications were found in the DTIC database matching "
                    "the search queries derived from this topic. This suggests "
                    "an open landscape with wide opportunity, or that the search "
                    "terms need refinement. Manual verification is recommended."
                ),
                total_results_found=0,
                results_analyzed=0,
                search_queries_used=query_texts,
            )
            md = generate_markdown_report(report)
            summary = generate_step_summary(report)
            _save_report(md, proposal.title, output_dir)
            return report, md, summary, []

        # Step 3: Fetch full abstracts for top candidates
        publications = await scraper.fetch_full_abstracts_batch(publications)

    # Step 4: Rank by embedding similarity
    logger.info("Computing embedding similarity...")
    ranking = rank_publications(proposal, publications)
    similarity_results = ranking.results
    logger.info("Top %d publications ranked", len(similarity_results))

    # Step 5: LLM analysis
    logger.info("Running LLM analysis...")
    report = await analyze_uniqueness(proposal, similarity_results, query_texts)

    # Update counts with pre-filter totals
    report.total_results_found = len(publications)

    # Step 6: Generate reports
    md = generate_markdown_report(report)
    summary = generate_step_summary(report)

    # Step 7: Compute landscape map for visualization
    landscape_map = _compute_landscape_map(ranking)

    # Save to file
    _save_report(md, proposal.title, output_dir)

    logger.info("Analysis complete. Verdict: %s (confidence: %.0f%%)",
                report.verdict.value, report.confidence * 100)

    return report, md, summary, landscape_map


def _save_report(markdown: str, title: str, output_dir: str) -> Path:
    """Save the markdown report to the output directory."""
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    # Sanitize filename
    safe_title = "".join(c if c.isalnum() or c in " -_" else "" for c in title)
    safe_title = safe_title.strip().replace(" ", "_")[:80]
    filename = f"landscape_report_{safe_title}.md"
    filepath = Path(output_dir) / filename
    filepath.write_text(markdown, encoding="utf-8")
    logger.info("Report saved to %s", filepath)
    return filepath
