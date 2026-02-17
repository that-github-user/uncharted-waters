"""Cosine similarity ranking for publications against a proposal."""

from __future__ import annotations

import re

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


_STOPWORDS = frozenset({
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
    "being", "have", "has", "had", "do", "does", "did", "will", "would",
    "could", "should", "may", "might", "can", "shall", "not", "no",
    "its", "it", "this", "that", "these", "those", "their", "them",
    "they", "we", "our", "you", "your", "he", "she", "his", "her",
    "my", "me", "i", "what", "which", "who", "whom", "how", "where",
    "when", "why", "if", "then", "than", "so", "as", "up", "out",
    "about", "into", "over", "after", "before", "between", "under",
    "above", "below", "all", "each", "every", "both", "few", "more",
    "most", "other", "some", "such", "only", "very", "also", "just",
    "using", "used", "use", "based", "provide", "provided", "including",
    "across", "through", "during", "among", "via", "new", "like",
})


def _extract_concepts(proposal: UserProposal) -> list[str]:
    """Extract concepts from the proposal's keywords, title, and description.

    Starts with user-provided keywords (multi-word phrases preserved), then
    extracts significant words from the topic description and title. Returns
    up to 20 concepts for IDF scoring.
    """
    concepts: list[str] = list(proposal.keywords or [])
    seen = set(w.lower() for kw in concepts for w in kw.split())

    for text in [proposal.topic_description or proposal.abstract, proposal.title]:
        if not text:
            continue
        words = re.findall(r"\b[a-zA-Z0-9][\w-]*\b", text.lower())
        for w in words:
            if w not in _STOPWORDS and len(w) >= 3 and w not in seen:
                concepts.append(w)
                seen.add(w)

    return concepts[:20]


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
    similarity with IDF-weighted per-keyword concept scores via geometric
    mean. This ensures a publication must cover *most* of the proposal's
    concepts to score highly — general survey papers matching one keyword
    are penalized without any arbitrary weight constants.

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
        # Geometric mean: sqrt(holistic * concept)
        # Requires both overall relevance AND specific concept coverage
        clipped_raw = np.maximum(raw_similarities, 0)
        clipped_concept = np.maximum(concept_scores, 0)
        final_scores = np.sqrt(clipped_raw * clipped_concept)
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
