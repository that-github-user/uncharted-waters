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

    # Strategy 2: topic description as a direct search query
    # Critical: the description may contain the actual publication title or
    # key phrases that differ from the user's title field.
    description = proposal.topic_description or proposal.abstract
    if description and description.strip().lower() != proposal.title.strip().lower():
        desc_words = description.split()
        if len(desc_words) <= 40:
            queries.append(SearchQuery(text=description, strategy="description"))
        else:
            excerpt = " ".join(desc_words[:40])
            queries.append(SearchQuery(text=excerpt, strategy="topic_excerpt"))

    # Strategy 3: keyword search
    if proposal.keywords:
        queries.append(
            SearchQuery(
                text=" ".join(proposal.keywords),
                strategy="keywords",
            )
        )

    # Strategy 4: title + keywords combined
    if proposal.keywords:
        combined = proposal.title + " " + " ".join(proposal.keywords[:5])
        queries.append(SearchQuery(text=combined, strategy="combined"))

    return queries


def _compute_landscape_map(ranking) -> list[dict]:
    """Radial layout: query at center, distance from center = 1 - similarity.

    Angular position is derived from PCA on publication embeddings so
    semantically similar publications cluster together around the ring.
    """
    if ranking.proposal_embedding.size == 0 or ranking.pub_embeddings.size == 0:
        return []

    pubs = ranking.publications
    sims = ranking.similarities
    n = len(pubs)
    if n == 0:
        return []

    # Angular position: PCA 1D on publication embeddings for semantic grouping
    pub_emb = ranking.pub_embeddings
    centered = pub_emb - pub_emb.mean(axis=0)
    try:
        _, _, Vt = np.linalg.svd(centered, full_matrices=False)
        proj_1d = centered @ Vt[0]
    except np.linalg.LinAlgError:
        proj_1d = np.zeros(n)

    # Sort by PCA score, assign evenly spaced angles
    order = np.argsort(proj_1d)
    angles = np.zeros(n)
    for rank_idx, idx in enumerate(order):
        angles[idx] = 2 * np.pi * rank_idx / n

    points = []

    # Query at center
    points.append({
        "x": 0.0,
        "y": 0.0,
        "type": "query",
        "label": "Your Topic",
        "similarity": 1.0,
    })

    # Publications: polar to cartesian
    for i, pub in enumerate(pubs):
        sim = float(sims[i]) if i < len(sims) else 0.0
        radius = 1.0 - max(sim, 0.0)
        angle = float(angles[i])
        above = sim >= ranking.threshold
        points.append({
            "x": round(float(radius * np.cos(angle)), 4),
            "y": round(float(radius * np.sin(angle)), 4),
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
