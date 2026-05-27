"""Embedding function wrapper.

We try to use sentence-transformers (best quality, downloads ~80 MB on
first run). If that import fails or the network is unavailable, we fall
back to a deterministic hashing embedder so the service still starts and
returns *some* relevance ordering for the demo.
"""

from __future__ import annotations

import hashlib
import math
from typing import Sequence

from .config import settings

_EMBED_DIM = 384  # MiniLM dim; matched by the fallback


class _HashingFallback:
    """Deterministic, dependency-free fallback embedder (cosine-safe)."""

    name = "hashing-fallback"

    def __init__(self, dim: int = _EMBED_DIM):
        self.dim = dim

    def _vec(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        for token in text.lower().split():
            h = hashlib.sha1(token.encode("utf-8")).digest()
            for i in range(self.dim):
                byte = h[i % len(h)]
                vec[i] += (byte - 127) / 128.0
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]

    def __call__(self, input: Sequence[str]) -> list[list[float]]:
        return [self._vec(t) for t in input]


class _SentenceTransformerEmbedder:
    name = "sentence-transformers"

    def __init__(self, model_name: str):
        from sentence_transformers import SentenceTransformer
        self.model = SentenceTransformer(model_name)

    def __call__(self, input: Sequence[str]) -> list[list[float]]:
        embeddings = self.model.encode(list(input), normalize_embeddings=True)
        return [e.tolist() for e in embeddings]


def build_embedder():
    """Construct the embedder with graceful fallback."""
    try:
        return _SentenceTransformerEmbedder(settings.embedding_model)
    except Exception as exc:
        print(
            f"[rag-service] sentence-transformers unavailable ({exc!r}); "
            "falling back to hashing embedder."
        )
        return _HashingFallback()
