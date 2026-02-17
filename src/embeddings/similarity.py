"""Cosine similarity ranking for publications against a proposal."""

from __future__ import annotations

import numpy as np

from src.config import (
    CONCEPT_MATCH_THRESHOLD,
    SIMILARITY_THRESHOLD,
    SIMILARITY_TOP_K,
)
from src.models import Publication, SimilarityResult, UserProposal
from src.embeddings.encoder import encode_concepts, encode_proposal, encode_publications


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


def _extract_concepts(proposal: UserProposal) -> list[str]:
    """Return user-provided keywords as concepts for IDF scoring.

    Only uses explicitly provided keywords — auto-extracting words from the
    title/description is redundant with the holistic embedding and produces
    generic terms (high document frequency → low IDF → low concept scores)
    that drag down composite scores via the combination formula.
    """
    if not proposal.keywords:
        return []
    return list(proposal.keywords)[:20]


def _compute_idf_concept_scores(
    proposal: UserProposal,
    pub_embeddings: np.ndarray,
) -> np.ndarray | None:
    """Compute IDF-weighted concept scores for each publication.

    Concepts are extracted from the proposal's keywords, title, and topic
    description. Each concept is encoded separately and matched against
    every publication. Keywords that appear in many publications (high
    document frequency) get low IDF weight — they're generic and not
    distinguishing. Keywords that appear in few publications get high IDF
    weight — they're specific and matching them is a strong signal.

    Returns an array of concept scores (one per publication), or None if
    no concepts can be extracted.
    """
    concepts = _extract_concepts(proposal)
    n_pubs = pub_embeddings.shape[0] if pub_embeddings.ndim > 1 else 0
    if not concepts or n_pubs == 0:
        return None

    concept_embeddings = encode_concepts(concepts)
    if concept_embeddings.size == 0:
        return None

    # concept_sims: (n_pubs, n_concepts) — per-keyword similarity for each pub
    concept_sims = pub_embeddings @ concept_embeddings.T

    # Document frequency: how many pubs match each keyword (binary threshold)
    matches = concept_sims >= CONCEPT_MATCH_THRESHOLD
    df = matches.sum(axis=0).astype(float)  # (n_concepts,)

    # IDF: log((N+1) / (df+1)) + 1  (smooth IDF, same as sklearn)
    idf = np.log((n_pubs + 1) / (df + 1)) + 1  # (n_concepts,)

    # Weighted concept score: continuous similarities weighted by IDF
    weighted = concept_sims * idf  # (n_pubs, n_concepts)
    concept_scores = weighted.sum(axis=1) / idf.sum()  # (n_pubs,) normalized

    return concept_scores


def rank_publications(
    proposal: UserProposal,
    publications: list[Publication],
    top_k: int = SIMILARITY_TOP_K,
    threshold: float = SIMILARITY_THRESHOLD,
) -> RankingResult:
    """Rank publications by composite similarity to the proposal.

    When keywords are provided, the score combines holistic embedding
    similarity with IDF-weighted per-keyword concept scores via weighted
    average (75% holistic, 25% concept). This lets concept coverage
    refine rankings without destroying strong embedding matches.

    When no keywords are provided, falls back to raw embedding similarity.

    Returns a RankingResult with the top_k publications above the similarity
    threshold (sorted descending) and raw embeddings for visualization.
    """
    if not publications:
        return RankingResult([], np.array([]), np.array([]), [], np.array([]), threshold)

    proposal_embedding = encode_proposal(proposal)
    pub_embeddings = encode_publications(publications)

    if pub_embeddings.size == 0:
        return RankingResult([], proposal_embedding, pub_embeddings, publications, np.array([]), threshold)

    # Holistic cosine similarity — embeddings are already L2-normalized
    raw_similarities = np.dot(pub_embeddings, proposal_embedding)

    # IDF-weighted concept scores (None if no keywords provided)
    concept_scores = _compute_idf_concept_scores(proposal, pub_embeddings)

    if concept_scores is not None:
        # Weighted average: holistic-dominant so concept coverage refines
        # but can't crush a strong embedding match
        clipped_raw = np.maximum(raw_similarities, 0)
        clipped_concept = np.maximum(concept_scores, 0)
        final_scores = 0.75 * clipped_raw + 0.25 * clipped_concept
    else:
        final_scores = raw_similarities

    # Build results using final scores for filtering/ranking
    results: list[SimilarityResult] = []
    for idx in range(len(publications)):
        score = float(final_scores[idx])
        if score >= threshold:
            results.append(
                SimilarityResult(
                    publication=publications[idx],
                    similarity_score=score,
                )
            )

    # Sort by descending score
    results.sort(key=lambda r: r.similarity_score, reverse=True)

    # Take top_k and assign ranks
    results = results[:top_k]
    for i, result in enumerate(results):
        result.rank = i + 1

    # Store raw similarities for landscape map visualization (not composite)
    return RankingResult(results, proposal_embedding, pub_embeddings, publications, raw_similarities, threshold)
