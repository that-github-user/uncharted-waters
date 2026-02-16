"""Tests for query generation, report formatting, and deterministic scoring."""

import pytest

from src.models import (
    AnalysisReport,
    MilitaryBranch,
    Publication,
    PublicationComparison,
    SimilarityResult,
    UserProposal,
    Verdict,
)
from src.pipeline import generate_search_queries
from src.analysis.report import generate_markdown_report, generate_step_summary
from src.analysis.scoring import (
    compute_confidence,
    compute_overlap_rating,
    compute_verdict,
)


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


def _make_result(score: float, branches: list[MilitaryBranch] | None = None) -> SimilarityResult:
    """Helper to build a SimilarityResult with a given score and branches."""
    return SimilarityResult(
        publication=Publication(
            id=f"pub.{int(score * 1000)}",
            title=f"Test Publication {score}",
            short_abstract="Abstract text",
            detected_branches=branches or [],
        ),
        similarity_score=score,
    )


class TestScoring:
    def test_overlap_rating_high(self):
        assert compute_overlap_rating(0.65) == "high"

    def test_overlap_rating_medium(self):
        assert compute_overlap_rating(0.50) == "medium"

    def test_overlap_rating_low(self):
        assert compute_overlap_rating(0.35) == "low"

    def test_overlap_rating_at_boundaries(self):
        assert compute_overlap_rating(0.60) == "high"
        assert compute_overlap_rating(0.45) == "medium"
        assert compute_overlap_rating(0.4499) == "low"

    def test_verdict_at_risk(self):
        """High overlap + same branch → AT_RISK."""
        results = [_make_result(0.70, [MilitaryBranch.NAVY])]
        ratings = [compute_overlap_rating(r.similarity_score) for r in results]
        verdict = compute_verdict(results, ratings, "navy")
        assert verdict == Verdict.AT_RISK

    def test_verdict_navy_unique(self):
        """High overlap + different branch → NAVY_UNIQUE."""
        results = [_make_result(0.70, [MilitaryBranch.ARMY])]
        ratings = [compute_overlap_rating(r.similarity_score) for r in results]
        verdict = compute_verdict(results, ratings, "navy")
        assert verdict == Verdict.NAVY_UNIQUE

    def test_verdict_unique(self):
        """All low overlaps → UNIQUE."""
        results = [
            _make_result(0.35),
            _make_result(0.32),
        ]
        ratings = [compute_overlap_rating(r.similarity_score) for r in results]
        verdict = compute_verdict(results, ratings, "navy")
        assert verdict == Verdict.UNIQUE

    def test_verdict_needs_review(self):
        """Medium overlap + same branch → NEEDS_REVIEW."""
        results = [_make_result(0.50, [MilitaryBranch.NAVY])]
        ratings = [compute_overlap_rating(r.similarity_score) for r in results]
        verdict = compute_verdict(results, ratings, "navy")
        assert verdict == Verdict.NEEDS_REVIEW

    def test_verdict_empty_results(self):
        """No results → UNIQUE."""
        verdict = compute_verdict([], [], "navy")
        assert verdict == Verdict.UNIQUE

    def test_verdict_medium_different_branch(self):
        """Medium overlap + different branch → NAVY_UNIQUE."""
        results = [_make_result(0.50, [MilitaryBranch.AIR_FORCE])]
        ratings = [compute_overlap_rating(r.similarity_score) for r in results]
        verdict = compute_verdict(results, ratings, "navy")
        assert verdict == Verdict.NAVY_UNIQUE

    def test_confidence_deterministic(self):
        """Same inputs always produce the same confidence."""
        results = [
            _make_result(0.65, [MilitaryBranch.NAVY]),
            _make_result(0.50, [MilitaryBranch.ARMY]),
            _make_result(0.35),
        ]
        ratings = [compute_overlap_rating(r.similarity_score) for r in results]
        verdict = compute_verdict(results, ratings, "navy")
        c1 = compute_confidence(results, ratings, verdict)
        c2 = compute_confidence(results, ratings, verdict)
        c3 = compute_confidence(results, ratings, verdict)
        assert c1 == c2 == c3

    def test_confidence_range(self):
        """Output always in [0.10, 0.99]."""
        test_cases = [
            [],
            [_make_result(0.31)],
            [_make_result(0.50, [MilitaryBranch.NAVY])],
            [_make_result(0.70, [MilitaryBranch.NAVY])],
            [_make_result(0.70, [MilitaryBranch.ARMY])],
            [_make_result(s / 100, [MilitaryBranch.NAVY]) for s in range(30, 90, 5)],
        ]
        for results in test_cases:
            ratings = [compute_overlap_rating(r.similarity_score) for r in results]
            verdict = compute_verdict(results, ratings, "navy")
            conf = compute_confidence(results, ratings, verdict)
            assert 0.10 <= conf <= 0.99, f"Confidence {conf} out of range for {verdict}"
