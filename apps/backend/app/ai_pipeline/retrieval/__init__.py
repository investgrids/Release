"""Importing this package registers every retriever module as a side effect."""
from __future__ import annotations

from app.ai_pipeline.retrieval import (  # noqa: F401
    company_retriever,
    event_retriever,
    historical_similarity_retriever,
    intelligence_graph_retriever,
    intelligence_publishing_retriever,
    macro_retriever,
    market_retriever,
    news_retriever,
    quant_signal_retriever,
    ripple_retriever,
)
