"""Orchestrates the full uniqueness analysis pipeline."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from src.analysis.llm_client import analyze_uniqueness
from src.analysis.report import generate_markdown_report, generate_step_summary
from src.config import DEFAULT_OUTPUT_DIR
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

    # Strategy 3: abstract excerpt (first ~200 chars of key content)
    abstract_words = proposal.abstract.split()
    if len(abstract_words) > 10:
        excerpt = " ".join(abstract_words[:40])
        queries.append(SearchQuery(text=excerpt, strategy="abstract_excerpt"))

    # Strategy 4: title + keywords combined
    if proposal.keywords:
        combined = proposal.title + " " + " ".join(proposal.keywords[:5])
        queries.append(SearchQuery(text=combined, strategy="combined"))

    return queries


async def run_pipeline(
    proposal: UserProposal,
    output_dir: str = DEFAULT_OUTPUT_DIR,
) -> tuple[AnalysisReport, str, str]:
    """Run the full uniqueness analysis pipeline.

    Returns:
        Tuple of (AnalysisReport, markdown_report_text, step_summary_text)
    """
    logger.info("Starting uniqueness analysis for: %s", proposal.title)

    # Step 1: Generate search queries
    queries = generate_search_queries(proposal)
    query_texts = [q.text for q in queries]
    logger.info("Generated %d search queries", len(queries))

    # Step 2: Search DTIC
    async with DimensionsScraper() as scraper:
        publications = await scraper.search_all(queries)
        logger.info("Found %d unique publications", len(publications))

        if not publications:
            logger.warning("No publications found — proposal may be unique by default")
            report = AnalysisReport(
                proposal=proposal,
                verdict=Verdict.UNIQUE,
                confidence=0.5,
                executive_summary=(
                    "No publications were found in the DTIC database matching "
                    "the search queries derived from this proposal. This may indicate "
                    "the research is highly novel, or that the search terms need "
                    "refinement. Manual verification is recommended."
                ),
                total_results_found=0,
                results_analyzed=0,
                search_queries_used=query_texts,
            )
            md = generate_markdown_report(report)
            summary = generate_step_summary(report)
            _save_report(md, proposal.title, output_dir)
            return report, md, summary

        # Step 3: Fetch full abstracts for top candidates
        publications = await scraper.fetch_full_abstracts_batch(publications)

    # Step 4: Rank by embedding similarity
    logger.info("Computing embedding similarity...")
    similarity_results = rank_publications(proposal, publications)
    logger.info("Top %d publications ranked", len(similarity_results))

    # Step 5: LLM analysis
    logger.info("Running LLM analysis...")
    report = await analyze_uniqueness(proposal, similarity_results, query_texts)

    # Update counts with pre-filter totals
    report.total_results_found = len(publications)

    # Step 6: Generate reports
    md = generate_markdown_report(report)
    summary = generate_step_summary(report)

    # Save to file
    _save_report(md, proposal.title, output_dir)

    logger.info("Analysis complete. Verdict: %s (confidence: %.0f%%)",
                report.verdict.value, report.confidence * 100)

    return report, md, summary


def _save_report(markdown: str, title: str, output_dir: str) -> Path:
    """Save the markdown report to the output directory."""
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    # Sanitize filename
    safe_title = "".join(c if c.isalnum() or c in " -_" else "" for c in title)
    safe_title = safe_title.strip().replace(" ", "_")[:80]
    filename = f"uniqueness_report_{safe_title}.md"
    filepath = Path(output_dir) / filename
    filepath.write_text(markdown, encoding="utf-8")
    logger.info("Report saved to %s", filepath)
    return filepath
