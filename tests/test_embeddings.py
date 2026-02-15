"""Tests for the embedding and similarity modules."""

import numpy as np
import pytest

from src.models import MilitaryBranch, Publication, SimilarityResult, UserProposal
from src.embeddings.encoder import format_proposal_text, format_publication_text


class TestTextFormatting:
    def test_format_proposal_basic(self):
        proposal = UserProposal(
            title="Test Title",
            abstract="Test abstract content",
            keywords=["kw1", "kw2"],
            military_branch=MilitaryBranch.NAVY,
        )
        text = format_proposal_text(proposal)
        assert "Test Title" in text
        assert "Test abstract content" in text
        assert "kw1" in text
        assert "kw2" in text

    def test_format_proposal_no_keywords(self):
        proposal = UserProposal(
            title="Title",
            abstract="Abstract",
        )
        text = format_proposal_text(proposal)
        assert "Title" in text
        assert "Abstract" in text

    def test_format_publication_with_abstract(self):
        pub = Publication(
            id="pub.1",
            title="Pub Title",
            full_abstract="Full abstract here",
            short_abstract="Short abstract",
        )
        text = format_publication_text(pub)
        assert "Pub Title" in text
        assert "Full abstract here" in text

    def test_format_publication_fallback_to_short_abstract(self):
        pub = Publication(
            id="pub.1",
            title="Pub Title",
            short_abstract="Short abstract only",
        )
        text = format_publication_text(pub)
        assert "Short abstract only" in text


class TestSimilarityRanking:
    """Test similarity ranking logic (mocking the actual encoding)."""

    def test_rank_empty_publications(self):
        from src.embeddings.similarity import rank_publications

        proposal = UserProposal(title="Test", abstract="Test abstract")
        results = rank_publications(proposal, [], top_k=5, threshold=0.0)
        assert results == []
