"""Tests for query generation and report formatting."""

import pytest

from src.models import (
    AnalysisReport,
    MilitaryBranch,
    PublicationComparison,
    UserProposal,
    Verdict,
)
from src.pipeline import generate_search_queries
from src.analysis.report import generate_markdown_report, generate_step_summary


class TestQueryGeneration:
    def test_generates_title_query(self):
        proposal = UserProposal(
            title="Underwater Navigation",
            abstract="This research explores navigation techniques.",
        )
        queries = generate_search_queries(proposal)
        titles = [q.strategy for q in queries]
        assert "title" in titles

    def test_generates_keyword_query(self):
        proposal = UserProposal(
            title="Test",
            abstract="Abstract",
            keywords=["AUV", "sonar"],
        )
        queries = generate_search_queries(proposal)
        titles = [q.strategy for q in queries]
        assert "keywords" in titles
        kw_query = next(q for q in queries if q.strategy == "keywords")
        assert "AUV" in kw_query.text

    def test_generates_abstract_excerpt(self):
        proposal = UserProposal(
            title="Test",
            abstract=" ".join(["word"] * 50),
        )
        queries = generate_search_queries(proposal)
        titles = [q.strategy for q in queries]
        assert "abstract_excerpt" in titles

    def test_no_abstract_excerpt_for_short_abstracts(self):
        proposal = UserProposal(
            title="Test",
            abstract="Short abstract",
        )
        queries = generate_search_queries(proposal)
        titles = [q.strategy for q in queries]
        assert "abstract_excerpt" not in titles


class TestReportGeneration:
    @pytest.fixture
    def sample_report(self):
        return AnalysisReport(
            proposal=UserProposal(
                title="Test Proposal",
                abstract="Test abstract",
                keywords=["kw1", "kw2"],
                military_branch=MilitaryBranch.NAVY,
            ),
            verdict=Verdict.NAVY_UNIQUE,
            confidence=0.85,
            executive_summary="This proposal appears to be Navy-unique.",
            comparisons=[
                PublicationComparison(
                    publication_id="pub.123",
                    title="Similar Work",
                    similarity_assessment="Moderately similar",
                    key_differences=["Different method"],
                    key_overlaps=["Same domain"],
                    overlap_rating="medium",
                )
            ],
            points_of_differentiation=["Novel approach X"],
            recommendations=["Emphasize method Y"],
            total_results_found=50,
            results_analyzed=10,
            search_queries_used=["query 1", "query 2"],
        )

    def test_markdown_report_contains_verdict(self, sample_report):
        md = generate_markdown_report(sample_report)
        assert "NAVY UNIQUE" in md
        assert "85%" in md

    def test_markdown_report_contains_proposal(self, sample_report):
        md = generate_markdown_report(sample_report)
        assert "Test Proposal" in md
        assert "Test abstract" in md

    def test_markdown_report_contains_comparisons(self, sample_report):
        md = generate_markdown_report(sample_report)
        assert "Similar Work" in md
        assert "Different method" in md
        assert "Same domain" in md

    def test_step_summary_is_shorter(self, sample_report):
        md = generate_markdown_report(sample_report)
        summary = generate_step_summary(sample_report)
        assert len(summary) < len(md)
        assert "NAVY UNIQUE" in summary

    def test_markdown_report_contains_disclaimer(self, sample_report):
        md = generate_markdown_report(sample_report)
        assert "subject matter expert" in md
