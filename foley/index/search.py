"""Hybrid retrieval: reciprocal rank fusion over a vector list and a keyword list.

Pure orchestration + fusion. This module depends only on the small index
protocols (:mod:`foley.index.protocols`) — never on ``torch``/``lancedb``/
``sqlite_vec`` — so the fusion rule is one SSOT exercised identically by every
backend and directly unit-testable.

Why rank fusion (report 04 §3.2): dense CLAP cosine lives in ``[-1, 1]`` while
BM25 scores are unbounded, so **averaging them lets one drown the other**.
**Reciprocal Rank Fusion** (RRF; Cormack, Clarke & Büttcher, SIGIR 2009) instead
fuses on *rank position*::

    score(d) = Σ_rankers  1 / (k + rank_r(d))          # k = 60 (standard)

A document ranked high by *either* the vector list or the BM25 list floats up;
``k=60`` damps the long tail. It is one line, parameter-light, and robust — the
right first-stage fusion for a mix of semantic captions and terse literal tags.

The concrete backends (LanceDB, sqlite-vec) can fuse natively in-engine; foley
deliberately fuses here instead so the ranking is byte-identical across backends
and gated by the eval harness (report 08) rather than an engine's internals.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:  # pragma: no cover - typing only
    from numpy import ndarray

    from .protocols import Embedder, KeywordIndex, VectorIndex

#: Standard RRF damping constant (Cormack et al., SIGIR 2009). Larger => flatter.
RRF_K: int = 60

#: Per-ranker shortlist depth pulled from each index before fusion. Fusing deeper
#: lists than the requested ``k`` lets a doc ranked mid-list by one ranker but top
#: by the other still surface.
DEFAULT_CANDIDATE_K: int = 50


@dataclass(frozen=True)
class FusedHit:
    """One fused retrieval hit: an id plus the scores that produced it.

    The raw component scores are carried through (not just the fused rank score)
    so the façade can stamp them onto a :class:`~foley.base.Candidate`
    (``clap_score`` / ``bm25_score`` / ``rrf_score``) for display and debugging.

    Attributes:
        id: The sound id.
        rrf_score: The fused RRF score (``None`` for a pure-vector search).
        clap_score: Cosine similarity from the vector ranker (``None`` if the id
            appeared only in the keyword list).
        bm25_score: BM25 score from the keyword ranker (``None`` if the id
            appeared only in the vector list).
    """

    id: str
    rrf_score: Optional[float] = None
    clap_score: Optional[float] = None
    bm25_score: Optional[float] = None


def reciprocal_rank_fusion(
    ranked_id_lists: "list[list[str]]", *, k: int = RRF_K
) -> "list[tuple[str, float]]":
    """Fuse several ranked id lists into one, by reciprocal rank.

    Args:
        ranked_id_lists: Each element is a list of ids in descending-relevance
            order (best first). Lists may overlap and may differ in length.
        k: The RRF damping constant (default :data:`RRF_K` = 60).

    Returns:
        ``[(id, fused_score), ...]`` sorted by fused score descending, ties
        broken by ``id`` ascending (so the fusion is fully deterministic).
    """
    scores: dict[str, float] = {}
    for ids in ranked_id_lists:
        for rank, id_ in enumerate(ids, start=1):
            scores[id_] = scores.get(id_, 0.0) + 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))


def fuse_hits(
    vector_hits: "list[tuple[str, float]]",
    keyword_hits: "list[tuple[str, float]]",
    *,
    k: int,
    rrf_k: int = RRF_K,
) -> "list[FusedHit]":
    """RRF-fuse a vector ranker's hits with a keyword ranker's hits.

    Args:
        vector_hits: ``[(id, cosine_similarity), ...]`` best-first (from
            :meth:`~foley.index.protocols.VectorIndex.knn`).
        keyword_hits: ``[(id, bm25_score), ...]`` best-first (from
            :meth:`~foley.index.protocols.KeywordIndex.bm25`).
        k: Number of fused hits to return.
        rrf_k: The RRF damping constant.

    Returns:
        The top-``k`` :class:`FusedHit`s, each carrying its raw component scores.
    """
    clap = dict(vector_hits)
    bm25 = dict(keyword_hits)
    fused = reciprocal_rank_fusion(
        [[i for i, _ in vector_hits], [i for i, _ in keyword_hits]], k=rrf_k
    )
    return [
        FusedHit(id=i, rrf_score=s, clap_score=clap.get(i), bm25_score=bm25.get(i))
        for i, s in fused[:k]
    ]


def hybrid_search(
    query: str,
    *,
    embedder: "Embedder",
    vindex: "VectorIndex",
    kindex: "KeywordIndex",
    k: int = 10,
    candidate_k: int = DEFAULT_CANDIDATE_K,
    rrf_k: int = RRF_K,
    where: Optional[dict] = None,
) -> "list[FusedHit]":
    """Embed ``query``, run the vector + keyword rankers, and RRF-fuse them.

    Args:
        query: The natural-language query.
        embedder: Text<->audio embedder (its ``embed_text`` produces the query
            vector).
        vindex: The vector index (CLAP KNN).
        kindex: The keyword index (BM25).
        k: Number of fused results to return.
        candidate_k: Shortlist depth pulled from each ranker before fusion.
        rrf_k: The RRF damping constant.
        where: Optional metadata push-down passed to both rankers.

    Returns:
        The top-``k`` fused :class:`FusedHit`s.
    """
    qvec = embedder.embed_text(query)[0]  # (dim,) — embed_text always returns 2-D
    vhits = vindex.knn(qvec, candidate_k, where=where)
    khits = kindex.bm25(query, candidate_k, where=where)
    return fuse_hits(vhits, khits, k=k, rrf_k=rrf_k)


def vector_search(
    qvec: "ndarray",
    *,
    vindex: "VectorIndex",
    k: int = 10,
    where: Optional[dict] = None,
) -> "list[FusedHit]":
    """Pure audio<->audio (or clip->library) vector search — no keyword leg.

    Used by ``SoundLibrary.similar`` and by searching with a reference clip.
    Hits keep their cosine similarity in ``clap_score`` and preserve the index's
    own descending-similarity order (``rrf_score`` is left ``None`` — there is no
    fusion).

    Args:
        qvec: An already-L2-normalized ``(dim,)`` query vector.
        vindex: The vector index.
        k: Number of neighbours to return.
        where: Optional metadata push-down.

    Returns:
        Up to ``k`` :class:`FusedHit`s in descending-similarity order.
    """
    return [FusedHit(id=i, clap_score=s) for i, s in vindex.knn(qvec, k, where=where)]
