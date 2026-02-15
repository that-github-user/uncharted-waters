"""Cosine similarity ranking for publications against a proposal."""

from __future__ import annotations

import numpy as np

from src.config import SIMILARITY_THRESHOLD, SIMILARITY_TOP_K
from src.models import Publication, SimilarityResult, UserProposal
from src.embeddings.encoder import encode_proposal, encode_publications


def rank_publications(
    proposal: UserProposal,
    publications: list[Publication],
    top_k: int = SIMILARITY_TOP_K,
    threshold: float = SIMILARITY_THRESHOLD,
) -> list[SimilarityResult]:
    """Rank publications by cosine similarity to the proposal.

    Returns the top_k publications above the similarity threshold,
    sorted by descending similarity score.
    """
    if not publications:
        return []

    proposal_embedding = encode_proposal(proposal)
    pub_embeddings = encode_publications(publications)

    if pub_embeddings.size == 0:
        return []

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

    return results
