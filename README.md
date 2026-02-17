---
title: Uncharted Waters
emoji: 🌊
colorFrom: gray
colorTo: yellow
sdk: docker
app_port: 7860
pinned: false
---

# Uncharted Waters

Automated research landscape analysis against the [DTIC Dimensions](https://dtic.dimensions.ai) database. Describe a research area and get back a structured assessment of what already exists, what's missing, and where the opportunities are.

**[Try it live on HuggingFace Spaces](https://huggingface.co/spaces/that-github-user/uncharted-waters)**

## How It Works

The pipeline runs four stages:

1. **Search** — Multiple query strategies scan the DTIC Dimensions publication database, deduplicating across result sets
2. **Embed** — Publications and the research topic are encoded with [nomic-embed-text-v1.5](https://huggingface.co/nomic-ai/nomic-embed-text-v1.5) using asymmetric retrieval prefixes (`search_query:` / `search_document:`)
3. **Score** — Similarity is computed as the geometric mean of holistic embedding similarity and IDF-weighted per-keyword concept scores. Keywords that appear in many results (generic terms) are down-weighted; rare, specific keywords carry more signal. This prevents a general survey paper from inflating overlap when the research topic is a specific multi-concept intersection
4. **Assess** — Claude analyzes the scored results and generates a landscape report with comparisons, gaps, and recommendations. The verdict and confidence are computed deterministically from scores and branch data — the LLM provides narrative, not metrics

## Verdicts

| Verdict | Meaning |
|---------|---------|
| **Open Landscape** | No substantially similar work found |
| **Branch Opportunity** | Similar work exists but funded by other branches |
| **Well Covered** | Very similar existing work found in the same branch |
| **Mixed Coverage** | Partial overlap — requires expert judgment |

## Development

```bash
# Clone and install (CPU-only PyTorch saves ~1.5GB)
git clone https://github.com/that-github-user/uncharted-waters.git
cd uncharted-waters
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements-dev.txt

# Configure
cp .env.example .env
# Edit .env — set ANTHROPIC_API_KEY

# Run locally
uvicorn src.api:app --reload
# → http://localhost:8000

# Run tests (all mock HTTP, no API key needed)
pytest tests/ -v
```

## Cost

Each analysis run uses approximately $0.02–0.05 in Anthropic API usage (Claude Sonnet).
