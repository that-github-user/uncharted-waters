"""Deterministic scoring functions for landscape assessment.

These replace LLM-generated metrics (verdict, confidence, overlap_rating)
with reproducible, rules-based computation from similarity scores and
branch data. The scoring maps naturally to the landscape framing:
UNIQUE = open landscape, NAVY_UNIQUE = branch opportunity,
AT_RISK = well covered, NEEDS_REVIEW = mixed coverage.
"""

from __future__ import annotations

from src.config import OVERLAP_HIGH_THRESHOLD, OVERLAP_MEDIUM_THRESHOLD
from src.models import MilitaryBranch, SimilarityResult, Verdict


def compute_overlap_rating(similarity_score: float) -> str:
    """Map a cosine similarity score to a categorical overlap rating.

    Thresholds are calibrated for embedding cosine similarity where
    the inclusion floor is already 0.30.
    """
    if similarity_score >= OVERLAP_HIGH_THRESHOLD:
        return "high"
    if similarity_score >= OVERLAP_MEDIUM_THRESHOLD:
        return "medium"
    return "low"


def compute_verdict(
    results: list[SimilarityResult],
    overlap_ratings: list[str],
    proposal_branch: str,
) -> Verdict:
    """Determine verdict from overlap distribution and branch matching.

    Rules (evaluated in order, first match wins):
      1. Any high-overlap pub (any branch) → AT_RISK (well covered / solved problem)
      2. Any medium-overlap pub shares the branch → NEEDS_REVIEW
      3. Any medium-overlap but none share the branch → NAVY_UNIQUE
      4. Only low overlaps or no results → UNIQUE
    """
    if not results:
        return Verdict.UNIQUE

    high_indices = [i for i, r in enumerate(overlap_ratings) if r == "high"]
    medium_indices = [i for i, r in enumerate(overlap_ratings) if r == "medium"]

    def _any_shares_branch(indices: list[int]) -> bool:
        for i in indices:
            pub_branches = [b.value for b in results[i].publication.detected_branches]
            if proposal_branch in pub_branches:
                return True
        return False

    if high_indices:
        return Verdict.AT_RISK

    if medium_indices:
        if _any_shares_branch(medium_indices):
            return Verdict.NEEDS_REVIEW
        return Verdict.NAVY_UNIQUE

    return Verdict.UNIQUE


def compute_confidence(
    results: list[SimilarityResult],
    overlap_ratings: list[str],
    verdict: Verdict,
) -> float:
    """Compute a confidence score (0.10–0.99) for the given verdict.

    Composite of a verdict-specific base score and a sample-size bonus.
    """
    if not results:
        return 0.90  # No results → high confidence in UNIQUE

    max_score = max(r.similarity_score for r in results)
    n_high = sum(1 for r in overlap_ratings if r == "high")
    n_medium = sum(1 for r in overlap_ratings if r == "medium")

    if verdict == Verdict.UNIQUE:
        # Higher confidence when max score is far below medium threshold
        gap = OVERLAP_MEDIUM_THRESHOLD - max_score
        # gap ranges from ~0.15 (score=0.30) to ~0.45 (score=0.0)
        # Map to 0.60–0.95
        base = 0.60 + min(gap / OVERLAP_MEDIUM_THRESHOLD, 1.0) * 0.35

    elif verdict == Verdict.AT_RISK:
        # More high-overlap results → higher confidence in AT_RISK
        # 1 high → 0.60, caps around 0.90 at 5+
        base = 0.60 + min(n_high / 5.0, 1.0) * 0.30

    elif verdict == Verdict.NAVY_UNIQUE:
        # Moderate base, scaled by clarity of overlap signals
        overlap_count = n_high + n_medium
        base = 0.65 + min(overlap_count / 8.0, 1.0) * 0.20

    else:  # NEEDS_REVIEW
        # Inherently uncertain
        base = 0.45 + min(n_medium / 6.0, 1.0) * 0.15

    # Sample size bonus: +0–5% based on result count (caps at 15)
    sample_bonus = min(len(results) / 15.0, 1.0) * 0.05

    confidence = base + sample_bonus
    confidence = round(max(0.10, min(0.99, confidence)), 2)
    return confidence
