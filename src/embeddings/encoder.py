"""Embedding model loading and encoding for scientific documents."""

from __future__ import annotations

import logging

import numpy as np
from sentence_transformers import SentenceTransformer

from src.config import (
    DEFAULT_EMBEDDING_MODEL,
    EMBEDDING_MODEL,
    FALLBACK_EMBEDDING_MODEL,
    SPECTER2_ADAPTER,
)
from src.models import Publication, UserProposal

logger = logging.getLogger(__name__)

_model: SentenceTransformer | None = None


def get_model() -> SentenceTransformer:
    """Load the embedding model (cached singleton)."""
    global _model
    if _model is not None:
        return _model

    model_name = EMBEDDING_MODEL
    try:
        logger.info("Loading embedding model: %s", model_name)
        if model_name == DEFAULT_EMBEDDING_MODEL:
            # SPECTER2 with proximity adapter
            _model = SentenceTransformer(model_name)
            try:
                _model.load_adapter(SPECTER2_ADAPTER)
                logger.info("Loaded SPECTER2 proximity adapter")
            except Exception as e:
                logger.warning("Could not load SPECTER2 adapter: %s", e)
        else:
            _model = SentenceTransformer(model_name)
        logger.info("Model loaded successfully")
    except Exception as e:
        logger.warning("Failed to load %s: %s. Falling back to MiniLM.", model_name, e)
        model_name = FALLBACK_EMBEDDING_MODEL
        _model = SentenceTransformer(model_name)

    return _model


def format_proposal_text(proposal: UserProposal) -> str:
    """Format a proposal into a single text string for embedding."""
    parts = [proposal.title]
    description = proposal.topic_description or proposal.abstract
    if description:
        parts.append(description)
    if proposal.keywords:
        parts.append("Keywords: " + ", ".join(proposal.keywords))
    if proposal.additional_context:
        parts.append(proposal.additional_context)
    return " ".join(parts)


def format_publication_text(pub: Publication) -> str:
    """Format a publication into a single text string for embedding."""
    parts = [pub.title]
    abstract = pub.best_abstract
    if abstract:
        parts.append(abstract)
    return " ".join(parts)


def encode_proposal(proposal: UserProposal) -> np.ndarray:
    """Encode a research proposal into an embedding vector."""
    model = get_model()
    text = format_proposal_text(proposal)
    return model.encode([text], normalize_embeddings=True)[0]


def encode_publications(publications: list[Publication]) -> np.ndarray:
    """Encode a list of publications into embedding vectors."""
    model = get_model()
    texts = [format_publication_text(pub) for pub in publications]
    if not texts:
        return np.array([])
    return model.encode(texts, normalize_embeddings=True, show_progress_bar=True)
