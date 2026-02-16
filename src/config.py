"""Configuration constants and settings."""

import os

# DTIC Dimensions URLs
DTIC_BASE_URL = "https://dtic.dimensions.ai"
DTIC_SEARCH_URL = f"{DTIC_BASE_URL}/discover/publication/results.json"
DTIC_DETAIL_URL = f"{DTIC_BASE_URL}/details/publication"

# Search parameters
SEARCH_MODE = "content"
SEARCH_TYPE = "kws"
SEARCH_FIELD = "full_search"

# Scraping behavior
REQUEST_DELAY_SECONDS = 2.0
MAX_PAGES = 5
DETAIL_FETCH_TOP_N = 50
USER_AGENT = (
    "DTIC-Uniqueness-Analyzer/0.1 "
    "(Research Proposal Uniqueness Assessment Tool; "
    "respectful automated access; contact: github.com/dtic-crawl)"
)

# Embedding models
DEFAULT_EMBEDDING_MODEL = "allenai/specter2_aug2023refresh"
SPECTER2_ADAPTER = "allenai/specter2_proximity"
FALLBACK_EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL)

# Similarity thresholds
SIMILARITY_TOP_K = 20
SIMILARITY_THRESHOLD = 0.3

# Overlap rating thresholds (cosine similarity)
OVERLAP_HIGH_THRESHOLD = 0.60
OVERLAP_MEDIUM_THRESHOLD = 0.45

# LLM settings
LLM_MODEL = "claude-sonnet-4-5-20250929"
LLM_MAX_TOKENS = 4096

# Military branch detection patterns
BRANCH_PATTERNS: dict[str, list[str]] = {
    "navy": [
        "naval", "onr", "office of naval research", "nrl",
        "naval research laboratory", "n00014", "navy",
    ],
    "army": [
        "aro", "arl", "army research office", "army research laboratory",
        "w911nf", "army",
    ],
    "air_force": [
        "afosr", "afrl", "air force office of scientific research",
        "air force research laboratory", "fa8650", "fa9550", "air force",
    ],
    "darpa": ["darpa", "defense advanced research projects agency", "hr0011"],
    "dod": ["dod", "department of defense", "osd"],
    "marine_corps": ["marine corps", "usmc", "marines"],
    "space_force": ["space force", "ussf"],
}

# Report output
DEFAULT_OUTPUT_DIR = "reports"
