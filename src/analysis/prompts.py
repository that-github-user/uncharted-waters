"""Prompt templates for LLM landscape analysis."""

SYSTEM_PROMPT = """\
You are an expert research analyst specializing in defense research landscape assessment. \
Your task is to analyze the existing publication landscape in the Defense Technical Information \
Center (DTIC) database for a given research topic, identifying coverage patterns, gaps, and \
opportunities.

You must provide a structured assessment with one of four landscape categories:

- **UNIQUE**: Open landscape — no substantially similar work exists in the DTIC database. \
The topic area has wide opportunity for new research.
- **NAVY_UNIQUE**: Branch opportunity — similar work exists in DTIC, but it was funded by \
other military branches (Army, Air Force, DARPA, etc.) — not by the branch of interest. \
There is an opportunity for the specified branch to invest in this area.
- **AT_RISK**: Well covered — the topic area is already well covered in DTIC, potentially \
including work funded by the branch of interest.
- **NEEDS_REVIEW**: Mixed coverage — the evidence is ambiguous. There are partial overlaps \
that require human expert judgment to fully assess the landscape.

Be thorough but fair. Consider that two papers can share a broad topic area while pursuing \
genuinely different research questions, methods, or applications. Focus on substantive \
relevance, not superficial keyword matches."""


def build_analysis_prompt(
    proposal_title: str,
    proposal_abstract: str,
    proposal_keywords: list[str],
    proposal_branch: str,
    additional_context: str,
    publications_text: str,
    precomputed_metrics: str = "",
) -> str:
    """Build the user prompt for landscape analysis."""
    keywords_str = ", ".join(proposal_keywords) if proposal_keywords else "None provided"

    metrics_section = ""
    if precomputed_metrics:
        metrics_section = f"""
---

## Pre-Computed Metrics

The following landscape assessment, confidence, and per-publication relevance ratings have \
been computed deterministically from the cosine similarity scores. Reference these in your \
narrative text — do NOT override them.

{precomputed_metrics}
"""

    return f"""\
## Research Topic Under Analysis

**Title:** {proposal_title}
**Topic Description:** {proposal_abstract}
**Keywords:** {keywords_str}
**Branch of Interest:** {proposal_branch}
**Research Focus:** {additional_context or "None provided"}

---

## Existing DTIC Publications

{publications_text}
{metrics_section}
---

## Instructions

Analyze the research topic against the publications above and provide your landscape \
assessment in the following JSON format. Do NOT wrap in markdown code fences.

Additionally, assess whether this research topic is inherently specific to the branch of \
interest's mission, platforms, or facilities (e.g., Navy shipyard maintenance is inherently \
Navy-specific), or whether it represents a universal defense problem applicable across \
branches (e.g., a novel ML architecture for predictive maintenance could serve any branch). \
Consider arguments for both sides before making your determination.

{{
  "executive_summary": "2-3 paragraph summary of the research landscape and gap analysis",
  "comparisons": [
    {{
      "publication_id": "pub id",
      "title": "pub title",
      "similarity_assessment": "1-2 sentence description of how this pub relates to the topic",
      "key_differences": ["difference 1", "difference 2"],
      "key_overlaps": ["overlap 1", "overlap 2"]
    }}
  ],
  "points_of_differentiation": [
    "Identified gaps and opportunities in the existing landscape (list 3-5 points)"
  ],
  "recommendations": [
    "Actionable recommendations for pursuing research in this area (list 2-4 points)"
  ],
  "branch_relevance": {{
    "determination": "branch_specific or cross_branch",
    "reasoning": "1-2 sentences explaining why this topic is or is not inherently tied to the branch of interest"
  }}
}}

Evaluate EVERY publication listed above. Be specific about relevance and gaps. \
Consider the branch of interest for branch opportunity determinations."""


def format_publications_for_prompt(
    publications: list[dict],
) -> str:
    """Format ranked publications into text for the LLM prompt."""
    if not publications:
        return "No similar publications were found in the DTIC database."

    parts = []
    for i, pub in enumerate(publications, 1):
        branches = ", ".join(pub.get("detected_branches", [])) or "Unknown"
        abstract = pub.get("abstract", "No abstract available")
        parts.append(
            f"### Publication {i} (Similarity: {pub['similarity_score']:.3f})\n"
            f"- **ID:** {pub['id']}\n"
            f"- **Title:** {pub['title']}\n"
            f"- **Year:** {pub.get('pub_year', 'Unknown')}\n"
            f"- **Authors:** {pub.get('authors', 'Unknown')}\n"
            f"- **Journal:** {pub.get('journal_title', 'Unknown')}\n"
            f"- **Funding Branches:** {branches}\n"
            f"- **Times Cited:** {pub.get('times_cited', 0)}\n"
            f"- **Abstract:** {abstract}\n"
        )
    return "\n".join(parts)
