# DTIC Uniqueness Analyzer

Automated uniqueness assessment for defense research proposals against the [DTIC Dimensions](https://dtic.dimensions.ai) database.

Researchers preparing defense R&D proposals often need to survey existing work in DTIC to understand how their project fits into the broader landscape. This tool automates that literature search — it finds semantically similar publications, identifies which military branches have funded related work, and generates a structured assessment report.

## How It Works

1. **You describe your research** (title, abstract, keywords, military branch)
2. **The tool searches DTIC** using multiple query strategies
3. **Publications are ranked** by semantic similarity using SPECTER2 embeddings
4. **Claude analyzes the results** and generates a verdict with detailed comparisons

### Verdicts

| Verdict | Meaning |
|---------|---------|
| **UNIQUE** | No substantially similar work found in DTIC |
| **NAVY_UNIQUE** | Similar work exists but was funded by other branches, not Navy |
| **AT_RISK** | Very similar existing work found — uniqueness may be hard to demonstrate |
| **NEEDS_REVIEW** | Ambiguous results requiring human expert judgment |

## Usage: GitHub Actions (Recommended)

This is designed to run via GitHub Actions `workflow_dispatch`. Fork the repo, add your API key, and trigger from the Actions tab.

### Setup

1. **Fork this repository** (or use as a template)
2. **Add your Anthropic API key** as a repository secret:
   - Go to Settings > Secrets and variables > Actions
   - Add a new secret named `ANTHROPIC_API_KEY`
3. **Trigger the workflow**:
   - Go to Actions > "DTIC Uniqueness Analysis"
   - Click "Run workflow"
   - Fill in your proposal details
   - Click "Run workflow"
4. **Get your report**:
   - The workflow summary shows a quick verdict
   - Download the full Markdown report from the workflow artifacts

### Security Notes

- **Your API key** is stored as a GitHub Secret — it is never exposed in logs or code
- **Your proposal text** is visible in the workflow run inputs (GitHub Actions limitation). If your proposal is sensitive/pre-decisional, use a **private fork** or run locally instead
- **The source code** contains no secrets — it's safe to keep the repo public
- **DTIC data** is publicly accessible; the tool only reads public publications

### Cost

Each analysis run costs approximately **$0.02–0.05** in Anthropic API usage (Claude Sonnet).

## Usage: Local

### Prerequisites

- Python 3.11+
- An [Anthropic API key](https://console.anthropic.com/)

### Install

```bash
# Clone the repo
git clone https://github.com/YOUR_USERNAME/dtic-crawl.git
cd dtic-crawl

# Install CPU-only PyTorch (saves ~1.5GB vs full CUDA build)
pip install torch --index-url https://download.pytorch.org/whl/cpu

# Install dependencies
pip install -r requirements.txt

# Set your API key
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY
```

### CLI

```bash
python -m src.cli \
  --title "Autonomous Underwater Vehicle Navigation Using Quantum Sensors" \
  --abstract "This research proposes developing a novel navigation system..." \
  --keywords "AUV, quantum sensing, inertial navigation" \
  --branch navy \
  --output reports/
```

### Web UI (Local)

```bash
# Set ANTHROPIC_API_KEY in environment or .env
uvicorn src.api:app --reload
# Open http://localhost:8000
```

## Configuration

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `ANTHROPIC_API_KEY` | (required) | Your Anthropic API key |
| `EMBEDDING_MODEL` | `allenai/specter2_aug2023refresh` | Embedding model to use |

Set `EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2` for a smaller/faster model (~80MB vs ~440MB).

## Project Structure

```
src/
├── cli.py              # CLI entry point
├── pipeline.py         # Orchestrates the full analysis flow
├── api.py              # FastAPI web interface
├── config.py           # Configuration constants
├── models.py           # Pydantic data models
├── scraper/
│   ├── base.py         # PublicationSource ABC
│   └── dimensions.py   # DTIC Dimensions scraper
├── embeddings/
│   ├── encoder.py      # SPECTER2 / MiniLM encoding
│   └── similarity.py   # Cosine similarity ranking
└── analysis/
    ├── prompts.py      # LLM prompt templates
    ├── llm_client.py   # Claude API wrapper
    └── report.py       # Markdown report generation
```

## Running Tests

```bash
pip install -r requirements-dev.txt
pytest tests/
```

## Limitations

- DTIC Dimensions abstracts may be truncated in search results; the tool fetches full abstracts from detail pages for top candidates
- The scraper respects rate limits (2s delay between requests) — a full run takes 2–5 minutes
- Embedding similarity is a heuristic; the LLM analysis provides the nuanced assessment
- Verdicts are advisory — always review with a subject matter expert before submission
