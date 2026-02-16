"""Prompt templates for LLM uniqueness analysis."""

SYSTEM_PROMPT = """\
You are an expert research analyst specializing in defense research uniqueness assessment. \
Your task is to evaluate whether a proposed research project is sufficiently unique compared \
to existing publications in the Defense Technical Information Center (DTIC) database.

You must provide a structured assessment with one of four verdicts:

- **UNIQUE**: No substantially similar work exists in the DTIC database. The proposal addresses \
a genuinely novel research question or approach.
- **NAVY_UNIQUE**: Similar work exists in DTIC, but it was funded by other military branches \
(Army, Air Force, DARPA, etc.) — not by the Navy. The Navy does not appear to have funded \
equivalent research.
- **AT_RISK**: Very similar work already exists in DTIC, potentially including Navy-funded work. \
The proposal may have difficulty demonstrating uniqueness.
- **NEEDS_REVIEW**: The evidence is ambiguous. There are partial overlaps that require human \
expert judgment to assess.

Be thorough but fair. Consider that two papers can share a broad topic area while pursuing \
genuinely different research questions, methods, or applications. Focus on substantive overlap, \
not superficial keyword matches."""


def build_analysis_prompt(
    proposal_title: str,
    proposal_abstract: str,
    proposal_keywords: list[str],
    proposal_branch: str,
    additional_context: str,
    publications_text: str,
    precomputed_metrics: str = "",
) -> str:
    """Build the user prompt for uniqueness analysis."""
    keywords_str = ", ".join(proposal_keywords) if proposal_keywords else "None provided"

    metrics_section = ""
    if precomputed_metrics:
        metrics_section = f"""
---

## Pre-Computed Metrics

The following verdict, confidence, and per-publication overlap ratings have been \
computed deterministically from the cosine similarity scores. Reference these in your \
narrative text — do NOT override them.

{precomputed_metrics}
"""

    return f"""\
## Research Proposal Under Assessment

**Title:** {proposal_title}
**Abstract:** {proposal_abstract}
**Keywords:** {keywords_str}
**Sponsoring Branch:** {proposal_branch}
**Additional Context:** {additional_context or "None provided"}

---

## Similar Publications Found in DTIC

{publications_text}
{metrics_section}
---

## Instructions

Analyze the proposal against the publications above and provide your assessment in the \
following JSON format. Do NOT wrap in markdown code fences.

{{
  "executive_summary": "2-3 paragraph summary of the uniqueness assessment",
  "comparisons": [
    {{
      "publication_id": "pub id",
      "title": "pub title",
      "similarity_assessment": "1-2 sentence description of how this pub relates to the proposal",
      "key_differences": ["difference 1", "difference 2"],
      "key_overlaps": ["overlap 1", "overlap 2"]
    }}
  ],
  "points_of_differentiation": [
    "What makes this proposal distinct from existing work (list 3-5 points)"
  ],
  "recommendations": [
    "Actionable recommendations for strengthening the uniqueness argument (list 2-4 points)"
  ]
}}

Evaluate EVERY publication listed above. Be specific about overlaps and differences. \
Consider the sponsoring branch for NAVY_UNIQUE determinations."""


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
