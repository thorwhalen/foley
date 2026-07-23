"""Shared fixtures for the foley test suite.

The star is :class:`FakeEmbedder` — a deterministic hashing bag-of-words
embedder. It lets the entire hybrid-search + library path be tested with only
``numpy`` (no ``torch``/CLAP, no model download): two texts that share a token
share a dimension, so cosine similarity behaves plausibly, and results are
reproducible across runs (a stable ``hashlib`` hash, not the salted builtin).
"""

import hashlib

import pytest

try:  # numpy is a test-extra dep; the pure tests (search, taxonomy) don't need it
    import numpy as np
except ImportError:  # pragma: no cover
    np = None


class FakeEmbedder:
    """Deterministic hashing bag-of-words embedder (a CLAP stand-in for tests)."""

    model_id = "fake/bow"
    dim = 64

    def __init__(self, *, dim: int = 64):
        self.dim = dim

    def _vec(self, text: str):
        import re

        vec = np.zeros(self.dim, dtype=np.float32)
        for tok in re.findall(r"[a-z0-9]+", text.lower()):
            digest = hashlib.md5(tok.encode()).digest()
            idx = int.from_bytes(digest[:4], "little") % self.dim
            vec[idx] += 1.0
        norm = float(np.linalg.norm(vec))
        return vec / norm if norm else vec

    def embed_text(self, text):
        if isinstance(text, str):
            text = [text]
        return np.stack([self._vec(t) for t in text]).astype(np.float32)

    def embed_audio(self, wav, sr):
        # Deterministic per-content vector: distinct clips embed to distinct
        # points (so ingest tests get non-degenerate vectors), reproducibly.
        arr = np.ascontiguousarray(np.asarray(wav, dtype=np.float32))
        seed = int.from_bytes(hashlib.md5(arr.tobytes()).digest()[:4], "little")
        rng = np.random.default_rng(seed)
        vec = rng.standard_normal(self.dim).astype(np.float32)
        norm = float(np.linalg.norm(vec))
        return vec / norm if norm else vec


@pytest.fixture
def fake_embedder():
    """A fresh :class:`FakeEmbedder` (dim=64)."""
    if np is None:  # pragma: no cover
        pytest.skip("numpy required")
    return FakeEmbedder()
