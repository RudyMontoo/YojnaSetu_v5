"""
embeddings.py — local all-MiniLM-L6-v2 embeddings (384-dim), matching the
vector store spec in CLAUDE.md / the v5.0 doc. Same model ingest.py already
used for ChromaDB — reused here so migrated Mongo scheme embeddings are
directly comparable to anything already indexed.

No API key needed: sentence-transformers downloads and runs the model
locally, same as today's ChromaDB path.
"""
import os
from functools import lru_cache

import numpy as np

MODEL_NAME = "all-MiniLM-L6-v2"

# Keep transformers away from TensorFlow. We only ever run this model through
# torch, but `transformers` probes for a TF backend on import, and if the
# installed tensorflow was built against a newer protobuf than the one
# resolved at runtime, that probe raises:
#
#   VersionError: Detected incompatible Protobuf Gencode/Runtime versions ...
#                 gencode 6.31.1 runtime 5.29.6
#
# which surfaces as every single embed_text() call failing — silently taking
# down scheme migration, vector search and Agent 1 eligibility with it, for a
# backend we do not use. Confirmed against this repo's own environment, where
# migrate_schemes inserted 0 of ~445 schemes until this was set.
#
# setdefault, not assignment: an operator who deliberately exports USE_TF
# keeps control.
os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("TRANSFORMERS_NO_TF", "1")


@lru_cache(maxsize=1)
def _model():
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(MODEL_NAME)


def embed_text(text: str) -> list[float]:
    vec = _model().encode(text, normalize_embeddings=True)
    return vec.tolist()


def embed_batch(texts: list[str]) -> list[list[float]]:
    vecs = _model().encode(texts, normalize_embeddings=True, batch_size=32, show_progress_bar=False)
    return vecs.tolist()


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Both vectors are pre-normalized by embed_text, so this is a plain dot product."""
    return float(np.dot(a, b))
