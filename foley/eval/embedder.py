"""A deterministic, numpy-only text embedder for the retrieval eval gate.

:class:`HashingBowEmbedder` is a hashing bag-of-words text embedder — the
shippable sibling of the test suite's ``FakeEmbedder``. It exists so the nDCG PR
gate is **deterministic and CLAP-free**: unlike ``FakeEmbedder``'s random
``embed_audio`` (whose content-noise vectors make RRF rankings platform-dependent
— the flakiness documented in ``tests/test_bootstrap.py``), the eval harness
*injects* ``embed_text(caption + tags)`` as each clip's vector, so both search
legs (vector cosine and BM25) carry the same caption bag-of-words. Every golden
query then shares 2–3 tokens with its answer clip → integer rank-1 in both legs →
a bit-exact, cross-platform-stable nDCG.

It is a text-only embedder: ``embed_audio`` is intentionally unimplemented (the
gate never calls it — vectors are injected via
:meth:`foley.index.library.SoundLibrary.add`).
"""

from __future__ import annotations

import hashlib
import re

#: Default embedding width (matches the test ``FakeEmbedder`` for parity).
DEFAULT_DIM = 64

_TOKEN_RE = re.compile(r"[a-z0-9]+")


class HashingBowEmbedder:
    """Deterministic hashing bag-of-words text embedder (L2-normalized).

    Two texts sharing a token share a dimension, so cosine similarity tracks
    lexical overlap — plausible *and* reproducible (a stable ``hashlib`` hash,
    never the salted builtin ``hash``). Suitable only for the eval gate /
    offline retrieval regression; real retrieval uses CLAP.
    """

    model_id = "foley-eval/hashing-bow-v1"

    def __init__(self, *, dim: int = DEFAULT_DIM):
        self.dim = dim

    def _vec(self, text: str):
        import numpy as np

        vec = np.zeros(self.dim, dtype="float32")
        for tok in _TOKEN_RE.findall(text.lower()):
            digest = hashlib.md5(tok.encode()).digest()
            vec[int.from_bytes(digest[:4], "little") % self.dim] += 1.0
        norm = float(np.linalg.norm(vec))
        return vec / norm if norm else vec

    def embed_text(self, text):
        """Embed ``text`` (or a list of texts) -> a ``(n, dim)`` float32 array."""
        import numpy as np

        texts = [text] if isinstance(text, str) else list(text)
        return np.stack([self._vec(t) for t in texts]).astype("float32")

    def embed_audio(self, wav, sr):  # noqa: D102 - intentionally unimplemented
        raise NotImplementedError(
            "HashingBowEmbedder is text-only: the eval harness injects clip "
            "vectors via SoundLibrary.add(vector=...). Use a CLAP embedder for "
            "audio embedding."
        )
