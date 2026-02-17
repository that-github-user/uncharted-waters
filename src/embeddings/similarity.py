"""Cosine similarity ranking for publications against a proposal."""

from __future__ import annotations

import numpy as np

from src.config import SIMILARITY_THRESHOLD, SIMILARITY_TOP_K
from src.models import Publication, SimilarityResult, UserProposal
from src.embeddings.encoder import encode_proposal, encode_publications


class RankingResult:
    """Container for similarity ranking output including embeddings for visualization."""

    def __init__(
        self,
        results: list[SimilarityResult],
        proposal_embedding: np.ndarray,
        pub_embeddings: np.ndarray,
        publications: list[Publication],
        similarities: np.ndarray,
        threshold: float,
    ):
        self.results = results
        self.proposal_embedding = proposal_embedding
        self.pub_embeddings = pub_embeddings
        self.publications = publications
        self.similarities = similarities
        self.threshold = threshold


def rank_publications(
    proposal: UserProposal,
    publications: list[Publication],
    top_k: int = SIMILARITY_TOP_K,
    threshold: float = SIMILARITY_THRESHOLD,
) -> RankingResult:
    """Rank publications by cosine similarity to the proposal.

    Returns a RankingResult with the top_k publications above the similarity
    threshold (sorted descending) and raw embeddings for visualization.
    """
    if not publications:
        return RankingResult([], np.array([]), np.array([]), [], np.array([]), threshold)

    proposal_embedding = encode_proposal(proposal)
    pub_embeddings = encode_publications(publications)

    if pub_embeddings.size == 0:
        return RankingResult([], proposal_embedding, pub_embeddings, publications, np.array([]), threshold)

    # Cosine similarity — embeddings are already L2-normalized
    similarities = np.dot(pub_embeddings, proposal_embedding)

    # Build results and filter
    results: list[SimilarityResult] = []
    for idx in range(len(publications)):
        sim_score = float(similarities[idx])
        if sim_score >= threshold:
            results.append(
                SimilarityResult(
                    publication=publications[idx],
                    similarity_score=sim_score,
                )
            )

    # Sort by descending similarity
    results.sort(key=lambda r: r.similarity_score, reverse=True)

    # Take top_k and assign ranks
    results = results[:top_k]
    for i, result in enumerate(results):
        result.rank = i + 1

    return RankingResult(results, proposal_embedding, pub_embeddings, publications, similarities, threshold)
