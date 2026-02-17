---
title: Uncharted Waters
emoji: 🌊
colorFrom: gray
colorTo: yellow
sdk: docker
app_port: 7860
pinned: false
---

# Uncharted Waters — DTIC Research Landscape Explorer

Explore the defense research landscape against the [DTIC Dimensions](https://dtic.dimensions.ai) database. Describe a general research topic and the tool searches DTIC, ranks similar publications by semantic similarity (SPECTER2), and uses Claude to generate a landscape assessment.

## Verdicts

| Verdict | Meaning |
|---------|---------|
| **UNIQUE** | Open landscape — no substantially similar work found |
| **NAVY_UNIQUE** | Branch opportunity — similar work funded by other branches |
| **AT_RISK** | Well covered — very similar existing work found |
| **NEEDS_REVIEW** | Mixed coverage — requires human expert judgment |

## Live Demo

The app is deployed on [HuggingFace Spaces](https://huggingface.co/spaces). Access requires a shared access code.

## Deploy Your Own

### HuggingFace Spaces (recommended)

1. **Create a Space** at [huggingface.co/new-space](https://huggingface.co/new-space) — select **Docker** as the SDK
2. **Generate a write token** at [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens)
3. **Add GitHub secrets** in your fork's Settings > Secrets and variables > Actions:
   - `HF_TOKEN` — your HuggingFace write token
4. **Add GitHub variable**:
   - `HF_SPACE_ID` — e.g. `username/uncharted-waters`
5. **Add HF Space secrets** (in the Space's Settings tab):
   - `ANTHROPIC_API_KEY` — your Anthropic API key
   - `ACCESS_CODE` — a shared code for gated access

Pushes to `master`/`main` automatically deploy via the `deploy-hf.yml` workflow.

### Local

```bash
git clone https://github.com/that-github-user/uncharted-waters.git
cd uncharted-waters

# CPU-only PyTorch (saves ~1.5GB)
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt

cp .env.example .env
# Edit .env — set ANTHROPIC_API_KEY (ACCESS_CODE is optional locally)

uvicorn src.api:app --reload
# Open http://localhost:8000
```

### CLI

```bash
python -m src.cli \
  --title "Autonomous Underwater Vehicle Navigation Using Quantum Sensors" \
  --topic "General description of the research area..." \
  --keywords "AUV, quantum sensing, inertial navigation" \
  --branch navy \
  --output reports/
```

## Configuration

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `ANTHROPIC_API_KEY` | (required) | Your Anthropic API key |
| `EMBEDDING_MODEL` | `allenai/specter2_aug2023refresh` | Embedding model to use |
| `ACCESS_CODE` | (unset) | Shared access code; unset = no gate |

## Running Tests

```bash
pip install -r requirements-dev.txt
pytest tests/ -v
```

Tests run automatically on push/PR via the `ci.yml` workflow. All tests mock HTTP — no API keys needed.

## Cost

Each analysis run costs approximately **$0.02-0.05** in Anthropic API usage (Claude Sonnet).
