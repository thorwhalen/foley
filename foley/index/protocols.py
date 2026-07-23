"""Structural contracts for the foley index (the retrieval boundary).

These three ``Protocol``s are the small, swappable seams report 04 §6.2 calls for:
keep the boundary as *protocols*, give each a zero-config sensible default, and
let every piece be replaced by keyword injection. They are the SSOT for the
Index-stage contracts (report 10 §4.2) and are deliberately kept here, separate
from any concrete backend, so the façade (:mod:`foley.index.library`) and the
search logic (:mod:`foley.index.search`) depend only on the interface — never on
``torch`` / ``lancedb`` / ``sqlite_vec``.

    * :class:`Embedder`     — the joint text<->audio space (CLAP default).
    * :class:`VectorIndex`  — approximate-nearest-neighbour over embeddings.
    * :class:`KeywordIndex` — BM25 / full-text over tags + caption.

A single backend object may satisfy *both* index protocols at once (LanceDB holds
the vector column and the FTS index in one table); the façade simply passes it as
both ``vindex`` and ``kindex``.

This module is stdlib-only: ``ndarray`` appears solely in annotations, imported
under ``TYPE_CHECKING`` so ``import foley.index.protocols`` never pulls numpy.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Protocol, Union, runtime_checkable

if TYPE_CHECKING:  # pragma: no cover - typing only, never imported at runtime
    from numpy import ndarray


@runtime_checkable
class Embedder(Protocol):
    """A joint text<->audio embedding space (CLAP by default).

    One space serves both text->audio search (``embed_text`` a query) and
    audio<->audio similarity (``embed_audio`` a clip). Implementations MUST
    return **L2-normalized** ``float32`` arrays so a plain inner product is
    cosine similarity, and MUST stamp ``model_id``/``dim`` so mixed-model
    libraries stay coherent (each :class:`~foley.base.SoundRecord` records the
    ``embedding_model``/``embedding_dim`` it was indexed under).

    Attributes:
        model_id: The checkpoint id (e.g. ``'laion/larger_clap_general'``).
        dim: The embedding dimensionality (e.g. ``512``).
    """

    model_id: str
    dim: int

    def embed_text(self, text: Union[str, list[str]]) -> "ndarray":
        """Embed one or more query strings.

        Args:
            text: A single string or a list of strings.

        Returns:
            A 2-D ``(n_texts, dim)`` L2-normalized ``float32`` array (``n_texts``
            is ``1`` for a single string) — always 2-D so callers can index
            ``[0]`` for the single-query case.
        """

    def embed_audio(self, wav: "ndarray", sr: int) -> "ndarray":
        """Embed one audio clip.

        Args:
            wav: A working-array clip (``float32``, mono preferred). CLAP expects
                48 kHz; implementations resample as needed.
            sr: The clip's sample rate in Hz.

        Returns:
            A 1-D ``(dim,)`` L2-normalized ``float32`` array.
        """


@runtime_checkable
class VectorIndex(Protocol):
    """Approximate-nearest-neighbour store over embedding vectors.

    The default is LanceDB (report 04 §2); Qdrant/pgvector/sqlite-vec bind the
    same protocol behind the scenes. ``where`` is an optional metadata push-down
    the façade may pass; a backend that cannot push filters down MAY ignore it
    (the façade over-fetches and post-filters to stay correct either way).
    """

    def upsert(self, id: str, vector: "ndarray", meta: dict) -> None:
        """Insert or replace the vector (and light metadata) for ``id``."""

    def knn(
        self, vector: "ndarray", k: int, *, where: Optional[dict] = None
    ) -> list[tuple[str, float]]:
        """Return the ``k`` nearest ids to ``vector``, most-similar first.

        Args:
            vector: A ``(dim,)`` query vector (already L2-normalized).
            k: Number of neighbours to return.
            where: Optional metadata predicates for push-down filtering.

        Returns:
            ``[(id, cosine_similarity), ...]`` in descending-similarity order.
        """

    def get_vector(self, id: str) -> "Optional[ndarray]":
        """Return the stored vector for ``id`` (or ``None`` if absent).

        Needed by ``SoundLibrary.similar`` (fetch a sound's own vector, then run
        :meth:`knn`) and by the optional CLAP rerank (score keyword-only hits).
        """


@runtime_checkable
class KeywordIndex(Protocol):
    """BM25 / full-text index over each sound's tags + caption.

    The default is LanceDB's Tantivy FTS (report 04 §3.4); SQLite FTS5 is the
    single-file fallback. Same ``where`` push-down contract as
    :class:`VectorIndex`.
    """

    def index(self, id: str, text: str, meta: dict) -> None:
        """Insert or replace the searchable text (and light metadata) for ``id``."""

    def bm25(
        self, query: str, k: int, *, where: Optional[dict] = None
    ) -> list[tuple[str, float]]:
        """Return the top-``k`` BM25 matches for ``query``, best first.

        Args:
            query: A natural-language / keyword query.
            k: Number of matches to return.
            where: Optional metadata predicates for push-down filtering.

        Returns:
            ``[(id, bm25_score), ...]`` in descending-score order.
        """
