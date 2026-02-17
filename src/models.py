"""Pydantic models for the DTIC Research Landscape Analyzer."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class MilitaryBranch(str, Enum):
    NAVY = "navy"
    ARMY = "army"
    AIR_FORCE = "air_force"
    DARPA = "darpa"
    DOD = "dod"
    MARINE_CORPS = "marine_corps"
    SPACE_FORCE = "space_force"
    UNKNOWN = "unknown"


class Verdict(str, Enum):
    UNIQUE = "UNIQUE"
    NAVY_UNIQUE = "NAVY_UNIQUE"
    AT_RISK = "AT_RISK"
    NEEDS_REVIEW = "NEEDS_REVIEW"


class UserProposal(BaseModel):
    """The user's research topic input."""

    title: str
    abstract: str = ""
    topic_description: str = ""
    keywords: list[str] = Field(default_factory=list)
    military_branch: MilitaryBranch = MilitaryBranch.NAVY
    additional_context: str = ""


class Publication(BaseModel):
    """A publication retrieved from DTIC Dimensions."""

    id: str
    title: str
    short_abstract: str = ""
    full_abstract: str = ""
    authors: list[str] = Field(default_factory=list)
    pub_year: int | None = None
    journal_title: str = ""
    doi: str = ""
    acknowledgements: str = ""
    times_cited: int = 0
    score: float = 0.0
    detected_branches: list[MilitaryBranch] = Field(default_factory=list)
    url: str = ""

    @property
    def best_abstract(self) -> str:
        return self.full_abstract or self.short_abstract


class SimilarityResult(BaseModel):
    """A publication with its computed similarity score."""

    publication: Publication
    similarity_score: float = 0.0
    rank: int = 0


class PublicationComparison(BaseModel):
    """LLM-generated comparison of a single publication against the proposal."""

    publication_id: str
    title: str
    similarity_assessment: str
    key_differences: list[str] = Field(default_factory=list)
    key_overlaps: list[str] = Field(default_factory=list)
    overlap_rating: str = "low"
    url: str = ""
    pub_year: int | None = None
    funding_branches: list[str] = Field(default_factory=list)
    similarity_score: float = 0.0


class AnalysisReport(BaseModel):
    """The complete uniqueness analysis report."""

    proposal: UserProposal
    verdict: Verdict
    confidence: float = Field(ge=0.0, le=1.0)
    executive_summary: str
    comparisons: list[PublicationComparison] = Field(default_factory=list)
    points_of_differentiation: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    total_results_found: int = 0
    results_analyzed: int = 0
    search_queries_used: list[str] = Field(default_factory=list)


class SearchQuery(BaseModel):
    """A generated search query for DTIC."""

    text: str
    strategy: str  # "title", "keywords", "topic_excerpt", "combined"
