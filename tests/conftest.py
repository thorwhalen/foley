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


# ---------------------------------------------------------------------------
# Spend + network isolation (#58): no test may reach a paid API by accident
# ---------------------------------------------------------------------------

#: Opt-in for tests that really call a provider (also needs the key itself).
LIVE_API_TESTS_ENV = "FOLEY_LIVE_API_TESTS"

#: foley's own env switches that change which provider or posture a default resolves to.
_FOLEY_POSTURE_ENV = ("FOLEY_LLM", "FOLEY_LLM_BASE_URL", "FOLEY_OFFLINE")


def live_api_tests_enabled() -> bool:
    """Whether the developer opted in to live-API tests (``FOLEY_LIVE_API_TESTS=1``)."""
    import os

    return os.environ.get(LIVE_API_TESTS_ENV, "").lower() in ("1", "true", "yes")


class NetworkBlocked(RuntimeError):
    """Raised by the test-suite socket guard when a test opens a non-loopback connection."""


def _is_loopback(address) -> bool:
    host = address[0] if isinstance(address, tuple) else address
    return isinstance(host, str) and (
        host in ("localhost", "::1", "0.0.0.0") or host.startswith("127.")
    )


@pytest.fixture(autouse=True)
def _isolate_from_paid_apis(monkeypatch):
    """Scrub every provider key + posture switch and block outbound sockets.

    Unless ``FOLEY_LIVE_API_TESTS=1``: the keys come from
    :func:`foley.requirements.provider_key_env_vars` (the sources' ``auth`` SSOT), so a
    new paid source is covered without editing this file. A test that needs a key sets
    it with ``monkeypatch.setenv`` after this fixture has run.
    """
    if live_api_tests_enabled():
        yield
        return
    import socket

    from foley.requirements import provider_key_env_vars

    for name in (*provider_key_env_vars(), *_FOLEY_POSTURE_ENV):
        monkeypatch.delenv(name, raising=False)

    real_connect = socket.socket.connect

    def guarded_connect(self, address):
        if not _is_loopback(address):
            raise NetworkBlocked(
                f"test tried to connect to {address!r}; set {LIVE_API_TESTS_ENV}=1 "
                "to allow live-API tests"
            )
        return real_connect(self, address)

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
    yield
